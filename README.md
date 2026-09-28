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

`<content_id>` must name exactly one Italian listed company with 20 baseline sessions. Check `gemini.checks`: quote verbatim in body, figure in body, adjective in title, numbers only from article/facts, no recommendation words unless already in the article.

## Workflow

Everyone works on `main`, stays inside their own folder, makes small commits and pulls often.
