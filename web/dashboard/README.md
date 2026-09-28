# Dashboard (prototype)

Portfolio on the left (value, chart, holdings), a lean summary in the middle (Fear & Greed slot and allocation pies), watchlist on the right. Clicking a stock opens its page: your thesis, what changed after the latest results, a decision to consider, and the last four earnings.

**Everything in `data.js` is simulated.** Prices, earnings, news and signals are placeholders so the design shows every state. Nothing in this folder reads the pipeline yet.

## Run it

No build step. Serve the folder and open it:

```bash
python3 -m http.server 8765 --directory web/dashboard
```

Then open http://localhost:8765. Opening `index.html` directly from disk also works.

## Pages

- **Riepilogo** (home, `#riepilogo`): a slot for the Fear & Greed index, then two interactive pies, by holding and by sector. Clicking a holding opens its company page; clicking a sector pins it and lists its holdings.
- **Notizie** (`#notizie`): MF headlines grouped by company, kept simple. Reached from the toolbar switch.
- **Company page** (`#azienda-<code>`): news that can move the stock (net signal, price verdict, thesis indicator), then thesis, what changed, decision and the last four earnings.

The left column (value, chart, holdings) and the right column (watchlist) stay on every page.

## Adding the Fear & Greed index

The home page reserves a card with the id `fear-greed`, sized like a half-circle gauge with a four-row history (previous close, 1 week, 1 month, 1 year ago). To fill it without touching `app.js`:

1. Create `web/dashboard/fear_greed.js` and load it in `index.html` **before** `app.js`.
2. In it, define `window.renderFearGreed = function (el, ctx) { … }`. `el` is the card element; replace its contents. `ctx.data` is `window.DEMO_DATA`.
3. The home page calls it after every render (switching back to Riepilogo, adding a position, resetting the demo), so it must be safe to call more than once.

Use the page's CSS variables (`--card`, `--ink`, `--ink-2`, `--fill`, `--up`, `--down`, `--sep`) so it works in light and dark mode. `data/fear_greed.json` and `web/fear-greed.html` already have the numbers and a first design.

## Files

| File | What it does | Touch it when |
|---|---|---|
| `data.js` | All data, as one object on `window.DEMO_DATA`. No logic except a seeded price generator. | Connecting real data |
| `app.js` | Rendering and interactions. Contains no data. | Changing the UI |
| `index.html` | Styles and page shell. Follows the device's light/dark setting. | Changing the look |

User edits (positions, watchlist, thesis changes, added companies) are saved in the browser's `localStorage` under `mf-desk:v1`. Use **Ripristina dati demo** in the footer to reset.

## Real data (connected)

`real_data.js` loads after `data.js` and replaces what the pipeline really has. It is generated from `web/public/data` by `make dashboard` (see `scripts/build_dashboard_data.py`); don't edit it by hand.

- Real: prices and the price chart (2021-01-04 to 2026-09-23), last-session move, trading-day calendar, company names, and MF stories since 1 Aug 2026 with the price verdict (status, peak move, how many times the normal daily swing).
- Portfolio quantities are rescaled so each position keeps its demo value at the real price, so the weights stay the same.
- Still simulated: theses, earnings, decisions, sectors. Stellantis (`STLAM`) keeps a simulated price because its ISIN is Dutch and the story matching only covers Italian ISINs; its name is marked "prezzo simulato". The index strip is hidden.

Demo tickers map to the bundle in `DEMO_COMPANIES` inside the generator (`ISP` → Intesa Sanpaolo `AMBR`, `LDO` → Leonardo `FINME`, `SPM` → Saipem `SAIP`, `TIT` → Telecom Italia `OLI`).

## Connecting real data

`app.js` only reads `window.DEMO_DATA`. To connect real data, produce an object with the same shape, either by generating `data.js` from a script or by replacing it with a loader that sets `window.DEMO_DATA` before `app.js` runs. The full shape is documented at the top of `data.js`.

### Key everything by `COD_AZIONE`

The demo uses exchange tickers as keys. `COD_AZIONE` is MF's internal code, not the exchange ticker, and several differ, so these won't join with `data/cards` until the keys change:

| Company | Demo key | `COD_AZIONE` in `data/cards` |
|---|---|---|
| Leonardo | `LDO` | `FINME` |
| Saipem | `SPM` | `SAIP` |
| Intesa Sanpaolo | `ISP` | `AMBR` |
| Stellantis | `STLAM` | `FIAT` |
| Telecom Italia | `TIT` | `OLI` |

Enel (`ENEL`), Prysmian (`PRY`), Moncler (`MONC`) and Technoprobe (`TPRO`) already match. Today the screen shows the key as the ticker; if we key by `COD_AZIONE`, the ticker field should become a separate display symbol.

### Where each field comes from

| `DEMO_DATA` field | Real source | Status |
|---|---|---|
| `notizie[].id`, `titolo`, `data` | `data/cards/<content_id>.json` → `article.content_id`, `article.titolo`, `article.pub_local` | Available |
| `notizie[].url` (not shown yet) | `article.url` (real milanofinanza.it link) | Available |
| `notizie[].riassunto` | `verdict.text_it`, or `gemini.sentence` from `data/cards_gemini_en/` | Available |
| `notizie[].sezione` | `news.news_type` (`earnings`, `deal`, `takeover`, …), needs an Italian label | Available |
| `notizie[].strumenti[]` | `instrument.cod_azione`; `sim` is the embedding cosine (1.0 for a name match); `dir` from the sign of `verdict.peak.move_pct` | Available (one instrument per card) |
| `notizie[].segnale` | The team's verdict: `verdict.status`, `peak.move_pct`, `peak.z`, `peak.retained_pct`. The UI currently shows direction + strength + "similar stories" history; the verdict should replace it. | Needs a small UI change |
| `notizie[].indicatore` | Which thesis indicator a story touches. Not produced; could come from `news_type` (e.g. `earnings` → the results indicators) or a Gemini call. | Not produced |
| `mercato[code]` (last session %) | `financial_instruments.instruments_quotes`, using the frozen daily-move rule in the root README (`PRZ_LAST` over the previous session's `PRZ_RIF`, minus 1) | Query needed |
| `aziende[code].prezzo`, `serie()` | `instruments_quotes.PRZ_LAST` by `DATE(DATA_QUOTAZ)`; `data/series/<content_id>.json` already has `prz_last` for story windows only | Query needed |
| `aziende[code].nome`, ISIN | `instruments_info.DES_AZIONE`, `COD_ISIN` | Query needed |
| `aziende[code].earnings[]`, `esito`, `decisione` | Nothing produces these yet. Candidates: cards with `news_type == "earnings"` as `fonti`, plus a model step for facts, guidance and thesis impact. | Not produced |
| `portafoglio`, `watchlist`, `tesi` | The user's own input. Stays in the browser. | By design |
| `indici`, `giorni` | Index levels and trading days from `instruments_quotes` | Query needed |

### Real stories that already overlap the demo

`data/cards` has stories on Enel, Prysmian, Leonardo, Moncler, Saipem and Technoprobe. Those are the easiest first stocks to wire up.

## Rules the screen follows

- Every simulated number is labelled "Demo — dati simulati". Sources without a real link say "Fonte non disponibile nella demo".
- Portfolio weights are rounded so they always add up to 100%.
- The decision section never states probabilities and has no trading buttons.
- A story links to a stock only above a 0.60 cosine similarity between article and instrument embeddings. Below that, the nearest instrument is usually noise.
