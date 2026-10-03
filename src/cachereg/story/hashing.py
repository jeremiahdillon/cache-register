"""Canonical hashes used to decide "same result?" without comparing image bytes.

* ``data_hash``: the Story frames in a canonical form — frames by name, columns by name, rows sorted
  by all columns; dates as ISO strings, floats to 7 significant digits (float32-safe), nulls as empty — serialised
  as CSV. Identical data hashes identically regardless of row order, column order or dtype width.
* ``inputs_hash``: the bytes of every file that can change how a receipt's visuals look.
"""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime
from pathlib import Path

import polars as pl

from cachereg.core.paths import REPO_ROOT


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return format(v, ".7g")
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def canonical_csv(df: pl.DataFrame) -> str:
    cols = sorted(df.columns)
    rows = sorted(tuple(_cell(v) for v in row) for row in df.select(cols).iter_rows())
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(cols)
    w.writerows(rows)
    return buf.getvalue()


def data_hash(frames: dict[str, pl.DataFrame]) -> str:
    h = hashlib.sha256()
    for name in sorted(frames):
        h.update(f"{name}\n{canonical_csv(frames[name])}\n".encode())
    return h.hexdigest()


SHARED_RENDER_INPUTS = (
    "config/brand/brand.yaml",
    "assets/fonts",
    "assets/templates",
    "src/cachereg/render.py",
    "src/cachereg/viz",
    "src/cachereg/story",
)


def inputs_hash(folder: Path, root: Path = REPO_ROOT) -> str:
    files: list[Path] = [folder / n for n in ("analysis.py", "charts.py", "receipt.yaml", "explore.yaml")]
    for rel in SHARED_RENDER_INPUTS:
        p = root / rel
        files += sorted(p.rglob("*")) if p.is_dir() else [p]
    h = hashlib.sha256()
    for f in sorted({f for f in files if f.is_file() and "__pycache__" not in f.parts}):
        if f.name == "receipt.yaml" or f.name == "explore.yaml":
            # as_of is tracked separately (it changes the data, not the look)
            body = "\n".join(line for line in f.read_text().splitlines() if not line.startswith("as_of:"))
            data = body.encode()
        else:
            data = f.read_bytes()
        try:
            label = f.resolve().relative_to(root).as_posix()
        except ValueError:
            label = f.name
        h.update(label.encode() + b"\0" + hashlib.sha256(data).digest())
    return h.hexdigest()
