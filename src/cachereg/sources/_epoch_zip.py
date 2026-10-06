"""Shared helpers for the two Epoch AI sources (`epoch_benchmarks`, `epoch_models`).

Not a source itself (no registry entry). Each Epoch dataset is one zip, revised in place with no
version history (Latest-only, PLAN §4.4): every fetch stores the zip as served, and its vintage is
the content hash. Staging parses each distinct content hash once.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import zipfile
from collections.abc import Iterable
from datetime import date

import polars as pl

from cachereg.core import http
from cachereg.core.store import RawFetch, StoredFetch, list_fetches

MAX_UNCOMPRESSED = 256 * 1024 * 1024  # zip-bomb guard: total declared size of all members

VINTAGES_SCHEMA = {
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
    "fetch_date": pl.Date,
    "content_sha256": pl.String,
    "vintage_id": pl.String,  # the earliest fetch with this content; its rows are the ones staged
}


def open_zip(body: bytes, required: Iterable[str]) -> zipfile.ZipFile:
    """Open and validate an Epoch zip in memory (nothing is extracted to disk)."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile as e:
        raise ValueError(f"not a zip file: {e}") from None
    infos = zf.infolist()
    for info in infos:
        name = info.filename
        if name.startswith(("/", "\\")) or ".." in re.split(r"[/\\]", name):
            raise ValueError(f"unsafe member name in zip: {name!r}")
    if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
        raise ValueError("zip expands beyond the size cap")
    names = {i.filename for i in infos}
    missing = sorted(set(required) - names)
    if missing:
        raise ValueError(f"zip is missing {', '.join(missing)}")
    return zf


def fetch_zip(source: str, adapter_version: str, url: str, filename: str, required: Iterable[str]) -> RawFetch:
    resp = http.get(url, headers={"Accept": "application/zip"})
    open_zip(resp.body, required)  # validate before storing
    raw = RawFetch(source, adapter_version)
    raw.add(filename, resp.body, resp.url, resp.status)
    raw.vintage = {"kind": "content_sha256", "value": hashlib.sha256(resp.body).hexdigest()}
    return raw


def distinct_vintages(
    source: str, filename: str, required: Iterable[str]
) -> tuple[pl.DataFrame, list[tuple[str, zipfile.ZipFile]]]:
    """The `vintages` table (one row per fetch) and one opened zip per distinct content hash."""
    rows, zips, first = [], [], {}
    required = tuple(required)
    fetches: list[StoredFetch] = list_fetches(source)
    for f in fetches:
        if filename not in f.manifest["files"]:
            raise ValueError(f"{source}: fetch {f.manifest['fetch_id']} has no {filename}")
        digest = f.manifest["files"][filename]
        if digest not in first:
            body = f.read(filename)
            if hashlib.sha256(body).hexdigest() != digest:
                raise ValueError(f"{source}: {filename} in fetch {f.manifest['fetch_id']} does not match its manifest")
            first[digest] = f.manifest["fetch_id"]
            zips.append((first[digest], open_zip(body, required)))
        rows.append(
            {
                "fetch_id": f.manifest["fetch_id"],
                "fetched_at": f.fetched_at,
                "fetch_date": f.fetched_at.date(),
                "content_sha256": digest,
                "vintage_id": first[digest],
            }
        )
    return pl.DataFrame(rows, schema=VINTAGES_SCHEMA), zips


def read_csv(zf: zipfile.ZipFile, member: str) -> tuple[list[str], list[dict[str, str]]]:
    """Header and rows of a CSV member. Rows whose cells are all empty are dropped (blank lines)."""
    with zf.open(member) as fh:
        reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", newline=""))
        header = list(reader.fieldnames or [])
        rows = [r for r in reader if any((v or "").strip() for k, v in r.items() if k is not None)]
    return header, rows


def text(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


class Counter:
    """Counts cells that are present but not parseable (reported via `_rejected_rows`)."""

    def __init__(self) -> None:
        self.n = 0

    def num(self, v: str | None) -> float | None:
        s = (v or "").strip()
        if not s:
            return None
        try:
            value = float(s.replace(",", ""))
        except ValueError:
            value = math.nan
        if not math.isfinite(value):  # "n/a", but also "NaN" and "inf", which float() accepts
            self.n += 1
            return None
        return value

    def day(self, v: str | None) -> tuple[date | None, str | None]:
        """ISO date, or a year-month / year (first day of the period), with its precision."""
        s = (v or "").strip()
        if not s:
            return None, None
        for pattern, precision in ((r"\d{4}-\d{2}-\d{2}", "day"), (r"\d{4}-\d{2}", "month"), (r"\d{4}", "year")):
            if re.fullmatch(pattern, s):
                parts = [int(p) for p in s.split("-")] + [1, 1]
                try:
                    return date(parts[0], parts[1], parts[2]), precision
                except ValueError:
                    break
        self.n += 1
        return None, None

    def flag(self, v: str | None) -> bool | None:
        s = (v or "").strip().lower()
        if not s:
            return None
        if s in ("true", "yes", "1"):
            return True
        if s in ("false", "no", "0"):
            return False
        self.n += 1
        return None

    def frame(self) -> pl.DataFrame:
        return pl.DataFrame({"rejected": [self.n]})
