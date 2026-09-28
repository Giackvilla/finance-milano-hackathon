#!/usr/bin/env python3
"""Unit tests for the Fear & Greed tilt, percentiles, and shock counts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fear_greed import (  # noqa: E402
    SQL_PATH,
    build_italy,
    build_payload,
    build_sector_series,
    carry_forward,
    italy_shock_counts,
    label_for,
    load_sectors,
    members_in_sql,
    percentile_rank,
    shock_counts,
    tilt_weights,
)


def _raw(date, raw, narrative, shocks, down, up, names, headlines=None):
    return {
        "date": date,
        "momentum_raw": raw,
        "strength_raw": raw,
        "breadth_raw": raw,
        "vol_raw": raw,
        "narrative_pct": narrative,
        "shocks": shocks,
        "shocks_down": down,
        "shocks_up": up,
        "names": names,
        "headlines": headlines or [],
    }


class PercentileTest(unittest.TestCase):
    def test_cume_dist_scale(self):
        history = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(percentile_rank(1.0, history), 100.0 / 3)
        self.assertAlmostEqual(percentile_rank(2.0, history), 200.0 / 3)
        self.assertAlmostEqual(percentile_rank(3.0, history), 100.0)

    def test_empty_history_rejected(self):
        with self.assertRaises(ValueError):
            percentile_rank(1.0, [])


class TiltTest(unittest.TestCase):
    def test_neutral_is_equal(self):
        weights = tilt_weights(50)
        for key in ("momentum", "strength", "volatility", "breadth", "narrative"):
            self.assertAlmostEqual(weights[key], 0.20)
        self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_fear_raises_volatility_and_breadth(self):
        fear = tilt_weights(0)
        neutral = tilt_weights(50)
        self.assertGreater(fear["volatility"], neutral["volatility"])
        self.assertGreater(fear["breadth"], neutral["breadth"])
        self.assertLess(fear["momentum"], neutral["momentum"])
        self.assertLess(fear["strength"], neutral["strength"])
        self.assertAlmostEqual(fear["narrative"], 0.20)
        self.assertAlmostEqual(sum(fear.values()), 1.0)

    def test_greed_raises_momentum_and_strength(self):
        greed = tilt_weights(100)
        neutral = tilt_weights(50)
        self.assertGreater(greed["momentum"], neutral["momentum"])
        self.assertGreater(greed["strength"], neutral["strength"])
        self.assertLess(greed["volatility"], neutral["volatility"])
        self.assertLess(greed["breadth"], neutral["breadth"])
        self.assertAlmostEqual(greed["narrative"], 0.20)
        self.assertAlmostEqual(sum(greed.values()), 1.0)


class LabelTest(unittest.TestCase):
    def test_band_edges(self):
        self.assertEqual(label_for(0), "Extreme fear")
        self.assertEqual(label_for(24.9), "Extreme fear")
        self.assertEqual(label_for(25), "Fear")
        self.assertEqual(label_for(44.9), "Fear")
        self.assertEqual(label_for(45), "Neutral")
        self.assertEqual(label_for(54.9), "Neutral")
        self.assertEqual(label_for(55), "Greed")
        self.assertEqual(label_for(74.9), "Greed")
        self.assertEqual(label_for(75), "Extreme greed")
        self.assertEqual(label_for(100), "Extreme greed")


class CarryTest(unittest.TestCase):
    def test_leading_gap_stays_neutral_then_holds(self):
        self.assertEqual(carry_forward([None, None]), [50.0, 50.0])
        self.assertEqual(carry_forward([None, 80.0, None]), [50.0, 80.0, 80.0])
        self.assertEqual(carry_forward([10.0, None]), [10.0, 10.0])


class ShockTest(unittest.TestCase):
    def test_cut_and_sign(self):
        rows = [
            {"z": 2.0, "ret": 0.04},
            {"z": -2.0, "ret": -0.03},
            {"z": 1.9, "ret": 0.02},
            {"z": -1.9, "ret": -0.02},
            {"z": None, "ret": 0.5},
        ]
        counted = shock_counts(rows)
        self.assertEqual(counted["shocks"], 2)
        self.assertEqual(counted["shocks_up"], 1)
        self.assertEqual(counted["shocks_down"], 1)
        self.assertEqual(counted["names"], 5)
        self.assertAlmostEqual(counted["shock_share"], 2 / 5)

    def test_italy_is_the_sum(self):
        italy = italy_shock_counts([
            {"shocks": 1, "shocks_down": 1, "shocks_up": 0, "names": 4},
            {"shocks": 2, "shocks_down": 0, "shocks_up": 2, "names": 6},
        ])
        self.assertEqual(italy["shocks"], 3)
        self.assertEqual(italy["shocks_down"], 1)
        self.assertEqual(italy["shocks_up"], 2)
        self.assertEqual(italy["names"], 10)
        self.assertAlmostEqual(italy["shock_share"], 0.3)


class SeriesTest(unittest.TestCase):
    def test_vol_is_inverted_and_gap_keeps_previous_narrative(self):
        series = build_sector_series([
            _raw("2024-01-02", 1.0, None, 1, 1, 0, 4),
            _raw("2024-01-03", 2.0, 80.0, 0, 0, 0, 4, ["Enel sale"]),
            _raw("2024-01-04", 3.0, None, 2, 0, 2, 4),
        ])
        self.assertEqual([day["components"]["narrative"]["value"] for day in series], [50.0, 80.0, 80.0])
        self.assertAlmostEqual(series[0]["components"]["volatility"]["value"], 100.0 - 100.0 / 3)
        self.assertAlmostEqual(series[2]["components"]["volatility"]["value"], 0.0)
        self.assertAlmostEqual(series[2]["components"]["momentum"]["value"], 100.0)
        self.assertEqual(series[1]["headlines"], ["Enel sale"])
        self.assertEqual(series[2]["shocks_5d"], 3)
        self.assertEqual(series[2]["shocks_down_5d"], 1)
        self.assertEqual(series[2]["shocks_up_5d"], 2)
        middle = series[1]
        self.assertAlmostEqual(
            middle["score"],
            sum(
                middle["components"][key]["value"] * middle["components"][key]["weight"]
                for key in middle["components"]
            ),
        )

    def test_italy_averages_scores_and_sums_shocks(self):
        left = build_sector_series([_raw("2024-01-02", 1.0, 20.0, 1, 1, 0, 4)])
        right = build_sector_series([_raw("2024-01-02", 1.0, 80.0, 2, 0, 2, 6)])
        italy = build_italy({"banche": left, "energia": right})
        self.assertEqual(len(italy), 1)
        self.assertAlmostEqual(italy[0]["score"], (left[0]["score"] + right[0]["score"]) / 2)
        self.assertEqual(italy[0]["shocks"], 3)
        self.assertEqual(italy[0]["names"], 10)
        self.assertEqual(italy[0]["shocks_5d"], 3)

    def test_payload_uses_sector_name_and_band(self):
        sectors = [
            {"id": "banche", "label": "Banche", "codes": ["AMBR"]},
            {"id": "energia", "label": "Energia", "codes": ["ENEL"]},
        ]
        raw = []
        for sector, narrative, shocks in (("banche", 20.0, 1), ("energia", 80.0, 2)):
            raw.append({
                "sector": sector,
                **_raw("2024-01-02", 1.0, narrative, shocks, shocks, 0, 4, ["titolo"]),
            })
        payload = build_payload(raw, sectors)
        self.assertEqual(payload["as_of"], "2024-01-02")
        self.assertEqual(payload["sectors"][0]["name"], "Banche")
        self.assertEqual(payload["sectors"][0]["label"], payload["sectors"][0]["series"][-1]["label"])
        self.assertNotIn("headlines", payload["italy"])
        self.assertEqual(payload["italy"]["shocks"], 3)


class MembersTest(unittest.TestCase):
    def test_sql_lists_the_same_baskets(self):
        sectors = load_sectors()
        sql = SQL_PATH.read_text()
        from_sql = members_in_sql(sql)
        from_json = [(sector["id"], code) for sector in sectors for code in sector["codes"]]
        self.assertEqual(from_sql, from_json)
        self.assertEqual(len(from_json), 30)


if __name__ == "__main__":
    unittest.main()
