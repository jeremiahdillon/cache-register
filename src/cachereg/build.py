"""`cachereg build`: raw → staged Parquet → DuckDB marts (idempotent, fully rebuilt; PLAN §4.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from importlib import resources

import duckdb
import polars as pl
import yaml

from cachereg.core.paths import REPO_ROOT, staged_dir, warehouse_path
from cachereg.core.registry import load_sources
from cachereg.core.store import list_fetches


@dataclass
class BuildReport:
    as_of: date
    staged: dict[str, int] = field(default_factory=dict)
    rejected: dict[str, int] = field(default_factory=dict)
    vintages: dict[str, dict] = field(default_factory=dict)


def stage_all() -> tuple[dict[str, int], dict[str, int]]:
    counts, rejected = {}, {}
    for src in load_sources().values():
        if not src.enabled or not list_fetches(src.id):
            continue
        out = staged_dir(src.id)
        out.mkdir(parents=True, exist_ok=True)
        for table, df in src.module("stage").stage().items():
            if table.startswith("_rejected"):
                rejected[src.id] = int(df["rejected"][0])
                continue
            df.write_parquet(out / f"{table}.parquet")
            counts[f"{src.id}.{table}"] = df.height
    return counts, rejected


def _vendor_alias_frame() -> pl.DataFrame:
    data = yaml.safe_load((REPO_ROOT / "config" / "entities" / "vendors.yaml").read_text())
    rows = [
        {
            "vendor_id": vid,
            "vendor_name": v["name"],
            "open_weights": v["open_weights"],
            "hq": v.get("hq"),
            "source": s,
            "alias": a,
        }
        for vid, v in data["vendors"].items()
        for s, aliases in v.get("aliases", {}).items()
        for a in aliases
    ]
    return pl.DataFrame(rows)


class VintageGapError(RuntimeError):
    """An Author-only (snapshot) source has no fetch on or before the requested as-of date."""


def cutoff(source: str, as_of: date) -> tuple[date, bool]:
    """The fetch date to use for ``as_of`` and whether it is *after* as_of (PLAN §4.4).

    Latest-only sources (``revisions: revised``) fall back to their earliest fetch, flagged.
    Snapshot sources (Author-only) never substitute later data: the gap is an error.
    """
    dates = sorted({f.fetched_at.date() for f in list_fetches(source)})
    if not dates:
        raise VintageGapError(f"{source}: no fetches at all")
    on_or_before = [d for d in dates if d <= as_of]
    if on_or_before:
        return on_or_before[-1], False
    if load_sources()[source].history == "snapshot":
        raise VintageGapError(
            f"{source}: no snapshot on or before {as_of} (first is {dates[0]}); snapshot sources cannot be back-filled"
        )
    return dates[0], True


def build(as_of: date) -> BuildReport:
    report = BuildReport(as_of=as_of)
    report.staged, report.rejected = stage_all()
    wh = warehouse_path()
    wh.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(wh))
    try:
        for parquet in sorted(p for p in staged_dir("").glob("*/*.parquet") if not p.parent.name.startswith("_")):
            view = f"stg_{parquet.parent.name}_{parquet.stem}"
            if not view.isidentifier() or "'" in parquet.as_posix():
                raise ValueError(f"unsafe staged path {parquet.name!r}")
            # Names come from our own registry/stage code and are validated above.
            con.execute(f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM read_parquet('{parquet.as_posix()}')")  # noqa: S608
        vendor_file = staged_dir("_entities") / "vendor_alias.parquet"
        vendor_file.parent.mkdir(parents=True, exist_ok=True)
        _vendor_alias_frame().write_parquet(vendor_file)
        con.execute(
            "CREATE OR REPLACE TABLE dim_vendor_alias AS SELECT * FROM read_parquet(?)", [vendor_file.as_posix()]
        )
        con.execute("SET VARIABLE as_of = ?::DATE", [as_of])
        # Marts are rebuilt from scratch every time: drop first so a stale table can never survive.
        for table in ("or_vendor_weekly", "or_model_daily", "or_rankings_daily"):
            con.execute(f"DROP TABLE IF EXISTS {table}")
        have = {s: bool(list_fetches(s)) for s in ("openrouter_rankings", "openrouter_models")}
        if any(have.values()) and not all(have.values()):
            missing = ", ".join(s for s, ok in have.items() if not ok)
            raise RuntimeError(f"OpenRouter marts need both sources; no fetches yet for: {missing}")
        if all(have.values()):
            rank_cut, rank_after = cutoff("openrouter_rankings", as_of)
            price_cut, price_after = cutoff("openrouter_models", as_of)
            con.execute("SET VARIABLE rankings_fetch_cutoff = ?::DATE", [rank_cut])
            con.execute("SET VARIABLE price_snapshot = ?::DATE", [price_cut])
            report.vintages["openrouter_rankings"] = {"fetch_cutoff": str(rank_cut), "vintage_after_as_of": rank_after}
            report.vintages["openrouter_models"] = {"snapshot": str(price_cut), "vintage_after_as_of": price_after}
            sql = resources.files("cachereg.marts").joinpath("010_openrouter_usage.sql").read_text()
            con.execute(sql)
    finally:
        con.close()
    return report
