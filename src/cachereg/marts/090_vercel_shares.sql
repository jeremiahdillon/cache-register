-- inputs: vercel_ai_gateway
-- Vercel AI Gateway marts (docs/plans/2026-10-08-vercel-ai-gateway.md): daily shares of requests,
-- tokens and spend by lab and by model, text modality, Latest-only.
-- Variables set by cachereg.build: as_of, vercel_ai_gateway_cutoff.
-- Assumptions (documented in every analysis that uses these marts):
--   * shares only, never volumes: a week's or month's share is the unweighted mean of its daily
--     shares (a busy day counts as much as a quiet one); a lab absent on a day counts as 0 that day.
--   * a day's rows all come from ONE fetch: the latest on/before the cutoff that holds the day
--     (models: per requested month, since the listed models depend on the window).
--   * spend share is Vercel's measure of what customers paid through the gateway, not a list-price
--     estimate.
--   * labs are complete (100 per day × metric); models are the month's top few plus `Other`.

CREATE OR REPLACE TABLE vercel_lab_share AS
WITH pick AS (
    SELECT date, max(fetch_id) AS fetch_id
    FROM stg_vercel_ai_gateway_shares
    WHERE dataset = 'labs' AND CAST(fetched_at AS DATE) <= getvariable('vercel_ai_gateway_cutoff')
    GROUP BY date
)
SELECT
    s.date,
    s.name AS lab,
    coalesce(v.vendor_id, '_unmapped') AS vendor_id,
    v.vendor_name,
    s.metric,
    s.share_pct,
    s.fetch_id
FROM stg_vercel_ai_gateway_shares s
JOIN pick USING (date, fetch_id)
LEFT JOIN dim_vendor_alias v ON v.source = 'vercel' AND v.alias = s.name
WHERE s.dataset = 'labs' AND s.date <= getvariable('as_of');

-- Weekly (ISO, Monday) and calendar-month means of daily shares per vendor. Unmapped labs are
-- summed under `_unmapped`. `days` = days with data in the period; `period_days` = its length.
CREATE OR REPLACE TABLE vercel_lab_share_period AS
WITH daily AS (
    SELECT date, vendor_id, any_value(vendor_name) AS vendor_name, metric, sum(share_pct) AS share_pct
    FROM vercel_lab_share
    GROUP BY date, vendor_id, metric
), kinds AS (
    SELECT unnest(['week', 'month']) AS period
), days AS (
    SELECT k.period, CAST(date_trunc(k.period, d.date) AS DATE) AS period_start, count(DISTINCT d.date) AS days
    FROM (SELECT DISTINCT date FROM vercel_lab_share) d CROSS JOIN kinds k
    GROUP BY ALL
)
SELECT
    k.period,
    CAST(date_trunc(k.period, d.date) AS DATE) AS period_start,
    d.vendor_id,
    any_value(d.vendor_name) AS vendor_name,
    d.metric,
    sum(d.share_pct) / any_value(n.days) AS mean_share_pct,
    any_value(n.days) AS days,
    CASE k.period
        WHEN 'week' THEN 7
        ELSE datediff('day', date_trunc('month', any_value(d.date)), date_trunc('month', any_value(d.date)) + INTERVAL 1 MONTH)
    END AS period_days
FROM daily d
CROSS JOIN kinds k
JOIN days n ON n.period = k.period AND n.period_start = CAST(date_trunc(k.period, d.date) AS DATE)
GROUP BY k.period, CAST(date_trunc(k.period, d.date) AS DATE), d.vendor_id, d.metric;

-- Models: the requested month's top few plus `Other` (kept as its own row). Model-level claims are
-- not supported (the list depends on the window); use for "largest models" context only.
CREATE OR REPLACE TABLE vercel_model_share AS
WITH pick AS (
    SELECT window_start, date, max(fetch_id) AS fetch_id
    FROM stg_vercel_ai_gateway_shares
    WHERE dataset = 'models' AND CAST(fetched_at AS DATE) <= getvariable('vercel_ai_gateway_cutoff')
    GROUP BY window_start, date
)
SELECT
    s.date,
    s.window_start,
    s.name AS model_name,
    m.model_id,
    s.is_other,
    s.metric,
    s.share_pct,
    s.unlisted_pct,
    s.fetch_id
FROM stg_vercel_ai_gateway_shares s
JOIN pick USING (window_start, date, fetch_id)
LEFT JOIN dim_model_alias m ON m.source = 'vercel' AND m.alias = s.name
WHERE s.dataset = 'models' AND s.date <= getvariable('as_of');

-- Every published label up to as_of, mapped or not, with its peak shares (unmapped labels are
-- reported here, never dropped from the series).
CREATE OR REPLACE TABLE vercel_label_coverage AS
WITH labels AS (
    SELECT 'lab' AS kind, lab AS label, vendor_id <> '_unmapped' AS mapped, vendor_id AS mapped_to,
        date, metric, share_pct
    FROM vercel_lab_share
    UNION ALL
    SELECT 'model', model_name, model_id IS NOT NULL OR is_other, model_id, date, metric, share_pct
    FROM vercel_model_share
)
SELECT
    kind,
    label,
    any_value(mapped) AS mapped,
    any_value(mapped_to) AS mapped_to,
    min(date) AS first_day,
    max(date) AS last_day,
    max(share_pct) FILTER (WHERE metric = 'tokens') AS peak_tokens_pct,
    max(share_pct) FILTER (WHERE metric = 'spend') AS peak_spend_pct,
    max(share_pct) FILTER (WHERE metric = 'requests') AS peak_requests_pct
FROM labels
GROUP BY kind, label
ORDER BY kind, mapped, peak_tokens_pct DESC NULLS LAST;
