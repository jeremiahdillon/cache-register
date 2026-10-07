-- inputs: census_btos
-- Census BTOS: AI use (current, last two weeks) and expected use (next six months) per two-week cycle
-- (docs/plans/2026-10-07-census-btos.md). Variables set by cachereg.build: as_of, census_btos_cutoff.
-- Each workbook uses its newest stored version on or before the cutoff (Latest-only); cycles are
-- kept when Census's scheduled publication date is on or before as_of.
-- Estimates are weighted shares of U.S. employer businesses (firm counts, not employment) answering
-- the question; "do not know" is in the denominator. Two wordings are two series, never one line:
-- `original` ("in producing goods or services", to 202520) and `current` ("in any of its business
-- functions", from 202524). Suppressed cells (RSE > 50% or disclosure) are rows with null values.

-- Every readable stored version of each workbook; `used` marks the one this build reads.
CREATE OR REPLACE TABLE btos_versions AS
WITH v AS (
    SELECT
        *,
        max(fetch_id) FILTER (WHERE fetch_date <= getvariable('census_btos_cutoff'))
            OVER (PARTITION BY file) AS used_fetch_id
    FROM stg_census_btos_versions
    WHERE readable
)
SELECT
    file,
    fetch_id,
    fetch_date,
    sha256,
    cells,
    newest_cycle,
    fetch_id = used_fetch_id AS used,
    lag(fetch_id) OVER (PARTITION BY file ORDER BY fetch_id) AS previous_fetch_id
FROM v
ORDER BY file, fetch_id;

CREATE OR REPLACE TABLE btos_ai_use AS
SELECT
    e.cycle,
    e.wording,
    e.question,
    e.answer,
    e.breakdown,
    e.group_key,
    e.sector_code,
    s.naics,
    s.title AS naics_title,
    e.size_class,
    z.min_employees,
    z.max_employees,
    e.estimate_pct,
    e.se_pct,
    greatest(e.estimate_pct - 1.645 * e.se_pct, 0) AS low90_pct,
    least(e.estimate_pct + 1.645 * e.se_pct, 100) AS high90_pct,
    e.status,
    c.collection_start,
    c.collection_end,
    c.reference_start,
    c.reference_end,
    c.publication_date,
    c.sample_year,
    c.first_of_sample_year,
    e.file,
    e.fetch_id
FROM stg_census_btos_estimates e
JOIN btos_versions v ON v.file = e.file AND v.fetch_id = e.fetch_id AND v.used
JOIN stg_census_btos_cycles c ON c.cycle = e.cycle
LEFT JOIN stg_census_btos_sectors s ON s.code = e.sector_code
LEFT JOIN stg_census_btos_size_classes z ON z.size_class = e.size_class
WHERE c.publication_date <= getvariable('as_of');

-- Where a line must break: the wording change, cycles with no collection (the Oct–Nov 2025
-- shutdown), and the start of each annual sample, within the span of the AI series.
CREATE OR REPLACE TABLE btos_series_breaks AS
WITH span AS (SELECT min(cycle) AS first_cycle, max(cycle) AS last_cycle FROM btos_ai_use),
wording AS (
    SELECT
        max(cycle) FILTER (WHERE wording = 'original') AS last_before,
        min(cycle) FILTER (WHERE wording = 'current') AS first_after
    FROM btos_ai_use
)
SELECT 'wording_change' AS kind, w.last_before, w.first_after, b.reference_end AS last_reference_day,
       a.reference_start AS first_reference_day
FROM wording w
JOIN stg_census_btos_cycles b ON b.cycle = w.last_before
JOIN stg_census_btos_cycles a ON a.cycle = w.first_after
UNION ALL
SELECT 'no_collection', c.cycle, c.cycle, c.reference_start, c.reference_end
FROM stg_census_btos_cycles c, span
WHERE c.publication_date IS NULL AND c.cycle BETWEEN span.first_cycle AND span.last_cycle
UNION ALL
SELECT 'sample_year_start', c.cycle, c.cycle, c.reference_start, c.reference_end
FROM stg_census_btos_cycles c, span
WHERE c.first_of_sample_year AND c.cycle BETWEEN span.first_cycle AND span.last_cycle
ORDER BY 2, 1;

-- Cells that differ between the version used and the previous stored version of the same workbook.
-- Cycles newer than the previous version's newest are new data, not revisions. Empty = no revisions
-- seen, which is what would let the source move from Latest-only to Exact.
CREATE OR REPLACE TABLE btos_revision_check AS
WITH pair AS (
    SELECT v.file, v.fetch_id AS used_fetch_id, v.previous_fetch_id, p.newest_cycle AS previous_newest
    FROM btos_versions v JOIN btos_versions p ON p.file = v.file AND p.fetch_id = v.previous_fetch_id
    WHERE v.used
),
cur AS (SELECT e.* FROM stg_census_btos_estimates e JOIN pair ON e.file = pair.file AND e.fetch_id = pair.used_fetch_id),
prev AS (SELECT e.* FROM stg_census_btos_estimates e JOIN pair ON e.file = pair.file AND e.fetch_id = pair.previous_fetch_id),
joined AS (
    SELECT
        coalesce(cur.file, prev.file) AS file,
        coalesce(cur.wording, prev.wording) AS wording,
        coalesce(cur.question, prev.question) AS question,
        coalesce(cur.answer, prev.answer) AS answer,
        coalesce(cur.group_key, prev.group_key) AS group_key,
        coalesce(cur.cycle, prev.cycle) AS cycle,
        prev.estimate_pct AS previous_pct,
        cur.estimate_pct AS used_pct,
        prev.se_pct AS previous_se,
        cur.se_pct AS used_se,
        prev.status AS previous_status,
        cur.status AS used_status,
        CASE
            WHEN cur.cycle IS NULL THEN 'removed'
            WHEN prev.cycle IS NULL THEN 'added'
            WHEN prev.status <> cur.status THEN 'status_changed'
            ELSE 'value_changed'
        END AS change,
        prev.fetch_id AS previous_fetch_id,
        cur.fetch_id AS used_fetch_id
    FROM cur FULL JOIN prev
      ON cur.file = prev.file AND cur.wording = prev.wording AND cur.question = prev.question
     AND cur.answer = prev.answer AND cur.group_key = prev.group_key AND cur.cycle = prev.cycle
)
SELECT j.*
FROM joined j JOIN pair ON pair.file = j.file
WHERE j.cycle <= pair.previous_newest
  AND (j.change IN ('removed', 'added', 'status_changed')
       OR j.previous_pct IS DISTINCT FROM j.used_pct OR j.previous_se IS DISTINCT FROM j.used_se)
ORDER BY j.file, j.cycle, j.group_key, j.question, j.answer;

-- Per series (the `yes` answer): cycles published and suppressed, and whether the group maps to
-- NAICS (`XX`, multi-sector firms, never does).
CREATE OR REPLACE TABLE btos_coverage AS
SELECT
    breakdown,
    wording,
    question,
    group_key,
    sector_code,
    naics,
    size_class,
    count(*) FILTER (WHERE status = 'published') AS cycles_published,
    count(*) FILTER (WHERE status = 'suppressed') AS cycles_suppressed,
    min(cycle) AS first_cycle,
    max(cycle) AS last_cycle,
    sector_code IS NULL OR naics IS NOT NULL AS mapped
FROM btos_ai_use
WHERE answer = 'yes'
GROUP BY ALL
ORDER BY breakdown, group_key, wording, question;
