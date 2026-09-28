#!/usr/bin/env python3
"""Offline unit tests for story validation and 24-hour headline dedup."""

from __future__ import annotations

import copy
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from story_selection import (  # noqa: E402
    deduplicate_stories,
    filter_valid_stories,
    story_matches_catalog,
)


CATALOG = [
    {"COD_AZIONE": "FINME", "DES_AZIONE": "Leonardo", "COD_ISIN": "IT0003856405"},
    {"COD_AZIONE": "SPM", "DES_AZIONE": "Saipem", "COD_ISIN": "IT0005252140"},
    {"COD_AZIONE": "AMBR", "DES_AZIONE": "Intesa Sanpaolo", "COD_ISIN": "IT0000072618"},
]


def _story(
    content_id: str,
    title: str,
    code: str = "FINME",
    published: str | None = "2024-06-01T10:00:00",
    **extra,
) -> dict:
    row = {
        "content_id": content_id,
        "titolo": title,
        "COD_AZIONE": code,
        "DES_AZIONE": next(
            (r["DES_AZIONE"] for r in CATALOG if r["COD_AZIONE"] == code), "Leonardo"
        ),
    }
    if published is not None:
        row["pub_local"] = published
    row.update(extra)
    return row


class StorySelectionTests(unittest.TestCase):
    def test_same_headline_within_24h_keeps_earlier(self):
        earlier = _story(
            "a1",
            "Leonardo, maxi-ordine per Atr!",
            published="2024-06-01T10:00:00",
        )
        later = _story(
            "a2",
            "leonardo maxi ordine per atr",
            published="2024-06-01T13:00:00",
        )
        out = deduplicate_stories([later, earlier])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["content_id"], "a1")

    def test_same_headline_25h_apart_keeps_both(self):
        first = _story(
            "b1",
            "Leonardo firma contratto",
            published="2024-06-01T10:00:00",
        )
        second = _story(
            "b2",
            "Leonardo firma contratto",
            published="2024-06-02T11:00:00",
        )
        out = deduplicate_stories([first, second])
        self.assertEqual(len(out), 2)
        self.assertEqual({r["content_id"] for r in out}, {"b1", "b2"})

    def test_different_headlines_one_hour_apart(self):
        first = _story(
            "c1",
            "Leonardo firma contratto",
            published="2024-06-01T10:00:00",
        )
        second = _story(
            "c2",
            "Leonardo: nuova commessa in Arabia",
            published="2024-06-01T11:00:00",
        )
        out = deduplicate_stories([first, second])
        self.assertEqual(len(out), 2)

    def test_same_content_id_collapses(self):
        first = _story(
            "same",
            "Leonardo firma contratto",
            published="2024-06-01T10:00:00",
        )
        second = _story(
            "same",
            "Leonardo firma contratto (update)",
            published="2024-06-02T18:00:00",
        )
        out = deduplicate_stories([first, second])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["content_id"], "same")

    def test_missing_timestamps_not_collapsed_by_window(self):
        first = _story("d1", "Leonardo firma contratto", published=None)
        second = _story("d2", "Leonardo firma contratto", published=None)
        # Explicitly omit pub_local
        first.pop("pub_local", None)
        second.pop("pub_local", None)
        out = deduplicate_stories([first, second], window=timedelta(hours=24))
        self.assertEqual(len(out), 2)

    def test_deduplicate_is_deterministic_and_preserves_input(self):
        items = [
            _story("e2", "Leonardo firma contratto", published="2024-06-01T12:00:00"),
            _story("e1", "Leonardo firma contratto", published="2024-06-01T10:00:00"),
        ]
        snapshot = copy.deepcopy(items)
        identities = [id(x) for x in items]
        out1 = deduplicate_stories(items)
        out2 = deduplicate_stories(items)
        self.assertEqual(items, snapshot)
        self.assertEqual([id(x) for x in items], identities)
        self.assertEqual(
            [r["content_id"] for r in out1],
            [r["content_id"] for r in out2],
        )
        self.assertEqual(len(out1), 1)
        self.assertEqual(out1[0]["content_id"], "e1")

    def test_filter_valid_stories_drops_homonym_keeps_company(self):
        bad = _story(
            "bad",
            "Leonardo Capital entra in Weltix per accelerare nella tokenizzazione",
            code="FINME",
        )
        good = _story(
            "good",
            "Leonardo, maxi-ordine per Atr da un miliardo di dollari dall’India",
            code="FINME",
        )
        self.assertFalse(story_matches_catalog(bad, CATALOG))
        self.assertTrue(story_matches_catalog(good, CATALOG))
        kept = filter_valid_stories([bad, good], CATALOG)
        self.assertEqual([r["content_id"] for r in kept], ["good"])

    def test_assigned_counterparty_is_kept(self):
        row = _story("joint", "Saipem e Prysmian firmano un accordo", code="SPM")
        self.assertTrue(story_matches_catalog(row, CATALOG))


if __name__ == "__main__":
    unittest.main()
