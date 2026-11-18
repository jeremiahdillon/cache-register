-- inputs: databricks_ai_index
-- Databricks AI Index marts (src/cachereg/sources/databricks_ai_index/SOURCE.md): weekly shares of tokens and
-- of "wallet" (Databricks' list-price spend estimate) on Unity Gateway, within proprietary and within
-- open-weight models, plus the proprietary / open-weight token mix. Latest-only.
-- Variables set by cachereg.build: as_of, databricks_ai_index_cutoff.
-- Assumptions (documented in every analysis that uses these marts):
--   * weeks start on the Monday of the page's label ("week of Nov 2"); `week` is the Sunday that ends it, the
--     convention of the other sources' weekly marts.
--   * a week's rows all come from ONE fetch: the latest on/before the cutoff that holds the week.
--   * shares are published to 0.1 point; a lab's share is the sum of its published layers (its named models
--     plus "Older <lab> Models"), so it carries up to ~0.05 × layers of rounding.
--   * a lab's share of ALL tokens = its share of its segment's tokens × that segment's share of tokens. Spend
--     has no published segment mix; mart 096 estimates it.

CREATE OR REPLACE TABLE dbx_layer_week AS
WITH pick AS (
    SELECT week_start, max(fetch_id) AS fetch_id
    FROM stg_databricks_ai_index_layers
    -- the fetch's UTC date (from its id), as build's cutoff; CAST(fetched_at AS DATE) would use the local zone
    WHERE CAST(strptime(left(fetch_id, 8), '%Y%m%d') AS DATE) <= getvariable('databricks_ai_index_cutoff')
    GROUP BY week_start
)
SELECT
    s.week_start,
    CAST(s.week_start + INTERVAL 6 DAY AS DATE) AS week,
    s.chart,
    s.metric,
    s.segment,
    s.provider_group,
    s.label,
    CASE WHEN s.segment = 'split' THEN NULL ELSE coalesce(v.vendor_id, '_other') END AS vendor_id,
    m.model_id,
    s.share_pct,
    s.updated,
    s.fetch_id
FROM stg_databricks_ai_index_layers s
JOIN pick USING (week_start, fetch_id)
LEFT JOIN dim_vendor_alias v ON v.source = 'databricks' AND v.alias = s.provider_group
LEFT JOIN dim_model_alias m ON m.source = 'databricks' AND m.alias = s.label
WHERE CAST(s.week_start + INTERVAL 6 DAY AS DATE) <= getvariable('as_of');

-- The proprietary / open-weight token mix per week (%).
CREATE OR REPLACE TABLE dbx_segment_mix_week AS
SELECT
    week_start,
    week,
    max(share_pct) FILTER (WHERE label = 'Proprietary') AS proprietary_token_pct,
    max(share_pct) FILTER (WHERE label = 'Open-weight') AS open_token_pct
FROM dbx_layer_week
WHERE segment = 'split'
GROUP BY week_start, week;

-- Per week × vendor × metric × segment: the vendor's share of its segment (sum of its layers) and, for tokens,
-- of all tokens. Unmapped groups ("Other proprietary", "Other open-weight") are `_other`.
CREATE OR REPLACE TABLE dbx_vendor_share_week AS
SELECT
    l.week_start,
    l.week,
    l.vendor_id,
    l.metric,
    l.segment,
    sum(l.share_pct) AS share_of_segment_pct,
    count(*) AS layers,
    CASE
        WHEN l.metric = 'tokens' THEN sum(l.share_pct) * any_value(
            CASE l.segment WHEN 'proprietary' THEN x.proprietary_token_pct ELSE x.open_token_pct END
        ) / 100
    END AS share_of_all_pct
FROM dbx_layer_week l
JOIN dbx_segment_mix_week x USING (week_start)
WHERE l.segment <> 'split'
GROUP BY l.week_start, l.week, l.vendor_id, l.metric, l.segment;
