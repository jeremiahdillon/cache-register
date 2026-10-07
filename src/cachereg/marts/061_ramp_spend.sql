-- inputs: ramp_ai_index
-- Ramp AI Index: AI spend per employee and AI share of business spend (docs/plans/2026-10-07-ramp-ai-index.md).
-- Variables set by cachereg.build: as_of, ramp_ai_index_cutoff. Uses ramp_cut_coverage (mart 060).
-- AI spend includes LLM subscriptions, coding agent subscriptions, API tokens, and GPU cloud and
-- infrastructure spend (Ramp). Population: businesses on Ramp. Sectors join NAICS through
-- config/entities/sectors.yaml; Technology and media -> 51 is assumed (naics_assumed).

-- USD per employee per month: median, top 10% and top 1% for all businesses; median by sector and
-- by business size. `first_month` marks a group's first month in the import (sectors enter as
-- Ramp's sample allows, so a series can start late).
CREATE OR REPLACE TABLE ramp_spend_per_employee AS
SELECT
    p.month,
    p.dimension,
    p.group_label,
    s.naics,
    s.title AS naics_title,
    s.assumed AS naics_assumed,
    p.statistic,
    p.usd_per_employee_month,
    p.month = min(p.month) OVER (PARTITION BY p.cut, p.group_label, p.statistic) AS first_month,
    p.cut,
    p.fetch_id
FROM stg_ramp_ai_index_spend_per_employee p
JOIN ramp_cut_coverage c ON c.cut = p.cut AND c.import_used = p.fetch_id
LEFT JOIN stg_ramp_ai_index_sectors s ON p.dimension = 'sector' AND s.label = p.group_label
WHERE p.month <= getvariable('as_of');

-- AI share of business spend excluding payroll, % (overall, and per sector).
CREATE OR REPLACE TABLE ramp_spend_share AS
SELECT
    x.month,
    x.scope,
    x.sector_label,
    s.naics,
    s.title AS naics_title,
    s.assumed AS naics_assumed,
    x.ai_share_pct,
    x.fetch_id
FROM stg_ramp_ai_index_spend_share x
JOIN ramp_cut_coverage c ON c.cut = x.cut AND c.import_used = x.fetch_id
LEFT JOIN stg_ramp_ai_index_sectors s ON x.scope = 'sector' AND s.label = x.sector_label
WHERE x.month <= getvariable('as_of');
