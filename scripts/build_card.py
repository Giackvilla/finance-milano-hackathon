#!/usr/bin/env python3
"""Build one MF story card: article + classify + tape verdict + Gemini.

Usage:
    python3 scripts/build_card.py <content_id> [--lang en|it] [--out data/card.json] [--no-gemini]

Prices/dates only from BigQuery (bq CLI via verdict.bq_tape). Gemini sees only
titolo, body, and the verdict facts text. Stdlib, Python 3.9.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from classify import classify  # noqa: E402
from verdict import bq_tape, verdict  # noqa: E402

PROJECT = "class-hackaton-09"
MODEL = "gemini-2.5-flash"

# Recommendation stems; matched tokens only fail the check if absent from the article.
_REC_RE = re.compile(
    r"\b(buy|sell|compra(?:re|to|ta|ti|te)?|vendi(?:amo|ate|ere)?|"
    r"vende(?:re)?|venduto|acquista(?:re|to|ta|ti|te)?|acquisto)\b",
    re.I,
)
# Sign only when not a date separator between digits (2026-08-07).
_NUM_RE = re.compile(r"(?<!\d)[+\-−–]?\d+(?:[.,]\d+)*(?:\s*%)?")
_ISO_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b"
)
_LONG_DATE_RE = re.compile(
    r"\b\d{1,2}\s+"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
    r"agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}\b",
    re.I,
)


def _strip_dates(text: str) -> str:
    text = _ISO_DATE_RE.sub(" ", text or "")
    text = _LONG_DATE_RE.sub(" ", text)
    return text


def normalise_number_token(tok: str) -> Optional[float]:
    """Map '1.234,5' / '1234.5' / '-19,2' / '−19.2' / '19%' to a float (strip %)."""
    if tok is None:
        return None
    s = str(tok).strip().replace("−", "-").replace("–", "-").replace(" ", "")
    s = s.strip("()[]")
    s = s.rstrip("%")
    if not s or s in ("+", "-"):
        return None
    # European thousands + decimal: 1.234,56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def extract_normalised_numbers(text: str) -> Set[float]:
    out: Set[float] = set()
    for m in _NUM_RE.finditer(_strip_dates(text or "")):
        v = normalise_number_token(m.group(0))
        if v is not None:
            out.add(round(v, 6))
    return out


def bq(sql: str, params: Dict[str, Tuple[str, str]], max_rows: int = 10000) -> List[dict]:
    cmd = [
        "bq", f"--project_id={PROJECT}", "query",
        "--use_legacy_sql=false", "--format=csv", f"--max_rows={max_rows}",
    ]
    cmd += [f"--parameter={k}:{t}:{v}" for k, (t, v) in params.items()]
    out = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=True).stdout
    if out.startswith("Waiting"):
        out = out.split("\n", 1)[1]
    return list(csv.DictReader(io.StringIO(out)))


def fetch_article(content_id: str) -> dict:
    rows = bq(
        "SELECT content_id, titolo, body, data_pubblicazione, testata, URL "
        "FROM `class-hackaton-09.news.articles` WHERE content_id = @id",
        {"id": ("STRING", content_id)},
    )
    if not rows:
        sys.exit(f"No article with content_id {content_id}")
    return rows[0]


def fetch_articles(content_ids: List[str]) -> Dict[str, dict]:
    """One BQ call for many article bodies."""
    if not content_ids:
        return {}
    arr = json.dumps(list(content_ids))
    rows = bq(
        "SELECT content_id, titolo, body, data_pubblicazione, testata, URL "
        "FROM `class-hackaton-09.news.articles` "
        "WHERE content_id IN UNNEST(@ids)",
        {"ids": ("ARRAY<STRING>", arr)},
        max_rows=max(10000, len(content_ids) + 10),
    )
    return {r["content_id"]: r for r in rows}


def numbers_not_in_sources(sentence: str, sources: str) -> List[float]:
    used = extract_normalised_numbers(sentence)
    allowed = extract_normalised_numbers(sources)
    # tolerate tiny float noise by matching via round already applied
    missing = sorted(used - allowed)
    return missing


def recommendation_words_not_in_article(sentence: str, article_text: str) -> List[str]:
    """Return recommendation tokens in the sentence that do not appear in the article."""
    art = (article_text or "").lower()
    bad: List[str] = []
    for m in _REC_RE.finditer(sentence or ""):
        tok = m.group(0)
        if tok.lower() not in art:
            bad.append(tok)
    return bad


def gemini_checks(g: dict, article: dict, facts: List[str]) -> dict:
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "")).strip()

    body = norm(article.get("body") or "")
    titolo = article.get("titolo") or ""
    article_text = f"{titolo}\n{article.get('body') or ''}"
    sources = f"{titolo}\n{article.get('body') or ''}\n" + "\n".join(facts)
    bad_nums = numbers_not_in_sources(g.get("sentence") or "", sources)
    bad_rec = recommendation_words_not_in_article(g.get("sentence") or "", article_text)
    adj = g.get("title_adjective") or ""
    return {
        "quote_is_verbatim": norm(g.get("quote") or "") in body if body else False,
        "figure_is_in_body": norm(g.get("figure_in_body") or "") in body if body else False,
        "adjective_is_in_title": adj.lower() in titolo.lower() if adj else False,
        "numbers_not_in_sources": bad_nums,
        "no_recommendation": len(bad_rec) == 0,
        "recommendation_words_flagged": bad_rec,
    }


def checks_ok(c: dict) -> bool:
    return (
        c.get("quote_is_verbatim")
        and c.get("figure_is_in_body")
        and c.get("adjective_is_in_title")
        and not c.get("numbers_not_in_sources")
        and c.get("no_recommendation")
    )


PROMPT = """You are checking one financial news article against facts about the stock price.

ARTICLE (source: {testata}, published {pub})
TITLE: {titolo}
BODY:
{body}

PRICE FACTS (computed from exchange data, treat them as given; do not compute or add any other number):
{facts}

NEWS CONTEXT:
- The headline classifier says news_type={news_type}, scheduled={scheduled}.
- headline_reports_move={headline_reports_move}.{move_note}

Return JSON with:
- instrument_name: the listed company the title is about.
- title_adjective: the word or short phrase in the title that characterises the event or the stock move (for example "tracolla", "vola", "crolla", "in calo"). Copy it exactly from the title.
- figure_in_body: the key figure in the body that the title adjective refers to, copied exactly as written in the body.
- adjective_matches: true if the title adjective is a fair description of that body figure, false otherwise.
- quote: one sentence copied verbatim from the body that contains or best supports figure_in_body.
- sentence: ONE sentence in {language} that says (a) whether the title adjective matches the figure in the body, and (b) whether the story fits the price facts, including the verdict (for example whether the move was already in the price before publication, mostly at the open, delayed, or a clear reaction). Cite the article as "{testata}, {pub_day}". Only use numbers that appear in the price facts or in the article. Never say buy, sell, or give any recommendation. Do not invent prices.
{retry_block}
"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        k: {"type": "BOOLEAN" if k == "adjective_matches" else "STRING"}
        for k in [
            "instrument_name",
            "title_adjective",
            "figure_in_body",
            "adjective_matches",
            "quote",
            "sentence",
        ]
    },
    "required": [
        "instrument_name",
        "title_adjective",
        "figure_in_body",
        "adjective_matches",
        "quote",
        "sentence",
    ],
}


def call_gemini(prompt: str) -> dict:
    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    url = (
        f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/global/"
        f"publishers/google/models/{MODEL}:generateContent"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        body = json.load(r)
    return json.loads(body["candidates"][0]["content"]["parts"][0]["text"])


def _move_note(headline_reports_move: bool) -> str:
    if headline_reports_move:
        return (
            " The headline was likely rewritten after the move and may describe the "
            "stock's own price change rather than a separate corporate event."
        )
    return ""


def run_gemini(
    article: dict,
    facts: List[str],
    news: dict,
    lang: str,
) -> Tuple[dict, dict, List[dict]]:
    """Return (gemini_payload_fields, final_checks, attempts)."""
    pub = (article.get("data_pubblicazione") or "")[:16].replace("T", " ")
    pub_day = pub[:10]
    base_kw = dict(
        testata=article.get("testata") or "MF",
        pub=pub,
        pub_day=pub_day,
        titolo=article.get("titolo") or "",
        body=article.get("body") or "",
        facts="\n".join(f"- {f}" for f in facts),
        language="Italian" if lang == "it" else "English",
        news_type=news.get("news_type"),
        scheduled=news.get("scheduled"),
        headline_reports_move=news.get("headline_reports_move"),
        move_note=_move_note(bool(news.get("headline_reports_move"))),
        retry_block="",
    )
    attempts: List[dict] = []
    g = call_gemini(PROMPT.format(**base_kw))
    c = gemini_checks(g, article, facts)
    attempts.append({"gemini": g, "checks": c})
    if not checks_ok(c):
        fail_bits = []
        if not c["quote_is_verbatim"]:
            fail_bits.append("quote is not verbatim in the body")
        if not c["figure_is_in_body"]:
            fail_bits.append("figure_in_body is not in the body")
        if not c["adjective_is_in_title"]:
            fail_bits.append("title_adjective is not in the title")
        if c["numbers_not_in_sources"]:
            fail_bits.append(
                f"sentence uses numbers not in sources: {c['numbers_not_in_sources']}"
            )
        if not c["no_recommendation"]:
            fail_bits.append(
                f"sentence has recommendation words absent from the article: "
                f"{c['recommendation_words_flagged']}"
            )
        retry_block = (
            "\nPREVIOUS ATTEMPT FAILED THESE CHECKS — fix them:\n- "
            + "\n- ".join(fail_bits)
            + "\nCopy the quote and figure exactly from the body; copy the adjective "
            "exactly from the title; only use numbers that appear in the article or "
            "the price facts; do not use buy/sell/recommendation words unless they "
            "already appear in the article.\n"
        )
        g2 = call_gemini(PROMPT.format(**{**base_kw, "retry_block": retry_block}))
        c2 = gemini_checks(g2, article, facts)
        attempts.append({"gemini": g2, "checks": c2})
        g, c = g2, c2
    return g, c, attempts


def load_context() -> dict:
    ctx: Dict[str, Any] = {}
    stats_path = ROOT / "data" / "stats.json"
    if stats_path.exists():
        try:
            stats = json.loads(stats_path.read_text())
            if "headline_numbers" in stats:
                ctx["headline_numbers"] = stats["headline_numbers"]
        except (OSError, json.JSONDecodeError):
            pass
    br_path = ROOT / "data" / "base_rate.json"
    if br_path.exists():
        try:
            ctx["base_rate"] = json.loads(br_path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return ctx


def _parse_pub_local(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    return None


def _float(v):
    if v is None or v == "":
        return None
    return float(v)


def _bool(v):
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return False
    return str(v).strip().lower() in ("true", "1", "t")


def pick_session_row(rows: List[dict], verd: dict) -> Optional[dict]:
    """Tape row matching verdict.peak (else largest) by session date d."""
    target = verd.get("peak") or verd.get("largest")
    if not target or not target.get("d"):
        return rows[0] if rows else None
    d = target["d"]
    for r in rows:
        if r.get("d") == d:
            return r
    return rows[0] if rows else None


def build_tape_block(rows: List[dict], verd: dict, lang: str) -> dict:
    sess = verd.get("peak") or verd.get("largest")
    row = pick_session_row(rows, verd)
    facts_text = [verd["text_it"] if lang == "it" else verd["text_en"]]
    if not sess and not row:
        return {
            "timing": None,
            "move_date": None,
            "move_pct": None,
            "z": None,
            "unusual": False,
            "volume_x": None,
            "baseline_sessions": None,
            "baseline_sd_pct": None,
            "px_before_move": None,
            "px_after_move": None,
            "last_session": None,
            "last_px": None,
            "retained_pct": None,
            "facts_text": facts_text,
        }
    move_pct = sess["move_pct"] if sess else _float(row.get("move"))
    if move_pct is not None and sess is None:
        move_pct = round(move_pct * 100, 2)
    z = sess["z"] if sess else (_float(row.get("z")))
    if z is not None and sess is None:
        z = round(z, 2)
    vol = sess.get("vol_x") if sess else None
    if vol is None and row:
        vol = _float(row.get("vol_x"))
        if vol is not None:
            vol = round(vol, 2)
    retained = sess.get("retained_pct") if sess else None
    if retained is None and row and row.get("retained") not in (None, ""):
        retained = round(float(row["retained"]) * 100, 2)

    baseline_sd = _float(row.get("baseline_sd")) if row else None
    return {
        "timing": (sess or {}).get("timing") or (row or {}).get("timing"),
        "move_date": (sess or {}).get("d") or (row or {}).get("d"),
        "move_pct": move_pct,
        "z": z,
        "unusual": bool(
            (sess is not None and verd.get("peak") is not None)
            or (_bool(row.get("unusual")) if row else False)
        ),
        "volume_x": vol,
        "baseline_sessions": int(row["n_base"]) if row and row.get("n_base") not in (None, "") else None,
        "baseline_sd_pct": round(baseline_sd * 100, 3) if baseline_sd is not None else None,
        "px_before_move": _float(row.get("prev_rif")) if row else None,
        "px_after_move": _float(row.get("last_px")) if row else None,
        "last_session": (row or {}).get("final_d"),
        "last_px": _float((row or {}).get("final_px")),
        "retained_pct": round(retained) if retained is not None else None,
        "facts_text": facts_text,
    }


def null_gemini() -> dict:
    return {
        "model": None,
        "instrument_name": None,
        "title_adjective": None,
        "figure_in_body": None,
        "adjective_matches": None,
        "sentence": None,
        "checks": None,
        "attempts": None,
    }


def build_card_dict(
    article: dict,
    rows: List[dict],
    lang: str = "en",
    use_gemini: bool = True,
) -> dict:
    """Assemble one card from article + its tape_window rows."""
    titolo = article.get("titolo") or (rows[0].get("titolo") if rows else "") or ""
    body = article.get("body") or ""
    news = classify(titolo, body)
    verd = verdict(rows, news)
    tape = build_tape_block(rows, verd, lang)
    facts = tape["facts_text"]

    first = rows[0] if rows else {}
    instrument = {
        "des_azione": first.get("DES_AZIONE"),
        "cod_azione": first.get("COD_AZIONE"),
        "isin": first.get("COD_ISIN"),
    }

    pub_local = verd.get("pub_local") or first.get("pub_local")
    art_block = {
        "content_id": article.get("content_id") or first.get("content_id"),
        "titolo": titolo,
        "data_pubblicazione": article.get("data_pubblicazione") or first.get("data_pubblicazione"),
        "pub_local": pub_local,
        "testata": article.get("testata"),
        "quote": None,
        "url": article.get("URL") or article.get("url"),
    }

    news_block = {
        "news_type": news["news_type"],
        "scheduled": news["scheduled"],
        "headline_reports_move": news["headline_reports_move"],
        "matched": [{"type": t, "keyword": k} for t, k in news.get("matched") or []],
    }

    if use_gemini:
        g, c, attempts = run_gemini(article, facts, news, lang)
        art_block["quote"] = g.get("quote")
        gemini_block = {
            "model": MODEL,
            "instrument_name": g.get("instrument_name"),
            "title_adjective": g.get("title_adjective"),
            "figure_in_body": g.get("figure_in_body"),
            "adjective_matches": g.get("adjective_matches"),
            "sentence": g.get("sentence"),
            "checks": c,
            "attempts": [
                {"checks": a["checks"], "sentence": a["gemini"].get("sentence")}
                for a in attempts
            ],
        }
    else:
        gemini_block = null_gemini()

    return {
        "article": art_block,
        "instrument": instrument,
        "news": news_block,
        "verdict": verd,
        "tape": tape,
        "gemini": gemini_block,
        "context": load_context(),
    }


def build_one(content_id: str, lang: str = "en", use_gemini: bool = True) -> dict:
    article = fetch_article(content_id)
    rows = bq_tape(content_ids=[content_id])
    if not rows:
        sys.exit(
            f"No tape window for {content_id} "
            "(title must name exactly one Italian listed company with 20 baseline sessions)."
        )
    return build_card_dict(article, rows, lang=lang, use_gemini=use_gemini)


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("content_id")
    ap.add_argument("--lang", choices=["it", "en"], default="en")
    ap.add_argument("--out", default=str(ROOT / "data" / "card.json"))
    ap.add_argument("--no-gemini", action="store_true")
    args = ap.parse_args(argv)

    card = build_one(args.content_id, lang=args.lang, use_gemini=not args.no_gemini)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(card, ensure_ascii=False, indent=2))
    print(json.dumps(card, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
