"""Stage LiteLLM price history: the commit of each day, and price intervals per key."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, date, datetime

import polars as pl

from cachereg.core.store import list_fetches
from cachereg.sources.litellm_prices.history import FLOOR, day_end_commits, parse_first_parent

SOURCE = "litellm_prices"
PRICE_FIELDS = {
    "input_usd_per_token": "input_cost_per_token",
    "output_usd_per_token": "output_cost_per_token",
    "cache_read_usd_per_token": "cache_read_input_token_cost",
}
DAYS_SCHEMA = {"date": pl.Date, "commit_sha": pl.String, "committed_at": pl.Datetime("us", "UTC")}
PRICES_SCHEMA = {
    "key": pl.String,
    "litellm_provider": pl.String,
    "mode": pl.String,
    "input_usd_per_token": pl.Float64,
    "output_usd_per_token": pl.Float64,
    "cache_read_usd_per_token": pl.Float64,
    "valid_from": pl.Date,
    "valid_to": pl.Date,  # exclusive; null = still listed on the last staged day
    "commit_sha": pl.String,
}


def _num(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _entries(body: bytes) -> dict[str, tuple]:
    data = json.loads(gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body)
    out = {}
    for key, m in data.items():
        if key == "sample_spec" or not isinstance(m, dict):
            continue
        provider, mode = m.get("litellm_provider"), m.get("mode")
        out[key] = (
            str(provider) if provider is not None else None,
            str(mode) if mode is not None else None,
            *(_num(m.get(f)) for f in PRICE_FIELDS.values()),
        )
    return out


def history_days() -> dict[date, tuple[str, int]]:
    """Every staged day → (commit sha, committer epoch), from the newest fetch's listing."""
    fetches = list_fetches(SOURCE)
    if not fetches:
        return {}
    ends = [(f.manifest.get("vintage") or {}).get("window", [None, None])[1] for f in fetches]
    end = max(date.fromisoformat(e) for e in ends if e)
    first_parent = parse_first_parent(fetches[-1].read("first_parent.tsv").decode())
    return day_end_commits(first_parent, FLOOR, end) if end >= FLOOR else {}


def vintage_at(as_of: date) -> dict | None:
    """The source revision used for ``as_of`` (PLAN §4.4): the commit of min(as_of, last staged day)."""
    days = history_days()
    if not days:
        return None
    day = min(as_of, max(days))
    if day < FLOOR:
        return None
    sha, _ = days[day]
    return {"kind": "git_commit", "value": sha, "date": day.isoformat()}


def stage() -> dict[str, pl.DataFrame]:
    files = {}
    for f in list_fetches(SOURCE):
        for name in f.manifest["files"]:
            if name.startswith("prices_"):
                files[name.removeprefix("prices_").split(".")[0]] = (f, name)
    days = history_days()
    missing = sorted(d for d, (sha, _) in days.items() if sha not in files)
    if missing:
        raise ValueError(f"{SOURCE}: no stored price file for {missing[0]} (and {len(missing) - 1} more); re-fetch")

    day_rows, rows, open_ = [], [], {}  # open_: key -> (entry tuple, valid_from, sha)
    prev_sha, state = None, {}
    for d in sorted(days):
        sha, ct = days[d]
        day_rows.append({"date": d, "commit_sha": sha, "committed_at": datetime.fromtimestamp(ct, UTC)})
        if sha == prev_sha:
            continue
        f, name = files[sha]
        state, prev_sha = _entries(f.read(name)), sha
        for key in [k for k in open_ if k not in state]:  # removed from the file
            entry, start, from_sha = open_.pop(key)
            rows.append((key, entry, start, d, from_sha))
        for key, entry in state.items():
            cur = open_.get(key)
            if cur is not None and cur[0] == entry:
                continue
            if cur is not None:
                rows.append((key, cur[0], cur[1], d, cur[2]))
            open_[key] = (entry, d, sha)
    rows += [(key, entry, start, None, sha) for key, (entry, start, sha) in open_.items()]

    prices = pl.DataFrame(
        [
            dict(
                zip(PRICES_SCHEMA, (key, *entry, start, end, sha), strict=True),
            )
            for key, entry, start, end, sha in rows
        ],
        schema=PRICES_SCHEMA,
    ).sort("key", "valid_from")
    return {"days": pl.DataFrame(day_rows, schema=DAYS_SCHEMA), "prices": prices}
