-- inputs: github_innovation_graph
-- GitHub activity marts: quarterly git pushes and developer accounts by economy from the GitHub
-- Innovation Graph, as released on or before as_of (Exact: each release is a commit, selected by its date).
-- Variables set by cachereg.build: as_of.
-- Assumptions (documented in every analysis that uses these marts):
--   * public activity only (pushes to public repositories); bots and accounts with inhuman activity
--     volumes are excluded by GitHub; economies under 100 active developers in a quarter are suppressed.
--   * git_pushes counts pushes, not commits (a push may hold many); web edits on github.com are pushes.
--   * developers counts accounts located in the economy at the quarter's end, active or not.
--   * `_world` sums every economy except aggregates (EU), so it misses suppressed economies.

CREATE OR REPLACE TABLE github_quarterly AS
WITH rel AS (
    SELECT release_sha, release_date FROM stg_github_innovation_graph_releases
    WHERE release_date <= getvariable('as_of')
    ORDER BY release_date DESC, release_sha DESC
    LIMIT 1
),
q AS (
    SELECT s.economy, s.is_aggregate, make_date(s.year, 3 * s.quarter - 2, 1) AS cal_quarter, s.metric, s.value,
        s.release_sha, s.release_date
    FROM stg_github_innovation_graph_quarterly s
    JOIN rel USING (release_sha)
),
wide AS (
    SELECT economy, is_aggregate, cal_quarter,
        max(value) FILTER (WHERE metric = 'git_pushes') AS git_pushes,
        max(value) FILTER (WHERE metric = 'developers') AS developers,
        any_value(release_sha) AS release_sha,
        any_value(release_date) AS release_date
    FROM q
    GROUP BY ALL
)
SELECT * FROM wide
UNION ALL
SELECT '_world', false, cal_quarter, sum(git_pushes), sum(developers), any_value(release_sha), any_value(release_date)
FROM wide WHERE NOT is_aggregate
GROUP BY cal_quarter
ORDER BY economy, cal_quarter;
