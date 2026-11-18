"""Fetch the Databricks AI Index page (weekly token and wallet shares on Unity Gateway).

One GET of the public page per run; no key, no API. The page is stored as served (raw is what the source
returned) only after it parses into every chart stage.py needs (parse.py): a page whose layout changed fails
the fetch, so nothing half-read is written. Vintage: the sha256 of the parsed records (the HTML also carries
deployment ids that change without the data changing) plus the "Updated" date and the weeks covered.
"""

from __future__ import annotations

import hashlib
import json

from cachereg.core import http
from cachereg.core.store import RawFetch
from cachereg.sources.databricks_ai_index import parse

SOURCE = "databricks_ai_index"
ADAPTER_VERSION = "1"
URL = "https://developers.databricks.com/ai-index"
FILE = "ai-index.html"


def fetch(full: bool = False, today=None) -> RawFetch:
    resp = http.get(URL, headers={"Accept": "text/html"})
    html = resp.body.decode("utf-8")
    recs = parse.records(html)  # raises on an unexpected page
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    raw.add(FILE, resp.body, resp.url, resp.status)
    canonical = json.dumps(recs, default=str, sort_keys=True).encode()
    weeks = sorted({r["week_start"] for r in recs})
    raw.vintage = {
        "kind": "content",
        "value": hashlib.sha256(canonical).hexdigest(),
        "updated": max(r["updated"] for r in recs).isoformat(),
        "window": [weeks[0].isoformat(), weeks[-1].isoformat()],
    }
    return raw
