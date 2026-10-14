"""Fetch the curated asset values: validate the committed files and store a copy when they changed."""

from __future__ import annotations

import hashlib

from cachereg.core.store import RawFetch, list_fetches
from cachereg.sources.curated_asset_values import dataset

SOURCE = "curated_asset_values"
ADAPTER_VERSION = "1"


def fetch(full: bool = False) -> RawFetch | None:
    files = {name: (dataset.CURATED_DIR / name).read_bytes() for name in (dataset.FILE, dataset.VOCAB)}
    rows = dataset.validate(files[dataset.FILE], dataset.load_vocab(dataset.CURATED_DIR / dataset.VOCAB))
    hashes = {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}
    stored = list_fetches(SOURCE)
    if stored and stored[-1].manifest["files"] == hashes and not full:
        return None
    if stored:  # never store a copy that edits or drops a row of the newest one (stage would refuse it)
        dataset.check_append_only(stored[-1].read(dataset.FILE), files[dataset.FILE])
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    for name, body in files.items():
        raw.add(name, body, f"config/curated/{name}", None)
    recorded = sorted(r["recorded_on"] for r in rows)
    raw.vintage = {
        "kind": "content",
        "value": hashes[dataset.FILE],
        "window": [recorded[0], recorded[-1]] if recorded else [None, None],
        "rows": len(rows),
    }
    return raw
