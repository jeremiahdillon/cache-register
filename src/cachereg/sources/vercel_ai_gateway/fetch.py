"""Fetch Vercel AI Gateway leaderboard data: daily shares by lab and by model (text modality).

Public export endpoint, no key, CC BY 4.0. Shares only, never volumes. Labs are complete (each
day × metric sums to 100); models are the top few of the *requested window* plus `Other`, so they
are fetched one calendar month per request and a month's list is "the top models of that month".
The first run (or `--full`) asks for everything from 2025-10-01 (the earliest day the export
serves); later runs re-fetch the trailing 35 days of labs and the current and previous month of
models, so revisions are captured as new vintages. Days end yesterday (UTC): today's rollup is
not complete. A body that does not validate fails the whole fetch (nothing written).
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from cachereg.core import http
from cachereg.core.store import RawFetch, list_fetches

SOURCE = "vercel_ai_gateway"
ADAPTER_VERSION = "1"
URL = "https://vercel.com/api/ai/leaderboard-export"
FLOOR = date(2025, 10, 1)  # "the point from which the daily rollups are complete"
REFRESH_DAYS = 35
MODALITY = "text"
LICENSE = "CC-BY-4.0"
METRICS = {"requests", "tokens", "spend"}
GROUPS = {"labs": "lab", "models": "model"}
SUM_TOLERANCE = 0.05  # labs: shares per day × metric sum to 100 within this (samples: ±0.0005)


def month_windows(start: date, end: date) -> list[tuple[date, date]]:
    """Calendar months overlapping start..end, each clipped to that range."""
    out, first = [], start.replace(day=1)
    while first <= end:
        nxt = (first + timedelta(days=32)).replace(day=1)
        out.append((max(first, start), min(nxt - timedelta(days=1), end)))
        first = nxt
    return out


def plan(today: date, full: bool) -> tuple[tuple[date, date], list[tuple[date, date]]]:
    """(labs window, model month windows) for a run on `today`."""
    end = today - timedelta(days=1)
    if end < FLOOR:
        raise ValueError(f"vercel: no complete day between {FLOOR} and {today}")
    if full or not list_fetches(SOURCE):
        return (FLOOR, end), month_windows(FLOOR, end)
    labs_from = max(FLOOR, end - timedelta(days=REFRESH_DAYS - 1))
    prev_month = (end.replace(day=1) - timedelta(days=1)).replace(day=1)
    return (labs_from, end), month_windows(max(FLOOR, prev_month), end)


def check_body(body, dataset: str, start: date, end: date) -> None:
    """Refuse a body that is not what was asked for, or whose shares are not shares."""
    where = f"vercel {dataset} {start}..{end}"
    if not isinstance(body, dict) or not isinstance(body.get("rows"), list):
        raise ValueError(f"{where}: unexpected response shape")
    if body.get("license") != LICENSE:
        raise ValueError(f"{where}: licence is {body.get('license')!r}, not {LICENSE}; check the terms before fetching")
    asked = {"dataset": dataset, "modality": MODALITY, "from": start.isoformat(), "to": end.isoformat()}
    answered = {k: body.get(k) for k in asked}
    if answered != asked:
        raise ValueError(f"{where}: answered for {answered}")
    if not body["rows"]:
        raise ValueError(f"{where}: no rows")
    sums: dict[tuple[str, str], float] = defaultdict(float)
    for r in body["rows"]:
        if not isinstance(r, dict):
            raise ValueError(f"{where}: a row is not an object")
        try:
            day = date.fromisoformat(r["date"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{where}: bad date {r.get('date')!r}") from None
        if not start <= day <= end:
            raise ValueError(f"{where}: date {day} outside the requested window")
        if r.get("metric") not in METRICS:
            raise ValueError(f"{where}: unknown metric {r.get('metric')!r}")
        if r.get("group") != GROUPS[dataset]:
            raise ValueError(f"{where}: unknown group {r.get('group')!r}")
        if r.get("modality") != MODALITY:
            raise ValueError(f"{where}: modality {r.get('modality')!r}")
        if not isinstance(r.get("name"), str) or not r["name"].strip():
            raise ValueError(f"{where}: a row has no name")
        share = r.get("share_percent")
        if isinstance(share, bool) or not isinstance(share, int | float) or not math.isfinite(share):
            raise ValueError(f"{where}: share {share!r} is not a number")
        if not 0 <= share <= 100:
            raise ValueError(f"{where}: share {share} outside 0–100")
        sums[(r["date"], r["metric"])] += share
    if dataset == "labs":  # labs are complete; models are a top-few list (no `Other` before June 2026)
        off = [(k, round(v, 4)) for k, v in sorted(sums.items()) if abs(v - 100) > SUM_TOLERANCE]
        if off:
            raise ValueError(f"{where}: lab shares do not sum to 100 on {off[:3]}")


def file_name(dataset: str, start: date, end: date) -> str:
    return f"{dataset}_{start:%Y%m%d}_{end:%Y%m%d}.json"


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    today = today or datetime.now(UTC).date()
    labs, months = plan(today, full)
    raw, earliest = RawFetch(SOURCE, ADAPTER_VERSION), set()
    for dataset, windows in (("labs", [labs]), ("models", months)):
        for start, end in windows:
            params = {"dataset": dataset, "modality": MODALITY, "format": "json"}
            resp = http.get(URL, params | {"from": start.isoformat(), "to": end.isoformat()})
            body = resp.json()
            check_body(body, dataset, start, end)
            earliest.add(body.get("earliest_available_date"))
            raw.add(file_name(dataset, start, end), resp.body, resp.url, resp.status)
    digest = hashlib.sha256()
    for name in sorted(raw.files):
        digest.update(name.encode() + b"\0" + raw.files[name])
    raw.vintage = {
        "kind": "content",
        "value": digest.hexdigest(),
        "window": [min(labs[0], months[0][0]).isoformat(), labs[1].isoformat()],
        "earliest_available_date": max((e for e in earliest if isinstance(e, str)), default=None),
    }
    return raw
