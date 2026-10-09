-- inputs: curated_disclosures
-- Curated disclosures marts (docs/plans/2026-10-08-curated-disclosures.md): dated public figures
-- (tokens, run-rates, users) cited to their source, as the dataset knew them on as_of.
-- Variables set by cachereg.build: as_of.
-- Assumptions (documented in every analysis that uses these marts):
--   * Exact by `recorded_on`: a row is visible when recorded on or before as_of and not superseded
--     by a row recorded on or before as_of. Selected by as_of, never by the fetch cutoff (stage
--     reads the newest copy, which holds every earlier one).
--   * self-reported, unaudited and chosen by the company; definitions shift between statements
--     (`scope`, `qualifier`); a series is only as regular as the company's statements.
--   * values are in the metric's unit and never converted between metrics here.

CREATE OR REPLACE TABLE disclosures AS
WITH known AS (
    SELECT * FROM stg_curated_disclosures_disclosures WHERE recorded_on <= getvariable('as_of')
)
SELECT
    k.id,
    k.statement_date,
    k.entity AS vendor_id,
    v.vendor_name,
    k.metric,
    m.definition AS metric_definition,
    k.value,
    k.unit,
    k.qualifier,
    k.value_as_stated,
    k.period_start,
    k.period_end,
    k.scope,
    k.source_kind,
    k.source_url,
    k.source_quote,
    k.recorded_on,
    k.supersedes,
    k.notes
FROM known k
LEFT JOIN stg_curated_disclosures_metrics m USING (metric)
LEFT JOIN stg_curated_disclosures_vendors v ON v.vendor_id = k.entity
WHERE k.id NOT IN (SELECT supersedes FROM known WHERE supersedes IS NOT NULL);

-- Per entity × metric, in the order of the period measured (period_end, then statement date), so a
-- retrospective figure sits where it belongs (Anthropic's "$9B at the end of 2025", said in April 2026,
-- comes before February's $14B): the change since the previous figure and the days between.
-- Descriptive only: no interpolation, no unit conversion.
CREATE OR REPLACE TABLE disclosure_series AS
SELECT
    vendor_id,
    metric,
    id,
    statement_date,
    period_start,
    period_end,
    value,
    unit,
    qualifier,
    source_kind,
    row_number() OVER w AS seq,
    value - lag(value) OVER w AS change,
    value / nullif(lag(value) OVER w, 0) AS ratio_to_previous,
    datediff('day', lag(period_end) OVER w, period_end) AS days_since_previous_period
FROM disclosures
WINDOW w AS (PARTITION BY vendor_id, metric ORDER BY period_end, statement_date, id)
ORDER BY vendor_id, metric, seq;

CREATE OR REPLACE TABLE disclosure_coverage AS
SELECT
    metric,
    any_value(unit) AS unit,
    list_sort(list(DISTINCT vendor_id)) AS vendors,
    count(*) AS figures,
    min(statement_date) AS first_statement,
    max(statement_date) AS last_statement,
    avg(CASE WHEN source_kind = 'primary' THEN 1.0 ELSE 0.0 END) AS share_primary
FROM disclosures
GROUP BY metric
ORDER BY metric;
