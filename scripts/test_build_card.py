#!/usr/bin/env python3
"""Unit tests for build_card number normaliser and recommendation check."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_card import (  # noqa: E402
    extract_normalised_numbers,
    gemini_checks,
    normalise_number_token,
    numbers_not_in_sources,
    recommendation_words_not_in_article,
)


class NumberNormaliserTests(unittest.TestCase):
    def test_variants_equal(self):
        pairs = [
            ("1.234,5", "1234.5"),
            ("-19,2", "-19.2"),
            ("−19.2", "-19.2"),
            ("+9%", "9"),
            ("(-20%)", "-20"),
            ("1,5", "1.5"),
            ("1.5", "1.5"),
        ]
        for a, b in pairs:
            with self.subTest(a=a, b=b):
                self.assertEqual(normalise_number_token(a), normalise_number_token(b))

    def test_extract_set(self):
        text = "The stock fell (-19,2%) after already being −16.8% at the open."
        nums = extract_normalised_numbers(text)
        self.assertIn(-19.2, nums)
        self.assertIn(-16.8, nums)

    def test_numbers_not_in_sources(self):
        sources = "body says -19,2% and facts say 8.8 times"
        sentence_ok = "The figure -19.2% matches; 8,8 times normal."
        sentence_bad = "The stock moved 42% which is nowhere."
        self.assertEqual(numbers_not_in_sources(sentence_ok, sources), [])
        missing = numbers_not_in_sources(sentence_bad, sources)
        self.assertTrue(any(abs(x - 42.0) < 1e-6 for x in missing))


class RecommendationCheckTests(unittest.TestCase):
    def test_flags_buy_absent_from_article(self):
        sent = "Investors should buy the stock after the drop."
        art = "Seri Industrial tracolla in borsa (-20%). Il titolo ha chiuso in calo."
        bad = recommendation_words_not_in_article(sent, art)
        self.assertTrue(any(w.lower() == "buy" for w in bad))

    def test_allows_vende_quoted_from_title(self):
        title = "Il fondo vende azioni di Amplifon"
        sent = "The title says the fund vende azioni, matching the body stake sale."
        art = f"{title}\nIl fondo ha ceduto una quota."
        bad = recommendation_words_not_in_article(sent, art)
        self.assertEqual(bad, [])

    def test_allows_vendite_meaning_sales(self):
        # 'vendite' must NOT match the recommendation regex (sales ≠ sell advice)
        sent = "Le vendite al dettaglio sono salite."
        art = "Nessuna parola di raccomandazione qui."
        bad = recommendation_words_not_in_article(sent, art)
        self.assertEqual(bad, [])

    def test_gemini_checks_wire_no_recommendation(self):
        article = {
            "titolo": "Seri Industrial tracolla in borsa (-20%)",
            "body": "Il titolo ha perso il 20% in seduta. Seri Industrial verso il delisting.",
        }
        g = {
            "quote": "Il titolo ha perso il 20% in seduta.",
            "figure_in_body": "20%",
            "title_adjective": "tracolla",
            "sentence": "Do not buy Seri after the drop of 20%.",
        }
        facts = ["The move was -19.2%."]
        c = gemini_checks(g, article, facts)
        self.assertFalse(c["no_recommendation"])
        self.assertTrue(any(w.lower() == "buy" for w in c["recommendation_words_flagged"]))


if __name__ == "__main__":
    unittest.main()
