#!/usr/bin/env python3
"""Offline unit tests for build_theses helpers (no BQ / Gemini)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_theses import (  # noqa: E402
    aggregate_prompt,
    assign_quarter,
    decision_prompt,
    decision_sources,
    force_insufficiente,
    is_preview_title,
    news_rollup,
    normalise_quote,
    quote_in_body,
    reaction_window,
    thesis_fingerprint,
    verify_decision,
    verify_quarter,
)


class ThesisFingerprintTests(unittest.TestCase):
    BASE = {
        "motivo": "Spesa per la difesa",
        "indicatori": ["Ordini", "Free cash flow"],
        "orizzonte": "3–5 anni",
        "pesoPrevisto": 5.0,
    }

    def test_stable_for_same_input(self):
        self.assertEqual(thesis_fingerprint(self.BASE), thesis_fingerprint(dict(self.BASE)))

    def test_orizzonte_invalidates(self):
        other = dict(self.BASE, orizzonte="1–3 anni")
        self.assertNotEqual(thesis_fingerprint(self.BASE), thesis_fingerprint(other))

    def test_peso_previsto_invalidates(self):
        other = dict(self.BASE, pesoPrevisto=10.0)
        self.assertNotEqual(thesis_fingerprint(self.BASE), thesis_fingerprint(other))

    def test_missing_and_null_peso_match(self):
        a = {"motivo": "x", "indicatori": ["i"], "orizzonte": "1–3 anni"}
        b = dict(a, pesoPrevisto=None)
        c = dict(a, pesoPrevisto="")
        self.assertEqual(thesis_fingerprint(a), thesis_fingerprint(b))
        self.assertEqual(thesis_fingerprint(a), thesis_fingerprint(c))

    def test_motivo_and_indicatori_still_matter(self):
        other_m = dict(self.BASE, motivo="Altro motivo")
        other_i = dict(self.BASE, indicatori=["Ordini"])
        self.assertNotEqual(thesis_fingerprint(self.BASE), thesis_fingerprint(other_m))
        self.assertNotEqual(thesis_fingerprint(self.BASE), thesis_fingerprint(other_i))


class QuoteNormalisationTests(unittest.TestCase):
    def test_fancy_quotes_and_whitespace(self):
        body = "Ricavi «oltre 6 miliardi» nel secondo trimestre."
        cit = "Ricavi  “oltre 6 miliardi”  nel secondo trimestre."
        self.assertTrue(quote_in_body(cit, body))

    def test_apostrophe_variants(self):
        body = "L’ad Battaini: «risultati solidi»."
        cit = "L'ad Battaini: \"risultati solidi\"."
        self.assertEqual(normalise_quote(cit), normalise_quote(body))
        self.assertTrue(quote_in_body(cit, body))

    def test_missing_quote_fails(self):
        self.assertFalse(quote_in_body("numero inventato 18,4 miliardi", "Ricavi oltre 6 miliardi."))


class NumberDropLogicTests(unittest.TestCase):
    def test_fact_with_bad_quote_is_dropped(self):
        articles = [{
            "content_id": "A1",
            "titolo": "Prysmian ricavi",
            "body": "I ricavi hanno superato i 6 miliardi di euro. La crescita organica è stata del 9,4%.",
        }]
        raw = {
            "pertinente": True,
            "fatti": [
                {
                    "testo": "Ricavi oltre 6 miliardi.",
                    "citazione": "I ricavi hanno superato i 6 miliardi di euro.",
                    "content_id": "A1",
                },
                {
                    "testo": "Ordini a 18,4 miliardi.",
                    "citazione": "frase che non esiste nel body",
                    "content_id": "A1",
                },
            ],
            "metriche": [
                {
                    "nome": "Crescita organica",
                    "valore": "9,4%",
                    "confronto": "+9,4%",
                    "base": "a/a",
                    "nota": "",
                },
                {
                    "nome": "Fake",
                    "valore": "18,4 mld",
                    "confronto": "+12%",
                    "base": "a/a",
                    "nota": "",
                },
            ],
            "guidance": "",
            "cambiato": "Nessun confronto.",
            "impatto": {"effetto": "rafforza", "testo": "In linea con la tesi."},
            "indicatori": [
                {
                    "nome": "Margine EBITDA rettificato",
                    "stato": "a_favore",
                    "testo": "Citato.",
                    "citazione": "non in body",
                    "content_id": "A1",
                },
            ],
        }
        cleaned, failures, drops = verify_quarter(
            raw, articles, ["Margine EBITDA rettificato"]
        )
        self.assertEqual(len(cleaned["fatti"]), 1)
        self.assertEqual(drops["fatti"], 1)
        self.assertEqual(len(cleaned["metriche"]), 1)
        self.assertGreaterEqual(drops["metriche"], 1)
        self.assertEqual(cleaned["indicatori"][0]["stato"], "non_citato")
        self.assertIsNone(cleaned["indicatori"][0]["citazione"])
        self.assertTrue(any("citazione" in f for f in failures))


class ReactionWindowTests(unittest.TestCase):
    def setUp(self):
        # Mon–Fri style fake series around 30 Jul 2026
        self.days = [
            "2026-07-28", "2026-07-29", "2026-07-30", "2026-07-31", "2026-08-03",
        ]
        self.closes = [100.0, 102.0, 105.0, 106.0, 104.0]

    def test_before_1730_uses_prev_to_pub_day(self):
        r = reaction_window("2026-07-30T08:12:00", self.days, self.closes)
        self.assertIsNotNone(r)
        # 29 → 30: 105/102 - 1
        self.assertAlmostEqual(r["pct"], round((105 / 102 - 1) * 100, 1))
        self.assertIn("29 lug 2026", r["da"])
        self.assertIn("30 lug 2026", r["a"])
        self.assertIn("08:12", r["nota"])

    def test_after_1730_uses_pub_to_next(self):
        r = reaction_window("2026-07-30T18:00:00", self.days, self.closes)
        self.assertIsNotNone(r)
        # 30 → 31: 106/105 - 1
        self.assertAlmostEqual(r["pct"], round((106 / 105 - 1) * 100, 1))
        self.assertIn("30 lug 2026", r["da"])
        self.assertIn("31 lug 2026", r["a"])
        self.assertIn("mercati chiusi", r["nota"])


class QuarterAssignmentTests(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(assign_quarter("2025-10-30"), "3T25")
        self.assertEqual(assign_quarter("2026-02-26"), "4T25")
        self.assertEqual(assign_quarter("2026-04-30"), "1T26")
        self.assertEqual(assign_quarter("2026-07-30"), "2T26")
        self.assertIsNone(assign_quarter("2026-06-01"))
        self.assertIsNone(assign_quarter("2025-09-01"))

    def test_preview_detection(self):
        self.assertTrue(is_preview_title("Enel, le stime in vista dei conti del primo trimestre"))
        self.assertFalse(is_preview_title("Enel, utile netto a 2 miliardi nel primo trimestre"))


class InsufficienteForceTests(unittest.TestCase):
    def test_fewer_than_two(self):
        self.assertTrue(force_insufficiente([{"id": "2T26"}], "2T26"))
        self.assertTrue(force_insufficiente([], None))

    def test_latest_older_than_1t26(self):
        qs = [{"id": "3T25"}, {"id": "4T25"}]
        self.assertTrue(force_insufficiente(qs, "4T25"))

    def test_ok_with_1t26_or_later(self):
        qs = [{"id": "4T25"}, {"id": "1T26"}]
        self.assertFalse(force_insufficiente(qs, "1T26"))
        qs2 = [{"id": "1T26"}, {"id": "2T26"}]
        self.assertFalse(force_insufficiente(qs2, "2T26"))


STORIES = [
    {"content_id": "N1", "titolo": "Leonardo, ordine da 1 miliardo", "pub_local": "2026-09-09T10:00:00", "status": "DELAYED"},
    {"content_id": "N2", "titolo": "Leonardo, nuova commessa", "pub_local": "2026-09-01T09:00:00", "status": "NO_REACTION"},
    {"content_id": "N3", "titolo": "Delfin, lettera ai revisori", "pub_local": "2026-09-03T21:00:00", "status": "ALREADY_IN_PRICE"},
    {"content_id": "OLD", "titolo": "Prima della finestra", "pub_local": "2026-07-01T09:00:00", "status": "REACTED"},
]
TAGS = {"N1": "Ordini", "N2": "Ordini", "N3": "Indicatore sconosciuto"}
INDS = ["Ordini", "Free cash flow"]


class NewsRollupTests(unittest.TestCase):
    def test_groups_by_indicator_and_verdict(self):
        r = news_rollup(STORIES, TAGS, INDS, since="2026-08-01")
        self.assertEqual(r["n"], 3)
        ordini, fcf = r["per_indicatore"]
        self.assertEqual((ordini["n"], ordini["reazione"], ordini["nessuna"]), (2, 1, 1))
        self.assertEqual([t["content_id"] for t in ordini["titoli"]], ["N1", "N2"])
        self.assertEqual(fcf["n"], 0)
        # Tag outside the thesis indicators counts as not touching the thesis
        self.assertEqual(r["fuori_tesi"], {"n": 1, "reazione": 0, "gia_nel_prezzo": 1, "nessuna": 0})

    def test_empty(self):
        r = news_rollup([], {}, INDS)
        self.assertEqual(r["n"], 0)
        self.assertEqual([i["n"] for i in r["per_indicatore"]], [0, 0])


class DecisionPromptTests(unittest.TestCase):
    TESI = {"motivo": "Spesa per la difesa", "indicatori": INDS, "orizzonte": "3–5 anni"}
    ESITO = {"stato": "rafforzata", "sintesi": "Ordini in forte crescita.", "evoluzione": "Accelerazione."}
    IND = [{"nome": "Ordini", "stato": "a_favore", "testo": "Ordini a 16,2 miliardi."}]

    def setUp(self):
        self.rollup = news_rollup(STORIES, TAGS, INDS, since="2026-08-01")

    def test_decision_prompt_has_both_analyses(self):
        p = decision_prompt("LDO", self.TESI, "portafoglio", 14.0, self.ESITO, self.IND,
                            self.rollup, ["mantenere", "ridurre"])
        self.assertIn("ANALISI DELLA TESI SUI RISULTATI", p)
        self.assertIn("rafforzata", p)
        self.assertIn("Ordini a 16,2 miliardi.", p)
        self.assertIn("ANALISI DELLE NOTIZIE", p)
        self.assertIn("Leonardo, ordine da 1 miliardo", p)
        self.assertIn("Non toccano la tesi: 1 articoli", p)

    def test_aggregate_prompt_no_longer_asks_for_decision(self):
        p = aggregate_prompt("LDO", self.TESI, [])
        self.assertNotIn("decisione", p)

    def test_news_numbers_pass_the_number_check(self):
        src = decision_sources("", 14.0, [self.ESITO["sintesi"]], self.rollup)
        raw = {
            "azione": "mantenere",
            "motivazione": "Gli ordini crescono. Delle 3 notizie recenti, 2 riguardano gli ordini, tra cui un ordine da 1 miliardo.",
            "aFavore": ["Peso del 14% coerente con la tesi."],
            "rischio": "Tensioni sulla governance.",
            "cambierebbe": "Un calo degli ordini.",
        }
        dec, fail = verify_decision(raw, src, "portafoglio", ["mantenere", "ridurre"], self.rollup)
        self.assertEqual(fail, [])
        self.assertEqual(dec["basata_su"], ["risultati", "notizie"])
        self.assertEqual(dec["notizie_considerate"], 3)

    def test_invented_number_fails(self):
        src = decision_sources("", None, [], self.rollup)
        raw = {"azione": "vendere", "motivazione": "Ricavi a 99 miliardi.", "aFavore": [], "rischio": "", "cambierebbe": ""}
        dec, fail = verify_decision(raw, src, "portafoglio", ["mantenere", "ridurre"], self.rollup)
        self.assertEqual(dec["azione"], "mantenere")
        self.assertTrue(any("numbers" in f for f in fail))
        self.assertTrue(any("azione" in f for f in fail))


if __name__ == "__main__":
    unittest.main()
