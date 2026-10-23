-- inputs: artificial_analysis
-- Artificial Analysis marts: models and per-eval scores from ONE snapshot (Author-only, PLAN §4.4).
-- Variables set by cachereg.build: as_of, artificial_analysis_cutoff.
-- Assumptions (documented in every analysis that uses these marts):
--   * the snapshot is the latest fetch made on or before the cutoff (build refuses an as-of before
--     the first snapshot); AA re-runs and re-versions its evals, so a score is the value in that
--     snapshot, not the value published when the model was released.
--   * only models released on or before as_of are kept (release date is AA's); a model with no
--     release date is excluded and counted in aa_undated.
--   * scores are as published: the indexes on AA's 0–100 scale, single evals as 0–1 fractions.

CREATE OR REPLACE TABLE aa_snapshot AS
SELECT fetch_id, fetched_at, snapshot_date
FROM (SELECT DISTINCT fetch_id, fetched_at, snapshot_date FROM stg_artificial_analysis_models)
WHERE snapshot_date <= getvariable('artificial_analysis_cutoff')
ORDER BY fetched_at DESC, fetch_id DESC
LIMIT 1;

CREATE OR REPLACE TABLE aa_models AS
SELECT m.slug, m.name, m.release_date, m.creator_slug, m.creator_name, m.aa_id, m.snapshot_date, m.fetch_id
FROM stg_artificial_analysis_models m
JOIN aa_snapshot USING (fetch_id)
WHERE m.release_date <= getvariable('as_of');

CREATE OR REPLACE TABLE aa_evals AS
SELECT e.slug, e.metric, e.value, m.release_date, m.creator_name, m.fetch_id
FROM stg_artificial_analysis_evaluations e
JOIN aa_models m ON m.fetch_id = e.fetch_id AND m.slug = e.slug;

CREATE OR REPLACE TABLE aa_undated AS
SELECT count(*) AS models
FROM stg_artificial_analysis_models m
JOIN aa_snapshot USING (fetch_id)
WHERE m.release_date IS NULL;
