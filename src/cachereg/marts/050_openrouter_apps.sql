-- inputs: openrouter_apps
-- OpenRouter app marts (docs/plans/2026-10-07-openrouter-apps-session-cost.md): weekly top-200
-- public apps by tokens, Latest-only. Variables set by cachereg.build: as_of, openrouter_apps_cutoff.
-- Assumptions (documented in every analysis that uses these marts):
--   * a week's rows all come from ONE fetch: the latest on/before the cutoff that holds the week.
--     A later vintage can drop an app (hidden or merged into another), so rows are never mixed
--     across fetches.
--   * only complete weeks with week_end <= as_of.
--   * tags are the newest tag fetch's (current tags), applied to every week; an app outside a
--     filter's top 200 in the tag week has no tag of that kind.

CREATE OR REPLACE TABLE or_app_weekly AS
WITH pick AS (
    SELECT week_start, max(fetch_id) AS fetch_id
    FROM stg_openrouter_apps_weekly
    WHERE CAST(fetched_at AS DATE) <= getvariable('openrouter_apps_cutoff')
    GROUP BY week_start
)
SELECT
    w.week_start,
    w.week_end,
    w.app_id,
    w.app_name,
    w.rank,
    w.total_tokens,
    w.total_requests,
    w.total_tokens / nullif(w.total_requests, 0) AS tokens_per_request,
    w.fetch_id
FROM stg_openrouter_apps_weekly w
JOIN pick USING (week_start, fetch_id)
WHERE w.week_end <= getvariable('as_of');

CREATE OR REPLACE TABLE or_app_tags AS
SELECT t.app_id, t.app_name, t.tag_kind, t.tag, t.rank_in_tag, t.tag_week_start, t.fetch_id
FROM stg_openrouter_apps_tags t
WHERE t.fetch_id = (
    SELECT max(fetch_id) FROM stg_openrouter_apps_tags
    WHERE CAST(fetched_at AS DATE) <= getvariable('openrouter_apps_cutoff')
);

CREATE OR REPLACE TABLE or_app_dim AS
WITH seen AS (
    SELECT
        app_id,
        arg_max(app_name, week_start) AS app_name,
        min(week_start) AS first_week,
        max(week_start) AS last_week,
        count(*) AS weeks_in_top200
    FROM or_app_weekly
    GROUP BY app_id
), tagged AS (
    SELECT
        app_id,
        list_sort(list(DISTINCT tag) FILTER (WHERE tag_kind = 'category')) AS categories,
        list_sort(list(DISTINCT tag) FILTER (WHERE tag_kind = 'subcategory')) AS subcategories
    FROM or_app_tags
    GROUP BY app_id
)
SELECT
    s.*,
    coalesce(t.categories, []::VARCHAR[]) AS categories,
    coalesce(t.subcategories, []::VARCHAR[]) AS subcategories
FROM seen s
LEFT JOIN tagged t USING (app_id);

-- Tokens per week × tag. An app counts under each of its tags, so one tag_kind's rows can sum to
-- more than the week's total (tags_overlap); `untagged` holds apps with no tag of that kind.
CREATE OR REPLACE TABLE or_app_category_weekly AS
WITH kinds AS (
    SELECT unnest(['category', 'subcategory']) AS tag_kind
), labelled AS (
    SELECT w.week_start, w.app_id, w.total_tokens, w.total_requests, k.tag_kind, coalesce(t.tag, 'untagged') AS tag
    FROM or_app_weekly w
    CROSS JOIN kinds k
    LEFT JOIN (SELECT DISTINCT app_id, tag_kind, tag FROM or_app_tags) t
        ON t.app_id = w.app_id AND t.tag_kind = k.tag_kind
), overlap AS (
    SELECT week_start, tag_kind, count(*) > count(DISTINCT app_id) AS tags_overlap
    FROM labelled
    GROUP BY week_start, tag_kind
)
SELECT
    l.week_start,
    l.tag_kind,
    l.tag,
    CAST(sum(l.total_tokens) AS BIGINT) AS total_tokens,
    CAST(sum(l.total_requests) AS BIGINT) AS total_requests,
    count(*) AS apps,
    any_value(o.tags_overlap) AS tags_overlap
FROM labelled l
JOIN overlap o USING (week_start, tag_kind)
GROUP BY l.week_start, l.tag_kind, l.tag;
