-- Daily prices for the company pages: one row per (COD_AZIONE, session).
-- Move follows the frozen rule: PRZ_LAST / previous session's PRZ_RIF - 1.
-- z_trailing = move / standard deviation of the 20 sessions before this one
-- (the per-day analogue of the article baseline; NULL until 20 moves exist).
-- Params: @cod_azioni ARRAY<STRING>, @from_date DATE, @to_date DATE

WITH sessions AS (
  SELECT
    COD_AZIONE,
    DATE(DATA_QUOTAZ) AS d,
    PRZ_LAST,
    QUANTITATIVO,
    SAFE_DIVIDE(PRZ_LAST, LAG(PRZ_RIF) OVER w) - 1 AS ret
  FROM `class-hackaton-09.financial_instruments.instruments_quotes`
  WHERE COD_AZIONE IN UNNEST(@cod_azioni)
    AND PRZ_LAST > 0 AND PRZ_RIF > 0
    AND DATE(DATA_QUOTAZ) <= @to_date
  WINDOW w AS (PARTITION BY COD_AZIONE ORDER BY DATA_QUOTAZ)
),

scored AS (
  SELECT
    *,
    COUNT(ret) OVER b AS n_base,
    STDDEV_SAMP(ret) OVER b AS sd
  FROM sessions
  WINDOW b AS (PARTITION BY COD_AZIONE ORDER BY d ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)
)

SELECT
  COD_AZIONE,
  d,
  PRZ_LAST AS prz_last,
  QUANTITATIVO AS volume,
  ret AS move,
  IF(n_base = 20, SAFE_DIVIDE(ret, sd), NULL) AS z_trailing
FROM scored
WHERE d >= @from_date
ORDER BY COD_AZIONE, d
