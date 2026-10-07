"""Stage every Ramp AI Index import (all kept; marts pick the latest import of each cut).

Tables: `adoption`, `spend_per_employee`, `spend_share`, `token_index`, `token_price` (the series,
each row tagged with its cut and import), `imports` (one row per import), `cuts` (the cut registry, so
marts can report never-imported cuts) and `sectors` (config/entities/sectors.yaml, Ramp labels →
NAICS). Labels stay as Ramp writes them; marts join vendors and sectors.
"""

from __future__ import annotations

from collections import defaultdict

import polars as pl
import yaml

from cachereg.core.paths import entities_dir
from cachereg.core.store import list_fetches
from cachereg.sources.ramp_ai_index import cuts

SOURCE = "ramp_ai_index"
TAG = {"cut": pl.String, "fetch_id": pl.String, "fetched_at": pl.Datetime("us", "UTC")}
SCHEMAS = {
    "adoption": TAG | {
        "month": pl.Date, "series_kind": pl.String, "series_label": pl.String, "adoption_pct": pl.Float64,
        "mom_pp": pl.Float64, "yoy_pp": pl.Float64, "census_question_version": pl.String,
    },
    "spend_per_employee": TAG | {
        "month": pl.Date, "dimension": pl.String, "group_label": pl.String, "statistic": pl.String,
        "usd_per_employee_month": pl.Float64,
    },
    "spend_share": TAG | {"month": pl.Date, "scope": pl.String, "sector_label": pl.String, "ai_share_pct": pl.Float64},
    "token_index": TAG | {"week": pl.Date, "measure": pl.String, "maker_label": pl.String, "index_value": pl.Float64},
    "token_price": TAG | {
        "day": pl.Date, "price_kind": pl.String, "series_label": pl.String, "usd_per_mtok": pl.Float64,
    },
}  # fmt: skip
IMPORTS_SCHEMA = TAG | {
    "via": pl.String, "rows": pl.Int64, "first_period": pl.Date, "last_period": pl.Date, "content_sha256": pl.String,
}  # fmt: skip
CUTS_SCHEMA = {"cut": pl.String, "position": pl.Int64, "menu": pl.String, "url": pl.String, "staged_table": pl.String,
               "grain": pl.String}  # fmt: skip
SECTORS_SCHEMA = {"naics": pl.String, "title": pl.String, "assumed": pl.Boolean, "label": pl.String}
OVERALL_SHARE = "AI share of business spend (%)"
STATISTICS = {"Median": "median", "Top 10%": "top_10pct", "Top 1%": "top_1pct"}


def series_kind(cut_id: str, label: str) -> str:
    kind = cut_id.split("/")[1]
    if label == "Ramp Overall":
        return "overall"
    if kind == "overall":
        return "census" if label == "Census Estimate" else "other"
    return {"models": "vendor", "sector": "sector", "size": "size"}[kind]


def _adoption(cut, cells, tag) -> list[dict]:
    rows = defaultdict(dict)
    for c in cells:
        rows[(c.period, c.key)][c.column] = c.value
    first = {}
    for period, key in rows:
        first[key] = min(first.get(key, period), period)
    out = []
    for (period, key), v in sorted(rows.items()):
        out.append(tag | {
            "month": period, "series_kind": series_kind(cut.id, key), "series_label": key,
            "adoption_pct": v.get("Adoption rate (%)"),
            "mom_pp": None if period == first[key] else v.get("Monthly change (pp)"),  # no prior month: Ramp writes 0
            "yoy_pp": v.get(cuts.YOY), "census_question_version": v.get("Census question version"),
        })  # fmt: skip
    return out


def _spend_per_employee(cut, cells, tag) -> list[dict]:
    dimension = cut.id.split("/")[1]
    out = []
    for c in cells:
        if cut.shape == "wide":  # overall: one column per statistic
            label = c.key.removesuffix(" (USD / employee / month)")
            group, statistic = "All businesses", STATISTICS.get(label, label.lower())
        else:
            group, statistic = c.key, "median"
        out.append(tag | {"month": c.period, "dimension": dimension, "group_label": group, "statistic": statistic,
                          "usd_per_employee_month": c.value})  # fmt: skip
    return out


def _spend_share(cut, cells, tag) -> list[dict]:
    return [
        tag
        | {
            "month": c.period,
            "scope": "overall" if c.key == OVERALL_SHARE else "sector",
            "sector_label": None if c.key == OVERALL_SHARE else c.key.removesuffix(" (%)"),
            "ai_share_pct": c.value,
        }  # fmt: skip
        for c in cells
    ]


def _token_index(cut, cells, tag) -> list[dict]:
    measure = {"token_volume": "volume", "token_spend": "spend"}[cut.id.split("/")[0]]
    return [tag | {"week": c.period, "measure": measure, "maker_label": c.key, "index_value": c.value} for c in cells]


def _token_price(cut, cells, tag) -> list[dict]:
    kind = cut.id.split("/")[1]
    return [tag | {"day": c.period, "price_kind": kind, "series_label": c.key, "usd_per_mtok": c.value} for c in cells]


BUILDERS = {
    "adoption": _adoption,
    "spend_per_employee": _spend_per_employee,
    "spend_share": _spend_share,
    "token_index": _token_index,
    "token_price": _token_price,
}


def load_sectors() -> list[dict]:
    data = yaml.safe_load((entities_dir() / "sectors.yaml").read_text()) or {}
    return [
        {"naics": str(code), "title": s["title"], "assumed": bool(s.get("assumed", False)), "label": label}
        for code, s in (data.get("sectors") or {}).items()
        for label in ((s.get("aliases") or {}).get("ramp") or [])
    ]


def stage() -> dict[str, pl.DataFrame]:
    rows = {t: [] for t in SCHEMAS}
    imports, rejected = [], 0
    for f in list_fetches(SOURCE):
        cut = cuts.BY_ID.get((f.manifest.get("vintage") or {}).get("cut"))
        if cut is None:
            rejected += 1  # a raw import of a cut this adapter no longer knows: counted, never staged
            continue
        try:
            body = f.read(cut.file_name)
        except OSError:
            rejected += 1  # the raw file is missing or unreadable: counted, never fatal
            continue
        try:
            cells = cuts.parse(body, cut)
        except ValueError:
            rejected += max(body.count(b"\n"), 1)  # the import's data rows
            continue
        tag = {"cut": cut.id, "fetch_id": f.manifest["fetch_id"], "fetched_at": f.fetched_at}
        rows[cut.table] += BUILDERS[cut.table](cut, cells, tag)
        periods = [c.period for c in cells]
        request = (f.manifest.get("requests") or [{}])[0]
        imports.append(tag | {
            "via": request.get("via"), "rows": len(set((c.period, c.key) for c in cells)) if cut.shape == "long"
            else len(set(periods)), "first_period": min(periods), "last_period": max(periods),
            "content_sha256": f.manifest["vintage"].get("value"),
        })  # fmt: skip
    out = {t: pl.DataFrame(r, schema=SCHEMAS[t], orient="row") for t, r in rows.items()}
    out["imports"] = pl.DataFrame(imports, schema=IMPORTS_SCHEMA, orient="row")
    out["cuts"] = pl.DataFrame(
        [{"cut": c.id, "position": i, "menu": c.menu, "url": c.url, "staged_table": c.table, "grain": c.grain}
         for i, c in enumerate(cuts.CUTS, start=1)],
        schema=CUTS_SCHEMA, orient="row",
    )  # fmt: skip
    out["sectors"] = pl.DataFrame(load_sectors(), schema=SECTORS_SCHEMA, orient="row")
    out["_rejected_rows"] = pl.DataFrame({"rejected": [rejected]})
    return out
