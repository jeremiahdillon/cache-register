"""Fetch OpenRouter's session-cost dataset: the current weekly snapshot (no date parameters).

One request per turn range, so each filtered list stays far below the page size and the
unfiltered sort's cost ties at page boundaries never matter; a full page is still followed with
`offset`. Every response must describe the same snapshot (`window_end_date`, `window_days`);
if the snapshot changes mid-fetch the whole fetch is retried once.
"""

from __future__ import annotations

import json
import math

from cachereg.core.store import RawFetch
from cachereg.sources._openrouter_datasets import Client

SOURCE = "openrouter_session_cost"
ADAPTER_VERSION = "1"
ENDPOINT = "session-cost"
TURN_RANGES = ("1-turn", "2-9-turns", "10-49-turns", "50-plus-turns")
LIMIT = 500
MAX_OFFSET = 5000  # API maximum


class SnapshotChanged(ValueError):
    """Responses within one fetch describe different snapshots."""


def file_name(turn_range: str, offset: int) -> str:
    return f"session_cost_{turn_range}_o{offset}.json"


def check_rows(rows: list, turn_range: str, seen: set) -> None:
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError("session-cost: a row is not an object")
        for k in ("app_slug", "app_name", "model_permaslug"):
            if not isinstance(r.get(k), str) or not r[k]:
                raise ValueError(f"session-cost: row without {k}")
        if r.get("turn_range") != turn_range:
            raise ValueError(f"session-cost: row turn_range {r.get('turn_range')!r} in the {turn_range} list")
        cost = r.get("median_session_cost_usd")
        if isinstance(cost, bool) or not isinstance(cost, int | float) or not math.isfinite(cost) or cost < 0:
            raise ValueError(f"session-cost: bad median_session_cost_usd {cost!r}")
        key = (r["app_slug"], r["model_permaslug"], turn_range)
        if key in seen:
            raise ValueError(f"session-cost: duplicate cell {key}")
        seen.add(key)


def _fetch_once(client: Client) -> RawFetch:
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    window, as_of, seen = None, [], set()
    for turn_range in TURN_RANGES:
        offset = 0
        while True:
            params = {"turn_range": turn_range, "limit": str(LIMIT), "offset": str(offset)}
            resp, body = client.get(ENDPOINT, params)
            meta = body["meta"]
            this = (meta.get("window_end_date"), meta.get("window_days"))
            if this[0] is None or this[1] is None:
                raise ValueError("session-cost: no snapshot published (window is null)")
            if window is None:
                window = this
            elif this != window:
                raise SnapshotChanged(f"session-cost: snapshot changed mid-fetch ({window} → {this})")
            check_rows(body["data"], turn_range, seen)
            as_of.append(meta.get("as_of"))
            raw.add(file_name(turn_range, offset), json.dumps(body).encode(), resp.url, resp.status)
            if len(body["data"]) < LIMIT:
                break
            offset += LIMIT
            if offset > MAX_OFFSET:
                raise ValueError(f"session-cost: {turn_range} has more than {MAX_OFFSET + LIMIT} cells")
    raw.vintage = {
        "kind": "snapshot",
        "value": window[0],
        "window_days": window[1],
        "as_of": max((a for a in as_of if a), default=None),
    }
    return raw


def fetch(full: bool = False, today=None) -> RawFetch:
    """`full` and `today` are unused: only the current snapshot can be fetched (Author-only)."""
    client = Client()
    try:
        return _fetch_once(client)
    except SnapshotChanged:
        return _fetch_once(client)  # published between two requests: once more, then fail
