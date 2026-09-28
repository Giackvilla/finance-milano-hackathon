#!/usr/bin/env python3
"""Build data/card.json for one article.

Usage:
    python3 scripts/build_card.py <content_id> [--lang it|en] [--out data/card.json]

Prices and dates come only from BigQuery (bq CLI, sql/events.sql).
Gemini sees only titolo and body, plus the tape figures already formatted as text.
Standard library only (Python 3.9).
"""
import argparse
import csv
import io
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT = "class-hackaton-09"
MODEL = "gemini-2.5-flash"
ROOT = Path(__file__).resolve().parent.parent
TIMING_TEXT = {
    "en": {"day_before": "the session before the article", "same_day": "the day of the article", "later": "after the article"},
    "it": {"day_before": "la seduta prima dell'articolo", "same_day": "il giorno dell'articolo", "later": "dopo l'articolo"},
}


def bq(sql, params):
    cmd = ["bq", f"--project_id={PROJECT}", "query", "--use_legacy_sql=false", "--format=csv", "--max_rows=1000"]
    cmd += [f"--parameter={k}:{t}:{v}" for k, (t, v) in params.items()]
    out = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=True).stdout
    start = out.find("\n", 0) if out.startswith("Waiting") else -1
    return list(csv.DictReader(io.StringIO(out[start + 1:])))


def fetch_article(content_id):
    rows = bq(
        "SELECT content_id, titolo, body, data_pubblicazione, testata, URL "
        "FROM `class-hackaton-09.news.articles` WHERE content_id = @id",
        {"id": ("STRING", content_id)},
    )
    if not rows:
        sys.exit(f"No article with content_id {content_id}")
    return rows[0]


def fetch_tape(article):
    day = article["data_pubblicazione"][:10]
    sql = (ROOT / "sql" / "events.sql").read_text()
    rows = [r for r in bq(sql, {"from_date": ("DATE", day), "to_date": ("DATE", day)})
            if r["content_id"] == article["content_id"]]
    if not rows:
        sys.exit("This article's title does not name exactly one company with 20 baseline sessions.")
    return rows[0]


def tape_facts(t, lang):
    move = float(t["move"]) * 100
    z = abs(float(t["z"]))
    retained = float(t["retained"]) * 100
    when = TIMING_TEXT[lang][t["timing"]]
    if lang == "it":
        return [
            f"Il movimento più anomalo è avvenuto {when} ({t['move_date']}): {move:+.1f}%.",
            f"È pari a {z:.1f} volte la deviazione standard delle 20 sedute precedenti l'articolo"
            + (" (anomalo: almeno 2 volte)." if z >= 2 else " (non anomalo: sotto 2 volte)."),
            f"All'ultima seduta, il {t['last_d']}, resta nel prezzo il {retained:.0f}% di quel movimento.",
        ]
    return [
        f"The most unusual move came {when} ({t['move_date']}): {move:+.1f}%.",
        f"That is {z:.1f} times the standard deviation of the 20 sessions before the article"
        + (" (unusual: at least 2 times)." if z >= 2 else " (not unusual: below 2 times)."),
        f"By the last session, {t['last_d']}, {retained:.0f}% of that move is still in the price.",
    ]


PROMPT = """You are checking one financial news article against facts about the stock price.

ARTICLE (source: {testata}, published {pub})
TITLE: {titolo}
BODY:
{body}

PRICE FACTS (computed from exchange data, treat them as given; do not compute or add any other number):
{facts}

Return JSON with:
- instrument_name: the listed company the title is about.
- title_adjective: the word or short phrase in the title that characterises the event or the stock move (for example "tracolla", "vola", "crolla", "in calo"). Copy it exactly from the title.
- figure_in_body: the key figure in the body that the title adjective refers to, copied exactly as written in the body.
- adjective_matches: true if the title adjective is a fair description of that body figure, false otherwise.
- quote: one sentence copied verbatim from the body that contains or best supports figure_in_body.
- sentence: ONE sentence in {language} that says whether the title adjective matches the figure in the body, and whether the story fits a move of the size and timing given in the price facts. Cite the article as "{testata}, {pub_day}". Only use numbers that appear in the price facts or in the article. Never say buy, sell, or give any recommendation.
"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {k: {"type": "BOOLEAN" if k == "adjective_matches" else "STRING"}
                   for k in ["instrument_name", "title_adjective", "figure_in_body", "adjective_matches", "quote", "sentence"]},
    "required": ["instrument_name", "title_adjective", "figure_in_body", "adjective_matches", "quote", "sentence"],
}


def gemini(prompt):
    token = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()
    url = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/global/publishers/google/models/{MODEL}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseSchema": SCHEMA},
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = json.load(r)
    return json.loads(body["candidates"][0]["content"]["parts"][0]["text"])


def checks(g, article, facts):
    norm = lambda s: re.sub(r"\s+", " ", s).strip()
    body = norm(article["body"])
    allowed = set(re.findall(r"\d+(?:[.,]\d+)?", article["titolo"] + " " + body + " " + " ".join(facts)))
    used = set(re.findall(r"\d+(?:[.,]\d+)?", g["sentence"]))
    return {
        "quote_is_verbatim": norm(g["quote"]) in body,
        "figure_is_in_body": norm(g["figure_in_body"]) in body,
        "adjective_is_in_title": g["title_adjective"].lower() in article["titolo"].lower(),
        "numbers_not_in_sources": sorted(used - allowed),
        "no_recommendation": not re.search(r"\b(buy|sell|compra\w*|vend\w*|acquist\w*)\b", g["sentence"], re.I),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content_id")
    ap.add_argument("--lang", choices=["it", "en"], default="en")
    ap.add_argument("--out", default=str(ROOT / "data" / "card.json"))
    args = ap.parse_args()

    article = fetch_article(args.content_id)
    t = fetch_tape(article)
    facts = tape_facts(t, args.lang)
    pub = article["data_pubblicazione"][:16].replace("T", " ")
    g = gemini(PROMPT.format(
        testata=article["testata"], pub=pub, pub_day=pub[:10], titolo=article["titolo"], body=article["body"],
        facts="\n".join(f"- {f}" for f in facts), language="Italian" if args.lang == "it" else "English",
    ))

    card = {
        "article": {"content_id": article["content_id"], "titolo": article["titolo"],
                    "data_pubblicazione": article["data_pubblicazione"], "testata": article["testata"],
                    "quote": g["quote"], "url": article["URL"]},
        "instrument": {"des_azione": t["DES_AZIONE"], "cod_azione": t["COD_AZIONE"], "isin": t["COD_ISIN"]},
        "tape": {
            "timing": t["timing"], "move_date": t["move_date"],
            "move_pct": round(float(t["move"]) * 100, 2), "z": round(float(t["z"]), 2),
            "unusual": t["unusual"] == "true", "volume_x": round(float(t["vol_x"] or 0), 1),
            "baseline_sessions": int(t["n_base"]), "baseline_sd_pct": round(float(t["baseline_sd"]) * 100, 3),
            "px_before_move": float(t["px_before_move"]), "px_after_move": float(t["px_after_move"]),
            "last_session": t["last_d"], "last_px": float(t["last_px"]),
            "retained_pct": round(float(t["retained"]) * 100),
            "facts_text": facts,
        },
        "gemini": {"model": MODEL, "instrument_name": g["instrument_name"], "title_adjective": g["title_adjective"],
                   "figure_in_body": g["figure_in_body"], "adjective_matches": g["adjective_matches"],
                   "sentence": g["sentence"], "checks": checks(g, article, facts)},
    }
    Path(args.out).write_text(json.dumps(card, ensure_ascii=False, indent=2))
    print(json.dumps(card, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
