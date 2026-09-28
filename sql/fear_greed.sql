-- Daily tape legs, 2σ shock counts, and the narrative percentile for each sector.
-- Weight tilt is applied in scripts/fear_greed.py.
-- Shock: |PRZ_LAST / previous PRZ_RIF - 1| >= 2 * stddev of the previous 20 sessions.
-- Narrative: an article is assigned when its cosine to the sector vector is at least 0.40.
-- Fear pole = mean embedding of assigned articles on bottom-quintile sector-return days.
-- Greed pole = top quintile.
-- narrative_pct = 100 * CUME_DIST of cosine(today, greed) - cosine(today, fear).

WITH members AS (
  SELECT sector, cod FROM UNNEST([
    STRUCT('banche' AS sector, 'AMBR' AS cod),
    STRUCT('banche' AS sector, 'CRIT' AS cod),
    STRUCT('banche' AS sector, 'BAMI' AS cod),
    STRUCT('banche' AS sector, 'BPEMI' AS cod),
    STRUCT('banche' AS sector, 'FBK' AS cod),
    STRUCT('banche' AS sector, 'MEDIOB' AS cod),
    STRUCT('banche' AS sector, 'BMPS' AS cod),
    STRUCT('assicurazioni' AS sector, 'GENE' AS cod),
    STRUCT('assicurazioni' AS sector, 'UNIPOL' AS cod),
    STRUCT('energia' AS sector, 'ENISPA' AS cod),
    STRUCT('energia' AS sector, 'ENEL' AS cod),
    STRUCT('energia' AS sector, 'SAIP' AS cod),
    STRUCT('energia' AS sector, 'TRN' AS cod),
    STRUCT('energia' AS sector, 'SRG' AS cod),
    STRUCT('energia' AS sector, 'IG' AS cod),
    STRUCT('energia' AS sector, 'AEM' AS cod),
    STRUCT('industriali' AS sector, 'FINME' AS cod),
    STRUCT('industriali' AS sector, 'PRY' AS cod),
    STRUCT('industriali' AS sector, 'INTP' AS cod),
    STRUCT('industriali' AS sector, 'COGE' AS cod),
    STRUCT('industriali' AS sector, 'PIRC' AS cod),
    STRUCT('industriali' AS sector, 'STM' AS cod),
    STRUCT('industriali' AS sector, 'FIAT' AS cod),
    STRUCT('lusso' AS sector, 'MONC' AS cod),
    STRUCT('lusso' AS sector, 'BC' AS cod),
    STRUCT('lusso' AS sector, 'RACE' AS cod),
    STRUCT('lusso' AS sector, 'CPR' AS cod),
    STRUCT('salute' AS sector, 'AMP' AS cod),
    STRUCT('salute' AS sector, 'DIA' AS cod),
    STRUCT('salute' AS sector, 'REC' AS cod)
  ])
),

quotes AS (
  SELECT sector, cod, d, PRZ_LAST, PRZ_RIF, PRZ_MIN, PRZ_MAX, qty
  FROM (
    SELECT
      m.sector,
      q.COD_AZIONE AS cod,
      DATE(q.DATA_QUOTAZ) AS d,
      q.PRZ_LAST,
      q.PRZ_RIF,
      q.PRZ_MIN,
      q.PRZ_MAX,
      IFNULL(q.QUANTITATIVO, 0) AS qty,
      ROW_NUMBER() OVER (
        PARTITION BY q.COD_AZIONE, DATE(q.DATA_QUOTAZ)
        ORDER BY q.DATA_QUOTAZ DESC
      ) AS rn
    FROM `class-hackaton-09.financial_instruments.instruments_quotes` q
    JOIN members m ON m.cod = q.COD_AZIONE
    WHERE q.PRZ_LAST > 0 AND q.PRZ_RIF > 0
  )
  WHERE rn = 1
),

name_day AS (
  SELECT
    sector,
    cod,
    d,
    ret,
    qty,
    PRZ_LAST,
    STDDEV_SAMP(ret) OVER w_base AS sd20,
    COUNT(ret) OVER w_base AS n_base,
    MAX(PRZ_MAX) OVER w_52 AS high_52,
    MIN(PRZ_MIN) OVER w_52 AS low_52,
    COUNT(PRZ_MAX) OVER w_52 AS n_high_obs,
    COUNT(PRZ_MIN) OVER w_52 AS n_low_obs
  FROM (
    SELECT
      sector, cod, d, qty, PRZ_LAST, PRZ_MIN, PRZ_MAX,
      SAFE_DIVIDE(PRZ_LAST, LAG(PRZ_RIF) OVER (PARTITION BY cod ORDER BY d)) - 1 AS ret
    FROM quotes
  )
  WINDOW
    w_base AS (PARTITION BY cod ORDER BY d ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING),
    w_52 AS (PARTITION BY cod ORDER BY d ROWS BETWEEN 251 PRECEDING AND CURRENT ROW)
),

sector_day AS (
  SELECT
    sector,
    d,
    AVG(ret) AS sector_ret,
    COUNTIF(n_base = 20 AND sd20 > 0) AS names,
    COUNTIF(n_base = 20 AND sd20 > 0 AND ABS(ret) >= 2 * sd20) AS shocks,
    COUNTIF(n_base = 20 AND sd20 > 0 AND ABS(ret) >= 2 * sd20 AND ret < 0) AS shocks_down,
    COUNTIF(n_base = 20 AND sd20 > 0 AND ABS(ret) >= 2 * sd20 AND ret > 0) AS shocks_up,
    COUNTIF(
      n_high_obs >= 252 AND n_low_obs >= 252 AND high_52 > 0 AND PRZ_LAST >= 0.95 * high_52
    ) AS n_near_high,
    COUNTIF(
      n_high_obs >= 252 AND n_low_obs >= 252 AND low_52 > 0 AND PRZ_LAST <= 1.05 * low_52
    ) AS n_near_low,
    COUNTIF(n_high_obs >= 252 AND n_low_obs >= 252 AND high_52 > 0 AND low_52 > 0) AS n_strength,
    SUM(IF(ret > 0, qty, 0)) AS up_qty,
    SUM(IF(ret < 0, qty, 0)) AS down_qty,
    SUM(qty) AS total_qty
  FROM name_day
  WHERE ret IS NOT NULL
  GROUP BY sector, d
),

sector_window AS (
  SELECT
    sector,
    d,
    sector_ret,
    names,
    shocks,
    shocks_down,
    shocks_up,
    n_strength,
    SAFE_DIVIDE(n_near_high - n_near_low, n_strength) AS strength_raw,
    SAFE_DIVIDE(up_qty - down_qty, NULLIF(total_qty, 0)) AS breadth_raw,
    EXP(SUM(SAFE.LN(1 + sector_ret)) OVER w125) - 1 AS momentum_raw,
    COUNT(SAFE.LN(1 + sector_ret)) OVER w125 AS n_mom,
    STDDEV_SAMP(sector_ret) OVER w20 AS vol_raw,
    COUNT(sector_ret) OVER w20 AS n_vol
  FROM sector_day
  WINDOW
    w125 AS (PARTITION BY sector ORDER BY d ROWS BETWEEN 124 PRECEDING AND CURRENT ROW),
    w20 AS (PARTITION BY sector ORDER BY d ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
),

market_days AS (
  SELECT
    sector, d, momentum_raw, strength_raw, breadth_raw, vol_raw,
    shocks, shocks_down, shocks_up, names
  FROM sector_window
  WHERE d >= DATE '2024-01-24'
    AND n_mom = 125
    AND n_vol = 20
    AND n_strength > 0
    AND strength_raw IS NOT NULL
    AND breadth_raw IS NOT NULL
    AND momentum_raw IS NOT NULL
    AND vol_raw IS NOT NULL
    AND vol_raw > 0
),

quintiles AS (
  SELECT
    sector,
    d,
    NTILE(5) OVER (PARTITION BY sector ORDER BY sector_ret) AS tile
  FROM sector_day
  WHERE d >= DATE '2024-01-24'
),

sector_vec AS (
  SELECT sector, ARRAY_AGG(avg_v ORDER BY pos) AS embedding
  FROM (
    SELECT m.sector, pos, AVG(v) AS avg_v
    FROM members m
    JOIN `class-hackaton-09.financial_instruments.instruments_embeddings` e
      ON e.COD_AZIONE = m.cod
    CROSS JOIN UNNEST(e.embedding) AS v WITH OFFSET pos
    WHERE ARRAY_LENGTH(e.embedding) = 512
    GROUP BY m.sector, pos
  )
  GROUP BY sector
  HAVING COUNT(*) = 512
),

articles AS (
  SELECT
    content_id,
    titolo,
    DATE(TIMESTAMP(data_pubblicazione), 'Europe/Rome') AS pub_date
  FROM `class-hackaton-09.news.articles`
  WHERE DATE(TIMESTAMP(data_pubblicazione), 'Europe/Rome') >= DATE '2024-01-24'
),

scores AS (
  SELECT
    a.content_id,
    a.pub_date,
    sv.sector,
    1 - ML.DISTANCE(e.embedding, sv.embedding, 'COSINE') AS cosine
  FROM articles a
  JOIN `class-hackaton-09.news.articles_embeddings` e USING (content_id)
  CROSS JOIN sector_vec sv
  WHERE ARRAY_LENGTH(e.embedding) = 512
),

best AS (
  SELECT content_id, pub_date, sector, cosine, titolo
  FROM (
    SELECT s.content_id, s.pub_date, s.sector, s.cosine, a.titolo
    FROM scores s
    JOIN articles a USING (content_id)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY s.content_id ORDER BY s.cosine DESC) = 1
      AND s.cosine >= 0.40
  )
),

heads AS (
  SELECT
    sector,
    pub_date AS d,
    TO_JSON_STRING(ARRAY_AGG(titolo ORDER BY cosine DESC LIMIT 3)) AS headlines
  FROM best
  GROUP BY sector, pub_date
),

pole_src AS (
  SELECT b.content_id, b.sector, IF(q.tile = 1, 'fear', 'greed') AS kind
  FROM best b
  JOIN quintiles q
    ON q.sector = b.sector AND q.d = b.pub_date
  WHERE q.tile IN (1, 5)
),

poles AS (
  SELECT sector, kind, ARRAY_AGG(avg_v ORDER BY pos) AS embedding
  FROM (
    SELECT p.sector, p.kind, pos, AVG(v) AS avg_v
    FROM pole_src p
    JOIN `class-hackaton-09.news.articles_embeddings` e USING (content_id)
    CROSS JOIN UNNEST(e.embedding) AS v WITH OFFSET pos
    WHERE ARRAY_LENGTH(e.embedding) = 512
    GROUP BY p.sector, p.kind, pos
  )
  GROUP BY sector, kind
  HAVING COUNT(*) = 512
),

day_vec AS (
  SELECT sector, d, ARRAY_AGG(avg_v ORDER BY pos) AS embedding
  FROM (
    SELECT b.sector, b.pub_date AS d, pos, AVG(v) AS avg_v
    FROM best b
    JOIN `class-hackaton-09.news.articles_embeddings` e USING (content_id)
    CROSS JOIN UNNEST(e.embedding) AS v WITH OFFSET pos
    WHERE ARRAY_LENGTH(e.embedding) = 512
    GROUP BY b.sector, b.pub_date, pos
  )
  GROUP BY sector, d
  HAVING COUNT(*) = 512
),

narrative AS (
  SELECT
    dv.sector,
    dv.d,
    (1 - ML.DISTANCE(dv.embedding, g.embedding, 'COSINE'))
      - (1 - ML.DISTANCE(dv.embedding, f.embedding, 'COSINE')) AS narrative_raw
  FROM day_vec dv
  JOIN poles g ON g.sector = dv.sector AND g.kind = 'greed'
  JOIN poles f ON f.sector = dv.sector AND f.kind = 'fear'
),

joined AS (
  SELECT
    m.sector,
    m.d,
    m.momentum_raw,
    m.strength_raw,
    m.breadth_raw,
    m.vol_raw,
    n.narrative_raw,
    m.shocks,
    m.shocks_down,
    m.shocks_up,
    m.names,
    IFNULL(h.headlines, '[]') AS headlines
  FROM market_days m
  LEFT JOIN narrative n USING (sector, d)
  LEFT JOIN heads h USING (sector, d)
),

ranked AS (
  SELECT
    sector,
    d,
    100 * CUME_DIST() OVER (PARTITION BY sector ORDER BY narrative_raw) AS narrative_pct
  FROM joined
  WHERE narrative_raw IS NOT NULL
)

SELECT
  j.sector,
  j.d,
  j.momentum_raw,
  j.strength_raw,
  j.breadth_raw,
  j.vol_raw,
  j.narrative_raw,
  r.narrative_pct,
  j.shocks,
  j.shocks_down,
  j.shocks_up,
  j.names,
  j.headlines
FROM joined j
LEFT JOIN ranked r USING (sector, d)
ORDER BY j.sector, j.d
