-- inputs: openrouter_rankings, openrouter_models
-- OpenRouter usage marts (PLAN §2.2): openrouter_rankings (native, Latest-only) and
-- openrouter_models (snapshot prices). Variables set by cachereg.build:
--   as_of, openrouter_rankings_cutoff, openrouter_models_cutoff.
-- Assumptions (documented in every analysis that uses these marts):
--   * list price of the base model; catalog variants (`:batch`, …) are not used for pricing.
--   * est_spend = tokens × (0.8 × prompt + 0.2 × completion) list price; caching ignored.
--   * `:free` variants priced at 0 and reported separately.
--   * rows priced with a snapshot newer than the row's date are flagged price_date_stale.

-- Latest vintage per (date, model) among fetches made on/before the cutoff.
CREATE OR REPLACE TABLE or_rankings_daily AS
SELECT date, model_permaslug, total_tokens, fetch_id
FROM (
    SELECT *, row_number() OVER (PARTITION BY date, model_permaslug ORDER BY fetched_at DESC) AS rn
    FROM stg_openrouter_rankings_daily
    WHERE date <= getvariable('as_of')
      AND CAST(fetched_at AS DATE) <= getvariable('openrouter_rankings_cutoff')
)
WHERE rn = 1;

CREATE OR REPLACE TABLE or_model_daily AS
WITH px AS (
    -- One price row per canonical_slug, so the join can never fan out token counts. The catalog
    -- lists variants under the same canonical_slug (e.g. `…:batch` at half price); rankings report
    -- the model itself, so prefer the entry without a `:variant` suffix, then the lowest id.
    SELECT * FROM stg_openrouter_models_prices
    WHERE snapshot_date = getvariable('openrouter_models_cutoff')
    QUALIFY row_number() OVER (PARTITION BY canonical_slug ORDER BY (id LIKE '%:%'), id) = 1
), r AS (
    SELECT *,
        model_permaslug = 'other' AS is_other,
        model_permaslug LIKE '%:free' AS is_free,
        split_part(model_permaslug, '/', 1) AS author_prefix,
        regexp_replace(model_permaslug, ':free$', '') AS price_key
    FROM or_rankings_daily
)
SELECT
    r.date,
    r.model_permaslug,
    r.author_prefix,
    CASE WHEN r.is_other THEN '_other' ELSE coalesce(v.vendor_id, '_unmapped') END AS vendor_id,
    r.is_other,
    r.is_free,
    r.total_tokens,
    px.prompt_usd_per_token,
    px.completion_usd_per_token,
    (px.canonical_slug IS NOT NULL) AS price_matched,
    0.8 * px.prompt_usd_per_token + 0.2 * px.completion_usd_per_token AS blended_usd_per_token,
    CASE
        WHEN r.is_free THEN 0.0
        ELSE r.total_tokens * (0.8 * px.prompt_usd_per_token + 0.2 * px.completion_usd_per_token)
    END AS est_spend_usd,
    getvariable('openrouter_models_cutoff') AS price_snapshot_date,
    getvariable('openrouter_models_cutoff') > r.date AS price_date_stale
FROM r
LEFT JOIN dim_vendor_alias v ON v.source = 'openrouter' AND v.alias = r.author_prefix
LEFT JOIN px ON px.canonical_slug = r.price_key;

CREATE OR REPLACE TABLE or_vendor_weekly AS
SELECT
    CAST(date_trunc('week', date) AS DATE) AS week,
    vendor_id,
    sum(total_tokens) AS tokens,
    sum(est_spend_usd) AS est_spend_usd,
    sum(CASE WHEN NOT is_other AND NOT is_free AND NOT price_matched THEN total_tokens ELSE 0 END) AS unpriced_tokens,
    sum(CASE WHEN is_free THEN total_tokens ELSE 0 END) AS free_tokens,
    count(DISTINCT date) AS days
FROM or_model_daily
GROUP BY ALL;
