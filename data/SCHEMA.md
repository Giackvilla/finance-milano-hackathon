# Dashboard bundle schema (v1.0)

Built by `make export` (`scripts/export_dashboard.py`) into `web/public/data/`. Everything is static JSON: fetch it with relative paths, no server needed. Every top-level object carries `schema_version`; if the shape changes, the version changes and the team is told.

Conventions:

- Dates are `YYYY-MM-DD`. Times are Rome local, `YYYY-MM-DDTHH:MM:SS` (`pub_local`).
- `*_pct` fields are already in percent (`17.65` means +17.65%).
- `z` is the move divided by the standard deviation of the 20 sessions before. `|z| >= 2` counts as unusual.
- Missing values are `null`. No `NaN` or `Infinity` ever appears.
- Text shown to users comes in both languages as `*_en` / `*_it` or `{ "en": …, "it": … }`.

## manifest.json

The first file to load. It holds `generated_at`, `languages`, `last_price_date` (`2026-09-23`), `stories_range`, `history_range`, `counts` (`stories`, `stories_with_gemini`, `stories_with_series`, `companies`), and `files`, which lists the path templates for every other file.

## status_meta.json

- `statuses`: an ordered array. Each entry has `status`, `group` (`before` | `after` | `none`), `color` (a token), `hex` (a suggested colour), `label_en`, `label_it`, `explain_en`, `explain_it`. Use this array for legends, badges and filter chips, and don't hardcode the six statuses.
- `groups`: labels for the three groups. Statuses in `before` are where the tape moved ahead of the headline, which is the signal.
- `news_types`: the classifier's type list, in priority order.

## stories.json

A flat array with one row per story that has a full card, newest first. It's meant for list, table and filter views.

| field | type | note |
|---|---|---|
| `content_id` | string | key for `stories/{content_id}.json` |
| `titolo`, `url`, `pub_local` | string | |
| `des_azione`, `cod_azione` | string | company name and ticker |
| `company_slug` | string | key for `companies/{slug}.json` |
| `news_type` | string | one of `status_meta.news_types` |
| `headline_reports_move` | bool | the headline itself reports a price move |
| `publication_phase` | string | `pre_open` / `in_session` / `after_close` / `non_trading_day` |
| `status` | string | one of `status_meta.statuses` |
| `peak_date`, `peak_timing` | string | the peak unusual session, or the largest session if none was unusual |
| `peak_move_pct`, `peak_z`, `retained_pct` | number | |
| `adjective_matches` | bool/null | Gemini's call on whether the headline adjective fits the body (English run) |
| `has_gemini`, `has_series` | bool | whether the detail file has a Gemini sentence or a chart |

## stories/{content_id}.json

Everything the detail page needs in one fetch.

- `article`: `content_id`, `titolo`, `data_pubblicazione` (UTC), `pub_local`, `testata`, `quote`, `url`.
- `instrument`: `des_azione`, `cod_azione`, `isin`, `company_slug`.
- `news`: `news_type`, `scheduled`, `headline_reports_move`, `matched` (the keywords that fired).
- `verdict`: `status`, `peak`, `largest`, `unusual_sessions[]`, `at_open`, `publication_phase`, `text_en`, `text_it`. `peak` and `largest` each hold `d`, `timing`, `timing_words_en/it`, `move_pct`, `z`, `vol_x`, `retained_pct`, `open_share_pct`.
- `tape`: figures for the session picked by the verdict (`move_date`, `move_pct`, `z`, `volume_x`, `baseline_sd_pct`, `px_before_move`, `px_after_move`, `last_px`, `retained_pct`, and more), plus `facts_text: {en: [...], it: [...]}`.
- `gemini`: `{en, it}`. Each language is either `null` or an object with `sentence`, `title_adjective`, `figure_in_body`, `adjective_matches`, `checks`, `model`. Show the sentence only when every value in `checks` passes.
- `series`: `null`, or an object with `baseline {from, to, sd_pct}`, `markers {publication, session_before, peak, last_session}`, and `sessions[]`. Each session has `d`, `rel` (-1 is the session before the article, 0 the first session on or after it), `prz_last`, `index_100` (the session before the article = 100), `move_pct`, `z`, `unusual`, `in_baseline`, `volume`.

## summary.json

Aggregates over MF stories from 2021-02-01 to 2026-09-15. The unit is the article, and the numbers are descriptive, not a strategy.

- `headline_numbers.en` / `.it`: sentences ready to show.
- `chance_pct`: `any_session` is the chance that any session is unusual. `after_unusual_rule_b` is the same with rule b, which applies from the reaction session on.
- `base_rate`: the raw counts behind `chance_pct`.
- `first_articles` (the main view: only the first story on a company within 7 days) and `all_matched` share the same shape:
  - `n_articles`, `n_unusual`
  - `status[]` with `{status, n, share}`
  - `by_news_type[]` with `{news_type, n, status[]}`, sorted by `n`
  - `per_session[]` with `{slot, n, n_unusual, share, chance, ratio}`. `ratio` is `share / chance`.
  - `share_anything_before`, `share_already_or_mostly_at_open`, `share_day_before_peak`
- `count`: the raw counts from `data/count.json`.

## companies.json

An array with one entry per company that has at least one matched MF story, sorted by `n_stories` descending. Each entry has `slug`, `des_azione`, `cod_azione`, `isin`, `n_stories`, `n_unusual`, `status` (a count for each status), `last_pub`, `n_detail` (how many of its stories have a detail file), and `has_prices`.

## companies/{slug}.json

These files are compact (no whitespace). The biggest, Unicredit, is about 1 MB.

- `slug`, `des_azione`, `cod_azione`, `isin`.
- `summary`: `n_stories`, `n_first_articles`, `n_unusual`, `status {…}`, `first_pub`, `last_pub`.
- `stories[]`, newest first. Each story has `content_id`, `titolo`, `pub_local`, `news_type`, `status`, `first_article` (the 7-day rule), `has_detail` (true when `stories/{content_id}.json` exists), and `peak` and `largest`, each `{d, timing, move_pct, z, retained_pct}` or `null`. History runs to 2026-09-15, plus any newer detail stories. Its `news_type` comes from the title only, while the detail cards also use the body.
- `prices`: `null`, or columnar arrays of the same length, which you can pass straight to a chart:
  - `d`: session dates, from 2021-01-04 to 2026-09-23.
  - `close`: `PRZ_LAST`.
  - `volume`: the number of shares traded.
  - `move_pct`: the daily move under the frozen rule.
  - `z`: the move divided by the standard deviation of the 20 sessions before that day. It's `null` until 20 moves exist.

To mark story days on the price chart, join `stories[].pub_local[:10]` or `peak.d` against `prices.d`.
