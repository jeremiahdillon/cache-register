-- inputs: openrouter_rankings
-- OpenRouter token marts (no prices), so token-only analyses depend on openrouter_rankings alone.
-- Variables set by cachereg.build: as_of, openrouter_rankings_cutoff.

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
