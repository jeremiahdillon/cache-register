"""Fetch OpenRouter's app-rankings dataset: weekly top-200 apps, plus current category tags.

The API returns one total per app for the requested window (no per-day rows), at most ranks
1–200 (`limit` ≤ 100, `offset` ≤ 100). Windows are ISO weeks, Monday–Sunday, from 2025-01-06 to
the last complete week. The first run back-fills every week; later runs re-fetch the trailing
weeks so revisions (late events, apps hidden or merged) are captured as a new vintage. Tags exist
only as filters, so each subcategory and category is asked for the newest week.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from cachereg.core.store import RawFetch, list_fetches
from cachereg.sources._openrouter_datasets import Client

SOURCE = "openrouter_apps"
ADAPTER_VERSION = "1"
ENDPOINT = "app-rankings"
FLOOR = date(2025, 1, 6)  # first Monday of the dataset (it starts 2025-01-01)
REFRESH_WEEKS = 5
LIMIT = 100  # API maximum; with offset ≤ 100 a window reaches rank 200 at most
CATEGORIES = ("coding", "creative", "productivity", "entertainment")
SUBCATEGORIES = (
    "cli-agent", "ide-extension", "cloud-agent", "programming-app", "native-app-builder",
    "creative-writing", "video-gen", "image-gen", "audio-gen", "roleplay", "game",
    "writing-assistant", "general-chat", "personal-agent", "legal",
)  # fmt: skip


def last_week_end(today: date) -> date:
    """The Sunday ending the latest complete ISO week (on or before today − 1)."""
    end = today - timedelta(days=1)
    return end - timedelta(days=(end.weekday() + 1) % 7)


def week_windows(today: date) -> list[tuple[date, date]]:
    last = last_week_end(today)
    weeks, start = [], FLOOR
    while start + timedelta(days=6) <= last:
        weeks.append((start, start + timedelta(days=6)))
        start += timedelta(days=7)
    return weeks


def plan_weeks(today: date, full: bool) -> list[tuple[date, date]]:
    weeks = week_windows(today)
    return weeks if full or not list_fetches(SOURCE) else weeks[-REFRESH_WEEKS:]


def file_name(start: date, end: date, offset: int) -> str:
    return f"apps_{start:%Y%m%d}_{end:%Y%m%d}_o{offset}.json"


def tag_file_name(kind: str, tag: str, start: date, offset: int) -> str:
    return f"tag_{kind}_{tag}_{start:%Y%m%d}_o{offset}.json"


def check_page(body: dict, start: date, end: date, offset: int, seen: set) -> None:
    meta = body["meta"]
    if (meta.get("start_date"), meta.get("end_date")) != (start.isoformat(), end.isoformat()):
        raise ValueError(
            f"app-rankings: window {start}..{end} answered as {meta.get('start_date')}..{meta.get('end_date')}"
        )
    for i, r in enumerate(body["data"]):
        if not isinstance(r, dict) or r.get("rank") != offset + i + 1:
            raise ValueError(f"app-rankings {start}: ranks are not contiguous from {offset + 1}")
        app_id = r.get("app_id")
        if isinstance(app_id, bool) or not isinstance(app_id, int):
            raise ValueError(f"app-rankings {start}: app_id {app_id!r} is not an integer")
        if app_id in seen:
            raise ValueError(f"app-rankings {start}: app_id {app_id} listed twice")
        seen.add(app_id)
        tokens = r.get("total_tokens")
        if not isinstance(tokens, str) or not tokens.isdigit():
            raise ValueError(f"app-rankings {start}: total_tokens {tokens!r} is not a decimal string")
        requests = r.get("total_requests")
        if isinstance(requests, bool) or not isinstance(requests, int) or requests < 0:
            raise ValueError(f"app-rankings {start}: total_requests {requests!r} is not a count")
        if not isinstance(r.get("app_name"), str):
            raise ValueError(f"app-rankings {start}: app {app_id} has no name")


def fetch_ranked(client: Client, raw: RawFetch, start: date, end: date, name, extra=None) -> list:
    """Ranks 1–100, then 101–200 when the first page is full; stores each page, returns as_of values.

    An unfiltered week is never empty: an empty first page (e.g. a week not yet materialised) fails
    the fetch, or the mart would silently drop the week or keep an older vintage. A tag filter can
    be empty.
    """
    as_of, seen = [], set()
    for offset in (0, LIMIT):
        params = {"start_date": start.isoformat(), "end_date": end.isoformat(), "sort": "popular"}
        params |= {"limit": str(LIMIT), "offset": str(offset), **(extra or {})}
        resp, body = client.get(ENDPOINT, params)
        check_page(body, start, end, offset, seen)
        if offset == 0 and not body["data"] and not extra:
            raise ValueError(f"app-rankings: no apps for the week {start}..{end}")
        as_of.append(body["meta"].get("as_of"))
        raw.add(name(offset), json.dumps(body).encode(), resp.url, resp.status)
        if len(body["data"]) < LIMIT:
            break
    return as_of


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    today = today or datetime.now(UTC).date()
    weeks = plan_weeks(today, full)
    if not weeks:
        raise ValueError(f"app-rankings: no complete week between {FLOOR} and {today}")
    client, raw, as_of = Client(), RawFetch(SOURCE, ADAPTER_VERSION), []
    for ws, we in weeks:
        as_of += fetch_ranked(client, raw, ws, we, lambda o, ws=ws, we=we: file_name(ws, we, o))
    ws, we = weeks[-1]
    for kind, tags in (("category", CATEGORIES), ("subcategory", SUBCATEGORIES)):
        for tag in tags:
            name = lambda o, kind=kind, tag=tag: tag_file_name(kind, tag, ws, o)  # noqa: E731
            as_of += fetch_ranked(client, raw, ws, we, name, {kind: tag})
    raw.vintage = {
        "kind": "api_as_of",
        "value": max((a for a in as_of if a), default=None),
        "window": [weeks[0][0].isoformat(), weeks[-1][1].isoformat()],
    }
    return raw
