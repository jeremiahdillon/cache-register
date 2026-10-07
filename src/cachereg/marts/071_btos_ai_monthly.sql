-- inputs: census_btos
-- Census BTOS AI use by calendar month, to sit beside monthly series such as Ramp's
-- (docs/plans/2026-10-07-census-btos.md). Uses btos_ai_use (mart 070); `yes` answers only.
-- Method (Cache Register's derivation, not a Census estimate): each cycle's reference fortnight (the
-- two weeks its question asks about) is split across calendar months by day; a month's value is the
-- day-weighted mean of the published cycles that touch it. SE = sqrt(sum((w_i / W)^2 * se_i^2)),
-- treating the cycles' panels (different businesses) as independent samples: an approximation.
-- Wordings are never averaged together; months with no published reference day are absent (never
-- interpolated). `has_suppression`: a cycle touching the month was suppressed, and suppression hits
-- small estimates, so the mean of the rest leans high. `partial`: under half the month covered.

CREATE OR REPLACE TABLE btos_ai_monthly AS
WITH days AS (
    SELECT u.*, CAST(d.day AS DATE) AS day
    FROM btos_ai_use u,
         unnest(generate_series(CAST(u.reference_start AS TIMESTAMP), CAST(u.reference_end AS TIMESTAMP),
                                INTERVAL 1 DAY)) AS d(day)
    WHERE u.answer = 'yes'
),
per_cycle AS (
    SELECT
        wording, question, breakdown, group_key, sector_code, naics, naics_title, size_class,
        CAST(date_trunc('month', day) AS DATE) AS month,
        cycle, status, estimate_pct, se_pct,
        count(*) AS days
    FROM days
    GROUP BY ALL
),
monthly AS (
    SELECT
        wording, question, breakdown, group_key, sector_code, naics, naics_title, size_class, month,
        sum(days * estimate_pct) FILTER (WHERE status = 'published')
            / sum(days) FILTER (WHERE status = 'published') AS pct,
        CASE WHEN count(se_pct) FILTER (WHERE status = 'published') = count(*) FILTER (WHERE status = 'published')
             THEN sqrt(sum(power(days * se_pct, 2)) FILTER (WHERE status = 'published'))
                  / sum(days) FILTER (WHERE status = 'published')
        END AS se,
        coalesce(sum(days) FILTER (WHERE status = 'published'), 0) AS ref_days_covered,
        count(*) FILTER (WHERE status = 'published') AS n_cycles,
        count(*) FILTER (WHERE status = 'suppressed') AS n_suppressed,
        string_agg(cycle, ',' ORDER BY cycle) AS cycles
    FROM per_cycle
    GROUP BY ALL
)
SELECT
    month,
    wording,
    question,
    breakdown,
    group_key,
    sector_code,
    naics,
    naics_title,
    size_class,
    pct,
    se,
    greatest(pct - 1.645 * se, 0) AS low90_pct,
    least(pct + 1.645 * se, 100) AS high90_pct,
    ref_days_covered,
    CAST(dayofmonth(last_day(month)) AS BIGINT) AS days_in_month,
    n_cycles,
    n_suppressed,
    ref_days_covered < dayofmonth(last_day(month)) / 2 AS partial,
    n_suppressed > 0 AS has_suppression,
    cycles
FROM monthly
WHERE n_cycles > 0
ORDER BY breakdown, group_key, question, wording, month;
