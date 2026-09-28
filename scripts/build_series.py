#!/usr/bin/env python3
"""Build per-story chart series JSON from BigQuery (sql/series.sql).

Usage:
    python3 scripts/build_series.py [<content_id> ...]
    python3 scripts/build_series.py --ids-file /tmp/hero_ids.txt

Default: ids from /tmp/hero_ids.txt (space-separated).
Writes data/series/<content_id>.json and data/series/index.json.
Validates z/move at rel -1 and 0 against data/cards/<id>.json when present.
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT = "class-hackaton-09"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "series"
CARDS_DIR = ROOT / "data" / "cards"
DEFAULT_IDS_FILE = Path("/tmp/hero_ids.txt")


def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return False
    return str(v).strip().lower() in ("true", "1", "t")


def _float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    return float(v)


def _round(v: Optional[float], nd: int) -> Optional[float]:
    if v is None:
        return None
    return round(v, nd)


def _pct(v: Optional[float], nd: int = 2) -> Optional[float]:
    if v is None:
        return None
    return round(float(v) * 100, nd)


def load_ids(argv: List[str]) -> List[str]:
    if len(argv) >= 2 and argv[1] == "--ids-file":
        path = Path(argv[2]) if len(argv) > 2 else DEFAULT_IDS_FILE
        text = path.read_text().strip()
        return text.split()
    if len(argv) >= 2:
        return argv[1:]
    if DEFAULT_IDS_FILE.exists():
        return DEFAULT_IDS_FILE.read_text().strip().split()
    sys.exit("No content ids: pass ids, --ids-file PATH, or put them in /tmp/hero_ids.txt")


def bq_series(content_ids: List[str], max_rows: int = 500000) -> List[dict]:
    sql = (ROOT / "sql" / "series.sql").read_text()
    arr = json.dumps(list(content_ids))
    cmd = [
        "bq", f"--project_id={PROJECT}", "query",
        "--use_legacy_sql=false", "--format=csv", f"--max_rows={max_rows}",
        f"--parameter=content_ids:ARRAY<STRING>:{arr}",
    ]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(f"bq failed with exit {proc.returncode}")
    # progress lines go to stderr; strip any Waiting header if it leaked to stdout
    out = proc.stdout
    if out.startswith("Waiting"):
        out = out.split("\n", 1)[1]
    return list(csv.DictReader(io.StringIO(out)))


def session_obj(row: dict) -> dict:
    return {
        "d": row["d"],
        "rel": int(row["rel"]),
        "prz_last": _round(_float(row["prz_last"]), 4),
        "index_100": _round(_float(row["index_100"]), 4),
        "move_pct": _pct(_float(row["move"])),
        "z": _round(_float(row["z"]), 2),
        "unusual": _bool(row["unusual"]),
        "in_baseline": _bool(row["in_baseline"]),
        "volume": _round(_float(row["quantitativo"]), 0),
    }


def build_payload(content_id: str, rows: List[dict]) -> dict:
    if not rows:
        return {
            "content_id": content_id,
            "des_azione": None,
            "cod_azione": None,
            "pub_local": None,
            "baseline": None,
            "markers": None,
            "sessions": [],
        }
    rows = sorted(rows, key=lambda r: r["d"])
    first = rows[0]
    sessions = [session_obj(r) for r in rows]

    by_rel = {s["rel"]: s for s in sessions}
    session_before = by_rel.get(-1)
    peak_candidates = [s for s in sessions if -1 <= s["rel"] <= 5 and s["z"] is not None]
    peak = None
    if peak_candidates:
        peak = max(peak_candidates, key=lambda s: abs(s["z"]))

    sd = _float(first["baseline_sd"])
    return {
        "content_id": content_id,
        "des_azione": first["DES_AZIONE"],
        "cod_azione": first["COD_AZIONE"],
        "pub_local": str(first["pub_local"]).replace(" ", "T"),
        "baseline": {
            "from": first["base_from"],
            "to": first["base_to"],
            "sd_pct": _pct(sd, 3) if sd is not None else None,
        },
        "markers": {
            "publication": str(first["pub_local"]).replace(" ", "T"),
            "session_before": session_before["d"] if session_before else None,
            "peak": peak["d"] if peak else None,
            "last_session": sessions[-1]["d"],
        },
        "sessions": sessions,
    }


def card_date_lookup(card: dict) -> Dict[str, Tuple[float, float, str]]:
    """d → (move_pct, z, source) from unusual_sessions / largest / peak / tape."""
    out: Dict[str, Tuple[float, float, str]] = {}

    def put(d, move_pct, z, src: str):
        if d and move_pct is not None and z is not None and d not in out:
            out[d] = (move_pct, z, src)

    for u in card.get("verdict", {}).get("unusual_sessions") or []:
        put(u.get("d"), u.get("move_pct"), u.get("z"), f"unusual_sessions[{u.get('timing')}]")
    for key in ("largest", "peak"):
        block = (card.get("verdict") or {}).get(key) or {}
        put(block.get("d"), block.get("move_pct"), block.get("z"), key)
    tape = card.get("tape") or {}
    put(tape.get("move_date"), tape.get("move_pct"), tape.get("z"), f"tape[{tape.get('timing')}]")
    return out


def validate(ids: List[str], payloads: Dict[str, dict]) -> List[dict]:
    """Compare series rel -1/0 against cards by session date; return comparison rows."""
    rows = []
    for cid in ids:
        card_path = CARDS_DIR / f"{cid}.json"
        series = payloads.get(cid) or {}
        by_rel = {s["rel"]: s for s in series.get("sessions") or []}
        if not card_path.exists():
            for rel in (-1, 0):
                s = by_rel.get(rel)
                rows.append({
                    "content_id": cid,
                    "rel": rel,
                    "d": s["d"] if s else None,
                    "series_move": s["move_pct"] if s else None,
                    "series_z": s["z"] if s else None,
                    "card_move": None,
                    "card_z": None,
                    "match": "no_card",
                    "note": "card missing",
                })
            continue

        card = json.loads(card_path.read_text())
        by_date = card_date_lookup(card)

        for rel in (-1, 0):
            s = by_rel.get(rel)
            card_move = card_z = None
            note = ""
            if s is not None and s["d"] in by_date:
                card_move, card_z, note = by_date[s["d"]]

            if s is None:
                match = "series_missing"
            elif card_move is None and card_z is None:
                match = "n/a"
                note = "card has no field for this session date"
            else:
                sm, sz = s["move_pct"], s["z"]
                ok = sm == card_move and sz == card_z
                match = "OK" if ok else "MISMATCH"
                if not ok:
                    note = (
                        f"{note}; series move={sm} z={sz} vs card move={card_move} z={card_z}"
                    )

            rows.append({
                "content_id": cid,
                "rel": rel,
                "d": s["d"] if s else None,
                "series_move": s["move_pct"] if s else None,
                "series_z": s["z"] if s else None,
                "card_move": card_move,
                "card_z": card_z,
                "match": match,
                "note": note,
            })
    return rows


def print_table(rows: List[dict]) -> None:
    headers = ["content_id", "rel", "series_move", "series_z", "card_move", "card_z", "match"]
    widths = {h: len(h) for h in headers}
    for r in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(r.get(h, ""))))
    fmt = "  ".join(f"{{:<{widths[h]}}}" for h in headers)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * widths[h] for h in headers)))
    for r in rows:
        print(fmt.format(*(str(r.get(h, "")) for h in headers)))

    mismatches = [r for r in rows if r["match"] == "MISMATCH"]
    if mismatches:
        print("\nMismatch detail:")
        for r in mismatches:
            print(f"  {r['content_id']} rel={r['rel']}: {r['note']}")
    else:
        print("\nAll comparable rel -1/0 values match the cards (or card had no field).")


def main() -> None:
    ids = load_ids(sys.argv)
    print(f"Querying series for {len(ids)} ids…", file=sys.stderr)
    raw = bq_series(ids)
    by_id: Dict[str, List[dict]] = {cid: [] for cid in ids}
    for r in raw:
        by_id.setdefault(r["content_id"], []).append(r)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payloads: Dict[str, dict] = {}
    index = []
    for cid in ids:
        payload = build_payload(cid, by_id.get(cid, []))
        payloads[cid] = payload
        (OUT_DIR / f"{cid}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )
        index.append({
            "content_id": cid,
            "des_azione": payload.get("des_azione"),
            "cod_azione": payload.get("cod_azione"),
            "n_sessions": len(payload.get("sessions") or []),
        })
        print(f"wrote {cid} ({len(payload.get('sessions') or [])} sessions)", file=sys.stderr)

    (OUT_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"wrote index.json ({len(index)} entries)", file=sys.stderr)

    print("\n=== Validation vs data/cards ===")
    print_table(validate(ids, payloads))


if __name__ == "__main__":
    main()
