#!/usr/bin/env python3
"""Cache daily prices for every company with a story (sql/company_prices.sql).

Usage:
    python3 scripts/fetch_company_prices.py
    python3 scripts/fetch_company_prices.py --from 2021-01-01 --to 2026-09-23

Companies come from data/tape_all.csv plus data/cards*/. Writes
data/company_prices.csv, which export_dashboard.py reads if present.
Stdlib, Python 3.9.
"""
from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Set

PROJECT = "class-hackaton-09"
ROOT = Path(__file__).resolve().parent.parent
TAPE_CSV = ROOT / "data" / "tape_all.csv"
OUT_CSV = ROOT / "data" / "company_prices.csv"
FROM_DATE = "2021-01-01"
TO_DATE = "2026-09-23"


def company_codes() -> List[str]:
    codes: Set[str] = set()
    if TAPE_CSV.exists():
        with open(TAPE_CSV, newline="") as f:
            for r in csv.DictReader(f):
                if r.get("COD_AZIONE"):
                    codes.add(r["COD_AZIONE"])
    for p in glob.glob(str(ROOT / "data" / "cards*" / "*.json")):
        if p.endswith("index.json"):
            continue
        cod = (json.loads(Path(p).read_text()).get("instrument") or {}).get("cod_azione")
        if cod:
            codes.add(cod)
    return sorted(codes)


def bq_prices(codes: List[str], from_date: str, to_date: str) -> str:
    sql = (ROOT / "sql" / "company_prices.sql").read_text()
    cmd = [
        "bq", f"--project_id={PROJECT}", "query",
        "--use_legacy_sql=false", "--format=csv", "--max_rows=2000000",
        f"--parameter=cod_azioni:ARRAY<STRING>:{json.dumps(codes)}",
        f"--parameter=from_date:DATE:{from_date}",
        f"--parameter=to_date:DATE:{to_date}",
    ]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(f"bq failed with exit {proc.returncode}")
    out = proc.stdout
    if out.startswith("Waiting"):
        out = out.split("\n", 1)[1]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="from_date", default=FROM_DATE)
    ap.add_argument("--to", dest="to_date", default=TO_DATE)
    args = ap.parse_args()

    codes = company_codes()
    if not codes:
        sys.exit(f"No companies found; build {TAPE_CSV} or data/cards first")
    print(f"Querying prices for {len(codes)} companies {args.from_date} .. {args.to_date} …",
          file=sys.stderr, flush=True)
    out = bq_prices(codes, args.from_date, args.to_date)
    n = sum(1 for _ in csv.DictReader(io.StringIO(out)))
    OUT_CSV.write_text(out)
    print(f"Wrote {n} rows → {OUT_CSV}", file=sys.stderr)


if __name__ == "__main__":
    main()
