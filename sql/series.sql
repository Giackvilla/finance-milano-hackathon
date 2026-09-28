-- Chart series: one row per (article, session) around publication.
-- Same company match, move, and baseline as tape_window.sql (frozen rule).
-- Window: 25 sessions before idx_before through last session on/before 2026-09-23,
--         capped at 40 sessions after idx_before.
-- rel = idx - idx_before - 1  (session before article = -1; first on/after = 0).
-- Params: @content_ids ARRAY<STRING>

WITH names AS (
  SELECT
    i.COD_AZIONE,
    i.DES_AZIONE,
    i.COD_ISIN,
    CONCAT(
      r'\b',
      IF(REGEXP_CONTAINS(SUBSTR(TRIM(i.DES_AZIONE), 1, 1), r'^[a-z]$'),
         CONCAT('[', SUBSTR(TRIM(i.DES_AZIONE), 1, 1), UPPER(SUBSTR(TRIM(i.DES_AZIONE), 1, 1)), ']'),
         REGEXP_REPLACE(SUBSTR(TRIM(i.DES_AZIONE), 1, 1), r'([.^$|()\[\]{}*+?\\])', r'\\\1')),
      r'(?i:', REGEXP_REPLACE(SUBSTR(TRIM(i.DES_AZIONE), 2), r'([.^$|()\[\]{}*+?\\])', r'\\\1'), r')\b'
    ) AS pattern
  FROM `class-hackaton-09.financial_instruments.instruments_info` i
  WHERE i.COD_TIPO = 'ORD'
    AND i.COD_ISIN LIKE 'IT%'
    AND LENGTH(TRIM(i.DES_AZIONE)) >= 3
    AND TRIM(i.DES_AZIONE) NOT IN ('Reti', 'Impianti', 'Energy', 'Maps', 'Simone', 'Plc', 'Circle', 'Pattern', 'Predict', 'Friends', 'Adventure', 'Tecno')
    AND i.COD_AZIONE IN (SELECT DISTINCT COD_AZIONE FROM `class-hackaton-09.financial_instruments.instruments_quotes`)
),

articles AS (
  SELECT
    content_id,
    titolo,
    data_pubblicazione,
    DATETIME(TIMESTAMP(data_pubblicazione, "UTC"), "Europe/Rome") AS pub_local,
    DATE(DATETIME(TIMESTAMP(data_pubblicazione, "UTC"), "Europe/Rome")) AS pub_date
  FROM `class-hackaton-09.news.articles`
  WHERE content_id IN UNNEST(@content_ids)
    AND NOT REGEXP_CONTAINS(titolo, r"^(Borse oggi in diretta|Cos.è successo oggi)")
),

matches AS (
  SELECT a.*, n.COD_AZIONE, n.DES_AZIONE, n.COD_ISIN,
         COUNT(*) OVER (PARTITION BY a.content_id) AS n_companies
  FROM articles a
  JOIN names n ON REGEXP_CONTAINS(a.titolo, n.pattern)
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
         MIN(s.d) AS base_from,
         MAX(s.d) AS base_to
  FROM anchored a JOIN sessions s
    ON s.COD_AZIONE = a.COD_AZIONE AND s.idx BETWEEN a.idx_before - 19 AND a.idx_before
  GROUP BY 1, 2
),

px_before AS (
  SELECT a.content_id, a.COD_AZIONE, s.PRZ_LAST AS px_before
  FROM anchored a
  JOIN sessions s ON s.COD_AZIONE = a.COD_AZIONE AND s.idx = a.idx_before
),

stock_last AS (
  SELECT COD_AZIONE, MAX(idx) AS max_idx
  FROM sessions
  WHERE d <= DATE '2026-09-23'
  GROUP BY 1
)

SELECT
  m.content_id,
  m.COD_AZIONE,
  m.DES_AZIONE,
  m.pub_local,
  s.d,
  s.idx - a.idx_before - 1 AS rel,
  s.PRZ_LAST AS prz_last,
  s.PRZ_RIF AS prz_rif,
  IF(
    s.PRZ_APERTURA > 0
    AND (
      NOT (s.PRZ_MIN > 0 AND s.PRZ_MAX > 0)
      OR (s.PRZ_APERTURA BETWEEN s.PRZ_MIN * 0.9999 AND s.PRZ_MAX * 1.0001)
    ),
    s.PRZ_APERTURA,
    NULL
  ) AS open_px,
  s.QUANTITATIVO AS quantitativo,
  s.ret AS move,
  SAFE_DIVIDE(s.ret, b.sd) AS z,
  ABS(SAFE_DIVIDE(s.ret, b.sd)) >= 2 AS unusual,
  (s.idx BETWEEN a.idx_before - 19 AND a.idx_before) AS in_baseline,
  b.sd AS baseline_sd,
  b.base_from,
  b.base_to,
  SAFE_DIVIDE(s.PRZ_LAST, p.px_before) * 100 AS index_100
FROM anchored a
JOIN matches m USING (content_id, COD_AZIONE)
JOIN baseline b USING (content_id, COD_AZIONE)
JOIN px_before p USING (content_id, COD_AZIONE)
JOIN stock_last sl ON sl.COD_AZIONE = a.COD_AZIONE
JOIN sessions s ON s.COD_AZIONE = a.COD_AZIONE
WHERE m.n_companies = 1
  AND b.n_base = 20
  AND s.idx BETWEEN a.idx_before - 25 AND LEAST(sl.max_idx, a.idx_before + 40)
  AND s.d <= DATE '2026-09-23'
ORDER BY m.content_id, s.d
