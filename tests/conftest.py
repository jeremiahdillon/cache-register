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


# The sources the synthetic fixture fetches. A full build would also expect Epoch (040 reads LiteLLM
# and Epoch), so tests that build "everything" name these instead.
SLICE = ["openrouter_rankings", "openrouter_models", "litellm_prices"]

LITELLM_MID = date(2026, 7, 15)  # synthetic LiteLLM commit that changes the price file mid-window

# model_id -> (openrouter permaslugs, litellm keys in preference order)
SYNTHETIC_MODELS = {
    "anthropic/claude-sonnet-9": (["anthropic/claude-sonnet-9-20260101"], ["openrouter/anthropic/claude-sonnet-9"]),
    "openai/gpt-9": (["openai/gpt-9-20260101"], ["openrouter/openai/gpt-9", "gpt-9-20260101"]),
    "moonshotai/kimi-9": (["moonshotai/kimi-9"], ["openrouter/moonshotai/kimi-9"]),
    "google/gemini-9-pro": (["google/gemini-9-pro"], ["gemini/gemini-9-pro"]),
}


def synthetic_litellm_files() -> dict[str, dict]:
    """Two synthetic LiteLLM states: before and from LITELLM_MID (keys -> entries)."""

    def entry(i, o):
        return {"input_cost_per_token": i, "output_cost_per_token": o, "litellm_provider": "x", "mode": "chat"}

    early = {
        "sample_spec": {"input_cost_per_token": 0},
        "openrouter/anthropic/claude-sonnet-9": entry(3e-6, 15e-6),
        "gpt-9-20260101": entry(1.25e-6, 10e-6),
        "gemini/gemini-9-pro": entry(1.25e-6, 10e-6),
    }
    late = dict(early)
    del late["gemini/gemini-9-pro"]  # removed upstream: later days use its last price, flagged
    late["openrouter/openai/gpt-9"] = entry(1e-6, 8e-6)  # preferred key appears mid-window
    late["openrouter/moonshotai/kimi-9"] = entry(0.6e-6, 2.5e-6)  # earlier days: first later price, flagged
    return {"c_early": early, "c_mid": late}


def write_synthetic_litellm(fetched: datetime, end: date) -> None:
    files = synthetic_litellm_files()
    t_early = int(datetime(2024, 12, 31, 12, tzinfo=UTC).timestamp())
    t_mid = int(datetime.combine(LITELLM_MID, datetime.min.time(), tzinfo=UTC).timestamp()) + 3600
    r = RawFetch("litellm_prices", "1", fetched_at=fetched)
    r.add("first_parent.tsv", f"c_mid\t{t_mid}\nc_early\t{t_early}\n".encode(), "https://example.test/x.git", 200)
    for sha, body in files.items():
        r.add(f"prices_{sha}.json", json.dumps(body).encode(), "https://example.test", 200)
    r.vintage = {"kind": "git_commit", "value": "c_mid", "window": ["2025-01-01", end.isoformat()]}
    r.write()


@pytest.fixture
def synthetic_entities(tmp_path, monkeypatch):
    """Synthetic config/entities: the real vendors.yaml and sectors.yaml plus a models.yaml for the synthetic models."""
    import shutil

    import yaml

    from cachereg.core import paths

    d = tmp_path / "entities"
    d.mkdir()
    shutil.copy(paths.entities_dir() / "vendors.yaml", d / "vendors.yaml")
    shutil.copy(paths.entities_dir() / "sectors.yaml", d / "sectors.yaml")
    models = {m: {"aliases": {"openrouter": o, "litellm": lk}} for m, (o, lk) in SYNTHETIC_MODELS.items()}
    (d / "models.yaml").write_text(yaml.safe_dump({"models": models}))
    monkeypatch.setattr(paths, "ENTITIES_DIR", d)
    return d


@pytest.fixture
def synthetic_raw(data_env, synthetic_entities):
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
    write_synthetic_litellm(fetched, date(2026, 8, 30))
    return data_env
