"""GitHub Innovation Graph source and mart 130 on synthetic releases (no network, no recorded files)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from cachereg.build import build
from cachereg.core.http import Response
from cachereg.core.warehouse import connect, query
from cachereg.sources.github_innovation_graph import fetch as gf
from cachereg.sources.github_innovation_graph import files as gfiles
from cachereg.sources.github_innovation_graph import stage as gs

SHA1, SHA2 = "a" * 40, "b" * 40


def commits(*releases: tuple[str, str]) -> bytes:
    """A commits listing, newest first as the API serves it."""
    return json.dumps(
        [{"sha": sha, "commit": {"committer": {"date": f"{d}T12:00:00Z"}}} for sha, d in reversed(releases)]
    ).encode()


def pushes(quarters: int) -> dict[str, bytes]:
    """Release files covering 2025 Q1 onwards: US, DE and the EU aggregate."""
    out = {}
    for name in gfiles.FILES:
        metric = name.removesuffix(".csv")
        lines = [f"{metric},iso2_code,year,quarter"]
        for i in range(quarters):
            y, q = 2025 + i // 4, i % 4 + 1
            base = 1000 if metric == "git_pushes" else 100
            lines += [f"{base * (i + 1)},US,{y},{q}", f"{base},DE,{y},{q}", f"{base * 5},EU,{y},{q}"]
        out[name] = ("\n".join(lines) + "\n").encode()
    return out


def fake_github(monkeypatch, listing: bytes, files_by_sha: dict[str, dict[str, bytes]], seen: list | None = None):
    def fake_get(url, params=None, headers=None, **kw):
        if seen is not None:
            seen.append(url)
        if url == gf.API:
            assert params["path"] == "data/git_pushes.csv"
            return Response(url, 200, listing)
        sha, name = url.split("/innovationgraph/")[1].split("/data/")
        return Response(url, 200, files_by_sha[sha][name])

    monkeypatch.setattr(gf.http, "get", fake_get)
    monkeypatch.setattr(gf, "PAUSE", 0)


@pytest.fixture
def two_releases(data_env, monkeypatch):
    """Release 1 (2025-08-13) has two quarters; release 2 (2026-01-28) has three."""
    files = {SHA1: pushes(2), SHA2: pushes(3)}
    fake_github(monkeypatch, commits((SHA1, "2025-08-13")), files)
    gf.fetch(today=date(2025, 9, 1)).write()
    fake_github(monkeypatch, commits((SHA1, "2025-08-13"), (SHA2, "2026-01-28")), files)
    gf.fetch(today=date(2026, 2, 1)).write()
    return data_env


def test_fetch_stores_each_release_once_and_records_the_newest(data_env, monkeypatch):
    seen = []
    fake_github(monkeypatch, commits((SHA1, "2025-08-13")), {SHA1: pushes(2)}, seen)
    first = gf.fetch(today=date(2025, 9, 1))
    first.write()
    assert sorted(first.files) == ["commits.json", f"developers_{SHA1}.csv", f"git_pushes_{SHA1}.csv"]
    assert first.vintage == {
        "kind": "git_commit",
        "value": SHA1,
        "date": "2025-08-13",
        "window": ["2025-08-13", "2025-08-31"],
        "new_releases": [SHA1],
    }
    seen.clear()
    again = gf.fetch(today=date(2025, 9, 8))
    assert sorted(again.files) == ["commits.json"]  # nothing new to download
    assert seen == [gf.API]


@pytest.mark.parametrize(
    ("body", "match"),
    [
        (b"pushes,iso2_code,year,quarter\n1,US,2025,1\n", "header"),
        (b"git_pushes,iso2_code,year,quarter\nmany,US,2025,1\n", "integers"),
        (b"git_pushes,iso2_code,year,quarter\n1,USA,2025,1\n", "two-letter"),
        (b"git_pushes,iso2_code,year,quarter\n1,US,2025,5\n", "out-of-range"),
        (b"git_pushes,iso2_code,year,quarter\n1,US,2025,1\n2,US,2025,1\n", "duplicate"),
        (b"git_pushes,iso2_code,year,quarter\n", "no rows"),
    ],
)
def test_fetch_refuses_malformed_files(data_env, monkeypatch, body, match):
    files = {SHA1: pushes(1) | {"git_pushes.csv": body}}
    fake_github(monkeypatch, commits((SHA1, "2025-08-13")), files)
    with pytest.raises(ValueError, match=match):
        gf.fetch(today=date(2025, 9, 1))


def test_fetch_refuses_a_bad_listing(data_env, monkeypatch):
    fake_github(monkeypatch, b"[]", {})
    with pytest.raises(ValueError, match="non-empty"):
        gf.fetch()
    fake_github(monkeypatch, json.dumps([{"sha": "short"}]).encode(), {})
    with pytest.raises(ValueError, match="40-character"):
        gf.fetch()


def test_vintage_at_is_the_newest_release_on_or_before_as_of(two_releases):
    assert gs.vintage_at(date(2025, 8, 12)) is None
    assert gs.vintage_at(date(2025, 12, 31))["value"] == SHA1
    assert gs.vintage_at(date(2026, 1, 28)) == {"kind": "git_commit", "value": SHA2, "date": "2026-01-28"}


def test_stage_needs_every_listed_release(data_env, monkeypatch):
    fake_github(monkeypatch, commits((SHA1, "2025-08-13")), {SHA1: pushes(1)})
    raw = gf.fetch(today=date(2025, 9, 1))
    raw.files.pop(f"developers_{SHA1}.csv")
    raw.write()
    with pytest.raises(ValueError, match="no stored developers.csv"):
        gs.stage()


def test_mart_uses_the_release_known_on_as_of_and_never_adds_aggregates(two_releases):
    def mart(as_of):
        build(as_of, ["github_innovation_graph"])
        return query(
            connect(),
            "SELECT economy, cal_quarter, git_pushes, developers, release_sha FROM github_quarterly "
            "WHERE economy IN ('US', '_world') ORDER BY economy, cal_quarter",
        ).rows()

    before = mart(date(2025, 12, 1))
    assert {r[4] for r in before} == {SHA1}
    assert [r[:4] for r in before] == [
        ("US", date(2025, 1, 1), 1000, 100),
        ("US", date(2025, 4, 1), 2000, 200),
        ("_world", date(2025, 1, 1), 2000, 200),  # US + DE, never the EU aggregate
        ("_world", date(2025, 4, 1), 3000, 300),
    ]
    after = mart(date(2026, 2, 1))
    assert {r[4] for r in after} == {SHA2}
    assert [r[1] for r in after if r[0] == "US"] == [date(2025, 1, 1), date(2025, 4, 1), date(2025, 7, 1)]
