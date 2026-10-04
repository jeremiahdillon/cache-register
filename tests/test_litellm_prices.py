"""LiteLLM price history source on synthetic data (no network, no recorded upstream files)."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, date, datetime

import pytest

from cachereg.core.http import Response
from cachereg.core.store import RawFetch
from cachereg.sources.litellm_prices import fetch as lf
from cachereg.sources.litellm_prices import stage as ls
from cachereg.sources.litellm_prices.history import day_end, day_end_commits, parse_first_parent


def _ts(y, m, d, hh=12, mm=0, ss=0) -> int:
    return int(datetime(y, m, d, hh, mm, ss, tzinfo=UTC).timestamp())


def test_day_end_commits_boundaries_and_gaps():
    fp = [  # newest first
        ("c3", _ts(2025, 1, 4, 0, 0, 0)),
        ("c2", _ts(2025, 1, 2, 23, 59, 59)),  # exactly at the end of Jan 2 counts for Jan 2
        ("c1", _ts(2024, 12, 20)),
    ]
    days = day_end_commits(fp, date(2025, 1, 1), date(2025, 1, 4))
    assert {d.day: sha for d, (sha, _) in days.items()} == {1: "c1", 2: "c2", 3: "c2", 4: "c3"}


def test_day_end_commits_non_monotonic_times_follow_first_parent_order():
    # c3 carries an older committer time than its parent c2: the first in order wins for each day.
    fp = [("c3", _ts(2025, 1, 2)), ("c2", _ts(2025, 1, 3)), ("c1", _ts(2024, 12, 31))]
    days = day_end_commits(fp, date(2025, 1, 2), date(2025, 1, 3))
    assert days[date(2025, 1, 2)][0] == "c3" and days[date(2025, 1, 3)][0] == "c3"


def test_day_end_commits_fails_when_history_is_too_short():
    with pytest.raises(ValueError, match="does not reach back"):
        day_end_commits([("c1", _ts(2025, 1, 5))], date(2025, 1, 1), date(2025, 1, 5))


def test_parse_first_parent_and_day_end():
    assert parse_first_parent("a\t10\n\nb\t5\n") == [("a", 10), ("b", 5)]
    assert day_end(date(2025, 1, 1)) == _ts(2025, 1, 1, 23, 59, 59)


def _file(**prices) -> bytes:
    """A synthetic price file: key -> (input, output) $/token, or None for an entry without prices."""
    data = {"sample_spec": {"input_cost_per_token": 0}}
    for key, p in prices.items():
        k = key.replace("__", "/")
        data[k] = {"litellm_provider": "openrouter", "mode": "chat"}
        if p is not None:
            data[k] |= {"input_cost_per_token": p[0], "output_cost_per_token": str(p[1])}
    return gzip.compress(json.dumps(data).encode(), mtime=0)


def _write_fetch(fetched: datetime, listing: list[tuple[str, int]], files: dict[str, bytes], window) -> None:
    r = RawFetch("litellm_prices", "1", fetched_at=fetched)
    r.add("first_parent.tsv", "".join(f"{s}\t{t}\n" for s, t in listing).encode(), "https://example.test/repo.git", 200)
    for sha, body in files.items():
        r.add(f"prices_{sha}.json.gz", body, "https://example.test", 200)
    r.vintage = {"kind": "git_commit", "value": listing[0][0], "window": [str(window[0]), str(window[1])]}
    r.write()


LISTING = [  # newest first; one commit per day from Jan 1 to Jan 5 2025, plus one before FLOOR
    ("s5", _ts(2025, 1, 5)),
    ("s4", _ts(2025, 1, 4)),
    ("s3", _ts(2025, 1, 3)),
    ("s2", _ts(2025, 1, 2)),
    ("s1", _ts(2024, 12, 31)),
]


def test_stage_builds_intervals_across_fetches(data_env):
    files = {
        "s1": _file(a=(1e-6, 2e-6), b=(5e-6, 1e-5)),
        "s2": _file(a=(1e-6, 2e-6), b=(5e-6, 1e-5), c=None),
        "s3": _file(a=(0.5e-6, 2e-6), c=None),  # a cut, b removed
        "s4": _file(a=(0.5e-6, 2e-6), b=(4e-6, 1e-5), c=None),  # b re-added at a new price
    }
    _write_fetch(datetime(2025, 1, 5, 6, tzinfo=UTC), LISTING[1:], files, (date(2025, 1, 1), date(2025, 1, 4)))
    _write_fetch(
        datetime(2025, 1, 6, 6, tzinfo=UTC), LISTING, {"s5": files["s4"]}, (date(2025, 1, 5), date(2025, 1, 5))
    )
    out = ls.stage()
    days = out["days"]
    assert days["date"].to_list() == [date(2025, 1, d) for d in range(1, 6)]
    assert days["commit_sha"].to_list() == ["s1", "s2", "s3", "s4", "s5"]
    p = {(r["key"], r["valid_from"].day): r for r in out["prices"].to_dicts()}
    assert p[("a", 1)]["valid_to"] == date(2025, 1, 3) and p[("a", 1)]["input_usd_per_token"] == 1e-6
    assert p[("a", 3)]["valid_to"] is None and p[("a", 3)]["commit_sha"] == "s3"
    assert p[("b", 1)]["valid_to"] == date(2025, 1, 3)  # removed on Jan 3
    assert p[("b", 4)]["input_usd_per_token"] == 4e-6 and p[("b", 4)]["valid_to"] is None
    assert p[("b", 1)]["output_usd_per_token"] == 1e-5  # string prices parsed
    assert p[("c", 2)]["input_usd_per_token"] is None  # listed without prices: kept, null
    assert "sample_spec" not in out["prices"]["key"].to_list()
    assert ls.vintage_at(date(2025, 1, 3)) == {"kind": "git_commit", "value": "s3", "date": "2025-01-03"}
    assert ls.vintage_at(date(2025, 3, 1))["value"] == "s5"  # clipped to the last staged day


def test_stage_fails_when_a_day_has_no_stored_file(data_env):
    _write_fetch(
        datetime(2025, 1, 4, 6, tzinfo=UTC),
        LISTING[2:],
        {"s1": _file(a=(1e-6, 2e-6))},
        (date(2025, 1, 1), date(2025, 1, 3)),
    )
    with pytest.raises(ValueError, match="no stored price file for 2025-01-02"):
        ls.stage()


def test_fetch_is_incremental_and_stores_bodies_as_returned(data_env, monkeypatch):
    listing = "".join(f"{s}\t{t}\n" for s, t in LISTING)
    monkeypatch.setattr(lf, "list_first_parent", lambda since: listing)
    calls = []

    def fake_get(url, params=None, headers=None, **kw):
        calls.append(url)
        sha = url.split("/")[-2]
        body = _file(a=(1e-6, 2e-6)) if sha != "s3" else json.dumps({"a": {"input_cost_per_token": 1}}).encode()
        assert headers == {"Accept-Encoding": "gzip"}
        return Response(url=url, status=200, body=body)

    monkeypatch.setattr(lf.http, "get", fake_get)
    raw = lf.fetch(today=date(2025, 1, 4))  # complete days: Jan 1..3
    assert raw.vintage == {"kind": "git_commit", "value": "s3", "window": ["2025-01-01", "2025-01-03"]}
    assert sorted(raw.files) == ["first_parent.tsv", "prices_s1.json.gz", "prices_s2.json.gz", "prices_s3.json"]
    raw.write()
    calls.clear()
    raw2 = lf.fetch(today=date(2025, 1, 6))
    assert [c.split("/")[-2] for c in calls] == ["s4", "s5"]  # only new commits are downloaded
    assert raw2.vintage["window"] == ["2025-01-04", "2025-01-05"]


def test_fetch_rejects_a_body_that_is_not_a_price_file(data_env, monkeypatch):
    monkeypatch.setattr(lf, "list_first_parent", lambda since: f"s1\t{_ts(2024, 12, 31)}\n")
    monkeypatch.setattr(lf.http, "get", lambda url, **kw: Response(url=url, status=200, body=b"[1, 2]"))
    with pytest.raises(ValueError, match="not a JSON object"):
        lf.fetch(today=date(2025, 1, 2))
