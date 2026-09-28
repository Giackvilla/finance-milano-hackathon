#!/usr/bin/env python3
"""Descriptive counts over MF articles vs the price window (not a strategy).

Usage:
    python3 scripts/stats.py            # query BigQuery for tape + base_rate
    python3 scripts/stats.py --offline  # reuse data/tape_all.csv + data/base_rate.json

Date range: 2021-02-01 .. 2026-09-15.
First-article filter: keep if the previous article on the same COD_AZIONE
is >= 7 days earlier by pub_local (or there is no previous).
Base rate: sql/base_rate.sql over non-ETF shares; cached in data/base_rate.json.
"""
import argparse
import collections
import csv
import io
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from verdict import bq_tape, verdict  # noqa: E402

PROJECT = "class-hackaton-09"
FROM_DATE = "2021-02-01"
TO_DATE = "2026-09-15"
TAPE_CSV = ROOT / "data" / "tape_all.csv"
BASE_RATE_JSON = ROOT / "data" / "base_rate.json"
STATS_JSON = ROOT / "data" / "stats.json"

STATUSES = (
    "NO_REACTION",
    "ALREADY_IN_PRICE",
    "PARTLY_IN_PRICE",
    "MOSTLY_AT_OPEN",
    "REACTED",
    "DELAYED",
)

# Slots for per_session: (key, chance_rule 'a'|'b')
SLOTS = (
    ("day_before", "a"),
    ("reaction", "b"),
    ("same_day_pre_open", "b"),
    ("same_day_in_session", "b"),
    ("same_day_after_close", "b"),
    ("later_1", "b"),
    ("later_2", "b"),
    ("later_3", "b"),
    ("later_4", "b"),
    ("later_5", "b"),
)


def _parse_pub_local(s):
    s = str(s).strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    raise ValueError(f"bad pub_local: {s!r}")


def _bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "t")


def _try_classify(titolo):
    try:
        from classify import classify
        return classify(titolo, body="")
    except Exception:
        return None


def load_rows(offline):
    if offline:
        if not TAPE_CSV.exists():
            sys.exit(f"Missing {TAPE_CSV}; run without --offline first")
        return list(csv.DictReader(open(TAPE_CSV, newline="")))
    print(f"Querying tape_window {FROM_DATE} .. {TO_DATE} …", flush=True)
    rows = bq_tape(content_ids=None, from_date=FROM_DATE, to_date=TO_DATE)
    TAPE_CSV.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(TAPE_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    else:
        TAPE_CSV.write_text("")
    print(f"Wrote {len(rows)} rows → {TAPE_CSV}", flush=True)
    return rows


def load_base_rate(offline):
    if offline and BASE_RATE_JSON.exists():
        return json.loads(BASE_RATE_JSON.read_text())
    if offline:
        sys.exit(f"Missing {BASE_RATE_JSON}; run once without --offline for base_rate")
    print("Querying base_rate.sql …", flush=True)
    sql = (ROOT / "sql" / "base_rate.sql").read_text()
    cmd = [
        "bq", f"--project_id={PROJECT}", "query",
        "--use_legacy_sql=false", "--format=csv", "--max_rows=10",
    ]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=True)
    out = proc.stdout
    if out.startswith("Waiting"):
        out = out.split("\n", 1)[1]
    row = next(csv.DictReader(io.StringIO(out)))
    br = {
        "n_sessions_a": int(row["n_sessions_a"]),
        "n_unusual_a": int(row["n_unusual_a"]),
        "share_a": float(row["share_a"]),
        "n_sessions_b": int(row["n_sessions_b"]),
        "n_unusual_b": int(row["n_unusual_b"]),
        "share_b": float(row["share_b"]),
    }
    BASE_RATE_JSON.write_text(json.dumps(br, indent=2))
    print(f"Wrote {BASE_RATE_JSON}: a={br['share_a']:.4%} b={br['share_b']:.4%}", flush=True)
    return br


def articles_from_rows(rows):
    by_id = collections.OrderedDict()
    for r in rows:
        by_id.setdefault(r["content_id"], []).append(r)
    arts = []
    for cid, rs in by_id.items():
        arts.append({
            "content_id": cid,
            "COD_AZIONE": rs[0]["COD_AZIONE"],
            "titolo": rs[0].get("titolo") or "",
            "pub_local": _parse_pub_local(rs[0]["pub_local"]),
            "publication_phase": rs[0]["publication_phase"],
            "rows": rs,
        })
    return arts


def first_article_filter(arts):
    """Keep if previous same-company article is >= 7 days earlier by pub_local."""
    by_co = collections.defaultdict(list)
    for a in arts:
        by_co[a["COD_AZIONE"]].append(a)
    kept = []
    gap = timedelta(days=7)
    for group in by_co.values():
        group = sorted(group, key=lambda x: (x["pub_local"], x["content_id"]))
        for i, a in enumerate(group):
            if i == 0 or (a["pub_local"] - group[i - 1]["pub_local"]) >= gap:
                kept.append(a)
    return kept


def _slot_for_row(r):
    """Yield slot keys this session row contributes to (may be more than one)."""
    timing = r["timing"]
    phase = r["publication_phase"]
    if timing == "day_before":
        yield "day_before"
    if _bool(r.get("is_reaction_session")):
        yield "reaction"
    if timing == "same_day":
        if phase == "pre_open":
            yield "same_day_pre_open"
        elif phase == "in_session":
            yield "same_day_in_session"
        elif phase == "after_close":
            yield "same_day_after_close"
    if timing == "later":
        lr = r.get("later_rank")
        if lr not in (None, ""):
            yield f"later_{int(lr)}"


def per_session_stats(arts, base_rate):
    tallies = {k: {"n": 0, "n_unusual": 0} for k, _ in SLOTS}
    for a in arts:
        for r in a["rows"]:
            unusual = _bool(r.get("unusual"))
            for slot in _slot_for_row(r):
                if slot not in tallies:
                    continue
                tallies[slot]["n"] += 1
                if unusual:
                    tallies[slot]["n_unusual"] += 1

    chance = {"a": base_rate["share_a"], "b": base_rate["share_b"]}
    out = {}
    for key, rule in SLOTS:
        t = tallies[key]
        n, nu = t["n"], t["n_unusual"]
        share = (nu / n) if n else None
        ch = chance[rule]
        ratio = (share / ch) if share is not None and ch else None
        out[key] = {
            "n": n,
            "n_unusual": nu,
            "share": round(share, 4) if share is not None else None,
            "chance_rule": rule,
            "chance": round(ch, 4),
            "ratio": round(ratio, 2) if ratio is not None else None,
        }
    return out


def summarise(arts, label, base_rate):
    status_counts = collections.Counter()
    by_type = collections.defaultdict(collections.Counter)
    unusual_n = 0
    already_or_open = 0
    anything_before = 0
    day_before_peak = 0

    for a in arts:
        news = _try_classify(a["titolo"])
        v = verdict(a["rows"], news)
        st = v["status"]
        status_counts[st] += 1
        ntype = (news or {}).get("news_type") or "unknown"
        by_type[ntype][st] += 1

        if st != "NO_REACTION":
            unusual_n += 1
            if st in ("ALREADY_IN_PRICE", "MOSTLY_AT_OPEN"):
                already_or_open += 1
            if st in ("ALREADY_IN_PRICE", "PARTLY_IN_PRICE", "MOSTLY_AT_OPEN"):
                anything_before += 1
            if v.get("peak") and v["peak"].get("timing") == "day_before":
                day_before_peak += 1

    return {
        "label": label,
        "n_articles": len(arts),
        "status": {s: status_counts.get(s, 0) for s in STATUSES},
        "by_news_type": {
            t: {s: by_type[t].get(s, 0) for s in STATUSES}
            for t in sorted(by_type)
        },
        "unusual_n": unusual_n,
        "share_already_or_mostly_at_open": round(already_or_open / unusual_n, 3) if unusual_n else None,
        "share_anything_before": round(anything_before / unusual_n, 3) if unusual_n else None,
        "count_already_or_mostly_at_open": already_or_open,
        "count_anything_before": anything_before,
        "unusual_day_before_peak": day_before_peak,
        "share_day_before_peak": round(day_before_peak / unusual_n, 3) if unusual_n else None,
        "per_session": per_session_stats(arts, base_rate),
    }


def _pct1(x):
    """0.071 → '7.1%'."""
    return f"{100.0 * x:.1f}%"


def headline_numbers(first_sum, base_rate):
    """Plain-language strings for the screen (en / it), from computed values."""
    ps = first_sum["per_session"]
    ca = base_rate["share_a"]
    cb = base_rate["share_b"]

    def line(slot_key):
        s = ps[slot_key]
        return s["share"], s["ratio"], s["chance"]

    db_share, db_ratio, _ = line("day_before")
    rx_share, rx_ratio, _ = line("reaction")
    ac_share, ac_ratio, _ = line("same_day_after_close")
    po_share, po_ratio, _ = line("same_day_pre_open")

    en = []
    it = []

    if db_share is not None:
        en.append(
            f"The session before an MF story is unusual {_pct1(db_share)} of the time, "
            f"against {_pct1(ca)} for any session."
        )
        it.append(
            f"La seduta prima di un articolo MF è anomala nel {_pct1(db_share)} dei casi, "
            f"contro il {_pct1(ca)} di una seduta qualsiasi."
        )

    if rx_share is not None and rx_ratio is not None:
        en.append(
            f"The first session trading on the story is unusual {_pct1(rx_share)} of the time, "
            f"{rx_ratio:.1f} times chance."
        )
        it.append(
            f"La prima seduta che tratta sulla notizia è anomala nel {_pct1(rx_share)} dei casi, "
            f"{rx_ratio:.1f} volte il caso."
        )

    if ac_share is not None:
        en.append(
            f"When MF publishes after the close, the same day had already moved unusually "
            f"in {_pct1(ac_share)} of cases"
            + (f" ({ac_ratio:.1f} times chance)." if ac_ratio is not None else ".")
        )
        it.append(
            f"Quando MF pubblica dopo la chiusura, lo stesso giorno si era già mosso in modo anomalo "
            f"nel {_pct1(ac_share)} dei casi"
            + (f" ({ac_ratio:.1f} volte il caso)." if ac_ratio is not None else ".")
        )

    if po_share is not None and po_ratio is not None:
        en.append(
            f"When MF publishes before the open, the same trading day is unusual "
            f"{_pct1(po_share)} of the time ({po_ratio:.1f} times chance)."
        )
        it.append(
            f"Quando MF pubblica prima dell'apertura, la stessa seduta è anomala "
            f"nel {_pct1(po_share)} dei casi ({po_ratio:.1f} volte il caso)."
        )

    return {
        "en": en,
        "it": it,
        "chance_a_pct": round(100 * ca, 2),
        "chance_b_pct": round(100 * cb, 2),
    }


def print_table(first, headlines):
    print()
    print(f"First articles (after 7-day filter): {first['n_articles']}")
    print(f"{'status':22} {'n':>6}")
    for s in STATUSES:
        print(f"{s:22} {first['status'].get(s, 0):6d}")
    print()
    print("per_session (first articles):")
    print(f"{'slot':22} {'n':>7} {'unusual':>8} {'share':>8} {'chance':>8} {'ratio':>7}")
    for key, _ in SLOTS:
        s = first["per_session"][key]
        sh = f"{100 * s['share']:.1f}%" if s["share"] is not None else "—"
        ch = f"{100 * s['chance']:.1f}%"
        rt = f"{s['ratio']:.2f}" if s["ratio"] is not None else "—"
        print(f"{key:22} {s['n']:7d} {s['n_unusual']:8d} {sh:>8} {ch:>8} {rt:>7}")
    print()
    print("headline_numbers:")
    for line in headlines.get("en") or []:
        print(f"  EN: {line}")
    for line in headlines.get("it") or []:
        print(f"  IT: {line}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help=f"read {TAPE_CSV} and {BASE_RATE_JSON}")
    args = ap.parse_args()

    # Tape can be offline; base_rate needs a live call unless cached
    rows = load_rows(args.offline)
    if args.offline and BASE_RATE_JSON.exists():
        base_rate = load_base_rate(True)
    else:
        # always allow live base_rate even when tape is offline
        base_rate = load_base_rate(False)

    arts = articles_from_rows(rows)
    n_before = len(arts)
    first = first_article_filter(arts)
    n_after = len(first)
    print(f"Articles before first-filter: {n_before}")
    print(f"Articles after first-filter:  {n_after}")

    all_sum = summarise(arts, "all_matched", base_rate)
    first_sum = summarise(first, "first_articles", base_rate)
    headlines = headline_numbers(first_sum, base_rate)

    out = {
        "from_date": FROM_DATE,
        "to_date": TO_DATE,
        "n_session_rows": len(rows),
        "n_articles_before_filter": n_before,
        "n_articles_after_filter": n_after,
        "base_rate": base_rate,
        "all_matched": all_sum,
        "first_articles": first_sum,
        "headline_numbers": headlines,
    }
    STATS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {STATS_JSON}")
    print_table(first_sum, headlines)


if __name__ == "__main__":
    main()
