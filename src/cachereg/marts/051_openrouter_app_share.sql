-- inputs: openrouter_apps, openrouter_rankings
-- App tokens as a share of all OpenRouter tokens, per week. Reads or_app_weekly (050) and
-- or_rankings_daily (005), both run first. Variables set by cachereg.build: as_of, <source>_cutoff.
-- Caveat: the denominator (rankings-daily, top 50 + `other`, summed Mon–Sun) includes traffic not
-- attributed to any public app, private apps and apps beyond rank 200, so app shares are lower
-- bounds and the remainder is not "other apps". Only weeks with all 7 rankings days are kept.

CREATE OR REPLACE TABLE or_app_share_weekly AS
WITH total AS (
    SELECT CAST(date_trunc('week', date) AS DATE) AS week_start, sum(total_tokens) AS openrouter_tokens
    FROM or_rankings_daily
    GROUP BY 1
    HAVING count(DISTINCT date) = 7
), apps AS (
    SELECT week_start, sum(total_tokens) AS top200_tokens, count(*) AS apps
    FROM or_app_weekly
    GROUP BY week_start
)
SELECT
    w.week_start,
    w.app_id,
    w.app_name,
    w.rank,
    w.total_tokens,
    CAST(t.openrouter_tokens AS BIGINT) AS openrouter_tokens,
    CAST(a.top200_tokens AS BIGINT) AS top200_tokens,
    a.apps AS top200_apps,
    a.top200_tokens / t.openrouter_tokens AS attributed_share,
    w.total_tokens / t.openrouter_tokens AS share_of_openrouter
FROM or_app_weekly w
JOIN apps a USING (week_start)
JOIN total t USING (week_start);
