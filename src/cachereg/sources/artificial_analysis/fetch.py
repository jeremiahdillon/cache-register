"""Snapshot Artificial Analysis's LLM data (intelligence index, per-eval scores, price, speed)."""

from __future__ import annotations

from cachereg.core import http
from cachereg.core.settings import get_secret
from cachereg.core.store import RawFetch

SOURCE = "artificial_analysis"
ADAPTER_VERSION = "1"
URL = "https://artificialanalysis.ai/api/v2/data/llms/models"


def fetch(full: bool = False, today=None) -> RawFetch:
    resp = http.get(URL, None, {"x-api-key": get_secret("ARTIFICIAL_ANALYSIS_API_KEY")})
    data = resp.json().get("data")
    if not isinstance(data, list) or not data:
        raise ValueError("unexpected response shape from /api/v2/data/llms/models")
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    raw.add("models.json", resp.body, resp.url, resp.status)
    raw.vintage = {"kind": "snapshot", "value": raw.fetched_at.date().isoformat()}
    return raw
