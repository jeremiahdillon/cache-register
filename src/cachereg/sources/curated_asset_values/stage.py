"""Stage the curated asset values: the newest stored copy only, after checking it is append-only.

Every older stored copy must appear unchanged in the newest (rows are only appended), so `asset_values`
holds each `id` once, and mart 110 selects rows by `recorded_on` and `supersedes` as of `as_of` (Exact).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import polars as pl
import yaml

from cachereg.core.paths import staged_dir
from cachereg.core.store import list_fetches
from cachereg.sources._curated import CuratedError
from cachereg.sources.curated_asset_values import dataset

SOURCE = "curated_asset_values"
DATES = ("statement_date", "period_start", "period_end", "recorded_on")
SCHEMA = {
    "id": pl.String,
    "statement_date": pl.Date,
    "asset": pl.String,
    "entity": pl.String,
    "metric": pl.String,
    "value_as_stated": pl.String,
    "value": pl.Float64,
    "unit": pl.String,
    "qualifier": pl.String,
    "period_start": pl.Date,
    "period_end": pl.Date,
    "scope": pl.String,
    "source_url": pl.String,
    "source_kind": pl.String,
    "source_quote": pl.String,
    "recorded_on": pl.Date,
    "supersedes": pl.String,
    "notes": pl.String,
    "fetch_id": pl.String,
}
ASSETS_SCHEMA = {"asset": pl.String, "asset_label": pl.String, "era": pl.String, "layer": pl.String}
METRICS_SCHEMA = {"metric": pl.String, "definition": pl.String, "units": pl.List(pl.String)}


def vintage_at(as_of: date) -> dict | None:
    """The dataset as known on ``as_of`` (PLAN §4.4): the newest `recorded_on` on or before it."""
    path = staged_dir(SOURCE) / "asset_values.parquet"
    if not path.is_file():
        return None
    seen = pl.read_parquet(path, columns=["recorded_on"]).filter(pl.col("recorded_on") <= as_of)
    if seen.is_empty():
        return None
    return {"kind": "recorded_on", "value": f"{seen.height} rows", "date": seen["recorded_on"].max().isoformat()}


def stage() -> dict[str, pl.DataFrame]:
    fetches = list_fetches(SOURCE)
    if not fetches:
        raise ValueError(f"{SOURCE}: no stored copy (run `cachereg fetch {SOURCE}`)")
    newest = fetches[-1]
    body = newest.read(dataset.FILE)
    for older in fetches[:-1]:
        try:
            dataset.check_append_only(older.read(dataset.FILE), body)
        except CuratedError as e:
            raise ValueError(f"{SOURCE}: copy {newest.manifest['fetch_id']} is not append-only over "
                             f"{older.manifest['fetch_id']}: {e}") from None  # fmt: skip
    vocab = dataset.check_vocab(yaml.safe_load(newest.read(dataset.VOCAB)) or {})
    out = []
    for r in dataset.validate(body, vocab):
        row = dict(r)
        for col in DATES:
            row[col] = date.fromisoformat(r[col])
        row["value"] = float(Decimal(r["value"]))
        row["supersedes"] = r["supersedes"] or None
        row["notes"] = r["notes"] or None
        out.append(row | {"fetch_id": newest.manifest["fetch_id"]})
    assets = [
        {"asset": k, "asset_label": v["label"], "era": v["era"], "layer": v["layer"]}
        for k, v in vocab["assets"].items()
    ]
    metrics = [
        {"metric": k, "definition": " ".join(str(v["definition"]).split()), "units": list(v["units"])}
        for k, v in vocab["metrics"].items()
    ]
    return {
        "asset_values": pl.DataFrame(out, schema=SCHEMA, orient="row"),
        "assets": pl.DataFrame(assets, schema=ASSETS_SCHEMA, orient="row"),
        "metrics": pl.DataFrame(metrics, schema=METRICS_SCHEMA, orient="row"),
        "_rejected_rows": pl.DataFrame({"rejected": [0]}),
    }
