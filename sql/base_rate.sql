-- Base rate of "unusual" sessions among Italian ORD stocks.
-- Daily move = PRZ_LAST / previous session PRZ_RIF - 1 (same as events.sql).
-- (a) sd over 20 sessions ending at this session inclusive — matches day_before.
-- (b) sd over 20 sessions strictly before — matches same_day / later / reaction.
-- Params: none. Evaluate sessions with d >= 2021-02-01; require n=20 and sd>0.

WITH it AS (
  SELECT COD_AZIONE
  FROM `class-hackaton-09.financial_instruments.instruments_info`
  WHERE COD_TIPO = 'ORD'
    AND COD_ISIN LIKE 'IT%'
),

sessions AS (
  SELECT
    COD_AZIONE,
    DATE(DATA_QUOTAZ) AS d,
    SAFE_DIVIDE(PRZ_LAST, LAG(PRZ_RIF) OVER w) - 1 AS ret,
    ROW_NUMBER() OVER w AS idx
  FROM `class-hackaton-09.financial_instruments.instruments_quotes`
  WHERE COD_AZIONE IN (SELECT COD_AZIONE FROM it)
    AND PRZ_LAST > 0 AND PRZ_RIF > 0
  WINDOW w AS (PARTITION BY COD_AZIONE ORDER BY DATA_QUOTAZ)
),

scored AS (
  SELECT
    d,
    ret,
    STDDEV_SAMP(ret) OVER (
      PARTITION BY COD_AZIONE ORDER BY idx
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS sd_a,
    COUNT(ret) OVER (
      PARTITION BY COD_AZIONE ORDER BY idx
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS n_a,
    STDDEV_SAMP(ret) OVER (
      PARTITION BY COD_AZIONE ORDER BY idx
      ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
    ) AS sd_b,
    COUNT(ret) OVER (
      PARTITION BY COD_AZIONE ORDER BY idx
      ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
    ) AS n_b
  FROM sessions
  WHERE d >= DATE '2021-02-01'
    AND ret IS NOT NULL
)

SELECT
  COUNTIF(n_a = 20 AND sd_a > 0) AS n_sessions_a,
  COUNTIF(n_a = 20 AND sd_a > 0 AND ABS(ret) >= 2 * sd_a) AS n_unusual_a,
  SAFE_DIVIDE(
    COUNTIF(n_a = 20 AND sd_a > 0 AND ABS(ret) >= 2 * sd_a),
    COUNTIF(n_a = 20 AND sd_a > 0)
  ) AS share_a,
  COUNTIF(n_b = 20 AND sd_b > 0) AS n_sessions_b,
  COUNTIF(n_b = 20 AND sd_b > 0 AND ABS(ret) >= 2 * sd_b) AS n_unusual_b,
  SAFE_DIVIDE(
    COUNTIF(n_b = 20 AND sd_b > 0 AND ABS(ret) >= 2 * sd_b),
    COUNTIF(n_b = 20 AND sd_b > 0)
  ) AS share_b
FROM scored
