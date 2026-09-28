#!/usr/bin/env python3
"""Classify a financial article with Gemini and validate its instrument in BigQuery.

The classifier is body-first and returns a card-compatible JSON object. Input can
come from the project news table, a local text/JSON file, or stdin.

Examples:
    python3 scripts/classify_gemini.py --content-id 202609101905313642
    python3 scripts/classify_gemini.py --file article.json
    cat article.txt | python3 scripts/classify_gemini.py --title "Prysmian ..."

Authentication uses ``gcloud auth print-access-token``. Stdlib only, Python 3.9.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


DEFAULT_PROJECT = "class-hackaton-09"
DEFAULT_LOCATION = "global"
DEFAULT_MODEL = "gemini-2.5-flash"

# These names deliberately match scripts/classify.py and data/card.json.
TOPICS = [
    "takeover",
    "earnings",
    "plan",
    "capital",
    "legal_regulatory",
    "analyst",
    "deal",
    "governance",
    "market_report",
    "other",
]

TOPIC_GUIDE = """\
- takeover: OPA/OPS/OPAS, tender offer, control bid, delisting or squeeze-out.
- earnings: results, revenue, profit/loss, margins, guidance or outlook tied to results.
- plan: industrial/strategic plan, business plan, targets or Capital Markets Day.
- capital: share/bond offerings, placements, capital increases, dividends, buybacks or debt ratings.
- legal_regulatory: courts, investigations, fines, regulators, antitrust or government approvals.
- analyst: broker research, recommendation, target price or analyst estimate changes.
- deal: commercial contracts, orders, partnerships, acquisitions, disposals or mergers that are not takeovers.
- governance: board, CEO/chair, appointments, resignations, shareholder meetings or ownership governance.
- market_report: the listed security's price movement, trading, technical analysis or market performance.
- other: none of the controlled topics above."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "company_name": {"type": "STRING"},
        "ticker": {"type": "STRING"},
        "company_evidence": {"type": "STRING"},
        "primary_topic": {"type": "STRING", "enum": TOPICS},
        "topics": {
            "type": "ARRAY",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "OBJECT",
                "properties": {
                    "topic": {"type": "STRING", "enum": TOPICS},
                    "confidence": {"type": "NUMBER"},
                    "evidence": {"type": "STRING"},
                },
                "required": ["topic", "confidence", "evidence"],
            },
        },
        "summary": {"type": "STRING"},
    },
    "required": [
        "company_name",
        "ticker",
        "company_evidence",
        "primary_topic",
        "topics",
        "summary",
    ],
}

PROMPT = """You classify one financial news article from its MAIN BODY.

Select the main listed company only from BIGQUERY INSTRUMENT CANDIDATES. Copy its
company_name and ticker exactly. The company_evidence must be a short verbatim
excerpt from the title or body that names that company.

Choose between one and three distinct controlled topics. Put the primary topic
first and set primary_topic to the same value. Base the decision on the main
body; use the title only as context. Every topic evidence must be a short
verbatim excerpt from the body (not a paraphrase). Confidence is from 0 to 1.

Topic definitions:
{topic_guide}

Offer routing:
- a public/control offer (OPA/OPS/OPAS, tender offer) is takeover;
- a share, bond or other securities offering is capital;
- a commercial offer, order or customer contract is deal.

BIGQUERY INSTRUMENT CANDIDATES:
{candidates}

TITLE:
{title}

MAIN BODY:
{body}

Write the summary in {language}. Do not add facts not present in the article.
{retry_block}
"""


class ClassificationError(RuntimeError):
    """A clear, user-facing classification or validation failure."""


def _project() -> str:
    return os.environ.get("GOOGLE_CLOUD_PROJECT", DEFAULT_PROJECT)


def _location() -> str:
    return os.environ.get("GOOGLE_CLOUD_LOCATION", DEFAULT_LOCATION)


def _model() -> str:
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold()
    return re.sub(r"\s+", " ", text).strip()


def _contains_verbatim(excerpt: str, source: str) -> bool:
    clean_excerpt = re.sub(r"\s+", " ", excerpt or "").strip()
    clean_source = re.sub(r"\s+", " ", source or "").strip()
    return bool(clean_excerpt and clean_excerpt in clean_source)


def bq_query(
    sql: str,
    params: Optional[Dict[str, Tuple[str, str]]] = None,
    max_rows: int = 10000,
    project: Optional[str] = None,
) -> List[dict]:
    """Run a parameterised BigQuery query through the installed bq CLI."""
    cmd = [
        "bq",
        f"--project_id={project or _project()}",
        "query",
        "--use_legacy_sql=false",
        "--format=csv",
        f"--max_rows={max_rows}",
    ]
    for key, (kind, value) in (params or {}).items():
        cmd.append(f"--parameter={key}:{kind}:{value}")
    try:
        proc = subprocess.run(
            cmd, input=sql, capture_output=True, text=True, check=True
        )
    except FileNotFoundError as exc:
        raise ClassificationError("bq CLI is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "BigQuery query failed").strip()
        raise ClassificationError(detail) from exc

    output = proc.stdout
    # bq may prefix progress output before the CSV header.
    lines = output.splitlines()
    header_at = next(
        (i for i, line in enumerate(lines) if line.startswith("content_id,") or line.startswith("COD_AZIONE,")),
        0,
    )
    return list(csv.DictReader(io.StringIO("\n".join(lines[header_at:]))))


def fetch_article(content_id: str, project: Optional[str] = None) -> dict:
    rows = bq_query(
        "SELECT content_id, titolo, body, data_pubblicazione, testata, URL "
        f"FROM `{project or _project()}.news.articles` WHERE content_id = @id",
        {"id": ("STRING", content_id)},
        project=project,
    )
    if not rows:
        raise ClassificationError(
            f"No article with content_id {content_id} in {(project or _project())}.news.articles"
        )
    if len(rows) > 1:
        raise ClassificationError(f"content_id {content_id} returned more than one article")
    return rows[0]


def fetch_instruments(project: Optional[str] = None) -> List[dict]:
    project = project or _project()
    return bq_query(
        "SELECT DISTINCT i.COD_AZIONE, i.DES_AZIONE, i.COD_ISIN "
        f"FROM `{project}.financial_instruments.instruments_info` i "
        "WHERE i.COD_TIPO = 'ORD' AND i.COD_ISIN LIKE 'IT%' "
        "AND LENGTH(TRIM(i.DES_AZIONE)) >= 3 "
        "AND EXISTS (SELECT 1 "
        f"FROM `{project}.financial_instruments.instruments_quotes` q "
        "WHERE q.COD_AZIONE = i.COD_AZIONE) "
        "ORDER BY i.COD_AZIONE",
        max_rows=5000,
        project=project,
    )


def _name_pattern(name: str) -> re.Pattern:
    # Whitespace in official names may vary in the article; punctuation does not.
    escaped = re.escape((name or "").strip()).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def find_instrument_candidates(
    title: str,
    body: str,
    instruments: Sequence[dict],
    limit: int = 30,
) -> List[dict]:
    """Find official instrument names mentioned in title/body, title first."""
    ranked = []
    for instrument in instruments:
        name = (instrument.get("DES_AZIONE") or "").strip()
        if not name:
            continue
        pattern = _name_pattern(name)
        in_title = bool(pattern.search(title or ""))
        body_hits = len(pattern.findall(body or ""))
        if not in_title and not body_hits:
            continue
        ranked.append((1 if in_title else 0, body_hits, len(name), instrument))
    ranked.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]["COD_AZIONE"]))

    seen = set()
    result = []
    for _, _, _, instrument in ranked:
        ticker = instrument.get("COD_AZIONE")
        if ticker in seen:
            continue
        seen.add(ticker)
        result.append(
            {
                "COD_AZIONE": ticker,
                "DES_AZIONE": instrument.get("DES_AZIONE"),
                "COD_ISIN": instrument.get("COD_ISIN"),
            }
        )
        if len(result) >= limit:
            break
    return result


def call_vertex_gemini(
    prompt: str,
    model: Optional[str] = None,
    project: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    """Call Vertex AI Gemini directly using a gcloud access token."""
    try:
        token = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except FileNotFoundError as exc:
        raise ClassificationError("gcloud CLI is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "gcloud authentication failed").strip()
        raise ClassificationError(detail) from exc
    if not token:
        raise ClassificationError("gcloud returned an empty access token")

    project = project or _project()
    location = location or _location()
    model = model or _model()
    url = (
        f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/"
        f"{location}/publishers/google/models/{model}:generateContent"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ClassificationError(f"Vertex AI HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ClassificationError(f"Vertex AI request failed: {exc.reason}") from exc

    try:
        text = response_body["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ClassificationError(
            "Vertex AI returned no usable structured classification: "
            + json.dumps(response_body, ensure_ascii=False)[:1000]
        ) from exc


def validate_classification(
    result: dict,
    title: str,
    body: str,
    candidates: Sequence[dict],
) -> Tuple[Optional[dict], List[str]]:
    """Validate the structured model result and return its official instrument."""
    errors: List[str] = []
    ticker = str(result.get("ticker") or "").strip()
    company_name = str(result.get("company_name") or "").strip()

    instrument = next(
        (
            item
            for item in candidates
            if str(item.get("COD_AZIONE") or "").casefold() == ticker.casefold()
            and _normalise(str(item.get("DES_AZIONE") or "")) == _normalise(company_name)
        ),
        None,
    )
    if instrument is None:
        errors.append("company_name and ticker are not one matching BigQuery candidate")

    company_evidence = str(result.get("company_evidence") or "")
    if not _contains_verbatim(company_evidence, f"{title}\n{body}"):
        errors.append("company_evidence is not verbatim in the title or body")

    topics = result.get("topics")
    if not isinstance(topics, list) or not 1 <= len(topics) <= 3:
        errors.append("topics must contain between one and three entries")
        topics = []

    topic_names = []
    for index, item in enumerate(topics):
        if not isinstance(item, dict):
            errors.append(f"topics[{index}] is not an object")
            continue
        topic = item.get("topic")
        topic_names.append(topic)
        if topic not in TOPICS:
            errors.append(f"topics[{index}].topic is not controlled")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            errors.append(f"topics[{index}].confidence is not between 0 and 1")
        if not _contains_verbatim(str(item.get("evidence") or ""), body):
            errors.append(f"topics[{index}].evidence is not verbatim in the body")

    if len(topic_names) != len(set(topic_names)):
        errors.append("topics must be distinct")
    primary = result.get("primary_topic")
    if primary not in TOPICS:
        errors.append("primary_topic is not controlled")
    if topic_names and (primary != topic_names[0] or primary not in topic_names):
        errors.append("primary_topic must equal the first topic")
    if not str(result.get("summary") or "").strip():
        errors.append("summary is empty")
    return instrument, errors


def _prompt(
    title: str,
    body: str,
    candidates: Sequence[dict],
    language: str,
    retry_errors: Optional[Sequence[str]] = None,
) -> str:
    candidate_json = json.dumps(
        [
            {
                "company_name": item["DES_AZIONE"],
                "ticker": item["COD_AZIONE"],
                "isin": item.get("COD_ISIN"),
            }
            for item in candidates
        ],
        ensure_ascii=False,
        indent=2,
    )
    retry_block = ""
    if retry_errors:
        retry_block = (
            "\nThe previous response failed validation. Correct every issue:\n- "
            + "\n- ".join(retry_errors)
        )
    return PROMPT.format(
        topic_guide=TOPIC_GUIDE,
        candidates=candidate_json,
        title=title or "(no title supplied)",
        body=body,
        language="Italian" if language == "it" else "English",
        retry_block=retry_block,
    )


def classify_article(
    article: dict,
    instruments: Sequence[dict],
    language: str = "en",
    model: Optional[str] = None,
    project: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    """Classify one article, retry once on local validation failure."""
    title = str(article.get("titolo") or article.get("title") or "")
    body = str(article.get("body") or "")
    if not body.strip():
        raise ClassificationError("The article body is empty")

    candidates = find_instrument_candidates(title, body, instruments)
    if not candidates:
        raise ClassificationError(
            "No listed company in the article matched an ordinary Italian instrument "
            "with quotes in BigQuery"
        )

    errors: Optional[List[str]] = None
    final_result: Optional[dict] = None
    final_instrument: Optional[dict] = None
    attempts = 0
    for _ in range(2):
        attempts += 1
        result = call_vertex_gemini(
            _prompt(title, body, candidates, language, errors),
            model=model,
            project=project,
            location=location,
        )
        instrument, current_errors = validate_classification(
            result, title, body, candidates
        )
        if not current_errors and instrument is not None:
            final_result = result
            final_instrument = instrument
            break
        errors = current_errors

    if final_result is None or final_instrument is None:
        raise ClassificationError(
            "Gemini classification failed validation after two attempts: "
            + "; ".join(errors or ["unknown validation error"])
        )

    topics = final_result["topics"]
    article_source = (
        f"{project or _project()}.news.articles"
        if article.get("content_id")
        else article.get("_input_source") or "stdin"
    )
    return {
        "article": {
            "content_id": article.get("content_id"),
            "titolo": title or None,
            "data_pubblicazione": article.get("data_pubblicazione"),
            "testata": article.get("testata"),
            "url": article.get("URL") or article.get("url"),
        },
        "instrument": {
            "des_azione": final_instrument.get("DES_AZIONE"),
            "cod_azione": final_instrument.get("COD_AZIONE"),
            "isin": final_instrument.get("COD_ISIN"),
        },
        "news": {
            "news_type": final_result["primary_topic"],
            "primary_topic": final_result["primary_topic"],
            "topics": topics,
            "scheduled": None,
            "headline_reports_move": None,
            "matched": [
                {"type": item["topic"], "keyword": item["evidence"]}
                for item in topics
            ],
        },
        "gemini": {
            "model": model or _model(),
            "instrument_name": final_instrument.get("DES_AZIONE"),
            "ticker": final_instrument.get("COD_AZIONE"),
            "company_evidence": final_result["company_evidence"],
            "summary": final_result["summary"],
            "checks": {
                "instrument_validated": True,
                "instrument_source": (
                    f"{project or _project()}.financial_instruments.instruments_info "
                    "+ instruments_quotes"
                ),
                "article_source": article_source,
                "company_evidence_is_verbatim": True,
                "topic_evidence_is_verbatim": True,
                "max_three_topics": len(topics) <= 3,
            },
            "attempts": attempts,
        },
    }


def parse_document(raw: str, title: Optional[str], source: str) -> dict:
    """Parse a JSON article object when possible, otherwise treat input as body."""
    if not raw.strip():
        raise ClassificationError(f"No article content received from {source}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = None

    if isinstance(value, dict):
        article = dict(value)
        article["titolo"] = title or article.get("titolo") or article.get("title") or article.get("headline") or ""
        article["body"] = article.get("body") or article.get("text") or article.get("content") or ""
    else:
        article = {"titolo": title or "", "body": raw}
    article["_input_source"] = source
    return article


def load_article(args: argparse.Namespace) -> dict:
    if args.content_id:
        return fetch_article(args.content_id, project=args.project)
    if args.file:
        path = Path(args.file)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ClassificationError(f"Cannot read {path}: {exc}") from exc
        return parse_document(raw, args.title, str(path.resolve()))
    if sys.stdin.isatty():
        raise ClassificationError(
            "Provide --content-id, --file, or pipe the article body on stdin"
        )
    return parse_document(sys.stdin.read(), args.title, "stdin")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--content-id", help="Article id in the BigQuery news table")
    group.add_argument("--file", help="UTF-8 article text or JSON file")
    parser.add_argument("--title", help="Title for --file or stdin input")
    parser.add_argument("--lang", choices=["en", "it"], default="en")
    parser.add_argument("--project", default=_project())
    parser.add_argument("--location", default=_location())
    parser.add_argument("--model", default=_model())
    parser.add_argument("--out", help="Write JSON to this path instead of stdout")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        article = load_article(args)
        instruments = fetch_instruments(project=args.project)
        card = classify_article(
            article,
            instruments,
            language=args.lang,
            model=args.model,
            project=args.project,
            location=args.location,
        )
        rendered = json.dumps(card, ensure_ascii=False, indent=2)
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered + "\n", encoding="utf-8")
        else:
            print(rendered)
        return 0
    except ClassificationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
