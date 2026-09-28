#!/usr/bin/env python3
"""Batch-build story cards from a date range or explicit ids.

Usage:
    python3 scripts/build_cards.py --from 2026-08-15 --to 2026-09-18 \\
        --first-only --unusual-only
    python3 scripts/build_cards.py --ids id1 id2 --gemini --lang en
    python3 scripts/build_cards.py --from 2026-08-15 --to 2026-09-18 \\
        --first-only --unusual-only --gemini --limit 3

One bq_tape call + one bodies call for the whole batch. Gemini is sequential.
Stdlib, Python 3.9.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_card import (  # noqa: E402
    build_card_dict,
    fetch_articles,
    _parse_pub_local,
)
from verdict import bq_tape, verdict  # noqa: E402
from classify import classify  # noqa: E402

CARDS_DIR = ROOT / "data" / "cards"


def _shift_date(ymd: str, days: int) -> str:
    dt = datetime.strptime(ymd, "%Y-%m-%d") + timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def _group_rows(rows: List[dict]) -> Dict[str, List[dict]]:
    by: Dict[str, List[dict]] = {}
    for r in rows:
        by.setdefault(r["content_id"], []).append(r)
    return by


def _article_meta(rows: List[dict]) -> dict:
    r0 = rows[0]
    return {
        "content_id": r0["content_id"],
        "titolo": r0.get("titolo"),
        "pub_local": r0.get("pub_local"),
        "pub_date": r0.get("pub_date") or (str(r0.get("pub_local") or "")[:10]),
        "COD_AZIONE": r0.get("COD_AZIONE"),
        "DES_AZIONE": r0.get("DES_AZIONE"),
    }


def filter_first_only(
    metas: List[dict],
    from_date: str,
    to_date: str,
) -> List[dict]:
    """Keep articles in [from_date, to_date] whose previous article on the same
    COD_AZIONE is at least 7 days earlier (computed over metas that already
    include the 7-day lookback window).
    """
    by_stock: Dict[str, List[dict]] = {}
    for m in metas:
        by_stock.setdefault(m["COD_AZIONE"], []).append(m)
    for cod in by_stock:
        by_stock[cod].sort(key=lambda m: m["pub_local"] or "")

    kept: List[dict] = []
    for cod, items in by_stock.items():
        for i, m in enumerate(items):
            pd = m["pub_date"]
            if not pd or pd < from_date or pd > to_date:
                continue
            if i == 0:
                kept.append(m)
                continue
            prev = items[i - 1]
            t = _parse_pub_local(m["pub_local"])
            p = _parse_pub_local(prev["pub_local"])
            if t is None or p is None:
                kept.append(m)
                continue
            if (t - p).days >= 7:
                kept.append(m)
    return kept


def index_entry(card: dict) -> dict:
    v = card.get("verdict") or {}
    peak = v.get("peak") or {}
    g = card.get("gemini") or {}
    return {
        "content_id": card["article"]["content_id"],
        "titolo": card["article"]["titolo"],
        "pub_local": card["article"].get("pub_local"),
        "des_azione": (card.get("instrument") or {}).get("des_azione"),
        "news_type": (card.get("news") or {}).get("news_type"),
        "headline_reports_move": (card.get("news") or {}).get("headline_reports_move"),
        "status": v.get("status"),
        "peak_z": peak.get("z"),
        "peak_move_pct": peak.get("move_pct"),
        "retained_pct": (card.get("tape") or {}).get("retained_pct"),
        "adjective_matches": g.get("adjective_matches"),
    }


def run(
    content_ids: Optional[List[str]],
    from_date: Optional[str],
    to_date: Optional[str],
    first_only: bool,
    unusual_only: bool,
    use_gemini: bool,
    lang: str,
    limit: Optional[int],
) -> Tuple[List[dict], dict]:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    tape_from = from_date
    tape_to = to_date
    if content_ids:
        rows = bq_tape(content_ids=content_ids)
    else:
        assert from_date and to_date
        # look back 7 days so --first-only does not wrongly keep the first days
        tape_from = _shift_date(from_date, -7) if first_only else from_date
        rows = bq_tape(content_ids=None, from_date=tape_from, to_date=to_date)

    by_id = _group_rows(rows)
    metas = [_article_meta(rs) for rs in by_id.values()]

    if content_ids:
        selected = [m for m in metas if m["content_id"] in set(content_ids)]
        # preserve caller order when possible
        order = {cid: i for i, cid in enumerate(content_ids)}
        selected.sort(key=lambda m: order.get(m["content_id"], 10**9))
    else:
        assert from_date and to_date
        if first_only:
            selected = filter_first_only(metas, from_date, to_date)
        else:
            selected = [
                m for m in metas
                if m["pub_date"] and from_date <= m["pub_date"] <= to_date
            ]

    candidates: List[Tuple[dict, List[dict], dict, dict]] = []
    for m in selected:
        rs = by_id[m["content_id"]]
        news = classify(m["titolo"] or "")
        verd = verdict(rs, news)
        if unusual_only and verd["status"] == "NO_REACTION":
            continue
        candidates.append((m, rs, news, verd))

    if not content_ids:
        candidates.sort(key=lambda x: x[0].get("pub_local") or "", reverse=True)
    if limit is not None:
        candidates = candidates[:limit]
    ordered_ids = [c[0]["content_id"] for c in candidates]

    if not ordered_ids:
        index = {"generated_at": datetime.utcnow().isoformat() + "Z", "cards": []}
        (CARDS_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2))
        return [], index

    articles = fetch_articles(ordered_ids)
    index_cards: List[dict] = []
    built: List[dict] = []

    total = len(ordered_ids)
    for i, cid in enumerate(ordered_ids, 1):
        rs = by_id[cid]
        article = articles.get(cid)
        if not article:
            # tape has the title; body missing — skip gemini-friendly fields
            article = {
                "content_id": cid,
                "titolo": rs[0].get("titolo"),
                "body": "",
                "data_pubblicazione": rs[0].get("data_pubblicazione"),
                "testata": None,
                "URL": None,
            }
        print(f"[{i}/{total}] {cid} …", flush=True)
        card = build_card_dict(article, rs, lang=lang, use_gemini=use_gemini)
        # Re-apply unusual filter with full classify (body) if needed
        if unusual_only and card["verdict"]["status"] == "NO_REACTION":
            print(f"  skip NO_REACTION after full classify", flush=True)
            continue
        out = CARDS_DIR / f"{cid}.json"
        out.write_text(json.dumps(card, ensure_ascii=False, indent=2))
        entry = index_entry(card)
        index_cards.append(entry)
        built.append(card)
        print(
            f"  {entry['des_azione']} | {entry['news_type']} | {entry['status']} | "
            f"z={entry['peak_z']}",
            flush=True,
        )

    index_cards.sort(key=lambda e: e.get("pub_local") or "", reverse=True)
    index = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "from_date": from_date,
        "to_date": to_date,
        "first_only": first_only,
        "unusual_only": unusual_only,
        "gemini": use_gemini,
        "n": len(index_cards),
        "cards": index_cards,
    }
    (CARDS_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2))
    return built, index


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids", nargs="+", help="Explicit content_id list")
    g.add_argument("--from", dest="from_date", help="Range start (Rome pub_date)")
    ap.add_argument("--to", dest="to_date", help="Range end (Rome pub_date)")
    ap.add_argument("--first-only", action="store_true")
    ap.add_argument("--unusual-only", action="store_true")
    ap.add_argument("--gemini", action="store_true", help="Call Gemini (default: off)")
    ap.add_argument("--lang", choices=["en", "it"], default="en")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out-dir", default=None, help="Default: data/cards")
    args = ap.parse_args(argv)

    global CARDS_DIR
    if args.out_dir:
        CARDS_DIR = Path(args.out_dir).resolve()
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    if args.from_date and not args.to_date:
        ap.error("--to is required with --from")
    if args.ids is None and args.to_date is None:
        ap.error("provide --ids or --from/--to")

    _, index = run(
        content_ids=args.ids,
        from_date=args.from_date,
        to_date=args.to_date,
        first_only=args.first_only,
        unusual_only=args.unusual_only,
        use_gemini=args.gemini,
        lang=args.lang,
        limit=args.limit,
    )
    # summary
    from collections import Counter
    st = Counter(c["status"] for c in index["cards"])
    nt = Counter(c["news_type"] for c in index["cards"])
    print(f"\nwrote {index['n']} cards → {CARDS_DIR}/")
    print("status:", dict(st))
    print("news_type:", dict(nt))


if __name__ == "__main__":
    main()
