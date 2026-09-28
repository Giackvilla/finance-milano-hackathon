#!/usr/bin/env python3
"""Load one MF catalog company and check a thesis against its article titles.

The Gemini thesis pipeline only knows the ten demo names. A holding added from
the catalog (for example 1BSP) still has prices and stories in web/public/data.
This module reads that file and compares the thesis words with the titles.
It does not call BigQuery or Gemini, and it does not invent figures that are
not already in the title or in the stored price reaction.

Stdlib, Python 3.9.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

import build_dashboard_data as dash

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "web" / "public" / "data"
NEWS_FROM = dash.NEWS_FROM

STOP = {
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra", "il", "lo", "la",
    "i", "gli", "le", "un", "uno", "una", "e", "o", "ma", "se", "che", "non",
    "piu", "anche", "come", "questo", "questa", "quello", "quella", "dei",
    "degli", "delle", "del", "della", "dello", "dal", "dallo", "dalla", "dai",
    "al", "allo", "alla", "ai", "agli", "alle", "nel", "nello", "nella", "nei",
    "negli", "nelle", "sul", "sullo", "sulla", "sui", "sugli", "sulle", "dell",
    "nell", "all", "dall", "sull", "sono", "sia", "suo", "sua", "suoi", "sue",
    "mio", "mia", "loro", "cui", "dopo", "prima", "quando", "dove", "cosa",
    "chi", "gia", "solo", "the", "and", "for",
}

_INDEX: Optional[Dict[str, str]] = None
_DAYS: Optional[List[str]] = None
_META: Optional[Dict[str, dict]] = None


def _strip(s: str) -> str:
    n = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in n if not unicodedata.combining(c))


def tokens(text: str) -> List[str]:
    out: List[str] = []
    for raw in re.findall(r"[A-Za-zÀ-ÿ0-9]+", text or ""):
        base = _strip(raw)
        if base in STOP:
            continue
        if len(base) >= 3 or (len(base) == 2 and raw.isupper()):
            out.append(base)
    return out


def _index() -> Dict[str, str]:
    global _INDEX
    if _INDEX is None:
        rows = json.loads((BUNDLE / "companies.json").read_text())
        _INDEX = {str(r["cod_azione"]).upper(): r["slug"] for r in rows if r.get("cod_azione")}
    return _INDEX


def _days() -> List[str]:
    global _DAYS
    if _DAYS is None:
        _DAYS = json.loads((BUNDLE / "companies" / "enel.json").read_text())["prices"]["d"]
    return _DAYS


def _meta() -> Dict[str, dict]:
    global _META
    if _META is None:
        _META = {m["status"]: m for m in json.loads((BUNDLE / "status_meta.json").read_text())["statuses"]}
    return _META


def load_company(ticker: str) -> Optional[dict]:
    slug = _index().get((ticker or "").upper())
    if not slug:
        return None
    path = BUNDLE / "companies" / f"{slug}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def aligned_closes(prices: dict, days: List[str]) -> List[Optional[float]]:
    """Closes on the desk calendar. Sessions before the first print stay empty."""
    by_d = dict(zip(prices.get("d") or [], prices.get("close") or []))
    out: List[Optional[float]] = []
    started = False
    last: Optional[float] = None
    for d in days:
        c = by_d.get(d)
        if c is not None:
            started = True
            last = c
        out.append(last if started else None)
    return out


def _fonte(st: dict, item: dict) -> dict:
    return {
        "titolo": st["titolo"],
        "url": item["url"],
        "data": dash.it_date(st["pub_local"]),
    }


def _hits(words: List[str], title_words: List[str]) -> int:
    if not words:
        return 0
    bag = set(title_words)
    return sum(1 for w in set(words) if w in bag)


def _reaction(stories: List[dict]) -> str:
    """a_favore / contro / neutro from unusual moves after publication."""
    voted = []
    for st in stories:
        if st["status"] not in ("REACTED", "DELAYED"):
            continue
        move = (st.get("peak") or st.get("largest") or {}).get("move_pct")
        if move is None or move == 0:
            continue
        voted.append(move)
    if not voted:
        return "neutro"
    up = sum(1 for m in voted if m > 0)
    down = len(voted) - up
    if up > down:
        return "a_favore"
    if down > up:
        return "contro"
    return "neutro"


def _overall(votes: List[str]) -> str:
    cited = [v for v in votes if v != "non_citato"]
    if not cited:
        return "insufficiente"
    fav = sum(1 for v in cited if v == "a_favore")
    con = sum(1 for v in cited if v == "contro")
    if fav and not con:
        return "rafforzata"
    if con and not fav:
        return "indebolita"
    return "invariata"


def _join_titles(stories: List[dict], n: int = 3) -> str:
    bits = []
    for st in stories[:n]:
        bits.append(f"«{st['titolo']}» ({dash.it_date(st['pub_local'])})")
    if len(stories) > n:
        bits.append(f"altri {len(stories) - n}")
    return ", ".join(bits)


def read_company(ticker: str, body: Optional[dict] = None, contesto: str = "portafoglio") -> Optional[dict]:
    company = load_company(ticker)
    if not company or not company.get("prices", {}).get("close"):
        return None
    ticker = ticker.upper()
    prices = company["prices"]
    days = _days()
    serie = aligned_closes(prices, days)
    last_close = prices["close"][-1]
    last_move = prices["move_pct"][-1] if prices.get("move_pct") else 0.0
    meta = _meta()
    stories = [
        st for st in company.get("stories") or []
        if (st.get("pub_local") or "") >= NEWS_FROM
    ]
    stories.sort(key=lambda st: st.get("pub_local") or "", reverse=True)

    body = body or {}
    motivo = str(body.get("motivo") or "")
    indicatori = [str(x).strip() for x in (body.get("indicatori") or []) if str(x).strip()][:3]
    orizzonte = str(body.get("orizzonte") or "")
    peso = body.get("pesoPrevisto", None)
    if peso == "":
        peso = None
    elif peso is not None:
        try:
            peso = float(peso)
        except (TypeError, ValueError):
            peso = None

    motivo_words = tokens(motivo)
    prepared = []
    for st in stories:
        item = dash.news_item(st, ticker, meta, None, None)
        prepared.append({"st": st, "item": item, "words": tokens(st.get("titolo") or "")})

    ind_rows = []
    for nome in indicatori:
        words = tokens(nome)
        matched = [p for p in prepared if _hits(words, p["words"])]
        if not matched:
            ind_rows.append({
                "nome": nome,
                "stato": "non_citato",
                "testo": "Nessun titolo MF recente contiene le parole di questo indicatore.",
                "citazione": None,
                "fonte": None,
                "_matched": [],
            })
            continue
        vote = _reaction([p["st"] for p in matched])
        top = matched[0]
        if vote == "a_favore":
            testo = f"Il titolo del {dash.it_date(top['st']['pub_local'])} cita l’indicatore e la reazione di prezzo successiva è al rialzo."
        elif vote == "contro":
            testo = f"Il titolo del {dash.it_date(top['st']['pub_local'])} cita l’indicatore e la reazione di prezzo successiva è al ribasso."
        else:
            testo = f"Il titolo del {dash.it_date(top['st']['pub_local'])} cita l’indicatore. Intorno all’articolo non c’è una seduta anomala successiva alla pubblicazione."
        ind_rows.append({
            "nome": nome,
            "stato": vote,
            "testo": testo,
            "citazione": top["st"]["titolo"],
            "fonte": _fonte(top["st"], top["item"]),
            "_matched": matched,
        })

    cited_inds = [r for r in ind_rows if r["stato"] != "non_citato"]
    if cited_inds:
        votes = [r["stato"] for r in ind_rows]
        matched_stories = []
        seen = set()
        for r in cited_inds:
            for p in r["_matched"]:
                if p["st"]["content_id"] not in seen:
                    seen.add(p["st"]["content_id"])
                    matched_stories.append(p["st"])
    else:
        matched_prep = [p for p in prepared if _hits(motivo_words, p["words"])]
        matched_stories = [p["st"] for p in matched_prep]
        votes = [_reaction(matched_stories)] if matched_stories else []

    stato = _overall(votes)
    nome = company.get("des_azione") or ticker

    if not prepared:
        sintesi = f"Nel dataset non ci sono articoli MF su {nome} dal {dash.it_date(NEWS_FROM)}. La tesi non si può confrontare con una notizia."
    elif stato == "insufficiente":
        sintesi = (
            f"{len(prepared)} {'articolo' if len(prepared) == 1 else 'articoli'} MF su {nome} "
            f"dal {dash.it_date(NEWS_FROM)}. Nessun titolo contiene le parole della tesi, "
            f"quindi non si può dire se sia rafforzata o indebolita. "
            f"Articoli controllati: {_join_titles([p['st'] for p in prepared])}."
        )
    elif stato == "rafforzata":
        sintesi = (
            f"La tesi risulta rafforzata sui titoli MF: gli articoli che la citano "
            f"hanno avuto una reazione di prezzo al rialzo. {_join_titles(matched_stories)}."
        )
    elif stato == "indebolita":
        sintesi = (
            f"La tesi risulta indebolita sui titoli MF: gli articoli che la citano "
            f"hanno avuto una reazione di prezzo al ribasso. {_join_titles(matched_stories)}."
        )
    else:
        sintesi = (
            f"Gli articoli citano la tesi, ma senza una seduta anomala dopo la pubblicazione. "
            f"La tesi resta invariata. {_join_titles(matched_stories or [p['st'] for p in prepared])}."
        )

    fact_src = matched_stories or [p["st"] for p in prepared]
    fatti = []
    for st in fact_src[:4]:
        item = next(p["item"] for p in prepared if p["st"]["content_id"] == st["content_id"])
        fatti.append({"testo": st["titolo"], "citazione": None, "fonte": _fonte(st, item)})

    # Tag each story with the indicator whose words appear in the title.
    notizie = []
    for p in prepared:
        item = p["item"]
        best = None
        best_n = 0
        for r in ind_rows:
            n = _hits(tokens(r["nome"]), p["words"])
            if n > best_n:
                best_n = n
                best = r["nome"]
        if best:
            item["indicatore"] = {"ticker": ticker, "nome": best}
        notizie.append(item)

    decisione = None
    mancano = None
    if stato == "insufficiente":
        mancano = [
            "Parole della tesi presenti in almeno un titolo MF",
            "Un indicatore da monitorare che gli articoli possano citare",
        ]
        if not any((st.get("news_type") == "earnings") for st in stories):
            mancano.append("Articoli di risultati trimestrali: nel dataset non ce ne sono per questa azienda")
    else:
        azione = {
            "portafoglio": {"rafforzata": "mantenere", "invariata": "mantenere", "indebolita": "ridurre"},
            "watchlist": {"rafforzata": "valutare_ingresso", "invariata": "attendere", "indebolita": "evitare"},
        }.get(contesto, {}).get(stato, "mantenere")
        if contesto not in ("portafoglio", "watchlist"):
            contesto = "portafoglio"
            azione = {"rafforzata": "mantenere", "invariata": "mantenere", "indebolita": "ridurre"}[stato]
        if stato == "rafforzata":
            motivazione = "Gli articoli che citano la tesi sono stati seguiti da un rialzo anomalo. L’indicazione è di non aumentare solo per questo: il controllo legge i titoli, non un bilancio."
        elif stato == "indebolita":
            motivazione = "Gli articoli che citano la tesi sono stati seguiti da un ribasso anomalo. Conviene chiedersi se il motivo per cui il titolo è in lista regge ancora."
        else:
            motivazione = "Gli articoli citano la tesi, senza una seduta anomala dopo la notizia. Non c’è un elemento nuovo per cambiare la posizione."
        decisione = {
            "contesto": contesto,
            "azione": azione,
            "motivazione": motivazione,
            "aFavore": [st["titolo"] for st in (matched_stories or fact_src)[:3]],
            "rischio": "Il controllo confronta le parole della tesi con i titoli MF. Un numero che sta solo nel corpo dell’articolo non entra nel giudizio.",
            "cambierebbe": "Un articolo di risultati, oppure una seduta anomala dopo una notizia che cita la tesi.",
            "basata_su": ["notizie"],
            "notizie_considerate": len(prepared),
            "notizie_da": dash.it_date(min(st["pub_local"] for st in stories)) if stories else None,
        }

    clean_inds = []
    for r in ind_rows:
        clean_inds.append({k: v for k, v in r.items() if k != "_matched"})

    return {
        "ok": True,
        "ticker": ticker,
        "nome": nome,
        "isin": company.get("isin"),
        "cod_azione": company.get("cod_azione"),
        "prezzo": last_close,
        "mercato": last_move or 0.0,
        "prezzo_fonte": "dataset",
        "serie": serie,
        "notizie": notizie,
        "tesi_usata": {
            "motivo": motivo,
            "indicatori": indicatori,
            "orizzonte": orizzonte,
            "pesoPrevisto": peso,
        },
        "esito": {
            "stato": stato,
            "sintesi": sintesi,
            "fatti": fatti,
            "interpretazioni": [],
            "indicatori": clean_inds,
            "metodo": (
                "Confronto tra le parole della tesi e i titoli degli articoli MF nel dataset, "
                "più la reazione di prezzo già calcolata (seduta anomala: almeno 2 volte "
                "l’oscillazione delle 20 sedute precedenti). I corpi degli articoli non sono "
                "nel bundle, quindi non ci sono citazioni dal testo."
            ),
        },
        "decisione": decisione,
        "mancano": mancano,
        "earnings": [],
        "evoluzione": (
            "Nel dataset non ci sono articoli di risultati trimestrali per questa azienda, "
            "quindi non c’è una serie di trimestri da confrontare con la tesi."
            if not any(st.get("news_type") == "earnings" for st in stories)
            else "I trimestri non sono ricostruiti: il controllo usa i titoli e la reazione di prezzo."
        ),
        "analisi_notizie": {
            "da": dash.it_date(NEWS_FROM),
            "n": len(prepared),
        },
        "valutazione": None,
    }
