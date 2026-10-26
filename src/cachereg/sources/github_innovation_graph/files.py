"""The Innovation Graph files this source keeps and how to read them (shared by fetch and stage)."""

from __future__ import annotations

import csv
import io

FILES = ("git_pushes.csv", "developers.csv")  # metric name = file stem = first column
AGGREGATES = {"EU"}  # economies that are sums of others (never added to a total)


def release_name(name: str, sha: str) -> str:
    return f"{name.removesuffix('.csv')}_{sha}.csv"


def parse(body: bytes, name: str) -> list[tuple[str, int, int, int]]:
    """(economy, year, quarter, value) rows; raises ValueError on any unexpected shape."""
    metric = name.removesuffix(".csv")
    reader = csv.reader(io.StringIO(body.decode("utf-8-sig")))
    header = next(reader, None)
    if header != [metric, "iso2_code", "year", "quarter"]:
        raise ValueError(f"header {header!r}, expected {metric},iso2_code,year,quarter")
    rows, seen = [], set()
    for line, r in enumerate(reader, start=2):
        if not r:
            continue
        if len(r) != 4:
            raise ValueError(f"line {line}: {len(r)} fields")
        value, economy, year, quarter = r
        try:
            v, y, q = int(value), int(year), int(quarter)
        except ValueError:
            raise ValueError(f"line {line}: value, year and quarter must be integers") from None
        if not (len(economy) == 2 and economy.isalpha() and economy.isupper()):
            raise ValueError(f"line {line}: economy {economy!r} is not a two-letter code")
        if not (1 <= q <= 4 and 2015 <= y <= 2100 and v >= 0):
            raise ValueError(f"line {line}: out-of-range year, quarter or value")
        if (economy, y, q) in seen:
            raise ValueError(f"line {line}: duplicate {economy} {y} Q{q}")
        seen.add((economy, y, q))
        rows.append((economy, y, q, v))
    if not rows:
        raise ValueError("no rows")
    return rows
