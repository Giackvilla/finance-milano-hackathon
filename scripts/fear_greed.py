#!/usr/bin/env python3
"""Italy and sector Fear & Greed, plus 2σ shock counts.

Usage:
    python3 scripts/fear_greed.py

Reads sql/fear_greed.sql (tape legs, shock counts, narrative percentile) and
data/sectors.json. Percentiles of the tape legs and the narrative weight tilt
are applied here. Writes data/fear_greed.json and a slim snapshot at
web/dashboard/fear_greed.js for the desk.

A shock is |daily return| >= 2 * the stddev of the previous 20 sessions.
Narrative near 0 raises the volatility and breadth weights. Narrative near 100
raises momentum and strength. The narrative weight stays 0.20 before
renormalization. Shock counts are reported beside the score and are not tilted.
"""

from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PROJECT = "class-hackaton-09"
Z_CUT = 2.0
NEUTRAL_NARRATIVE = 50.0
COMPONENT_KEYS = ("momentum", "strength", "breadth", "volatility", "narrative")
TRAILING_SESSIONS = 5

SECTORS_PATH = ROOT / "data" / "sectors.json"
SQL_PATH = ROOT / "sql" / "fear_greed.sql"
OUT_PATH = ROOT / "data" / "fear_greed.json"
DASH_JS = ROOT / "web" / "dashboard" / "fear_greed.js"
# Demo desk keys differ from COD_AZIONE for a few names.
DEMO_ALIAS = {"AMBR": "ISP", "SAIP": "SPM", "FINME": "LDO", "FIAT": "STLAM"}

_MEMBER = re.compile(r"STRUCT\('([a-z]+)' AS sector, '([A-Z0-9]+)' AS cod\)")


def percentile_rank(value: float, history: list[float]) -> float:
    """Percent of history at or below value, on a 0–100 scale (CUME_DIST)."""
    if not history:
        raise ValueError("empty history")
    return 100.0 * sum(1 for item in history if item <= value) / len(history)


def tilt_weights(narrative: float) -> dict[str, float]:
    """Tape weights start at 0.20. Fear raises volatility and breadth.

    Greed raises momentum and strength. Narrative stays 0.20 before the
    weights are renormalized to 1.
    """
    bias = (narrative - NEUTRAL_NARRATIVE) / NEUTRAL_NARRATIVE
    raw = {
        "momentum": 0.20 + 0.10 * bias,
        "strength": 0.20 + 0.05 * bias,
        "volatility": 0.20 - 0.10 * bias,
        "breadth": 0.20 - 0.05 * bias,
        "narrative": 0.20,
    }
    total = sum(raw.values())
    return {key: weight / total for key, weight in raw.items()}


def label_for(score: float) -> str:
    """Bands 0–25, 25–45, 45–55, 55–75, 75–100. The shared edge starts the next band."""
    if score < 25:
        return "Extreme fear"
    if score < 45:
        return "Fear"
    if score < 55:
        return "Neutral"
    if score < 75:
        return "Greed"
    return "Extreme greed"


def carry_forward(values: list[float | None]) -> list[float]:
    """Keep the previous narrative score. Leading gaps stay neutral (50)."""
    out: list[float] = []
    previous = NEUTRAL_NARRATIVE
    for value in values:
        if value is None:
            out.append(previous)
        else:
            previous = float(value)
            out.append(previous)
    return out


def shock_fields(shocks: int, shocks_down: int, shocks_up: int, names: int) -> dict:
    return {
        "shocks": shocks,
        "shocks_down": shocks_down,
        "shocks_up": shocks_up,
        "names": names,
        "shock_share": (shocks / names) if names else 0.0,
    }


def shock_counts(rows: list[dict]) -> dict:
    """Count names with |z| >= 2. Down and up split on the sign of the return."""
    shocks = shocks_down = shocks_up = 0
    for row in rows:
        z = row["z"]
        if z is None or abs(z) < Z_CUT:
            continue
        shocks += 1
        if row["ret"] < 0:
            shocks_down += 1
        elif row["ret"] > 0:
            shocks_up += 1
    return shock_fields(shocks, shocks_down, shocks_up, len(rows))


def italy_shock_counts(parts: list[dict]) -> dict:
    """Italy is the sum of sector counts. Baskets do not overlap."""
    return shock_fields(
        sum(part["shocks"] for part in parts),
        sum(part["shocks_down"] for part in parts),
        sum(part["shocks_up"] for part in parts),
        sum(part["names"] for part in parts),
    )


def with_trailing(days: list[dict], n: int = TRAILING_SESSIONS) -> list[dict]:
    out = []
    for index, day in enumerate(days):
        window = days[max(0, index - n + 1) : index + 1]
        packed = dict(day)
        packed["shocks_5d"] = sum(item["shocks"] for item in window)
        packed["shocks_down_5d"] = sum(item["shocks_down"] for item in window)
        packed["shocks_up_5d"] = sum(item["shocks_up"] for item in window)
        out.append(packed)
    return out


def score_from(values: dict[str, float], weights: dict[str, float]) -> float:
    return sum(values[key] * weights[key] for key in COMPONENT_KEYS)


def build_sector_series(raw_rows: list[dict]) -> list[dict]:
    raw_rows = sorted(raw_rows, key=lambda row: row["date"])
    histories = {
        "momentum": [row["momentum_raw"] for row in raw_rows],
        "strength": [row["strength_raw"] for row in raw_rows],
        "breadth": [row["breadth_raw"] for row in raw_rows],
        "volatility": [row["vol_raw"] for row in raw_rows],
    }
    narrative = carry_forward([row["narrative_pct"] for row in raw_rows])
    days = []
    for index, raw in enumerate(raw_rows):
        values = {
            "momentum": percentile_rank(raw["momentum_raw"], histories["momentum"]),
            "strength": percentile_rank(raw["strength_raw"], histories["strength"]),
            "breadth": percentile_rank(raw["breadth_raw"], histories["breadth"]),
            "volatility": 100.0 - percentile_rank(raw["vol_raw"], histories["volatility"]),
            "narrative": narrative[index],
        }
        weights = tilt_weights(narrative[index])
        score = score_from(values, weights)
        days.append({
            "date": raw["date"],
            "score": score,
            "label": label_for(score),
            "components": {
                key: {"value": values[key], "weight": weights[key]}
                for key in COMPONENT_KEYS
            },
            **shock_fields(raw["shocks"], raw["shocks_down"], raw["shocks_up"], raw["names"]),
            "headlines": list(raw.get("headlines") or []),
        })
    return with_trailing(days)


def build_italy(sector_series: dict[str, list[dict]]) -> list[dict]:
    """Equal-weight average of the sector scores on dates present for every sector."""
    by_date: dict[str, list[dict]] = {}
    for series in sector_series.values():
        for day in series:
            by_date.setdefault(day["date"], []).append(day)
    n_sectors = len(sector_series)
    italy = []
    for date in sorted(by_date):
        days = by_date[date]
        if len(days) != n_sectors:
            continue
        score = sum(day["score"] for day in days) / n_sectors
        components = {}
        for key in COMPONENT_KEYS:
            components[key] = {
                "value": sum(day["components"][key]["value"] for day in days) / n_sectors,
                "weight": sum(day["components"][key]["weight"] for day in days) / n_sectors,
            }
        shocks = italy_shock_counts(days)
        italy.append({
            "date": date,
            "score": score,
            "label": label_for(score),
            "components": components,
            **shocks,
        })
    return with_trailing(italy)


def public_day(day: dict, *, headlines: bool) -> dict:
    packed = {
        "date": day["date"],
        "score": round(day["score"], 1),
        "label": day["label"],
        "components": {
            key: {
                "value": round(day["components"][key]["value"], 1),
                "weight": round(day["components"][key]["weight"], 4),
            }
            for key in COMPONENT_KEYS
        },
        "shocks": day["shocks"],
        "shocks_down": day["shocks_down"],
        "shocks_up": day["shocks_up"],
        "names": day["names"],
        "shock_share": round(day["shock_share"], 4),
        "shocks_5d": day["shocks_5d"],
        "shocks_down_5d": day["shocks_down_5d"],
        "shocks_up_5d": day["shocks_up_5d"],
    }
    if headlines:
        packed["headlines"] = day.get("headlines") or []
    return packed


def load_sectors(path: Path = SECTORS_PATH) -> list[dict]:
    return json.loads(path.read_text())["sectors"]


def members_in_sql(sql: str) -> list[tuple[str, str]]:
    return _MEMBER.findall(sql)


def assert_members_match(sectors: list[dict], sql: str) -> None:
    from_sql = members_in_sql(sql)
    from_json = [(sector["id"], code) for sector in sectors for code in sector["codes"]]
    if from_sql != from_json:
        raise SystemExit("data/sectors.json and sql/fear_greed.sql list different members")


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def parse_row(row: dict) -> dict:
    headlines = row.get("headlines") or "[]"
    if isinstance(headlines, str):
        headlines = json.loads(headlines) if headlines.strip() else []
    narrative = row.get("narrative_pct")
    return {
        "sector": row["sector"],
        "date": str(row["d"])[:10],
        "momentum_raw": float(row["momentum_raw"]),
        "strength_raw": float(row["strength_raw"]),
        "breadth_raw": float(row["breadth_raw"]),
        "vol_raw": float(row["vol_raw"]),
        "narrative_pct": None if _blank(narrative) else float(narrative),
        "shocks": int(float(row["shocks"])),
        "shocks_down": int(float(row["shocks_down"])),
        "shocks_up": int(float(row["shocks_up"])),
        "names": int(float(row["names"])),
        "headlines": headlines,
    }


def build_payload(raw_rows: list[dict], sectors: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for row in raw_rows:
        grouped.setdefault(row["sector"], []).append(row)
    series = {}
    for sector in sectors:
        rows = grouped.get(sector["id"])
        if not rows:
            raise SystemExit(f"no sessions for sector {sector['id']}")
        series[sector["id"]] = build_sector_series(rows)
    italy = build_italy(series)
    if not italy:
        raise SystemExit("no date is present for every sector")
    return {
        "as_of": italy[-1]["date"],
        "italy": public_day(italy[-1], headlines=False),
        "sectors": [
            {
                "id": sector["id"],
                "name": sector["label"],
                **public_day(series[sector["id"]][-1], headlines=True),
                "series": [
                    public_day(day, headlines=True) for day in series[sector["id"]]
                ],
            }
            for sector in sectors
        ],
        "italy_series": [public_day(day, headlines=False) for day in italy],
    }


def _spark(series: list[dict], n: int = 63) -> list[float]:
    return [day["score"] for day in series[-n:]]


def write_dashboard_js(payload: dict, sectors: list[dict], path: Path = DASH_JS) -> None:
    """Slim snapshot for the desk. The full history stays in data/fear_greed.json."""
    codes = {sector["id"]: sector["codes"] for sector in sectors}

    def tickers(sector_id: str) -> list[str]:
        return [DEMO_ALIAS.get(code, code) for code in codes.get(sector_id, [])]

    def slim(day: dict, spark: list[float], headlines: bool) -> dict:
        packed = {
            "date": day["date"],
            "score": day["score"],
            "label": day["label"],
            "components": day["components"],
            "shocks": day["shocks"],
            "shocks_down": day["shocks_down"],
            "shocks_up": day["shocks_up"],
            "names": day["names"],
            "shock_share": day["shock_share"],
            "shocks_5d": day["shocks_5d"],
            "shocks_down_5d": day["shocks_down_5d"],
            "shocks_up_5d": day["shocks_up_5d"],
            "spark": spark,
        }
        if headlines:
            packed["headlines"] = day.get("headlines") or []
        return packed

    desk = {
        "as_of": payload["as_of"],
        "italy": slim(payload["italy"], _spark(payload.get("italy_series") or []), False),
        "sectors": [
            {
                "id": sector["id"],
                "name": sector["name"],
                "tickers": tickers(sector["id"]),
                **slim(sector, _spark(sector.get("series") or []), True),
            }
            for sector in payload["sectors"]
        ],
    }
    # public_day already rounded the latest block; don't round twice.
    text = (
        "/* Generated by scripts/fear_greed.py from data/fear_greed.json. Do not edit. */\n"
        "window.FEAR_GREED = "
        + json.dumps(desk, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    path.write_text(text)


def bq_rows() -> list[dict]:
    sql = SQL_PATH.read_text()
    cmd = [
        "bq", f"--project_id={PROJECT}", "query",
        "--use_legacy_sql=false", "--quiet", "--format=csv",
        "--max_rows=100000",
        "--maximum_bytes_billed=3000000000",
    ]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(f"bq failed with exit {proc.returncode}")
    out = proc.stdout
    if out.startswith("Waiting"):
        out = out.split("\n", 1)[1]
    return [parse_row(row) for row in csv.DictReader(io.StringIO(out))]


def main() -> None:
    sectors = load_sectors()
    assert_members_match(sectors, SQL_PATH.read_text())
    raw_rows = bq_rows()
    if not raw_rows:
        sys.exit("fear_greed query returned no rows")
    payload = build_payload(raw_rows, sectors)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    write_dashboard_js(payload, sectors)
    italy = payload["italy"]
    print(
        f"wrote {OUT_PATH} as_of={payload['as_of']} "
        f"italy={italy['score']} {italy['label']} "
        f"shocks={italy['shocks_down']} down / {italy['shocks_up']} up"
    )
    for sector in payload["sectors"]:
        narr = sector["components"]["narrative"]
        print(
            f"  {sector['name']}: {sector['score']} {sector['label']} "
            f"narrative={narr['value']} w={narr['weight']} "
            f"shocks={sector['shocks_down']} down / {sector['shocks_up']} up "
            f"5d={sector['shocks_5d']}"
        )


if __name__ == "__main__":
    main()
