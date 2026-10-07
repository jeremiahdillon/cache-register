"""Fetch the BTOS workbooks (public census.gov downloads, no key) and keep them as served.

Every file is downloaded and parsed in full before anything is written. `National.xlsx` (88 KB) is
stored on every fetch as the release marker; every other file only when its content differs from the
newest stored copy, so an unchanged 10 MB workbook is not stored again. Stage reads every stored
version; marts use, per file, the newest one on or before the build cutoff.
"""

from __future__ import annotations

import hashlib
import time
from datetime import date

from cachereg.core import http
from cachereg.core.store import RawFetch, list_fetches
from cachereg.sources.census_btos import files, workbook

SOURCE = "census_btos"
ADAPTER_VERSION = "1"
PAUSE = 1.0  # seconds between downloads
TIMEOUT = 180.0  # the sector × size workbook is ~10 MB


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def latest_hashes() -> dict[str, str]:
    """File key → content hash of its newest stored copy (from the manifests)."""
    out = {}
    for f in list_fetches(SOURCE):  # oldest first, so later fetches win
        for spec in files.FILES:
            digest = f.manifest.get("files", {}).get(spec.file_name)
            if digest:
                out[spec.key] = digest
    return out


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    """`full` and `today` are unused: every workbook is its breakdown's full history."""
    stored = latest_hashes()
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    hashes, unchanged, newest = {}, [], None
    for i, spec in enumerate(files.FILES):
        if i:
            time.sleep(PAUSE)
        resp = http.get(spec.url, headers={"Accept": "*/*"}, timeout=TIMEOUT)
        try:
            parsed = workbook.parse(resp.body, spec)  # validate before storing
        except ValueError as e:
            raise ValueError(f"{spec.name}: {e}") from None
        digest = sha256(resp.body)
        hashes[spec.key] = digest
        if spec.always_store or stored.get(spec.key) != digest:
            raw.add(spec.file_name, resp.body, resp.url, resp.status)
        else:
            unchanged.append(spec.key)
        if spec.key == "national":
            cycle = max(c.cycle for c in parsed.cells if not c.suppressed)
            pub = parsed.cycles[cycle].publication_date
            newest = (cycle, pub.isoformat() if pub else None)
    raw.vintage = {
        "kind": "btos_release",
        "value": newest[0] if newest else None,  # newest cycle with national AI data
        "date": newest[1] if newest else None,  # its publication date
        "files": hashes,
        "unchanged": unchanged,  # not stored again: stage finds them in an earlier fetch
    }
    return raw
