-- inputs: epoch_benchmarks
-- Epoch capabilities marts (PLAN §2, analysis (a)): the Epoch Capabilities Index (ECI) and
-- per-benchmark scores from ONE vintage of epoch_benchmarks (Latest-only, PLAN §4.4).
-- Variables set by cachereg.build: as_of, epoch_benchmarks_cutoff.
-- Assumptions (documented in every analysis that uses these marts):
--   * the vintage is the latest fetch made on or before the cutoff date; Epoch re-fits ECI on
--     every update, so a model's ECI is the value in that vintage, not a historical index.
--   * only models released on or before as_of are kept (release date is Epoch's); a partial date
--     counts from the END of its period, and a model with no release date is excluded (it cannot
--     be placed before as_of; excluded rows are counted in epoch_undated).
--   * model_id comes from config/entities/models.yaml `aliases.epoch` (Epoch model groups);
--     null when unmapped. Coverage is reported in epoch_alias_coverage.
--   * scores keep every published row (repeated runs, agents or scaffolds of one version stay
--     separate rows); score_norm = score × Epoch's `scale` (0–1).

CREATE OR REPLACE TABLE epoch_bench_vintage AS
SELECT vintage_id, fetch_id, fetched_at, content_sha256
FROM stg_epoch_benchmarks_vintages
WHERE fetch_date <= getvariable('epoch_benchmarks_cutoff')
ORDER BY fetched_at DESC, fetch_id DESC
LIMIT 1;

CREATE OR REPLACE MACRO epoch_visible_from(d, prec) AS
    CASE prec
        WHEN 'year' THEN CAST(d + INTERVAL 1 YEAR - INTERVAL 1 DAY AS DATE)
        WHEN 'month' THEN last_day(d)
        ELSE d
    END;

CREATE OR REPLACE TABLE epoch_eci AS
SELECT
    e.model_group,
    e.display_name,
    e.eci,
    e.eci_ci_low,
    e.eci_ci_high,
    e.release_date,
    e.organization,
    e.country,
    e.accessibility,
    e.accessibility_group,
    a.model_id,
    e.vintage_id
FROM stg_epoch_benchmarks_eci e
JOIN epoch_bench_vintage v ON v.vintage_id = e.vintage_id
LEFT JOIN dim_model_alias a ON a.source = 'epoch' AND a.alias = e.model_group
WHERE epoch_visible_from(e.release_date, e.release_date_precision) <= getvariable('as_of');

CREATE OR REPLACE TABLE epoch_scores AS
SELECT
    s.benchmark,
    b.in_eci,
    s.model_version,
    m.model_group,
    m.release_date,
    a.model_id,
    s.row,
    s.row_id,
    s.score,
    s.scale,
    s.score_norm,
    b.random_baseline,
    b.score_ceiling,
    s.vintage_id
FROM stg_epoch_benchmarks_scores s
JOIN epoch_bench_vintage v ON v.vintage_id = s.vintage_id
JOIN stg_epoch_benchmarks_models m ON m.vintage_id = s.vintage_id AND m.model_version = s.model_version
LEFT JOIN stg_epoch_benchmarks_benchmarks b ON b.vintage_id = s.vintage_id AND b.benchmark = s.benchmark
LEFT JOIN dim_model_alias a ON a.source = 'epoch' AND a.alias = m.model_group
WHERE epoch_visible_from(m.release_date, m.release_date_precision) <= getvariable('as_of');

-- PLAN §4.3 coverage: share of the measure that resolves to a canonical model.
CREATE OR REPLACE TABLE epoch_alias_coverage AS
WITH ranked AS (
    SELECT *, row_number() OVER (ORDER BY eci DESC NULLS LAST, model_group) AS eci_rank FROM epoch_eci
)
SELECT
    measure,
    count(*) AS models,
    count(model_id) AS mapped,
    count(model_id) / nullif(count(*), 0) AS share_mapped
FROM (
    SELECT 'eci_models' AS measure, model_id FROM ranked
    UNION ALL
    SELECT 'eci_top50' AS measure, model_id FROM ranked WHERE eci_rank <= 50
)
GROUP BY measure
ORDER BY measure;

-- What the as_of filter leaves out because a date is missing (reported, never silently lost).
CREATE OR REPLACE TABLE epoch_undated AS
SELECT 'eci' AS measure, count(*) AS rows_without_date
FROM stg_epoch_benchmarks_eci e JOIN epoch_bench_vintage v ON v.vintage_id = e.vintage_id
WHERE e.release_date IS NULL
UNION ALL
SELECT 'scores', count(*)
FROM stg_epoch_benchmarks_scores s
JOIN epoch_bench_vintage v ON v.vintage_id = s.vintage_id
JOIN stg_epoch_benchmarks_models m ON m.vintage_id = s.vintage_id AND m.model_version = s.model_version
WHERE m.release_date IS NULL;
