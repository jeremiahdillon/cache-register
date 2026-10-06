"""Epoch AI sources and marts on synthetic zips (no network, no recorded upstream files)."""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from datetime import UTC, date, datetime

import pytest

from cachereg.build import build
from cachereg.core.http import Response
from cachereg.core.store import RawFetch
from cachereg.core.warehouse import connect, query
from cachereg.sources import _epoch_zip
from cachereg.sources.epoch_benchmarks import fetch as bf
from cachereg.sources.epoch_benchmarks import stage as bs
from cachereg.sources.epoch_models import fetch as mf
from cachereg.sources.epoch_models import stage as ms


def _csv(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    w.writerows(rows)
    return out.getvalue()


def _zip(members: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in members.items():
            zf.writestr(name, body)
    return buf.getvalue()


def bench_zip(eci: dict[str, float] | None = None) -> bytes:
    """Two synthetic model groups, three versions, two described benchmarks and one undescribed."""
    eci = eci or {"Model Nine": 150.0, "Model Eight": 120.0}
    return _zip(
        {
            "README.md": "synthetic\n",
            "model_metadata.csv": _csv(
                [
                    "model_version",
                    "model_group",
                    "date",
                    "display_name",
                    "organization",
                    "country",
                    "accessibility",
                    "training_compute_flop",
                ],
                [
                    ["vendor-nine-20260101_high", "Model Nine", "2026-01-01", "", "Vendor", "US", "API access", ""],
                    ["vendor-nine-20260101_low", "Model Nine", "2026-01-01", "", "Vendor", "US", "API access", ""],
                    ["vendor-eight", "Model Eight", "2025-06-01", "", "Vendor", "US", "API access", "1e24"],
                    ["", "", "", "", "", "", "", ""],  # blank line upstream: dropped silently
                    ["", "Orphan", "2025-01-01", "", "", "", "", ""],  # no version: rejected
                    ["vendor-ten", "Model Ten", "2026-09-01", "", "Vendor", "US", "API access", ""],
                ],
            ),
            "epoch_capabilities_index/eci_scores.csv": _csv(
                [
                    "Model",
                    "Display name",
                    "eci",
                    "eci_ci_low",
                    "eci_ci_high",
                    "date",
                    "Organization",
                    "Country (of organization)",
                    "Model accessibility",
                    "Accessibility group",
                    "model_versions",
                ],
                [
                    [
                        g,
                        g,
                        v,
                        v - 2,
                        v + 2,
                        "2026-01-01" if g == "Model Nine" else "2025-06-01",
                        "Vendor",
                        "US",
                        "API access",
                        "Closed weights",
                        "",
                    ]
                    for g, v in eci.items()
                ]
                + [
                    [
                        "Model Ten",
                        "Model Ten",
                        160,
                        158,
                        162,
                        "2026-09-01",
                        "Vendor",
                        "US",
                        "API access",
                        "Closed weights",
                        "",
                    ]
                ],
            ),
            "benchmark_metadata.csv": _csv(
                [
                    "benchmark",
                    "in_eci",
                    "source_file",
                    "score_column",
                    "scale",
                    "random_baseline",
                    "score_ceiling",
                    "release_date",
                    "superseded_by",
                ],
                [
                    [
                        "Bench A",
                        "True",
                        "bench_a.csv",
                        "Best score (across scorers)",
                        "1.0",
                        "0.25",
                        "1.0",
                        "2024-01-01",
                        "",
                    ],
                    ["Bench P", "False", "bench_p.csv", "Percent correct", "0.01", "0", "1", "2024-02-01", ""],
                    ["Bench X", "False", "", "", "1.0", "0", "1", "", ""],
                ],
            ),
            "bench_a.csv": _csv(
                ["Model version", "mean_score", "Best score (across scorers)", "id"],
                [
                    ["vendor-nine-20260101_high", "0.5", "0.8", "r1"],  # decoy column mean_score ignored
                    ["vendor-nine-20260101_high", "0.6", "0.7", "r2"],  # repeated run: kept
                    ["vendor-eight", "0.3", "", "r3"],  # empty: skipped, not rejected
                    ["vendor-eight", "0.3", "n/a", "r4"],  # non-numeric: rejected
                    ["", "0.1", "0.2", "r5"],  # no version: kept, null
                ],
            ),
            "bench_p.csv": _csv(["Model version", "Percent correct"], [["vendor-eight", "41.8"]]),
            "bench_x.csv": _csv(["Model version", "Score"], [["vendor-eight", "9"]]),
        }
    )


def models_zip() -> bytes:
    header = [
        "Model",
        "Publication date",
        "Organization",
        "Domain",
        "Task",
        "Model accessibility",
        "Country (of organization)",
        "Base model",
        "Notability criteria",
        "Confidence",
        "Last modified",
        "Parameters",
        "Training compute (FLOP)",
        "Training compute cost (2023 USD)",
        "Open model weights?",
        "Frontier model",
    ]

    def row(name, day, params="", weights="No", frontier=""):
        return [
            name,
            day,
            "Vendor",
            "Language",
            "Chat",
            "API access",
            "US",
            "",
            "",
            "Confident",
            "",
            params,
            "",
            "",
            weights,
            frontier,
        ]

    return _zip(
        {
            "README.md": "synthetic\n",
            "all_ai_models.csv": _csv(
                header,
                [
                    row("Model Nine", "2026-01-01", "1.5e12", "No", "True"),
                    row("Model Eight", "2025-06", "7e10", "Yes"),
                    row("Model Year", "2026", "abc"),  # unparseable parameters: rejected cell
                    row("Model Late", "2026-09-30"),
                ],
            ),
            "notable_ai_models.csv": _csv(["Model"], [["Model Nine"], ["Model Eight"]]),
            "frontier_ai_models.csv": _csv(["Model"], [["Model Nine"]]),
            "large_scale_ai_models.csv": _csv(["Model"], [["Model Nine"], ["Not In All"]]),
        }
    )


def _write(source: str, filename: str, body: bytes, fetched: datetime) -> None:
    r = RawFetch(source, "1", fetched_at=fetched)
    r.add(filename, body, "https://example.test/x.zip", 200)
    r.vintage = {"kind": "content_sha256", "value": hashlib.sha256(body).hexdigest()}
    r.write()


# ---- fetch -------------------------------------------------------------------------------------


def test_fetch_stores_the_zip_with_a_content_hash_vintage(data_env, monkeypatch):
    body = bench_zip()
    seen = {}

    def fake_get(url, params=None, headers=None, **kw):
        seen["headers"] = headers
        return Response(url=url, status=200, body=body)

    monkeypatch.setattr(_epoch_zip.http, "get", fake_get)
    raw = bf.fetch()
    assert seen["headers"] == {"Accept": "application/zip"}
    assert list(raw.files) == ["benchmark_data.zip"] and raw.files["benchmark_data.zip"] == body
    assert raw.vintage == {"kind": "content_sha256", "value": hashlib.sha256(body).hexdigest()}
    assert raw.requests[0]["url"] == bf.URL


@pytest.mark.parametrize(
    ("body", "match"),
    [
        (b"not a zip", "not a zip"),
        (_zip({"README.md": "x"}), "missing all_ai_models.csv"),
        (_zip({"README.md": "x", "../evil.csv": "x"}), "unsafe member"),
    ],
)
def test_fetch_refuses_bad_zips_before_storing(data_env, monkeypatch, body, match):
    monkeypatch.setattr(_epoch_zip.http, "get", lambda url, **kw: Response(url=url, status=200, body=body))
    with pytest.raises(ValueError, match=match):
        mf.fetch()


def test_zip_size_cap(monkeypatch):
    monkeypatch.setattr(_epoch_zip, "MAX_UNCOMPRESSED", 10)
    with pytest.raises(ValueError, match="size cap"):
        _epoch_zip.open_zip(_zip({"README.md": "x" * 11}), ["README.md"])


# ---- stage -------------------------------------------------------------------------------------


def test_stage_benchmarks(data_env):
    first, second = bench_zip(), bench_zip({"Model Nine": 151.0, "Model Eight": 120.0})
    _write("epoch_benchmarks", bf.FILE, first, datetime(2026, 9, 1, 6, tzinfo=UTC))
    _write("epoch_benchmarks", bf.FILE, first, datetime(2026, 9, 8, 6, tzinfo=UTC))  # unchanged upstream
    _write("epoch_benchmarks", bf.FILE, second, datetime(2026, 9, 15, 6, tzinfo=UTC))
    out = bs.stage()
    v = out["vintages"]
    assert v.height == 3 and v["vintage_id"].n_unique() == 2
    assert v["vintage_id"][1] == v["fetch_id"][0]  # unchanged content points at the first fetch
    assert out["eci"]["vintage_id"].n_unique() == 2 and out["eci"].height == 6  # staged once per content

    one = out["scores"].filter(out["scores"]["vintage_id"] == v["vintage_id"][0])
    a = one.filter(one["benchmark"] == "Bench A")
    assert a["score"].to_list() == [0.8, 0.7, 0.2]  # metadata's column, not the decoy
    assert a["row"].to_list() == [1, 2, 5] and a["row_id"].to_list() == ["r1", "r2", "r5"]
    assert a["model_version"].to_list()[2] is None
    p = one.filter(one["benchmark"] == "Bench P")
    assert p["score"][0] == 41.8 and p["score_norm"][0] == pytest.approx(0.418)  # score × scale
    assert "Bench X" not in one["benchmark"].to_list()  # no score column in metadata: not read
    m = out["models"].filter(out["models"]["vintage_id"] == v["vintage_id"][0])
    assert m.height == 4 and m["release_date"][0] == date(2026, 1, 1)
    assert out["_rejected_rows"]["rejected"][0] == 4  # per content: orphan row + "n/a", twice
    assert out["benchmarks"].filter(out["benchmarks"]["benchmark"] == "Bench A")["in_eci"][0] is True


def test_stage_benchmarks_fails_on_a_missing_listed_column(data_env):
    body = bench_zip()
    zf = zipfile.ZipFile(io.BytesIO(body))
    members = {n: zf.read(n).decode() for n in zf.namelist()}
    members["bench_a.csv"] = _csv(["Model version", "mean_score"], [["vendor-eight", "0.3"]])
    _write("epoch_benchmarks", bf.FILE, _zip(members), datetime(2026, 9, 1, 6, tzinfo=UTC))
    with pytest.raises(ValueError, match="bench_a.csv has no column 'Best score"):
        bs.stage()


def test_stage_fails_when_the_stored_zip_does_not_match_its_manifest(data_env):
    _write("epoch_benchmarks", bf.FILE, bench_zip(), datetime(2026, 9, 1, 6, tzinfo=UTC))
    from cachereg.core.store import list_fetches

    (list_fetches("epoch_benchmarks")[0].path / bf.FILE).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="does not match its manifest"):
        bs.stage()


def test_stage_models(data_env):
    _write("epoch_models", mf.FILE, models_zip(), datetime(2026, 9, 1, 6, tzinfo=UTC))
    out = ms.stage()
    m = {r["model"]: r for r in out["models"].to_dicts()}
    assert m["Model Nine"]["parameters"] == 1.5e12 and m["Model Nine"]["frontier_model"] is True
    assert m["Model Nine"]["in_notable"] and m["Model Nine"]["in_frontier"] and m["Model Nine"]["in_large_scale"]
    assert m["Model Eight"]["open_model_weights"] is True and not m["Model Eight"]["in_frontier"]
    assert (m["Model Eight"]["publication_date"], m["Model Eight"]["publication_date_precision"]) == (
        date(2025, 6, 1),
        "month",
    )
    assert m["Model Year"]["publication_date_precision"] == "year" and m["Model Year"]["parameters"] is None
    assert out["_rejected_rows"]["rejected"][0] == 1


# ---- marts -------------------------------------------------------------------------------------


@pytest.fixture
def epoch_raw(synthetic_raw, synthetic_entities):
    """The OpenRouter/LiteLLM synthetic fixture plus two Epoch vintages and `epoch` aliases."""
    import yaml

    f = synthetic_entities / "models.yaml"
    models = yaml.safe_load(f.read_text())
    models["models"]["openai/gpt-9"]["aliases"]["epoch"] = ["Model Nine"]
    f.write_text(yaml.safe_dump(models))
    _write("epoch_benchmarks", bf.FILE, bench_zip(), datetime(2026, 8, 1, 6, tzinfo=UTC))
    _write(
        "epoch_benchmarks",
        bf.FILE,
        bench_zip({"Model Nine": 155.0, "Model Eight": 121.0}),
        datetime(2026, 8, 20, 6, tzinfo=UTC),
    )
    _write("epoch_models", mf.FILE, models_zip(), datetime(2026, 8, 1, 6, tzinfo=UTC))
    return synthetic_raw


def _rows(sql: str) -> list[dict]:
    con = connect()
    try:
        return query(con, sql).to_dicts()
    finally:
        con.close()


def test_eci_mart_reads_one_vintage_and_joins_prices(epoch_raw):
    report = build(date(2026, 8, 10), ["openrouter_rankings", "litellm_prices", "epoch_benchmarks"])
    assert "020_epoch_capabilities" in report.marts_built
    eci = {r["model_group"]: r for r in _rows("SELECT * FROM epoch_eci")}
    assert eci["Model Nine"]["eci"] == 150.0  # the Aug 1 vintage, not Aug 20's re-fit
    assert "Model Ten" not in eci  # released after as_of
    assert eci["Model Nine"]["model_id"] == "openai/gpt-9" and eci["Model Eight"]["model_id"] is None
    cov = {r["measure"]: r for r in _rows("SELECT * FROM epoch_alias_coverage")}
    assert (cov["eci_models"]["models"], cov["eci_models"]["mapped"]) == (2, 1)
    # Analysis (a)'s join path: ECI → canonical model → LiteLLM price keys → staged prices.
    priced = _rows(
        """SELECT e.model_group, p.key, p.input_usd_per_token FROM epoch_eci e
           JOIN dim_model_alias l ON l.source = 'litellm' AND l.model_id = e.model_id
           JOIN stg_litellm_prices_prices p ON p.key = l.alias"""
    )
    assert {r["model_group"] for r in priced} == {"Model Nine"} and priced[0]["input_usd_per_token"] > 0
    scores = _rows("SELECT * FROM epoch_scores WHERE benchmark = 'Bench A' ORDER BY row")
    assert [r["row"] for r in scores] == [1, 2]  # null-version row excluded; repeated runs kept
    assert all(r["model_id"] == "openai/gpt-9" and r["in_eci"] for r in scores)

    build(date(2026, 8, 25), ["epoch_benchmarks"])
    assert {r["model_group"]: r["eci"] for r in _rows("SELECT * FROM epoch_eci")}["Model Nine"] == 155.0


def test_eci_mart_falls_back_to_the_earliest_vintage(epoch_raw):
    report = build(date(2026, 7, 1), ["epoch_benchmarks"])
    assert report.vintages["epoch_benchmarks"]["vintage_after_as_of"] is True
    eci = {r["model_group"]: r["eci"] for r in _rows("SELECT * FROM epoch_eci")}
    assert eci == {"Model Nine": 150.0, "Model Eight": 120.0}  # the earliest vintage, flagged


@pytest.mark.parametrize(("as_of", "visible"), [(date(2026, 6, 30), False), (date(2026, 12, 31), True)])
def test_models_mart_partial_dates_count_from_the_end_of_their_period(epoch_raw, as_of, visible):
    build(as_of, ["epoch_models"])
    names = {r["model"] for r in _rows("SELECT model FROM epoch_ai_models")}
    assert ("Model Year" in names) is visible
    assert "Model Eight" in names  # 2025-06 (month precision)


def test_models_mart_month_precision_counts_from_the_last_day(epoch_raw):
    build(date(2025, 6, 29), ["epoch_models"])
    assert "Model Eight" not in {r["model"] for r in _rows("SELECT model FROM epoch_ai_models")}
    build(date(2025, 6, 30), ["epoch_models"])
    assert "Model Eight" in {r["model"] for r in _rows("SELECT model FROM epoch_ai_models")}


def test_models_mart_day_precision_and_alias(epoch_raw):
    build(date(2026, 9, 29), ["epoch_models"])
    assert "Model Late" not in {r["model"] for r in _rows("SELECT model FROM epoch_ai_models")}
    nine = _rows("SELECT * FROM epoch_ai_models WHERE model = 'Model Nine'")[0]
    assert nine["model_id"] == "openai/gpt-9"


# ---- regressions from the code review ----------------------------------------------------------


def _members(body: bytes) -> dict[str, str]:
    zf = zipfile.ZipFile(io.BytesIO(body))
    return {n: zf.read(n).decode() for n in zf.namelist()}


def test_stage_rejects_duplicate_versions_nan_and_blank_eci_groups(data_env):
    m = _members(bench_zip())
    m["model_metadata.csv"] += "vendor-eight,Model Eight,2025-06-02,,Vendor,US,API access,\n"  # listed twice
    m["epoch_capabilities_index/eci_scores.csv"] += ",,99,98,100,2025-01-01,Vendor,US,API access,Closed weights,\n"
    m["bench_p.csv"] += "vendor-ten,NaN\nvendor-ten,inf\n"
    _write("epoch_benchmarks", bf.FILE, _zip(m), datetime(2026, 9, 1, 6, tzinfo=UTC))
    out = bs.stage()
    models = out["models"]
    assert models.filter(models["model_version"] == "vendor-eight")["release_date"].to_list() == [date(2025, 6, 1)]
    assert None not in out["eci"]["model_group"].to_list()
    assert out["scores"].filter(out["scores"]["benchmark"] == "Bench P").height == 1  # NaN, inf dropped
    # orphan row, "n/a", duplicate version, blank ECI group, NaN, inf
    assert out["_rejected_rows"]["rejected"][0] == 6


def test_eci_mart_partial_and_missing_release_dates(data_env, synthetic_entities):
    m = _members(bench_zip())
    m["model_metadata.csv"] = m["model_metadata.csv"].replace(
        "vendor-eight,Model Eight,2025-06-01", "vendor-eight,Model Eight,"
    )
    m["epoch_capabilities_index/eci_scores.csv"] = m["epoch_capabilities_index/eci_scores.csv"].replace(
        "2026-01-01", "2026-01"
    )
    _write("epoch_benchmarks", bf.FILE, _zip(m), datetime(2026, 9, 1, 6, tzinfo=UTC))
    build(date(2026, 1, 15), ["epoch_benchmarks"])
    assert "Model Nine" not in {r["model_group"] for r in _rows("SELECT * FROM epoch_eci")}  # visible from Jan 31
    build(date(2026, 1, 31), ["epoch_benchmarks"])
    assert "Model Nine" in {r["model_group"] for r in _rows("SELECT * FROM epoch_eci")}
    undated = {r["measure"]: r["rows_without_date"] for r in _rows("SELECT * FROM epoch_undated")}
    assert undated == {"eci": 0, "scores": 1}  # vendor-eight's Bench P score has no release date
    assert "vendor-eight" not in {r["model_version"] for r in _rows("SELECT * FROM epoch_scores")}


def test_stage_models_requires_the_subset_model_column(data_env):
    m = _members(models_zip())
    m["frontier_ai_models.csv"] = _csv(["Name"], [["Model Nine"]])
    _write("epoch_models", mf.FILE, _zip(m), datetime(2026, 9, 1, 6, tzinfo=UTC))
    with pytest.raises(ValueError, match="frontier_ai_models.csv has no column 'Model'"):
        ms.stage()
