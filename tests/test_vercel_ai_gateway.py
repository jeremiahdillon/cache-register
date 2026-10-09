"""Vercel AI Gateway source and mart 090 on synthetic data (no network, no recorded data)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from cachereg.build import build
from cachereg.core.http import Response
from cachereg.core.store import list_fetches
from cachereg.core.warehouse import connect, query
from cachereg.sources.vercel_ai_gateway import fetch as vf

TODAY = date(2025, 11, 3)  # first run: labs 2025-10-01..11-02, models months 2025-10 and 2025-11 (to 11-02)
LABS = {"anthropic": 40.0, "openai": 30.0, "spacexai": 20.0, "newlab": 10.0}  # tokens; other metrics rotate
MODELS = {"Claude Opus 5.5": 30.0, "GPT-6 Luna": 20.0}


def lab_rows(day: date, scale: float = 1.0) -> list[dict]:
    rows = []
    for i, metric in enumerate(("tokens", "spend", "requests")):
        names = list(LABS)
        values = list(LABS.values())[i:] + list(LABS.values())[:i]  # each metric sums to 100
        if day.day % 2 == 0 and metric == "tokens":  # even days: anthropic 20, openai 50 (mean 30 / 40)
            values = [20.0, 50.0, 20.0, 10.0]
        rows += [
            {"date": day.isoformat(), "group": "lab", "name": n, "metric": metric, "modality": "text",
             "share_percent": v * scale}
            for n, v in zip(names, values, strict=True)
        ]  # fmt: skip
    return rows


def model_rows(day: date, other: bool = True) -> list[dict]:
    named = dict(MODELS) | ({"Other": 50.0} if other else {})
    return [
        {"date": day.isoformat(), "group": "model", "name": n, "metric": m, "modality": "text", "share_percent": v}
        for m in ("tokens", "spend", "requests")
        for n, v in named.items()
    ]


def body(dataset: str, start: str, end: str, **override) -> dict:
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    days = [s + timedelta(days=i) for i in range((e - s).days + 1)]
    rows = [r for d in days for r in (lab_rows(d) if dataset == "labs" else model_rows(d))]
    return {
        "dataset": dataset, "modality": "text", "from": start, "to": end, "earliest_available_date": "2025-10-01",
        "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "rows": rows,
    } | override  # fmt: skip


@pytest.fixture
def api(data_env, monkeypatch):
    """Fake export endpoint; `state["mutate"]` can rewrite a body before it is served."""
    state = {"seen": [], "mutate": None}

    def fake_get(url, params=None, headers=None, **kw):
        assert url == vf.URL and params["modality"] == "text" and params["format"] == "json"
        state["seen"].append(dict(params))
        b = body(params["dataset"], params["from"], params["to"])
        if state["mutate"]:
            state["mutate"](b, params)
        return Response(url + "?synthetic", 200, json.dumps(b).encode())

    monkeypatch.setattr(vf.http, "get", fake_get)
    return state


def fetch_at(today: date, full: bool = False):
    raw = vf.fetch(full=full, today=today)
    raw.fetched_at = datetime.combine(today, datetime.min.time(), tzinfo=UTC) + timedelta(hours=6)
    return raw.write()


@pytest.fixture
def entities(synthetic_entities):
    """The synthetic models.yaml plus Vercel display names for two models."""
    import yaml

    f = synthetic_entities / "models.yaml"
    models = yaml.safe_load(f.read_text())["models"]
    models["anthropic/claude-opus-5.5"] = {"aliases": {"vercel": ["Claude Opus 5.5"]}}
    models["openai/gpt-6-luna"] = {"aliases": {"vercel": ["GPT-6 Luna"]}}
    f.write_text(yaml.safe_dump({"models": models}))
    return synthetic_entities


def marts(as_of: date):
    build(as_of, ["vercel_ai_gateway"])

    def q(sql: str) -> list[dict]:
        con = connect()
        try:
            return query(con, sql).to_dicts()
        finally:
            con.close()

    return q


# --- plan and fetch -----------------------------------------------------------


def test_month_windows_are_clipped_calendar_months():
    assert vf.month_windows(date(2025, 10, 15), date(2025, 12, 2)) == [
        (date(2025, 10, 15), date(2025, 10, 31)),
        (date(2025, 11, 1), date(2025, 11, 30)),
        (date(2025, 12, 1), date(2025, 12, 2)),
    ]


def test_first_run_asks_for_everything_then_the_trailing_window(api):
    fetch_at(TODAY)
    assert [(p["dataset"], p["from"], p["to"]) for p in api["seen"]] == [
        ("labs", "2025-10-01", "2025-11-02"),
        ("models", "2025-10-01", "2025-10-31"),
        ("models", "2025-11-01", "2025-11-02"),
    ]
    api["seen"].clear()
    fetch_at(date(2025, 12, 20))
    assert [(p["dataset"], p["from"], p["to"]) for p in api["seen"]] == [
        ("labs", "2025-11-15", "2025-12-19"),  # 35 days ending yesterday
        ("models", "2025-11-01", "2025-11-30"),  # the previous and the current month
        ("models", "2025-12-01", "2025-12-19"),
    ]
    api["seen"].clear()
    fetch_at(date(2025, 12, 21), full=True)
    assert api["seen"][0]["from"] == "2025-10-01" and len(api["seen"]) == 4


def test_vintage_records_content_window_and_earliest_day(api):
    raw = vf.fetch(today=TODAY)
    assert raw.vintage["kind"] == "content" and len(raw.vintage["value"]) == 64
    assert raw.vintage["window"] == ["2025-10-01", "2025-11-02"]
    assert raw.vintage["earliest_available_date"] == "2025-10-01"


def test_nothing_before_the_first_day():
    with pytest.raises(ValueError, match="no complete day"):
        vf.plan(date(2025, 10, 1), full=True)


def _set(key, value, dataset="labs"):
    def mutate(b, params):
        if params["dataset"] == dataset:
            if key in b:
                b[key] = value
            else:
                b["rows"][0][key] = value

    return mutate


def _lab_sum_97(b, params):
    if params["dataset"] == "labs":
        b["rows"][0]["share_percent"] -= 3


def _outside(b, params):
    b["rows"][0]["date"] = "2025-09-30"


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (_set("license", "proprietary"), "licence"),
        (_set("metric", "latency"), "unknown metric"),
        (_set("share_percent", 101.0), "outside 0–100"),
        (_set("share_percent", -1.0), "outside 0–100"),
        (_set("share_percent", "12"), "not a number"),
        (_lab_sum_97, "do not sum to 100"),
        (_outside, "outside the requested window"),
        (_set("dataset", "apps"), "answered for"),
        (_set("group", "provider", "models"), "unknown group"),
    ],
)
def test_a_bad_body_is_refused_and_nothing_written(api, mutate, match):
    api["mutate"] = mutate
    with pytest.raises(ValueError, match=match):
        fetch_at(TODAY)
    assert list_fetches("vercel_ai_gateway") == []


def test_models_days_need_not_sum_to_100(api):
    api["mutate"] = lambda b, p: (
        p["dataset"] == "models" and b.update(rows=[r for r in b["rows"] if r["name"] != "Other"])
    )
    fetch_at(TODAY)  # no `Other` row (as before June 2026): accepted


# --- stage and marts ------------------------------------------------------------


def test_stage_flags_other_and_computes_the_unlisted_share(api, entities):
    fetch_at(TODAY)
    q = marts(date(2025, 11, 2))
    rows = q("SELECT model_name, model_id, is_other, share_pct, unlisted_pct FROM vercel_model_share "
             "WHERE date = DATE '2025-10-05' AND metric = 'tokens' ORDER BY model_name")  # fmt: skip
    assert rows == [
        {"model_name": "Claude Opus 5.5", "model_id": "anthropic/claude-opus-5.5", "is_other": False,
         "share_pct": 30.0, "unlisted_pct": 50.0},
        {"model_name": "GPT-6 Luna", "model_id": "openai/gpt-6-luna", "is_other": False,
         "share_pct": 20.0, "unlisted_pct": 50.0},
        {"model_name": "Other", "model_id": None, "is_other": True, "share_pct": 50.0, "unlisted_pct": 50.0},
    ]  # fmt: skip


def test_monthly_share_is_the_mean_of_daily_shares_and_labels_map(api, entities):
    fetch_at(TODAY)
    q = marts(date(2025, 11, 2))
    oct_ = {
        r["vendor_id"]: r
        for r in q(
            "SELECT * FROM vercel_lab_share_period WHERE period = 'month' "
            "AND period_start = DATE '2025-10-01' AND metric = 'tokens'"
        )  # fmt: skip
    }
    # 31 October days: 16 odd (anthropic 40) and 15 even (anthropic 20): mean of days, not volumes
    assert oct_["anthropic"]["mean_share_pct"] == pytest.approx((16 * 40 + 15 * 20) / 31)
    assert oct_["anthropic"]["days"] == 31 and oct_["anthropic"]["period_days"] == 31
    assert oct_["xai"]["mean_share_pct"] == pytest.approx(20.0)  # spacexai → xai
    assert oct_["_unmapped"]["mean_share_pct"] == pytest.approx(10.0)  # kept, never dropped
    nov = q("SELECT days, period_days FROM vercel_lab_share_period WHERE period = 'month' "
            "AND period_start = DATE '2025-11-01' AND vendor_id = 'anthropic' AND metric = 'tokens'")  # fmt: skip
    assert nov == [{"days": 2, "period_days": 30}]  # a partial month says so
    cov = {r["label"]: r for r in q("SELECT * FROM vercel_label_coverage WHERE kind = 'lab'")}
    assert cov["newlab"]["mapped"] is False and cov["newlab"]["peak_tokens_pct"] == 10.0
    assert cov["spacexai"]["mapped_to"] == "xai"


def test_a_lab_missing_on_a_day_counts_as_zero(api, entities):
    def drop(b, params):
        if params["dataset"] == "labs":  # newlab absent on 2025-10-01: openai takes its share that day
            for r in b["rows"]:
                if r["date"] == "2025-10-01" and r["name"] == "openai":
                    r["share_percent"] += next(
                        x["share_percent"] for x in b["rows"]
                        if x["date"] == r["date"] and x["metric"] == r["metric"] and x["name"] == "newlab"
                    )  # fmt: skip
            b["rows"] = [r for r in b["rows"] if not (r["date"] == "2025-10-01" and r["name"] == "newlab")]

    api["mutate"] = drop
    fetch_at(TODAY)
    q = marts(date(2025, 11, 2))
    got = q("SELECT mean_share_pct FROM vercel_lab_share_period WHERE period = 'month' "
            "AND period_start = DATE '2025-10-01' AND vendor_id = '_unmapped' AND metric = 'tokens'")  # fmt: skip
    assert got[0]["mean_share_pct"] == pytest.approx(10.0 * 30 / 31)


def test_the_newest_fetch_on_or_before_the_cutoff_wins_per_day(api, entities):
    fetch_at(TODAY)
    api["mutate"] = lambda b, p: (
        p["dataset"] == "labs"
        and b.update(
            rows=[r | {"share_percent": 25.0} for r in b["rows"]]  # a revision: four labs at 25
        )
    )
    fetch_at(date(2025, 11, 10))
    newest = marts(date(2025, 11, 10))
    sql = "SELECT share_pct FROM vercel_lab_share WHERE date = DATE '{}' AND lab = 'anthropic' AND metric = 'tokens'"
    day, old_day = sql.format("2025-11-01"), sql.format("2025-10-02")
    assert newest(day)[0]["share_pct"] == 25.0
    assert newest(old_day)[0]["share_pct"] == 20.0  # outside the refresh window: first fetch
    older = marts(date(2025, 11, 2))
    assert older(day)[0]["share_pct"] == 40.0  # the cutoff for 11-02 is the first fetch


# --- mart 091: the lenses side by side -----------------------------------------------------------


GAP_DAY, GAP_SLUG = "2026-07-10", "moonshotai/kimi-9"  # Kimi drops out of the OpenRouter top list that day


def test_gateway_lenses_are_rows_and_reproduce_openrouter_estimated_spend(data_env, entities):
    import polars as pl

    from cachereg.core.store import RawFetch
    from tests.conftest import synthetic_models, synthetic_rankings, write_synthetic_litellm
    from tests.test_ramp_ai_index import import_all

    fetched = datetime(2026, 8, 31, 12, tzinfo=UTC)
    rankings = synthetic_rankings(date(2026, 6, 1), 91)
    rankings["data"] = [r for r in rankings["data"] if (r["date"], r["model_permaslug"]) != (GAP_DAY, GAP_SLUG)]
    for sid, name, payload, vintage in (
        ("openrouter_rankings", "rankings.json", rankings, {"kind": "api_as_of", "value": "2026-08-31T02:00:00Z"}),
        ("openrouter_models", "models.json", synthetic_models(), {"kind": "snapshot", "value": "2026-08-31"}),
    ):
        r = RawFetch(sid, "1", fetched_at=fetched)
        r.add(name, json.dumps(payload).encode(), "https://example.test", 200)
        r.vintage = vintage
        r.write()
    write_synthetic_litellm(fetched, date(2026, 8, 30))
    v = RawFetch("vercel_ai_gateway", "1", fetched_at=datetime(2026, 8, 31, 12, tzinfo=UTC))
    v.add("labs.json", json.dumps(body("labs", "2026-07-01", "2026-07-31")).encode(), "https://example.test", 200)
    v.write()
    import_all()  # Ramp: Jan–Mar 2026, OpenAI, Anthropic and an unmapped "Acme Labs"
    build(date(2026, 8, 30), ["vercel_ai_gateway", "openrouter_rankings", "litellm_prices", "ramp_ai_index"])
    con = connect()
    try:
        lenses = query(con, "SELECT * FROM gateway_lenses")
        daily = query(con, "SELECT date, vendor_id, est_spend_usd, total_tokens FROM or_model_daily")
    finally:
        con.close()
    july = lenses.filter(pl.col("month") == date(2026, 7, 1))
    assert set(july["lens"]) == {
        "vercel_tokens", "vercel_spend", "openrouter_tokens", "openrouter_tokens_volume_weighted",
        "openrouter_est_spend",
    }  # fmt: skip
    assert set(lenses["lens"]) >= {"ramp_paying"}
    # Shares recomputed here from the daily rows: the sum of a vendor's daily shares over ALL 31 July days
    # (a day it is absent counts 0), so Moonshot's gap day pulls its mean down.
    d = daily.with_columns(pl.col("est_spend_usd").fill_null(0)).filter(pl.col("date").dt.month() == 7)
    assert d["date"].n_unique() == 31
    per_day = d.group_by("date", "vendor_id").agg(pl.col("est_spend_usd").sum(), pl.col("total_tokens").sum())
    totals = d.group_by("date").agg(
        pl.col("est_spend_usd").sum().alias("spend"), pl.col("total_tokens").sum().alias("tok")
    )
    per_day = per_day.join(totals, on="date")

    def expected(vendor: str, col: str, total: str) -> float:
        rows = per_day.filter(pl.col("vendor_id") == vendor)
        return (100 * rows[col] / rows[total]).sum() / 31

    def got(lens: str, vendor: str) -> float:
        return july.filter((pl.col("lens") == lens) & (pl.col("vendor_id") == vendor))["value_pct"][0]

    assert per_day.filter(pl.col("vendor_id") == "moonshot").height == 30  # absent on the gap day
    for vendor in ("anthropic", "moonshot"):
        assert got("openrouter_est_spend", vendor) == pytest.approx(expected(vendor, "est_spend_usd", "spend"))
        assert got("openrouter_tokens", vendor) == pytest.approx(expected(vendor, "total_tokens", "tok"))
    m = per_day.filter(pl.col("vendor_id") == "moonshot")
    assert got("openrouter_tokens_volume_weighted", "moonshot") == pytest.approx(
        100 * m["total_tokens"].sum() / d["total_tokens"].sum()
    )
    # coverage: mean daily share of non-free tokens that are priced (the x-ai model and `other` are unpriced)
    paid = query_daily_coverage()
    assert july.filter(pl.col("lens") == "openrouter_est_spend")["coverage_pct"].unique().to_list() == [
        pytest.approx(paid)
    ]
    for lens in ("openrouter_tokens", "openrouter_tokens_volume_weighted", "openrouter_est_spend", "vercel_tokens"):
        assert july.filter(pl.col("lens") == lens)["value_pct"].sum() == pytest.approx(100.0)
    # Anthropic's OpenRouter share shrinks while volumes grow: the two weightings differ.
    a = july.filter(pl.col("vendor_id") == "anthropic")
    mean, weighted = (
        a.filter(pl.col("lens") == x)["value_pct"][0]
        for x in ("openrouter_tokens", "openrouter_tokens_volume_weighted")
    )
    assert mean != pytest.approx(weighted)
    # Vercel: xAI via `spacexai`; ranks skip ids that are not vendors.
    vt = july.filter(pl.col("lens") == "vercel_tokens")
    assert vt.filter(pl.col("vendor_id") == "xai")["value_pct"][0] == pytest.approx(20.0)
    assert vt.filter(pl.col("vendor_id") == "_unmapped")["vendor_rank"][0] is None
    # Ramp: adoption rows, unmapped labels kept with their label.
    ramp = lenses.filter((pl.col("lens") == "ramp_paying") & (pl.col("month") == date(2026, 3, 1)))
    assert set(zip(ramp["vendor_id"], ramp["label"], strict=True)) == {
        ("openai", "OpenAI"), ("anthropic", "Anthropic"), ("_unmapped", "Acme Labs")}  # fmt: skip
    assert lenses.group_by("month", "lens", "vendor_id", "label").len()["len"].max() == 1


def query_daily_coverage() -> float:
    """Mean over July days of priced non-free tokens / non-free tokens, from or_model_daily."""
    con = connect()
    try:
        return query(
            con,
            "SELECT 100 * avg(p) AS c FROM (SELECT date, sum(total_tokens) FILTER (WHERE NOT is_free AND price_matched)"
            " / sum(total_tokens) FILTER (WHERE NOT is_free) AS p FROM or_model_daily"
            " WHERE month(date) = 7 GROUP BY date)",
        )["c"][0]
    finally:
        con.close()
