#!/usr/bin/env python3
"""Unit tests for the deterministic MF headline classifier."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import classify, normalise  # noqa: E402


# Real titles from data/events_all.csv, hand-labelled (news_type, headline_reports_move).
REAL_CASES = [
    # takeover
    (
        "Valtecne, opa a premio di G Square: titolo in rally sull’Egm (+32%)",
        "takeover",
        True,
    ),
    (
        "Super opa con delisting su Braga Moro: la pmi dell’energia lascia Piazza Affari dopo 10 mesi con Sattin, Caslini e Banca Finint",
        "takeover",
        False,
    ),
    (
        "Digital Value, scatta l’opa obbligatoria a 29 euro: obiettivo il delisting. Nuovi vertici",
        "takeover",
        False,
    ),
    (
        "Mediobanca, Mps arriva all'86,33% dopo la riapertura dell’opas. Ora la scelta su delisting e fusione",
        "takeover",
        False,
    ),
    (
        "Seri Industrial tracolla in borsa (-20%): l’ex Spac verso il delisting a forte sconto",
        "takeover",
        True,
    ),
    # earnings
    (
        "Promotica, fatturato consolidato preliminare a 57 mln (+54%)",
        "earnings",
        False,
    ),
    (
        "Credem, utile trimestrale a 139,5 milioni: prestiti e raccolta in crescita",
        "earnings",
        False,
    ),
    (
        "Diasorin, boom di ricavi (+34%) nel primo trimestre",
        "earnings",
        False,  # % annotates ricavi, not the tape
    ),
    (
        "Snam, risultati semestrali in crescita e debito light",
        "earnings",
        False,
    ),
    (
        "Saipem perde l’8,9% dopo i conti, analisti divisi sul titolo. Interviene il ceo Puliti",
        "earnings",
        True,
    ),
    (
        "Banche, Intesa Sanpaolo apre la stagione dei conti. Ecco che cosa si aspetta il consenso degli analisti",
        "earnings",
        False,
    ),
    # plan
    (
        "Diasorin approva il piano industriale 2024-2027: crescita almeno del 5% nel 2024. I punti principali del nuovo business plan",
        "plan",
        False,
    ),
    (
        "Sesa lancia il nuovo piano industriale: meno m&a, focus su crescita organica e cedole. Parla l’ad Alessandro Fabbroni",
        "plan",
        False,
    ),
    (
        "Prysmian, i giudizi degli analisti in vista del Capital Markets Day: quanto potrà salire il titolo",
        "plan",
        False,
    ),
    # capital
    (
        "Unicredit chiede il via libera alla Bce per un buyback da 1 miliardo",
        "capital",
        False,
    ),
    (
        "Amplifon, via libera all’aumento di capitale da 45,3 milioni di azioni tramite abb",
        "capital",
        False,
    ),
    (
        "Eni, il dividendo trimestrale di 0,23 euro sarà in pagamento il 22 novembre",
        "capital",
        False,
    ),
    (
        "Leonardo, S&P alza le prospettive sul rating BBB- del gruppo di Roberto Cingolani. Ecco perché",
        "capital",
        False,
    ),
    (
        "Unicredit acquista 10,2 milioni di azioni proprie. Sospetto l'attivismo di Goldman Sachs sul capitale",
        "capital",
        False,
    ),
    # legal_regulatory
    (
        "Ue, multa da 69,4 milioni a Unicredit per cartello sui titoli di Stato",
        "legal_regulatory",
        False,
    ),
    (
        "Golden power, Unicredit pensa al Consiglio di Stato. L’Ue decide sulla procedura d’infrazione contro l’Italia",
        "legal_regulatory",
        False,
    ),
    (
        "Poste Italiane, multa di 4 milioni di euro dall’Antitrust per pratiche scorrette su app",
        "legal_regulatory",
        False,
    ),
    # analyst
    (
        "Fincantieri, Equita promuove il titolo a Buy: l’underwater diventa il secondo motore del gruppo",
        "analyst",
        False,
    ),
    (
        "FinecoBank, Berenberg: crescita a effetto valanga, nuovo target price",
        "analyst",
        False,
    ),
    (
        "Nexi, Barclays taglia il target price e il titolo scivola in borsa: ecco cosa si aspettano gli analisti",
        "analyst",
        True,
    ),
    # deal
    (
        "Webuild, maxi contratto da 1 miliardo di dollari in Pennsylvania per il tunnel che proteggerà i fiumi di Pittsburgh",
        "deal",
        False,
    ),
    (
        "Omer, contratto per gli interni di 40 treni Frecciarossa. Titolo in rally sull’Egm",
        "deal",
        True,
    ),
    (
        "Lottomatica, il fondo Apollo vende ancora: cede il 10,3% e scende al 31,6% della società di scommesse",
        "deal",
        False,
    ),
    (
        "Azimut rileva la minoranza di 16 società di consulenza in Australia che gestiscono asset per 14 miliardi",
        "deal",
        False,
    ),
    # governance
    (
        "Anche Sabrina Pucci si dimette dal cda di Generali",
        "governance",
        False,
    ),
    (
        "Sogefi, Frederic Sipahi è il nuovo amministratore delegato",
        "governance",
        False,
    ),
    (
        "I fondi presentano le liste per Mps e Banco Bpm. Ora occhi puntati su Lovaglio e Crédit Agricole",
        "governance",
        False,
    ),
    (
        "Intesa Sanpaolo sceglie Riccardo Ranalli per la presidenza di Intesa Vita. In arrivo i cda di Fideuram e delle altre controllate",
        "governance",
        False,
    ),
    # market_report
    (
        "Borse oggi in diretta | Il Ftse Mib chiude in calo (-0,6%). Maglia nera Leonardo, bene Stellantis",
        "market_report",
        True,
    ),
    (
        "CASO DI BORSA: brilla Alkemy (+3,47%)",
        "market_report",
        True,
    ),
    (
        "Cos'è successo oggi sui mercati: dal crollo di Eurogroup L. ai tagli di Volkswagen",
        "market_report",
        True,
    ),
    (
        "Unicredit, l'analisi tecnica: timido test in area 74,35-74,50 euro",
        "market_report",
        False,
    ),
    (
        "Recordati: il titolo allunga al rialzo",
        "market_report",
        True,
    ),
    # other
    (
        "Generali non investe e non investirà in bitcoin",
        "other",
        False,
    ),
    (
        "Poste Italiane prova a giocare la carta del Danish Compromise",
        "other",
        False,
    ),
]


class ClassifyTests(unittest.TestCase):
    def test_real_titles_type_and_move(self):
        self.assertGreaterEqual(len(REAL_CASES), 30)
        for title, exp_type, exp_move in REAL_CASES:
            with self.subTest(title=title[:80]):
                out = classify(title)
                self.assertEqual(out["news_type"], exp_type, msg=title)
                self.assertEqual(out["headline_reports_move"], exp_move, msg=title)
                self.assertIn("matched", out)
                self.assertIn("scheduled", out)

    def test_false_positive_traps(self):
        traps = [
            # "utile per" = useful, not earnings
            ("Una guida utile per le imprese di Piazza Affari", "other"),
            # conti correnti = bank accounts product
            ("Unicredit lancia nuovi conti correnti per i giovani", "other"),
            # ops inside English / unrelated — no bare ops: "operations"
            ("Leonardo operations in the US expand capacity", "other"),
            # piano = slowly / floor sense without industriale
            ("Il piano terra del nuovo hub di Poste Italiane a Roma", "other"),
            # cede una quota = deal, not tape move
            (
                "Il fondo cede una quota di Amplifon e resta azionista di minoranza",
                "deal",
            ),
            # fusione nucleare ≠ M&A deal
            (
                "Eni conferma: lavoriamo sulla fusione nucleare, prima centrale nel 2030",
                "other",
            ),
            # broker name without research language
            (
                "Elezioni: Citi, Unicredit e Ubs si aspettano una reazione composta dello spread",
                "other",
            ),
        ]
        for title, exp_type in traps:
            with self.subTest(title=title):
                out = classify(title)
                self.assertEqual(out["news_type"], exp_type, msg=title)
                if "cede una quota" in normalise(title):
                    self.assertFalse(out["headline_reports_move"], msg=title)

    def test_scheduled_flags(self):
        self.assertTrue(classify("Acea, utile netto del semestre in crescita")["scheduled"])
        self.assertTrue(
            classify("Italgas presenta il piano industriale 2025-2028")["scheduled"]
        )
        self.assertFalse(classify("Opa su Eles, Mare Group rilancia")["scheduled"])
        self.assertFalse(
            classify("Equita alza il target price su Prysmian")["scheduled"]
        )
        self.assertIsNone(
            classify("Borse oggi in diretta | Ftse Mib in rialzo")["scheduled"]
        )
        # dividend payment date → scheduled capital
        out = classify(
            "Eni, il dividendo trimestrale di 0,23 euro sarà in pagamento il 22 novembre"
        )
        self.assertEqual(out["news_type"], "capital")
        self.assertTrue(out["scheduled"])

        # assemblea is scheduled governance
        out = classify("Mediobanca convoca l’assemblea dei soci per il 28 ottobre")
        self.assertEqual(out["news_type"], "governance")
        self.assertTrue(out["scheduled"])

    def test_priority_takeover_over_earnings_and_capital(self):
        out = classify(
            "Unipol incorpora UnipolSai e lancia un’opa da 1,13 miliardi. "
            "Alza il dividendo. Utile in crescita"
        )
        self.assertEqual(out["news_type"], "takeover")

    def test_body_fallback(self):
        # title is pure tape; body carries the event
        out = classify(
            "Il titolo vola in borsa",
            body="La società ha pubblicato i conti del semestre con utile in forte crescita.",
        )
        self.assertEqual(out["news_type"], "earnings")

    def test_cli_single_title_shape(self):
        out = classify("Enel piazza un green bond da 1 miliardo")
        self.assertEqual(set(out), {"news_type", "scheduled", "headline_reports_move", "matched"})


if __name__ == "__main__":
    unittest.main()
