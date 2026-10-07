-- inputs: openrouter_session_cost
-- OpenRouter session cost (Author-only snapshots, docs/plans/2026-10-07-openrouter-apps-session-cost.md).
-- Variables set by cachereg.build: as_of, openrouter_session_cost_cutoff.
-- Each snapshot is a 30-day window ending on `window_end_date`, published weekly, so consecutive
-- snapshots overlap. A cell is the median USD per session of one harness × model × turn range,
-- with no session count: cells cannot be pooled or averaged across models, turn ranges or
-- harnesses. Compare harnesses at a fixed (model, turn range); that is left to analyses.

-- Every snapshot with window_end_date <= as_of, each from its latest fetch on/before the cutoff.
CREATE OR REPLACE TABLE or_session_cost AS
WITH pick AS (
    SELECT window_end_date, max(fetch_id) AS fetch_id
    FROM stg_openrouter_session_cost_cells
    WHERE CAST(fetched_at AS DATE) <= getvariable('openrouter_session_cost_cutoff')
      AND window_end_date <= getvariable('as_of')
    GROUP BY window_end_date
), latest AS (
    SELECT max(window_end_date) AS window_end_date FROM pick
)
SELECT
    c.window_end_date,
    c.window_days,
    c.window_end_date - CAST(c.window_days - 1 AS INTEGER) AS window_start_date,
    c.window_end_date = latest.window_end_date AS is_latest_snapshot,
    c.app_slug,
    c.app_name,
    h.app_id,
    h.vendor_id AS harness_vendor_id,
    c.turn_range,
    c.turn_min,
    c.turn_max,
    c.model_permaslug,
    a.model_id,
    v.vendor_id AS model_vendor_id,
    c.median_session_cost_usd,
    c.fetch_id
FROM stg_openrouter_session_cost_cells c
JOIN pick USING (window_end_date, fetch_id)
CROSS JOIN latest
LEFT JOIN stg_openrouter_session_cost_harnesses h ON h.app_slug = c.app_slug
LEFT JOIN dim_model_alias a ON a.source = 'openrouter' AND a.alias = c.model_permaslug
LEFT JOIN dim_vendor_alias v ON v.source = 'openrouter' AND v.alias = split_part(c.model_permaslug, '/', 1);

-- Coverage per snapshot × harness: unmapped models and harnesses are counted, never dropped.
CREATE OR REPLACE TABLE or_session_cost_coverage AS
SELECT
    window_end_date,
    app_slug,
    any_value(app_id) AS app_id,
    any_value(app_id) IS NULL AS harness_unmapped,
    count(*) AS cells,
    count(model_id) AS cells_with_model_id,
    count(DISTINCT model_permaslug) AS models,
    count(DISTINCT model_permaslug) FILTER (WHERE model_id IS NULL) AS unmapped_models,
    list_sort(list(DISTINCT turn_range)) AS turn_ranges
FROM or_session_cost
GROUP BY window_end_date, app_slug;
