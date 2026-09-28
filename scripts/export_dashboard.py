#!/usr/bin/env python3
"""Merge pipeline outputs into one static JSON bundle for the dashboard.

Usage:
    python3 scripts/export_dashboard.py
    python3 scripts/export_dashboard.py --out-dir /tmp/bundle

Reads (no BigQuery, no Gemini):
    data/cards/, data/cards_gemini_en/, data/cards_gemini_it/, data/series/
    data/stats.json, data/base_rate.json, data/count.json
    data/tape_all.csv        (company history; if missing, companies/ is left as is)
    data/company_prices.csv  (company price chart; optional)

Writes web/public/data/ — see data/SCHEMA.md for the shape of each file.
Stdlib, Python 3.9.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from classify import PRIORITY as NEWS_TYPES, classify  # noqa: E402
from verdict import verdict  # noqa: E402
from story_selection import (  # noqa: E402
    catalog_from_rows,
    deduplicate_stories,
    filter_valid_stories,
    story_matches_catalog,
)

SCHEMA_VERSION = "1.0"
DATA = ROOT / "data"
OUT_DIR = ROOT / "web" / "public" / "data"
TAPE_CSV = DATA / "tape_all.csv"
PRICES_CSV = DATA / "company_prices.csv"
LAST_PRICE_DATE = "2026-09-23"
LANGS = ("en", "it")

STATUS_META = [
    {
        "status": "NO_REACTION",
        "group": "none",
        "color": "neutral",
        "hex": "#9CA3AF",
        "label_en": "No reaction",
        "label_it": "Nessuna reazione",
        "explain_en": "No session in the window moved at least 2 times the normal daily swing.",
        "explain_it": "Nessuna seduta nella finestra si è mossa almeno il doppio dell'oscillazione normale.",
    },
    {
        "status": "ALREADY_IN_PRICE",
        "group": "before",
        "color": "danger",
        "hex": "#DC2626",
        "label_en": "Already in the price",
        "label_it": "Già nel prezzo",
        "explain_en": "The biggest unusual move closed before the article was published.",
        "explain_it": "Il movimento anomalo più ampio aveva chiuso prima della pubblicazione.",
    },
    {
        "status": "PARTLY_IN_PRICE",
        "group": "before",
        "color": "warning",
        "hex": "#F59E0B",
        "label_en": "Partly in the price",
        "label_it": "In parte nel prezzo",
        "explain_en": "Some unusual move closed before publication, but the biggest one came after.",
        "explain_it": "Una parte del movimento anomalo aveva chiuso prima della pubblicazione, ma il più ampio è arrivato dopo.",
    },
    {
        "status": "MOSTLY_AT_OPEN",
        "group": "before",
        "color": "caution",
        "hex": "#EAB308",
        "label_en": "Mostly at the open",
        "label_it": "Quasi tutto in apertura",
        "explain_en": "The article came out during trading, and more than half of the day's move was already in the opening price.",
        "explain_it": "L'articolo è uscito a mercato aperto e più di metà del movimento del giorno era già nel prezzo di apertura.",
    },
    {
        "status": "REACTED",
        "group": "after",
        "color": "success",
        "hex": "#16A34A",
        "label_en": "Reacted",
        "label_it": "Reazione",
        "explain_en": "The biggest unusual move came on the first session trading on the story.",
        "explain_it": "Il movimento anomalo più ampio è arrivato nella prima seduta che tratta sulla notizia.",
    },
    {
        "status": "DELAYED",
        "group": "after",
        "color": "info",
        "hex": "#2563EB",
        "label_en": "Delayed",
        "label_it": "In ritardo",
        "explain_en": "The biggest unusual move came after the first session trading on the story.",
        "explain_it": "Il movimento anomalo più ampio è arrivato dopo la prima seduta che tratta sulla notizia.",
    },
]
STATUSES = [m["status"] for m in STATUS_META]
GROUPS = {
    "before": {"label_en": "Tape moved before the headline", "label_it": "Il prezzo si è mosso prima del titolo"},
    "after": {"label_en": "Tape moved after the headline", "label_it": "Il prezzo si è mosso dopo il titolo"},
    "none": {"label_en": "No unusual move", "label_it": "Nessun movimento anomalo"},
}
GEMINI_KEYS = (
    "model", "instrument_name", "title_adjective", "figure_in_body",
    "adjective_matches", "sentence", "checks",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, obj: Any, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = {"separators": (",", ":")} if compact else {"indent": 1}
    path.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, **fmt) + "\n")


def load_dir(name: str) -> Dict[str, dict]:
    d = DATA / name
    if not d.is_dir():
        return {}
    return {p.stem: read_json(p) for p in sorted(d.glob("*.json")) if p.stem != "index"}


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "company"


def _float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    f = float(v)
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _round(v: Optional[float], nd: int) -> Optional[float]:
    return None if v is None else round(v, nd)


# ---------------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------------

def gemini_block(card: Optional[dict]) -> Optional[dict]:
    g = (card or {}).get("gemini") or {}
    if not g.get("sentence"):
        return None
    return {k: g.get(k) for k in GEMINI_KEYS}


def merge_story(cid: str, plain: Optional[dict], en: Optional[dict], it: Optional[dict],
                series: Optional[dict], slug: str) -> dict:
    base = en or it or plain
    assert base is not None
    v = base["verdict"]
    tape = dict(base.get("tape") or {})
    facts_en = (en or {}).get("tape", {}).get("facts_text") or ([v["text_en"]] if v.get("text_en") else [])
    facts_it = (it or {}).get("tape", {}).get("facts_text") or ([v["text_it"]] if v.get("text_it") else [])
    tape["facts_text"] = {"en": facts_en, "it": facts_it}

    series_out = None
    if series and series.get("sessions"):
        series_out = {k: series.get(k) for k in ("baseline", "markers", "sessions")}

    return {
        "schema_version": SCHEMA_VERSION,
        "content_id": cid,
        "article": base["article"],
        "instrument": {**(base.get("instrument") or {}), "company_slug": slug},
        "news": base.get("news"),
        "verdict": v,
        "tape": tape,
        "gemini": {"en": gemini_block(en), "it": gemini_block(it)},
        "series": series_out,
    }


def story_row(s: dict) -> dict:
    v = s["verdict"]
    peak = v.get("peak") or {}
    largest = v.get("largest") or {}
    news = s.get("news") or {}
    g_en = s["gemini"]["en"] or {}
    return {
        "content_id": s["content_id"],
        "titolo": s["article"]["titolo"],
        "pub_local": s["article"].get("pub_local"),
        "url": s["article"].get("url"),
        "des_azione": s["instrument"].get("des_azione"),
        "cod_azione": s["instrument"].get("cod_azione"),
        "company_slug": s["instrument"]["company_slug"],
        "news_type": news.get("news_type"),
        "headline_reports_move": news.get("headline_reports_move"),
        "publication_phase": v.get("publication_phase"),
        "status": v["status"],
        "peak_date": peak.get("d") or largest.get("d"),
        "peak_timing": peak.get("timing") or largest.get("timing"),
        "peak_move_pct": peak.get("move_pct", largest.get("move_pct")),
        "peak_z": peak.get("z", largest.get("z")),
        "retained_pct": (s.get("tape") or {}).get("retained_pct"),
        "adjective_matches": g_en.get("adjective_matches"),
        "has_gemini": any(s["gemini"][l] for l in LANGS),
        "has_series": s["series"] is not None,
    }


def _csv_rows(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_instrument_catalog(out_dir: Optional[Path] = None) -> List[dict]:
    """Load the best local instrument catalog available to an offline export."""
    rows: List[dict] = []
    for path in (TAPE_CSV, DATA / "events_all.csv", DATA / "candidates_recent.csv"):
        rows.extend(_csv_rows(path))
    for name in ("cards", "cards_gemini_en", "cards_gemini_it"):
        for card in load_dir(name).values():
            inst = card.get("instrument") or {}
            rows.append({
                "COD_AZIONE": inst.get("cod_azione"),
                "DES_AZIONE": inst.get("des_azione"),
                "COD_ISIN": inst.get("isin"),
            })
    source = (out_dir or OUT_DIR) / "companies.json"
    if source.exists():
        try:
            rows.extend(json.loads(source.read_text()))
        except (OSError, ValueError):
            pass
    return catalog_from_rows(rows)


def build_stories(catalog: Optional[List[dict]] = None) -> List[dict]:
    plain, en, it, series = (load_dir(n) for n in ("cards", "cards_gemini_en", "cards_gemini_it", "series"))
    ids = sorted(set(plain) | set(en) | set(it))
    out = []
    for cid in ids:
        base = en.get(cid) or it.get(cid) or plain[cid]
        name = (base.get("instrument") or {}).get("des_azione") or cid
        out.append(merge_story(cid, plain.get(cid), en.get(cid), it.get(cid), series.get(cid), slugify(name)))
    catalog = load_instrument_catalog() if catalog is None else catalog
    if catalog:
        out = filter_valid_stories(out, catalog)
    # A duplicate can have the English/Italian/chart artifact that the
    # earliest card lacks; the shared merge keeps those non-empty fields on
    # the canonical (earliest) content id.
    out = deduplicate_stories(out)
    out.sort(key=lambda s: s["article"].get("pub_local") or "", reverse=True)
    return out


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _status_list(counts: Dict[str, int]) -> List[dict]:
    total = sum(counts.values()) or 1
    return [{"status": s, "n": counts.get(s, 0), "share": round(counts.get(s, 0) / total, 4)} for s in STATUSES]


def _block(b: dict) -> dict:
    by_type = []
    for t, counts in b["by_news_type"].items():
        by_type.append({"news_type": t, "n": sum(counts.values()), "status": _status_list(counts)})
    by_type.sort(key=lambda x: -x["n"])
    return {
        "n_articles": b["n_articles"],
        "n_unusual": b["unusual_n"],
        "status": _status_list(b["status"]),
        "by_news_type": by_type,
        "per_session": [{"slot": k, **v} for k, v in b["per_session"].items()],
        "share_anything_before": b.get("share_anything_before"),
        "share_already_or_mostly_at_open": b.get("share_already_or_mostly_at_open"),
        "share_day_before_peak": b.get("share_day_before_peak"),
    }


def build_summary() -> dict:
    stats = read_json(DATA / "stats.json")
    count_path = DATA / "count.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "from_date": stats["from_date"],
        "to_date": stats["to_date"],
        "headline_numbers": {l: stats["headline_numbers"][l] for l in LANGS},
        "chance_pct": {
            "any_session": stats["headline_numbers"]["chance_a_pct"],
            "after_unusual_rule_b": stats["headline_numbers"]["chance_b_pct"],
        },
        "base_rate": stats["base_rate"],
        "first_articles": _block(stats["first_articles"]),
        "all_matched": _block(stats["all_matched"]),
        "count": read_json(count_path) if count_path.exists() else None,
    }


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

def _parse_local(s: str) -> datetime:
    return datetime.strptime(str(s).replace(" ", "T")[:19], "%Y-%m-%dT%H:%M:%S")


def _session_brief(sess: Optional[dict]) -> Optional[dict]:
    if not sess:
        return None
    return {k: sess.get(k) for k in ("d", "timing", "move_pct", "z", "retained_pct")}


def history_from_tape(catalog: Optional[List[dict]] = None) -> Dict[str, dict]:
    """content_id → company history row, from the offline verdict over tape_all.csv."""
    by_id: Dict[str, List[dict]] = collections.OrderedDict()
    with open(TAPE_CSV, newline="") as f:
        for r in csv.DictReader(f):
            by_id.setdefault(r["content_id"], []).append(r)
    out = {}
    for cid, rows in by_id.items():
        r0 = rows[0]
        probe = {
            "content_id": cid,
            "titolo": r0.get("titolo") or "",
            "COD_AZIONE": r0.get("COD_AZIONE"),
            "DES_AZIONE": r0.get("DES_AZIONE"),
            "COD_ISIN": r0.get("COD_ISIN"),
        }
        if catalog and not story_matches_catalog(probe, catalog):
            continue
        news = classify(r0.get("titolo") or "")
        v = verdict(rows, news)
        out[cid] = {
            "content_id": cid,
            "titolo": r0.get("titolo") or "",
            "pub_local": str(r0["pub_local"]).replace(" ", "T")[:19],
            "cod_azione": r0["COD_AZIONE"],
            "des_azione": r0["DES_AZIONE"],
            "isin": r0.get("COD_ISIN"),
            "news_type": news.get("news_type"),
            "status": v["status"],
            "peak": _session_brief(v.get("peak")),
            "largest": _session_brief(v.get("largest")),
        }
    # Tape can contain the same headline under multiple IDs.  Keep the
    # earliest history row before company counts and first-article flags.
    return {s["content_id"]: s for s in deduplicate_stories(list(out.values()))}


def history_from_story(s: dict) -> dict:
    v = s["verdict"]
    return {
        "content_id": s["content_id"],
        "titolo": s["article"]["titolo"],
        "pub_local": s["article"].get("pub_local"),
        "cod_azione": s["instrument"].get("cod_azione"),
        "des_azione": s["instrument"].get("des_azione"),
        "isin": s["instrument"].get("isin"),
        "news_type": (s.get("news") or {}).get("news_type"),
        "status": v["status"],
        "peak": _session_brief(v.get("peak")),
        "largest": _session_brief(v.get("largest")),
    }


def mark_first_articles(items: List[dict]) -> None:
    """Same 7-day rule as stats.py: previous story on the company at least 7 days earlier."""
    items.sort(key=lambda x: (x["pub_local"], x["content_id"]))
    prev = None
    for it in items:
        t = _parse_local(it["pub_local"])
        it["first_article"] = prev is None or (t - prev) >= timedelta(days=7)
        prev = t


def load_prices() -> Dict[str, dict]:
    if not PRICES_CSV.exists():
        return {}
    cols: Dict[str, dict] = {}
    with open(PRICES_CSV, newline="") as f:
        for r in csv.DictReader(f):
            c = cols.setdefault(r["COD_AZIONE"], {"d": [], "close": [], "volume": [], "move_pct": [], "z": []})
            move = _float(r["move"])
            c["d"].append(r["d"])
            c["close"].append(_round(_float(r["prz_last"]), 4))
            c["volume"].append(_round(_float(r["volume"]), 0))
            c["move_pct"].append(_round(None if move is None else move * 100, 2))
            c["z"].append(_round(_float(r["z_trailing"]), 2))
    return cols


def _history_from_existing(source: Path, catalog: Optional[List[dict]] = None) -> Dict[str, dict]:
    """Recover cached histories when the tape CSV is unavailable."""
    index_path = source / "companies.json"
    if not index_path.exists():
        return {}
    try:
        index = json.loads(index_path.read_text())
    except (OSError, ValueError):
        return {}
    out: Dict[str, dict] = {}
    for entry in index:
        path = source / "companies" / f"{entry.get('slug')}.json"
        try:
            obj = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for row in obj.get("stories") or []:
            hist = {
                "content_id": row.get("content_id"),
                "titolo": row.get("titolo") or "",
                "pub_local": row.get("pub_local"),
                "cod_azione": obj.get("cod_azione") or entry.get("cod_azione"),
                "des_azione": obj.get("des_azione") or entry.get("des_azione"),
                "isin": obj.get("isin") or entry.get("isin"),
                "news_type": row.get("news_type"),
                "status": row.get("status") or "NO_REACTION",
                "peak": row.get("peak"),
                "largest": row.get("largest"),
            }
            if hist["content_id"] and (not catalog or story_matches_catalog(hist, catalog)):
                out[hist["content_id"]] = hist
    return {s["content_id"]: s for s in deduplicate_stories(list(out.values()))}


def _existing_prices(source: Path) -> Dict[str, dict]:
    """Read prices from the old bundle so an offline export is lossless."""
    out: Dict[str, dict] = {}
    path = source / "companies.json"
    if not path.exists():
        return out
    try:
        index = json.loads(path.read_text())
    except (OSError, ValueError):
        return out
    for entry in index:
        if not entry.get("has_prices"):
            continue
        try:
            obj = json.loads((source / "companies" / f"{entry['slug']}.json").read_text())
        except (OSError, ValueError):
            continue
        if obj.get("prices") is not None and obj.get("cod_azione"):
            out[obj["cod_azione"]] = obj["prices"]
    return out


def build_companies(stories: List[dict], source_dir: Optional[Path] = None,
                    catalog: Optional[List[dict]] = None) -> tuple:
    source_dir = source_dir or OUT_DIR
    catalog = load_instrument_catalog(source_dir) if catalog is None else catalog
    hist = (history_from_tape(catalog) if TAPE_CSV.exists()
            else _history_from_existing(source_dir, catalog))
    for s in stories:
        if not catalog or story_matches_catalog(s, catalog):
            hist[s["content_id"]] = history_from_story(s)
    hist = {s["content_id"]: s for s in deduplicate_stories(list(hist.values()))}
    detail_ids = {s["content_id"] for s in stories}
    prices = load_prices()
    if not prices:
        prices = _existing_prices(source_dir)

    by_cod: Dict[str, List[dict]] = collections.defaultdict(list)
    for h in hist.values():
        by_cod[h["cod_azione"]].append(h)

    index, files = [], {}
    for cod, items in by_cod.items():
        mark_first_articles(items)
        items.sort(key=lambda x: x["pub_local"], reverse=True)
        latest = items[0]
        slug = slugify(latest["des_azione"] or cod)
        status = collections.Counter(i["status"] for i in items)
        rows = [
            {
                "content_id": i["content_id"],
                "titolo": i["titolo"],
                "pub_local": i["pub_local"],
                "news_type": i["news_type"],
                "status": i["status"],
                "first_article": i["first_article"],
                "has_detail": i["content_id"] in detail_ids,
                "peak": i["peak"],
                "largest": i["largest"],
            }
            for i in items
        ]
        summary = {
            "n_stories": len(items),
            "n_first_articles": sum(1 for i in items if i["first_article"]),
            "n_unusual": sum(n for st, n in status.items() if st != "NO_REACTION"),
            "status": {st: status.get(st, 0) for st in STATUSES},
            "first_pub": items[-1]["pub_local"],
            "last_pub": latest["pub_local"],
        }
        company = {
            "slug": slug,
            "des_azione": latest["des_azione"],
            "cod_azione": cod,
            "isin": latest["isin"],
        }
        files[slug] = {
            "schema_version": SCHEMA_VERSION,
            **company,
            "summary": summary,
            "stories": rows,
            "prices": prices.get(cod),
        }
        index.append({
            **company,
            **{k: summary[k] for k in ("n_stories", "n_unusual", "status", "last_pub")},
            "n_detail": sum(1 for r in rows if r["has_detail"]),
            "has_prices": cod in prices,
        })

    dupes = [s for s, n in collections.Counter(c["slug"] for c in index).items() if n > 1]
    if dupes:
        sys.exit(f"Company slug collision: {dupes}; make slugify() disambiguate")
    index.sort(key=lambda c: (-c["n_stories"], c["slug"]))
    return index, files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args(argv)
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    # A custom output directory is generally a preview; use the committed
    # bundle as a read-only source for cached company histories and prices.
    source_dir = out if out == OUT_DIR else OUT_DIR
    catalog = load_instrument_catalog(source_dir)
    stories = build_stories(catalog)
    shutil.rmtree(out / "stories", ignore_errors=True)
    for s in stories:
        write_json(out / "stories" / f"{s['content_id']}.json", s)
    rows = [story_row(s) for s in stories]
    write_json(out / "stories.json", rows)
    print(f"stories: {len(rows)} ({sum(r['has_gemini'] for r in rows)} with Gemini, "
          f"{sum(r['has_series'] for r in rows)} with series)")

    summary = build_summary()
    write_json(out / "summary.json", summary)
    write_json(out / "status_meta.json", {
        "schema_version": SCHEMA_VERSION,
        "statuses": STATUS_META,
        "groups": GROUPS,
        "news_types": NEWS_TYPES,
    })

    index, files = build_companies(stories, source_dir=source_dir, catalog=catalog)
    shutil.rmtree(out / "companies", ignore_errors=True)
    for slug, obj in files.items():
        write_json(out / "companies" / f"{slug}.json", obj, compact=True)
    write_json(out / "companies.json", index)
    n_companies = len(index)
    print(f"companies: {n_companies} ({sum(c['has_prices'] for c in index)} with prices)")

    pubs = [r["pub_local"] for r in rows if r["pub_local"]]
    write_json(out / "manifest.json", {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "languages": list(LANGS),
        "last_price_date": LAST_PRICE_DATE,
        "stories_range": {"from": min(pubs)[:10] if pubs else None, "to": max(pubs)[:10] if pubs else None},
        "history_range": {"from": summary["from_date"], "to": summary["to_date"]},
        "counts": {
            "stories": len(rows),
            "stories_with_gemini": sum(r["has_gemini"] for r in rows),
            "stories_with_series": sum(r["has_series"] for r in rows),
            "companies": n_companies,
        },
        "files": {
            "stories": "stories.json",
            "story": "stories/{content_id}.json",
            "summary": "summary.json",
            "status_meta": "status_meta.json",
            "companies": "companies.json",
            "company": "companies/{slug}.json",
        },
    })
    print(f"wrote bundle → {out}")


if __name__ == "__main__":
    main()
