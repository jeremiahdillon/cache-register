"""Fetch OpenRouter's rankings-daily dataset into the raw store."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from cachereg.core import http
from cachereg.core.settings import get_secret
from cachereg.core.store import RawFetch, list_fetches

SOURCE = "openrouter_rankings"
ADAPTER_VERSION = "1"
URL = "https://openrouter.ai/api/v1/datasets/rankings-daily"
FLOOR = date(2025, 1, 1)
REFRESH_DAYS = 35


def month_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Inclusive [start, end] split at calendar-month boundaries."""
    windows, cur = [], start
    while cur <= end:
        nxt = (cur.replace(day=1) + timedelta(days=32)).replace(day=1)
        windows.append((cur, min(end, nxt - timedelta(days=1))))
        cur = nxt
    return windows


def plan_window(today: date, full: bool) -> tuple[date, date]:
    end = today - timedelta(days=1)  # most recent completed UTC day
    start = FLOOR if full or not list_fetches(SOURCE) else max(FLOOR, end - timedelta(days=REFRESH_DAYS - 1))
    return start, end


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    today = today or datetime.now(UTC).date()
    start, end = plan_window(today, full)
    headers = {"Authorization": f"Bearer {get_secret('OPENROUTER_API_KEY')}"}
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    as_of = []
    for ws, we in month_windows(start, end):
        params = {"start_date": ws.isoformat(), "end_date": we.isoformat(), "period": "day"}
        resp = http.get(URL, params, headers)
        body = resp.json()
        if not isinstance(body.get("data"), list):
            raise ValueError(f"unexpected response shape for {ws}..{we}")
        as_of.append(body.get("meta", {}).get("as_of"))
        raw.add(f"rankings_{ws:%Y%m%d}_{we:%Y%m%d}.json", json.dumps(body).encode(), resp.url, resp.status)
    raw.vintage = {
        "kind": "api_as_of",
        "value": max(a for a in as_of if a) if any(as_of) else None,
        "window": [start.isoformat(), end.isoformat()],
    }
    return raw
