-- inputs: epoch_benchmarks, litellm_prices
-- Daily list price of every ECI-scored model (analysis (a) "cost of intelligence", used by (b)).
-- Reads epoch_eci (020) and LiteLLM price intervals; needs no OpenRouter data.
-- Variables set by cachereg.build: as_of.
-- Assumptions (documented in every analysis that uses this mart):
--   * price = 0.8 × input + 0.2 × output list price per token (the house blend of
--     010_openrouter_usage), the cheapest of the model's mapped LiteLLM keys (aliases.litellm)
--     valid at the end of the day; zero prices (free tiers) are ignored.
--   * usd_per_mtok = median of that daily price over the trailing 28 days (OpenRouter listings
--     follow the cheapest provider and swing several-fold within days); usd_per_mtok_daily is
--     the unsmoothed price.
--   * basis 'listed': a mapped key is valid that day. 'backfilled': released but not yet listed
--     in LiteLLM, priced at its first listed daily price (an upper-bound sensitivity, not the
--     main series). Days run from 2025-01-01 (LiteLLM's staged floor) to as_of.
--   * ECI is one Epoch vintage (020), placed at each model's release date.

CREATE OR REPLACE TABLE eci_model_price_daily AS
WITH lim AS (
    SELECT least(max(date), getvariable('as_of')) AS last_day FROM stg_litellm_prices_days
),
days AS (
    SELECT CAST(d AS DATE) AS day
    FROM lim, generate_series(DATE '2025-01-01', lim.last_day, INTERVAL 1 DAY) g(d)
),
intervals AS (  -- as known on as_of (same rule as lp_price_intervals in 010)
    SELECT key, valid_from,
        CASE WHEN valid_to > getvariable('as_of') THEN NULL ELSE valid_to END AS valid_to,
        0.8 * input_usd_per_token + 0.2 * output_usd_per_token AS usd_per_token
    FROM stg_litellm_prices_prices
    WHERE valid_from <= getvariable('as_of')
      AND input_usd_per_token IS NOT NULL AND output_usd_per_token IS NOT NULL
),
m AS (
    SELECT model_group, display_name, eci, eci_ci_low, eci_ci_high, release_date, organization, model_id
    FROM epoch_eci WHERE model_id IS NOT NULL AND release_date IS NOT NULL
),
iv AS (
    SELECT m.model_group, p.valid_from, p.valid_to, p.usd_per_token
    FROM m
    JOIN dim_model_alias a ON a.source = 'litellm' AND a.model_id = m.model_id
    JOIN intervals p ON p.key = a.alias
    WHERE p.usd_per_token > 0
),
listed AS (
    SELECT iv.model_group, d.day, min(iv.usd_per_token) * 1e6 AS usd_per_mtok_daily
    FROM iv JOIN days d ON d.day >= iv.valid_from AND (iv.valid_to IS NULL OR d.day < iv.valid_to)
    GROUP BY ALL
),
smoothed AS (
    SELECT *, 'listed' AS basis,
        median(usd_per_mtok_daily) OVER (
            PARTITION BY model_group ORDER BY day RANGE BETWEEN INTERVAL 27 DAYS PRECEDING AND CURRENT ROW
        ) AS usd_per_mtok
    FROM listed
),
first_listed AS (
    SELECT model_group, min(day) AS first_day, arg_min(usd_per_mtok_daily, day) AS first_price
    FROM listed GROUP BY ALL
),
backfill AS (
    SELECT f.model_group, d.day, f.first_price AS usd_per_mtok_daily, 'backfilled' AS basis,
        f.first_price AS usd_per_mtok
    FROM first_listed f JOIN m USING (model_group)
    JOIN days d ON d.day >= m.release_date AND d.day < f.first_day
)
SELECT m.model_group, m.display_name, m.model_id, m.eci, m.eci_ci_low, m.eci_ci_high, m.release_date,
    m.organization, x.day, x.usd_per_mtok, x.usd_per_mtok_daily, x.basis
FROM (
    SELECT model_group, day, usd_per_mtok_daily, basis, usd_per_mtok FROM smoothed
    UNION ALL
    SELECT model_group, day, usd_per_mtok_daily, basis, usd_per_mtok FROM backfill
) x
JOIN m USING (model_group)
WHERE x.day >= m.release_date;
