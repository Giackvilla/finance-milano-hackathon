#!/usr/bin/env python3
"""Catalog thesis check: a name outside the demo book still gets a reading."""
import unittest

import catalog_company as cat


class CatalogThesisTest(unittest.TestCase):
    def test_bending_spoons_price_and_stories(self):
        out = cat.read_company("1BSP", {"motivo": "acquisizione di Airtable", "indicatori": [], "orizzonte": "3–5 anni"}, "portafoglio")
        self.assertIsNotNone(out)
        self.assertEqual(out["prezzo"], 31.5)
        self.assertEqual(out["prezzo_fonte"], "dataset")
        self.assertEqual(len(out["notizie"]), 3)
        self.assertEqual(out["serie"][-1], 31.5)
        self.assertIsNone(out["serie"][0])
        self.assertNotEqual(out["esito"]["stato"], "insufficiente")
        self.assertIn("Airtable", out["esito"]["sintesi"])
        self.assertEqual(out["decisione"]["contesto"], "portafoglio")
        self.assertEqual(out["decisione"]["azione"], "mantenere")
        self.assertTrue(out["esito"]["metodo"])

    def test_unrelated_thesis_is_insufficient_not_empty(self):
        out = cat.read_company("1BSP", {"motivo": "gay", "indicatori": [], "orizzonte": "3–5 anni"})
        self.assertEqual(out["esito"]["stato"], "insufficiente")
        self.assertIsNone(out["decisione"])
        self.assertIn("parole della tesi", out["esito"]["sintesi"])
        self.assertTrue(any("Miro" in f["testo"] or "Airtable" in f["testo"] for f in out["esito"]["fatti"]))
        self.assertTrue(out["mancano"])

    def test_indicator_links_the_story(self):
        out = cat.read_company("1BSP", {
            "motivo": "Crescita tramite acquisizioni",
            "indicatori": ["Miro"],
            "orizzonte": "3–5 anni",
        })
        ind = out["esito"]["indicatori"][0]
        self.assertEqual(ind["nome"], "Miro")
        self.assertNotEqual(ind["stato"], "non_citato")
        linked = [n for n in out["notizie"] if n.get("indicatore")]
        self.assertTrue(linked)
        self.assertEqual(linked[0]["indicatore"]["nome"], "Miro")

    def test_unknown_ticker(self):
        self.assertIsNone(cat.read_company("NOPE"))


if __name__ == "__main__":
    unittest.main()
