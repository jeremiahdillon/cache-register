from __future__ import annotations

import compileall
from datetime import date
from pathlib import Path

import polars as pl

from cachereg.story.hashing import data_hash

ROOT = Path(__file__).resolve().parents[1]


def frames():
    return {
        "b": pl.DataFrame({"week": [date(2026, 1, 5), date(2026, 1, 12)], "share": [0.1, 0.2], "n": [1, 2]}),
        "a": pl.DataFrame({"x": ["p", "q"]}),
    }


def test_hash_ignores_row_and_column_order_and_float_width():
    f = frames()
    shuffled = {
        "a": f["a"].reverse(),
        "b": f["b"]
        .reverse()
        .select("n", "share", "week")
        .with_columns(pl.col("share").cast(pl.Float32).cast(pl.Float64)),
    }
    assert data_hash(f) == data_hash(shuffled)


def test_hash_changes_when_values_change():
    f = frames()
    changed = dict(f, b=f["b"].with_columns(pl.Series("share", [0.1, 0.25])))
    assert data_hash(f) != data_hash(changed)


def test_explorations_and_receipts_compile():
    for tree in ("explore", "receipts"):
        assert compileall.compile_dir(ROOT / tree, quiet=1, legacy=True) or not any((ROOT / tree).rglob("*.py"))
