"""Ramp AI Index manual import: cuts, parser, fetch and stage on invented pastes (never real data)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import polars as pl
import pytest

from cachereg.build import build
from cachereg.core.manual import ManualInput
from cachereg.core.registry import load_sources
from cachereg.core.store import list_fetches
from cachereg.core.warehouse import connect, query
from cachereg.sources.ramp_ai_index import cuts
from cachereg.sources.ramp_ai_index import fetch as rf
from cachereg.sources.ramp_ai_index import stage as rs

MONTHS = ["2026-03-01", "2026-02-01", "2026-01-01"]  # newest first, as Ramp pastes adoption
WEEKS = ["2026-01-04", "2026-01-11", "2026-01-18"]  # Sundays
DAYS = [(date(2025, 12, 29) + timedelta(days=d)).isoformat() for d in range(21)]  # covers the three weeks
AT = datetime(2026, 4, 10, 12, tzinfo=UTC)


def tsv(header: list[str], rows: list[list], eol: str = "\n") -> bytes:
    lines = ["\t".join(header)] + ["\t".join("" if v is None else str(v) for v in r) for r in rows]
    return eol.join(lines).encode()  # no trailing newline, like the page


def long(cut_id: str, keys: list[str], values) -> bytes:
    cut = cuts.BY_ID[cut_id]
    return tsv(list(cut.columns), [[m, k, *values(i, k)] for i, m in enumerate(MONTHS) for k in keys])


def wide(cut_id: str, columns: list[str], periods: list[str], scale: float = 1.0) -> bytes:
    rows = [[p, *(round((j + 1) * (i + 2) * scale, 6) for j in range(len(columns)))] for i, p in enumerate(periods)]
    return tsv(["Date", *columns], rows)


def adoption(i, k):
    return [30.0 - i, 0.5, 4.0]


SAMPLES = {
    "adoption/overall": tsv(
        list(cuts.BY_ID["adoption/overall"].columns),
        [
            ["2026-03-01", "Ramp Overall", 40.5, 0.5, 9.1, ""],
            ["2026-03-01", "Census Estimate", 12.25, 0.25, "", "v2"],
            ["2026-02-01", "Ramp Overall", 40.0, 0.25, 9.0, ""],
            ["2026-02-01", "Census Estimate", "", "", "", ""],
            ["2026-01-01", "Ramp Overall", 39.75, 0, "", ""],
            ["2026-01-01", "Census Estimate", 11.5, "", "", "v1"],
        ],
    ),  # fmt: skip
    "adoption/models": long(
        "adoption/models", ["Ramp Overall", "OpenAI", "Anthropic", "Acme Labs"], lambda i, k: [30.0 - i, 0.5, ""]
    ),  # fmt: skip
    "adoption/sector": long("adoption/sector", ["Construction", "Widget making"], lambda i, k: [20.0 - i, 0.5]),
    "adoption/size": long("adoption/size", ["Large", "Small"], lambda i, k: [25.0 - i, 0.5]),
    "spend_per_employee/overall": wide(
        "spend_per_employee/overall",
        ["Median (USD / employee / month)", "Top 10% (USD / employee / month)", "Top 1% (USD / employee / month)"],
        MONTHS,
    ),
    "spend_per_employee/sector": long("spend_per_employee/sector", ["Construction", "Retail"], lambda i, k: [3.5 + i]),
    "spend_per_employee/size": long("spend_per_employee/size", ["Large", "Small"], lambda i, k: [1.25 + i]),
    "spend_share/overall": wide(
        "spend_share/overall", ["AI share of business spend (%)", "Construction (%)", "Retail (%)"], MONTHS
    ),  # fmt: skip
    # Consistent with the prices below: Anthropic costs 1.5x OpenAI, so spend = volume x price.
    "token_volume/maker": tsv(["Date", "OpenAI", "Anthropic", "Acme Labs"], [[w, 4, 2, 1] for w in WEEKS]),
    "token_spend/maker": tsv(["Date", "Anthropic", "OpenAI", "Acme Labs"], [[w, 3, 4, 1] for w in WEEKS]),
    "token_price/blended": wide("token_price/blended", list(cuts.PRICES), DAYS, scale=0.5),
    "token_price/input": wide("token_price/input", list(cuts.PRICES), DAYS, scale=0.25),
    "token_price/output": wide("token_price/output", list(cuts.PRICES), DAYS, scale=2.0),
}


def imp(cut_id: str, body: bytes | None = None, at: datetime = AT, via: str = "clipboard"):
    raw = rf.fetch(manual=ManualInput(SAMPLES[cut_id] if body is None else body, via, cut_id))
    raw.fetched_at = at
    raw.write()
    return raw


# --- cuts and parser -----------------------------------------------------------------------


def test_every_cut_has_a_sample_and_the_registry_is_consistent():
    assert set(SAMPLES) == set(cuts.BY_ID) and len(cuts.CUTS) == 13
    assert {c.table for c in cuts.CUTS} == set(rs.SCHEMAS)
    assert len({c.file_name for c in cuts.CUTS}) == 13
    listing = rf.manual_help()
    assert all(c.id in listing and c.menu in listing for c in cuts.CUTS)
    assert load_sources()["ramp_ai_index"].input == "manual"


@pytest.mark.parametrize("cut_id", sorted(SAMPLES))
def test_every_sample_parses(cut_id):
    cells = cuts.parse(SAMPLES[cut_id], cuts.BY_ID[cut_id])
    assert cells and all(isinstance(c.period, date) for c in cells)


def test_tolerated_variants_parse_to_the_same_cells():
    cut = cuts.BY_ID["adoption/sector"]
    base = cuts.parse(SAMPLES[cut.id], cut)
    crlf = SAMPLES[cut.id].replace(b"\n", b"\r\n")
    for variant in (
        crlf,
        b"\xef\xbb\xbf" + SAMPLES[cut.id],
        SAMPLES[cut.id] + b"\n",
        SAMPLES[cut.id].replace(b"\n", b"\t\n", 1),
    ):  # fmt: skip  (BOM, trailing newline, trailing tab)
        assert cuts.parse(variant, cut) == base


def test_scientific_notation_and_empty_cells():
    cut = cuts.BY_ID["token_volume/maker"]
    cells = cuts.parse(tsv(["Date", "OpenAI", "Anthropic"], [["2026-01-04", "2.5e-9", ""]]), cut)
    assert [c.value for c in cells] == [2.5e-9, None]


def test_short_rows_are_padded_with_empty_cells():
    cut = cuts.BY_ID["adoption/overall"]
    body = tsv(list(cut.columns), [["2026-01-01", "Census Estimate"]])
    assert {c.value for c in cuts.parse(body, cut)} == {None}


def test_a_wide_cut_accepts_a_new_column_and_column_order_is_free():
    cut = cuts.BY_ID["token_spend/maker"]
    cells = cuts.parse(tsv(["Date", "Newco", "Anthropic", "OpenAI"], [["2026-01-04", 1, 2, 3]]), cut)
    assert {c.key: c.value for c in cells} == {"Newco": 1.0, "Anthropic": 2.0, "OpenAI": 3.0}


PRICE_HEADER = ["Date", *cuts.PRICES]


@pytest.mark.parametrize(
    ("cut_id", "body", "match"),
    [
        ("adoption/sector", tsv(["Date", "Series", "Adoption rate (%)", "Monthly change (pp)"], []), "does not match"),
        ("adoption/models", SAMPLES["adoption/overall"], "does not match"),  # wrong view, different header
        ("spend_share/overall", tsv(["Date", "Construction (%)"], [["2026-01-01", 1]]), "lacks"),
        ("spend_share/overall", tsv(["Date", "AI share of business spend (%)", "Construction"], [["2026-01-01", 1, 2]]),
         "do not belong"),
        ("token_volume/maker", tsv(["Day", "OpenAI", "Anthropic"], [["2026-01-04", 1, 2]]), "start with Date"),
        ("token_volume/maker", tsv(["Date", "OpenAI", "Anthropic", "OpenAI"], [["2026-01-04", 1, 2, 3]]), "repeated"),
        ("token_volume/maker", tsv(["Date", "OpenAI", "Anthropic"], [["2026-01-05", 1, 2]]), "not a Sunday"),
        ("adoption/size", tsv(list(cuts.BY_ID["adoption/size"].columns), [["2026-01-02", "Large", 1, 0]]),
         "first of a month"),
        ("adoption/size", tsv(list(cuts.BY_ID["adoption/size"].columns), [["Jan 2026", "Large", 1, 0]]), "ISO date"),
        ("adoption/size", tsv(list(cuts.BY_ID["adoption/size"].columns), [["2026-01-01", "Large", "n/a", 0]]),
         "not a number"),
        ("adoption/size", tsv(list(cuts.BY_ID["adoption/size"].columns), [["2026-01-01", "Large", "inf", 0]]),
         "finite"),
        ("adoption/size", tsv(list(cuts.BY_ID["adoption/size"].columns), [["2026-01-01", "", 1, 0]]), "empty"),
        ("adoption/size", tsv(list(cuts.BY_ID["adoption/size"].columns),
                              [["2026-01-01", "Large", 1, 0], ["2026-01-01", "Large", 2, 0]]), "duplicate"),
        ("token_price/input", tsv(PRICE_HEADER, [["2026-01-05", 1, 2, 3], ["2026-01-05", 1, 2, 3]]), "duplicate"),
        ("token_price/input", tsv(PRICE_HEADER, [["2026-01-05", 1, 2, 3, 4]]), "more fields"),
        ("token_price/input", tsv(PRICE_HEADER, []), "no data rows"),
        ("token_price/input", b"  \n", "empty"),
        ("token_price/input", b"\xff\xfe", "UTF-8"),
    ],
)  # fmt: skip
def test_refused_pastes(cut_id, body, match):
    with pytest.raises(ValueError, match=match):
        cuts.parse(body, cuts.BY_ID[cut_id])


# --- fetch -------------------------------------------------------------------------------


def test_fetch_stores_the_bytes_and_records_the_import(data_env):
    raw = imp("token_volume/maker", via="file")
    (stored,) = list_fetches("ramp_ai_index")
    assert stored.read("token_volume__maker.tsv") == SAMPLES["token_volume/maker"]
    m = json.loads((stored.path / "manifest.json").read_text())
    url = cuts.BY_ID["token_volume/maker"].url
    assert m["requests"] == [{"url": url, "status": None, "file": "token_volume__maker.tsv", "via": "file",
                              "cut": "token_volume/maker"}]  # fmt: skip
    assert m["vintage"] | {"value": "-"} == {"kind": "content", "value": "-", "cut": "token_volume/maker",
                                              "first_period": WEEKS[0], "last_period": WEEKS[-1]}  # fmt: skip
    assert len(raw.vintage["value"]) == 64


@pytest.mark.parametrize(("cut", "match"), [(None, "without --cut"), ("adoption/everything", "unknown cut")])
def test_fetch_needs_a_known_cut(data_env, cut, match):
    with pytest.raises(ValueError, match=match):
        rf.fetch(manual=ManualInput(SAMPLES["adoption/size"], "clipboard", cut))


def test_fetch_without_manual_input_explains_itself(data_env):
    with pytest.raises(ValueError, match="imported by hand"):
        rf.fetch()


def test_wrong_click_guard_refuses_another_cuts_latest_bytes_and_accepts_a_reimport(data_env):
    imp("token_price/blended")
    with pytest.raises(ValueError, match="same data as the latest token_price/blended"):
        imp("token_price/input", SAMPLES["token_price/blended"])  # same header, so only the guard can tell
    imp("token_price/blended", at=datetime(2026, 4, 11, tzinfo=UTC))  # same cut again: stored
    assert len(list_fetches("ramp_ai_index")) == 2


def test_two_imports_in_the_same_second_both_land(data_env):
    imp("adoption/size")
    imp("adoption/sector")  # same fetched_at: the store moves the second import on by a second
    assert [f.manifest["vintage"]["cut"] for f in list_fetches("ramp_ai_index")] == ["adoption/size", "adoption/sector"]


# --- stage -------------------------------------------------------------------------------


@pytest.fixture
def staged(data_env, synthetic_entities):
    for i, cut_id in enumerate(SAMPLES):
        imp(cut_id, at=datetime(2026, 4, 10, 12, i, tzinfo=UTC))
    return rs.stage()


def test_stage_writes_every_table(staged):
    assert {t: df.height for t, df in staged.items() if not t.startswith("_")} == {
        "adoption": 6 + 12 + 6 + 6, "spend_per_employee": 9 + 6 + 6, "spend_share": 9, "token_index": 18,
        "token_price": 189, "imports": 13, "cuts": 13, "sectors": 20,
    }  # fmt: skip
    assert staged["_rejected_rows"]["rejected"][0] == 0


def test_stage_adoption_kinds_and_first_month(staged):
    a = staged["adoption"]
    kinds = {(c, label): k for c, label, k in a.select("cut", "series_label", "series_kind").unique().iter_rows()}
    assert kinds[("adoption/overall", "Ramp Overall")] == "overall"
    assert kinds[("adoption/overall", "Census Estimate")] == "census"
    assert kinds[("adoption/models", "Ramp Overall")] == "overall"
    assert kinds[("adoption/models", "Acme Labs")] == "vendor"
    assert kinds[("adoption/sector", "Widget making")] == "sector"
    assert kinds[("adoption/size", "Small")] == "size"
    first = a.filter(a["month"] == date(2026, 1, 1))
    assert first["mom_pp"].null_count() == first.height  # Ramp writes 0; there is no prior month
    later = a.filter((a["cut"] == "adoption/sector") & (a["month"] == date(2026, 2, 1)))
    assert later["mom_pp"].to_list() == [0.5, 0.5]
    census = a.filter(a["series_kind"] == "census").sort("month")
    assert census["census_question_version"].to_list() == ["v1", None, "v2"]
    assert census["adoption_pct"].to_list() == [11.5, None, 12.25]  # an empty month stays, as nulls


def test_stage_spend_tokens_and_prices(staged):
    spe = staged["spend_per_employee"]
    assert set(spe.filter(spe["dimension"] == "overall")["statistic"]) == {"median", "top_10pct", "top_1pct"}
    assert set(spe.filter(spe["dimension"] == "size")["group_label"]) == {"Large", "Small"}
    share = staged["spend_share"]
    assert set(share.filter(share["scope"] == "overall")["sector_label"].to_list()) == {None}
    assert set(share.filter(share["scope"] == "sector")["sector_label"]) == {"Construction", "Retail"}
    tok = staged["token_index"]
    assert set(tok["measure"]) == {"volume", "spend"} and tok["week"].min() == date(2026, 1, 4)
    price = staged["token_price"]
    assert set(price["price_kind"]) == {"blended", "input", "output"}
    imports = staged["imports"]
    assert imports.filter(imports["cut"] == "adoption/models")["rows"][0] == 12
    assert imports.filter(imports["cut"] == "token_volume/maker")["rows"][0] == 3
    assert staged["sectors"].filter(staged["sectors"]["label"] == "Technology and media")["assumed"][0]


def test_stage_is_independent_of_row_and_column_order(data_env, synthetic_entities):
    imp("adoption/sector")
    imp("token_spend/maker")
    first = rs.stage()
    lines = SAMPLES["adoption/sector"].split(b"\n")
    reordered = b"\n".join([lines[0], *reversed(lines[1:])])
    cols = [line.split(b"\t") for line in SAMPLES["token_spend/maker"].split(b"\n")]
    swapped = b"\n".join(b"\t".join([c[0], c[2], c[1], c[3]]) for c in cols)
    imp("adoption/sector", reordered, at=datetime(2026, 4, 11, tzinfo=UTC))
    imp("token_spend/maker", swapped, at=datetime(2026, 4, 11, 0, 1, tzinfo=UTC))
    second = rs.stage()
    for table, key in (("adoption", ["month", "series_label"]), ("token_index", ["week", "maker_label"])):
        a = first[table]
        b = second[table].filter(second[table]["fetch_id"] > a["fetch_id"].max())  # the reordered import
        cols_ = [c for c in a.columns if c not in rs.TAG]
        assert b.height == a.height and a.select(cols_).sort(key).equals(b.select(cols_).sort(key))


def test_stage_counts_an_unreadable_import_as_rejected(data_env, synthetic_entities):
    imp("adoption/size")
    (stored,) = list_fetches("ramp_ai_index")
    (stored.path / "adoption__size.tsv").write_bytes(b"Date\tnope\n2026-01-01\t1\n2026-02-01\t2")
    out = rs.stage()
    assert out["_rejected_rows"]["rejected"][0] == 2 and out["adoption"].height == 0


# --- marts 060-062 --------------------------------------------------------------------------


def marts(as_of: date):
    build(as_of, ["ramp_ai_index"])

    def q(sql: str):
        con = connect()
        try:
            return query(con, sql)
        finally:
            con.close()

    return q


def import_all(skip: tuple[str, ...] = (), at: datetime = AT) -> None:
    for i, cut_id in enumerate(c for c in SAMPLES if c not in skip):
        imp(cut_id, at=at + timedelta(minutes=i))


def test_marts_build_with_coverage_and_entity_joins(data_env, synthetic_entities):
    import_all()
    q = marts(date(2026, 4, 30))
    cov = q("SELECT * FROM ramp_cut_coverage ORDER BY position")
    assert cov.height == 13 and cov["present_at_cutoff"].all() and not cov["cut_after_cutoff"].any()
    a = q("SELECT * FROM ramp_adoption")
    overall = a.filter(a["series_kind"] == "overall")
    assert set(overall["cut"]) == {"adoption/overall"} and overall.height == 3  # one overall series
    assert overall.sort("month")["adoption_pct"].to_list() == [39.75, 40.0, 40.5]
    vendors = a.filter((a["series_kind"] == "vendor") & (a["month"] == date(2026, 3, 1)))
    assert dict(vendors.select("series_label", "vendor_id").iter_rows()) == {
        "OpenAI": "openai", "Anthropic": "anthropic", "Acme Labs": None}  # fmt: skip
    assert sorted(vendors["vendor_rank"].to_list()) == [1, 1, 1]  # all tied in the sample
    sector = a.filter(a["series_label"] == "Construction")
    assert set(sector["naics"]) == {"23"} and not sector["naics_assumed"].any()
    labels = q("SELECT kind, label FROM ramp_label_coverage WHERE NOT mapped ORDER BY kind, label")
    assert set(labels.iter_rows()) == {("vendor", "Acme Labs"), ("sector", "Widget making")}
    check = q("SELECT * FROM ramp_overall_check")
    assert check["disagree"].all() and check["models_view_pct"].to_list() == [28.0, 29.0, 30.0]
    census = q("SELECT * FROM ramp_census_restated")
    assert census["census_question_version"].to_list() == ["v1", None, "v2"]
    spe = q("SELECT * FROM ramp_spend_per_employee WHERE dimension = 'sector'")
    assert set(spe["naics"]) == {"23", "44-45"} and spe["first_month"].sum() == 2
    share = q("SELECT * FROM ramp_spend_share WHERE scope = 'overall'")
    assert share.height == 3 and share["naics"].null_count() == 3


def test_each_cut_uses_its_latest_import_on_or_before_the_cutoff(data_env, synthetic_entities):
    import_all(skip=("adoption/size",))
    later = datetime(2026, 5, 2, tzinfo=UTC)
    imp("adoption/size", at=later)  # first imported after the cutoff below
    revised = SAMPLES["adoption/sector"].replace(b"Construction\t20.0", b"Construction\t21.5")
    imp("adoption/sector", revised, at=later)
    q = marts(date(2026, 4, 30))
    cov = {r["cut"]: r for r in q("SELECT * FROM ramp_cut_coverage").iter_rows(named=True)}
    assert cov["adoption/size"]["present_at_cutoff"] is False and cov["adoption/size"]["cut_after_cutoff"] is True
    assert q("SELECT count(*) AS n FROM ramp_adoption WHERE series_kind = 'size'")["n"][0] == 0
    old = q("SELECT adoption_pct FROM ramp_adoption WHERE series_label = 'Construction' AND month = '2026-03-01'")
    assert old["adoption_pct"].to_list() == [20.0]
    q = marts(date(2026, 5, 31))
    new = q("SELECT adoption_pct FROM ramp_adoption WHERE series_label = 'Construction' AND month = '2026-03-01'")
    assert new["adoption_pct"].to_list() == [21.5]
    assert q("SELECT count(*) AS n FROM ramp_adoption WHERE series_kind = 'size'")["n"][0] == 6


def test_a_never_imported_cut_is_listed_and_periods_after_as_of_are_dropped(data_env, synthetic_entities):
    import_all(skip=("token_price/output",))
    q = marts(date(2026, 2, 15))  # before the import: the earliest import is used (flagged by build)
    cov = q("SELECT * FROM ramp_cut_coverage WHERE cut = 'token_price/output'")
    assert cov["first_import"][0] is None and cov["present_at_cutoff"][0] is False
    assert q("SELECT max(month) AS m FROM ramp_adoption")["m"][0] == date(2026, 2, 1)


def test_token_shares_ignore_rescaling_and_the_checks_pass_on_consistent_data(data_env, synthetic_entities):
    import_all()
    q = marts(date(2026, 4, 30))
    shares = q("SELECT * FROM ramp_token_share ORDER BY week, measure, maker_label")
    sums = shares.group_by("week", "measure").agg(pl.col("share").sum().alias("total"))
    assert all(abs(x - 1) < 1e-12 for x in sums["total"])
    before = shares.select("week", "measure", "maker_label", "share")
    rescaled = SAMPLES["token_volume/maker"].replace(b"\t4\t2\t1", b"\t100\t50\t25")  # a new peak, same shares
    imp("token_volume/maker", rescaled, at=AT + timedelta(days=1))
    after = marts(date(2026, 4, 30))("SELECT week, measure, maker_label, share FROM ramp_token_share")
    assert before.sort("week", "measure", "maker_label").equals(after.sort("week", "measure", "maker_label"))
    tc = q("SELECT * FROM ramp_token_check")
    assert tc.height == 3 and tc["decisive"].all() and not tc["suspect_swap"].any()
    assert all(abs(x - 1.5) < 1e-9 for x in tc["implied_price_ratio"])
    pc = q("SELECT * FROM ramp_price_check")
    assert pc.height == 63 and pc["within_bounds"].all()
    assert not q("SELECT * FROM ramp_price_identical")["identical"].any()


def test_swapped_views_show_up_in_the_checks(data_env, synthetic_entities):
    import_all(skip=("token_volume/maker", "token_spend/maker", "token_price/input", "token_price/output"))
    imp("token_volume/maker", SAMPLES["token_spend/maker"], at=AT + timedelta(hours=1))
    imp("token_spend/maker", SAMPLES["token_volume/maker"], at=AT + timedelta(hours=2))
    imp("token_price/input", SAMPLES["token_price/output"], at=AT + timedelta(hours=3))
    imp("token_price/output", SAMPLES["token_price/input"], at=AT + timedelta(hours=4))
    q = marts(date(2026, 4, 30))
    assert q("SELECT * FROM ramp_token_check")["suspect_swap"].all()
    assert not q("SELECT * FROM ramp_price_check")["within_bounds"].any()


def test_a_view_imported_twice_under_two_cuts_is_reported_identical(data_env, synthetic_entities):
    import_all(skip=("token_price/input",))
    imp("token_price/input", SAMPLES["token_price/blended"] + b"\n", at=AT + timedelta(hours=1))  # bytes differ
    ident = marts(date(2026, 4, 30))("SELECT * FROM ramp_price_identical WHERE identical")
    assert set(ident.select("kind_a", "kind_b").iter_rows()) == {("blended", "input")}
