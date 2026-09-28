#!/usr/bin/env python3
"""Unit tests for the body-first Gemini classifier."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_gemini import (  # noqa: E402
    ClassificationError,
    classify_article,
    find_instrument_candidates,
    parse_document,
    validate_classification,
)


INSTRUMENTS = [
    {
        "COD_AZIONE": "PRY",
        "DES_AZIONE": "Prysmian",
        "COD_ISIN": "IT0004176001",
    },
    {
        "COD_AZIONE": "ENI",
        "DES_AZIONE": "Eni",
        "COD_ISIN": "IT0003132476",
    },
]


class CandidateTests(unittest.TestCase):
    def test_title_match_is_ranked_before_body_only_match(self):
        candidates = find_instrument_candidates(
            "Prysmian colloca nuove azioni",
            "L'operazione di Prysmian segue un precedente accordo con Eni.",
            INSTRUMENTS,
        )
        self.assertEqual([c["COD_AZIONE"] for c in candidates], ["PRY", "ENI"])

    def test_name_matching_respects_word_boundaries(self):
        candidates = find_instrument_candidates("Benigni", "Nessun emittente", INSTRUMENTS)
        self.assertEqual(candidates, [])


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.title = "Prysmian colloca nuove azioni"
        self.body = (
            "Prysmian ha collocato nuove azioni per finanziare l'acquisizione. "
            "Il gruppo userà i proventi per l'operazione."
        )

    def valid_result(self):
        return {
            "company_name": "Prysmian",
            "ticker": "PRY",
            "company_evidence": "Prysmian",
            "primary_topic": "capital",
            "topics": [
                {
                    "topic": "capital",
                    "confidence": 0.98,
                    "evidence": "ha collocato nuove azioni",
                },
                {
                    "topic": "deal",
                    "confidence": 0.82,
                    "evidence": "finanziare l'acquisizione",
                },
            ],
            "summary": "Prysmian raccoglie capitale per finanziare un'acquisizione.",
        }

    def test_valid_result_resolves_official_instrument(self):
        instrument, errors = validate_classification(
            self.valid_result(), self.title, self.body, [INSTRUMENTS[0]]
        )
        self.assertEqual(errors, [])
        self.assertEqual(instrument["COD_ISIN"], "IT0004176001")

    def test_rejects_more_than_three_topics_and_non_verbatim_evidence(self):
        result = self.valid_result()
        result["topics"] = result["topics"] + [
            {"topic": "plan", "confidence": 0.5, "evidence": "invented"},
            {"topic": "analyst", "confidence": 0.5, "evidence": "invented again"},
        ]
        _, errors = validate_classification(
            result, self.title, self.body, [INSTRUMENTS[0]]
        )
        self.assertTrue(any("between one and three" in error for error in errors))

    def test_rejects_ticker_company_pair_from_different_candidates(self):
        result = self.valid_result()
        result["ticker"] = "ENI"
        _, errors = validate_classification(result, self.title, self.body, INSTRUMENTS)
        self.assertTrue(any("matching BigQuery candidate" in error for error in errors))


class ClassifierTests(unittest.TestCase):
    @patch("classify_gemini.call_vertex_gemini")
    def test_card_compatible_output_and_retry(self, call_mock):
        invalid = ValidationTests().valid_result()
        invalid["topics"][0]["evidence"] = "not in the body"
        valid = ValidationTests().valid_result()
        call_mock.side_effect = [invalid, valid]
        article = {
            "content_id": "123",
            "titolo": "Prysmian colloca nuove azioni",
            "body": (
                "Prysmian ha collocato nuove azioni per finanziare l'acquisizione. "
                "Il gruppo userà i proventi per l'operazione."
            ),
        }

        card = classify_article(article, INSTRUMENTS, model="gemini-test")

        self.assertEqual(card["instrument"]["cod_azione"], "PRY")
        self.assertEqual(card["news"]["news_type"], "capital")
        self.assertEqual(len(card["news"]["topics"]), 2)
        self.assertTrue(card["gemini"]["checks"]["instrument_validated"])
        self.assertEqual(card["gemini"]["attempts"], 2)
        self.assertEqual(call_mock.call_count, 2)
        retry_prompt = call_mock.call_args_list[1].args[0]
        self.assertIn("previous response failed validation", retry_prompt)

    def test_requires_a_bigquery_instrument_match(self):
        with self.assertRaisesRegex(ClassificationError, "No listed company"):
            classify_article(
                {"titolo": "Unknown Corp", "body": "Unknown Corp reported revenue."},
                INSTRUMENTS,
            )


class InputTests(unittest.TestCase):
    def test_json_input_accepts_common_field_names(self):
        article = parse_document(
            json.dumps({"headline": "Eni results", "text": "Eni reported revenue."}),
            title=None,
            source="article.json",
        )
        self.assertEqual(article["titolo"], "Eni results")
        self.assertEqual(article["body"], "Eni reported revenue.")

    def test_plain_text_uses_title_override(self):
        article = parse_document("Eni reported revenue.", "Eni results", "stdin")
        self.assertEqual(article["titolo"], "Eni results")
        self.assertEqual(article["body"], "Eni reported revenue.")


if __name__ == "__main__":
    unittest.main()
