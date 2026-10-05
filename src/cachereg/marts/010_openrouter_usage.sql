-- inputs: openrouter_rankings, litellm_prices
-- OpenRouter usage marts (PLAN §2.2): openrouter_rankings (native, Latest-only) priced day by day
-- from litellm_prices (native, Exact). Variables set by cachereg.build: as_of, <source>_cutoff.
-- Assumptions (documented in every analysis that uses these marts):
--   * est_spend = tokens × (0.8 × input + 0.2 × output) list price; caching ignored.
--   * a permaslug is priced only through config/entities/models.yaml (dim_model_alias): its
--     model's `litellm` keys, in preference order. Unmapped permaslugs stay unpriced (measured).
--   * the price of day D is the key's LiteLLM entry at the end of D (stg_litellm_prices_days).
--     When no mapped key is listed that day, the entry nearest the date (any of the model's keys)
--     is used and the row is flagged price_date_stale: first the last entry before D (after_removal), then the first entry after
--     D (before_listing). Days after the staged LiteLLM history use its last day (beyond_history).
--   * only LiteLLM data known on as_of is read: entries starting later are ignored and an entry
--     that ended after as_of is treated as still listed.
--   * `:free` variants priced at 0 and reported separately.

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

-- LiteLLM price intervals as known on as_of (only entries with both an input and output price).
CREATE OR REPLACE TABLE lp_price_intervals AS
SELECT
    key,
    input_usd_per_token,
    output_usd_per_token,
    valid_from,
    CASE WHEN valid_to > getvariable('as_of') THEN NULL ELSE valid_to END AS valid_to,
    commit_sha
FROM stg_litellm_prices_prices
WHERE valid_from <= getvariable('as_of')
  AND input_usd_per_token IS NOT NULL
  AND output_usd_per_token IS NOT NULL;

-- One price per (date, permaslug): the best candidate among the model's LiteLLM keys.
CREATE OR REPLACE TABLE or_model_price_daily AS
WITH r AS (
    SELECT DISTINCT date, model_permaslug
    FROM or_rankings_daily
    WHERE model_permaslug <> 'other' AND model_permaslug NOT LIKE '%:free'
), lim AS (
    SELECT least(max(date), getvariable('as_of')) AS last_day FROM stg_litellm_prices_days
), cand AS (
    SELECT
        r.date,
        r.model_permaslug,
        a.model_id,
        l.alias AS price_key,
        l.rank,
        p.input_usd_per_token,
        p.output_usd_per_token,
        p.valid_from,
        p.commit_sha,
        CASE
            WHEN p.valid_to IS NOT NULL AND p.valid_to <= r.date THEN 'after_removal'
            WHEN p.valid_from > r.date THEN 'before_listing'
            WHEN r.date > lim.last_day THEN 'beyond_history'
            ELSE 'current'
        END AS basis
    FROM r
    CROSS JOIN lim
    JOIN dim_model_alias a ON a.source = 'openrouter' AND a.alias = r.model_permaslug
    JOIN dim_model_alias l ON l.source = 'litellm' AND l.model_id = a.model_id
    JOIN lp_price_intervals p ON p.key = l.alias
)
SELECT *
FROM cand
QUALIFY row_number() OVER (
    PARTITION BY date, model_permaslug
    ORDER BY
        CASE basis WHEN 'current' THEN 0 WHEN 'beyond_history' THEN 1 WHEN 'after_removal' THEN 2 ELSE 3 END,
        -- listed that day: preference order decides. Otherwise the entry nearest the date decides
        -- (the latest one before it, or the earliest one after it), then preference order.
        CASE WHEN basis = 'current' THEN rank ELSE 0 END,
        CASE WHEN basis = 'before_listing' THEN epoch(valid_from) ELSE -epoch(valid_from) END,
        rank,
        price_key
) = 1;

CREATE OR REPLACE TABLE or_model_daily AS
WITH r AS (
    SELECT *,
        model_permaslug = 'other' AS is_other,
        model_permaslug LIKE '%:free' AS is_free,
        split_part(model_permaslug, '/', 1) AS author_prefix
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
    px.input_usd_per_token AS prompt_usd_per_token,
    px.output_usd_per_token AS completion_usd_per_token,
    (px.price_key IS NOT NULL) AS price_matched,
    0.8 * px.input_usd_per_token + 0.2 * px.output_usd_per_token AS blended_usd_per_token,
    CASE
        WHEN r.is_free THEN 0.0
        ELSE r.total_tokens * (0.8 * px.input_usd_per_token + 0.2 * px.output_usd_per_token)
    END AS est_spend_usd,
    px.model_id,
    px.price_key,
    px.basis AS price_basis,
    px.valid_from AS price_valid_from,
    px.commit_sha AS price_commit,
    coalesce(px.basis <> 'current', false) AS price_date_stale
FROM r
LEFT JOIN dim_vendor_alias v ON v.source = 'openrouter' AND v.alias = r.author_prefix
LEFT JOIN or_model_price_daily px ON px.date = r.date AND px.model_permaslug = r.model_permaslug;

CREATE OR REPLACE TABLE or_vendor_weekly AS
SELECT
    CAST(date_trunc('week', date) AS DATE) AS week,
    vendor_id,
    sum(total_tokens) AS tokens,
    sum(est_spend_usd) AS est_spend_usd,
    sum(CASE WHEN NOT is_other AND NOT is_free AND NOT price_matched THEN total_tokens ELSE 0 END) AS unpriced_tokens,
    sum(CASE WHEN NOT is_free AND price_matched AND price_date_stale THEN total_tokens ELSE 0 END) AS stale_priced_tokens,
    sum(CASE WHEN is_free THEN total_tokens ELSE 0 END) AS free_tokens,
    count(DISTINCT date) AS days
FROM or_model_daily
GROUP BY ALL;
