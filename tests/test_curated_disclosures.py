"""Curated disclosures: validation, append-only rule, stage and mart 080 (synthetic rows), plus a check
that the real committed file validates (it is our own dataset, not a recorded third-party response)."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import yaml

from cachereg.build import build
from cachereg.core.paths import REPO_ROOT
from cachereg.core.store import RawFetch
from cachereg.core.warehouse import connect, query
from cachereg.sources.curated_disclosures import dataset as ds
from cachereg.sources.curated_disclosures import fetch as cf
from cachereg.sources.curated_disclosures import stage as cs

METRICS = {
    "metrics": {
        "tokens_processed_monthly": {"unit": "tokens_per_month", "definition": "Synthetic tokens per month."},
        "revenue_run_rate": {"unit": "usd_per_year", "definition": "Synthetic run-rate."},
    }
}


def row(**kw) -> dict:
    """A valid synthetic row; keyword arguments override fields (the id follows unless given)."""
    r = {
        "statement_date": "2026-01-10", "entity": "google", "metric": "tokens_processed_monthly",
        "value_as_stated": "1.5 quadrillion", "value": "1500000000000000", "unit": "tokens_per_month",
        "qualifier": "over", "period_start": "2026-01-10", "period_end": "2026-01-10", "scope": "all surfaces",
        "source_url": "https://example.test/remarks", "source_kind": "primary",
        "source_quote": "We now process over 1.5 Quadrillion   monthly tokens.", "recorded_on": "2026-02-01",
        "supersedes": "", "notes": "",
    } | kw  # fmt: skip
    r.setdefault("id", f"{r['entity']}-{r['metric']}-{r['statement_date']}")
    return {c: r[c] for c in ds.COLUMNS}


def to_csv(rows: list[dict], columns=ds.COLUMNS) -> bytes:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue().encode()


def check(rows: list[dict]) -> list[dict]:
    return ds.validate(to_csv(rows), METRICS["metrics"], {"google", "openai", "anthropic"})


ANTHROPIC = dict(
    entity="anthropic", metric="revenue_run_rate", statement_date="2026-02-12", value_as_stated="$14 billion",
    value="14000000000", unit="usd_per_year", qualifier="exact", period_start="2026-02-12", period_end="2026-02-12",
    source_quote="Today, our run-rate revenue is $14 billion.", recorded_on="2026-03-01",
)  # fmt: skip


# --- parsing -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value", "currency", "plus"),
    [
        ("3.2 quadrillion", Decimal("3.2e15"), False, False),
        ("8.3 trillion", Decimal("8300000000000"), False, False),
        ("$20B+", Decimal("2e10"), True, True),
        ("900M", Decimal("9e8"), False, False),
        ("300,000", Decimal(300000), False, False),
        ("seven billion", Decimal("7e9"), False, False),
        ("$1.25 billion", Decimal("1250000000"), True, False),
    ],
)
def test_parse_stated_is_exact_decimal(text, value, currency, plus):
    assert ds.parse_stated(text) == (value, currency, plus)


@pytest.mark.parametrize("text", ["about 5 billion", "5 bn", "eleventy billion", "", "1,00 million"])
def test_parse_stated_refuses_what_it_cannot_read(text):
    with pytest.raises(ds.DisclosureError):
        ds.parse_stated(text)


# --- validation: one failing row per rule ----------------------------------------


def test_a_valid_file_passes_and_curly_quotes_and_spaces_are_normalised():
    rows = check([row(source_quote="“We now process over 1.5 quadrillion monthly tokens.”")])
    assert rows[0]["id"] == "google-tokens_processed_monthly-2026-01-10"


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"scope": ""}, "scope is empty"),
        ({"statement_date": "10/01/2026", "id": "google-tokens_processed_monthly-10/01/2026"}, "not an ISO date"),
        ({"period_start": "2026-02-01"}, "period_start is after period_end"),
        ({"recorded_on": "2026-01-09"}, "statement_date is after recorded_on"),
        ({"id": "google-tokens-2026-01-10"}, "id must be"),
        ({"id": "google-tokens_processed_monthly-2026-01-10-1"}, "id must be"),
        ({"entity": "acme"}, "not in vendors.yaml"),
        ({"metric": "vibes", "id": "google-vibes-2026-01-10"}, "not in metrics.yaml"),
        ({"unit": "tokens"}, "is measured in tokens_per_month"),
        ({"value": "-1"}, "finite and > 0"),
        ({"value": "1e400"}, "finite and > 0"),
        ({"value": "lots"}, "not a number"),
        ({"qualifier": "more than"}, "qualifier must be"),
        ({"source_kind": "rumour"}, "primary or secondary"),
        ({"source_url": "http://example.test"}, "must be https"),
        ({"source_quote": " ".join(["word"] * 24 + ["1.5 quadrillion"])}, "longer than 25 words"),
        ({"source_quote": "We now process over 1.4 quadrillion tokens."}, "does not contain"),
        ({"value": "1400000000000000"}, "reads as"),
        ({"value_as_stated": "$1.5 quadrillion", "source_quote": "We process $1.5 quadrillion"}, "needs a usd unit"),
        (
            {"value_as_stated": "1.5 quadrillion+", "qualifier": "exact", "source_quote": "1.5 quadrillion+ a month"},
            "qualifier is over",
        ),
        ({"supersedes": "google-tokens_processed_monthly-2025-01-01"}, "not an earlier row"),
        ({"notes": " padded"}, "leading or trailing spaces"),
    ],
)
def test_each_rule_refuses_one_bad_row(override, match):
    with pytest.raises(ds.DisclosureError, match=match):
        check([row(**override)])


def test_ids_are_unique_and_a_second_row_takes_a_suffix():
    with pytest.raises(ds.DisclosureError, match="not unique"):
        check([row(), row()])
    check([row(), row(id="google-tokens_processed_monthly-2026-01-10-2")])


def test_columns_must_be_exact():
    with pytest.raises(ds.DisclosureError, match="columns must be exactly"):
        ds.validate(to_csv([row()], columns=ds.COLUMNS[:-1]), METRICS["metrics"], {"google"})


def test_a_row_is_superseded_once_and_never_by_an_older_row():
    fix = row(id="google-tokens_processed_monthly-2026-01-10-2", value_as_stated="1.6 quadrillion",
              value="1600000000000000", source_quote="over 1.6 quadrillion", recorded_on="2026-03-01",
              supersedes="google-tokens_processed_monthly-2026-01-10")  # fmt: skip
    check([row(), fix])
    again = fix | {"id": "google-tokens_processed_monthly-2026-01-10-3"}
    with pytest.raises(ds.DisclosureError, match="already superseded"):
        check([row(), fix, again])
    with pytest.raises(ds.DisclosureError, match="recorded after it"):
        check([row(recorded_on="2026-04-01"), fix])


# --- append-only -------------------------------------------------------------------


def test_append_only_allows_added_rows_and_refuses_edits_and_removals():
    old = to_csv([row()])
    ds.check_append_only(old, to_csv([row(), row(**ANTHROPIC)]))  # added: fine
    with pytest.raises(ds.DisclosureError, match=r"edited \(notes\)"):
        ds.check_append_only(old, to_csv([row(notes="changed")]))
    with pytest.raises(ds.DisclosureError, match="removed"):
        ds.check_append_only(to_csv([row(), row(**ANTHROPIC)]), old)


def test_main_skips_without_a_base_and_checks_head_against_base(monkeypatch, capsys):
    files = {"base": to_csv([row()]), "good": to_csv([row(), row(**ANTHROPIC)]), "bad": to_csv([row(value="2")])}
    monkeypatch.setattr(ds, "_git_show", lambda rev: files.get(rev))
    assert ds.main(["--base", "0" * 40]) == 0  # a new branch
    assert ds.main(["--base", "first", "--head", "good"]) == 0  # the commit that introduces the file
    assert "skipped" in capsys.readouterr().out
    assert ds.main(["--base", "base", "--head", "good"]) == 0
    assert ds.main(["--base", "base", "--head", "bad"]) == 1
    assert ds.main(["--base", "base", "--head", "gone"]) == 1  # the file was removed
    assert ds.main(["--head", "good"]) == 2


# --- fetch, stage, mart --------------------------------------------------------------


@pytest.fixture
def curated(data_env, synthetic_entities, tmp_path, monkeypatch):
    d = tmp_path / "curated"
    d.mkdir()
    (d / ds.METRICS).write_text(yaml.safe_dump(METRICS))
    monkeypatch.setattr(ds, "CURATED_DIR", d)

    def commit(rows: list[dict], at: datetime) -> None:
        (d / ds.FILE).write_bytes(to_csv(rows))
        raw = cf.fetch()
        if raw is not None:
            raw.fetched_at = at
            raw.write()

    return commit


def marts(as_of: date):
    build(as_of, ["curated_disclosures"])
    con = connect()
    try:
        return {r["id"]: r for r in query(con, "SELECT * FROM disclosures").to_dicts()}
    finally:
        con.close()


AT1, AT2 = datetime(2026, 2, 2, tzinfo=UTC), datetime(2026, 3, 2, tzinfo=UTC)
FIX = dict(
    id="google-tokens_processed_monthly-2026-01-10-2", value_as_stated="1.6 quadrillion", value="1600000000000000",
    source_quote="over 1.6 quadrillion", recorded_on="2026-03-01",
    supersedes="google-tokens_processed_monthly-2026-01-10",
)  # fmt: skip


def test_fetch_stores_once_and_skips_an_unchanged_file(curated):
    from cachereg.core.store import list_fetches

    curated([row()], AT1)
    curated([row()], AT2)
    assert len(list_fetches("curated_disclosures")) == 1
    f = list_fetches("curated_disclosures")[0]
    assert f.manifest["vintage"]["window"] == ["2026-02-01", "2026-02-01"]
    assert set(f.manifest["files"]) == {"disclosures.csv", "metrics.yaml"}


def test_fetch_never_stores_an_invalid_file(curated):
    from cachereg.core.store import list_fetches

    with pytest.raises(ds.DisclosureError):
        curated([row(value="1")], AT1)
    assert list_fetches("curated_disclosures") == []


def test_supersession_and_recorded_on_select_rows_as_of(curated):
    curated([row()], AT1)
    curated([row(), row(**ANTHROPIC), row(**FIX)], AT2)
    before = marts(date(2026, 2, 15))
    assert list(before) == ["google-tokens_processed_monthly-2026-01-10"]  # later rows invisible (Exact)
    assert before["google-tokens_processed_monthly-2026-01-10"]["vendor_name"] == "Google"
    after = marts(date(2026, 3, 5))
    assert sorted(after) == ["anthropic-revenue_run_rate-2026-02-12", FIX["id"]]  # the corrected row is gone
    assert after[FIX["id"]]["value"] == 1.6e15


def test_stage_reads_the_newest_copy_and_refuses_an_edited_row(curated, monkeypatch):
    curated([row()], AT1)
    curated([row(), row(**ANTHROPIC)], AT2)
    staged = cs.stage()["disclosures"]
    assert staged["id"].to_list() == [
        "google-tokens_processed_monthly-2026-01-10",
        "anthropic-revenue_run_rate-2026-02-12",
    ]
    with pytest.raises(ds.DisclosureError, match="edited"):  # fetch refuses to store it
        curated([row(notes="edited later"), row(**ANTHROPIC)], datetime(2026, 4, 2, tzinfo=UTC))
    raw = RawFetch("curated_disclosures", "1", fetched_at=datetime(2026, 4, 2, tzinfo=UTC))  # planted by hand
    raw.add(ds.FILE, to_csv([row(notes="edited later"), row(**ANTHROPIC)]), "config/curated/disclosures.csv", None)
    raw.add(ds.METRICS, yaml.safe_dump(METRICS).encode(), "config/curated/metrics.yaml", None)
    raw.write()
    with pytest.raises(ValueError, match="not append-only"):
        cs.stage()


def test_disclosure_series_orders_by_period_and_states_changes(curated):
    early = row(**ANTHROPIC | dict(statement_date="2026-04-06", id="anthropic-revenue_run_rate-2026-04-06",
                                   value_as_stated="$9 billion", value="9000000000", period_start="2025-12-31",
                                   period_end="2025-12-31", source_quote="up from $9 billion at the end of 2025",
                                   recorded_on="2026-04-07"))  # fmt: skip
    curated([row(**ANTHROPIC | {"recorded_on": "2026-04-07"}), early], AT1)
    build(date(2026, 4, 8), ["curated_disclosures"])
    con = connect()
    try:
        s = query(con, "SELECT id, seq, ratio_to_previous FROM disclosure_series ORDER BY seq").to_dicts()
    finally:
        con.close()
    assert [r["id"] for r in s] == [early["id"], "anthropic-revenue_run_rate-2026-02-12"]  # retrospective first
    assert s[1]["ratio_to_previous"] == pytest.approx(14 / 9)


# --- the real file -------------------------------------------------------------------------


def test_the_committed_dataset_validates():
    rows = ds.validate((REPO_ROOT / "config/curated/disclosures.csv").read_bytes())
    assert len(rows) >= 50
    assert all(r["recorded_on"] >= r["statement_date"] for r in rows)
