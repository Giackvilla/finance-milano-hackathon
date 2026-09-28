#!/usr/bin/env python3
"""Unit tests for scripts.verdict — synthetic rows, no BigQuery."""
import unittest

from verdict import OPEN_MAJORITY, Z_CUT, verdict


def row(**kw):
    base = {
        "content_id": "t1",
        "titolo": "Test Co",
        "data_pubblicazione": "2026-08-07 09:02:40",
        "pub_local": "2026-08-07T11:02:40",
        "pub_date": "2026-08-07",
        "publication_phase": "in_session",
        "COD_AZIONE": "TST",
        "DES_AZIONE": "Test",
        "d": "2026-08-07",
        "timing": "same_day",
        "later_rank": "",
        "closed_before_publication": "false",
        "is_reaction_session": "false",
        "prev_rif": "10",
        "open_px": "",
        "last_px": "11",
        "move": "0.05",
        "z": "1.0",
        "unusual": "false",
        "gap": "",
        "intraday": "",
        "open_share": "",
        "vol_x": "1.0",
        "baseline_sd": "0.05",
        "n_base": "20",
        "final_d": "2026-09-23",
        "final_px": "10.5",
        "retained": "0.5",
    }
    base.update(kw)
    return base


class VerdictTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(Z_CUT, 2)
        self.assertEqual(OPEN_MAJORITY, 0.5)

    def test_no_reaction(self):
        rows = [
            row(d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="1.5", move="0.03", unusual="false"),
            row(d="2026-08-07", timing="same_day", is_reaction_session="true",
                z="0.8", move="0.02", unusual="false"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "NO_REACTION")
        self.assertIsNone(v["peak"])
        self.assertEqual(v["unusual_sessions"], [])
        self.assertIsNotNone(v["largest"])
        self.assertEqual(v["largest"]["d"], "2026-08-06")
        self.assertEqual(v["largest"]["timing_words_en"], "the session before the article")
        self.assertIn("twice the normal daily swing", v["text_en"])
        self.assertNotIn("|z|", v["text_en"])
        self.assertNotIn("same_day", v["text_en"])

    def test_already_in_price_day_before(self):
        rows = [
            row(d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="-3.5", move="-0.10", unusual="true", retained="0.8", vol_x="2.1"),
            row(d="2026-08-07", timing="same_day", is_reaction_session="true",
                z="0.5", move="0.01", unusual="false"),
        ]
        v = verdict(rows, {"news_type": "earnings", "scheduled": True, "headline_reports_move": False})
        self.assertEqual(v["status"], "ALREADY_IN_PRICE")
        self.assertEqual(v["peak"]["d"], "2026-08-06")
        self.assertEqual(v["peak"]["timing"], "day_before")
        self.assertEqual(v["peak"]["timing_words_en"], "the session before the article")
        self.assertIn("scheduled event", v["text_en"])
        self.assertIn("6 Aug 2026", v["text_en"])
        self.assertIn("6 agosto 2026", v["text_it"])

    def test_already_in_price_after_close_same_day(self):
        rows = [
            row(publication_phase="after_close", pub_local="2026-08-07T18:00:00",
                d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="0.4", move="0.01", unusual="false"),
            row(publication_phase="after_close", pub_local="2026-08-07T18:00:00",
                d="2026-08-07", timing="same_day", closed_before_publication="true",
                is_reaction_session="false",
                z="4.2", move="0.12", unusual="true", retained="0.9"),
            row(publication_phase="after_close", pub_local="2026-08-07T18:00:00",
                d="2026-08-10", timing="later", later_rank="1",
                closed_before_publication="false", is_reaction_session="true",
                z="0.3", move="0.01", unusual="false"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "ALREADY_IN_PRICE")
        self.assertEqual(v["peak"]["d"], "2026-08-07")
        self.assertEqual(v["publication_phase"], "after_close")
        self.assertIsNone(v["at_open"])

    def test_partly_in_price(self):
        rows = [
            row(d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="2.5", move="0.08", unusual="true"),
            row(d="2026-08-07", timing="same_day", is_reaction_session="true",
                closed_before_publication="false",
                z="5.0", move="0.15", unusual="true", retained="0.7"),
        ]
        v = verdict(rows, {"news_type": "mna", "scheduled": False, "headline_reports_move": True})
        self.assertEqual(v["status"], "PARTLY_IN_PRICE")
        self.assertEqual(v["peak"]["d"], "2026-08-07")
        self.assertIn("Part of the unusual movement", v["text_en"])
        self.assertIn("The headline reports the price move itself.", v["text_en"])
        self.assertIn("Il titolo dell'articolo racconta", v["text_it"])
        self.assertNotIn("titolo descrive", v["text_it"])

    def test_mostly_at_open_seri_like(self):
        rows = [
            row(d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="1.0", move="0.02", unusual="false"),
            row(d="2026-08-07", timing="same_day", is_reaction_session="true",
                closed_before_publication="false",
                open_px="2.45", gap="-0.1681", open_share="0.86",
                z="-8.79", move="-0.1919", unusual="true", retained="1.08"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "MOSTLY_AT_OPEN")
        self.assertIn("published at 11:02", v["text_en"])
        self.assertIn("pubblicato alle 11:02", v["text_it"])
        self.assertIn("more than half", v["text_en"])
        self.assertIn("l'azione", v["text_it"])

    def test_reacted_low_open_share(self):
        rows = [
            row(d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="0.3", move="0.01", unusual="false"),
            row(d="2026-08-07", timing="same_day", is_reaction_session="true",
                closed_before_publication="false",
                open_px="10.5", gap="0.05", open_share="0.2",
                z="3.0", move="0.12", unusual="true", retained="0.5"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "REACTED")
        self.assertIsNotNone(v["at_open"])
        self.assertEqual(v["at_open"]["open_share_pct"], 20.0)

    def test_reacted_missing_open(self):
        rows = [
            row(publication_phase="in_session",
                d="2026-08-07", timing="same_day", is_reaction_session="true",
                open_px="", gap="", open_share="",
                z="3.0", move="0.12", unusual="true", retained="0.5"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "REACTED")
        self.assertIsNone(v["at_open"])

    def test_reacted(self):
        rows = [
            row(d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="1.0", move="0.02", unusual="false"),
            row(d="2026-08-07", timing="same_day", is_reaction_session="true",
                closed_before_publication="false",
                z="-4.0", move="-0.12", unusual="true", retained="1.1", vol_x="3"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "REACTED")
        self.assertEqual(v["peak"]["timing"], "same_day")
        self.assertIn("moved further in the same direction", v["text_en"])

    def test_delayed(self):
        rows = [
            row(d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="0.2", move="0.01", unusual="false"),
            row(d="2026-08-07", timing="same_day", is_reaction_session="true",
                closed_before_publication="false",
                z="1.1", move="0.03", unusual="false"),
            row(d="2026-08-11", timing="later", later_rank="2",
                closed_before_publication="false", is_reaction_session="false",
                z="3.8", move="0.11", unusual="true", retained="0.4"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "DELAYED")
        self.assertEqual(v["peak"]["d"], "2026-08-11")
        self.assertEqual(v["peak"]["timing_words_en"], "2 sessions after the article")
        self.assertEqual(v["peak"]["timing_words_it"], "2 sedute dopo l'articolo")

    def test_non_trading_day(self):
        rows = [
            row(publication_phase="non_trading_day", pub_local="2026-09-05T13:35:09",
                pub_date="2026-09-05",
                d="2026-09-04", timing="day_before", closed_before_publication="true",
                z="0.5", move="0.01", unusual="false"),
            row(publication_phase="non_trading_day", pub_local="2026-09-05T13:35:09",
                pub_date="2026-09-05",
                d="2026-09-07", timing="later", later_rank="1",
                closed_before_publication="false", is_reaction_session="true",
                z="3.1", move="0.09", unusual="true", retained="0.6"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "REACTED")
        self.assertEqual(v["publication_phase"], "non_trading_day")
        self.assertEqual(v["peak"]["timing_words_en"], "1 session after the article")
        self.assertIsNone(v["at_open"])

    def test_in_session_at_open(self):
        rows = [
            row(d="2026-08-06", timing="day_before", closed_before_publication="true",
                z="0.3", move="0.01", unusual="false"),
            row(d="2026-08-07", timing="same_day", is_reaction_session="true",
                closed_before_publication="false",
                open_px="10.5", gap="0.05", open_share="0.4",
                z="3.0", move="0.12", unusual="true", retained="0.5"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "REACTED")
        self.assertIsNotNone(v["at_open"])
        self.assertEqual(v["at_open"]["open_share_pct"], 40.0)
        self.assertEqual(v["at_open"]["gap_pct"], 5.0)

    def test_pre_open_no_at_open_even_with_open(self):
        rows = [
            row(publication_phase="pre_open", pub_local="2026-08-07T08:00:00",
                d="2026-08-07", timing="same_day", is_reaction_session="true",
                open_px="10.2", gap="0.02", open_share="0.3",
                z="2.5", move="0.07", unusual="true"),
        ]
        v = verdict(rows, None)
        self.assertEqual(v["status"], "REACTED")
        self.assertIsNone(v["at_open"])


if __name__ == "__main__":
    unittest.main()
