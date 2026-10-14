"""yahoo_prices and finra_trace sources and marts 100/101 on synthetic data (no network, no recorded data)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from cachereg.build import build
from cachereg.core.http import Response
from cachereg.core.warehouse import connect, query
from cachereg.sources.finra_trace import fetch as ff
from cachereg.sources.yahoo_prices import fetch as yf

ET = -4 * 3600  # exchange offset in the synthetic bodies (EDT)
DAYS = [date(2026, 3, 2) + timedelta(days=i) for i in range(5)]  # Mon–Fri


def _open_ts(d: date) -> int:  # 09:30 exchange time
    return int(datetime(d.year, d.month, d.day, 13, 30, tzinfo=UTC).timestamp())


def yahoo_body(ticker: str, closes: list[float | None], session_day: date) -> dict:
    end = int(datetime(session_day.year, session_day.month, session_day.day, 20, 0, tzinfo=UTC).timestamp())
    n = len(closes)
    return {"chart": {"result": [{
        "meta": {"symbol": ticker, "currency": "USD", "gmtoffset": ET,
                 "currentTradingPeriod": {"regular": {"start": end - 23400, "end": end}}},
        "timestamp": [_open_ts(d) for d in DAYS[:n]],
        "indicators": {"quote": [{"open": closes, "high": closes, "low": closes, "close": closes,
                                  "volume": [1000] * n}], "adjclose": [{"adjclose": closes}]},
    }], "error": None}}  # fmt: skip


def finra_body(cusip: str, rows: list[tuple[str, float, float | None]]) -> dict:
    data = [{"cusip": cusip, "issueSymbolIdentifier": "CRWV0000001", "tradeDate": d, "lastSalePrice": p,
             "lastSaleYield": y} for d, p, y in rows]  # fmt: skip
    return {"status": "success", "returnBody": {"statusCode": 200, "data": json.dumps(data)}}


def write_at(raw, when: datetime):
    raw.fetched_at = when
    return raw.write()


def q(sql: str) -> list[dict]:
    con = connect()
    try:
        return query(con, sql).to_dicts()
    finally:
        con.close()


@pytest.fixture
def yahoo(data_env, monkeypatch):
    state = {"closes": [10.0, 11.0, 12.0, 13.0, 14.0], "symbol": "CRWV"}

    def fake_get(url, params=None, headers=None, **kw):
        assert url == yf.URL.format(ticker="CRWV") and params["interval"] == "1d"
        body = yahoo_body(state["symbol"], state["closes"], DAYS[len(state["closes"]) - 1])
        return Response(url + "?synthetic", 200, json.dumps(body).encode())

    monkeypatch.setattr(yf.http, "get", fake_get)
    monkeypatch.setattr(yf, "TICKERS", ["CRWV"])
    return state


@pytest.fixture
def finra(data_env, monkeypatch):
    state = {"seen": [], "rows": {}}
    monkeypatch.setattr(ff, "_session", lambda: (None, "tok"))

    def fake_open(opener, req, retries=3):
        assert req.headers["X-xsrf-token"] == "tok"
        cusip = json.loads(req.data)["orFilters"][0]["compareFilters"][0]["fieldValue"]
        state["seen"].append(cusip)
        return 200, json.dumps(finra_body(cusip, state["rows"].get(cusip, [("2026-03-02", 100.0, 9.0)]))).encode()

    monkeypatch.setattr(ff, "_open", fake_open)
    return state


def test_yahoo_intraday_bar_is_not_final_until_the_session_closes(yahoo):
    day = DAYS[-1]
    close = datetime(day.year, day.month, day.day, 20, 0, tzinfo=UTC)
    write_at(yf.fetch(), close - timedelta(hours=2))  # during the last session
    build(day, ["yahoo_prices"])
    rows = q("SELECT date, close FROM stock_daily ORDER BY date")
    assert [r["date"] for r in rows] == DAYS[:-1]  # the intraday bar is dropped

    yahoo["closes"] = [10.0, 11.0, 12.0, 13.0, 15.0]
    write_at(yf.fetch(), close + timedelta(minutes=30))
    build(day, ["yahoo_prices"])
    rows = q("SELECT date, close FROM stock_daily ORDER BY date")
    assert len(rows) == 5 and rows[-1]["close"] == 15.0  # latest fetch, final bar


def test_yahoo_refuses_a_body_for_another_symbol(yahoo):
    yahoo["symbol"] = "NVDA"
    with pytest.raises(ValueError, match="answered for"):
        yf.fetch()


def test_finra_fetches_each_bond_and_the_mart_joins_terms(finra):
    finra["rows"]["21873SAG3"] = [("2026-03-02", 101.0, None), ("2026-03-03", 99.0, 9.9), ("2026-03-04", 98.0, 10.1)]
    write_at(ff.fetch(today=date(2026, 3, 4)), datetime(2026, 3, 4, 23, tzinfo=UTC))
    assert finra["seen"] == list(ff.BONDS)
    build(date(2026, 3, 4), ["finra_trace"])
    rows = q(
        "SELECT date, coupon_pct, maturity, last_price, last_yield_pct FROM bond_eod"
        " WHERE cusip = '21873SAG3' ORDER BY date"
    )
    assert [r["last_yield_pct"] for r in rows] == [None, 9.9, 10.1]  # a price without a yield is kept
    assert rows[0]["coupon_pct"] == 9.75 and rows[0]["maturity"] == date(2031, 10, 1)


def test_finra_refuses_an_empty_answer(finra):
    finra["rows"]["21873SAB4"] = [("2026-03-02", 100.0, 9.0)]
    finra["rows"]["21873SAC2"] = []
    with pytest.raises(ValueError, match="no end-of-day rows"):
        ff.fetch(today=date(2026, 3, 4))
