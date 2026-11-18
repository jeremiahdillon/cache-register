"""Databricks AI Index source and marts 095/096 on a synthetic page (no network, no recorded data)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from cachereg.build import build
from cachereg.core.http import Response
from cachereg.core.store import list_fetches
from cachereg.core.warehouse import connect, query
from cachereg.sources.databricks_ai_index import fetch as dfetch
from cachereg.sources.databricks_ai_index import parse
from tests.conftest import write_synthetic_litellm

LABELS = ["Jul 20", "Jul 27", "Aug 3", "Aug 10"]  # Mondays of 2026; "Updated Aug 10, 2026"
UPDATED = "Aug 10, 2026"
# Synthetic shares, the same every week. Proprietary wallet shares are consistent with the synthetic LiteLLM
# prices (blended 0.8 × in + 0.2 × out): Sonnet 9 5.4, GPT 9 2.4 ($/M, from LITELLM_MID); the buckets at 5.4
# and 3.0, so P_prop = 4.26 and wallet_i = tokens_i × p_i / P_prop, rounded to 0.1.
PROP_TOKENS = [("Anthropic", "Sonnet 9", 50.0), ("Anthropic", "Older Anthropic Models", 10.0),
               ("OpenAI", "GPT 9", 30.0), ("Other proprietary", "Gemini, Grok", 10.0)]  # fmt: skip
PROP_WALLET = [("Anthropic", "Sonnet 9", 63.4), ("Anthropic", "Older Anthropic Models", 12.7),
               ("OpenAI", "GPT 9", 16.9), ("Other proprietary", "Gemini, Grok", 7.0)]  # fmt: skip
OPEN_TOKENS = [("Moonshot", "Kimi 9", 80.0), ("Other open-weight", "Other", 20.0)]
OPEN_WALLET = [("Moonshot", "Kimi 9", 80.0), ("Other open-weight", "Other", 20.0)]
SPLIT = [("Model type", "Open-weight", 25.0), ("Model type", "Proprietary", 75.0)]


def _layers(spec, n=4, bump: float = 0.0):
    out = [{"label": lab, "group": g, "tooltip": lab, "color": "#000", "values": [v] * n} for g, lab, v in spec]
    if bump:  # move `bump` points from the second layer to the first in the last week (a revision)
        out[0]["values"][-1] += bump
        out[1]["values"][-1] -= bump
    return out


def _block(title: str, props: dict) -> list:
    return [
        "$", "div", None,
        {"children": [
            ["$", "h3", None, {"className": "t", "children": title}],
            ["$", "p", None, {"className": "u", "children": ["Updated ", UPDATED]}],
            ["$", "$L30", None, props],
        ]},
    ]  # fmt: skip


def page(labels=LABELS, drop: str | None = None, prop_tokens=PROP_TOKENS, bump: float = 0.0) -> bytes:
    """A synthetic page: flight rows split over two chunks; later charts refer back to row 1's weeks."""
    ref = "$1:props:children:2:props:weeks"
    charts = [
        ("tokenShareChart", "Token Share - Proprietary",
         {"weeks": list(labels), "layers": _layers(prop_tokens, len(labels), bump)}),
        ("walletShareChart", "Wallet Share - Proprietary", {"weeks": ref, "layers": _layers(PROP_WALLET, len(labels))}),
        ("ossTokenShareChart", "Token Share - Open", {"weeks": ref, "layers": _layers(OPEN_TOKENS, len(labels))}),
        ("ossWalletShareChart", "Wallet Share - Open", {"weeks": ref, "layers": _layers(OPEN_WALLET, len(labels))}),
        ("openWeightShareChart", "Proprietary vs Open", {"weeks": ref, "layers": _layers(SPLIT, len(labels))}),
    ]  # fmt: skip
    rows = ['0:"$Sreact.fragment"']  # flight rows are compact JSON, like the page
    for i, (cid, title, props) in enumerate(charts, start=1):
        if cid != drop:
            rows.append(
                f"{i}:" + json.dumps(_block(title, props | {"canvasId": cid, "yAxisTitle": "%"}), separators=(",", ":"))
            )
    text = "\n".join(rows) + "\n"
    half = len(text) // 2
    chunks = [json.dumps(text[:half])[1:-1], json.dumps(text[half:])[1:-1]]
    scripts = "".join(f'<script>self.__next_f.push([1,"{c}"])</script>' for c in chunks)
    return f"<!DOCTYPE html><html><body>{scripts}</body></html>".encode()


@pytest.fixture
def site(data_env, monkeypatch):
    state = {"body": page()}

    def fake_get(url, params=None, headers=None, **kw):
        assert url == dfetch.URL
        return Response(url, 200, state["body"])

    monkeypatch.setattr(dfetch.http, "get", fake_get)
    return state


@pytest.fixture
def entities(synthetic_entities):
    import yaml

    f = synthetic_entities / "models.yaml"
    models = yaml.safe_load(f.read_text())["models"]
    for mid, label in [
        ("anthropic/claude-sonnet-9", "Sonnet 9"),
        ("openai/gpt-9", "GPT 9"),
        ("moonshotai/kimi-9", "Kimi 9"),
    ]:
        models[mid]["aliases"]["databricks"] = [label]
    f.write_text(yaml.safe_dump({"models": models}))
    return synthetic_entities


def fetch_at(day: date):
    raw = dfetch.fetch()
    raw.fetched_at = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    return raw.write()


def marts(as_of: date):
    build(as_of, ["databricks_ai_index", "litellm_prices"])

    def q(sql: str) -> list[dict]:
        con = connect()
        try:
            return query(con, sql).to_dicts()
        finally:
            con.close()

    return q


# --- parsing ---------------------------------------------------------------------


def test_parse_dates_weeks_and_resolves_references():
    cs = parse.charts(page().decode())
    assert set(cs) == set(parse.CHARTS)
    w = cs["walletShareChart"]  # its weeks are a reference into row 1
    assert w.weeks == [date(2026, 7, 20), date(2026, 7, 27), date(2026, 8, 3), date(2026, 8, 10)]
    assert w.updated == date(2026, 8, 10) and w.title == "Wallet Share - Proprietary"
    recs = parse.records(page().decode())
    assert len(recs) == 4 * (4 + 4 + 2 + 2 + 2)
    assert {r["segment"] for r in recs} == {"proprietary", "open_weight", "split"}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"drop": "openWeightShareChart"}, "charts missing"),
        ({"labels": ["Jul 20", "Jul 27", "Aug 4", "Aug 10"]}, "does not match"),
        ({"labels": ["Jul 21", "Jul 28", "Aug 4", "Aug 11"]}, "does not match"),  # 'Updated' dates the last label
        ({"prop_tokens": PROP_TOKENS[:3]}, "sum to 90.0"),
    ],
)
def test_parse_refuses_an_unexpected_page(kwargs, message):
    with pytest.raises(ValueError, match=message):
        parse.charts(page(**kwargs).decode())


def test_parse_refuses_a_page_without_data():
    with pytest.raises(ValueError, match="no Next.js data"):
        parse.charts("<html><body>redesigned</body></html>")


# --- fetch -----------------------------------------------------------------------


def test_fetch_stores_the_page_and_a_content_vintage(site):
    raw = dfetch.fetch()
    assert list(raw.files) == [dfetch.FILE] and raw.files[dfetch.FILE] == site["body"]
    assert raw.vintage["kind"] == "content" and len(raw.vintage["value"]) == 64
    assert raw.vintage["updated"] == "2026-08-10" and raw.vintage["window"] == ["2026-07-20", "2026-08-10"]


def test_fetch_writes_nothing_for_a_changed_page(site):
    site["body"] = page(drop="walletShareChart")
    with pytest.raises(ValueError, match="charts missing"):
        fetch_at(date(2026, 8, 17))
    assert list_fetches("databricks_ai_index") == []


# --- marts -----------------------------------------------------------------------


def test_marts_rescale_shares_to_all_models(site, entities):
    write_synthetic_litellm(datetime(2026, 8, 17, 6, tzinfo=UTC), date(2026, 8, 16))
    fetch_at(date(2026, 8, 17))
    q = marts(date(2026, 8, 31))
    tok = q("SELECT week, share_of_segment_pct, share_of_all_pct FROM dbx_vendor_share_week "
            "WHERE vendor_id = 'anthropic' AND metric = 'tokens' ORDER BY week")  # fmt: skip
    assert [r["week"] for r in tok] == [date(2026, 7, 26), date(2026, 8, 2), date(2026, 8, 9), date(2026, 8, 16)]
    assert tok[-1]["share_of_segment_pct"] == pytest.approx(60.0) and tok[-1]["share_of_all_pct"] == pytest.approx(45.0)
    price = q("SELECT segment, mean_price_usd_per_token, priced_token_pct, named_unpriced FROM dbx_segment_price_week "
              "WHERE week_start = DATE '2026-08-10' ORDER BY segment")  # fmt: skip
    assert price[1]["mean_price_usd_per_token"] * 1e6 == pytest.approx(342 / 80.3)  # Σ tok·p / Σ wallet, named
    assert price[1]["priced_token_pct"] == pytest.approx(80.0) and price[1]["named_unpriced"] is None
    assert price[0]["mean_price_usd_per_token"] * 1e6 == pytest.approx(0.98)
    spend = q("SELECT * FROM dbx_vendor_spend_week WHERE vendor_id = 'anthropic' ORDER BY week")[-1]
    p_prop = 342 / 80.3
    s_open = 100 * 25 * 0.98 / (25 * 0.98 + 75 * p_prop)
    assert spend["open_spend_pct"] == pytest.approx(s_open)
    assert spend["share_of_all_pct"] == pytest.approx(76.1 * (1 - s_open / 100))
    assert spend["share_of_all_lo_pct"] < spend["share_of_all_pct"] < spend["share_of_all_hi_pct"] < 76.1
    kimi = q(
        "SELECT price_date_stale FROM dbx_model_price_week WHERE label = 'Kimi 9' AND week_start = DATE '2026-07-20'"
    )
    assert kimi == [{"price_date_stale": False}]  # listed from LITELLM_MID (2026-07-15), before the week's Sunday


def test_marts_take_each_week_from_the_latest_fetch(site, entities):
    write_synthetic_litellm(datetime(2026, 8, 17, 6, tzinfo=UTC), date(2026, 8, 16))
    fetch_at(date(2026, 8, 17))
    site["body"] = page(bump=2.0)  # Sonnet 9 52, Older Anthropic 8: Anthropic unchanged; revision visible per model
    fetch_at(date(2026, 8, 18))
    q = marts(date(2026, 8, 31))
    rows = q("SELECT label, share_pct, fetch_id FROM dbx_layer_week WHERE week_start = DATE '2026-08-10' "
             "AND chart = 'tokenShareChart' AND label = 'Sonnet 9'")  # fmt: skip
    assert rows[0]["share_pct"] == pytest.approx(52.0) and rows[0]["fetch_id"].startswith("20260818")
    q2 = marts(date(2026, 8, 17))  # an as-of before the revision sees the first fetch
    first = q2("SELECT share_pct FROM dbx_layer_week WHERE week_start = DATE '2026-08-10' "
               "AND chart = 'tokenShareChart' AND label = 'Sonnet 9'")  # fmt: skip
    assert first[0]["share_pct"] == pytest.approx(50.0)
