#!/usr/bin/env python3
"""Offline unit tests for conservative title-to-instrument matching."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from company_matching import instrument_matches, matching_instruments  # noqa: E402


INSTRUMENTS = [
    {"COD_AZIONE": "FINME", "DES_AZIONE": "Leonardo", "COD_ISIN": "IT0003856405"},
    {"COD_AZIONE": "OLI", "DES_AZIONE": "Telecom Italia", "COD_ISIN": "IT0003497168"},
    {"COD_AZIONE": "AMBR", "DES_AZIONE": "Intesa Sanpaolo", "COD_ISIN": "IT0000072618"},
    {"COD_AZIONE": "SPM", "DES_AZIONE": "Saipem", "COD_ISIN": "IT0005252140"},
    {"COD_AZIONE": "PRY", "DES_AZIONE": "Prysmian", "COD_ISIN": "IT0004176001"},
    {"COD_AZIONE": "ARIS", "DES_AZIONE": "Ariston", "COD_ISIN": "IT0004240443"},
    {"COD_AZIONE": "UCG", "DES_AZIONE": "Unicredit", "COD_ISIN": "IT0005239360"},
]


def _codes(title: str) -> list[str]:
    return [row["COD_AZIONE"] for row in matching_instruments(title, INSTRUMENTS)]


class CompanyMatchingTests(unittest.TestCase):
    def test_keep_leonardo(self):
        titles = [
            "Difesa, titoli in rally: Giappone verso il 3,5% del pil e nuovo contratto per Leonardo, tra le top pick di Citi",
            "Leonardo, maxi-ordine per Atr da un miliardo di dollari dall’India. Ma in borsa il titolo scende",
            "Leonardo firma il primo contratto con l’esercito brasiliano per sette blindati Centauro II",
            "Leonardo: gli analisti promuovono il titolo e arriva una nuova commessa in Arabia Saudita",
            "Finmeccanica torna sul mercato con il nome Leonardo",
            "Nuova commessa di Leonardo in Arabia Saudita",
        ]
        for title in titles:
            with self.subTest(title=title[:80]):
                self.assertEqual(_codes(title), ["FINME"], msg=title)

    def test_drop_leonardo_homonyms(self):
        titles = [
            "Essilux, Leonardo Maria Del Vecchio sbarca su X e attacca Milleri sui compensi",
            "Delfin, arbitrato di 18 mesi sulla penale da 500 milioni di Leonardo Maria Del Vecchio. Debito verso la rinegoziazione",
            "Dagli occhiali ai giornali, dai ristoranti all'acqua minerale: la parabola disordinata di Leonardo jr.",
            "EssilorLuxottica, nessuno scossone. Milleri amareggiato per Leonardo jr ma governance resta solida",
            "Leonardo Maria Del Vecchio lascia EssilorLuxottica: gestione distante e impersonale. La lettera di dimissioni",
            "Leonardo Capital entra in Weltix per accelerare nella tokenizzazione",
            "Intelligenza artificiale, arriva Vitruvian-1: il modello di AI italiano ispirato a Leonardo da Vinci. Ecco cosa può fare",
            "Morto Leonardo Del Vecchio, il patron di Essilor-Luxottica aveva 87 anni",
            "Eredità Del Vecchio, Leonardo Maria pronto a chiedere la prelazione sulle quote in Delfin",
            "Gli eredi Del Vecchio lavorano a una doppia Delfin per distribuirsi parte dell’eredità miliardaria di Leonardo.",
            "Testamento Del Vecchio, spunta l'ottavo socio di Delfin: Rocco Basilico, figlio della moglie di Leonardo",
        ]
        for title in titles:
            with self.subTest(title=title[:80]):
                self.assertEqual(matching_instruments(title, INSTRUMENTS), [], msg=title)

    def test_intesa_keep_and_drop(self):
        self.assertEqual(
            _codes(
                "Antitrust avvia l’istruttoria per valutare l’opas di Intesa Sanpaolo su Monte dei Paschi di Siena"
            ),
            ["AMBR"],
        )
        self.assertEqual(
            _codes("Intesa Sanpaolo vede crescere i ricavi nel trimestre"),
            ["AMBR"],
        )
        self.assertEqual(
            _codes(
                "Ariston, segnali positivi dalla Germania: Intesa Sanpaolo vede un upside del 32% sul titolo"
            ),
            ["ARIS"],
        )
        self.assertEqual(
            _codes("Saipem, gli analisti di Intesa alzano il target price"),
            ["SPM"],
        )
        self.assertEqual(
            _codes("Intesa San Paolo conferma il piano"),
            ["AMBR"],
        )

    def test_tim_keep_drop_and_ambiguous(self):
        self.assertEqual(_codes("Tim, piano industriale e nuovi obiettivi"), ["OLI"])
        self.assertEqual(matching_instruments("Tim Cook presenta il nuovo iPhone", INSTRUMENTS), [])
        self.assertEqual(matching_instruments("Tim Brasil cresce nel mobile", INSTRUMENTS), [])
        self.assertEqual(
            matching_instruments(
                "Il cloud nazionale di Tim, Leonardo & C fa contenti gli azionisti",
                INSTRUMENTS,
            ),
            [],
        )

    def test_generic_energy_never_matches(self):
        energy = [{"COD_AZIONE": "ENRG", "DES_AZIONE": "Energy", "COD_ISIN": "XX0000000001"}]
        self.assertEqual(matching_instruments("Energy, prezzi in rialzo", energy), [])

    def test_two_listed_companies_rejected(self):
        self.assertEqual(
            matching_instruments("Saipem e Prysmian firmano un accordo", INSTRUMENTS),
            [],
        )

    def test_genitive_operating_targets_and_agreement_noun(self):
        self.assertEqual(
            _codes("Deutsche Bank taglia il rating di Unicredit"),
            ["UCG"],
        )
        self.assertEqual(
            _codes(
                "A ruba il bond perpetuo di Prysmian, richieste per quasi 6 miliardi. "
                "Ecco quanto rende e il punto degli analisti"
            ),
            ["PRY"],
        )
        self.assertEqual(
            _codes(
                "Prysmian alza i target di riduzione delle emissioni e conferma gli obiettivi a lungo termine"
            ),
            ["PRY"],
        )
        self.assertEqual(
            _codes("Flop di Saipem, a preoccupare gli analisti è la dinamica del debito"),
            ["SPM"],
        )
        self.assertEqual(
            _codes("Prysmian aggiorna il record in borsa: Ubs alza stime e target price"),
            ["PRY"],
        )
        self.assertFalse(
            instrument_matches(
                "Ecco i dettagli sull'intesa tra la banca e il gruppo di Pignataro",
                "Intesa Sanpaolo",
                "AMBR",
            )
        )
        self.assertTrue(
            instrument_matches("Intesa San Paolo conferma il piano", "Intesa Sanpaolo", "AMBR")
        )
        self.assertTrue(
            instrument_matches(
                "Nuovo ordine per Danieli & C. dall’India, vale 110 milioni di euro",
                "Danieli & C",
                "DAN",
            )
        )
        self.assertTrue(
            instrument_matches(
                "Azioni, B&C Speakers in forte denaro dopo il deal Eminence",
                "B&C Speakers",
                "BEC",
            )
        )
        self.assertTrue(
            instrument_matches(
                "Recordati alza il target sulle vendite dei prodotti per le malattie rare",
                "Recordati",
                "REC",
            )
        )
        self.assertTrue(
            instrument_matches("Acea conferma i target 2021", "Acea", "ACE")
        )
        self.assertFalse(
            instrument_matches(
                "Intesa Sanpaolo alza il target price sul titolo",
                "Intesa Sanpaolo",
                "AMBR",
            )
        )

    def test_instrument_matches_leonardo_disambiguation(self):
        self.assertTrue(
            instrument_matches("Leonardo, maxi-ordine", "Leonardo", "FINME")
        )
        self.assertFalse(
            instrument_matches(
                "Leonardo Maria Del Vecchio lascia", "Leonardo", "FINME"
            )
        )


if __name__ == "__main__":
    unittest.main()
