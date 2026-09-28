#!/usr/bin/env python3
"""Count, over all matched stories, when the unusual day happened relative to publication.

Input: data/events_all.csv, produced by sql/events.sql over 2021-02-01..2026-09-15.
The window is 1 session before, the article day, and up to 5 sessions after,
so "later" covers more sessions than the other two by construction.
"""
import collections
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "data" / "events_all.csv")))
unusual = [r for r in rows if r["unusual"] == "true"]
by_timing = collections.Counter(r["timing"] for r in unusual)

result = {
    "matched_stories": len(rows),
    "with_unusual_day": len(unusual),
    "unusual_day_before": by_timing["day_before"],
    "unusual_same_day": by_timing["same_day"],
    "unusual_later": by_timing["later"],
    "share_day_before": round(by_timing["day_before"] / len(unusual), 3),
}
(ROOT / "data" / "count.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
