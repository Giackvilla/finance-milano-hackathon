#!/usr/bin/env python3
"""Deterministic, rule-based MF headline classifier (Italian). Stdlib only."""

from __future__ import annotations

import csv
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Priority (first type in this list that scores a hit wins).
#   takeover > earnings > plan > capital > legal_regulatory > analyst >
#   deal > governance > market_report > other
#
# Why this order (checked against events_all.csv):
# - Takeover (opa/ops/opas/delisting) is rare and decisive; those titles often
#   also cite Consob, dividends or analysts — the bid is the story.
# - Earnings routinely co-occur with broker notes ("dopo i conti, Equita…")
#   and with capital ("utile… alza il dividendo"); the results release is primary.
# - Plan is a distinct scheduled corporate disclosure.
# - Capital next: buyback/bond/dividend without earnings language.
# - Legal/regulatory beats analyst/deal (antitrust clearance of a deal is still
#   a regulatory event for the card).
# - Analyst before deal/governance: a rating change is the identifiable event.
# - Deal before governance: contract/M&A asset news before boardroom chatter.
# - market_report is residual pure-tape / chartist copy with no event keyword.
# ---------------------------------------------------------------------------
PRIORITY: List[str] = [
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

# type -> list of regex strings (applied on accent-stripped lowercase text).
# Word boundaries keep "opa" out of other words; keep this table skimmable.
RULES: Dict[str, List[str]] = {
    "takeover": [
        r"\bopa\b",
        r"\bops\b",
        r"\bopas\b",
        r"offerta pubblica(?:\s+di\s+(?:acquisto|scambio))?",
        r"\bdelisting\b",
        r"\bsqueeze[- ]?out\b",
        r"acquisizione del controllo",
        r"\bcordata\b",
        r"\bscalata\b",
        r"soglia d[' ]opa",
        r"finalizzat[ao] al delisting",
        r"obiettivo (?:il |un )?delisting",
        r"rilancio(?:\s+(?:tutto\s+)?cash|\s+dell[' ]?offerta|\s+per\b|\s+e\b)",
        r"premio (?:dell[' ]?\d|di\s+\d|del\s+\d).{0,40}(?:opa|ops|opas|offerta|delisting)",
        r"(?:opa|ops|opas|offerta).{0,40}premio (?:dell[' ]?\d|di\s+\d|del\s+\d)",
    ],
    "earnings": [
        r"\bconti\b(?!\s+correnti)",
        r"dopo i conti",
        r"post[- ]conti",
        r"stagione dei conti",
        r"\brisultat[io]\b",
        r"\btrimestrale\b",
        r"\bsemestrale\b",
        r"(?:primo|secondo|terzo|quarto)\s+trimestre",
        r"nel semestre",
        r"del semestre",
        r"\bbilancio\b",
        r"\butile\b(?!\s+per\b)",
        r"\butili\b",
        r"allarme utili",
        r"\bperdita\b",
        r"\bricavi\b",
        r"\bfatturato\b",
        r"\bebitda\b",
        r"\bmargin[ie]\b",
        r"\bguidance\b",
        r"\boutlook\b",
        r"conferma(?:no)? i target(?:\s+20\d{2})?",
        r"alza(?:no)? le stime",
        r"taglia(?:no)? le stime",
        r"abbassa(?:no)? le stime",
        r"ritira(?:no)? (?:gli |l[' ]?)outlook",
        r"chiude il semestre",
        r"oltre le attese",
        r"sotto le attese",
        r"batte (?:le attese|il consenso)",
        r"delude (?:le attese|il consenso)",
        r"sopra il consenso",
        r"sotto il consenso",
    ],
    "plan": [
        r"piano industriale",
        r"piano strategico",
        r"business plan",
        r"capital markets day",
        r"\bcmd\b",
        r"piano al 20(?:2[4-9]|3[0-5])",
        r"target al 20(?:2[4-9]|3[0-5])",
        r"obiettivi al 20(?:2[4-9]|3[0-5])",
    ],
    "capital": [
        r"\bdividendo\b",
        r"\bdividendi\b",
        r"\bcedola\b",
        r"\bcedole\b",
        r"\bbuyback\b",
        r"riacquisto (?:di )?azioni",
        r"aumento di capitale",
        r"\bobbligazioni?\b",
        r"\bbond\b",
        r"green bond",
        r"rating del debito",
        r"rating (?:di |sul )?debito",
        r"azioni (?:proprie|proprie\b)",
        r"acquista .{0,30}azioni proprie",
        r"riacquisto .{0,40}(?:azioni|titoli) proprie",
        r"(?:moody'?s|s&p|standard & poor|fitch).{0,40}(?:rating|outlook|prospettive|investment grade|bbb|bb\+|alza|taglia|conferma)",
        r"(?:rating|outlook|prospettive|investment grade|bbb).{0,40}(?:moody'?s|s&p|standard & poor|fitch)",
        r"fitch (?:alza|taglia|conferma|rating)",
        r"rating (?:bbb|bb\+|bb-|bb\b|a\+|a-|aa|aaa)",
        r"prospettive sul rating",
        r"investment grade",
        r"\bcoupon\b",
        r"ex[- ]?dividend",
        r"stacco (?:della |del |delle )?cedola",
        r"data stacco",
        r"azioni gratuite",
        r"in pagamento il \d",
    ],
    "legal_regulatory": [
        r"\bindagine\b",
        r"\binchiesta\b",
        r"\bprocura\b",
        r"\bantitrust\b",
        r"\bconsob\b",
        r"\bmulta\b",
        r"\bsanzion[ei]\b",
        r"golden power",
        r"\bagcom\b",
        r"\barera\b",
        r"\btribunale\b",
        r"\bcausa\b(?!\s+di\s+borsa)",
        r"procedura d[' ]infrazione",
        r"via libera (?:di |dell[' ]?)?(?:bruxelles|ue|antitrust|consob)",
        r"ok (?:di |dell[' ]?)?(?:bruxelles|ue|antitrust|consob)",
        r"\bbruxelles\b.{0,50}(?:antitrust|infrazione|multa|condiz|fusione|opa|ops)",
        r"(?:antitrust|infrazione|multa|golden power).{0,50}\bbruxelles\b",
        r"\bue\b.{0,40}(?:multa|infrazione|antitrust|procedimento)",
    ],
    "analyst": [
        r"gli analisti",
        r"\banalisti\b",
        r"target price",
        r"prezzo obiettivo",
        r"alza(?:no)? (?:il |i )?target",
        r"taglia(?:no)? (?:il |i )?target",
        r"target a \d",
        r"(?:taglia|alza|conferma|abbassa|tagliato|alzato)\s+(?:il |un |il suo )?rating",
        r"rating (?:a |ad |di |su |sul |sulla |buy|hold|sell|neutral|outperform|underperform)",
        r"\bgiudizio\b",
        r"\bpromuove\b",
        r"(?:analist\w*|rating|giudizio|broker).{0,30}\bboccia\b",
        r"\bboccia\b.{0,30}(?:rating|giudizio|target|titolo)",
        r"\boutperform\b",
        r"\bunderperform\b",
        r"\bneutral\b",
        r"\boverweight\b",
        r"\bunderweight\b",
        r"strong buy",
        r"(?:giudizio|rating|conferma(?:no)?(?:\s+il)?)\s+(?:buy|hold|sell|neutral)",
        r"\bupside\b",
        r"potenziale di rialzo",
        r"mediobanca research",
        # broker houses only with nearby recommendation language
        r"(?:equita|kepler|intermonte|jefferies|goldman|morgan stanley|barclays|"
        r"\bciti\b|jp\s*morgan|jpmorgan|bernstein|deutsche bank|banca akros|\bakros\b|"
        r"berenberg|\bubs\b|\bhsbc\b|\bbofa\b|bank of america|\bkbw\b|\balantra\b)"
        r".{0,55}(?:target|rating|giudizio|promuove|boccia|buy|hold|sell|neutral|"
        r"outperform|underperform|upside|stime|analist|raccomand|overweight|underweight)",
        r"(?:target|rating|giudizio|promuove|boccia|buy|hold|sell|neutral|"
        r"outperform|upside|stime|analist|raccomand|overweight|alza|taglia)"
        r".{0,55}(?:equita|kepler|intermonte|jefferies|goldman|morgan stanley|barclays|"
        r"\bciti\b|jp\s*morgan|jpmorgan|bernstein|deutsche bank|banca akros|\bakros\b|"
        r"berenberg|\bubs\b|\bhsbc\b|\bbofa\b|bank of america|\bkbw\b|\balantra\b)",
        r"per (?:equita|kepler|intermonte|jefferies|goldman|barclays|citi|"
        r"berenberg|ubs|hsbc|bofa|kbw|alantra|akros|jp\s*morgan|morgan stanley)",
        r"secondo (?:equita|kepler|intermonte|jefferies|goldman|barclays|citi|"
        r"berenberg|ubs|hsbc|bofa|kbw|alantra|akros|gli analisti)",
    ],
    "deal": [
        r"\bcontratt[oi]\b",
        r"\bcommess[ae]\b",
        r"\bordini\b",
        r"maxi[- ]?(?:contratto|commessa|ordine)",
        r"nuovo ordine",
        r"\baccord[oi]\b",
        r"\bpartnership\b",
        r"\balleanza\b",
        r"joint venture",
        r"\bacquisizione\b(?!\s+del\s+controllo)",
        r"\bacquisizioni\b",
        r"\bcessione\b",
        r"\bcessioni\b",
        r"\brileva\b",
        r"\brilevato\b",
        r"\bcompra\b",
        r"\bacquista\b",
        r"\bperfeziona\b.{0,40}(?:acquisiz|acquisto|rilev)",
        r"cede (?:una |il |la |lo |i |le |ad?\s+\w+ )?(?:quota|asset|ram[oi]|partecipazione|societ|\d)",
        r"vende (?:una |il |la |ancora )?(?:quota|asset|partecipazione|\d)",
        r"\bfusione\b(?!\s+nucleare)",
        r"\bincorpora\b",
        r"\brisiko\b",
        r"si aggiudica",
        r"\bm&a\b",
    ],
    "governance": [
        r"\bcda\b",
        r"consiglio di amministrazione",
        r"consiglio di sorveglianza",
        r"\bceo\b",
        r"amministratore delegato",
        r"(?<![a-z])\bad\b(?=\s+(?:di|del|della|profumo|puliti|folgero|descalzi|orcel|lovaglio|battaini|cingolani|palermo|verdesca|manzana))",
        r"\bnomina\b.{0,40}(?:ceo|(?<![a-z])ad\b|presidente|consiglier|cda|amministratore|vertice|board)",
        r"(?:ceo|(?<![a-z])ad\b|presidente|consiglier|cda|amministratore|vertice|board).{0,40}\bnomina\b",
        r"\bnominat[oi]\b",
        r"\bdimissioni\b",
        r"\bdimette\b",
        r"\bdimettono\b",
        r"\bassemblea\b",
        r"\bpatto\b",
        r"\bliste?\b.{0,30}(?:cda|assemblea|soci|azionist|mps|banco|generali)",
        r"(?:presenta(?:no)?|deposita(?:no)?) le liste",
        r"\bpresidente\b",
        r"\bsuccessione\b",
        r"sostituzione di",
        r"vende azioni",
        r"vendita di azioni",
        r"vendite di azioni",
        r"rinnovo dei vertici",
        r"nuovo (?:ad|ceo|presidente|amministratore)",
        r"\bconsiglier[ie]\b",
        r"\bboard\b",
        r"per i soci",
        r"ai soci",
        r"dei soci(?!\s+di\b)",
    ],
    "market_report": [
        r"borse oggi",
        r"la diretta dai mercati",
        r"cos[' ]e successo oggi sui mercati",
        r"caso di borsa",
        r"titolo del giorno",
        r"analisi tecnica",
        r"vola in borsa",
        r"balza in borsa",
        r"corre in borsa",
        r"tracolla in borsa",
        r"crolla in borsa",
        r"affonda in borsa",
        r"cade in borsa",
        r"scivola in borsa",
        r"sprofonda in borsa",
        r"brilla in borsa",
        r"festeggia in borsa",
        r"decolla in borsa",
        r"volano in borsa",
        r"titolo (?:in )?(?:rally|volata|tonfo|crollo|rialzo|ribasso|calo)",
        r"il titolo (?:crolla|balza|vola|corre|affonda|scivola|cade|tracolla|sprofonda|rimbalza)",
        r"(?:crolla|balza|vola|affonda|scivola|tracolla)\s+(?:del|di)\s+\d",
        r"in rally",
        # bare "piazza affari" is too common in event titles; require tape cue
        r"piazza affari.{0,40}(?:chiude|rialzo|ribasso|calo|rosso|verde|rally|tonfo|croll)",
        r"(?:chiude|rialzo|ribasso|calo|rosso|verde|rally|tonfo|croll|vola|balza).{0,40}piazza affari",
        r"a piazza affari",
        r"trend di breve",
        r"trend primario",
        r"\bpullback\b",
        r"\bbreakout\b",
        r"allunga al rialzo",
        r"strappo rialzista",
        r"rimbalzo tecnico",
        r"consolidamento sui massimi",
        r"a un passo dai massimi",
        r"sui massimi",
        r"sui minimi",
        r"il titolo prova",
        r"il titolo allunga",
        r"il titolo tiene",
        r"fase di consolidamento",
        r"nuovo allungo",
        r"tenuta di \d",
        r"test (?:in area|a|di|del|iniziale)\s+\d",
        r"fallito (?:il |l[' ]?)?(?:iniziale )?test",
        r"conferma sopra \d",
        r"prossima resistenza",
        r"prossimo supporto",
        r"resistenza in area",
        r"supporto (?:a|in area)",
        r"chiude in (?:calo|rialzo|ribasso|rosso|verde|parita)",
        r"maglia (?:rosa|nera)",
        r"sospes[oa] per eccesso",
        r"sospes[oa] (?:all[' ]?egm|a piazza|in borsa)",
    ],
}

# Movement verbs that need price context (%, borsa, titolo, piazza affari, seduta).
_MOVE_VERBS_AMBIG = (
    r"(?:perde|cede|guadagna|sale|scatta|balza|corre|vola|brilla|festeggia|"
    r"tracolla|crolla|affonda|cade|scivola|sprofonda|decolla|rimbalza)"
)
_PRICE_CTX = (
    r"(?:borsa|titolo|piazza affari|seduta|egm|star|ftse|mib|listino|"
    r"rally|volata|tonfo)"
)

_PCT_RE = re.compile(r"[(\[]?\s*[+\-−–]?\s*\d+(?:[.,]\d+)?\s*%\s*[)\]]?")
_METRIC_BEFORE_PCT = re.compile(
    r"(?:fatturato|ricavi|ricavo|utile|utili|ebitda|margini|perdita|"
    r"giro d[' ]affari).{0,60}$",
    re.I,
)

_HEADLINE_MOVE_PATTERNS = [
    r"(?:balza|vola|corre|crolla|affonda|scivola|tracolla|perde|guadagna|cede|sale)"
    r"\s+(?:del|di|dell[' ]?|l[' ]?)\s*\d+(?:[.,]\d+)?\s*%",
    r"guadagna il \d+(?:[.,]\d+)?\s*%",
    r"chiude in (?:calo|rialzo|ribasso|rosso|verde|parita)",
    r"in (?:netto )?(?:calo|rialzo|ribasso)(?:\s+del|\s+dello|\s*\()",
    r"\bin rosso\b",
    r"\bin verde\b",
    r"maglia (?:rosa|nera)",
    r"sospes[oa] per eccesso",
    r"titolo in (?:rally|volata|tonfo|crollo|rialzo|ribasso|calo|rosso|verde)",
    r"in rally",
    r"allunga al rialzo",
    r"il titolo allunga",
    r"sale in controtendenza",
    r"(?:vola|balza|corre|sale|scatta|decolla|brilla|festeggia|tracolla|crolla|"
    r"affonda|cade|scivola|sprofonda)\s+(?:in\s+)?(?:borsa|piazza affari)",
    r"(?:in\s+)?borsa\s*[(\[]?\s*[+\-−–]?\s*\d",
    rf"{_MOVE_VERBS_AMBIG}.{{0,40}}{_PRICE_CTX}",
    rf"{_PRICE_CTX}.{{0,40}}{_MOVE_VERBS_AMBIG}",
    r"il titolo (?:crolla|balza|vola|corre|affonda|scivola|cade|tracolla|sprofonda|rimbalza|risale)",
    r"titolo (?:risale|cede|perde|guadagna)\b",
    r"rally (?:sull[' ]?egm|a piazza|in borsa|del titolo)",
    r"tonfo (?:di|per)\b",
    r"crollo (?:di|per)\b",
    r"caso di borsa",
    r"borse oggi",
]

_DIV_DATE = re.compile(
    r"(?:ex[- ]?dividend|stacco|data stacco|stacca(?:no)? (?:la )?cedola|"
    r"cedola (?:il|dal)\s+\d|dividendo (?:il|dal)\s+\d|"
    r"in pagamento (?:il|dal)\s+\d)",
    re.I,
)
_ASSEMBLEA = re.compile(r"\bassemblea\b", re.I)

_COMPILED: Dict[str, List[Tuple[str, re.Pattern]]] = {
    t: [(pat, re.compile(pat, re.I)) for pat in pats] for t, pats in RULES.items()
}
_MOVE_COMPILED = [re.compile(p, re.I) for p in _HEADLINE_MOVE_PATTERNS]


def normalise(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _collect_hits(text: str) -> List[Tuple[str, str]]:
    hits: List[Tuple[str, str]] = []
    for ntype, patterns in _COMPILED.items():
        for pat, cre in patterns:
            if not cre.search(text):
                continue
            hits.append((ntype, pat))
    return hits


def _pick_type(hits: List[Tuple[str, str]]) -> str:
    if not hits:
        return "other"
    present = {h[0] for h in hits}
    # Dividend payment / buyback without real P&L language → capital over
    # a lone "trimestrale"/"semestre" earnings hit.
    soft_earn = {
        r"\btrimestrale\b",
        r"\bsemestrale\b",
        r"(?:primo|secondo|terzo|quarto)\s+trimestre",
        r"nel semestre",
        r"del semestre",
    }
    earn_pats = {h[1] for h in hits if h[0] == "earnings"}
    cap_hard = {
        h[1]
        for h in hits
        if h[0] == "capital"
        and any(
            k in h[1]
            for k in (
                "dividendo",
                "cedola",
                "buyback",
                "azioni proprie",
                "aumento di capitale",
                "obbligaz",
                "bond",
                "moody",
                "s&p",
                "fitch",
                "investment grade",
                "rating (?:bbb",
                "prospettive sul rating",
                "in pagamento",
            )
        )
    }
    if cap_hard and earn_pats and earn_pats <= soft_earn:
        present.discard("earnings")
    for t in PRIORITY:
        if t in present:
            return t
    return "other"


def _scheduled(news_type: str, text: str) -> Optional[bool]:
    if news_type in ("market_report", "other"):
        return None
    if news_type in ("earnings", "plan"):
        return True
    if news_type == "capital":
        return bool(_DIV_DATE.search(text))
    if news_type == "governance":
        return bool(_ASSEMBLEA.search(text))
    if news_type in ("takeover", "deal", "legal_regulatory", "analyst"):
        return False
    return None


def _pct_is_price_move(text: str) -> bool:
    """Signed % is a tape move unless it annotates a P&L/revenue metric."""
    for m in _PCT_RE.finditer(text):
        frag = m.group(0)
        if not re.search(r"[+\-−–(]", frag):
            continue
        before = text[max(0, m.start() - 60) : m.start()]
        if _METRIC_BEFORE_PCT.search(before):
            continue
        return True
    return False


def _headline_reports_move(text: str) -> bool:
    """True if the title describes the stock's own price move."""
    if _pct_is_price_move(text):
        return True
    deal_cede = bool(
        re.search(r"cede (?:una |il |la )?(?:quota|partecipazione|asset|ram)", text)
    )
    has_price_cue = bool(
        re.search(
            r"[+\-−–]\s*\d+(?:[.,]\d+)?\s*%|\bborsa\b|\btitolo\b|piazza affari|\bseduta\b",
            text,
        )
    )
    for cre in _MOVE_COMPILED:
        m = cre.search(text)
        if not m:
            continue
        frag = m.group(0)
        if deal_cede and not has_price_cue and re.search(r"\b(?:cede|perde)\b", frag):
            continue
        return True
    return False


def classify(titolo: str, body: str = "") -> dict:
    """Classify an MF headline (and optional body snippet)."""
    title_n = normalise(titolo)
    hits = _collect_hits(title_n)
    news_type = _pick_type(hits)

    if body and news_type in ("other", "market_report"):
        body_n = normalise(body)[:600]
        body_hits = _collect_hits(body_n)
        event_hits = [h for h in body_hits if h[0] != "market_report"]
        if event_hits:
            upgraded = _pick_type(event_hits)
            if upgraded != "other":
                hits = hits + event_hits
                news_type = upgraded

    seen = set()
    matched: List[Tuple[str, str]] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            matched.append(h)

    return {
        "news_type": news_type,
        "scheduled": _scheduled(news_type, title_n),
        "headline_reports_move": _headline_reports_move(title_n),
        "matched": matched,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_batch(csv_path: Path) -> None:
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    by_type: Dict[str, List[str]] = {t: [] for t in PRIORITY}
    move_count = 0
    for row in rows:
        titolo = row.get("titolo") or ""
        out = classify(titolo)
        by_type.setdefault(out["news_type"], []).append(titolo)
        if out["headline_reports_move"]:
            move_count += 1

    print(f"n={len(rows)}")
    print("news_type counts:")
    for t in PRIORITY:
        print(f"  {t:20s} {len(by_type.get(t, []))}")
    print(f"headline_reports_move: {move_count}")

    random.seed(7)
    print("\nexamples (seed=7, up to 12 per type):")
    for t in PRIORITY:
        titles = by_type.get(t, [])
        if not titles:
            print(f"\n[{t}] (none)")
            continue
        sample = titles if len(titles) <= 12 else random.sample(titles, 12)
        print(f"\n[{t}] n={len(titles)}")
        for s in sample:
            print(f"  - {s}")


def main(argv: List[str]) -> None:
    if len(argv) >= 2:
        title = " ".join(argv[1:])
        print(classify(title))
        return
    csv_path = _repo_root() / "data" / "events_all.csv"
    if not csv_path.exists():
        print(f"missing {csv_path}", file=sys.stderr)
        sys.exit(1)
    run_batch(csv_path)


if __name__ == "__main__":
    main(sys.argv)
