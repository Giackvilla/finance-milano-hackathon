#!/usr/bin/env python3
"""The combined classifier on the 14 demo cards, plus the Webuild failure."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from choose_news import choose_news_type, evidence_supports  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "data" / "cards_gemini_it"

# Hand-checked: first Gemini topic whose quote matches that topic's rules.
EXPECTED = {
    "Pininfarina": "takeover",
    "Newprinces": "earnings",
    "Italmobiliare": "governance",
    "Trevi": "takeover",
    "Garofalo Health Care": "earnings",
    "Moncler": "market_report",
    "Webuild": "market_report",
    "Iren": "plan",
    "Lottomatica": "deal",
    "Saipem": "market_report",
    "A2a": "market_report",
    "Maire": "deal",
    "Rai Way": "analyst",
    "Nexi": "market_report",
}


class ChooseTests(unittest.TestCase):
    def test_demo_cards(self):
        seen = set()
        for path in CARDS.glob("*.json"):
            if path.name == "index.json":
                continue
            card = json.loads(path.read_text())
            name = card["instrument"]["des_azione"]
            news = card["news"]
            chosen, reason = choose_news_type(
                news.get("keyword_news_type"),
                news.get("topics"),
                card["article"]["titolo"],
            )
            self.assertEqual(chosen, EXPECTED[name], name)
            self.assertEqual(reason, "gemini_quote", name)
            seen.add(name)
        self.assertEqual(seen, set(EXPECTED))

    def test_webuild_capital_quote_does_not_support_capital(self):
        quote = (
            "Webuild contesta la ricostruzione della stampa su possibili extracosti "
            "e precisa di non aver chiesto al governo 22 miliardi di euro"
        )
        self.assertFalse(evidence_supports("capital", quote))

    def test_keyword_title_when_gemini_quotes_fail(self):
        chosen, reason = choose_news_type(
            "earnings",
            [{"topic": "deal", "evidence": "una frase senza termini di deal"}],
            "Società, utile in crescita nel semestre",
        )
        self.assertEqual((chosen, reason), ("earnings", "keyword_title"))

    def test_other_when_nothing_is_supported(self):
        chosen, reason = choose_news_type(
            "other",
            [{"topic": "deal", "evidence": "nessun termine utile"}],
            "Un titolo senza evento",
        )
        self.assertEqual((chosen, reason), ("other", "unsupported"))


if __name__ == "__main__":
    unittest.main()
