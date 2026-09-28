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

## Building the card for the chosen story

```bash
python3 scripts/build_card.py <content_id>            # writes data/card.json
python3 scripts/build_card.py <content_id> --lang it  # Gemini sentence in Italian
python3 scripts/count_day_before.py                   # writes data/count.json
```

`<content_id>` comes from `data/candidates_recent.csv`. The article's title must name exactly one company.
Check `gemini.checks` in the output: the quote must be verbatim, the figure must be in the body, and no number may come from outside the sources.

## Workflow

Everyone works on `main`, stays inside their own folder, makes small commits and pulls often.
