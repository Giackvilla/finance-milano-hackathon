# From headlines to signals

Challenge 2, Finance Milano Hackathon. One card for one real MF story: the headline, what the tape did around it, and one Gemini sentence on whether the headline matches the facts.

**The signal is where the headline and the tape disagree.**

## Layout

| Folder | Owner | Contents |
|---|---|---|
| `sql/` | Data | BigQuery queries. `events.sql` matches titles to `DES_AZIONE` and computes the tape figures. |
| `data/` | Data | `card.json` is the contract between everyone. Don't change its shape without telling the team. |
| `scripts/` | Model | Gemini prompt and call. Reads only `titolo` and `body`. |
| `web/` | Screen | The card. Reads `data/card.json`. |
| `pitch.md` | Pitch | The three beats. |

## Frozen rule

- Baseline: the 20 sessions before the article date.
- Daily move: `PRZ_LAST / PRZ_RIF - 1`, with `PRZ_RIF` taken from the previous session (on the same row it equals `PRZ_LAST` for most stocks).
- Unusual: absolute move at least 2 times the baseline standard deviation.
- Retained: `(PRZ_LAST on 2026-09-23 - price before the move) / (price after the move - price before the move)`.

Prices and dates come only from BigQuery. Gemini never does arithmetic.

## Running the queries

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project class-hackaton-09

bq --project_id=class-hackaton-09 query --use_legacy_sql=false --format=csv --max_rows=500 \
  --parameter=from_date:DATE:2026-07-01 --parameter=to_date:DATE:2026-09-18 \
  < sql/events.sql > data/candidates_recent.csv
```

## Building the card

```bash
# One story → data/card.json (or --out path). Prices from BigQuery; Gemini on titolo+body+verdict text.
python3 scripts/build_card.py <content_id>
python3 scripts/build_card.py <content_id> --lang it
python3 scripts/build_card.py <content_id> --no-gemini --out /tmp/card.json

# Batch over a Rome pub_date range (or --ids …). Default skips Gemini; add --gemini to call it.
python3 scripts/build_cards.py --from 2026-08-15 --to 2026-09-18 --first-only --unusual-only
python3 scripts/build_cards.py --from 2026-08-15 --to 2026-09-18 --first-only --unusual-only --gemini --limit 3
```

`card.json` blocks: **article** (id, titolo, UTC + Rome times, quote, url) · **instrument** · **news** (classify: type, scheduled, headline_reports_move) · **verdict** (status + peak/largest + bilingual text) · **tape** (peak-or-largest session figures + `facts_text`) · **gemini** (sentence + checks; nulls with `--no-gemini`) · **context** (optional `stats.json` / `base_rate.json`).

Verdict statuses: **NO_REACTION** — no session with |z|≥2 · **ALREADY_IN_PRICE** — peak unusual session closed before publication · **PARTLY_IN_PRICE** — some unusual move closed before, peak did not · **MOSTLY_AT_OPEN** — more than half of the day's move was already in the opening price before an in-session article (fixed majority rule, not tuned) · **REACTED** — peak unusual move on the reaction session · **DELAYED** — peak unusual move after the reaction session.

`<content_id>` must name exactly one Italian listed company with 20 baseline sessions. Company matching is deliberately conservative: it uses canonical instrument names plus reviewed aliases (Telecom Italia/Tim, Finmeccanica, and Intesa San Paolo), and it rejects a fresh title when more than one listed company remains. Person and brand homonyms (Leonardo Maria Del Vecchio, Leonardo jr., Leonardo Capital, Leonardo da Vinci) are not the aerospace company. A bank is not the subject when it is only the source of the note ("analisti di Intesa", "Intesa Sanpaolo vede un upside"). The bare noun "intesa" after an apostrophe (l'intesa, sull'intesa) is an agreement, not the bank. This is title entity matching, not full semantic entity resolution.

Before aggregation, rows for the same canonical company with the same normalized title within 24 hours are treated as one article. The normalization is limited to case, accents, punctuation, and whitespace, so distinct follow-up stories remain distinct. The offline exporter drops a cached row only when the assigned company itself is a homonym or only the broker, and it collapses duplicate headlines before rebuilding company histories. A headline that also names a counterparty stays on the company it was already assigned to.

Check `gemini.checks`: quote verbatim in body, figure in body, adjective in title, numbers only from article/facts, no recommendation words unless already in the article.

## Body-first Gemini classification CLI

`scripts/classify_gemini.py` calls Gemini through Vertex AI with the access token
from `gcloud auth print-access-token`. It reads the full article body, returns at
most three controlled topics, and validates the selected company and ticker
against ordinary Italian instruments that also have quotes in BigQuery.

```bash
# Article from class-hackaton-09.news.articles
python3 scripts/classify_gemini.py --content-id 202609101905313642

# JSON (titolo/title/headline + body/text/content) or plain UTF-8 text
python3 scripts/classify_gemini.py --file article.json --lang it

# Body on stdin; title is optional but improves company matching
cat article.txt | python3 scripts/classify_gemini.py \
  --title "Prysmian colloca nuove azioni" --out /tmp/classification.json
```

The defaults match the card builder: project `class-hackaton-09`, Vertex location
`global`, and model `gemini-2.5-flash`. Override them with `--project`,
`--location`, and `--model` (or `GOOGLE_CLOUD_PROJECT`,
`GOOGLE_CLOUD_LOCATION`, and `GEMINI_MODEL`).

The controlled labels are the existing card labels: `takeover`, `earnings`,
`plan`, `capital`, `legal_regulatory`, `analyst`, `deal`, `governance`,
`market_report`, and `other`. Public/control offers are `takeover`; securities
offerings are `capital`; commercial offers and contracts are `deal`. The output
keeps the card's `article`, `instrument`, `news`, and `gemini` blocks.

The demo cards in `data/cards_gemini_en` and `data/cards_gemini_it` use both
classifiers (`news.classifier` = `both`). `scripts/choose_news.py` keeps the
first Gemini topic whose quote matches that topic's rules, and falls back to
the keyword label, then to `other`. `scheduled` and `headline_reports_move`
stay on the keyword rules, because the verdict text uses them. Refresh the
Gemini topics with `python3 scripts/refresh_demo_news.py`.

## For the dashboard

Read only `web/public/data/`. It is committed, so the dashboard never needs gcloud or a Gemini key. The shape of every file is in [data/SCHEMA.md](data/SCHEMA.md).

- `manifest.json` has counts, dates and the file path templates.
- `stories.json` is the list view. `stories/<content_id>.json` is one story with the card, the Gemini sentence in both languages, and the chart series.
- `summary.json` holds the headline numbers and the status breakdowns by news type.
- `status_meta.json` has labels, explanations and colours for the six statuses.
- `companies.json` and `companies/<slug>.json` hold every MF story on a company since 2021, with its verdict, plus daily prices for the company page.

```bash
make export   # offline: rebuild the bundle from data/ and run the contract test
make all      # BigQuery + Gemini: events, tape/stats, prices, cards, Gemini cards, series, export
make test     # all unit tests
```

`make export` needs `data/tape_all.csv` (from `make stats`) and optionally `data/company_prices.csv` (from `make prices`) to rebuild the company files. Both are gitignored. Without them, the existing `companies/` is kept as it is.

## Workflow

Everyone works on `main`, stays inside their own folder, makes small commits and pulls often.
