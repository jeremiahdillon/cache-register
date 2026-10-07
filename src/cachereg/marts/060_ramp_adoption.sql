-- inputs: ramp_ai_index
-- Ramp AI Index: per-cut coverage, monthly adoption and the label map (docs/plans/2026-10-07-ramp-ai-index.md).
-- Variables set by cachereg.build: as_of, ramp_ai_index_cutoff.
-- Every import holds one cut's full history. Each cut uses its latest import on or before the
-- cutoff (Latest-only); cuts are never filled from one another. Periods after as_of are dropped.
-- Population: businesses on Ramp (card and bill pay), not all US businesses.

-- One row per cut in the adapter's registry, imported or not: which import is used, and gaps.
CREATE OR REPLACE TABLE ramp_cut_coverage AS
WITH used AS (
    SELECT cut, max(fetch_id) AS import_used
    FROM stg_ramp_ai_index_imports
    WHERE CAST(fetched_at AS DATE) <= getvariable('ramp_ai_index_cutoff')
    GROUP BY cut
), firsts AS (
    SELECT cut, min(CAST(fetched_at AS DATE)) AS first_import FROM stg_ramp_ai_index_imports GROUP BY cut
)
SELECT
    c.position,
    c.cut,
    c.menu,
    c.staged_table,
    f.first_import,
    u.import_used,
    u.import_used IS NOT NULL AS present_at_cutoff,
    u.import_used IS NULL AND f.first_import IS NOT NULL AS cut_after_cutoff,
    CAST(i.fetched_at AS DATE) AS imported_on,
    i.via,
    i.first_period,
    i.last_period
FROM stg_ramp_ai_index_cuts c
LEFT JOIN firsts f USING (cut)
LEFT JOIN used u USING (cut)
LEFT JOIN stg_ramp_ai_index_imports i ON i.cut = c.cut AND i.fetch_id = u.import_used
ORDER BY c.position;

-- Adoption: share of businesses (in Ramp's sample) with AI spend in the month. The overall series
-- comes from adoption/overall only, labs from adoption/models, sectors and sizes from their cuts.
-- Lab shares do not sum to the overall share: a business can pay several labs.
CREATE OR REPLACE TABLE ramp_adoption AS
SELECT
    a.month,
    a.series_kind,
    a.series_label,
    v.vendor_id,
    s.naics,
    s.title AS naics_title,
    s.assumed AS naics_assumed,
    a.adoption_pct,
    a.mom_pp,
    a.yoy_pp,
    CASE WHEN a.series_kind = 'vendor'
         THEN rank() OVER (PARTITION BY a.month, a.series_kind ORDER BY a.adoption_pct DESC NULLS LAST) END
        AS vendor_rank,
    a.cut,
    a.fetch_id
FROM stg_ramp_ai_index_adoption a
JOIN ramp_cut_coverage c ON c.cut = a.cut AND c.import_used = a.fetch_id
LEFT JOIN dim_vendor_alias v ON a.series_kind = 'vendor' AND v.source = 'ramp' AND v.alias = a.series_label
LEFT JOIN stg_ramp_ai_index_sectors s ON a.series_kind = 'sector' AND s.label = a.series_label
WHERE a.month <= getvariable('as_of')
  AND a.series_kind IN ('overall', 'vendor', 'sector', 'size')
  AND NOT (a.series_kind = 'overall' AND a.cut <> 'adoption/overall');

-- Ramp Overall as it appears in both adoption cuts; a difference means the two were imported on
-- different days and Ramp revised in between (re-import both), or the views disagree.
CREATE OR REPLACE TABLE ramp_overall_check AS
WITH o AS (
    SELECT a.cut, a.month, a.adoption_pct
    FROM stg_ramp_ai_index_adoption a
    JOIN ramp_cut_coverage c ON c.cut = a.cut AND c.import_used = a.fetch_id
    WHERE a.series_kind = 'overall' AND a.month <= getvariable('as_of')
)
SELECT
    month,
    max(adoption_pct) FILTER (WHERE cut = 'adoption/overall') AS overall_pct,
    max(adoption_pct) FILTER (WHERE cut = 'adoption/models') AS models_view_pct,
    overall_pct - models_view_pct AS difference_pp,
    coalesce(abs(overall_pct - models_view_pct) > 0.005, false) AS disagree
FROM o
GROUP BY month
ORDER BY month;

-- Ramp's restatement of the Census Bureau's BTOS (in adoption/overall). Kept apart and never used
-- as a lens: the BTOS source itself is. Never draw it as one line across the question-wording change.
CREATE OR REPLACE TABLE ramp_census_restated AS
SELECT a.month, a.adoption_pct, a.mom_pp, a.census_question_version, a.fetch_id
FROM stg_ramp_ai_index_adoption a
JOIN ramp_cut_coverage c ON c.cut = a.cut AND c.import_used = a.fetch_id
WHERE a.series_kind = 'census' AND a.month <= getvariable('as_of')
ORDER BY a.month;

-- Labels that join to no vendor or sector (counted, never dropped from the series).
CREATE OR REPLACE TABLE ramp_label_coverage AS
WITH labels AS (
    SELECT DISTINCT 'vendor' AS kind, a.cut, a.series_label AS label
    FROM stg_ramp_ai_index_adoption a JOIN ramp_cut_coverage c ON c.cut = a.cut AND c.import_used = a.fetch_id
    WHERE a.series_kind = 'vendor'
    UNION
    SELECT DISTINCT 'vendor', t.cut, t.maker_label
    FROM stg_ramp_ai_index_token_index t JOIN ramp_cut_coverage c ON c.cut = t.cut AND c.import_used = t.fetch_id
    UNION
    SELECT DISTINCT 'sector', a.cut, a.series_label
    FROM stg_ramp_ai_index_adoption a JOIN ramp_cut_coverage c ON c.cut = a.cut AND c.import_used = a.fetch_id
    WHERE a.series_kind = 'sector'
    UNION
    SELECT DISTINCT 'sector', p.cut, p.group_label
    FROM stg_ramp_ai_index_spend_per_employee p
    JOIN ramp_cut_coverage c ON c.cut = p.cut AND c.import_used = p.fetch_id
    WHERE p.dimension = 'sector'
    UNION
    SELECT DISTINCT 'sector', s.cut, s.sector_label
    FROM stg_ramp_ai_index_spend_share s JOIN ramp_cut_coverage c ON c.cut = s.cut AND c.import_used = s.fetch_id
    WHERE s.scope = 'sector'
)
SELECT
    l.kind,
    l.cut,
    l.label,
    coalesce(v.vendor_id, s.naics) AS mapped_to,
    coalesce(v.vendor_id, s.naics) IS NOT NULL AS mapped
FROM labels l
LEFT JOIN dim_vendor_alias v ON l.kind = 'vendor' AND v.source = 'ramp' AND v.alias = l.label
LEFT JOIN stg_ramp_ai_index_sectors s ON l.kind = 'sector' AND s.label = l.label
ORDER BY l.kind, l.cut, l.label;
