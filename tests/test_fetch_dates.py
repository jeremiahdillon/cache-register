"""Marts date a fetch by its UTC date, the date build.cutoff() uses, whatever the session's time zone.

Before the `fetch_date(fetch_id)` macro, marts compared `CAST(fetched_at AS DATE)`, which DuckDB evaluates in
the session's local zone: behind UTC, a later fetch made just after 00:00 UTC was dated a day early and
selected for an as_of before its UTC date; ahead of UTC, the cutoff fetch itself made late in the UTC day was
dated a day late and excluded. Each case runs the build under a forced session zone (`build._connect`), one
test per selection pattern: 005's latest-per-row, 090's `pick`, 101's per-ticker `pick`.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from cachereg import build as build_mod
from cachereg.build import build
from cachereg.core.store import RawFetch
from cachereg.core.warehouse import connect, query
from tests.conftest import synthetic_rankings
from tests.test_market_sources import (
    yahoo,  # noqa: F401 (fixture)
    yf,
)
from tests.test_vercel_ai_gateway import (
    api,  # noqa: F401 (fixture)
    vf,
)


def _at(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=UTC)


# zone, (first fetch, second fetch) as (day offset from D, hour, minute), as_of offset, which fetch is right
CASES = {
    # behind UTC: the second fetch (D 00:30Z) is D-1 locally; for as_of D-1 the first fetch is right
    "behind": ("America/Los_Angeles", ((-1, 13, 0), (0, 0, 30)), -1, 0),
    # ahead of UTC: the second fetch (D 23:00Z) is D+1 locally; for as_of D it is the right one
    "ahead": ("Asia/Tokyo", ((-1, 8, 0), (0, 23, 0)), 0, 1),
}


@pytest.fixture(params=sorted(CASES))
def zone(request, monkeypatch):
    tz, times, as_of_offset, right = CASES[request.param]
    real = build_mod._connect

    def connect_in_zone(path):
        con = real(path)
        con.execute(f"SET TimeZone = '{tz}'")
        return con

    monkeypatch.setattr(build_mod, "_connect", connect_in_zone)
    return times, as_of_offset, right


def _q(sql: str) -> list[dict]:
    con = connect()
    try:
        return query(con, sql).to_dicts()
    finally:
        con.close()


def test_005_rankings_rows_come_from_the_utc_dated_fetch(data_env, zone):
    times, as_of_offset, right = zone
    d = date(2026, 9, 2)
    ids = []
    for days, h, m in times:
        r = RawFetch("openrouter_rankings", "1", fetched_at=_at(d + timedelta(days=days), h, m))
        body = json.dumps(synthetic_rankings(date(2026, 8, 1), 30)).encode()
        r.add("rankings.json", body, "https://example.test", 200)
        r.vintage = {"kind": "api_as_of", "value": r.fetched_at.isoformat()}
        r.write()
        ids.append(r.fetch_id)
    build(d + timedelta(days=as_of_offset), ["openrouter_rankings"])
    got = {r["fetch_id"] for r in _q("SELECT DISTINCT fetch_id FROM or_rankings_daily")}
    assert got == {ids[right]}


def test_090_vercel_day_comes_from_the_utc_dated_fetch(api, zone):  # noqa: F811
    times, as_of_offset, right = zone
    d = date(2025, 11, 10)
    ids = []
    for days, h, m in times:
        when = _at(d + timedelta(days=days), h, m)
        raw = vf.fetch(full=True, today=when.date())
        raw.fetched_at = when
        raw.write()
        ids.append(raw.fetch_id)
    build(d + timedelta(days=as_of_offset), ["vercel_ai_gateway"])
    got = _q("SELECT DISTINCT fetch_id FROM vercel_lab_share WHERE date = DATE '2025-11-08'")
    assert [r["fetch_id"] for r in got] == [ids[right]]


def test_101_stock_closes_come_from_the_utc_dated_fetch(yahoo, zone):  # noqa: F811
    times, as_of_offset, right = zone
    d = date(2026, 3, 9)  # after the synthetic sessions (2026-03-02..06), so every bar is final
    ids = []
    for days, h, m in times:
        raw = yf.fetch()
        raw.fetched_at = _at(d + timedelta(days=days), h, m)
        raw.write()
        ids.append(raw.fetch_id)
    build(d + timedelta(days=as_of_offset), ["yahoo_prices"])
    got = {r["fetch_id"] for r in _q("SELECT DISTINCT fetch_id FROM stock_daily")}
    assert got == {ids[right]}
