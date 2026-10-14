-- inputs: curated_asset_values
-- Curated asset values (docs/plans/2026-10-14-gpu-vs-fiber.md): dated, cited figures on what GPUs,
-- AI infrastructure and dot-com fiber cost, fetched, were assumed to last or recovered in a bust, as the
-- dataset knew them on as_of.
-- Variables set by cachereg.build: as_of.
-- Assumptions (documented in every analysis that uses these marts):
--   * Exact by `recorded_on`: a row is visible when recorded on or before as_of and not superseded
--     by a row recorded on or before as_of.
--   * values are in the unit the source stated them in (`unit`), never converted here; a range is two
--     rows (qualifier range_low / range_high); press figures are marked `secondary`.

CREATE OR REPLACE TABLE asset_values AS
WITH known AS (
    SELECT * FROM stg_curated_asset_values_asset_values WHERE recorded_on <= getvariable('as_of')
)
SELECT
    k.id,
    k.statement_date,
    k.asset,
    a.asset_label,
    a.era,
    a.layer,
    k.entity,
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
LEFT JOIN stg_curated_asset_values_assets a USING (asset)
LEFT JOIN stg_curated_asset_values_metrics m USING (metric)
WHERE k.id NOT IN (SELECT supersedes FROM known WHERE supersedes IS NOT NULL);
