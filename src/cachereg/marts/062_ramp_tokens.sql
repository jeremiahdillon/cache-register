-- inputs: ramp_ai_index
-- Ramp AI Index tokenomics: token shares by lab, token prices and their checks
-- (docs/plans/2026-10-07-ramp-ai-index.md). Variables: as_of, ramp_ai_index_cutoff. Uses
-- ramp_cut_coverage (mart 060).
-- Population: Ramp customers who connected their AI providers to Ramp's Token Spend Management
-- (model-attributed API spend), not the card and bill-pay sample behind adoption; Ramp says it is
-- not representative of its total AI spend. Never mix the two denominators.
-- Volume and spend come as an index (100 = the largest single cell in the chart), rescaled whenever
-- a new peak appears, so only shares within a week are published. A week is labelled by the Sunday
-- that ends it.

CREATE OR REPLACE TABLE ramp_token_share AS
SELECT
    t.week,
    t.measure,
    t.maker_label,
    v.vendor_id,
    t.index_value / sum(t.index_value) OVER (PARTITION BY t.week, t.measure) AS share,
    count(t.index_value) OVER (PARTITION BY t.week, t.measure) AS makers_with_data,
    t.fetch_id
FROM stg_ramp_ai_index_token_index t
JOIN ramp_cut_coverage c ON c.cut = t.cut AND c.import_used = t.fetch_id
LEFT JOIN dim_vendor_alias v ON v.source = 'ramp' AND v.alias = t.maker_label
WHERE t.week <= getvariable('as_of');

-- Realised price, USD per million tokens (total dollars ÷ total tokens, so it moves with the mix).
CREATE OR REPLACE TABLE ramp_token_price AS
SELECT
    p.day,
    p.price_kind,
    p.series_label,
    v.vendor_id,  -- null for the combined 'OpenAI & Anthropic' series
    p.usd_per_mtok,
    p.fetch_id
FROM stg_ramp_ai_index_token_price p
JOIN ramp_cut_coverage c ON c.cut = p.cut AND c.import_used = p.fetch_id
LEFT JOIN dim_vendor_alias v ON v.source = 'ramp' AND v.alias = p.series_label
WHERE p.day <= getvariable('as_of');

-- The three price views share one header, so the import cannot check which is which. Blended is a
-- token-weighted mix of input and output, so input <= blended <= output should hold; a day that
-- breaks it points to a view imported under the wrong cut (or a definition change at Ramp).
CREATE OR REPLACE TABLE ramp_price_check AS
WITH w AS (
    SELECT
        day,
        series_label,
        max(usd_per_mtok) FILTER (WHERE price_kind = 'input') AS input,
        max(usd_per_mtok) FILTER (WHERE price_kind = 'blended') AS blended,
        max(usd_per_mtok) FILTER (WHERE price_kind = 'output') AS output
    FROM ramp_token_price
    GROUP BY day, series_label
)
SELECT
    *,
    CASE WHEN input IS NULL OR blended IS NULL OR output IS NULL THEN NULL
         ELSE input <= blended + 1e-9 AND blended <= output + 1e-9 END AS within_bounds
FROM w
ORDER BY day, series_label;

-- Two price views with identical values on every shared day: one was imported twice.
CREATE OR REPLACE TABLE ramp_price_identical AS
SELECT
    a.price_kind AS kind_a,
    b.price_kind AS kind_b,
    count(*) AS shared_points,
    bool_and(a.usd_per_mtok IS NOT DISTINCT FROM b.usd_per_mtok) AS identical
FROM ramp_token_price a
JOIN ramp_token_price b ON a.day = b.day AND a.series_label = b.series_label AND a.price_kind < b.price_kind
GROUP BY a.price_kind, b.price_kind;

-- Volume and spend share one column set, so the import cannot tell them apart either. Spend share ÷
-- volume share is proportional to a lab's realised price, so the implied Anthropic : OpenAI price
-- ratio must sit on the same side of 1 as the ratio from the blended price view. A swap inverts it.
-- Blind when the two labs are priced alike (price ratio within 0.8–1.25): `decisive` is false then.
CREATE OR REPLACE TABLE ramp_token_check AS
WITH s AS (
    SELECT
        week,
        max(share) FILTER (WHERE measure = 'spend' AND vendor_id = 'anthropic')
            / max(share) FILTER (WHERE measure = 'volume' AND vendor_id = 'anthropic') AS anthropic_rel,
        max(share) FILTER (WHERE measure = 'spend' AND vendor_id = 'openai')
            / max(share) FILTER (WHERE measure = 'volume' AND vendor_id = 'openai') AS openai_rel
    FROM ramp_token_share
    GROUP BY week
), p AS (
    SELECT
        s.week,
        avg(t.usd_per_mtok) FILTER (WHERE t.vendor_id = 'anthropic')
            / avg(t.usd_per_mtok) FILTER (WHERE t.vendor_id = 'openai') AS price_ratio
    FROM s
    JOIN ramp_token_price t ON t.price_kind = 'blended' AND t.day BETWEEN s.week - INTERVAL 6 DAY AND s.week
    GROUP BY s.week
)
SELECT
    s.week,
    s.anthropic_rel / s.openai_rel AS implied_price_ratio,
    p.price_ratio,
    p.price_ratio NOT BETWEEN 0.8 AND 1.25 AS decisive,
    p.price_ratio NOT BETWEEN 0.8 AND 1.25
        AND (s.anthropic_rel / s.openai_rel - 1) * (p.price_ratio - 1) < 0 AS suspect_swap
FROM s
JOIN p USING (week)
ORDER BY s.week;
