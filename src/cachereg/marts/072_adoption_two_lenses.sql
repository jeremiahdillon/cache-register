-- inputs: ramp_ai_index, census_btos
-- Analysis (c) "Two lenses on adoption": Ramp's paid adoption beside BTOS's self-reported AI use, by
-- month, overall and by NAICS sector (docs/plans/2026-10-07-census-btos.md). Uses ramp_adoption,
-- ramp_census_restated (mart 060) and btos_ai_monthly (mart 071).
-- The lenses measure different things and are rows, never a ratio or a difference:
--   ramp_paid           share of businesses on Ramp with AI spend in the month (observed, paid)
--   btos_use_current    share of U.S. employer businesses reporting AI use in the last two weeks
--   btos_use_expected   share expecting to use AI in the next six months
-- Sectors are Ramp's adoption sectors. Ramp's "Technology and media" -> 51 is assumed
-- (`naics_assumed`), so BTOS 54 rides along as `role = 'sensitivity'`. Sizes are not joined: Ramp's
-- Large / Medium / Small have no published thresholds.

CREATE OR REPLACE TABLE adoption_two_lenses AS
WITH ramp_sectors AS (
    SELECT DISTINCT naics, naics_assumed FROM ramp_adoption WHERE series_kind = 'sector' AND naics IS NOT NULL
),
ramp AS (
    SELECT
        month,
        CASE series_kind WHEN 'overall' THEN 'overall' ELSE 'sector' END AS scope,
        naics,
        naics_title,
        coalesce(naics_assumed, false) AS naics_assumed,
        'matched' AS role,
        'ramp_paid' AS lens,
        CAST(NULL AS VARCHAR) AS wording,
        adoption_pct AS pct,
        CAST(NULL AS DOUBLE) AS se,
        CAST(NULL AS DOUBLE) AS low90_pct,
        CAST(NULL AS DOUBLE) AS high90_pct,
        CAST(NULL AS BOOLEAN) AS partial,
        CAST(NULL AS BOOLEAN) AS has_suppression
    FROM ramp_adoption
    WHERE series_kind = 'overall' OR (series_kind = 'sector' AND naics IS NOT NULL)
),
btos AS (
    SELECT
        b.month,
        CASE b.breakdown WHEN 'national' THEN 'overall' ELSE 'sector' END AS scope,
        b.naics,
        b.naics_title,
        coalesce(r.naics_assumed, false) AS naics_assumed,
        CASE WHEN b.breakdown = 'sector' AND r.naics IS NULL THEN 'sensitivity' ELSE 'matched' END AS role,
        CASE b.question WHEN 'ai_current' THEN 'btos_use_current' ELSE 'btos_use_expected' END AS lens,
        b.wording,
        b.pct,
        b.se,
        b.low90_pct,
        b.high90_pct,
        b.partial,
        b.has_suppression
    FROM btos_ai_monthly b
    LEFT JOIN ramp_sectors r ON r.naics = b.naics
    WHERE b.breakdown = 'national'
       OR (b.breakdown = 'sector' AND (r.naics IS NOT NULL
           OR (b.naics = '54' AND EXISTS (SELECT 1 FROM ramp_sectors WHERE naics = '51' AND naics_assumed))))
)
SELECT * FROM ramp
UNION ALL
SELECT * FROM btos
ORDER BY scope, naics NULLS FIRST, lens, month;

-- Ramp's "Census Estimate" against our BTOS data under Ramp's own rules: the unweighted mean of the
-- national current-use `yes` cycles grouped by the month their collection starts, or ends. Ramp used
-- the start rule through May 2026 and the end rule from June 2026 (first real build, 2026-10-08), so a
-- month agrees when either rule reproduces it. Checks both adapters at once; a month where neither does
-- points to a Census revision, a changed Ramp method, or a wrong import.
CREATE OR REPLACE TABLE btos_ramp_census_check AS
WITH national AS (
    SELECT *
    FROM btos_ai_use
    WHERE breakdown = 'national' AND question = 'ai_current' AND answer = 'yes' AND status = 'published'
),
by_start AS (
    SELECT CAST(date_trunc('month', collection_start) AS DATE) AS month, wording, avg(estimate_pct) AS pct,
           count(*) AS n_cycles
    FROM national GROUP BY ALL
),
by_end AS (
    SELECT CAST(date_trunc('month', collection_end) AS DATE) AS month, avg(estimate_pct) AS pct, count(*) AS n_cycles
    FROM national GROUP BY ALL
),
span AS (SELECT min(month) AS first_month, max(month) AS last_month FROM ramp_census_restated),
joined AS (
    SELECT
        coalesce(r.month, s.month, e.month) AS month,
        r.adoption_pct AS ramp_pct,
        r.census_question_version,
        s.wording,
        s.pct AS start_rule_pct,
        s.n_cycles AS start_rule_cycles,
        e.pct AS end_rule_pct,
        e.n_cycles AS end_rule_cycles,
        abs(r.adoption_pct - s.pct) <= 0.005 AS start_ok,
        abs(r.adoption_pct - e.pct) <= 0.005 AS end_ok
    FROM ramp_census_restated r
    FULL JOIN by_start s ON s.month = r.month
    FULL JOIN by_end e ON e.month = coalesce(r.month, s.month)
)
SELECT
    j.month,
    j.ramp_pct,
    j.census_question_version,
    j.wording,
    j.start_rule_pct,
    j.start_rule_cycles,
    j.end_rule_pct,
    j.end_rule_cycles,
    CASE
        WHEN j.ramp_pct IS NULL THEN NULL
        WHEN coalesce(j.start_ok, false) AND coalesce(j.end_ok, false) THEN 'both'
        WHEN coalesce(j.start_ok, false) THEN 'collection_start'
        WHEN coalesce(j.end_ok, false) THEN 'collection_end'
        ELSE 'neither'
    END AS matches,
    CASE WHEN j.ramp_pct IS NOT NULL THEN coalesce(j.start_ok, false) OR coalesce(j.end_ok, false) END AS agree,
    CASE
        WHEN j.census_question_version IS NULL OR j.wording IS NULL THEN NULL
        ELSE (j.census_question_version LIKE 'pre%') = (j.wording = 'original')
    END AS wording_agrees
FROM joined j
CROSS JOIN span
WHERE j.month BETWEEN span.first_month AND span.last_month
ORDER BY j.month;
