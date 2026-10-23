"""Artificial Analysis source and mart 120 on synthetic snapshots (no network, no recorded data)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from cachereg.build import VintageGapError, build
from cachereg.core.http import Response
from cachereg.core.store import list_fetches
from cachereg.core.warehouse import connect, query
from cachereg.sources.artificial_analysis import fetch as af


def model(slug, creator, released, index=None, tb4=None, **evals):
    return {
        "id": f"id-{slug}", "name": slug.title(), "slug": slug, "release_date": released,
        "model_creator": {"id": f"c-{creator}", "name": creator.title(), "slug": creator},
        "evaluations": {"artificial_analysis_intelligence_index": index, "terminalbench_v4_0": tb4} | evals,
        "pricing": {"price_1m_blended_3_to_1": 1.0},
    }  # fmt: skip


SNAPSHOT = [
    model("acme-9", "acme", "2026-01-10", 40.0, 0.25),
    model("acme-10", "acme", "2026-06-01", 50.0, 0.5, gpqa="n/a"),  # non-numeric eval: rejected
    model("open-1", "openlab", "2026-03-01", 30.0, None),
    model("future-1", "acme", "2026-12-01", 60.0, 0.7),  # released after as_of
    model("undated", "openlab", None, 10.0),
]


@pytest.fixture
def api(data_env, monkeypatch):
    monkeypatch.setenv("ARTIFICIAL_ANALYSIS_API_KEY", "aa-synthetic")
    state = {"data": SNAPSHOT}

    def fake_get(url, params=None, headers=None, **kw):
        assert url == af.URL and headers["x-api-key"] == "aa-synthetic"
        body = json.dumps({"status": 200, "data": state["data"]}).encode()
        return Response(url, 200, body)

    monkeypatch.setattr(af.http, "get", fake_get)
    return state


def test_fetch_stores_snapshot(api):
    af.fetch().write()
    (f,) = list_fetches("artificial_analysis")
    assert f.manifest["vintage"]["kind"] == "snapshot"
    assert json.loads(f.read("models.json"))["data"][0]["slug"] == "acme-9"


def test_fetch_rejects_empty(api):
    api["data"] = []
    with pytest.raises(ValueError, match="unexpected response shape"):
        af.fetch()


def test_build_marts(api):
    raw = af.fetch()
    raw.write()
    as_of = raw.fetched_at.date()
    if as_of < date(2026, 6, 1):  # keep the fixture's dates meaningful whatever today's date
        pytest.skip("synthetic release dates are after today")
    report = build(as_of, ["artificial_analysis"])
    assert report.rejected["artificial_analysis"] == 1
    con = connect()
    try:
        slugs = set(query(con, "SELECT slug FROM aa_models")["slug"])
        assert "undated" not in slugs and ("future-1" in slugs) == (as_of >= date(2026, 12, 1))
        assert {"acme-9", "acme-10", "open-1"} <= slugs
        tb = query(con, "SELECT slug, value FROM aa_evals WHERE metric = 'terminalbench_v4_0' ORDER BY slug")
        assert {k: v for k, v in tb.iter_rows() if k != "future-1"} == {"acme-10": 0.5, "acme-9": 0.25}
        assert "open-1" not in set(tb["slug"])  # null = not evaluated, not staged
        assert query(con, "SELECT models FROM aa_undated")["models"][0] == 1
    finally:
        con.close()


def test_build_refuses_as_of_before_first_snapshot(api):
    af.fetch().write()
    with pytest.raises(VintageGapError):
        build(date(2020, 1, 1), ["artificial_analysis"])
