"""Mart 111 (balance sheet) on synthetic SEC company facts: tag options, completeness, filing dates."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from cachereg.build import build
from cachereg.core.warehouse import connect, query
from tests.test_sec_edgar import fact, facts_doc, tickers, write_fetch

CASH = "CashAndCashEquivalentsAtCarryingValue"


def alpha() -> dict:
    """Reports cash and short-term investments as one tag; debt as current + non-current, restated once."""
    return facts_doc(
        1,
        {
            "CashCashEquivalentsAndShortTermInvestments": [fact(None, "2026-06-30", 100, "2026-07-25")],
            CASH: [fact(None, "2026-06-30", 30, "2026-07-25")],
            "LongTermDebtNoncurrent": [
                fact(None, "2026-06-30", 40, "2026-07-25"),
                fact(None, "2026-06-30", 45, "2026-10-01"),  # restated later
            ],
            "LongTermDebtCurrent": [fact(None, "2026-06-30", 5, "2026-07-25")],
            "OperatingLeaseLiability": [fact(None, "2026-06-30", 7, "2026-07-25")],
        },
    )


def beta() -> dict:
    """Cash plus marketable securities; total debt as one tag; a later date with cash only."""
    return facts_doc(
        2,
        {
            CASH: [fact(None, "2026-06-30", 4, "2026-07-30"), fact(None, "2026-09-30", 6, "2026-10-30")],
            "MarketableSecuritiesCurrent": [fact(None, "2026-06-30", 1, "2026-07-30")],
            "LongTermDebt": [fact(None, "2026-06-30", 25, "2026-07-30")],
            "DebtInstrumentCarryingAmount": [fact(None, "2026-06-30", 26, "2026-07-30")],
            "PaymentsToAcquirePropertyPlantAndEquipment": [fact("2026-04-01", "2026-06-30", 3, "2026-07-30")],
        },
    )


@pytest.fixture
def raw(data_env, tmp_path, monkeypatch, synthetic_entities):
    tickers(tmp_path, monkeypatch)
    write_fetch({"0000000001": alpha(), "0000000002": beta()}, datetime(2026, 11, 1, 12, tzinfo=UTC))
    return data_env


def latest(as_of: date) -> dict[str, dict]:
    build(as_of, ["sec_edgar"])
    con = connect()
    try:
        return {r["ticker"]: r for r in query(con, "SELECT * FROM balance_sheet_latest").to_dicts()}
    finally:
        con.close()


def test_preferred_tags_and_complete_options(raw):
    got = latest(date(2026, 11, 15))
    a, b = got["AAA"], got["BBB"]
    assert (a["liquidity_usd"], a["debt_usd"], a["operating_lease_liability_usd"]) == (100, 50, 7)
    assert a["debt_tags"] == "LongTermDebtCurrent + LongTermDebtNoncurrent"
    assert (b["liquidity_usd"], b["debt_usd"]) == (5, 25)  # cash + marketable; LongTermDebt before DebtInstrument…
    assert b["period_end"] == date(2026, 6, 30)  # no debt at 2026-09-30: the latest date with both


def test_values_as_filed_on_as_of(raw):
    assert latest(date(2026, 9, 1))["AAA"]["debt_usd"] == 45  # the restatement (filed 2026-10-01) not yet known
    assert latest(date(2026, 11, 15))["AAA"]["debt_usd"] == 50
    assert set(latest(date(2026, 7, 27))) == {"AAA"}  # Beta's 10-Q is filed on 2026-07-30
