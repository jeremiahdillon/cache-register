-- inputs: litellm_prices
-- LiteLLM price intervals and price days (PLAN §2.2), on their own so that analyses pricing models without OpenRouter
-- data (e.g. receipts/opus-tenth-life) can be built from litellm_prices alone. Read by 010_openrouter_usage.
-- Variables set by cachereg.build: as_of.
-- Assumptions: only LiteLLM data known on as_of is read: entries starting later are ignored and an entry
-- that ended after as_of is treated as still listed.

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

-- Days with a LiteLLM price snapshot known on as_of: the spine for analyses that price models per day
-- (they read this mart, never the staged view).
CREATE OR REPLACE TABLE lp_price_days AS
SELECT DISTINCT date
FROM stg_litellm_prices_days
WHERE date <= getvariable('as_of');
