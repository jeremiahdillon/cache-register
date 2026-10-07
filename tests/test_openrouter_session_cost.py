"""OpenRouter session-cost source and mart 055 on synthetic snapshots (no network, no recorded data)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
import yaml

from cachereg.build import VintageGapError, build
from cachereg.core.http import Response
from cachereg.core.store import RawFetch
from cachereg.core.warehouse import connect, query
from cachereg.sources import _openrouter_datasets as ds
from cachereg.sources.openrouter_session_cost import fetch as sf
from cachereg.sources.openrouter_session_cost import harnesses
from cachereg.sources.openrouter_session_cost import stage as ss

SONNET = "anthropic/claude-sonnet-9-20260101"  # mapped in the synthetic models.yaml
GPT = "openai/gpt-9-20260101"  # mapped
UNMAPPED = "acme/unknown-model-20260101"


def cell(app, model, turn, cost):
    return {"app_slug": app, "app_name": app.replace("-", " ").title(), "turn_range": turn,
            "model_permaslug": model, "median_session_cost_usd": cost}  # fmt: skip


def snapshot(window_end: str, scale: float = 1.0) -> dict[str, list[dict]]:
    """Cells per turn range for one synthetic snapshot."""
    return {
        "1-turn": [cell("harness-a", SONNET, "1-turn", 0.10 * scale), cell("harness-b", GPT, "1-turn", 0.05 * scale)],
        "2-9-turns": [
            cell("harness-a", SONNET, "2-9-turns", 0.80 * scale),
            cell("harness-b", UNMAPPED, "2-9-turns", 0.3),
        ],
        "10-49-turns": [cell("harness-a", GPT, "10-49-turns", 2.5 * scale)],
        "50-plus-turns": [cell("harness-c", SONNET, "50-plus-turns", 9.0 * scale)],
    }


def body(rows, window_end="2026-09-27", days=30, as_of="2026-09-28T07:00:00.000Z"):
    return {"data": rows, "meta": {"as_of": as_of, "version": "v1", "window_days": days, "window_end_date": window_end}}


@pytest.fixture
def entities(synthetic_entities):
    (synthetic_entities / "apps.yaml").write_text(
        yaml.safe_dump(
            {
                "harnesses": {
                    "harness-a": {"app_id": 101, "name": "Harness A", "vendor": "anthropic"},
                    "harness-b": {"app_id": 102, "name": "Harness B"},
                }
            }  # fmt: skip
        )
    )
    return synthetic_entities


@pytest.fixture
def api(data_env, monkeypatch):
    """Fake session-cost API serving `state["cells"]`; records every request's params."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-synthetic")
    monkeypatch.setattr(ds, "PAUSE", 0)
    state = {"cells": snapshot("2026-09-27"), "window": "2026-09-27", "seen": [], "meta": {}}

    def fake_get(url, params=None, headers=None, **kw):
        assert url == ds.BASE + "session-cost" and headers["Authorization"] == "Bearer sk-synthetic"
        state["seen"].append(dict(params))
        window = state["window"](len(state["seen"])) if callable(state["window"]) else state["window"]
        rows = state["cells"][params["turn_range"]]
        off, lim = int(params["offset"]), int(params["limit"])
        b = body(rows[off : off + lim], window)
        b["meta"] |= state["meta"]
        return Response(url + "?synthetic", 200, json.dumps(b).encode())

    monkeypatch.setattr(ds.http, "get", fake_get)
    return state


def write_snapshot(cells: dict[str, list[dict]], window_end: str, fetched: datetime) -> None:
    r = RawFetch("openrouter_session_cost", "1", fetched_at=fetched)
    for turn, rows in cells.items():
        r.add(sf.file_name(turn, 0), json.dumps(body(rows, window_end)).encode(), "https://example.test", 200)
    r.vintage = {"kind": "snapshot", "value": window_end, "window_days": 30}
    r.write()


def marts(as_of: date):
    """Build, then a query function that opens (and closes) its own read-only connection."""
    build(as_of, ["openrouter_session_cost"])

    def q(sql: str):
        con = connect()
        try:
            return query(con, sql)
        finally:
            con.close()

    return q


# --- fetch -------------------------------------------------------------------


def test_fetch_asks_once_per_turn_range_and_records_the_snapshot(api):
    raw = sf.fetch()
    assert [p["turn_range"] for p in api["seen"]] == list(sf.TURN_RANGES)
    assert all(p["limit"] == "500" and p["offset"] == "0" for p in api["seen"])
    assert sorted(raw.files) == sorted(sf.file_name(t, 0) for t in sf.TURN_RANGES)
    assert raw.vintage == {
        "kind": "snapshot",
        "value": "2026-09-27",
        "window_days": 30,
        "as_of": "2026-09-28T07:00:00.000Z",
    }
    manifest = raw.write().joinpath("manifest.json").read_text()
    assert "sk-synthetic" not in manifest


def test_fetch_pages_while_a_page_is_full(api, monkeypatch):
    monkeypatch.setattr(sf, "LIMIT", 1)
    raw = sf.fetch()
    two = [p["offset"] for p in api["seen"] if p["turn_range"] == "1-turn"]
    assert two == ["0", "1", "2"]  # two full pages, then an empty one
    assert {"session_cost_1-turn_o0.json", "session_cost_1-turn_o1.json", "session_cost_1-turn_o2.json"} <= set(
        raw.files
    )


def test_fetch_refuses_more_cells_than_the_api_can_page(api, monkeypatch):
    monkeypatch.setattr(sf, "LIMIT", 1)
    monkeypatch.setattr(sf, "MAX_OFFSET", 0)
    with pytest.raises(ValueError, match="more than"):
        sf.fetch()


def test_a_snapshot_published_mid_fetch_is_retried_once(api):
    api["window"] = lambda n: "2026-09-27" if n <= 2 else "2026-10-04"  # changes at request 3
    raw = sf.fetch()
    assert raw.vintage["value"] == "2026-10-04" and len(api["seen"]) == 3 + 4


def test_a_snapshot_that_keeps_changing_fails(api):
    api["window"] = lambda n: f"2026-09-{n:02d}"
    with pytest.raises(sf.SnapshotChanged):
        sf.fetch()
    assert len(api["seen"]) == 4  # two attempts of two requests each


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"meta": {"window_end_date": None}}, "no snapshot"),
        ({"meta": {"version": "v2"}}, "version"),
        ({"rows": [cell("harness-a", SONNET, "1-turn", 1.0)] * 2}, "duplicate"),
        ({"rows": [cell("harness-a", SONNET, "2-9-turns", 1.0)]}, "turn_range"),
        ({"rows": [cell("harness-a", SONNET, "1-turn", True)]}, "median"),
        ({"rows": [cell("harness-a", SONNET, "1-turn", -1.0)]}, "median"),
        ({"rows": [cell("", SONNET, "1-turn", 1.0)]}, "app_slug"),
    ],
)
def test_fetch_refuses_bad_responses(api, change, match):
    api["meta"] = change.get("meta", {})
    if "rows" in change:
        api["cells"]["1-turn"] = change["rows"]
    with pytest.raises(ValueError, match=match):
        sf.fetch()


# --- entities and stage -------------------------------------------------------


def test_harnesses_validation(entities):
    f = entities / "apps.yaml"
    assert [h.app_slug for h in harnesses.load_harnesses()] == ["harness-a", "harness-b"]
    f.write_text(yaml.safe_dump({"harnesses": {"x": {"app_id": 1, "name": "X", "vendor": "nobody"}}}))
    with pytest.raises(ValueError, match="vendors.yaml"):
        harnesses.load_harnesses()
    f.write_text(yaml.safe_dump({"harnesses": {"x": {"app_id": 1, "name": "X"}, "y": {"app_id": 1, "name": "Y"}}}))
    with pytest.raises(ValueError, match="twice"):
        harnesses.load_harnesses()
    f.write_text(yaml.safe_dump({"harnesses": {"x": {"app_id": "1", "name": "X"}}}))
    with pytest.raises(ValueError, match="integer"):
        harnesses.load_harnesses()


def test_the_shipped_apps_file_loads_and_its_vendors_resolve():
    assert {h.app_slug for h in harnesses.load_harnesses()} >= {"claude-code", "codex"}


def test_stage_bounds_rejects_and_harnesses(data_env, entities):
    cells = snapshot("2026-09-27")
    cells["1-turn"].append({"app_slug": "harness-a", "turn_range": "1-turn", "model_permaslug": GPT})  # no cost
    cells["2-9-turns"].append(cell("harness-a", GPT, "7-turns", 1.0))  # unknown range
    write_snapshot(cells, "2026-09-27", datetime(2026, 9, 28, 12, tzinfo=UTC))
    out = ss.stage()
    c = out["cells"]
    assert c.height == 6 and int(out["_rejected_rows"]["rejected"][0]) == 2
    bounds = set(c.select("turn_range", "turn_min", "turn_max").iter_rows())
    assert bounds == {("1-turn", 1, 1), ("2-9-turns", 2, 9), ("10-49-turns", 10, 49), ("50-plus-turns", 50, None)}
    assert c["window_end_date"].unique().to_list() == [date(2026, 9, 27)]
    assert out["harnesses"]["app_id"].to_list() == [101, 102]


# --- mart 055 ----------------------------------------------------------------


@pytest.fixture
def snapshots(data_env, entities):
    write_snapshot(snapshot("2026-09-27"), "2026-09-27", datetime(2026, 9, 28, 12, tzinfo=UTC))
    write_snapshot(snapshot("2026-10-04", 2.0), "2026-10-04", datetime(2026, 10, 5, 12, tzinfo=UTC))
    # the same window fetched again later (e.g. a manual re-run): the later fetch wins
    write_snapshot(snapshot("2026-10-04", 3.0), "2026-10-04", datetime(2026, 10, 6, 12, tzinfo=UTC))
    return data_env


def test_mart_keeps_every_snapshot_and_the_latest_fetch_per_window(snapshots):
    q = marts(date(2026, 10, 7))
    rows = q("SELECT window_end_date, count(*) AS n, any_value(fetch_id) AS f, bool_or(is_latest_snapshot) AS latest "
             "FROM or_session_cost GROUP BY 1 ORDER BY 1")  # fmt: skip
    assert rows["n"].to_list() == [6, 6]
    assert rows["f"].to_list() == ["20260928T120000Z", "20261006T120000Z"]
    assert rows["latest"].to_list() == [False, True]
    a = q("SELECT median_session_cost_usd, window_start_date FROM or_session_cost "
          "WHERE window_end_date = DATE '2026-10-04' AND app_slug = 'harness-a' AND turn_range = '1-turn'")  # fmt: skip
    assert a["median_session_cost_usd"][0] == pytest.approx(0.30)
    assert a["window_start_date"][0] == date(2026, 9, 5)


def test_mart_as_of_selects_by_fetch_and_window(snapshots):
    q = marts(date(2026, 10, 5))  # the 10-06 re-fetch is not yet known
    r = q("SELECT DISTINCT window_end_date, fetch_id FROM or_session_cost ORDER BY 1")
    assert r["fetch_id"].to_list() == ["20260928T120000Z", "20261005T120000Z"]
    q = marts(date(2026, 10, 1))
    assert q("SELECT DISTINCT window_end_date FROM or_session_cost")["window_end_date"].to_list() == [date(2026, 9, 27)]


def test_mart_joins_models_and_harnesses_and_reports_coverage(snapshots):
    q = marts(date(2026, 10, 7))
    r = q("SELECT app_slug, model_permaslug, model_id, model_vendor_id, app_id, harness_vendor_id FROM or_session_cost "
          "WHERE window_end_date = DATE '2026-10-04' ORDER BY app_slug, turn_min")  # fmt: skip
    first = r.row(0, named=True)
    assert first["model_id"] == "anthropic/claude-sonnet-9" and first["model_vendor_id"] == "anthropic"
    assert first["app_id"] == 101 and first["harness_vendor_id"] == "anthropic"
    cov = q("SELECT * FROM or_session_cost_coverage WHERE window_end_date = DATE '2026-10-04' ORDER BY app_slug")
    by = {r["app_slug"]: r for r in cov.iter_rows(named=True)}
    assert (by["harness-b"]["cells"], by["harness-b"]["cells_with_model_id"], by["harness-b"]["unmapped_models"]) == (
        2,
        1,
        1,
    )
    assert by["harness-c"]["harness_unmapped"] is True and by["harness-c"]["app_id"] is None
    assert by["harness-a"]["turn_ranges"] == ["1-turn", "10-49-turns", "2-9-turns"]


def test_build_refuses_an_as_of_before_the_first_snapshot(snapshots):
    with pytest.raises(VintageGapError, match="snapshot"):
        build(date(2026, 9, 27), ["openrouter_session_cost"])
