"""Canonical hashes used to decide "same result?" without comparing image bytes.

* ``data_hash``: the Story frames in a canonical form — frames by name, columns by name, rows sorted
  by all columns; dates as ISO strings, floats to 7 significant digits (float32-safe; first to 12, so summation-order
  noise cannot flip a value that sits on a 7-digit rounding boundary), nulls as empty — serialised
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
        # 12 digits first: 72.43627499999999 and 72.43627500000001 (one mean, summed in two orders) are one value
        return format(float(format(v, ".12g")), ".7g")
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
    "config/sources.yaml",  # licence rights and attributions change what is written and the footer
    "assets/fonts",
    "assets/templates",
    "src/cachereg/render.py",
    "src/cachereg/viz",
    "src/cachereg/story",
)


UNHASHED_KEYS = ("as_of:", "blurb:")  # as_of changes the data, not the look (tracked separately); blurb is site text


def _look(text: str) -> str:
    """A receipt.yaml / explore.yaml without its UNHASHED_KEYS (a key's indented continuation lines included)."""
    kept, skipping = [], False
    for line in text.splitlines():
        if line.startswith(UNHASHED_KEYS):
            skipping = True
        elif not (skipping and line[:1] in (" ", "\t")):
            skipping = False
            kept.append(line)
    return "\n".join(kept)


def inputs_hash(folder: Path, root: Path = REPO_ROOT) -> str:
    files: list[Path] = [folder / n for n in ("analysis.py", "charts.py", "receipt.yaml", "explore.yaml")]
    for rel in SHARED_RENDER_INPUTS:
        p = root / rel
        files += sorted(p.rglob("*")) if p.is_dir() else [p]
    h = hashlib.sha256()
    for f in sorted({f for f in files if f.is_file() and "__pycache__" not in f.parts}):
        if f.name == "receipt.yaml" or f.name == "explore.yaml":
            data = _look(f.read_text()).encode()
        else:
            data = f.read_bytes()
        try:
            label = f.resolve().relative_to(root).as_posix()
        except ValueError:
            label = f.name
        h.update(label.encode() + b"\0" + hashlib.sha256(data).digest())
    return h.hexdigest()
