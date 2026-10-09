"""Fetch the curated disclosures dataset: validate the committed file and store a copy in raw.

No network: the dataset is ours (`config/curated/disclosures.csv`, CC BY 4.0) with its vocabulary
(`metrics.yaml`). A file that does not validate, or that edits or drops a row of the newest stored
copy, is never stored. When both files are byte-identical to the newest stored copy, nothing is
written (`fetch` returns None). Rows are only appended, so the newest copy holds every earlier one;
as-of is by each row's `recorded_on` (Exact).
"""

from __future__ import annotations

import hashlib

from cachereg.core.store import RawFetch, list_fetches
from cachereg.sources.curated_disclosures import dataset

SOURCE = "curated_disclosures"
ADAPTER_VERSION = "1"


def fetch(full: bool = False) -> RawFetch | None:
    files = {name: (dataset.CURATED_DIR / name).read_bytes() for name in (dataset.FILE, dataset.METRICS)}
    rows = dataset.validate(files[dataset.FILE], dataset.load_metrics(dataset.CURATED_DIR / dataset.METRICS))
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
