#!/usr/bin/env python3
"""Build verified thesis/earnings analysis for the dashboard from real MF articles.

Usage:
    python3 scripts/build_theses.py
    python3 scripts/build_theses.py --force
    python3 scripts/build_theses.py --only PRY ENEL
    python3 scripts/build_theses.py --force --only STLAM

Reads theses from web/dashboard/data.js (via node), preferring overrides in
data/theses_overrides/<TICKER>.json when present. Company stories/prices from
web/public/data/companies/, article bodies from BigQuery, and calls Gemini
2.5 Flash. Writes data/theses/<TICKER>.json. Re-runs skip Gemini/BQ when the
cache exists and the thesis input is unchanged (unless --force).
Stdlib, Python 3.9.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_card import (  # noqa: E402
    PROJECT,
    MODEL,
    bq,
    fetch_articles,
    numbers_not_in_sources,
    recommendation_words_not_in_article,
)

BUNDLE = ROOT / "web" / "public" / "data"
DATA_JS = ROOT / "web" / "dashboard" / "data.js"
OUT_DIR = ROOT / "data" / "theses"
OVERRIDES_DIR = ROOT / "data" / "theses_overrides"

MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]

DEMO_COMPANIES = {
    "PRY": "prysmian",
    "ENEL": "enel",
    "ISP": "intesa-sanpaolo",
    "LDO": "leonardo",
    "TIT": "telecom-italia",
    "REC": "recordati",
    "MONC": "moncler",
    "SPM": "saipem",
    "TPRO": "technoprobe",
}

# Search aliases for BigQuery title matching (case-insensitive LIKE).
SEARCH_NAMES: Dict[str, List[str]] = {
    "PRY": ["Prysmian"],
    "ENEL": ["Enel"],
    "ISP": ["Intesa Sanpaolo", "Intesa"],
    "LDO": ["Leonardo"],
    "STLAM": ["Stellantis"],
    "TIT": ["Telecom Italia", "Tim"],
    "REC": ["Recordati"],
    "MONC": ["Moncler"],
    "SPM": ["Saipem"],
    "TPRO": ["Technoprobe"],
}

RESULTS_KEYWORDS = (
    "trimestre", "semestre", "conti", "risultati", "ricavi", "utile",
    "bilancio", "ebitda", "guidance", "trimestrale", "redditività", "utili",
)

PREVIEW_RE = re.compile(
    r"\b(attesi|attesa|attese|in vista dei conti|in attesa dei|prima dei conti|"
    r"verso i conti|le stime|si aspettano|aspettano i conti|aspettarsi|"
    r"il \d{1,2} \w+ i conti)\b",
    re.I,
)

QUARTERS = [
    {
        "id": "3T25",
        "label": "3T 2025",
        "periodo": "luglio–settembre 2025",
        "from": "2025-10-20",
        "to": "2025-11-20",
    },
    {
        "id": "4T25",
        "label": "4T 2025",
        "periodo": "ottobre–dicembre 2025",
        "from": "2026-01-25",
        "to": "2026-03-31",
    },
    {
        "id": "1T26",
        "label": "1T 2026",
        "periodo": "gennaio–marzo 2026",
        "from": "2026-04-15",
        "to": "2026-05-31",
    },
    {
        "id": "2T26",
        "label": "2T 2026",
        "periodo": "aprile–giugno 2026",
        "from": "2026-07-15",
        "to": "2026-09-15",
    },
]

QUOTE_TRANS = str.maketrans({
    "«": '"', "»": '"',
    "“": '"', "”": '"',
    "‘": "'", "’": "'",
    "\u00a0": " ",
})

NEWS_FROM = "2026-08-01"

# Bump when the output shape or the inputs to Gemini change, so cached files rebuild.
PIPELINE_VERSION = 2

VERDICT_GROUP = {
    "REACTED": "reazione",
    "DELAYED": "reazione",
    "ALREADY_IN_PRICE": "gia_nel_prezzo",
    "PARTLY_IN_PRICE": "gia_nel_prezzo",
    "MOSTLY_AT_OPEN": "gia_nel_prezzo",
    "NO_REACTION": "nessuna",
}
MAX_TITOLI_PER_INDICATORE = 5


# ---------------------------------------------------------------------------
# Small helpers (also used by test_theses.py)
# ---------------------------------------------------------------------------

def it_date(d: str) -> str:
    """ISO date (YYYY-MM-DD or datetime) → '30 lug 2026'."""
    s = (d or "")[:10]
    y, m, dd = s.split("-")
    return f"{int(dd)} {MESI[int(m) - 1]} {y}"


def normalise_quote(s: str) -> str:
    """Collapse whitespace and normalise fancy quotes for substring checks."""
    t = (s or "").translate(QUOTE_TRANS)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def quote_in_body(citazione: str, body: str) -> bool:
    if not citazione:
        return False
    return normalise_quote(citazione) in normalise_quote(body)


def _peso_previsto(tesi: dict):
    """Normalise pesoPrevisto for fingerprints (None == missing / empty)."""
    peso = tesi.get("pesoPrevisto", None)
    if peso is None or peso == "":
        return None
    try:
        return float(peso)
    except (TypeError, ValueError):
        return None


def thesis_fingerprint(tesi: dict) -> str:
    payload = {
        "motivo": tesi.get("motivo") or "",
        "indicatori": list(tesi.get("indicatori") or []),
        "orizzonte": tesi.get("orizzonte") or "",
        "pesoPrevisto": _peso_previsto(tesi),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def is_preview_title(titolo: str) -> bool:
    return bool(PREVIEW_RE.search(titolo or ""))


def assign_quarter(pub_date: str) -> Optional[str]:
    """Return quarter id if pub_date (YYYY-MM-DD) falls in a results window."""
    d = (pub_date or "")[:10]
    for q in QUARTERS:
        if q["from"] <= d <= q["to"]:
            return q["id"]
    return None


def force_insufficiente(quarters_ok: List[dict], latest_id: Optional[str]) -> bool:
    """True if latest available quarter is older than 1T26 or fewer than 2 survive."""
    if len(quarters_ok) < 2:
        return True
    order = [q["id"] for q in QUARTERS]
    if latest_id is None:
        return True
    # insufficiente if latest available is older than 1T26
    try:
        return order.index(latest_id) < order.index("1T26")
    except ValueError:
        return True


def _empty_counts() -> Dict[str, int]:
    return {"n": 0, "reazione": 0, "gia_nel_prezzo": 0, "nessuna": 0}


def news_rollup(
    stories: List[dict],
    tags: Dict[str, str],
    indicatori: List[str],
    since: str = NEWS_FROM,
) -> dict:
    """Deterministic summary of MF stories since `since`, grouped by thesis indicator."""
    per: Dict[str, dict] = {
        nome: {"nome": nome, **_empty_counts(), "titoli": []} for nome in indicatori
    }
    fuori = _empty_counts()
    n = 0
    for st in sorted(stories or [], key=lambda s: s.get("pub_local") or "", reverse=True):
        pub = st.get("pub_local") or ""
        if pub < since:
            continue
        n += 1
        group = VERDICT_GROUP.get(st.get("status") or "", "nessuna")
        nome = tags.get(st.get("content_id") or "")
        bucket = per.get(nome) if nome else None
        if bucket is None:
            fuori["n"] += 1
            fuori[group] += 1
            continue
        bucket["n"] += 1
        bucket[group] += 1
        if len(bucket["titoli"]) < MAX_TITOLI_PER_INDICATORE:
            bucket["titoli"].append({
                "content_id": st.get("content_id"),
                "titolo": st.get("titolo") or "",
                "data": it_date(pub),
                "status": st.get("status"),
            })
    return {
        "da": it_date(since),
        "n": n,
        "per_indicatore": [per[nome] for nome in indicatori],
        "fuori_tesi": fuori,
    }


def news_rollup_text(rollup: dict) -> str:
    """Plain-Italian block for the decision prompt; also used as number-check source."""
    lines = [f"Articoli MF dal {rollup['da']}: {rollup['n']}."]
    for ind in rollup["per_indicatore"]:
        lines.append(
            f"- {ind['nome']}: {ind['n']} articoli "
            f"(reazione del prezzo {ind['reazione']}, già nel prezzo {ind['gia_nel_prezzo']}, "
            f"nessun movimento anomalo {ind['nessuna']})"
        )
        for t in ind["titoli"]:
            lines.append(f"  · {t['data']}: {t['titolo']}")
    f = rollup["fuori_tesi"]
    lines.append(
        f"- Non toccano la tesi: {f['n']} articoli "
        f"(reazione {f['reazione']}, già nel prezzo {f['gia_nel_prezzo']}, nessuna {f['nessuna']})"
    )
    return "\n".join(lines)


def reaction_window(
    pub_local: str,
    days: Sequence[str],
    closes: Sequence[float],
) -> Optional[dict]:
    """Deterministic price reaction around a results article.

    If pub time < 17:30 → previous session close → publication-day close.
    Else → publication-day close → next session close.
    """
    if not pub_local or not days:
        return None
    pub_s = str(pub_local).strip().replace(" ", "T")
    try:
        if "T" in pub_s:
            dt = datetime.strptime(pub_s[:19], "%Y-%m-%dT%H:%M:%S")
        else:
            dt = datetime.strptime(pub_s[:10], "%Y-%m-%d")
    except ValueError:
        return None

    by_d = {d: c for d, c in zip(days, closes) if c is not None}
    sorted_days = sorted(by_d.keys())
    pub_day = dt.strftime("%Y-%m-%d")

    # Find session on or before pub_day, and next after.
    on_or_before = [d for d in sorted_days if d <= pub_day]
    after = [d for d in sorted_days if d > pub_day]
    if not on_or_before:
        return None

    before_cutoff = dt.time() < time(17, 30)
    if before_cutoff:
        # previous session → pub day (or last session <= pub day if pub day not a session)
        if pub_day in by_d:
            a_day = pub_day
            prev = [d for d in sorted_days if d < pub_day]
            if not prev:
                return None
            da_day = prev[-1]
        else:
            # non-trading day: use last before as "pub", previous as "da"
            a_day = on_or_before[-1]
            prev = [d for d in sorted_days if d < a_day]
            if not prev:
                return None
            da_day = prev[-1]
        nota = (
            f"Articolo MF delle {dt.strftime('%H:%M')}: "
            f"risultati noti prima dell'apertura."
            if dt.time() < time(9, 0)
            else f"Articolo MF delle {dt.strftime('%H:%M')}: risultati durante la seduta."
        )
    else:
        # pub day close → next session
        if pub_day in by_d:
            da_day = pub_day
        else:
            da_day = on_or_before[-1]
        if not after:
            return None
        a_day = after[0]
        nota = (
            f"Articolo MF delle {dt.strftime('%H:%M')}: "
            f"risultati pubblicati a mercati chiusi."
        )

    c0, c1 = by_d.get(da_day), by_d.get(a_day)
    if c0 is None or c1 is None or c0 == 0:
        return None
    pct = round((c1 / c0 - 1) * 100, 1)
    return {
        "pct": pct,
        "da": f"chiusura del {it_date(da_day)}",
        "a": f"chiusura del {it_date(a_day)}",
        "nota": nota,
    }


def call_gemini(prompt: str, schema: dict, max_retries: int = 8) -> dict:
    """Vertex Gemini call with a caller-supplied JSON responseSchema."""
    import time as _time
    import urllib.error

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
            "responseSchema": schema,
        },
    }
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                body = json.load(r)
            # Pace requests to stay under Vertex quotas.
            _time.sleep(1.5)
            return json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 503) and attempt < max_retries - 1:
                wait = 5 * (2 ** attempt)
                print(f"    Gemini HTTP {e.code}, retry in {wait}s…", flush=True)
                _time.sleep(wait)
                if attempt % 3 == 2:
                    token = subprocess.run(
                        ["gcloud", "auth", "print-access-token"],
                        capture_output=True, text=True, check=True,
                    ).stdout.strip()
                continue
            raise
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                wait = 5 * (2 ** attempt)
                print(f"    Gemini error {e!r}, retry in {wait}s…", flush=True)
                _time.sleep(wait)
                continue
            raise
    raise last_err or RuntimeError("Gemini call failed")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_demo() -> dict:
    """Load window.DEMO_DATA from data.js via node (serie may be a function)."""
    script = (
        "global.window={};"
        f"require({json.dumps(str(DATA_JS))});"
        "const D=window.DEMO_DATA;"
        "const aziende={};"
        "for (const [t,a] of Object.entries(D.aziende)) {"
        "  aziende[t]={nome:a.nome,prezzo:a.prezzo,tesi:a.tesi};"
        "}"
        "console.log(JSON.stringify({"
        "  portafoglio:D.portafoglio,watchlist:D.watchlist,aziende"
        "}));"
    )
    out = subprocess.run(
        ["node", "-e", script],
        capture_output=True, text=True, check=True, cwd=str(ROOT),
    ).stdout
    return json.loads(out)


def load_override(ticker: str) -> Optional[dict]:
    p = OVERRIDES_DIR / f"{ticker.upper()}.json"
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def apply_overrides(demo: dict) -> List[str]:
    """Prefer data/theses_overrides/<TICKER>.json over data.js theses. Returns tickers overridden."""
    applied: List[str] = []
    for ticker, a in (demo.get("aziende") or {}).items():
        ov = load_override(ticker)
        if not ov:
            continue
        tesi = dict(a.get("tesi") or {})
        for k in ("orizzonte", "motivo", "indicatori", "pesoPrevisto"):
            if k in ov:
                tesi[k] = ov[k]
        a["tesi"] = tesi
        applied.append(ticker)
    return applied


def load_company(slug: str) -> Optional[dict]:
    p = BUNDLE / "companies" / f"{slug}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def portfolio_weights(demo: dict) -> Dict[str, float]:
    total = 0.0
    values: Dict[str, float] = {}
    for p in demo["portafoglio"]:
        t = p["ticker"]
        a = demo["aziende"].get(t) or {}
        v = float(p["quantita"]) * float(a.get("prezzo") or 0)
        values[t] = v
        total += v
    if total <= 0:
        return {t: 0.0 for t in values}
    return {t: round(100.0 * v / total, 1) for t, v in values.items()}


# ---------------------------------------------------------------------------
# Candidate articles
# ---------------------------------------------------------------------------

def _kw_sql_fragment() -> str:
    # Whole words: a plain LIKE '%conti%' also matches "sconti", "racconti".
    # Leading boundary only: RE2's \b is ASCII, so a trailing \b never matches after "à".
    return "REGEXP_CONTAINS(titolo, r'(?i)\\b(" + "|".join(RESULTS_KEYWORDS) + ")')"


_RESULTS_WORD_RE = re.compile(r"\b(" + "|".join(RESULTS_KEYWORDS) + r"|utili|chiude il 20\d\d)\b", re.I)


def results_score(titolo: str) -> int:
    return len(_RESULTS_WORD_RE.findall(titolo or ""))


def search_bq_candidates(names: List[str], date_from: str, date_to: str) -> List[dict]:
    """Title search on news.articles within [date_from, date_to], results keywords."""
    name_parts = []
    for n in names:
        low = n.lower().replace("'", "''")
        if low == "tim":
            # Word-boundary: avoid matching "ultimi", "trimestrale", …
            name_parts.append(r"(REGEXP_CONTAINS(titolo, r'(?i)\bTim\b') "
                              r"AND NOT REGEXP_CONTAINS(titolo, r'(?i)\bTim (Brasil|Cook)\b'))")
        else:
            name_parts.append(f"LOWER(titolo) LIKE '%{low}%'")
    name_clause = " OR ".join(name_parts)
    sql = f"""
SELECT content_id, titolo,
       CAST(data_pubblicazione AS STRING) AS data_pubblicazione,
       LENGTH(IFNULL(body, '')) AS body_len
FROM `class-hackaton-09.news.articles`
WHERE DATE(data_pubblicazione) BETWEEN @from_date AND @to_date
  AND ({name_clause})
  AND {_kw_sql_fragment()}
  AND NOT REGEXP_CONTAINS(titolo, r"^(Borse oggi in diretta|Cos.è successo oggi)")
ORDER BY data_pubblicazione
"""
    try:
        rows = bq(
            sql,
            {"from_date": ("DATE", date_from), "to_date": ("DATE", date_to)},
            max_rows=500,
        )
    except subprocess.CalledProcessError as e:
        print(f"  BQ search failed: {e}", file=sys.stderr)
        return []
    return rows


def collect_candidates(
    ticker: str,
    company: Optional[dict],
) -> Dict[str, List[dict]]:
    """Per-quarter candidate stubs: content_id, titolo, pub_local, body_len, source."""
    by_q: Dict[str, List[dict]] = {q["id"]: [] for q in QUARTERS}
    seen: Dict[str, set] = {q["id"]: set() for q in QUARTERS}

    def add(qid: str, item: dict) -> None:
        cid = item["content_id"]
        if cid in seen[qid]:
            return
        seen[qid].add(cid)
        by_q[qid].append(item)

    # 1) earnings stories from company file
    if company:
        for st in company.get("stories") or []:
            if st.get("news_type") != "earnings":
                continue
            qid = assign_quarter(st.get("pub_local") or "")
            if not qid:
                continue
            add(qid, {
                "content_id": st["content_id"],
                "titolo": st.get("titolo") or "",
                "pub_local": st.get("pub_local") or "",
                "body_len": 0,
                "source": "company",
            })

    # 2) BigQuery title search across full span of windows
    names = SEARCH_NAMES.get(ticker) or [ticker]
    date_from = QUARTERS[0]["from"]
    date_to = QUARTERS[-1]["to"]
    for row in search_bq_candidates(names, date_from, date_to):
        pub = (row.get("data_pubblicazione") or "").replace(" ", "T")
        qid = assign_quarter(pub)
        if not qid:
            continue
        add(qid, {
            "content_id": row["content_id"],
            "titolo": row.get("titolo") or "",
            "pub_local": pub,
            "body_len": int(row.get("body_len") or 0),
            "source": "bq",
        })

    # Rank: non-preview first; then titles that read most like a results report
    # about this company (title opens with its name: +2, e.g. not "Subsea7, … Saipem");
    # company-file earnings stories count as one extra hit; then earliest pub.
    lead = tuple(n.lower() for n in names)

    def score(i: dict) -> int:
        t = (i["titolo"] or "").lower()
        return (results_score(i["titolo"]) + (2 if t.startswith(lead) else 0)
                + (1 if i.get("source") == "company" else 0))

    out: Dict[str, List[dict]] = {}
    for q in QUARTERS:
        qid = q["id"]
        items = by_q[qid]
        real = [i for i in items if not is_preview_title(i["titolo"])]
        pool = real if real else items
        pool.sort(key=lambda i: (
            -score(i),
            i.get("pub_local") or "",
            -(i.get("body_len") or 0),
        ))
        out[qid] = pool[:2]
    return out


# ---------------------------------------------------------------------------
# Gemini schemas & prompts
# ---------------------------------------------------------------------------

QUARTER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "pertinente": {"type": "BOOLEAN"},
        "fatti": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "testo": {"type": "STRING"},
                    "citazione": {"type": "STRING"},
                    "content_id": {"type": "STRING"},
                },
                "required": ["testo", "citazione", "content_id"],
            },
        },
        "metriche": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "nome": {"type": "STRING"},
                    "valore": {"type": "STRING"},
                    "confronto": {"type": "STRING"},
                    "base": {"type": "STRING"},
                    "nota": {"type": "STRING"},
                },
                "required": ["nome", "valore", "confronto", "base", "nota"],
            },
        },
        "guidance": {"type": "STRING"},
        "cambiato": {"type": "STRING"},
        "impatto": {
            "type": "OBJECT",
            "properties": {
                "effetto": {"type": "STRING"},
                "testo": {"type": "STRING"},
            },
            "required": ["effetto", "testo"],
        },
        "indicatori": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "nome": {"type": "STRING"},
                    "stato": {"type": "STRING"},
                    "testo": {"type": "STRING"},
                    "citazione": {"type": "STRING"},
                    "content_id": {"type": "STRING"},
                },
                "required": ["nome", "stato", "testo"],
            },
        },
    },
    "required": [
        "pertinente", "fatti", "metriche", "guidance",
        "cambiato", "impatto", "indicatori",
    ],
}

AGG_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "stato": {"type": "STRING"},
        "sintesi": {"type": "STRING"},
        "interpretazioni": {"type": "ARRAY", "items": {"type": "STRING"}},
        "evoluzione": {"type": "STRING"},
        "mancano": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["stato", "sintesi", "interpretazioni", "evoluzione"],
}

DEC_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "azione": {"type": "STRING"},
        "motivazione": {"type": "STRING"},
        "aFavore": {"type": "ARRAY", "items": {"type": "STRING"}},
        "rischio": {"type": "STRING"},
        "cambierebbe": {"type": "STRING"},
    },
    "required": ["azione", "motivazione", "aFavore", "rischio", "cambierebbe"],
}

NEWS_IND_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "tags": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "content_id": {"type": "STRING"},
                    "nome": {"type": "STRING"},
                },
                "required": ["content_id", "nome"],
            },
        },
    },
    "required": ["tags"],
}


def _format_articles(arts: List[dict]) -> str:
    blocks = []
    for a in arts:
        blocks.append(
            f"--- ARTICLE content_id={a.get('content_id')}\n"
            f"TITLE: {a.get('titolo') or ''}\n"
            f"PUB: {(a.get('data_pubblicazione') or a.get('pub_local') or '')[:16]}\n"
            f"URL: {a.get('URL') or a.get('url') or ''}\n"
            f"BODY:\n{a.get('body') or ''}\n"
        )
    return "\n".join(blocks)


def quarter_prompt(
    tesi: dict,
    quarter: dict,
    articles: List[dict],
    prev_facts: List[dict],
    retry_block: str = "",
) -> str:
    prev = "Nessun trimestre precedente verificato."
    if prev_facts:
        prev = "\n".join(f"- {f.get('testo')}" for f in prev_facts)
    inds = ", ".join(tesi.get("indicatori") or [])
    return f"""Sei un analista che spiega i risultati trimestrali a un investitore retail italiano.
Rispondi SOLO in italiano, linguaggio semplice e concreto. Nessuna raccomandazione buy/sell.

TESI DI INVESTIMENTO (input dell'utente):
- Orizzonte: {tesi.get('orizzonte')}
- Motivo: {tesi.get('motivo')}
- Indicatori da monitorare (usa ESATTAMENTE questi nomi): {inds}

TRIMESTRE DA VALUTARE: {quarter['label']} ({quarter['periodo']})
Finestra tipica di pubblicazione: {quarter['from']} → {quarter['to']}

FATTI VERIFICATI DEL TRIMESTRE PRECEDENTE:
{prev}

ARTICOLI MF (unica fonte di numeri e citazioni):
{_format_articles(articles)}

Restituisci JSON con:
- pertinente: true SOLO se almeno un articolo riporta davvero i risultati di QUESTO trimestre/periodo (non anteprime, non analisi di terzi senza numeri societari, non risultati di altre società).
- fatti: al massimo 3. Ogni fatto ha testo (parafrasi breve), citazione (frase COPIATA ALLA LETTERA dal body di un articolo), content_id di quell'articolo.
- metriche: 0-4. valore e confronto devono essere COPIATI dal testo degli articoli. base è "a/a", "t/t" o stringa vuota. nota breve o vuota.
- guidance: stringa o stringa vuota se assente.
- cambiato: cosa cambia rispetto al trimestre precedente (usa i fatti precedenti se disponibili).
- impatto: effetto uno tra rafforzza→usa "rafforza", "invariata", "indebolisce"; testo breve sul legame con la tesi.
- indicatori: una voce per OGNI indicatore della tesi. stato: a_favore|neutro|contro|non_citato. Se citato, citazione verbatim + content_id; altrimenti citazione e content_id vuoti.

Regole ferree:
- Ogni citazione deve essere una sottostringa esatta del body.
- Ogni numero in testo/metriche/guidance/cambiato/impatto deve comparire negli articoli.
- Non inventare. Se i dati non bastano, pertinente=false e fatti vuoti.
{retry_block}
"""


def _quarters_text(quarters: List[dict]) -> str:
    q_txt = []
    for q in quarters:
        if q.get("mancante"):
            q_txt.append(f"- {q['label']}: mancante")
            continue
        fatti = "; ".join(f.get("testo", "") for f in (q.get("fatti") or [])[:3])
        imp = (q.get("impatto") or {}).get("testo") or ""
        q_txt.append(
            f"- {q['label']} ({q.get('data')}): {fatti} | impatto: {imp} | "
            f"guidance: {q.get('guidance') or 'n/d'}"
        )
    return "\n".join(q_txt)


def _tesi_header(ticker: str, tesi: dict) -> str:
    return (
        f"TICKER: {ticker}\n"
        f"TESI: {tesi.get('motivo')}\n"
        f"Indicatori: {', '.join(tesi.get('indicatori') or [])}\n"
        f"Orizzonte: {tesi.get('orizzonte')}"
    )


def aggregate_prompt(
    ticker: str,
    tesi: dict,
    quarters: List[dict],
    retry_block: str = "",
) -> str:
    return f"""Sei un analista per investitori retail. Italiano semplice. Nessun target di prezzo, nessuna probabilità.

{_tesi_header(ticker, tesi)}

TRIMESTRI VERIFICATI (dal più vecchio):
{_quarters_text(quarters)}

Restituisci JSON:
- stato: rafforzata | invariata | indebolita | insufficiente
- sintesi: ESATTAMENTE 2 frasi sul legame tra risultati e tesi
- interpretazioni: al massimo 2 opinioni chiaramente etichettabili come opinioni. NON menzionare mai il peso di portafoglio né percentuali di peso.
- evoluzione: 1-2 frasi sull'andamento tra i trimestri
- mancano: lista di ciò che manca (solo se davvero insufficiente; altrimenti array vuoto)

Non citare numeri che non sono nei trimestri verificati.
Non dare probabilità né target di prezzo.
{retry_block}
"""


def decision_prompt(
    ticker: str,
    tesi: dict,
    contesto: str,
    peso: Optional[float],
    esito: dict,
    indicatori: List[dict],
    rollup: dict,
    azioni_ok: List[str],
    retry_block: str = "",
) -> str:
    peso_line = (
        f"Peso attuale nel portafoglio dimostrativo: {peso}% "
        f"(puoi ragionare sulla concentrazione)."
        + (" Sopra il 20% del portafoglio non indicare 'aggiungere': anche con una tesi rafforzata "
           "aumenterebbe la concentrazione; valuta 'mantenere' o 'ridurre'."
           if peso is not None and peso >= 20 else "")
        if peso is not None and contesto == "portafoglio"
        else "Il titolo è in watchlist (non ancora in portafoglio)."
    )
    ind_txt = "\n".join(
        f"- {i['nome']}: {i['stato']} — {i.get('testo') or ''}" for i in indicatori
    ) or "- nessun indicatore"
    return f"""Sei un analista per investitori retail. Italiano semplice. Nessun target di prezzo, nessuna probabilità.
Devi dare UNA indicazione da valutare che tenga conto di ENTRAMBE le analisi sotto: i risultati rispetto alla tesi e le notizie recenti.

{_tesi_header(ticker, tesi)}
Contesto: {contesto}
{peso_line}

1) ANALISI DELLA TESI SUI RISULTATI VERIFICATI
Stato della tesi: {esito.get('stato')}
Sintesi: {esito.get('sintesi')}
Andamento tra i trimestri: {esito.get('evoluzione') or 'n/d'}
Indicatori della tesi nei risultati:
{ind_txt}

2) ANALISI DELLE NOTIZIE MF (verdetto sul prezzo calcolato, non stimato)
{news_rollup_text(rollup)}

Azioni ammesse ({contesto}): {', '.join(azioni_ok)}

Restituisci JSON:
- azione: una delle ammesse
- motivazione: 2 frasi. La prima collega i risultati alla tesi, la seconda dice cosa aggiungono o tolgono le notizie recenti.
- aFavore: al massimo 3 elementi; almeno uno dai risultati e, se ci sono notizie collegate alla tesi, almeno uno dalle notizie.
- rischio: il rischio principale, anche se viene dalle notizie.
- cambierebbe: cosa, nei prossimi risultati o nelle prossime notizie, cambierebbe la valutazione.

Non citare numeri che non compaiono sopra. Se le notizie non toccano la tesi, dillo invece di inventare un legame.
{retry_block}
"""


def news_indicators_prompt(tesi: dict, headlines: List[dict]) -> str:
    inds = ", ".join(tesi.get("indicatori") or [])
    lines = "\n".join(
        f"- {h['content_id']}: {h['titolo']}" for h in headlines
    )
    return f"""Per ogni titolo MF sotto, se tocca CHIARAMENTE uno degli indicatori della tesi, restituisci {{content_id, nome}} con nome ESATTAMENTE uguale a uno di: {inds}.
Se il titolo non riguarda un indicatore, non includerlo.

Indicatori ammessi: {inds}
Motivo tesi: {tesi.get('motivo')}

TITOLI:
{lines}
"""


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _sources_text(articles: List[dict]) -> str:
    parts = []
    for a in articles:
        parts.append(a.get("titolo") or "")
        parts.append(a.get("body") or "")
    return "\n".join(parts)


def _body_by_id(articles: List[dict]) -> Dict[str, str]:
    return {a["content_id"]: a.get("body") or "" for a in articles}


def verify_quarter(
    raw: dict,
    articles: List[dict],
    thesis_indicators: List[str],
) -> Tuple[dict, List[str], dict]:
    """Apply deterministic checks; return (cleaned, failure_msgs, debug_drop)."""
    failures: List[str] = []
    drops = {"fatti": 0, "metriche": 0, "indicatori_to_non_citato": 0, "fields": []}
    sources = _sources_text(articles)
    bodies = _body_by_id(articles)
    art_ids = set(bodies)

    def check_nums(label: str, text: str) -> bool:
        missing = numbers_not_in_sources(text or "", sources)
        if missing:
            failures.append(f"{label}: numbers not in sources {missing}")
            return False
        return True

    def check_rec(label: str, text: str) -> bool:
        bad = recommendation_words_not_in_article(text or "", sources)
        if bad:
            failures.append(f"{label}: recommendation words {bad}")
            return False
        return True

    pertinente = bool(raw.get("pertinente"))
    fatti_ok = []
    for i, f in enumerate(raw.get("fatti") or []):
        if len(fatti_ok) >= 3:
            break
        testo = (f.get("testo") or "").strip()
        cit = (f.get("citazione") or "").strip()
        cid = (f.get("content_id") or "").strip()
        ok = True
        if cid not in art_ids:
            failures.append(f"fatto[{i}]: unknown content_id {cid}")
            ok = False
        elif not quote_in_body(cit, bodies[cid]):
            failures.append(f"fatto[{i}]: citazione not verbatim")
            ok = False
        if not check_nums(f"fatto[{i}].testo", testo):
            ok = False
        if not check_rec(f"fatto[{i}].testo", testo):
            ok = False
        if ok:
            fatti_ok.append({"testo": testo, "citazione": cit, "content_id": cid})
        else:
            drops["fatti"] += 1

    metriche_ok = []
    for i, m in enumerate(raw.get("metriche") or []):
        if len(metriche_ok) >= 4:
            break
        nome = (m.get("nome") or "").strip()
        valore = (m.get("valore") or "").strip()
        confronto = (m.get("confronto") or "").strip()
        base = (m.get("base") or "").strip() or None
        if base not in ("a/a", "t/t", None):
            base = None
        nota = (m.get("nota") or "").strip() or None
        blob = f"{nome} {valore} {confronto} {nota or ''}"
        ok = check_nums(f"metrica[{i}]", blob) and check_rec(f"metrica[{i}]", blob)
        # valore/confronto must appear as substrings in sources (after norm)
        if ok and valore and normalise_quote(valore) not in normalise_quote(sources):
            # soft: number check already covers digits; if no digits, require substring
            if not re.search(r"\d", valore):
                failures.append(f"metrica[{i}]: valore not in sources")
                ok = False
        if ok:
            metriche_ok.append({
                "nome": nome, "valore": valore, "confronto": confronto,
                "base": base, "nota": nota,
            })
        else:
            drops["metriche"] += 1

    guidance = (raw.get("guidance") or "").strip() or None
    if guidance in ("", "null", "None"):
        guidance = None
    if guidance:
        if not (check_nums("guidance", guidance) and check_rec("guidance", guidance)):
            drops["fields"].append("guidance")
            guidance = None

    cambiato = (raw.get("cambiato") or "").strip()
    if cambiato and not (check_nums("cambiato", cambiato) and check_rec("cambiato", cambiato)):
        drops["fields"].append("cambiato")
        cambiato = "Confronto con il trimestre precedente non verificabile dai testi."

    impatto = raw.get("impatto") or {}
    effetto = (impatto.get("effetto") or "invariata").strip()
    if effetto not in ("rafforza", "invariata", "indebolisce"):
        effetto = "invariata"
    impatto_testo = (impatto.get("testo") or "").strip()
    if impatto_testo and not (
        check_nums("impatto", impatto_testo) and check_rec("impatto", impatto_testo)
    ):
        drops["fields"].append("impatto")
        impatto_testo = "Impatto sulla tesi non verificabile dai numeri degli articoli."
    impatto_ok = {"effetto": effetto, "testo": impatto_testo}

    # Indicators: one per thesis indicator
    ind_by_name = {}
    for ind in raw.get("indicatori") or []:
        nome = (ind.get("nome") or "").strip()
        if nome:
            ind_by_name[nome] = ind

    indicatori_ok = []
    for nome in thesis_indicators:
        ind = ind_by_name.get(nome) or {}
        stato = (ind.get("stato") or "non_citato").strip()
        if stato not in ("a_favore", "neutro", "contro", "non_citato"):
            stato = "non_citato"
        testo = (ind.get("testo") or "").strip() or "Non citato negli articoli di questo trimestre."
        cit = (ind.get("citazione") or "").strip() or None
        cid = (ind.get("content_id") or "").strip() or None
        if stato != "non_citato":
            ok = True
            if not cid or cid not in art_ids:
                ok = False
                failures.append(f"indicatore {nome}: bad content_id")
            elif not cit or not quote_in_body(cit, bodies[cid]):
                ok = False
                failures.append(f"indicatore {nome}: citazione not verbatim")
            if testo and not (check_nums(f"ind {nome}", testo) and check_rec(f"ind {nome}", testo)):
                ok = False
            if not ok:
                drops["indicatori_to_non_citato"] += 1
                stato, cit, cid = "non_citato", None, None
                testo = "Citazione non verificabile; indicatore non citato in modo affidabile."
        else:
            cit, cid = None, None
        indicatori_ok.append({
            "nome": nome, "stato": stato, "testo": testo,
            "citazione": cit, "content_id": cid,
        })

    if not pertinente:
        failures.append("pertinente=false")
    if not fatti_ok:
        failures.append("no surviving facts")

    cleaned = {
        "pertinente": pertinente and bool(fatti_ok),
        "fatti": fatti_ok,
        "metriche": metriche_ok,
        "guidance": guidance,
        "cambiato": cambiato,
        "impatto": impatto_ok,
        "indicatori": indicatori_ok,
    }
    return cleaned, failures, drops


def _text_checker(sources: str, failures: List[str]):
    def check(label: str, text: str) -> str:
        t = (text or "").strip()
        missing = numbers_not_in_sources(t, sources)
        if missing:
            failures.append(f"{label}: numbers {missing}")
        bad = recommendation_words_not_in_article(t, sources)
        if bad:
            failures.append(f"{label}: rec words {bad}")
        return t
    return check


def verify_aggregate(raw: dict, sources_extra: str) -> Tuple[dict, List[str]]:
    failures: List[str] = []
    check = _text_checker(sources_extra, failures)

    stato = (raw.get("stato") or "insufficiente").strip()
    if stato not in ("rafforzata", "invariata", "indebolita", "insufficiente"):
        stato = "invariata"
    sintesi = check("sintesi", raw.get("sintesi") or "")
    interpretazioni = []
    for i, s in enumerate((raw.get("interpretazioni") or [])[:2]):
        interpretazioni.append(check(f"interpretazioni[{i}]", s))
    # Strip any accidental peso mentions
    interpretazioni = [
        re.sub(r"(?i)\bpeso\b[^.]*\.?", "", x).strip() or x
        for x in interpretazioni
    ]
    evoluzione = check("evoluzione", raw.get("evoluzione") or "")
    mancano = [str(x) for x in (raw.get("mancano") or []) if x]

    cleaned = {
        "stato": stato,
        "sintesi": sintesi,
        "interpretazioni": interpretazioni,
        "evoluzione": evoluzione,
        "mancano": mancano,
    }
    return cleaned, failures


def verify_decision(
    raw: dict,
    sources: str,
    contesto: str,
    azioni_ok: List[str],
    rollup: dict,
) -> Tuple[dict, List[str]]:
    failures: List[str] = []
    check = _text_checker(sources, failures)
    azione = (raw.get("azione") or "").strip()
    if azione not in azioni_ok:
        failures.append(f"azione {azione} not in {azioni_ok}")
        azione = azioni_ok[0]
    decisione = {
        "contesto": contesto,
        "azione": azione,
        "motivazione": check("motivazione", raw.get("motivazione") or ""),
        "aFavore": [check(f"aFavore[{i}]", x) for i, x in enumerate((raw.get("aFavore") or [])[:3])],
        "rischio": check("rischio", raw.get("rischio") or ""),
        "cambierebbe": check("cambierebbe", raw.get("cambierebbe") or ""),
        "basata_su": ["risultati", "notizie"],
        "notizie_considerate": rollup.get("n", 0),
        "notizie_da": rollup.get("da"),
    }
    return decisione, failures


# ---------------------------------------------------------------------------
# Fonte helpers / final shaping
# ---------------------------------------------------------------------------

def make_fonte(article: dict) -> dict:
    pub = article.get("data_pubblicazione") or article.get("pub_local") or ""
    url = article.get("URL") or article.get("url") or ""
    return {
        "titolo": article.get("titolo") or "",
        "url": url,
        "data": it_date(pub) if pub[:10] else "",
    }


def fatti_with_fonte(fatti: List[dict], by_id: Dict[str, dict]) -> List[dict]:
    out = []
    for f in fatti:
        art = by_id.get(f["content_id"]) or {}
        out.append({
            "testo": f["testo"],
            "citazione": f["citazione"],
            "fonte": make_fonte(art),
        })
    return out


def indicatori_with_fonte(
    inds: List[dict], by_id: Dict[str, dict]
) -> List[dict]:
    out = []
    for ind in inds:
        cid = ind.get("content_id")
        fonte = make_fonte(by_id[cid]) if cid and cid in by_id else None
        out.append({
            "nome": ind["nome"],
            "stato": ind["stato"],
            "testo": ind["testo"],
            "citazione": ind.get("citazione"),
            "fonte": fonte,
        })
    return out


def mancante_quarter(q: dict) -> dict:
    return {"id": q["id"], "label": q["label"], "mancante": True}


# ---------------------------------------------------------------------------
# STLAM prices from BigQuery
# ---------------------------------------------------------------------------

def fetch_stlam_prices() -> Optional[Tuple[List[str], List[float]]]:
    """Stellantis trades as COD_AZIONE FIAT (ISIN NL00150001Q9)."""
    sql = """
SELECT CAST(DATE(DATA_QUOTAZ) AS STRING) AS d, PRZ_LAST AS close
FROM `class-hackaton-09.financial_instruments.instruments_quotes`
WHERE COD_AZIONE = 'FIAT'
  AND PRZ_LAST > 0
  AND DATE(DATA_QUOTAZ) BETWEEN '2025-10-01' AND '2026-09-20'
ORDER BY d
"""
    try:
        rows = bq(sql, {}, max_rows=5000)
    except Exception as e:
        print(f"  STLAM price query failed: {e}", file=sys.stderr)
        return None
    if not rows:
        return None
    days = [r["d"][:10] for r in rows]
    closes = [float(r["close"]) for r in rows]
    return days, closes


# ---------------------------------------------------------------------------
# Per-ticker pipeline
# ---------------------------------------------------------------------------

def run_quarter_gemini(
    tesi: dict,
    quarter: dict,
    articles: List[dict],
    prev_facts: List[dict],
) -> Tuple[dict, List[dict], dict]:
    """Returns (verified, attempts, drop_stats)."""
    attempts: List[dict] = []
    prompt = quarter_prompt(tesi, quarter, articles, prev_facts)
    raw = call_gemini(prompt, QUARTER_SCHEMA)
    cleaned, failures, drops = verify_quarter(raw, articles, list(tesi.get("indicatori") or []))
    attempts.append({"raw": raw, "failures": failures, "drops": drops})

    if failures and (not cleaned["pertinente"] or drops["fatti"] or drops["metriche"]
                     or drops["indicatori_to_non_citato"] or drops["fields"]):
        retry = (
            "\nTENTATIVO PRECEDENTE FALLITO — correggi:\n- "
            + "\n- ".join(failures[:12])
            + "\nCopia citazioni e numeri ESATTAMENTE dal body; niente raccomandazioni.\n"
        )
        raw2 = call_gemini(quarter_prompt(tesi, quarter, articles, prev_facts, retry), QUARTER_SCHEMA)
        cleaned2, failures2, drops2 = verify_quarter(
            raw2, articles, list(tesi.get("indicatori") or [])
        )
        attempts.append({"raw": raw2, "failures": failures2, "drops": drops2})
        # Prefer the attempt with more surviving facts
        if len(cleaned2["fatti"]) >= len(cleaned["fatti"]):
            cleaned, failures, drops = cleaned2, failures2, drops2

    # Final drop pass already applied inside verify; if still not pertinente → empty
    if not cleaned["pertinente"] or not cleaned["fatti"]:
        cleaned["pertinente"] = False
        cleaned["fatti"] = []

    return cleaned, attempts, drops


def merge_indicatori_across_quarters(
    thesis_inds: List[str],
    quarters_chron: List[Tuple[dict, Optional[dict]]],
) -> List[dict]:
    """Latest quarter's assessments; fall back to most recent cited per indicator."""
    latest_verified = None
    for _qmeta, v in reversed(quarters_chron):
        if v and v.get("fatti"):
            latest_verified = v
            break

    by_latest = {
        ind["nome"]: ind for ind in (latest_verified or {}).get("indicatori") or []
    }
    out = []
    for nome in thesis_inds:
        chosen = by_latest.get(nome)
        if chosen and chosen.get("stato") != "non_citato" and chosen.get("citazione"):
            out.append(dict(chosen))
            continue
        found = None
        for qmeta, v in reversed(quarters_chron):
            if not v:
                continue
            for ind in v.get("indicatori") or []:
                if (
                    ind["nome"] == nome
                    and ind.get("stato") != "non_citato"
                    and ind.get("citazione")
                ):
                    found = dict(ind)
                    found["testo"] = (
                        f"{(ind.get('testo') or '').rstrip('.')} "
                        f"(rilevato in {qmeta.get('label')})."
                    )
                    break
            if found:
                break
        out.append(found or {
            "nome": nome,
            "stato": "non_citato",
            "testo": "Non citato negli articoli dei trimestri disponibili.",
            "citazione": None,
            "content_id": None,
        })
    return out


def tag_news_indicators(
    ticker: str,
    tesi: dict,
    company: Optional[dict],
) -> Dict[str, str]:
    """One Gemini call over recent headlines → content_id → indicator nome."""
    if not company:
        return {}
    headlines = []
    for st in company.get("stories") or []:
        if (st.get("pub_local") or "") < NEWS_FROM:
            continue
        headlines.append({
            "content_id": st["content_id"],
            "titolo": st.get("titolo") or "",
        })
    if not headlines:
        return {}
    # Cap to keep prompt small
    headlines = headlines[:40]
    try:
        raw = call_gemini(news_indicators_prompt(tesi, headlines), NEWS_IND_SCHEMA)
    except Exception as e:
        print(f"  news-indicator Gemini failed for {ticker}: {e}", file=sys.stderr)
        return {}
    allowed = set(tesi.get("indicatori") or [])
    out: Dict[str, str] = {}
    for tag in raw.get("tags") or []:
        cid = (tag.get("content_id") or "").strip()
        nome = (tag.get("nome") or "").strip()
        if cid and nome in allowed:
            out[cid] = nome
    return out


def decision_sources(base: str, peso: Optional[float], esito_testi: List[str], rollup: dict) -> str:
    parts = [base, news_rollup_text(rollup), *esito_testi]
    if peso is not None:
        parts.append(f"{peso}\n{str(peso).replace('.', ',')}")
    return "\n".join(p for p in parts if p)


def run_decision_gemini(
    ticker: str,
    tesi: dict,
    contesto: str,
    peso: Optional[float],
    esito: dict,
    indicatori: List[dict],
    rollup: dict,
    azioni_ok: List[str],
    src_base: str,
    debug: Dict[str, Any],
) -> dict:
    esito_testi = [esito.get("sintesi") or "", esito.get("evoluzione") or ""]
    esito_testi += [i.get("testo") or "" for i in indicatori]
    sources = decision_sources(src_base, peso, esito_testi, rollup)

    def ask(retry: str = "") -> Tuple[dict, List[str]]:
        raw = call_gemini(
            decision_prompt(ticker, tesi, contesto, peso, esito, indicatori, rollup, azioni_ok, retry),
            DEC_SCHEMA,
        )
        return verify_decision(raw, sources, contesto, azioni_ok, rollup)

    print(f"  decision Gemini (risultati + {rollup['n']} notizie)…", flush=True)
    dec, fail = ask()
    debug["attempts"]["decisione"] = [{"failures": fail}]
    if fail:
        dec2, fail2 = ask(
            "\nTENTATIVO PRECEDENTE FALLITO:\n- " + "\n- ".join(fail[:10])
            + "\nUsa solo numeri presenti sopra.\n"
        )
        debug["attempts"]["decisione"].append({"failures": fail2})
        if len(fail2) <= len(fail):
            dec = dec2
    return dec


def process_ticker(
    ticker: str,
    demo: dict,
    weights: Dict[str, float],
    stlam_prices: Optional[Tuple[List[str], List[float]]],
) -> dict:
    azienda = demo["aziende"][ticker]
    tesi = azienda["tesi"]
    slug = DEMO_COMPANIES.get(ticker)
    company = load_company(slug) if slug else None
    portafoglio_tickers = {p["ticker"] for p in demo["portafoglio"]}
    contesto = "portafoglio" if ticker in portafoglio_tickers else "watchlist"
    azioni_ok = (
        ["mantenere", "aggiungere", "ridurre", "vendere"]
        if contesto == "portafoglio"
        else ["valutare_ingresso", "attendere", "evitare"]
    )
    peso = weights.get(ticker) if contesto == "portafoglio" else None

    debug: Dict[str, Any] = {
        "candidate_ids": {},
        "attempts": {},
        "checks": {},
        "dropped": {},
    }

    candidates = collect_candidates(ticker, company)
    debug["candidate_ids"] = {
        qid: [c["content_id"] for c in items] for qid, items in candidates.items()
    }

    # Fetch all candidate bodies in one BQ call
    all_ids = []
    for items in candidates.values():
        for c in items:
            all_ids.append(c["content_id"])
    articles_by_id = fetch_articles(all_ids) if all_ids else {}

    # Price series for reaction
    price_days: List[str] = []
    price_closes: List[float] = []
    if company and company.get("prices"):
        price_days = list(company["prices"]["d"])
        price_closes = list(company["prices"]["close"])
    elif ticker == "STLAM" and stlam_prices:
        price_days, price_closes = stlam_prices

    earnings: List[dict] = []
    verified_list: List[Tuple[dict, Optional[dict]]] = []
    prev_facts: List[dict] = []
    total_dropped = 0
    source_blob_parts: List[str] = []

    for q in QUARTERS:
        qid = q["id"]
        cands = candidates.get(qid) or []
        arts = []
        for c in cands:
            a = articles_by_id.get(c["content_id"])
            if not a:
                continue
            # Enrich pub_local
            a = dict(a)
            a["pub_local"] = c.get("pub_local") or (a.get("data_pubblicazione") or "").replace(" ", "T")
            arts.append(a)
        # Prefer longest body among fetched
        arts.sort(key=lambda a: (-len(a.get("body") or ""), a.get("pub_local") or ""))
        arts = arts[:2]

        if not arts:
            entry = mancante_quarter(q)
            earnings.append(entry)
            verified_list.append((q, None))
            debug["attempts"][qid] = []
            debug["checks"][qid] = {"reason": "no_candidates"}
            continue

        print(f"  {qid}: Gemini on {len(arts)} article(s)…", flush=True)
        cleaned, attempts, drops = run_quarter_gemini(tesi, q, arts, prev_facts)
        debug["attempts"][qid] = [
            {"failures": a.get("failures"), "drops": a.get("drops")} for a in attempts
        ]
        drop_n = (
            drops.get("fatti", 0)
            + drops.get("metriche", 0)
            + drops.get("indicatori_to_non_citato", 0)
            + len(drops.get("fields") or [])
        )
        # Also count from last attempt
        if attempts:
            last = attempts[-1].get("drops") or {}
            drop_n = (
                last.get("fatti", 0)
                + last.get("metriche", 0)
                + last.get("indicatori_to_non_citato", 0)
                + len(last.get("fields") or [])
            )
        total_dropped += drop_n
        debug["dropped"][qid] = drop_n
        debug["checks"][qid] = {
            "pertinente": cleaned.get("pertinente"),
            "n_fatti": len(cleaned.get("fatti") or []),
        }

        if not cleaned.get("pertinente") or not cleaned.get("fatti"):
            earnings.append(mancante_quarter(q))
            verified_list.append((q, None))
            continue

        by_id = {a["content_id"]: a for a in arts}
        for a in arts:
            source_blob_parts.append(a.get("titolo") or "")
            source_blob_parts.append(a.get("body") or "")

        # Anchor reaction on earliest article that contributed a verified fact
        cited_ids = list(dict.fromkeys(f["content_id"] for f in cleaned["fatti"] if f.get("content_id")))
        anchor_arts = [by_id[c] for c in cited_ids if c in by_id] or arts
        earliest = sorted(
            anchor_arts,
            key=lambda a: a.get("pub_local") or a.get("data_pubblicazione") or "",
        )[0]
        reazione = None
        if price_days:
            reazione = reaction_window(
                earliest.get("pub_local") or earliest.get("data_pubblicazione") or "",
                price_days,
                price_closes,
            )

        data_pub = (earliest.get("pub_local") or earliest.get("data_pubblicazione") or "")[:10]
        entry = {
            "id": q["id"],
            "label": q["label"],
            "periodo": q["periodo"],
            "data": it_date(data_pub),
            "fatti": fatti_with_fonte(cleaned["fatti"], by_id),
            "metriche": cleaned["metriche"],
            "guidance": cleaned["guidance"],
            "cambiato": cleaned["cambiato"],
            "impatto": cleaned["impatto"],
            "reazione": reazione,
            "fonti": [make_fonte(a) for a in anchor_arts],
            # keep internal for aggregation / indicator merge
            "_verified": cleaned,
            "_by_id": {k: {"content_id": k, **v} for k, v in by_id.items()},
        }
        earnings.append(entry)
        verified_list.append((q, cleaned))
        prev_facts = cleaned["fatti"]

    ok_quarters = [(q, v) for q, v in verified_list if v and v.get("fatti")]
    latest_id = ok_quarters[-1][0]["id"] if ok_quarters else None
    n_ok = len(ok_quarters)

    # Aggregation
    insuff = force_insufficiente(
        [{"id": q["id"]} for q, _ in ok_quarters],
        latest_id,
    )

    # Strip internal keys for Gemini view
    earnings_for_prompt = []
    for e in earnings:
        if e.get("mancante"):
            earnings_for_prompt.append(e)
        else:
            earnings_for_prompt.append({
                k: v for k, v in e.items() if not k.startswith("_")
            })

    print(f"  aggregate Gemini ({n_ok} quarters)…", flush=True)
    agg_raw = call_gemini(
        aggregate_prompt(ticker, tesi, earnings_for_prompt),
        AGG_SCHEMA,
    )
    src = "\n".join(source_blob_parts)
    for e in earnings:
        if e.get("mancante"):
            continue
        for f in e.get("fatti") or []:
            src += "\n" + (f.get("testo") or "")
        for m in e.get("metriche") or []:
            src += f"\n{m.get('valore','')} {m.get('confronto','')}"
        if e.get("guidance"):
            src += "\n" + e["guidance"]

    agg, agg_fail = verify_aggregate(agg_raw, src)
    debug["attempts"]["aggregate"] = [{"failures": agg_fail}]
    if agg_fail:
        retry = (
            "\nTENTATIVO PRECEDENTE FALLITO:\n- "
            + "\n- ".join(agg_fail[:10])
            + "\nUsa solo numeri presenti nei trimestri.\n"
        )
        agg_raw2 = call_gemini(
            aggregate_prompt(ticker, tesi, earnings_for_prompt, retry),
            AGG_SCHEMA,
        )
        agg2, agg_fail2 = verify_aggregate(agg_raw2, src)
        debug["attempts"]["aggregate"].append({"failures": agg_fail2})
        agg = agg2

    if insuff:
        agg["stato"] = "insufficiente"
        mancano = []
        missing_labels = [q["label"] for q, v in verified_list if not v]
        if n_ok < 2:
            mancano.append(
                f"Solo {n_ok} trimestre/i con risultati verificati (ne servono almeno 2)."
            )
        if latest_id is None or force_insufficiente(
            [{"id": q["id"]} for q, _ in ok_quarters], latest_id
        ):
            if latest_id is None:
                mancano.append("Nessun risultato trimestrale recente trovato negli articoli MF.")
            elif latest_id not in ("1T26", "2T26"):
                mancano.append(
                    f"Ultimo trimestre disponibile ({latest_id}) anteriore al 1T 2026."
                )
        for lab in missing_labels:
            mancano.append(f"Risultati {lab} non coperti da articoli MF verificati.")
        agg["mancano"] = mancano or ["Copertura insufficiente degli ultimi risultati."]
    else:
        agg["mancano"] = []

    # Build final earnings (strip internals)
    earnings_final = []
    all_by_id: Dict[str, dict] = {}
    for e in earnings:
        if e.get("mancante"):
            earnings_final.append({"id": e["id"], "label": e["label"], "mancante": True})
            continue
        all_by_id.update(e.get("_by_id") or {})
        earnings_final.append({
            "id": e["id"],
            "label": e["label"],
            "periodo": e["periodo"],
            "data": e["data"],
            "fatti": e["fatti"],
            "metriche": e["metriche"],
            "guidance": e["guidance"],
            "cambiato": e["cambiato"],
            "impatto": e["impatto"],
            "reazione": e["reazione"],
            "fonti": e["fonti"],
        })

    # esito.fatti = latest quarter
    latest_entry = None
    for e in reversed(earnings):
        if not e.get("mancante") and e.get("fatti"):
            latest_entry = e
            break

    esito_fatti = (latest_entry or {}).get("fatti") or []
    merged_inds = merge_indicatori_across_quarters(
        list(tesi.get("indicatori") or []),
        verified_list,
    )
    # Attach fonti to indicatori
    esito_inds = []
    for ind in merged_inds:
        cid = ind.get("content_id")
        fonte = None
        if cid and cid in all_by_id:
            fonte = make_fonte(all_by_id[cid])
        elif cid and cid in articles_by_id:
            fonte = make_fonte(articles_by_id[cid])
        esito_inds.append({
            "nome": ind["nome"],
            "stato": ind["stato"],
            "testo": ind["testo"],
            "citazione": ind.get("citazione"),
            "fonte": fonte,
        })

    n_articles = len({cid for items in candidates.values() for cid in [c["content_id"] for c in items]})
    # Count articles actually used
    used = sum(1 for e in earnings_final if not e.get("mancante"))
    metodo = (
        f"Generato da Gemini 2.5 Flash su articoli MF; "
        f"{n_ok} trimestri verificati; citazioni e numeri verificati sul testo degli articoli."
    )

    print(f"  news-indicator tags…", flush=True)
    notizie_indicatori = tag_news_indicators(ticker, tesi, company)
    analisi_notizie = news_rollup(
        (company or {}).get("stories") or [],
        notizie_indicatori,
        list(tesi.get("indicatori") or []),
    )

    decisione = None
    if not insuff:
        decisione = run_decision_gemini(
            ticker, tesi, contesto, peso, agg, esito_inds, analisi_notizie,
            azioni_ok, src, debug,
        )

    result = {
        "tesi_usata": {
            "motivo": tesi.get("motivo") or "",
            "indicatori": list(tesi.get("indicatori") or []),
            "orizzonte": tesi.get("orizzonte") or "",
            "pesoPrevisto": _peso_previsto(tesi),
        },
        "valutazione": None,
        "esito": {
            "stato": agg["stato"],
            "sintesi": agg["sintesi"],
            "fatti": esito_fatti,
            "interpretazioni": agg.get("interpretazioni") or [],
            "indicatori": esito_inds,
            "metodo": metodo,
        },
        "evoluzione": agg.get("evoluzione") or "",
        "earnings": earnings_final,
        "analisi_notizie": analisi_notizie,
        "decisione": decisione,
        "notizie_indicatori": notizie_indicatori,
        "debug": {
            **debug,
            "thesis_fp": thesis_fingerprint(tesi),
            "pipeline_version": PIPELINE_VERSION,
            "n_quarters_ok": n_ok,
            "n_facts_latest": len(esito_fatti),
            "total_dropped": total_dropped,
            "insufficiente_forced": insuff,
            "stlam_prices": bool(stlam_prices) if ticker == "STLAM" else None,
        },
    }
    if decisione is None:
        result["mancano"] = agg.get("mancano") or []
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="Ignore cache")
    ap.add_argument(
        "--only", nargs="+", metavar="TICKER",
        help="Process only these tickers",
    )
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    demo = load_demo()
    overridden = apply_overrides(demo)
    if overridden:
        print(f"Overrides: {', '.join(overridden)}", flush=True)
    weights = portfolio_weights(demo)
    tickers = list(demo["aziende"].keys())
    if args.only:
        only = {t.upper() for t in args.only}
        tickers = [t for t in tickers if t in only]
        missing = only - set(tickers)
        if missing:
            sys.exit(f"Unknown tickers: {sorted(missing)}")

    stlam_prices = None
    if "STLAM" in tickers:
        print("Fetching STLAM prices from BigQuery…", flush=True)
        stlam_prices = fetch_stlam_prices()
        if not stlam_prices:
            print("  STLAM prices unavailable — reazione will be null", flush=True)

    for ticker in tickers:
        tesi = demo["aziende"][ticker]["tesi"]
        fp = thesis_fingerprint(tesi)
        cache_path = OUT_DIR / f"{ticker}.json"
        if cache_path.exists() and not args.force:
            try:
                cached = json.loads(cache_path.read_text())
                cdbg = cached.get("debug") or {}
                if cdbg.get("thesis_fp") == fp and cdbg.get("pipeline_version") == PIPELINE_VERSION:
                    print(f"{ticker}: cache hit ({cache_path.relative_to(ROOT)})", flush=True)
                    continue
                why = "thesis changed" if cdbg.get("thesis_fp") != fp else "pipeline updated"
                print(f"{ticker}: {why} — rebuilding", flush=True)
            except (OSError, json.JSONDecodeError):
                pass

        print(f"{ticker}: building…", flush=True)
        try:
            result = process_ticker(ticker, demo, weights, stlam_prices)
        except Exception as e:
            print(f"{ticker}: FAILED — {e}", file=sys.stderr)
            raise
        cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        d = result["debug"]
        print(
            f"{ticker}: wrote {cache_path.relative_to(ROOT)} "
            f"stato={result['esito']['stato']} quarters={d['n_quarters_ok']} "
            f"facts={d['n_facts_latest']} dropped={d['total_dropped']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
