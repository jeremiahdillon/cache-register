"""Stage Epoch's benchmark data: model versions, ECI, benchmark metadata and scores, per vintage.

Each distinct zip (content hash) is staged once under its `vintage_id`; `vintages` maps every
fetch to one. Marts pick a single vintage via `epoch_benchmarks_cutoff` (PLAN §4.4, Latest-only).
Scores are read only for benchmarks whose `benchmark_metadata.csv` row names a source file and a
score column; the column is never guessed.
"""

from __future__ import annotations

import polars as pl

from cachereg.sources._epoch_zip import Counter, distinct_vintages, read_csv, text
from cachereg.sources.epoch_benchmarks.fetch import FILE, REQUIRED

SOURCE = "epoch_benchmarks"
ECI_FILE = "epoch_capabilities_index/eci_scores.csv"

MODELS_SCHEMA = {
    "vintage_id": pl.String,
    "model_version": pl.String,
    "model_group": pl.String,
    "release_date": pl.Date,  # partial dates: first day of the period, see release_date_precision
    "release_date_precision": pl.String,  # day | month | year
    "display_name": pl.String,
    "organization": pl.String,
    "country": pl.String,
    "accessibility": pl.String,
    "training_compute_flop": pl.Float64,
}
ECI_SCHEMA = {
    "vintage_id": pl.String,
    "model_group": pl.String,
    "display_name": pl.String,
    "eci": pl.Float64,
    "eci_ci_low": pl.Float64,
    "eci_ci_high": pl.Float64,
    "release_date": pl.Date,
    "release_date_precision": pl.String,
    "organization": pl.String,
    "country": pl.String,
    "accessibility": pl.String,
    "accessibility_group": pl.String,
}
BENCHMARKS_SCHEMA = {
    "vintage_id": pl.String,
    "benchmark": pl.String,
    "in_eci": pl.Boolean,
    "source_file": pl.String,
    "score_column": pl.String,
    "scale": pl.Float64,
    "random_baseline": pl.Float64,
    "score_ceiling": pl.Float64,
    "release_date": pl.Date,
    "superseded_by": pl.String,
}
SCORES_SCHEMA = {
    "vintage_id": pl.String,
    "benchmark": pl.String,
    "model_version": pl.String,  # null for rows Epoch lists without a model version
    "row": pl.Int64,  # 1-based data row in the source file: repeated runs of one version stay distinct
    "row_id": pl.String,  # the file's own `id` column, when it has one
    "score": pl.Float64,  # as published, in the file's own unit
    "scale": pl.Float64,
    "score_norm": pl.Float64,  # score × scale (Epoch's metadata maps every benchmark to 0–1 this way)
    "score_column": pl.String,
    "source_file": pl.String,
}


def _models(vid, zf, bad: Counter) -> list[dict]:
    """One row per model version. A version listed twice keeps its first row; the repeat is counted
    as rejected (a duplicate would multiply every score row joined to it)."""
    out, seen = [], set()
    for r in read_csv(zf, "model_metadata.csv")[1]:
        version = text(r.get("model_version"))
        if version is None or r.get("model_version") in seen:  # no version: cannot be keyed
            bad.n += 1
            continue
        seen.add(r.get("model_version"))
        day, precision = bad.day(r.get("date"))
        out.append(
            {
                "vintage_id": vid,
                "model_version": r.get("model_version"),  # verbatim (upstream keys can carry spaces)
                "model_group": text(r.get("model_group")),
                "release_date": day,
                "release_date_precision": precision,
                "display_name": text(r.get("display_name")),
                "organization": text(r.get("organization")),
                "country": text(r.get("country")),
                "accessibility": text(r.get("accessibility")),
                "training_compute_flop": bad.num(r.get("training_compute_flop")),
            }
        )
    return out


def _eci(vid, zf, bad: Counter) -> list[dict]:
    out = []
    for r in read_csv(zf, ECI_FILE)[1]:
        group = text(r.get("Model"))
        if group is None:  # an index value for no model: rejected
            bad.n += 1
            continue
        day, precision = bad.day(r.get("date"))
        out.append(
            {
                "vintage_id": vid,
                "model_group": group,
                "display_name": text(r.get("Display name")),
                "eci": bad.num(r.get("eci")),
                "eci_ci_low": bad.num(r.get("eci_ci_low")),
                "eci_ci_high": bad.num(r.get("eci_ci_high")),
                "release_date": day,
                "release_date_precision": precision,
                "organization": text(r.get("Organization")),
                "country": text(r.get("Country (of organization)")),
                "accessibility": text(r.get("Model accessibility")),
                "accessibility_group": text(r.get("Accessibility group")),
            }
        )
    return out


def _benchmarks(vid, zf, bad: Counter) -> list[dict]:
    return [
        {
            "vintage_id": vid,
            "benchmark": text(r.get("benchmark")),
            "in_eci": bad.flag(r.get("in_eci")),
            "source_file": text(r.get("source_file")),
            "score_column": text(r.get("score_column")),
            "scale": bad.num(r.get("scale")),
            "random_baseline": bad.num(r.get("random_baseline")),
            "score_ceiling": bad.num(r.get("score_ceiling")),
            "release_date": bad.day(r.get("release_date"))[0],
            "superseded_by": text(r.get("superseded_by")),
        }
        for r in read_csv(zf, "benchmark_metadata.csv")[1]
    ]


def _scores(vid, zf, benchmarks: list[dict], bad: Counter) -> list[dict]:
    out = []
    names = set(zf.namelist())
    for b in benchmarks:
        src, col = b["source_file"], b["score_column"]
        if not src or not col:
            continue  # described without a score column: not read (SOURCE.md, known gaps)
        if src not in names:
            raise ValueError(f"{SOURCE}: benchmark {b['benchmark']!r} lists {src}, which is not in the zip")
        header, rows = read_csv(zf, src)
        for needed in ("Model version", col):
            if needed not in header:
                raise ValueError(f"{SOURCE}: {src} has no column {needed!r} (benchmark {b['benchmark']!r})")
        scale = b["scale"] if b["scale"] is not None else 1.0
        for i, r in enumerate(rows, start=1):
            score = bad.num(r.get(col))
            if score is None:
                continue  # empty (normal in multi-score files) or counted as rejected
            out.append(
                {
                    "vintage_id": vid,
                    "benchmark": b["benchmark"],
                    "model_version": r.get("Model version") if text(r.get("Model version")) else None,
                    "row": i,
                    "row_id": text(r.get("id")),
                    "score": score,
                    "scale": scale,
                    "score_norm": score * scale,
                    "score_column": col,
                    "source_file": src,
                }
            )
    return out


def stage() -> dict[str, pl.DataFrame]:
    vintages, zips = distinct_vintages(SOURCE, FILE, REQUIRED)
    bad = Counter()
    models, eci, benchmarks, scores = [], [], [], []
    for vid, zf in zips:
        models += _models(vid, zf, bad)
        eci += _eci(vid, zf, bad)
        bench = _benchmarks(vid, zf, bad)
        benchmarks += bench
        scores += _scores(vid, zf, bench, bad)
    return {
        "vintages": vintages,
        "models": pl.DataFrame(models, schema=MODELS_SCHEMA),
        "eci": pl.DataFrame(eci, schema=ECI_SCHEMA),
        "benchmarks": pl.DataFrame(benchmarks, schema=BENCHMARKS_SCHEMA),
        "scores": pl.DataFrame(scores, schema=SCORES_SCHEMA),
        "_rejected_rows": bad.frame(),
    }
