-- One row per (article, company) where the title names exactly one Italian listed company.
-- Frozen rule: baseline = 20 sessions before the article date,
-- daily move = PRZ_LAST / PRZ_RIF(previous session) - 1,
-- unusual = |move| >= 2 * baseline standard deviation.
-- Params: @from_date, @to_date (article publication dates, inclusive).

WITH names AS (
  SELECT
    i.COD_AZIONE,
    i.DES_AZIONE,
    i.COD_ISIN,
    -- first letter must be capitalised (unless the name itself starts lowercase, e.g. doValue): "impianti" in a sentence is not Impianti
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
    -- company names that are also everyday or foreign words in titles
    AND TRIM(i.DES_AZIONE) NOT IN ('Reti', 'Impianti', 'Energy', 'Maps', 'Simone', 'Plc', 'Circle', 'Pattern', 'Predict', 'Friends', 'Adventure', 'Tecno')
    AND i.COD_AZIONE IN (SELECT DISTINCT COD_AZIONE FROM `class-hackaton-09.financial_instruments.instruments_quotes`)
),

articles AS (
  SELECT content_id, titolo, data_pubblicazione, DATE(data_pubblicazione) AS pub_date
  FROM `class-hackaton-09.news.articles`
  WHERE DATE(data_pubblicazione) BETWEEN @from_date AND @to_date
    -- multi-stock live blogs and daily recaps are not about one company
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
  -- idx of the last session strictly before the article date ("day before")
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

window_days AS (
  -- day before, same day (if the article date is a session), and up to 5 sessions later
  SELECT a.content_id, a.COD_AZIONE, m.pub_date, s.d, s.ret, s.prev_rif, s.PRZ_LAST, s.QUANTITATIVO,
         CASE WHEN s.d < m.pub_date THEN 'day_before'
              WHEN s.d = m.pub_date THEN 'same_day'
              ELSE 'later' END AS timing,
         SAFE_DIVIDE(s.ret, b.sd) AS z,
         SAFE_DIVIDE(s.QUANTITATIVO, b.avg_qty) AS vol_x
  FROM anchored a
  JOIN matches m USING (content_id, COD_AZIONE)
  JOIN baseline b USING (content_id, COD_AZIONE)
  JOIN sessions s
    ON s.COD_AZIONE = a.COD_AZIONE AND s.idx BETWEEN a.idx_before AND a.idx_before + 6
),

peak AS (
  SELECT * EXCEPT (rk) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY content_id, COD_AZIONE ORDER BY ABS(z) DESC) AS rk
    FROM window_days
  ) WHERE rk = 1
),

last_session AS (
  SELECT COD_AZIONE, d AS last_d, PRZ_LAST AS last_px
  FROM sessions
  WHERE d = (SELECT MAX(DATE(DATA_QUOTAZ)) FROM `class-hackaton-09.financial_instruments.instruments_quotes`)
)

SELECT
  m.content_id, m.titolo, m.data_pubblicazione, m.COD_AZIONE, m.DES_AZIONE, m.COD_ISIN,
  b.n_base, b.sd AS baseline_sd,
  p.d AS move_date, p.timing, p.ret AS move, p.z, p.vol_x,
  ABS(p.z) >= 2 AS unusual,
  p.prev_rif AS px_before_move, p.PRZ_LAST AS px_after_move,
  l.last_d, l.last_px,
  SAFE_DIVIDE(l.last_px - p.prev_rif, p.PRZ_LAST - p.prev_rif) AS retained
FROM matches m
JOIN baseline b USING (content_id, COD_AZIONE)
JOIN peak p USING (content_id, COD_AZIONE)
LEFT JOIN last_session l USING (COD_AZIONE)
WHERE m.n_companies = 1 AND b.n_base = 20
ORDER BY ABS(p.z) DESC
