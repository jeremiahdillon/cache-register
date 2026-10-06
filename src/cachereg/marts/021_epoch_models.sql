-- inputs: epoch_models
-- Epoch "Data on AI models" at ONE vintage (Latest-only, PLAN §4.4).
-- Variables set by cachereg.build: as_of, epoch_models_cutoff.
-- Assumptions: the vintage is the latest fetch made on or before the cutoff date; only models
-- published on or before as_of are kept, a partial date counting from the END of its period
-- (year → Dec 31, month → last day), so a model is never visible before it could exist;
-- model_id via config/entities/models.yaml `aliases.epoch`.

CREATE OR REPLACE TABLE epoch_models_vintage AS
SELECT vintage_id, fetch_id, fetched_at, content_sha256
FROM stg_epoch_models_vintages
WHERE fetch_date <= getvariable('epoch_models_cutoff')
ORDER BY fetched_at DESC, fetch_id DESC
LIMIT 1;

CREATE OR REPLACE TABLE epoch_ai_models AS
SELECT m.* EXCLUDE (vintage_id), a.model_id, m.vintage_id
FROM stg_epoch_models_models m
JOIN epoch_models_vintage v ON v.vintage_id = m.vintage_id
LEFT JOIN dim_model_alias a ON a.source = 'epoch' AND a.alias = m.model
WHERE CASE m.publication_date_precision
          WHEN 'year' THEN CAST(m.publication_date + INTERVAL 1 YEAR - INTERVAL 1 DAY AS DATE)
          WHEN 'month' THEN last_day(m.publication_date)
          ELSE m.publication_date
      END <= getvariable('as_of');
