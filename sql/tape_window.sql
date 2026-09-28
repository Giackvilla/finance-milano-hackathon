-- One row per (article, session) in the tape window around publication.
-- Same company match and frozen rule as events.sql; pub_date is Rome local.
-- Window: day_before, same_day (if any), first 5 later. Require n_base = 20.
-- Params: @content_ids ARRAY<STRING>, @from_date DATE, @to_date DATE.
-- Ids mode: non-empty @content_ids. Range mode: empty array + pub_date between dates.

WITH catalog AS (
  -- Deduplicate the instrument catalogue before adding aliases.  Otherwise
  -- Intesa/Tim/Leonardo aliases inflate n_companies.
  SELECT DISTINCT i.COD_AZIONE, i.DES_AZIONE, i.COD_ISIN
  FROM `class-hackaton-09.financial_instruments.instruments_info` i
  WHERE i.COD_TIPO = 'ORD' AND i.COD_ISIN LIKE 'IT%'
    AND LENGTH(TRIM(i.DES_AZIONE)) >= 3
    AND TRIM(i.DES_AZIONE) NOT IN ('Reti', 'Impianti', 'Energy', 'Maps', 'Simone', 'Plc', 'Circle', 'Pattern', 'Predict', 'Friends', 'Adventure', 'Tecno')
    AND i.COD_AZIONE IN (SELECT DISTINCT COD_AZIONE FROM `class-hackaton-09.financial_instruments.instruments_quotes`)
),
alias_rows AS (
  SELECT c.*, TRIM(c.DES_AZIONE) AS alias_name
  FROM catalog c
  UNION ALL SELECT c.*, 'Tim' FROM catalog c WHERE LOWER(TRIM(c.DES_AZIONE)) = 'telecom italia'
  UNION ALL SELECT c.*, 'Finmeccanica' FROM catalog c WHERE LOWER(TRIM(c.DES_AZIONE)) = 'leonardo'
  UNION ALL SELECT c.*, 'Intesa' FROM catalog c WHERE LOWER(TRIM(c.DES_AZIONE)) = 'intesa sanpaolo'
  UNION ALL SELECT c.*, 'Intesa San Paolo' FROM catalog c WHERE LOWER(TRIM(c.DES_AZIONE)) = 'intesa sanpaolo'
),
names AS (
  SELECT
    r.COD_AZIONE, r.DES_AZIONE, r.COD_ISIN,
    -- RE2-compatible boundaries (Python uses equivalent \w boundaries).
    -- Bare Intesa: an apostrophe belongs to l'intesa / sull'intesa ("agreement").
    CASE
      WHEN LOWER(TRIM(r.alias_name)) = 'intesa' THEN
        '(?i)(^|[^[:alnum:]_''])intesa($|[^[:alnum:]_])'
      ELSE CONCAT(r'(?i)(^|[^[:alnum:]_])',
        REGEXP_REPLACE(REGEXP_REPLACE(TRIM(r.alias_name), r'([.^$|()\[\]{}*+?\\])', r'\\\1'), r' ', r'[[:space:]-]+'),
        r'($|[^[:alnum:]_])')
    END AS pattern
  FROM alias_rows r
),

articles AS (
  SELECT
    content_id,
    titolo,
    data_pubblicazione,
    DATETIME(TIMESTAMP(data_pubblicazione, "UTC"), "Europe/Rome") AS pub_local,
    DATE(DATETIME(TIMESTAMP(data_pubblicazione, "UTC"), "Europe/Rome")) AS pub_date
  FROM `class-hackaton-09.news.articles`
  WHERE ((ARRAY_LENGTH(@content_ids) > 0 AND content_id IN UNNEST(@content_ids))
     OR (ARRAY_LENGTH(@content_ids) = 0
         AND DATE(DATETIME(TIMESTAMP(data_pubblicazione, "UTC"), "Europe/Rome"))
             BETWEEN @from_date AND @to_date))
    -- multi-stock live blogs and daily recaps are not about one company
    AND NOT REGEXP_CONTAINS(titolo, r"^(Borse oggi in diretta|Cos.è successo oggi)")
),

-- Exclusions are scoped to the matched instrument so a Del Vecchio / Intesa
-- analyst aside does not drop the real company named in the same headline.
matched_rows AS (
  SELECT DISTINCT a.content_id, a.titolo, a.data_pubblicazione, a.pub_local, a.pub_date,
         n.COD_AZIONE, n.DES_AZIONE, n.COD_ISIN
  FROM articles a
  JOIN names n ON REGEXP_CONTAINS(a.titolo, n.pattern)
  WHERE NOT (
      -- Leonardo person / other-entity uses (COD_AZIONE FINME or DES_AZIONE)
      (UPPER(n.COD_AZIONE) = 'FINME' OR LOWER(TRIM(n.DES_AZIONE)) = 'leonardo')
      AND (
        REGEXP_CONTAINS(a.titolo,
          r'(?i)(^|[^[:alnum:]_])leonardo[[:space:],;:/()\-]+(maria([[:space:]]+del[[:space:]]+vecchio)?|del[[:space:]]+vecchio|jr|j[[:space:]]*r|da[[:space:]]+vinci|capital|lmdv|group|holding)($|[^[:alnum:]_])')
        OR REGEXP_CONTAINS(a.titolo,
          r'(?i)(^|[^[:alnum:]_])(maria|del[[:space:]]+vecchio)[[:space:]]*[,:\-]?[[:space:]]*leonardo($|[^[:alnum:]_])')
        OR (
          REGEXP_CONTAINS(a.titolo, r'(?i)del[[:space:]]+vecchio')
          AND REGEXP_CONTAINS(a.titolo, r'(?i)(^|[^[:alnum:]_])di[[:space:]]+leonardo($|[^[:alnum:]_])')
        )
      )
    )
    AND NOT (
      -- Intesa as analyst / broker source (mirrors company_matching._analyst_reference)
      LOWER(TRIM(n.DES_AZIONE)) = 'intesa sanpaolo'
      AND (
        REGEXP_CONTAINS(a.titolo,
          r'(?i)(analist[[:alpha:]]*|stime)[[:space:]]+(di|da)[[:space:]]+intesa(?:[[:space:]-]+san[[:space:]-]*paolo)?($|[^[:alnum:]_])')
        OR REGEXP_CONTAINS(a.titolo,
          r'(?i)(^|[^[:alnum:]_])secondo[[:space:]]+intesa(?:[[:space:]-]+san[[:space:]-]*paolo)?($|[^[:alnum:]_])')
        OR REGEXP_CONTAINS(a.titolo,
          r'(?i)(^|[^[:alnum:]_])intesa(?:[[:space:]-]+san[[:space:]-]*paolo)?[[:space:],;:/()\-]+(vede|vedono|alza|alzano|taglia|tagliano|conferma|confermano|aggiorna|aggiornano|stima|stimano|prevede|prevedono|promuove|boccia|raccomanda|raccomandano|fissa|fissano)([[:space:]]+[^[:space:]]+){0,5}[[:space:]]+(target[[:space:]]+price|target[[:space:]]+sul[[:space:]]+titolo|rating|upside|stime|valutazion[[:alpha:]]*|giudizio|raccomand[[:alpha:]]*)($|[^[:alnum:]_])')
      )
    )
    AND NOT (
      -- Tim Cook / Tim Brasil are not Telecom Italia
      LOWER(TRIM(n.DES_AZIONE)) = 'telecom italia'
      AND REGEXP_CONTAINS(a.titolo,
        r'(?i)(^|[^[:alnum:]_])tim[[:space:],;:/()\-]+(cook|brasil)($|[^[:alnum:]_])')
    )
),
matches AS (
  SELECT m.*, COUNT(*) OVER (PARTITION BY m.content_id) AS n_companies
  FROM matched_rows m
),

sessions AS (
  SELECT
    COD_AZIONE,
    DATE(DATA_QUOTAZ) AS d,
    PRZ_LAST,
    PRZ_RIF,
    PRZ_APERTURA,
    PRZ_MIN,
    PRZ_MAX,
    QUANTITATIVO,
    LAG(PRZ_RIF) OVER w AS prev_rif,
    SAFE_DIVIDE(PRZ_LAST, LAG(PRZ_RIF) OVER w) - 1 AS ret,
    ROW_NUMBER() OVER w AS idx
  FROM `class-hackaton-09.financial_instruments.instruments_quotes`
  WHERE COD_AZIONE IN (SELECT DISTINCT COD_AZIONE FROM matches WHERE n_companies = 1)
    AND PRZ_LAST > 0 AND PRZ_RIF > 0
  WINDOW w AS (PARTITION BY COD_AZIONE ORDER BY DATA_QUOTAZ)
),

anchored AS (
  SELECT m.content_id, m.COD_AZIONE,
         MAX(IF(s.d < m.pub_date, s.idx, NULL)) AS idx_before
  FROM matches m JOIN sessions s USING (COD_AZIONE)
  WHERE m.n_companies = 1
  GROUP BY 1, 2
),

baseline AS (
  SELECT a.content_id, a.COD_AZIONE,
         COUNT(s.ret) AS n_base,
         STDDEV_SAMP(s.ret) AS sd,
         AVG(s.QUANTITATIVO) AS avg_qty
  FROM anchored a JOIN sessions s
    ON s.COD_AZIONE = a.COD_AZIONE AND s.idx BETWEEN a.idx_before - 19 AND a.idx_before
  GROUP BY 1, 2
),

phase AS (
  SELECT
    m.content_id,
    m.COD_AZIONE,
    CASE
      WHEN NOT EXISTS (
        SELECT 1 FROM sessions s
        WHERE s.COD_AZIONE = m.COD_AZIONE AND s.d = m.pub_date
      ) THEN 'non_trading_day'
      WHEN TIME(m.pub_local) < TIME '09:00:00' THEN 'pre_open'
      WHEN TIME(m.pub_local) < TIME '17:30:00' THEN 'in_session'
      ELSE 'after_close'
    END AS publication_phase
  FROM matches m
  WHERE m.n_companies = 1
),

-- open usable only if > 0 and inside [min, max] when those are positive
open_ok AS (
  SELECT
    s.*,
    IF(
      s.PRZ_APERTURA > 0
      AND (
        NOT (s.PRZ_MIN > 0 AND s.PRZ_MAX > 0)
        OR (s.PRZ_APERTURA BETWEEN s.PRZ_MIN * 0.9999 AND s.PRZ_MAX * 1.0001)
      ),
      s.PRZ_APERTURA,
      NULL
    ) AS open_px
  FROM sessions s
),

win AS (
  SELECT
    m.content_id, m.titolo, m.data_pubblicazione, m.pub_local, m.pub_date,
    ph.publication_phase,
    m.COD_AZIONE, m.DES_AZIONE, m.COD_ISIN,
    s.d,
    CASE
      WHEN s.d < m.pub_date THEN 'day_before'
      WHEN s.d = m.pub_date THEN 'same_day'
      ELSE 'later'
    END AS timing,
    IF(s.d > m.pub_date,
       ROW_NUMBER() OVER (
         PARTITION BY m.content_id, m.COD_AZIONE, s.d > m.pub_date
         ORDER BY s.d
       ),
       NULL) AS later_rank,
    s.prev_rif,
    s.open_px,
    s.PRZ_LAST AS last_px,
    s.ret AS move,
    SAFE_DIVIDE(s.ret, b.sd) AS z,
    ABS(SAFE_DIVIDE(s.ret, b.sd)) >= 2 AS unusual,
    SAFE_DIVIDE(s.open_px, s.prev_rif) - 1 AS gap,
    SAFE_DIVIDE(s.PRZ_LAST, s.open_px) - 1 AS intraday,
    SAFE_DIVIDE(LN(SAFE_DIVIDE(s.open_px, s.prev_rif)), LN(SAFE_DIVIDE(s.PRZ_LAST, s.prev_rif))) AS open_share,
    SAFE_DIVIDE(s.QUANTITATIVO, b.avg_qty) AS vol_x,
    b.sd AS baseline_sd,
    b.n_base,
    a.idx_before,
    s.idx
  FROM anchored a
  JOIN matches m USING (content_id, COD_AZIONE)
  JOIN baseline b USING (content_id, COD_AZIONE)
  JOIN phase ph USING (content_id, COD_AZIONE)
  JOIN open_ok s ON s.COD_AZIONE = a.COD_AZIONE
  WHERE m.n_companies = 1
    AND b.n_base = 20
    AND (
      s.idx = a.idx_before
      OR s.d = m.pub_date
      OR (s.d > m.pub_date AND s.idx <= a.idx_before + 6)
    )
),

-- keep day_before + same_day + later ranks 1..5 only
windowed AS (
  SELECT * EXCEPT (idx_before, idx)
  FROM win
  WHERE timing IN ('day_before', 'same_day')
     OR (timing = 'later' AND later_rank BETWEEN 1 AND 5)
),

flags AS (
  SELECT
    w.*,
    (w.d < w.pub_date
      OR (w.d = w.pub_date AND w.publication_phase = 'after_close')) AS closed_before_publication,
    CASE
      WHEN w.publication_phase IN ('pre_open', 'in_session')
        THEN w.timing = 'same_day'
      ELSE w.timing = 'later' AND w.later_rank = 1
    END AS is_reaction_session
  FROM windowed w
),

last_session AS (
  SELECT COD_AZIONE, d AS final_d, PRZ_LAST AS final_px
  FROM sessions
  WHERE d = (SELECT MAX(DATE(DATA_QUOTAZ)) FROM `class-hackaton-09.financial_instruments.instruments_quotes`)
)

SELECT
  f.content_id, f.titolo, f.data_pubblicazione, f.pub_local, f.pub_date, f.publication_phase,
  f.COD_AZIONE, f.DES_AZIONE, f.COD_ISIN,
  f.d, f.timing, f.later_rank,
  f.closed_before_publication, f.is_reaction_session,
  f.prev_rif, f.open_px, f.last_px, f.move, f.z, f.unusual,
  f.gap, f.intraday, f.open_share, f.vol_x, f.baseline_sd, f.n_base,
  l.final_d, l.final_px,
  SAFE_DIVIDE(l.final_px - f.prev_rif, f.last_px - f.prev_rif) AS retained
FROM flags f
LEFT JOIN last_session l USING (COD_AZIONE)
ORDER BY f.content_id, f.d
