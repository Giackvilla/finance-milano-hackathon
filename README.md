# MF Desk

Finance Milano Hackathon, challenge 2. You write a thesis for an Italian name. The desk checks that thesis against Milano Finanza articles and Borsa Italiana closes, then drafts an indication to evaluate.

The indication is an input for a person, not an order. The screen estimates no chance of success. The portfolio and watchlist in the demo are example holdings.

## Run the desk

Python 3.9 or newer. The scripts use the standard library only. `web/public/data/` and `web/dashboard/real_data.js` are committed, so browsing needs no cloud login and no Gemini key.

```bash
python3 scripts/serve_dashboard.py --dry-run
```

Open http://127.0.0.1:8000. `--dry-run` (or `DASHBOARD_DRY_RUN=1`) skips BigQuery and Gemini when a thesis is saved. The page still marks the analysis **Da ricalcolare** and shows a local diff.

A save that really rebuilds the reading:

```bash
make serve
```

Same URL. The browser POSTs the thesis to `/api/tesi/<TICKER>`. The server writes `data/theses_overrides/<TICKER>.json`, runs `scripts/build_theses.py --only` and `scripts/build_dashboard_data.py`, and the page shows **Cosa è cambiato**. That path needs the `gcloud` and `bq` CLIs, Vertex AI, and Node, because the thesis builder loads `web/dashboard/data.js` through `node`.

Opening `web/dashboard/index.html` from disk is enough to look around. Regenerating a thesis needs the server above.

Static copy, no API:

```bash
python3 -m http.server 8765 --directory web/dashboard
```

Positions, the watchlist, thesis edits, and added names stay in the browser under `localStorage` key `mf-desk:v1`. **Ripristina dati demo** in the footer clears them.

## Pages

The portfolio column and the watchlist stay up on every page.

| Hash | Page |
|---|---|
| `#riepilogo` | Italy Fear & Greed, then allocation by holding and by sector. |
| `#notizie` | MF headlines, filtered to the portfolio, the watchlist, or every tracked name. |
| `#azienda-<ticker>` | Thesis, what the latest results change, the last four earnings windows, MF news grouped by the thesis indicator each story touches, then the indication. |

Held names use Mantenere, Aggiungere, Ridurre, Vendere. Watchlist names use Valutare ingresso, Attendere, Evitare per ora. Those words are the indication. The page has no control that sends an order.

Each block is labelled:

- **Dataset.** Borsa Italiana closes and MF articles, with links back to the source. Prices run through 23 Sep 2026. Stories on the desk start 1 Aug 2026.
- **Modello.** Gemini readings: earnings against the thesis, headlines mapped to indicators, the decision draft, the one-sentence card, and Fear & Greed.
- **Esempio.** The starting positions, weights, and theses.

Stellantis (`STLAM`) keeps a simulated price. Its ISIN is Dutch (`COD_AZIONE` `FIAT`) and the offline Italian tape has no FIAT series. The UI badges it and leaves it out of the portfolio total, so dataset prices and the simulated series stay separate.

Screen-level notes, including the `DEMO_DATA` field map, are in [web/dashboard/README.md](web/dashboard/README.md).

## Committed bundle

From `web/public/data/manifest.json`, generated 28 Sep 2026:

| | |
|---|---|
| Detail stories | 35, published 17 Aug 2026 to 18 Sep 2026 |
| Gemini sentence and chart | 14 of those 35 |
| Companies | 280, with MF stories from 1 Feb 2021 to 15 Sep 2026 |
| Last close | 23 Sep 2026 |

The shape of each file is in [data/SCHEMA.md](data/SCHEMA.md). `make dashboard` turns that bundle into `web/dashboard/real_data.js`.

## Layout

| Path | Contents |
|---|---|
| `web/dashboard/` | The desk. `data.js` is the demo shell. `real_data.js` and `fear_greed.js` are generated. |
| `web/public/data/` | Static JSON the desk is built from. |
| `web/fear-greed.html` | Standalone Fear & Greed page. |
| `data/` | Cards, Gemini cards, series, theses, stats. `tape_all.csv` and `company_prices.csv` are gitignored. |
| `scripts/` | Builders and tests. |
| `sql/` | BigQuery queries. |
| `eval/` | Hand review of 12 articles. |
| `pitch/jury_qa.md` | Jury answers, English and Italian. |

## Rebuild

GCP project `class-hackaton-09`. Gemini model `gemini-2.5-flash` on Vertex, location `global`. The access token is `gcloud auth print-access-token`.

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project class-hackaton-09
```

```bash
make export      # offline: rebuild web/public/data from data/, run the contract test, write real_data.js
make dashboard   # rewrite web/dashboard/real_data.js only
make test        # unit tests
make all         # BigQuery + Gemini, then export
```

`make all` runs events, tape and stats, company prices, cards, Gemini cards, chart series, theses, then export.

`make export` rebuilds `web/public/data/companies/` when `data/tape_all.csv` is present (`make stats`). The price columns in those files need `data/company_prices.csv` (`make prices`). Without those two CSVs the company files already in the repo are left as they are.

Fear & Greed is outside `make all`:

```bash
python3 scripts/fear_greed.py
```

That writes `data/fear_greed.json` and `web/dashboard/fear_greed.js`. A shock is a daily move at least twice the standard deviation of the previous 20 sessions. The narrative leg tilts the other weights. Shock counts sit beside the score and are not tilted.

Makefile dates: cards from `2026-08-15` to `2026-09-18` (`FROM`, `TO`). The events query starts at `2026-07-01`. Hero ids default to the English Gemini cards already in `data/cards_gemini_en/`. Override with `HERO_IDS`.

### One card

```bash
python3 scripts/build_card.py <content_id>
python3 scripts/build_card.py <content_id> --lang it
python3 scripts/build_card.py <content_id> --no-gemini --out /tmp/card.json

python3 scripts/build_cards.py --from 2026-08-15 --to 2026-09-18 --first-only --unusual-only
python3 scripts/build_cards.py --ids <content_id> --gemini --lang it --out-dir data/cards_gemini_it
```

Blocks: `article`, `instrument`, `news`, `verdict`, `tape`, `gemini`, and optional `context`. `--no-gemini` leaves the Gemini fields null. Prices come from BigQuery. Gemini sees the title, the body, and the verdict facts as text.

### Classification

`scripts/classify_gemini.py` reads the full body, returns at most three controlled topics, and checks the company and ticker against ordinary Italian instruments that also have quotes in BigQuery.

```bash
python3 scripts/classify_gemini.py --content-id 202609101905313642
python3 scripts/classify_gemini.py --file article.json --lang it
```

Override the defaults with `--project`, `--location`, `--model`, or `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GEMINI_MODEL`.

Labels, in priority order: `takeover`, `earnings`, `plan`, `capital`, `legal_regulatory`, `analyst`, `deal`, `governance`, `market_report`, `other`. A public or control offer is `takeover`. A securities offering is `capital`. A commercial contract is `deal`.

Cards in `data/cards_gemini_en` and `data/cards_gemini_it` set `news.classifier` to `both`. `scripts/choose_news.py` keeps the first Gemini topic whose quote matches that topic’s rules, then the keyword label, then `other`. `scheduled` and `headline_reports_move` stay on the keyword rules, because the verdict text uses them. `python3 scripts/refresh_demo_news.py` refreshes the Gemini topics on those cards.

### Theses

```bash
python3 scripts/build_theses.py
python3 scripts/build_theses.py --only PRY ENEL
python3 scripts/build_theses.py --force --only STLAM
```

The builder reads the thesis from `data.js`, and uses `data/theses_overrides/<TICKER>.json` when that file exists. It writes `data/theses/<TICKER>.json`. An unchanged thesis skips Gemini and BigQuery unless `--force` is set. Quote and number checks drop a fact whose figure is not in the sources. `valutazione` stays null: there is no P/E series in the warehouse extract.

A name that is not in that list still gets a reading when it is in the offline bundle. Saving the thesis, or opening a holding you added from the catalog, calls `POST /api/catalog/<TICKER>`. That path does not use Gemini. It compares the words of the thesis with MF titles from 1 Aug 2026 and the price reaction already stored on the company file. If the titles do not contain the thesis, the page says so and lists the articles it did check. Bending Spoons (`1BSP`) is one of those names.

| Desk ticker | `COD_AZIONE` | Company file |
|---|---|---|
| `ENEL`, `PRY`, `MONC`, `TPRO`, `REC` | same code | `enel`, `prysmian`, `moncler`, `technoprobe`, `recordati` |
| `ISP` | `AMBR` | `intesa-sanpaolo` |
| `LDO` | `FINME` | `leonardo` |
| `SPM` | `SAIP` | `saipem` |
| `TIT` | `OLI` | `telecom-italia` |
| `STLAM` | `FIAT` | simulated price, no offline series |

## Tape rule

Frozen. Nothing here was trained or tuned.

- Baseline: the 20 sessions before the article date.
- Daily move: `PRZ_LAST / previous session's PRZ_RIF - 1`. On the same row `PRZ_RIF` equals `PRZ_LAST` for most stocks, so a same-row ratio is almost always zero.
- Unusual: absolute move at least 2 times the sample standard deviation of that baseline.
- Retained: `(PRZ_LAST on 2026-09-23 - price before the move) / (price after the move - price before the move)`.

Prices and dates come only from BigQuery. Gemini does no arithmetic.

| Status | Meaning |
|---|---|
| `NO_REACTION` | No session in the window has \|z\| ≥ 2. |
| `ALREADY_IN_PRICE` | The peak unusual session closed before publication. |
| `PARTLY_IN_PRICE` | Some unusual move closed before publication. The peak did not. |
| `MOSTLY_AT_OPEN` | In-session article, and more than half of that day’s move was already in the open. Fixed majority, not fitted. |
| `REACTED` | The peak unusual move is on the reaction session. |
| `DELAYED` | The peak unusual move is after the reaction session. |

A card sentence is shown only when every Gemini check passes: the quote is verbatim in the body, the figure is in the body, the adjective is in the title, every number comes from the article or the facts text, and recommendation words appear only when the article already uses them.

The board score next to a headline is the observed move around that article, including sessions after publication, scaled from the peak and from `|z|`. It describes the past.

## Tests

```bash
make test
```

Runs `test_verdict`, `test_classify`, `test_build_card`, `test_export`, `test_theses`, `test_choose_news`, `test_classify_gemini`, `test_fear_greed`, and `test_catalog_company`.

A separate hand review of 12 articles is in [eval/manual_article_eval.md](eval/manual_article_eval.md): company match 11/12, strict type 8/12. Full bodies are not in the export, so that review scores quotes as partial.

## Limits

Match is on the title. A shared token such as Leonardo attaches the person as well as Leonardo SpA. The hand review counted on the order of 80 of 749 stories under that name. The tape is daily closes, plus the open-share rule for `MOSTLY_AT_OPEN`. The 2σ / 20-session cut is a description, not a model. Sessions well after publication sit near the base rate. Gemini text that fails a check is omitted. A link from a story to a thesis indicator can be loose. Article bodies are not in `web/public/data/`. The demo book is invented.

Wording for the jury, in both languages, is in [pitch/jury_qa.md](pitch/jury_qa.md).
