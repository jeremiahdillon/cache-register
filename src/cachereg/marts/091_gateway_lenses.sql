-- inputs: vercel_ai_gateway, openrouter_rankings, litellm_prices, ramp_ai_index
-- Vendor lenses for analysis (e) "developer wallet vs enterprise wallet"
-- (docs/plans/2026-10-08-vercel-ai-gateway.md): monthly by vendor, long format, one row per lens.
-- Reads vercel_lab_share_period (090), or_model_daily (010) and ramp_adoption (060); runs after them.
-- Variables set by cachereg.build: as_of (each mart it reads applies its own cutoff).
-- Assumptions (documented in every analysis that uses this mart):
--   * lenses are rows, never ratios or differences: they measure different populations and
--     different things, so they are never put on one axis as one quantity.
--       vercel_tokens, vercel_spend    Vercel AI Gateway, share of tokens / of spend (Vercel's measure)
--       openrouter_tokens              OpenRouter, share of tokens (mean of daily shares)
--       openrouter_tokens_volume_weighted  the same, the month's tokens over the month's total
--       openrouter_est_spend           OpenRouter, share of estimated spend (list prices, caching
--                                      ignored, 010); unpriced tokens count as no spend
--       ramp_paying                    Ramp, share of businesses paying the lab (adoption, not a share
--                                      of a total: lab rows do not sum to 100)
--   * months are calendar months; Vercel and OpenRouter shares are unweighted means of daily shares
--     (a vendor absent on a day counts 0) unless the lens says volume-weighted. `days` and
--     `period_days` show partial months.
--   * OpenRouter's denominator is everything ranked that day, incl. its `other` row (`_other`) and
--     free variants; spend shares are of priced spend, averaged over the days with any priced spend.
--     `coverage_pct` (est. spend lens) is the mean daily share of non-free tokens that are priced.
--   * `vendor_rank` ranks named vendors (ids without a leading `_`) per lens and month.

CREATE OR REPLACE TABLE gateway_lenses AS
WITH or_day AS (
    SELECT
        date,
        vendor_id,
        sum(total_tokens) AS tokens,
        coalesce(sum(est_spend_usd), 0) AS spend,
        sum(CASE WHEN NOT is_free THEN total_tokens ELSE 0 END) AS paid_tokens,
        sum(CASE WHEN NOT is_free AND price_matched THEN total_tokens ELSE 0 END) AS priced_tokens
    FROM or_model_daily
    GROUP BY date, vendor_id
), or_total AS (
    SELECT date, sum(tokens) AS tokens, sum(spend) AS spend, sum(priced_tokens) / nullif(sum(paid_tokens), 0) AS priced
    FROM or_day
    GROUP BY date
), or_month AS (
    SELECT
        CAST(date_trunc('month', date) AS DATE) AS month,
        count(*) AS days,
        count(*) FILTER (WHERE spend > 0) AS spend_days,
        sum(tokens) AS tokens,
        100 * avg(priced) AS coverage_pct
    FROM or_total
    GROUP BY 1
), openrouter AS (
    SELECT
        CAST(date_trunc('month', d.date) AS DATE) AS month,
        d.vendor_id,
        sum(100.0 * d.tokens / t.tokens) AS tokens_pct_sum,
        sum(100.0 * d.spend / nullif(t.spend, 0)) AS spend_pct_sum,
        sum(d.tokens) AS tokens
    FROM or_day d
    JOIN or_total t USING (date)
    GROUP BY 1, 2
), lenses AS (
    SELECT period_start AS month, vendor_id, NULL AS label, 'vercel_' || metric AS lens,
        mean_share_pct AS value_pct, days, period_days, NULL::DOUBLE AS coverage_pct
    FROM vercel_lab_share_period
    WHERE period = 'month' AND metric IN ('tokens', 'spend')
    UNION ALL
    SELECT o.month, o.vendor_id, NULL, l.lens,
        CASE l.lens
            WHEN 'openrouter_tokens' THEN o.tokens_pct_sum / m.days
            WHEN 'openrouter_tokens_volume_weighted' THEN 100.0 * o.tokens / m.tokens
            ELSE coalesce(o.spend_pct_sum, 0) / nullif(m.spend_days, 0)
        END,
        CASE WHEN l.lens = 'openrouter_est_spend' THEN m.spend_days ELSE m.days END,  -- the days averaged
        datediff('day', o.month, o.month + INTERVAL 1 MONTH),
        CASE WHEN l.lens = 'openrouter_est_spend' THEN m.coverage_pct END
    FROM openrouter o
    JOIN or_month m USING (month)
    CROSS JOIN (VALUES ('openrouter_tokens'), ('openrouter_tokens_volume_weighted'), ('openrouter_est_spend')) l(lens)
    UNION ALL
    SELECT month, coalesce(vendor_id, '_unmapped'), series_label, 'ramp_paying', adoption_pct, NULL, NULL, NULL
    FROM ramp_adoption
    WHERE series_kind = 'vendor'
)
SELECT
    month,
    lens,
    vendor_id,
    label,
    value_pct,
    CASE WHEN NOT starts_with(vendor_id, '_')
         THEN rank() OVER (PARTITION BY month, lens, starts_with(vendor_id, '_') ORDER BY value_pct DESC) END
        AS vendor_rank,
    days,
    period_days,
    coverage_pct
FROM lenses
WHERE month <= getvariable('as_of')
ORDER BY month, lens, vendor_rank NULLS LAST, vendor_id;
