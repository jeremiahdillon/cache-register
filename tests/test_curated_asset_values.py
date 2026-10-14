"""Curated asset values: validation, append-only rule, stage and mart 100 (synthetic rows), plus a check
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
from cachereg.core.store import RawFetch, list_fetches
from cachereg.core.warehouse import connect, query
from cachereg.sources import _curated
from cachereg.sources._curated import CuratedError
from cachereg.sources.curated_asset_values import dataset as ds
from cachereg.sources.curated_asset_values import fetch as cf
from cachereg.sources.curated_asset_values import stage as cs

VOCAB = {
    "assets": {
        "gpu_x9": {"label": "Synthetic X9", "era": "ai", "layer": "equipment"},
        "glass": {"label": "Synthetic glass", "era": "dotcom", "layer": "infrastructure"},
    },
    "metrics": {
        "rental_price": {"definition": "Synthetic rent.", "units": ["usd_per_gpu_hour"]},
        "utilization": {"definition": "Synthetic share in use.", "units": ["percent"]},
    },
}


def row(**kw) -> dict:
    """A valid synthetic row; keyword arguments override fields (the id follows unless given)."""
    r = {
        "statement_date": "2026-01-10", "asset": "gpu_x9", "entity": "Example Cloud", "metric": "rental_price",
        "value_as_stated": "$2.10", "value": "2.10", "unit": "usd_per_gpu_hour", "qualifier": "exact",
        "period_start": "2026-01-10", "period_end": "2026-01-10", "scope": "on-demand, per GPU",
        "source_url": "https://example.test/prices", "source_kind": "secondary",
        "source_quote": "An X9 now rents for $2.10 an hour.", "recorded_on": "2026-02-01",
        "supersedes": "", "notes": "",
    } | kw  # fmt: skip
    r.setdefault("id", f"{r['asset']}-{r['metric']}-{r['statement_date']}")
    return {c: r[c] for c in ds.COLUMNS}


LIT = dict(
    asset="glass", entity="market", metric="utilization", statement_date="2001-08-01", value_as_stated="2.7%",
    value="2.7", unit="percent", period_start="2001-08-01", period_end="2001-08-01",
    source_quote="only 2.7% of the glass is lit", recorded_on="2026-02-01",
)  # fmt: skip


def to_csv(rows: list[dict], columns=ds.COLUMNS) -> bytes:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue().encode()


def check(rows: list[dict]) -> list[dict]:
    return ds.validate(to_csv(rows), VOCAB)


@pytest.mark.parametrize(
    ("text", "value", "suffix"),
    [
        ("2.7%", Decimal("2.7"), "%"),
        ("2.7 percent", Decimal("2.7"), "%"),
        ("$250 million", Decimal("2.5e8"), None),
        ("six", Decimal(6), None),
        ("forty", Decimal(40), None),
        ("30x", Decimal(30), "x"),
        ("2.5×", Decimal("2.5"), "x"),
    ],
)
def test_parse_figure_reads_percentages_and_multiples_too(text, value, suffix):
    parsed, _, _, got = ds.parse_figure(text)
    assert (parsed, got) == (value, suffix)


def test_a_valid_file_passes():
    assert [r["id"] for r in check([row(), row(**LIT)])] == [
        "gpu_x9-rental_price-2026-01-10",
        "glass-utilization-2001-08-01",
    ]


@pytest.mark.parametrize(
    ("override", "match"),
    [
        ({"entity": ""}, "entity is empty"),
        ({"period_start": "2026-02-01"}, "period_start is after period_end"),
        ({"recorded_on": "2026-01-09"}, "statement_date is after recorded_on"),
        ({"id": "gpu_x9-rent-2026-01-10"}, "id must be"),
        ({"asset": "gpu_x10", "id": "gpu_x10-rental_price-2026-01-10"}, "asset 'gpu_x10' is not in"),
        ({"metric": "vibes", "id": "gpu_x9-vibes-2026-01-10"}, "metric 'vibes' is not in"),
        ({"unit": "usd_per_node_hour"}, "is stated in usd_per_gpu_hour"),
        ({"value": "0"}, "finite and > 0"),
        ({"qualifier": "roughly"}, "qualifier must be"),
        ({"source_kind": "rumour"}, "primary or secondary"),
        ({"source_url": "http://example.test"}, "must be https"),
        ({"source_quote": " ".join(["word"] * 25 + ["$2.10"])}, "longer than 25 words"),
        ({"source_quote": "An X9 rents for $2.20 an hour."}, "does not contain"),
        ({"value": "2.2"}, "reads as"),
        ({"value_as_stated": "2.10", "source_quote": "2.10%", "unit": "usd_per_gpu_hour"}, None),
        ({"supersedes": "gpu_x9-rental_price-2025-01-01"}, "not an earlier row"),
    ],
)
def test_each_rule_refuses_one_bad_row(override, match):
    if match is None:  # a figure without $ in a usd unit is allowed (the quote may say "2.10 dollars")
        check([row(**override)])
        return
    with pytest.raises(CuratedError, match=match):
        check([row(**override)])


def test_percent_and_multiple_figures_need_their_units():
    low_end = {"value_as_stated": "70", "value": "70", "source_quote": "a 70-80% loan to value"}
    check([row(**LIT | low_end)])  # the low end of a range carries no % of its own
    with pytest.raises(CuratedError, match="has unit percent"):
        check([row(value_as_stated="2.10%", source_quote="up 2.10%")])
    with pytest.raises(CuratedError, match="has unit multiple"):
        check([row(value_as_stated="2.10x", source_quote="2.10x faster")])
    with pytest.raises(CuratedError, match="needs a usd unit"):
        check([row(**LIT | {"value_as_stated": "$2.7", "source_quote": "$2.7 and 2.7%", "unit": "percent"})])


def test_vocab_needs_era_layer_and_units():
    with pytest.raises(CuratedError, match="era"):
        ds.check_vocab({"assets": {"x": {"label": "X", "era": "now", "layer": "equipment"}}, "metrics": {}})
    with pytest.raises(CuratedError, match="units"):
        ds.check_vocab({"assets": {}, "metrics": {"m": {"definition": "M"}}})


def test_append_only_and_its_cli(monkeypatch, capsys):
    base, good, bad = to_csv([row()]), to_csv([row(), row(**LIT)]), to_csv([row(value="2.2")])
    ds.check_append_only(base, good)
    with pytest.raises(CuratedError, match="edited"):
        ds.check_append_only(base, to_csv([row(notes="later")]))
    with pytest.raises(CuratedError, match="removed"):
        ds.check_append_only(good, base)
    files = {"base": base, "good": good, "bad": bad}
    monkeypatch.setattr(_curated, "_git_show", lambda rev, path: files.get(rev))
    assert ds.main(["--base", "0" * 40]) == 0
    assert ds.main(["--base", "first", "--head", "good"]) == 0
    assert "skipped" in capsys.readouterr().out
    assert ds.main(["--base", "base", "--head", "good"]) == 0
    assert ds.main(["--base", "base", "--head", "bad"]) == 1
    assert ds.main(["--base", "base", "--head", "gone"]) == 1


# --- fetch, stage, mart --------------------------------------------------------------


@pytest.fixture
def curated(data_env, tmp_path, monkeypatch):
    d = tmp_path / "curated"
    d.mkdir()
    (d / ds.VOCAB).write_text(yaml.safe_dump(VOCAB))
    monkeypatch.setattr(ds, "CURATED_DIR", d)

    def commit(rows: list[dict], at: datetime) -> None:
        (d / ds.FILE).write_bytes(to_csv(rows))
        raw = cf.fetch()
        if raw is not None:
            raw.fetched_at = at
            raw.write()

    return commit


AT1, AT2 = datetime(2026, 2, 2, tzinfo=UTC), datetime(2026, 3, 2, tzinfo=UTC)
FIX = dict(
    id="gpu_x9-rental_price-2026-01-10-2", value_as_stated="$2.40", value="2.40",
    source_quote="Correction: an X9 rents for $2.40 an hour.", recorded_on="2026-03-01",
    supersedes="gpu_x9-rental_price-2026-01-10",
)  # fmt: skip


def mart(as_of: date) -> dict[str, dict]:
    build(as_of, ["curated_asset_values"])
    con = connect()
    try:
        return {r["id"]: r for r in query(con, "SELECT * FROM asset_values").to_dicts()}
    finally:
        con.close()


def test_fetch_stores_once_and_never_an_invalid_file(curated):
    with pytest.raises(CuratedError):
        curated([row(value="1")], AT1)
    assert list_fetches("curated_asset_values") == []
    curated([row()], AT1)
    curated([row()], AT2)
    assert len(list_fetches("curated_asset_values")) == 1


def test_supersession_and_recorded_on_select_rows_as_of(curated):
    curated([row()], AT1)
    curated([row(), row(**LIT | {"recorded_on": "2026-03-01"}), row(**FIX)], AT2)
    before = mart(date(2026, 2, 15))
    assert list(before) == ["gpu_x9-rental_price-2026-01-10"]
    assert before["gpu_x9-rental_price-2026-01-10"]["asset_label"] == "Synthetic X9"
    after = mart(date(2026, 3, 5))
    assert sorted(after) == ["glass-utilization-2001-08-01", FIX["id"]]
    assert after[FIX["id"]]["value"] == 2.4
    assert after["glass-utilization-2001-08-01"]["era"] == "dotcom"


def test_stage_refuses_a_planted_copy_that_edits_a_row(curated):
    curated([row()], AT1)
    raw = RawFetch("curated_asset_values", "1", fetched_at=AT2)
    raw.add(ds.FILE, to_csv([row(notes="edited later")]), "config/curated/asset_values.csv", None)
    raw.add(ds.VOCAB, yaml.safe_dump(VOCAB).encode(), "config/curated/asset_vocab.yaml", None)
    raw.write()
    with pytest.raises(ValueError, match="not append-only"):
        cs.stage()


def test_the_committed_dataset_validates():
    ds.validate((REPO_ROOT / "config/curated/asset_values.csv").read_bytes())
