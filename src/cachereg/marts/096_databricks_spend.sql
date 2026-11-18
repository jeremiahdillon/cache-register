-- inputs: databricks_ai_index, litellm_prices
-- Databricks: a lab's share of ALL Unity Gateway spend. The page gives wallet shares within proprietary and
-- within open-weight models and the token mix between them, but not the spend mix; this mart estimates it.
-- Variables set by cachereg.build: as_of. Reads dbx_layer_week and dbx_segment_mix_week (095) and
-- lp_price_intervals (008), which run first.
-- Method (documented in every analysis that uses this mart):
--   * within a segment, wallet_i / tokens_i = p_i / P (model i's price over the segment's mean price), so
--     P = Σ tokens_i × p_i / Σ wallet_i over the segment's named models with a list price. p_i is the
--     model's LiteLLM blended price (0.8 × input + 0.2 × output, as mart 010) listed on the week's Sunday,
--     through its `litellm` aliases in preference order; when none is listed that day, the entry nearest the
--     date (flagged price_date_stale, as mart 010). `priced_token_pct` says how much of the segment's tokens
--     the estimate rests on; the unnamed buckets ("Older … Models", "Other", "Gemini, Grok") are never priced.
--   * open-weight share of spend S = T_open × P_open / (T_open × P_open + T_prop × P_prop); a proprietary lab's
--     share of all spend = its wallet share of proprietary × (1 − S). Sensitivity: P_open × 2 (lower share) and
--     × ½ (higher share).
--   * Databricks' wallet share is itself a list-price estimate ("not what Databricks bills"); caching and
--     discounts are not in it.

CREATE OR REPLACE TABLE dbx_model_price_week AS
WITH named AS (
    SELECT DISTINCT week_start, week, segment, label, model_id
    FROM dbx_layer_week
    WHERE model_id IS NOT NULL AND segment <> 'split'
), cand AS (
    SELECT n.*, a.alias AS price_key, a.rank, p.valid_from,
           0.8 * p.input_usd_per_token + 0.2 * p.output_usd_per_token AS blended_usd_per_token,
           CASE
               WHEN p.valid_from <= n.week AND (p.valid_to IS NULL OR p.valid_to > n.week) THEN 'current'
               WHEN p.valid_from > n.week THEN 'before_listing'
               ELSE 'after_removal'
           END AS basis
    FROM named n
    JOIN dim_model_alias a ON a.source = 'litellm' AND a.model_id = n.model_id
    JOIN lp_price_intervals p ON p.key = a.alias
)
SELECT *, basis <> 'current' AS price_date_stale FROM cand
-- listed that week: preference order decides; otherwise the entry nearest the week (as mart 010)
QUALIFY row_number() OVER (
    PARTITION BY week_start, segment, label
    ORDER BY
        CASE basis WHEN 'current' THEN 0 WHEN 'after_removal' THEN 1 ELSE 2 END,
        CASE WHEN basis = 'current' THEN rank ELSE 0 END,
        CASE WHEN basis = 'before_listing' THEN epoch(valid_from) ELSE -epoch(valid_from) END,
        rank,
        price_key
) = 1;

CREATE OR REPLACE TABLE dbx_segment_price_week AS
WITH t AS (
    SELECT week_start, segment, label, share_pct AS tok FROM dbx_layer_week WHERE metric = 'tokens' AND segment <> 'split'
), w AS (
    SELECT week_start, segment, label, share_pct AS wal FROM dbx_layer_week WHERE metric = 'spend'
)
SELECT
    t.week_start,
    t.segment,
    sum(t.tok * p.blended_usd_per_token) / nullif(sum(w.wal) FILTER (WHERE p.price_key IS NOT NULL), 0)
        AS mean_price_usd_per_token,
    coalesce(sum(t.tok) FILTER (WHERE p.price_key IS NOT NULL), 0) AS priced_token_pct,
    coalesce(sum(w.wal) FILTER (WHERE p.price_key IS NOT NULL), 0) AS priced_wallet_pct,
    coalesce(sum(t.tok) FILTER (WHERE p.price_date_stale), 0) AS stale_priced_token_pct,
    count(p.price_key) FILTER (WHERE t.tok > 0) AS models_priced,
    string_agg(t.label, ', ' ORDER BY t.label) FILTER (WHERE p.price_key IS NULL AND t.tok > 0 AND t.label IN
        (SELECT label FROM dbx_layer_week WHERE model_id IS NOT NULL)) AS named_unpriced
FROM t
JOIN w USING (week_start, segment, label)
LEFT JOIN dbx_model_price_week p USING (week_start, segment, label)
GROUP BY t.week_start, t.segment;

CREATE OR REPLACE TABLE dbx_spend_mix_week AS
WITH p AS (
    SELECT week_start,
           max(mean_price_usd_per_token) FILTER (WHERE segment = 'proprietary') AS p_prop,
           max(mean_price_usd_per_token) FILTER (WHERE segment = 'open_weight') AS p_open
    FROM dbx_segment_price_week GROUP BY week_start
)
SELECT
    x.week_start, x.week, x.proprietary_token_pct, x.open_token_pct, p.p_prop, p.p_open,
    100 * x.open_token_pct * p.p_open / (x.open_token_pct * p.p_open + x.proprietary_token_pct * p.p_prop)
        AS open_spend_pct,
    100 * x.open_token_pct * 2 * p.p_open / (x.open_token_pct * 2 * p.p_open + x.proprietary_token_pct * p.p_prop)
        AS open_spend_pct_hi,
    100 * x.open_token_pct * 0.5 * p.p_open / (x.open_token_pct * 0.5 * p.p_open + x.proprietary_token_pct * p.p_prop)
        AS open_spend_pct_lo
FROM dbx_segment_mix_week x
JOIN p USING (week_start);

-- Per week × vendor: share of all spend (estimate) with its sensitivity range.
CREATE OR REPLACE TABLE dbx_vendor_spend_week AS
WITH v AS (
    SELECT week_start, week, vendor_id, segment, sum(share_pct) AS wallet_of_segment_pct
    FROM dbx_layer_week WHERE metric = 'spend' GROUP BY ALL
)
SELECT
    v.week_start, v.week, v.vendor_id, v.segment, v.wallet_of_segment_pct, m.open_spend_pct,
    v.wallet_of_segment_pct * CASE v.segment WHEN 'proprietary' THEN 100 - m.open_spend_pct ELSE m.open_spend_pct END / 100
        AS share_of_all_pct,
    v.wallet_of_segment_pct * CASE v.segment WHEN 'proprietary' THEN 100 - m.open_spend_pct_hi ELSE m.open_spend_pct_lo END / 100
        AS share_of_all_lo_pct,
    v.wallet_of_segment_pct * CASE v.segment WHEN 'proprietary' THEN 100 - m.open_spend_pct_lo ELSE m.open_spend_pct_hi END / 100
        AS share_of_all_hi_pct
FROM v JOIN dbx_spend_mix_week m USING (week_start);
