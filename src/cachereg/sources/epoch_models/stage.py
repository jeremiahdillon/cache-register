"""Stage Epoch's "Data on AI models": one row per model per vintage, a fixed column subset.

`all_ai_models.csv` is the superset; membership in the notable, frontier and large-scale files is
kept as flags. Unparseable numbers and dates become null and are counted (cells) in
`_rejected_rows`.
"""

from __future__ import annotations

import polars as pl

from cachereg.sources._epoch_zip import Counter, distinct_vintages, read_csv, text
from cachereg.sources.epoch_models.fetch import FILE, REQUIRED, SUBSETS

SOURCE = "epoch_models"
TEXT = {  # staged column -> CSV column
    "organization": "Organization",
    "domain": "Domain",
    "task": "Task",
    "model_accessibility": "Model accessibility",
    "country": "Country (of organization)",
    "base_model": "Base model",
    "notability_criteria": "Notability criteria",
    "confidence": "Confidence",
    "last_modified": "Last modified",
}
NUMBERS = {
    "parameters": "Parameters",
    "training_compute_flop": "Training compute (FLOP)",
    "training_compute_cost_2023_usd": "Training compute cost (2023 USD)",
}
FLAGS = {"open_model_weights": "Open model weights?", "frontier_model": "Frontier model"}
MODELS_SCHEMA = {
    "vintage_id": pl.String,
    "model": pl.String,
    "publication_date": pl.Date,
    "publication_date_precision": pl.String,  # day | month | year
    **{k: pl.String for k in TEXT},
    **{k: pl.Float64 for k in NUMBERS},
    **{k: pl.Boolean for k in FLAGS},
    **{k: pl.Boolean for k in SUBSETS},
}


def stage() -> dict[str, pl.DataFrame]:
    vintages, zips = distinct_vintages(SOURCE, FILE, REQUIRED)
    bad = Counter()
    rows = []
    for vid, zf in zips:
        header, models = read_csv(zf, "all_ai_models.csv")
        needed = ["Model", "Publication date", *TEXT.values(), *NUMBERS.values(), *FLAGS.values()]
        missing = [c for c in needed if c not in header]
        if missing:
            raise ValueError(f"{SOURCE}: all_ai_models.csv has no column(s) {', '.join(map(repr, missing))}")
        members = {}
        for flag, member in SUBSETS.items():
            sub_header, sub_rows = read_csv(zf, member)
            if "Model" not in sub_header:
                raise ValueError(f"{SOURCE}: {member} has no column 'Model'")
            members[flag] = {text(r.get("Model")) for r in sub_rows} - {None}
        for r in models:
            name = text(r.get("Model"))
            if name is None:
                bad.n += 1
                continue
            day, precision = bad.day(r.get("Publication date"))
            rows.append(
                {
                    "vintage_id": vid,
                    "model": name,
                    "publication_date": day,
                    "publication_date_precision": precision,
                    **{k: text(r.get(c)) for k, c in TEXT.items()},
                    **{k: bad.num(r.get(c)) for k, c in NUMBERS.items()},
                    **{k: bad.flag(r.get(c)) for k, c in FLAGS.items()},
                    **{flag: name in names for flag, names in members.items()},
                }
            )
    return {"vintages": vintages, "models": pl.DataFrame(rows, schema=MODELS_SCHEMA), "_rejected_rows": bad.frame()}
