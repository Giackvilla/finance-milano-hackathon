#!/usr/bin/env python3
"""Deterministic tape verdict: was the news already in the price?

Usage:
    python3 scripts/verdict.py <content_id> [<content_id> ...]

Runs sql/tape_window.sql via bq. news=None (unknown/unscheduled) for CLI.
No arithmetic beyond abs() and |z|>=2 / open_share comparisons; moves come from SQL.
Never outputs buy/sell advice.
"""
import csv
import io
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT = "class-hackaton-09"
ROOT = Path(__file__).resolve().parent.parent
Z_CUT = 2
OPEN_MAJORITY = 0.5  # more than half of the day's move already at the open

_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MONTHS_IT = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
              "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")


def _bool(v):
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return False
    return str(v).strip().lower() in ("true", "1", "t")


def _float(v):
    if v is None or v == "":
        return None
    return float(v)


def _pct(v, nd=2):
    if v is None:
        return None
    return round(float(v) * 100, nd)


def _parse_dt(s):
    if s is None or s == "":
        return None
    s = str(s).strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    return None


def _fmt_date(d, lang):
    """d: 'YYYY-MM-DD' or datetime → '9 Sep 2026' / '9 settembre 2026'."""
    if d is None or d == "":
        return ""
    if isinstance(d, datetime):
        dt = d
    else:
        dt = _parse_dt(str(d)[:10])
        if dt is None:
            return str(d)
    if lang == "it":
        return f"{dt.day} {_MONTHS_IT[dt.month - 1]} {dt.year}"
    return f"{dt.day} {_MONTHS_EN[dt.month - 1]} {dt.year}"


def _pub_hhmm(pub_local):
    dt = _parse_dt(pub_local)
    if dt is None:
        return None
    return f"{dt.hour:02d}:{dt.minute:02d}"


def _timing_words(timing, later_rank):
    if timing == "day_before":
        return "the session before the article", "la seduta prima dell'articolo"
    if timing == "same_day":
        return "the day of the article", "il giorno dell'articolo"
    n = later_rank if later_rank is not None else 1
    if n == 1:
        return "1 session after the article", "la seduta dopo l'articolo"
    return f"{n} sessions after the article", f"{n} sedute dopo l'articolo"


def _parse_row(r):
    return {
        "content_id": r["content_id"],
        "titolo": r.get("titolo"),
        "data_pubblicazione": r.get("data_pubblicazione"),
        "pub_local": r["pub_local"],
        "pub_date": r["pub_date"],
        "publication_phase": r["publication_phase"],
        "COD_AZIONE": r.get("COD_AZIONE"),
        "DES_AZIONE": r.get("DES_AZIONE"),
        "d": r["d"],
        "timing": r["timing"],
        "later_rank": int(r["later_rank"]) if r.get("later_rank") not in (None, "") else None,
        "closed_before_publication": _bool(r.get("closed_before_publication")),
        "is_reaction_session": _bool(r.get("is_reaction_session")),
        "prev_rif": _float(r.get("prev_rif")),
        "open_px": _float(r.get("open_px")),
        "last_px": _float(r.get("last_px")),
        "move": _float(r.get("move")),
        "z": _float(r.get("z")),
        "unusual": _bool(r.get("unusual")),
        "gap": _float(r.get("gap")),
        "intraday": _float(r.get("intraday")),
        "open_share": _float(r.get("open_share")),
        "vol_x": _float(r.get("vol_x")),
        "baseline_sd": _float(r.get("baseline_sd")),
        "n_base": int(r["n_base"]) if r.get("n_base") not in (None, "") else None,
        "final_d": r.get("final_d"),
        "final_px": _float(r.get("final_px")),
        "retained": _float(r.get("retained")),
    }


def _session_dict(row):
    en, it = _timing_words(row["timing"], row.get("later_rank"))
    return {
        "d": row["d"],
        "timing": row["timing"],
        "timing_words_en": en,
        "timing_words_it": it,
        "move_pct": _pct(row["move"]),
        "z": round(row["z"], 2) if row["z"] is not None else None,
        "vol_x": round(row["vol_x"], 2) if row["vol_x"] is not None else None,
        "retained_pct": _pct(row["retained"]),
        "open_share_pct": _pct(row["open_share"]),
    }


def _unusual_entry(row):
    return {
        "d": row["d"],
        "timing": row["timing"],
        "closed_before_publication": row["closed_before_publication"],
        "move_pct": _pct(row["move"]),
        "z": round(row["z"], 2) if row["z"] is not None else None,
    }


def _times_normal(z):
    return round(abs(z), 1)


def _news_bits(news):
    if not news:
        return {"news_type": None, "scheduled": False, "headline_reports_move": False, "unknown": True}
    return {
        "news_type": news.get("news_type"),
        "scheduled": bool(news.get("scheduled")),
        "headline_reports_move": bool(news.get("headline_reports_move")),
        "unknown": False,
    }


def _retained_sentences(retained_pct, final_d):
    """Plain retained phrasing (en, it). retained_pct is percent (e.g. 108)."""
    if retained_pct is None:
        return None, None
    by_en = f"by {_fmt_date(final_d, 'en')}" if final_d else "by the last session"
    by_it = f"al {_fmt_date(final_d, 'it')}" if final_d else "all'ultima seduta"
    n = f"{retained_pct:.0f}"
    if retained_pct > 100:
        en = (f"{by_en}, the stock has moved further in the same direction since "
              f"({n}% of the move is in the price)")
        it = (f"{by_it}, l'azione ha continuato nella stessa direzione "
              f"(il {n}% del movimento è nel prezzo)")
    elif retained_pct < 0:
        en = f"{by_en}, the move has fully reversed"
        it = f"{by_it}, il movimento si è completamente invertito"
    else:
        en = f"{by_en}, {n}% of that move is still in the price"
        it = f"{by_it}, il {n}% di quel movimento è ancora nel prezzo"
    return en, it


def _x_normal_en(z):
    return f"{_times_normal(z)} times the normal daily swing of the 20 sessions before the article"


def _x_normal_it(z):
    return f"{_times_normal(z)} volte l'oscillazione normale delle 20 sedute precedenti l'articolo"


def _move_s(move_pct):
    if move_pct is None:
        return None
    return f"{move_pct:+.1f}%"


def _text(status, peak, largest, phase, pub_local, news, peak_row, reaction):
    n = _news_bits(news)
    hhmm = _pub_hhmm(pub_local)
    final_d = None
    if peak_row and peak_row.get("final_d"):
        final_d = peak_row["final_d"]
    elif reaction and reaction.get("final_d"):
        final_d = reaction["final_d"]

    ret_en = ret_it = None
    if peak and peak.get("retained_pct") is not None:
        ret_en, ret_it = _retained_sentences(peak["retained_pct"], final_d)

    headline_en = "The headline reports the price move itself."
    headline_it = "Il titolo dell'articolo racconta il movimento dell'azione stesso."

    def maybe_headline(en_parts, it_parts):
        if n["headline_reports_move"]:
            en_parts.append(headline_en)
            it_parts.append(headline_it)
        return " ".join(en_parts), " ".join(it_parts)

    if status == "NO_REACTION":
        lg = largest
        move_s = _move_s(lg["move_pct"]) if lg else "?"
        zx = _times_normal(lg["z"]) if lg and lg.get("z") is not None else "?"
        when_en = lg["timing_words_en"] if lg else ""
        when_it = lg["timing_words_it"] if lg else ""
        en = [
            "No session in the window moved more than twice the normal daily swing of the 20 sessions before the article;",
            f"the largest was {move_s} ({zx} times normal) {when_en}.",
        ]
        it = [
            "Nessuna seduta nella finestra ha mosso più del doppio dell'oscillazione normale delle 20 sedute precedenti l'articolo;",
            f"la più ampia è stata {move_s} ({zx} volte il normale) {when_it}.",
        ]
        return maybe_headline(en, it)

    peak_date = _fmt_date(peak["d"], "en")
    peak_date_it = _fmt_date(peak["d"], "it")
    move_s = _move_s(peak["move_pct"])
    x_en = _x_normal_en(peak["z"])
    x_it = _x_normal_it(peak["z"])
    when_en = peak["timing_words_en"]
    when_it = peak["timing_words_it"]

    if status == "ALREADY_IN_PRICE":
        if n["scheduled"]:
            en = [
                f"The biggest unusual move came before the article on a scheduled event "
                f"(on {peak_date}, {move_s}, {x_en}).",
            ]
            it = [
                f"Il movimento anomalo più ampio è arrivato prima dell'articolo su un evento programmato "
                f"(il {peak_date_it}, {move_s}, {x_it}).",
            ]
        else:
            en = [
                f"The biggest unusual move came before the article was published "
                f"(on {peak_date}, {move_s}, {x_en}).",
            ]
            it = [
                f"Il movimento anomalo più ampio è arrivato prima che l'articolo fosse pubblicato "
                f"(il {peak_date_it}, {move_s}, {x_it}).",
            ]
        if ret_en:
            en.append(ret_en[0].upper() + ret_en[1:] + ".")
            it.append(ret_it[0].upper() + ret_it[1:] + ".")
        return maybe_headline(en, it)

    if status == "PARTLY_IN_PRICE":
        en = [
            f"Part of the unusual movement came before publication; the biggest was {when_en} "
            f"({peak_date}, {move_s}, {x_en}).",
        ]
        it = [
            f"Parte del movimento anomalo è arrivata prima della pubblicazione; il più ampio è stato {when_it} "
            f"({peak_date_it}, {move_s}, {x_it}).",
        ]
        if ret_en:
            en.append(ret_en[0].upper() + ret_en[1:] + ".")
            it.append(ret_it[0].upper() + ret_it[1:] + ".")
        return maybe_headline(en, it)

    if status == "MOSTLY_AT_OPEN":
        gap_s = _move_s(_pct(peak_row["gap"])) if peak_row and peak_row.get("gap") is not None else "?"
        share = peak.get("open_share_pct")
        share_s = f"{share:.0f}%" if share is not None else "?"
        en = [
            f"The article was published at {hhmm} during the session; by the 09:00 open the stock was already {gap_s} — "
            f"more than half ({share_s}) of the day's {move_s}, {x_en}.",
        ]
        it = [
            f"L'articolo è stato pubblicato alle {hhmm} durante la seduta; all'apertura delle 09:00 l'azione era già {gap_s} — "
            f"più della metà ({share_s}) del {move_s} della giornata, {x_it}.",
        ]
        if ret_en:
            en.append(ret_en[0].upper() + ret_en[1:] + ".")
            it.append(ret_it[0].upper() + ret_it[1:] + ".")
        return maybe_headline(en, it)

    if status == "REACTED":
        en = [
            f"The stock moved {when_en} ({peak_date}, {move_s}, {x_en}); nothing unusual closed before publication.",
        ]
        it = [
            f"L'azione si è mossa {when_it} ({peak_date_it}, {move_s}, {x_it}); niente di anomalo aveva chiuso prima della pubblicazione.",
        ]
        if ret_en:
            en.append(ret_en[0].upper() + ret_en[1:] + ".")
            it.append(ret_it[0].upper() + ret_it[1:] + ".")
        return maybe_headline(en, it)

    # DELAYED
    en = [
        f"The stock moved {when_en} ({peak_date}, {move_s}, {x_en}); nothing unusual closed before publication.",
    ]
    it = [
        f"L'azione si è mossa {when_it} ({peak_date_it}, {move_s}, {x_it}); niente di anomalo aveva chiuso prima della pubblicazione.",
    ]
    if ret_en:
        en.append(ret_en[0].upper() + ret_en[1:] + ".")
        it.append(ret_it[0].upper() + ret_it[1:] + ".")
    return maybe_headline(en, it)


def verdict(rows, news):
    """Return status/peak/largest/text for one article's tape_window rows.

    rows: list of dicts (CSV strings ok). news: classify dict or None.
    """
    parsed = [_parse_row(r) for r in rows]
    if not parsed:
        return {
            "status": "NO_REACTION",
            "peak": None,
            "largest": None,
            "unusual_sessions": [],
            "at_open": None,
            "publication_phase": None,
            "pub_local": None,
            "text_en": "No price sessions for this article.",
            "text_it": "Nessuna seduta di prezzo per questo articolo.",
        }

    phase = parsed[0]["publication_phase"]
    pub_local = parsed[0]["pub_local"]

    with_z = [r for r in parsed if r["z"] is not None]
    largest_row = max(with_z, key=lambda r: abs(r["z"])) if with_z else None
    largest = _session_dict(largest_row) if largest_row else None

    unusual = [r for r in parsed if r["unusual"] and r["z"] is not None and abs(r["z"]) >= Z_CUT]
    unusual_sessions = [_unusual_entry(r) for r in sorted(unusual, key=lambda r: r["d"])]

    peak_row = max(unusual, key=lambda r: abs(r["z"])) if unusual else None

    if not peak_row:
        status = "NO_REACTION"
    elif peak_row["closed_before_publication"]:
        status = "ALREADY_IN_PRICE"
    elif any(r["closed_before_publication"] for r in unusual):
        status = "PARTLY_IN_PRICE"
    elif (
        peak_row["is_reaction_session"]
        and phase == "in_session"
        and peak_row["open_share"] is not None
        and peak_row["open_share"] > OPEN_MAJORITY
    ):
        status = "MOSTLY_AT_OPEN"
    elif peak_row["is_reaction_session"]:
        status = "REACTED"
    else:
        status = "DELAYED"

    peak = _session_dict(peak_row) if peak_row else None

    reaction = next((r for r in parsed if r["is_reaction_session"]), None)
    at_open = None
    if (
        phase == "in_session"
        and reaction is not None
        and reaction["open_px"] is not None
    ):
        at_open = {
            "open_share_pct": _pct(reaction["open_share"]),
            "gap_pct": _pct(reaction["gap"]),
        }

    text_en, text_it = _text(status, peak, largest, phase, pub_local, news, peak_row, reaction)
    return {
        "status": status,
        "peak": peak,
        "largest": largest,
        "unusual_sessions": unusual_sessions,
        "at_open": at_open,
        "publication_phase": phase,
        "pub_local": pub_local,
        "text_en": text_en,
        "text_it": text_it,
    }


def bq_tape(content_ids=None, from_date=None, to_date=None, max_rows=500000):
    """Run tape_window.sql. Pass content_ids=list, or from_date+to_date with empty ids."""
    sql = (ROOT / "sql" / "tape_window.sql").read_text()
    if content_ids:
        arr = json.dumps(list(content_ids))
        fd = from_date or "1900-01-01"
        td = to_date or "1900-01-01"
    else:
        if not from_date or not to_date:
            raise ValueError("from_date and to_date required when content_ids is empty")
        arr = "[]"
        fd, td = from_date, to_date
    cmd = [
        "bq", f"--project_id={PROJECT}", "query",
        "--use_legacy_sql=false", "--format=csv", f"--max_rows={max_rows}",
        f"--parameter=content_ids:ARRAY<STRING>:{arr}",
        f"--parameter=from_date:DATE:{fd}",
        f"--parameter=to_date:DATE:{td}",
    ]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=True)
    out = proc.stdout
    if out.startswith("Waiting"):
        out = out.split("\n", 1)[1]
    return list(csv.DictReader(io.StringIO(out)))


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/verdict.py <content_id> [<content_id> ...]", file=sys.stderr)
        sys.exit(2)
    ids = sys.argv[1:]
    rows = bq_tape(content_ids=ids)
    by_id = {}
    for r in rows:
        by_id.setdefault(r["content_id"], []).append(r)
    for cid in ids:
        article_rows = by_id.get(cid, [])
        out = verdict(article_rows, None)
        out["content_id"] = cid
        if article_rows:
            out["DES_AZIONE"] = article_rows[0].get("DES_AZIONE")
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
