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

from cachereg.core.paths import entities_dir, staged_dir, warehouse_path
from cachereg.core.registry import load_sources, reproducibility_class
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

    Exact sources (native, not revised) whose fetches record a ``vintage.window`` are selected by
    source time and are never flagged. Latest-only sources (``revisions: revised``) fall back to
    their earliest fetch, flagged. Snapshot sources (Author-only) never substitute later data: the
    gap is an error.
    """
    fetches = list_fetches(source)
    dates = sorted({f.fetched_at.date() for f in fetches})
    if not dates:
        raise VintageGapError(f"{source}: no fetches at all")
    src = load_sources()[source]
    if reproducibility_class(src) == "Exact":
        # Selected by source time (marts filter by revision date), so a later fetch is never "after":
        # the earliest fetch whose history reaches as_of, else the latest (marts flag the gap).
        ends = [(f, (f.manifest.get("vintage") or {}).get("window", [None, None])[1]) for f in fetches]
        if all(end for _, end in ends):
            covering = [f for f, end in ends if date.fromisoformat(end) >= as_of]
            return (covering[0] if covering else fetches[-1]).fetched_at.date(), False
    on_or_before = [d for d in dates if d <= as_of]
    if on_or_before:
        return on_or_before[-1], False
    if src.history == "snapshot":
        raise VintageGapError(
            f"{source}: no snapshot on or before {as_of} (first is {dates[0]}); snapshot sources cannot be back-filled"
        )
    return dates[0], True


def exact_vintage(source: str, as_of: date) -> dict | None:
    """The source revision an Exact source resolves for ``as_of`` (PLAN §4.4), if its stage module
    provides ``vintage_at(as_of)``; None for other classes. Independent of when it was fetched."""
    src = load_sources()[source]
    if reproducibility_class(src) != "Exact":
        return None
    hook = getattr(src.module("stage"), "vintage_at", None)
    return hook(as_of) if hook else None


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
    data = yaml.safe_load((entities_dir() / "vendors.yaml").read_text())
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


def _model_alias_frame() -> pl.DataFrame:
    """config/entities/models.yaml → one row per (model_id, source, alias); rank = position in the list.

    For sources whose list is a preference order (``litellm``), rank 1 is preferred. A source alias
    may belong to one model only, or a join through it would fan out.
    """
    f = entities_dir() / "models.yaml"
    models = (yaml.safe_load(f.read_text()) or {}).get("models") or {} if f.is_file() else {}
    rows, owner = [], {}
    for mid, m in models.items():
        for src, aliases in ((m or {}).get("aliases") or {}).items():
            for rank, alias in enumerate(aliases, start=1):
                if owner.setdefault((src, alias), mid) != mid:
                    raise ValueError(
                        f"models.yaml: {src} alias {alias!r} is listed under {owner[(src, alias)]} and {mid}"
                    )
                rows.append({"model_id": mid, "source": src, "alias": alias, "rank": rank})
    schema = {"model_id": pl.String, "source": pl.String, "alias": pl.String, "rank": pl.Int64}
    return pl.DataFrame(rows, schema=schema)


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
        model_file = staged_dir("_entities") / "model_alias.parquet"
        _model_alias_frame().write_parquet(model_file)
        con.execute("CREATE OR REPLACE TABLE dim_model_alias AS SELECT * FROM read_parquet(?)", [model_file.as_posix()])

        con.execute("SET VARIABLE as_of = ?::DATE", [as_of])
        for sid in selected:
            day, after = cutoff(sid, as_of)
            con.execute(f"SET VARIABLE {sid}_cutoff = ?::DATE", [day])
            report.vintages[sid] = {"fetch_date": str(day), "vintage_after_as_of": after}
            revision = exact_vintage(sid, as_of)
            if revision:
                report.vintages[sid]["revision"] = revision

        # Every mart's tables are dropped first, so a table from an earlier or broader build can
        # never be read as if it were current.
        for mart in marts:
            for table in reversed(mart.tables):
                con.execute(f"DROP TABLE IF EXISTS {table}")
        chosen = set(selected)
        # A mart runs when all its inputs were chosen (marts run in file order, so a later mart can
        # read an earlier one's tables). A full build refuses a partly covered mart (a source's data is
        # missing). A scoped build skips it, unless that leaves a chosen source that some mart reads
        # but no built mart uses: then the scope itself is missing a source.
        partial = []
        for mart in marts:
            if mart.inputs <= chosen:
                con.execute(mart.sql)
                report.marts_built.append(mart.name)
            else:
                report.marts_skipped.append(mart.name)
                if mart.inputs & chosen:
                    partial.append(mart)
        used = set().union(*(m.inputs for m in marts if m.name in report.marts_built))
        for mart in partial:
            if sources is None or (mart.inputs & chosen) - used:
                missing = ", ".join(sorted(mart.inputs - chosen))
                raise RuntimeError(f"mart {mart.name} needs {', '.join(sorted(mart.inputs))}; missing: {missing}")
    finally:
        con.close()
    return report
