-- One row per (article, company) where the title names exactly one Italian listed company.
-- Frozen rule: baseline = 20 sessions before the article date,
-- daily move = PRZ_LAST / PRZ_RIF(previous session) - 1,
-- unusual = |move| >= 2 * baseline standard deviation.
-- Params: @from_date, @to_date (article publication dates, inclusive).

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
  SELECT content_id, titolo, data_pubblicazione, DATE(data_pubblicazione) AS pub_date
  FROM `class-hackaton-09.news.articles`
  WHERE DATE(data_pubblicazione) BETWEEN @from_date AND @to_date
    -- multi-stock live blogs and daily recaps are not about one company
    AND NOT REGEXP_CONTAINS(titolo, r"^(Borse oggi in diretta|Cos.è successo oggi)")
),

-- Exclusions are scoped to the matched instrument so a Del Vecchio / Intesa
-- analyst aside does not drop the real company named in the same headline.
matched_rows AS (
  SELECT DISTINCT a.content_id, a.titolo, a.data_pubblicazione, a.pub_date,
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
