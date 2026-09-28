#!/usr/bin/env python3
"""Write web/dashboard/real_data.js from the bundle in web/public/data.

Usage:
    python3 scripts/build_dashboard_data.py

The prototype reads window.DEMO_DATA. real_data.js loads after data.js and
replaces what the pipeline really has: prices, last-session moves, trading
days, company names, and MF stories with their price verdict. Theses,
earnings and decisions stay simulated because nothing produces them yet.
A .js file (not fetch) so the page still works when opened from disk.
Stdlib, Python 3.9.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "web" / "public" / "data"
OUT = ROOT / "web" / "dashboard" / "real_data.js"

# Demo keys are exchange tickers; the bundle is keyed by company slug / COD_AZIONE.
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
CALENDAR_SLUG = "enel"
NEWS_FROM = "2026-08-01"
MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
SEZIONE = {
    "takeover": "Opa e M&A",
    "earnings": "Risultati",
    "plan": "Piano industriale",
    "capital": "Capitale e dividendi",
    "legal_regulatory": "Legale e regole",
    "analyst": "Analisti",
    "deal": "Accordi e commesse",
    "governance": "Governance",
    "market_report": "Mercati",
    "other": "Altro",
}
GROUP_CLS = {"before": "warn", "after": "pos", "none": "neu"}


def load(rel: str):
    return json.loads((BUNDLE / rel).read_text())


def it_num(v: float, nd: int = 1) -> str:
    return f"{v:.{nd}f}".replace(".", ",")


def it_signed(v: float, nd: int = 1) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + it_num(abs(v), nd) + "%"


def it_date(d: str) -> str:
    y, m, dd = d[:10].split("-")
    return f"{int(dd)} {MESI[int(m) - 1]} {y}"


def aligned_closes(prices: dict, days: List[str]) -> List[float]:
    by_d = dict(zip(prices["d"], prices["close"]))
    first = next(c for c in prices["close"] if c is not None)
    out, last = [], first
    for d in days:
        c = by_d.get(d)
        if c is not None:
            last = c
        out.append(last)
    return out


def summary_it(st: dict, meta: dict, detail: Optional[dict]) -> str:
    if detail:
        return detail["verdict"]["text_it"]
    peak, largest = st.get("peak"), st.get("largest")
    if st["status"] == "NO_REACTION" or not peak:
        if largest and largest.get("move_pct") is not None and largest.get("z") is not None:
            return (f"Nessuna seduta anomala intorno all'articolo: la più ampia ha fatto "
                    f"{it_signed(largest['move_pct'])} il {it_date(largest['d'])}, "
                    f"{it_num(abs(largest['z']))} volte l'oscillazione normale.")
        return "Nessuna seduta anomala intorno all'articolo."
    return (f"{meta['explain_it']} Picco: {it_signed(peak['move_pct'])} il {it_date(peak['d'])}, "
            f"{it_num(abs(peak['z']))} volte l'oscillazione normale delle 20 sedute precedenti.")


def news_item(st: dict, ticker: str, meta_by: Dict[str, dict], detail: Optional[dict]) -> dict:
    meta = meta_by[st["status"]]
    peak = st.get("peak") or st.get("largest") or {}
    move, z = peak.get("move_pct"), peak.get("z")
    unusual = st["status"] != "NO_REACTION"
    direction = "flat" if not unusual or not move else ("up" if move > 0 else "down")
    return {
        "id": st["content_id"],
        "data": st["pub_local"][:16],
        "sezione": SEZIONE.get(st.get("news_type") or "other", "Altro"),
        "titolo": st["titolo"],
        "riassunto": summary_it(st, meta, detail),
        "url": (detail or {}).get("article", {}).get("url"),
        "strumenti": [{"ticker": ticker, "sim": 1.0, "dir": direction}],
        "segnale": {"dir": direction, "forza": round(min(1.0, abs(z) / 6), 2) if unusual and z else 0.1},
        "verdetto": {
            "status": st["status"],
            "label": meta["label_it"],
            "cls": GROUP_CLS[meta["group"]],
            "move_pct": move,
            "z": z,
            "d": peak.get("d"),
        },
        "indicatore": None,
    }


def main() -> None:
    manifest = load("manifest.json")
    meta_by = {m["status"]: m for m in load("status_meta.json")["statuses"]}
    detail_ids = {r["content_id"] for r in load("stories.json")}

    days = load(f"companies/{CALENDAR_SLUG}.json")["prices"]["d"]
    aziende, serie, mercato, notizie = {}, {}, {}, []
    for ticker, slug in DEMO_COMPANIES.items():
        c = load(f"companies/{slug}.json")
        p = c["prices"]
        serie[ticker] = aligned_closes(p, days)
        mercato[ticker] = p["move_pct"][-1] or 0.0
        aziende[ticker] = {"nome": c["des_azione"], "prezzo": p["close"][-1],
                           "cod_azione": c["cod_azione"], "isin": c["isin"]}
        for st in c["stories"]:
            if st["pub_local"] < NEWS_FROM:
                continue
            detail = load(f"stories/{st['content_id']}.json") if st["content_id"] in detail_ids else None
            notizie.append(news_item(st, ticker, meta_by, detail))

    demo_ids = {n["id"] for n in notizie}
    for row in load("stories.json"):
        if row["content_id"] in demo_ids:
            continue
        detail = load(f"stories/{row['content_id']}.json")
        v = detail["verdict"]
        st = {
            "content_id": row["content_id"], "titolo": row["titolo"], "pub_local": row["pub_local"],
            "news_type": row["news_type"], "status": row["status"],
            "peak": v.get("peak"), "largest": v.get("largest"),
        }
        notizie.append(news_item(st, row["cod_azione"], meta_by, detail))
    notizie.sort(key=lambda n: n["data"], reverse=True)

    last = manifest["last_price_date"]
    payload = {
        "aggiornamento": it_date(last),
        "giorni": days,
        "aziende": aziende,
        "serie": serie,
        "mercato": mercato,
        "notizie": notizie,
        "etichetta": "Prezzi e notizie MF reali · tesi ed earnings simulati",
        "sottotitolo": (f"Articoli MF Milano Finanza dal {it_date(NEWS_FROM)}, collegati al titolo quando il nome "
                        f"dell'azienda compare nel titolo dell'articolo. Il verdetto confronta l'articolo con il prezzo: "
                        f"una seduta è anomala se si muove almeno 2 volte l'oscillazione normale delle 20 sedute precedenti."),
        "generato": manifest["generated_at"],
    }
    js = f"""/*
 * DATI REALI — generato da scripts/build_dashboard_data.py a partire da web/public/data.
 * Non modificare a mano: rigenera con `make dashboard`.
 * Sostituisce prezzi, variazioni, calendario delle sedute, nomi e notizie MF.
 * Tesi, earnings e decisioni restano quelli simulati di data.js.
 */
(function () {{
  'use strict';
  const D = window.DEMO_DATA, R = {json.dumps(payload, ensure_ascii=False, separators=(",", ":"))};
  D.reale = {{ etichetta: R.etichetta, sottotitolo: R.sottotitolo, generato: R.generato }};
  D.aggiornamento = R.aggiornamento;
  D.giorni = R.giorni.map(d => new Date(d + 'T00:00:00Z'));
  // Demo quantities were sized on simulated prices: keep each position's demo value at the real price.
  D.portafoglio.forEach(p => {{
    const a = D.aziende[p.ticker], r = R.aziende[p.ticker];
    if (a && r) p.quantita = Math.max(1, Math.round(p.quantita * a.prezzo / r.prezzo));
  }});
  Object.entries(D.aziende).forEach(([t, a]) => {{
    if (R.aziende[t]) Object.assign(a, R.aziende[t]);
    else a.nome += ' · prezzo simulato';
  }});
  Object.assign(D.mercato, R.mercato);
  const simulata = D.serie;
  D.serie = (t, prezzo, variazione) => R.serie[t] || simulata(t, prezzo, variazione).slice(-D.giorni.length);
  D.notizie = R.notizie;
  D.indici = [];
}})();
"""
    OUT.write_text(js)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(aziende)} companies, {len(notizie)} stories, "
          f"{len(days)} sessions to {last}")


if __name__ == "__main__":
    main()
