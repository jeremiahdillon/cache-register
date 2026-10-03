"""`cachereg build`: raw → staged Parquet → DuckDB marts (idempotent, fully rebuilt; PLAN §4.1).

A mart is one SQL file in `cachereg/marts/` whose header declares its inputs
(`-- inputs: source_a, source_b`). `build(sources=…)` stages only those sources and runs only the
marts whose inputs are all among them, so one receipt can be rebuilt without anything else.
Before marts run, each staged source gets a DuckDB variable `<source_id>_cutoff` (the fetch date
chosen for `as_of`), plus `as_of`; mart SQL reads only these.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from importlib import resources

import duckdb
import polars as pl
import yaml

from cachereg.core.paths import REPO_ROOT, staged_dir, warehouse_path
from cachereg.core.registry import load_sources
from cachereg.core.store import list_fetches

INPUTS_RE = re.compile(r"^--\s*inputs:\s*(.+)$", re.M)
TABLE_RE = re.compile(r"CREATE\s+OR\s+REPLACE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_]*)", re.I)


@dataclass(frozen=True)
class Mart:
    name: str
    inputs: frozenset[str]
    tables: tuple[str, ...]
    sql: str


@dataclass
class BuildReport:
    as_of: date
    sources: list[str] = field(default_factory=list)
    staged: dict[str, int] = field(default_factory=dict)
    rejected: dict[str, int] = field(default_factory=dict)
    vintages: dict[str, dict] = field(default_factory=dict)
    marts_built: list[str] = field(default_factory=list)
    marts_skipped: list[str] = field(default_factory=list)


class VintageGapError(RuntimeError):
    """An Author-only (snapshot) source has no fetch on or before the requested as-of date."""


def load_marts() -> list[Mart]:
    marts = []
    for f in sorted(resources.files("cachereg.marts").iterdir(), key=lambda p: p.name):
        if not f.name.endswith(".sql"):
            continue
        sql = f.read_text()
        m = INPUTS_RE.search(sql)
        if not m:
            raise ValueError(f"mart {f.name} has no '-- inputs:' header")
        inputs = frozenset(s.strip() for s in m.group(1).split(",") if s.strip())
        marts.append(Mart(f.name.removesuffix(".sql"), inputs, tuple(TABLE_RE.findall(sql)), sql))
    return marts


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


def _stage(source_ids: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    sources = load_sources()
    counts, rejected = {}, {}
    for sid in source_ids:
        out = staged_dir(sid)
        out.mkdir(parents=True, exist_ok=True)
        for table, df in sources[sid].module("stage").stage().items():
            if table.startswith("_rejected"):
                rejected[sid] = int(df["rejected"][0])
                continue
            df.write_parquet(out / f"{table}.parquet")
            counts[f"{sid}.{table}"] = df.height
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


def select_sources(requested: list[str] | None) -> list[str]:
    """Requested sources (validated), or every enabled source that has fetches."""
    sources = load_sources()
    if requested is None:
        return [s.id for s in sources.values() if s.enabled and list_fetches(s.id)]
    unknown = [s for s in requested if s not in sources]
    if unknown:
        raise ValueError(f"unknown source(s): {', '.join(unknown)}")
    return list(dict.fromkeys(requested))


def build(as_of: date, sources: list[str] | None = None) -> BuildReport:
    selected = select_sources(sources)
    no_data = [s for s in selected if not list_fetches(s)]
    if no_data:
        raise VintageGapError(f"no fetches yet for: {', '.join(no_data)} (run `cachereg fetch` first)")
    report = BuildReport(as_of=as_of, sources=selected)
    report.staged, report.rejected = _stage(selected)
    marts = load_marts()

    wh = warehouse_path()
    wh.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(wh))
    try:
        for sid in selected:
            for parquet in sorted(staged_dir(sid).glob("*.parquet")):
                view = f"stg_{sid}_{parquet.stem}"
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
        for sid in selected:
            day, after = cutoff(sid, as_of)
            con.execute(f"SET VARIABLE {sid}_cutoff = ?::DATE", [day])
            report.vintages[sid] = {"fetch_date": str(day), "vintage_after_as_of": after}

        # Every mart's tables are dropped first, so a table from an earlier or broader build can
        # never be read as if it were current.
        for mart in marts:
            for table in reversed(mart.tables):
                con.execute(f"DROP TABLE IF EXISTS {table}")
        chosen = set(selected)
        for mart in marts:
            if mart.inputs <= chosen:
                con.execute(mart.sql)
                report.marts_built.append(mart.name)
            elif mart.inputs & chosen:
                missing = ", ".join(sorted(mart.inputs - chosen))
                raise RuntimeError(f"mart {mart.name} needs {', '.join(sorted(mart.inputs))}; missing: {missing}")
            else:
                report.marts_skipped.append(mart.name)
    finally:
        con.close()
    return report
