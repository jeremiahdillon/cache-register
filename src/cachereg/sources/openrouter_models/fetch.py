"""Snapshot OpenRouter's public model catalog (prices)."""

from __future__ import annotations

from cachereg.core import http
from cachereg.core.store import RawFetch

SOURCE = "openrouter_models"
ADAPTER_VERSION = "1"
URL = "https://openrouter.ai/api/v1/models"


def fetch(full: bool = False, today=None) -> RawFetch:
    resp = http.get(URL)
    if not isinstance(resp.json().get("data"), list):
        raise ValueError("unexpected response shape from /api/v1/models")
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    raw.add("models.json", resp.body, resp.url, resp.status)
    raw.vintage = {"kind": "snapshot", "value": raw.fetched_at.date().isoformat()}
    return raw
