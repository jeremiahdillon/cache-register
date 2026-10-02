"""Read-only access to the DuckDB warehouse for analyses (marts only — PLAN §4.1)."""

from __future__ import annotations

import duckdb
import polars as pl

from cachereg.core.paths import warehouse_path


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(warehouse_path()), read_only=True)


def query(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pl.DataFrame:
    """Run SQL and return a polars DataFrame (without requiring pyarrow)."""
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return pl.DataFrame(rel.fetchall(), schema=cols, orient="row", infer_schema_length=None)
