"""OpenRouter app-rankings source and marts 050/051 on synthetic data (no network, no recorded data)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from cachereg.build import build
from cachereg.core.http import Response
from cachereg.core.store import RawFetch
from cachereg.core.warehouse import connect, query
from cachereg.sources import _openrouter_datasets as ds
from cachereg.sources.openrouter_apps import fetch as af
from cachereg.sources.openrouter_apps import stage as ast
from tests.conftest import synthetic_rankings

TODAY = date(2025, 2, 5)  # a Wednesday: four complete weeks, 2025-01-06 .. 2025-02-02
APPS = {101: "Harness A", 102: "Chat B", 103: "Writer C"}
TAGS = {  # (kind, tag) -> app ids carrying it
    ("category", "coding"): [101],
    ("category", "entertainment"): [102],
    ("subcategory", "cli-agent"): [101],
    ("subcategory", "general-chat"): [102],
    ("subcategory", "roleplay"): [102],
}


def ranking(start: date, drop: tuple = ()) -> list[dict]:
    """Synthetic top apps for the week starting `start`: Harness A grows week by week."""
    week = (start - af.FLOOR).days // 7
    volume = {101: 1_000 * (week + 1), 102: 2_500, 103: 400}
    ordered = sorted((a for a in volume if a not in drop), key=lambda a: -volume[a])
    return [
        {
            "rank": i + 1,
            "app_id": a,
            "app_name": APPS[a],
            "total_tokens": str(volume[a]),
            "total_requests": 10 * (i + 1),
        }
        for i, a in enumerate(ordered)
    ]


def page(rows, start, end, offset, limit, as_of="2025-02-05T03:00:00.000Z"):
    meta = {"as_of": as_of, "version": "v1", "start_date": start, "end_date": end}
    return {"data": rows[offset : offset + limit], "meta": meta}


@pytest.fixture
def api(data_env, monkeypatch):
    """Fake app-rankings API; `state["mutate"]` can rewrite a response body before it is served."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-synthetic")
    monkeypatch.setattr(ds, "PAUSE", 0)
    state = {"seen": [], "mutate": None, "drop": ()}

    def fake_get(url, params=None, headers=None, **kw):
        assert url == ds.BASE + "app-rankings" and params["sort"] == "popular"
        state["seen"].append(dict(params))
        start = date.fromisoformat(params["start_date"])
        rows = ranking(start, state["drop"])
        for kind in ("category", "subcategory"):
            if kind in params:
                members = TAGS.get((kind, params[kind]), [])
                rows = [r | {"rank": i + 1} for i, r in enumerate(r for r in rows if r["app_id"] in members)]
        b = page(rows, params["start_date"], params["end_date"], int(params["offset"]), int(params["limit"]))
        if state["mutate"]:
            state["mutate"](b, params)
        return Response(url + "?synthetic", 200, json.dumps(b).encode())

    monkeypatch.setattr(ds.http, "get", fake_get)
    return state


def marts(as_of: date, sources=("openrouter_apps",)):
    build(as_of, list(sources))

    def q(sql: str):
        con = connect()
        try:
            return query(con, sql)
        finally:
            con.close()

    return q


# --- windows -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("today", "end"),
    [
        (date(2026, 10, 5), date(2026, 10, 4)),  # Monday: yesterday's Sunday closes the week
        (date(2026, 10, 4), date(2026, 9, 27)),  # Sunday: that week is not complete yet
        (date(2026, 10, 7), date(2026, 10, 4)),
    ],
)
def test_last_week_end(today, end):
    assert af.last_week_end(today) == end


def test_week_windows_are_iso_weeks_from_the_floor():
    weeks = af.week_windows(date(2026, 10, 7))
    assert weeks[0] == (date(2025, 1, 6), date(2025, 1, 12))
    assert weeks[-1] == (date(2026, 9, 28), date(2026, 10, 4))
    assert len(weeks) == 91 and all(s.weekday() == 0 and (e - s).days == 6 for s, e in weeks)
    assert af.week_windows(date(2025, 1, 12)) == []


# --- fetch -------------------------------------------------------------------


def test_backfill_then_refresh_the_trailing_weeks(api, monkeypatch):
    monkeypatch.setattr(af, "LIMIT", 2)  # 3 apps: a full first page, then a second page
    raw = af.fetch(today=TODAY)
    weekly = [p for p in api["seen"] if "category" not in p and "subcategory" not in p]
    assert [(p["start_date"], p["offset"]) for p in weekly[:2]] == [("2025-01-06", "0"), ("2025-01-06", "2")]
    assert len(weekly) == 4 * 2
    assert af.file_name(date(2025, 1, 6), date(2025, 1, 12), 2) in raw.files
    tagged = [p for p in api["seen"] if p not in weekly]
    assert {p["start_date"] for p in tagged} == {"2025-01-27"}  # newest week only
    assert len(tagged) == len(af.CATEGORIES) + len(af.SUBCATEGORIES)  # no filter fills a page of 2
    assert "tag_subcategory_general-chat_20250127_o0.json" in raw.files
    assert raw.vintage == {
        "kind": "api_as_of",
        "value": "2025-02-05T03:00:00.000Z",
        "window": ["2025-01-06", "2025-02-02"],
    }
    assert "sk-synthetic" not in raw.write().joinpath("manifest.json").read_text()

    api["seen"].clear()
    monkeypatch.setattr(af, "REFRESH_WEEKS", 2)
    af.fetch(today=TODAY + timedelta(days=7))
    weekly = {p["start_date"] for p in api["seen"] if "category" not in p and "subcategory" not in p}
    assert weekly == {"2025-01-27", "2025-02-03"}


def test_a_full_tag_page_is_followed_by_the_second_page(api, monkeypatch):
    monkeypatch.setattr(af, "LIMIT", 1)
    af.fetch(today=TODAY)
    coding = [p["offset"] for p in api["seen"] if p.get("category") == "coding"]
    assert coding == ["0", "1"]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda b, p: b["meta"].update(start_date="2025-01-01"), "answered as"),
        (lambda b, p: b["meta"].update(version="v2"), "version"),
        (lambda b, p: b["data"][1].update(rank=5), "contiguous"),
        (lambda b, p: b["data"][0].update(total_tokens="1.5e9"), "decimal string"),
        (lambda b, p: b["data"][0].update(total_tokens=12), "decimal string"),
        (lambda b, p: b["data"][0].update(app_id="101"), "integer"),
        (lambda b, p: b["data"][1].update(app_id=b["data"][0]["app_id"]), "twice"),
        (lambda b, p: b["data"][0].update(total_requests=True), "count"),
    ],
)
def test_fetch_refuses_bad_pages(api, mutate, match):
    api["mutate"] = mutate
    with pytest.raises(ValueError, match=match):
        af.fetch(today=TODAY)


def test_an_empty_week_is_refused_but_an_empty_tag_filter_is_not(api):
    def empty_week(b, p):
        if p["start_date"] == "2025-01-27" and "category" not in p and "subcategory" not in p:
            b["data"] = []

    api["mutate"] = empty_week
    with pytest.raises(ValueError, match="no apps for the week 2025-01-27"):
        af.fetch(today=TODAY)
    api["mutate"] = None
    raw = af.fetch(today=TODAY)  # e.g. `category=creative` has no members in the synthetic data
    assert json.loads(raw.files["tag_category_creative_20250127_o0.json"])["data"] == []


def test_duplicate_app_ids_across_the_two_pages_are_refused(api, monkeypatch):
    monkeypatch.setattr(af, "LIMIT", 2)

    def repeat(b, p):
        if p["offset"] == "2" and "category" not in p and "subcategory" not in p:
            b["data"][0]["app_id"] = 102

    api["mutate"] = repeat
    with pytest.raises(ValueError, match="twice"):
        af.fetch(today=TODAY)


def test_requests_are_spaced(data_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-synthetic")
    clock, slept = [100.0], []
    monkeypatch.setattr(ds.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(ds.time, "sleep", lambda s: (slept.append(s), clock.__setitem__(0, clock[0] + s)))
    body = json.dumps(page([], "2025-01-06", "2025-01-12", 0, 1)).encode()
    monkeypatch.setattr(ds.http, "get", lambda url, params, headers: Response(url, 200, body))
    c = ds.Client()
    c.get("app-rankings", {})
    clock[0] += 0.5
    c.get("app-rankings", {})
    assert slept == [pytest.approx(ds.PAUSE - 0.5)]


# --- stage -------------------------------------------------------------------


def write_fetch(fetched: datetime, weeks: list[date], drop=(), tags=True, extra_rows=()) -> None:
    r = RawFetch("openrouter_apps", "1", fetched_at=fetched)
    for ws in weeks:
        we = ws + timedelta(days=6)
        rows = ranking(ws, drop if ws == weeks[-1] else ()) + list(extra_rows)
        r.add(af.file_name(ws, we, 0), json.dumps(page(rows, str(ws), str(we), 0, 100)).encode(), "https://x.test", 200)
    if tags:
        ws = weeks[-1]
        for (kind, tag), members in TAGS.items():
            rows = [x | {"rank": i + 1} for i, x in enumerate(x for x in ranking(ws) if x["app_id"] in members)]
            b = page(rows, str(ws), str(ws + timedelta(days=6)), 0, 100)
            r.add(af.tag_file_name(kind, tag, ws, 0), json.dumps(b).encode(), "https://x.test", 200)
    r.vintage = {"kind": "api_as_of", "value": "x", "window": [str(weeks[0]), str(weeks[-1] + timedelta(days=6))]}
    r.write()


WEEKS = [af.FLOOR + timedelta(days=7 * i) for i in range(4)]  # 2025-01-06 .. 2025-01-27


def test_stage_parses_big_token_strings_tags_and_rejects(data_env):
    big = {"rank": 4, "app_id": 104, "app_name": "Huge D", "total_tokens": str(2**53 + 1), "total_requests": 1}
    bad = {"rank": 5, "app_id": 105, "app_name": "Bad E", "total_tokens": "-3", "total_requests": 1}
    write_fetch(datetime(2025, 2, 5, 12, tzinfo=UTC), WEEKS[:1], extra_rows=[big, bad])
    out = ast.stage()
    w = out["weekly"]
    assert w.filter(w["app_id"] == 104)["total_tokens"][0] == 2**53 + 1
    assert int(out["_rejected_rows"]["rejected"][0]) == 1
    t = out["tags"]
    assert sorted(t.filter(t["app_id"] == 102)["tag"].to_list()) == ["entertainment", "general-chat", "roleplay"]
    assert t["tag_week_start"].unique().to_list() == [WEEKS[0]]


def test_stage_rejects_a_file_without_a_readable_window(data_env):
    r = RawFetch("openrouter_apps", "1", fetched_at=datetime(2025, 2, 5, 12, tzinfo=UTC))
    good = page(ranking(WEEKS[0]), str(WEEKS[0]), str(WEEKS[0] + timedelta(days=6)), 0, 100)
    bad = page(ranking(WEEKS[1]), None, "2025-01-19", 0, 100)
    r.add(af.file_name(WEEKS[0], WEEKS[0] + timedelta(days=6), 0), json.dumps(good).encode(), "https://x.test", 200)
    r.add(af.file_name(WEEKS[1], WEEKS[1] + timedelta(days=6), 0), json.dumps(bad).encode(), "https://x.test", 200)
    r.add("tag_oddname.json", json.dumps(good).encode(), "https://x.test", 200)
    r.write()
    out = ast.stage()
    assert out["weekly"]["week_start"].unique().to_list() == [WEEKS[0]]
    assert out["tags"].height == 0
    assert int(out["_rejected_rows"]["rejected"][0]) == 3 + 3  # both unreadable files' rows


# --- marts -------------------------------------------------------------------


@pytest.fixture
def two_vintages(data_env):
    write_fetch(datetime(2025, 2, 3, 12, tzinfo=UTC), WEEKS)  # backfill
    # refresh of the last two weeks a week later: Writer C is gone from the newest week (hidden)
    write_fetch(datetime(2025, 2, 10, 12, tzinfo=UTC), WEEKS[2:] + [WEEKS[-1] + timedelta(days=7)], drop=(103,))
    return data_env


def test_each_week_comes_from_one_fetch(two_vintages):
    q = marts(date(2025, 2, 12))
    r = q(
        "SELECT week_start, list_sort(list(app_id)) AS apps, any_value(fetch_id) AS f "
        "FROM or_app_weekly GROUP BY 1 ORDER BY 1"
    )
    assert r["week_start"].to_list() == WEEKS + [WEEKS[-1] + timedelta(days=7)]
    assert r["f"].to_list() == ["20250203T120000Z"] * 2 + ["20250210T120000Z"] * 3
    assert r["apps"].to_list()[-1] == [101, 102]  # dropped by the newer vintage, not carried over
    assert r["apps"].to_list()[3] == [101, 102, 103]  # 2025-01-27 in the newer fetch: not its last week


def test_as_of_selects_the_vintage_and_complete_weeks(two_vintages):
    q = marts(date(2025, 2, 8))  # before the refresh; 2025-02-03 week not complete
    r = q("SELECT DISTINCT week_start, fetch_id FROM or_app_weekly ORDER BY 1")
    assert r["week_start"].to_list() == WEEKS and set(r["fetch_id"]) == {"20250203T120000Z"}
    q = marts(date(2025, 1, 20))  # before any fetch: Latest-only falls back to the earliest fetch
    assert q("SELECT max(week_end) AS m FROM or_app_weekly")["m"][0] == date(2025, 1, 19)


def test_app_dim_and_tag_weeks(two_vintages):
    q = marts(date(2025, 2, 12))
    d = {r["app_id"]: r for r in q("SELECT * FROM or_app_dim").iter_rows(named=True)}
    assert d[102]["subcategories"] == ["general-chat", "roleplay"] and d[102]["categories"] == ["entertainment"]
    assert d[103]["subcategories"] == [] and d[103]["last_week"] == WEEKS[-1]
    assert d[101]["weeks_in_top200"] == 5
    c = q("SELECT * FROM or_app_category_weekly WHERE week_start = DATE '2025-01-27' ORDER BY tag_kind, tag")
    rows = {(r["tag_kind"], r["tag"]): r for r in c.iter_rows(named=True)}
    assert rows[("subcategory", "untagged")]["apps"] == 1  # Writer C
    assert rows[("subcategory", "roleplay")]["total_tokens"] == 2_500
    assert rows[("subcategory", "general-chat")]["tags_overlap"] is True
    assert rows[("category", "coding")]["tags_overlap"] is False
    sub = sum(r["total_tokens"] for k, r in rows.items() if k[0] == "subcategory")
    assert sub == 4_000 + 2 * 2_500 + 400  # Chat B counted under both of its subcategories


def test_share_of_openrouter_uses_complete_rankings_weeks(two_vintages, synthetic_entities):
    r = RawFetch("openrouter_rankings", "1", fetched_at=datetime(2025, 2, 10, 12, tzinfo=UTC))
    body = synthetic_rankings(WEEKS[0], 7 * 2 + 3)  # two full weeks and three days of the third
    r.add("rankings.json", json.dumps(body).encode(), "https://x.test", 200)
    r.vintage = {"kind": "api_as_of", "value": "x"}
    r.write()
    q = marts(date(2025, 2, 12), ("openrouter_apps", "openrouter_rankings"))
    s = q("SELECT * FROM or_app_share_weekly ORDER BY week_start, rank")
    assert s["week_start"].unique().to_list() == WEEKS[:2]
    week1 = sum(int(x["total_tokens"]) for x in body["data"] if x["date"] <= "2025-01-12")
    first = s.row(0, named=True)
    assert first["openrouter_tokens"] == week1 and first["top200_tokens"] == 1_000 + 2_500 + 400
    assert first["attributed_share"] == pytest.approx(3_900 / week1)
    assert first["share_of_openrouter"] == pytest.approx(2_500 / week1)  # Chat B ranks first in week 1
