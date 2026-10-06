"""SEC EDGAR source and capex marts on synthetic company facts (no network, no recorded filings)."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, date, datetime

import pytest
import yaml

from cachereg.build import build
from cachereg.core.http import Response
from cachereg.core.settings import MissingSecretError
from cachereg.core.store import RawFetch
from cachereg.core.warehouse import connect, query
from cachereg.sources.sec_edgar import companies
from cachereg.sources.sec_edgar import fetch as ef
from cachereg.sources.sec_edgar import stage as es

PPE = "PaymentsToAcquirePropertyPlantAndEquipment"
PRODUCTIVE = "PaymentsToAcquireProductiveAssets"
LEASE = "RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability"
AGENT = "Synthetic Tester tester@example.test"


def fact(start, end, val, filed, form="10-Q", accn=None):
    f = {"end": end, "val": val, "accn": accn or f"0000000000-{filed[2:4]}-{filed[5:7]}{filed[8:]}", "fy": 2026}
    f |= {"fp": "Q", "form": form, "filed": filed}
    return f | ({"start": start} if start else {})


def facts_doc(cik, tags: dict[str, list[dict]], name="Synthetic Co") -> dict:
    return {
        "cik": cik,
        "entityName": name,
        "facts": {"us-gaap": {t: {"label": t, "units": {"USD": fs}} for t, fs in tags.items()}},
    }


def calendar_company() -> dict:
    """Calendar fiscal year; YTD facts only for 2025, a reported Q1 2026, a restated 6M."""
    return facts_doc(
        1,
        {
            PPE: [
                fact("2025-01-01", "2025-03-31", 10, "2025-04-25"),
                fact("2025-01-01", "2025-06-30", 22, "2025-07-25"),
                fact("2025-01-01", "2025-06-30", 24, "2026-07-24"),  # restated a year later
                fact("2025-01-01", "2025-09-30", 36, "2025-10-24"),
                fact("2025-01-01", "2025-12-31", 52, "2026-02-01", form="10-K"),
                fact("2025-01-01", "2025-12-31", 99, "2026-01-28", form="8-K"),  # earnings release: ignored
                fact("2026-01-01", "2026-03-31", 20, "2026-04-24"),
                fact(None, "2026-03-31", 500, "2026-04-24"),  # instant: not a flow
            ],
            LEASE: [fact("2026-01-01", "2026-03-31", 3, "2026-04-24")],
        },
    )


def offset_company() -> dict:
    """Fiscal year ending in late January (52/53 weeks); tag switch to ProductiveAssets in FY2026."""
    return facts_doc(
        2,
        {
            PPE: [
                fact("2024-01-29", "2024-04-28", 1, "2024-05-20"),
                fact("2024-01-29", "2025-01-26", 4, "2025-02-20", form="10-K"),
                # an older tag still present for a newer period: the preferred tag wins
                fact("2025-01-27", "2025-04-27", 50, "2025-05-20"),
            ],
            PRODUCTIVE: [
                fact("2025-01-27", "2025-04-27", 5, "2025-05-20"),
                fact("2025-01-27", "2025-07-27", 11, "2025-08-20"),
            ],
        },
    )


def tickers(tmp_path, monkeypatch, entries=None):
    entries = entries or {
        "AAA": {"cik": 1, "name": "Alpha", "group": "hyperscaler"},
        "BBB": {"cik": "0000000002", "name": "Beta", "group": "hyperscaler", "vendor": "nvidia"},
    }
    f = tmp_path / "tickers.yaml"
    f.write_text(yaml.safe_dump({"companies": entries}))
    monkeypatch.setattr(companies, "TICKERS_FILE", f)
    return f


def write_fetch(docs: dict[str, dict], fetched: datetime, gz: bool = True) -> None:
    r = RawFetch("sec_edgar", "1", fetched_at=fetched)
    for cik, doc in docs.items():
        body = json.dumps(doc).encode()
        body = gzip.compress(body) if gz else body
        r.add(ef.file_name(cik, body), body, "https://example.test", 200)
    r.vintage = {"kind": "edgar_filed", "value": "x", "window": ["2024-01-01", fetched.date().isoformat()]}
    r.write()


@pytest.fixture
def edgar_raw(data_env, tmp_path, monkeypatch, synthetic_entities):
    tickers(tmp_path, monkeypatch)
    docs = {"0000000001": calendar_company(), "0000000002": offset_company()}
    write_fetch(docs, datetime(2026, 9, 1, 12, tzinfo=UTC))
    return data_env


def marts(as_of: date):
    build(as_of, ["sec_edgar"])
    con = connect()
    return con, lambda sql: query(con, sql)


# --- fetch -------------------------------------------------------------------


def test_fetch_sends_the_user_agent_and_stores_responses_as_served(data_env, tmp_path, monkeypatch):
    tickers(tmp_path, monkeypatch)
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", AGENT)
    monkeypatch.setattr(ef, "PAUSE", 0)
    seen = []

    def fake_get(url, params=None, headers=None, **kw):
        seen.append((url, headers))
        cik = int(url.split("CIK")[1][:10])
        body = json.dumps(calendar_company() | {"cik": cik}).encode()
        return Response(url, 200, gzip.compress(body) if cik == 1 else body)

    monkeypatch.setattr(ef.http, "get", fake_get)
    raw = ef.fetch(today=date(2026, 9, 2))
    assert [u for u, _ in seen] == [ef.URL.format(cik="0000000001"), ef.URL.format(cik="0000000002")]
    assert all(h["User-Agent"] == AGENT and h["Accept-Encoding"] == "gzip" for _, h in seen)
    assert sorted(raw.files) == ["companyfacts_CIK0000000001.json.gz", "companyfacts_CIK0000000002.json"]
    assert raw.vintage["kind"] == "edgar_filed"
    assert raw.vintage["date"] == "2026-07-24" and raw.vintage["window"] == ["2025-04-25", "2026-09-01"]
    manifest = raw.write().joinpath("manifest.json").read_text()
    assert AGENT not in manifest


@pytest.mark.parametrize(
    ("body", "match"),
    [
        (b"<html>blocked</html>", "Expecting value"),
        (json.dumps({"cik": 1}).encode(), "facts"),
        (json.dumps(facts_doc(7, {})).encode(), "CIK"),
    ],
)
def test_fetch_refuses_bad_responses(data_env, tmp_path, monkeypatch, body, match):
    tickers(tmp_path, monkeypatch, {"AAA": {"cik": 1, "name": "Alpha", "group": "hyperscaler"}})
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", AGENT)
    monkeypatch.setattr(ef.http, "get", lambda url, **kw: Response(url, 200, body))
    with pytest.raises(ValueError, match=match):
        ef.fetch()


def test_fetch_needs_the_user_agent(data_env, tmp_path, monkeypatch):
    tickers(tmp_path, monkeypatch)
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    monkeypatch.setenv("CACHEREG_SECRETS_FILE", str(tmp_path / "none.env"))
    monkeypatch.setattr("cachereg.core.settings.REPO_ROOT", tmp_path)
    with pytest.raises(MissingSecretError):
        ef.fetch()


def test_tickers_validation(tmp_path, monkeypatch):
    tickers(tmp_path, monkeypatch, {"A": {"cik": 1, "name": "A", "group": "bank"}})
    with pytest.raises(ValueError, match="group"):
        companies.load_companies()
    tickers(
        tmp_path,
        monkeypatch,
        {"A": {"cik": 1, "name": "A", "group": "neocloud"}, "B": {"cik": "1", "name": "B", "group": "neocloud"}},
    )
    with pytest.raises(ValueError, match="twice"):
        companies.load_companies()


# --- stage -------------------------------------------------------------------


def test_stage_reads_the_newest_fetch_per_company(edgar_raw):
    newer = calendar_company()
    newer["facts"]["us-gaap"][PPE]["units"]["USD"].append(fact("2026-01-01", "2026-06-30", 41, "2026-08-01"))
    write_fetch({"0000000001": newer}, datetime(2026, 9, 8, 12, tzinfo=UTC), gz=False)
    out = es.stage()
    facts, comps = out["facts"], out["companies"]
    assert set(facts["cik"]) == {"0000000001", "0000000002"}
    a = facts.filter(facts["cik"] == "0000000001")
    assert a["fetch_id"].unique().to_list() == ["20260908T120000Z"]
    assert a.filter(a["period_end"] == date(2026, 6, 30)).height == 1
    assert a.filter(a["period_start"].is_null()).height == 1  # the instant fact
    b = facts.filter(facts["cik"] == "0000000002")
    assert b["fetch_id"].unique().to_list() == ["20260901T120000Z"]
    assert comps.sort("cik")["ticker"].to_list() == ["AAA", "BBB"]
    assert comps.sort("cik")["vendor_id"].to_list() == [None, "nvidia"]
    assert out["_rejected_rows"]["rejected"][0] == 0


def test_stage_counts_unparsable_facts_and_needs_every_company(edgar_raw, tmp_path, monkeypatch):
    bad = calendar_company()
    bad["facts"]["us-gaap"][PPE]["units"]["USD"] += [fact("2025-01-01", "2025-03-31", None, "2025-04-25")]
    bad["facts"]["us-gaap"][PPE]["units"]["USD"] += [fact("2025-01-01", "not a date", 1, "2025-04-25")]
    write_fetch({"0000000001": bad}, datetime(2026, 9, 8, 12, tzinfo=UTC))
    assert es.stage()["_rejected_rows"]["rejected"][0] == 2
    tickers(tmp_path, monkeypatch, {"ZZZ": {"cik": 9, "name": "Z", "group": "supplier"}})
    with pytest.raises(ValueError, match="no stored facts for ZZZ"):
        es.stage()


# --- marts -------------------------------------------------------------------


def _quarters(q, cik):
    rows = q(
        f"SELECT period_start, period_end, cal_quarter, value_usd, method, tag FROM edgar_quarterly "  # noqa: S608
        f"WHERE cik = '{cik}' AND measure = 'capex' ORDER BY period_end"
    )
    return rows.rows()


def test_quarters_from_year_to_date_facts(edgar_raw):
    _, q = marts(date(2026, 9, 1))
    rows = _quarters(q, "0000000001")
    assert [(r[0], r[1], r[3], r[4]) for r in rows] == [
        (date(2025, 1, 1), date(2025, 3, 31), 10, "reported"),
        (date(2025, 4, 1), date(2025, 6, 30), 14, "ytd_difference"),  # restated 6M: 24 − 10
        (date(2025, 7, 1), date(2025, 9, 30), 12, "ytd_difference"),  # 36 − 24
        (date(2025, 10, 1), date(2025, 12, 31), 16, "ytd_difference"),  # Q4 = FY − 9M (8-K ignored)
        (date(2026, 1, 1), date(2026, 3, 31), 20, "reported"),
    ]


def test_restatements_count_from_their_filing_date(edgar_raw):
    _, q = marts(date(2026, 3, 1))  # before the restatement and before Q1 2026 was filed
    rows = _quarters(q, "0000000001")
    assert [r[3] for r in rows] == [10, 12, 14, 16]
    assert q("SELECT max(filed) AS f FROM edgar_quarterly")["f"][0] <= date(2026, 3, 1)


def test_offset_fiscal_years_tag_precedence_and_calendar_quarters(edgar_raw):
    _, q = marts(date(2026, 9, 1))
    rows = _quarters(q, "0000000002")
    assert [(r[1], r[2], r[3], r[5]) for r in rows] == [
        (date(2024, 4, 28), date(2024, 1, 1), 1, PPE),  # Jan 29–Apr 28: midpoint in Q1
        (date(2025, 4, 27), date(2025, 1, 1), 5, PRODUCTIVE),  # preferred tag over the 50
        (date(2025, 7, 27), date(2025, 4, 1), 6, PRODUCTIVE),  # Apr 28–Jul 27: midpoint in Q2
    ]
    # the 12-month fact has no 9-month partner, so no Q4 is derived for that year


def test_group_quarters_flag_incomplete_and_add_finance_leases(edgar_raw):
    _, q = marts(date(2026, 9, 1))
    g = q(
        "SELECT cal_quarter, capex_usd, capex_incl_finance_leases_usd, companies_reported, companies_expected, "
        "complete, finance_lease_companies, tickers FROM capex_group_quarterly WHERE company_group = 'hyperscaler' "
        "ORDER BY cal_quarter"
    ).rows()
    by_q = {r[0]: r[1:] for r in g}
    assert by_q[date(2024, 1, 1)] == (1, 1, 1, 1, True, 0, "BBB")  # AAA's first quarter is later
    assert by_q[date(2025, 1, 1)] == (15, 15, 2, 2, True, 0, "AAA,BBB")
    assert by_q[date(2025, 7, 1)] == (12, 12, 1, 2, False, 0, "AAA")
    assert by_q[date(2026, 1, 1)] == (20, 23, 1, 2, False, 1, "AAA")


def test_two_fiscal_quarters_in_one_calendar_quarter_fail_the_build(
    data_env, tmp_path, monkeypatch, synthetic_entities
):
    tickers(tmp_path, monkeypatch, {"AAA": {"cik": 1, "name": "Alpha", "group": "hyperscaler"}})
    doc = facts_doc(
        1,
        {PPE: [fact("2025-01-01", "2025-03-31", 1, "2025-04-20"), fact("2025-02-01", "2025-04-30", 1, "2025-05-20")]},
    )
    write_fetch({"0000000001": doc}, datetime(2026, 9, 1, 12, tzinfo=UTC))
    with pytest.raises(Exception, match="two fiscal quarters"):
        build(date(2026, 9, 1), ["sec_edgar"])


def test_build_records_the_filing_used_as_the_revision(edgar_raw):
    report = build(date(2025, 9, 1), ["sec_edgar"])
    rev = report.vintages["sec_edgar"]["revision"]
    assert rev == {"kind": "edgar_filed", "value": "0000000000-25-0820", "date": "2025-08-20"}
    assert report.vintages["sec_edgar"]["vintage_after_as_of"] is False
