#!/usr/bin/env python3
"""Contract checks on the dashboard bundle in web/public/data (run after export)."""

from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_dashboard import OUT_DIR, SCHEMA_VERSION, slugify  # noqa: E402

STORY_ROW_KEYS = {
    "content_id", "titolo", "pub_local", "url", "des_azione", "cod_azione",
    "company_slug", "news_type", "headline_reports_move", "publication_phase",
    "status", "peak_date", "peak_timing", "peak_move_pct", "peak_z",
    "retained_pct", "adjective_matches", "has_gemini", "has_series",
}
STORY_KEYS = {
    "schema_version", "content_id", "article", "instrument", "news",
    "verdict", "tape", "gemini", "series",
}
COMPANY_KEYS = {"schema_version", "slug", "des_azione", "cod_azione", "isin", "summary", "stories", "prices"}
PRICE_COLS = ("d", "close", "volume", "move_pct", "z")


def load(rel: str):
    return json.loads((OUT_DIR / rel).read_text())


def walk_numbers(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from walk_numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_numbers(v)
    elif isinstance(obj, float):
        yield obj


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OUT_DIR / "manifest.json").exists():
            raise unittest.SkipTest(f"no bundle at {OUT_DIR}; run scripts/export_dashboard.py")
        cls.manifest = load("manifest.json")
        cls.stories = load("stories.json")
        cls.meta = load("status_meta.json")
        cls.summary = load("summary.json")
        cls.companies = load("companies.json")
        cls.statuses = {m["status"] for m in cls.meta["statuses"]}

    def test_schema_version(self):
        for name in ("manifest.json", "summary.json", "status_meta.json"):
            with self.subTest(name=name):
                self.assertEqual(load(name)["schema_version"], SCHEMA_VERSION)

    def test_manifest_counts(self):
        c = self.manifest["counts"]
        self.assertEqual(c["stories"], len(self.stories))
        self.assertEqual(c["stories_with_gemini"], sum(r["has_gemini"] for r in self.stories))
        self.assertEqual(c["stories_with_series"], sum(r["has_series"] for r in self.stories))
        self.assertEqual(c["companies"], len(self.companies))

    def test_story_rows_and_details_agree(self):
        ids = [r["content_id"] for r in self.stories]
        self.assertEqual(len(ids), len(set(ids)))
        on_disk = {p.stem for p in (OUT_DIR / "stories").glob("*.json")}
        self.assertEqual(on_disk, set(ids))
        for r in self.stories:
            with self.subTest(content_id=r["content_id"]):
                self.assertEqual(set(r), STORY_ROW_KEYS)
                self.assertIn(r["status"], self.statuses)
                s = load(f"stories/{r['content_id']}.json")
                self.assertEqual(set(s), STORY_KEYS)
                self.assertEqual(s["schema_version"], SCHEMA_VERSION)
                self.assertEqual(s["verdict"]["status"], r["status"])
                self.assertEqual(r["has_gemini"], any(s["gemini"][l] for l in ("en", "it")))
                self.assertEqual(r["has_series"], s["series"] is not None)
                self.assertEqual(set(s["tape"]["facts_text"]), {"en", "it"})
                if s["series"]:
                    self.assertTrue(s["series"]["sessions"])

    def test_story_companies_exist(self):
        slugs = {c["slug"] for c in self.companies}
        for r in self.stories:
            with self.subTest(content_id=r["content_id"]):
                self.assertIn(r["company_slug"], slugs)
                self.assertTrue((OUT_DIR / "companies" / f"{r['company_slug']}.json").exists())

    def test_companies(self):
        on_disk = {p.stem for p in (OUT_DIR / "companies").glob("*.json")}
        self.assertEqual(on_disk, {c["slug"] for c in self.companies})
        story_ids = {r["content_id"] for r in self.stories}
        for entry in self.companies:
            with self.subTest(slug=entry["slug"]):
                c = load(f"companies/{entry['slug']}.json")
                self.assertEqual(set(c), COMPANY_KEYS)
                self.assertEqual(c["summary"]["n_stories"], len(c["stories"]))
                self.assertEqual(entry["n_stories"], len(c["stories"]))
                self.assertEqual(sum(c["summary"]["status"].values()), len(c["stories"]))
                for st in c["stories"]:
                    self.assertIn(st["status"], self.statuses)
                    self.assertEqual(st["has_detail"], st["content_id"] in story_ids)
                self.assertEqual(entry["has_prices"], c["prices"] is not None)
                if c["prices"]:
                    n = len(c["prices"]["d"])
                    self.assertEqual({len(c["prices"][k]) for k in PRICE_COLS}, {n})

    def test_summary_statuses_known(self):
        for block in ("first_articles", "all_matched"):
            with self.subTest(block=block):
                got = [x["status"] for x in self.summary[block]["status"]]
                self.assertEqual(set(got), self.statuses)

    def test_no_nan_or_infinity(self):
        files = [OUT_DIR / "stories.json", OUT_DIR / "summary.json", OUT_DIR / "companies.json"]
        files += sorted((OUT_DIR / "stories").glob("*.json"))
        for p in files:
            with self.subTest(file=p.name):
                self.assertNotIn("NaN", p.read_text())
                self.assertTrue(all(math.isfinite(x) for x in walk_numbers(json.loads(p.read_text()))))


class SlugTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Garofalo Health Care"), "garofalo-health-care")
        self.assertEqual(slugify("Banca Popolare di Sondrio"), "banca-popolare-di-sondrio")
        self.assertEqual(slugify("Città & Co."), "citta-co")


if __name__ == "__main__":
    unittest.main()
