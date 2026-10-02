"""Shared fixtures. All data here is synthetic — never recorded API responses (licensing, PLAN §4.2)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from cachereg.core.store import RawFetch

VENDORS = {  # permaslug -> (prompt $/token, completion $/token); None = not in the price catalog
    "anthropic/claude-sonnet-9-20260101": (3e-6, 15e-6),
    "openai/gpt-9-20260101": (1.25e-6, 10e-6),
    "moonshotai/kimi-9": (0.6e-6, 2.5e-6),
    "google/gemini-9-pro": (1.25e-6, 10e-6),
    "x-ai/retired-model": None,
    "openai/gpt-9-mini:free": (0.0, 0.0),
}


@pytest.fixture
def data_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHEREG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CACHEREG_OUTPUTS_DIR", str(tmp_path / "outputs"))
    return tmp_path


def synthetic_rankings(start: date, days: int) -> dict:
    rows = []
    for d in range(days):
        day = start + timedelta(days=d)
        shift = d / max(days - 1, 1)  # Anthropic share shrinks over the window
        tokens = {
            "anthropic/claude-sonnet-9-20260101": int(5e9 * (1 - 0.6 * shift)),
            "openai/gpt-9-20260101": int(4e9 * (1 + 0.5 * shift)),
            "moonshotai/kimi-9": int(2e9 * (1 + 2 * shift)),
            "google/gemini-9-pro": int(1e9),
            "x-ai/retired-model": int(3e8),
            "openai/gpt-9-mini:free": int(6e8),
        }
        for slug, t in tokens.items():
            rows.append({"date": day.isoformat(), "model_permaslug": slug, "total_tokens": str(t)})
        rows.append({"date": day.isoformat(), "model_permaslug": "other", "total_tokens": str(int(7e8))})
    end = start + timedelta(days=days - 1)
    return {
        "data": rows,
        "meta": {
            "as_of": f"{end + timedelta(days=1)}T02:00:00Z",
            "start_date": str(start),
            "end_date": str(end),
            "version": "v1",
        },
    }


def synthetic_models() -> dict:
    data = []
    for slug, price in VENDORS.items():
        if price is None or slug.endswith(":free"):
            continue
        data.append(
            {
                "id": slug.rsplit("-2026", 1)[0],
                "canonical_slug": slug,
                "name": slug,
                "pricing": {"prompt": str(price[0]), "completion": str(price[1])},
            }
        )
    return {"data": data}


@pytest.fixture
def synthetic_raw(data_env):
    """Write one rankings fetch (2026-06-01..2026-08-30, 13 full weeks) and one price snapshot."""
    fetched = datetime(2026, 8, 31, 12, tzinfo=UTC)
    r = RawFetch("openrouter_rankings", "1", fetched_at=fetched)
    r.add("rankings.json", json.dumps(synthetic_rankings(date(2026, 6, 1), 91)).encode(), "https://example.test", 200)
    r.vintage = {"kind": "api_as_of", "value": "2026-08-31T02:00:00Z"}
    r.write()
    m = RawFetch("openrouter_models", "1", fetched_at=fetched)
    m.add("models.json", json.dumps(synthetic_models()).encode(), "https://example.test", 200)
    m.vintage = {"kind": "snapshot", "value": "2026-08-31"}
    m.write()
    return data_env
