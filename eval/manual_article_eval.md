# Manual article quality evaluation

**Date:** 2026-09-28 · **Sample:** 12 articles · **Bodies locally:** not available (`body` empty in cards, stories, and company JSON)

## Method

Hand review of what the dashboard pipeline actually ships: titles, `news_type` / keyword / Gemini topics, `article.quote` when present, company-story peak/status, and thesis links in `data/theses/*.json`. Judged (1) company match, (2) classification (news type and, where present, thesis indicator), (3) whether attached quotes/interpretations are supported by available text.

**Honesty rule:** full MF bodies are not in the repo export. Evidence is scored **partial** when quote ↔ title/topic is coherent (and/or build-time `quote_is_verbatim` is true), not **ok**, because the body cannot be re-read offline.

## Sample selection

Varied set across companies and story shapes used by the desk:

| Bucket | Examples |
|---|---|
| Earnings | Garofalo Health Care, NewPrinces |
| M&A / takeover / orders | Lottomatica–Cirsa, Pininfarina OPA, Maire orders |
| Guidance / rating | Iren plan+dividend, Rai Way MS target cut |
| Tape-recap | Nexi allungo, Moncler trend |
| Thesis-linked | Enel → FCF indicator |
| Ambiguous name | “Leonardo Maria Del Vecchio” → Leonardo SpA |

Sources: `data/cards_gemini_it`, `data/cards`, `web/public/data/companies`, `data/theses`, `data/candidates_recent.csv`.

## Results table

| id | ticker | title (short) | match | class. | evidence | notes |
|---|---|---|---|---|---|---|
| 202609101405465587 | GHC | Utile frena, ricavi su; cerca M&A | ✓ | ✓ | partial | Earnings OK; quote supports “frena”; body n/a |
| 202609151013178211 | NWL | Ricavi/EBITDA up, semestre in perdita | ✓ | ✓ | partial | Earnings OK; loss quote fits title |
| 202609020746321794 | LTMC | Rileva Cirsa; titolo −11,2% | ✓ | ✓ | partial | Acquirer match OK; quote is tape, deal in topics |
| 202609170819021103 | PININ | OPA €1, premio 20%, delisting | ✓ | ✓ | partial | Takeover OK; premium quote fits |
| 202608270925452473 | MT | Nuovi ordini 110m (Tecnimont) | ✓ | partial | partial | Orders labelled **deal** (not M&A) |
| 202609041033385407 | AET | Dividendo 6,7%; piano ottobre; Equita | ✓ | partial | partial | plan vs capital vs analyst disagreement |
| 202608261044164621 | RWAY | MS taglia TP −20%, equal-weight | ✓ | ✓ | partial | Analyst OK; TP quote fits |
| 202608250749363291 | NEXI | Titolo prova un nuovo allungo | ✓ | ✓ | partial | Tape-recap → market_report |
| 202609101156153188 | MONC | Trend rimane negativo | ✓ | ✓ | partial | market_report vs story `other` |
| 202609111222214538 | FINME | Leonardo Maria Del Vecchio su X… | ✗ | ✗ | n/a | Person ≠ Leonardo SpA |
| 202609111817042189 | ENEL | Controllata Usa, cassa + M&A renewables | ✓ | ✓ | partial | Deal OK; thesis→FCF link loose |
| 202609091059297824 | COGE | Smentisce 22mld; titolo −7,9% | ✓ | partial | partial | capital→market_report; quote is close only |

Raw machine-readable copy: [`manual_article_eval.json`](manual_article_eval.json).

## Summary rates

| Dimension | Score |
|---|---|
| Company match | **11/12 (92%)** ✓ · 1 ✗ |
| Classification (strict ✓) | **8/12 (67%)** · 3 partial · 1 ✗ |
| Classification (✓ or partial) | **11/12 (92%)** |
| Evidence vs article text | **0/12 full ✓** · 11 partial · 1 n/a (no body offline) |

## Error patterns

1. **Homonym false matches (Leonardo)** — “Leonardo Maria Del Vecchio” / Figc “Leonardo” attached to Leonardo SpA. ~**80/749 (~11%)** stories under `leonardo.json` look like this family of errors. Also bleeds into thesis earnings candidates (`LDO` debug lists a Delfin/Del Vecchio id under 2T26).
2. **news_type divergence** across keyword → Gemini/choose_news → company export (Iren, Webuild, Moncler).
3. **Orders as “deal”** — commercial backlog news (Maire) typed like M&A.
4. **Loose thesis–indicator links** — Enel M&A/cash story mapped to “Free cash flow dopo gli investimenti” without a shipped supporting quote.
5. **Quote prefers tape** on mixed headlines (Lottomatica, Webuild) while substance sits in `topics[].evidence`.
6. **Bodies omitted from the dashboard bundle** — offline audit cannot re-verify citazioni.

## Recommended fixes

1. Negative match rules for `Leonardo Maria`, `Del Vecchio`, football contexts; require defence context for `FINME`.
2. Export one canonical `news_type` (after `choose_news`) into company stories.
3. Separate orders/contracts from M&A `deal`, or bias the chooser when evidence is only `ordini`/`commesse`.
4. Thesis links: require a verbatim span tied to the indicator; otherwise mark low confidence.
5. Prefer substantive quotes over tape lines when both topics exist.
6. Optionally ship a short body excerpt (or content hash) for offline quote checks.
