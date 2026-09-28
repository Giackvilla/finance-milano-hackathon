# One-command pipeline. `make export` works offline; the rest need gcloud (and Gemini for `gemini`).
#   make export   rebuild web/public/data from what is already in data/ and run the contract test
#   make all      data → cards → gemini → export

PY       ?= python3
PROJECT  ?= class-hackaton-09
FROM     ?= 2026-08-15
TO       ?= 2026-09-18
# Hero stories = the ones that already have Gemini cards; override with HERO_IDS="id1 id2".
HERO_IDS ?= $(basename $(notdir $(filter-out %/index.json,$(wildcard data/cards_gemini_en/*.json))))

.PHONY: all data events stats series prices cards gemini theses export dashboard test serve

all: data cards gemini series theses export

data: events stats prices

events:
	bq --project_id=$(PROJECT) query --use_legacy_sql=false --format=csv --max_rows=500 \
	  --parameter=from_date:DATE:2026-07-01 --parameter=to_date:DATE:$(TO) \
	  < sql/events.sql > data/candidates_recent.csv

# Live tape pull → data/tape_all.csv + data/stats.json (reuses data/base_rate.json when cached)
stats:
	$(PY) scripts/stats.py

prices:
	$(PY) scripts/fetch_company_prices.py

cards:
	$(PY) scripts/build_cards.py --from $(FROM) --to $(TO) --first-only --unusual-only

gemini:
	$(PY) scripts/build_cards.py --ids $(HERO_IDS) --gemini --lang en --out-dir data/cards_gemini_en
	$(PY) scripts/build_cards.py --ids $(HERO_IDS) --gemini --lang it --out-dir data/cards_gemini_it

series:
	$(PY) scripts/build_series.py $(HERO_IDS)

# Thesis / earnings analysis from MF articles (needs gcloud + BigQuery + Gemini)
theses:
	$(PY) scripts/build_theses.py

export:
	$(PY) scripts/export_dashboard.py
	$(PY) scripts/test_export.py
	$(PY) scripts/build_dashboard_data.py

# Only regenerate web/dashboard/real_data.js from the committed bundle
dashboard:
	$(PY) scripts/build_dashboard_data.py

# Local dashboard + thesis regenerate API (POST /api/tesi/<TICKER>)
serve:
	$(PY) scripts/serve_dashboard.py

test:
	@total=0; failed=0; \
	for t in test_verdict test_classify test_build_card test_export test_theses \
		test_choose_news test_classify_gemini test_fear_greed \
		test_company_matching test_story_selection; do \
	  out=$$($(PY) scripts/$$t.py 2>&1); ec=$$?; echo "$$out"; \
	  n=$$(echo "$$out" | sed -n 's/.*Ran \([0-9][0-9]*\) test.*/\1/p' | tail -1); \
	  total=$$((total + $${n:-0})); \
	  if [ $$ec -ne 0 ]; then failed=1; fi; \
	done; \
	echo ""; echo "TOTAL: $$total tests"; \
	if [ $$failed -ne 0 ]; then exit 1; fi
