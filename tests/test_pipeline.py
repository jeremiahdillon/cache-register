"""End-to-end on synthetic data: raw → staged → marts → story → rendered targets."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from cachereg.build import build
from cachereg.core.warehouse import connect, query
from cachereg.sources.openrouter_rankings.fetch import month_windows

ROOT = Path(__file__).resolve().parents[1]
WALLET = ROOT / "analyses" / "explore" / "2026-10-02-openrouter-wallet-share"


def test_month_windows_cover_range_without_gaps():
    w = month_windows(date(2025, 1, 15), date(2025, 3, 2))
    assert w == [
        (date(2025, 1, 15), date(2025, 1, 31)),
        (date(2025, 2, 1), date(2025, 2, 28)),
        (date(2025, 3, 1), date(2025, 3, 2)),
    ]


def test_build_marts(synthetic_raw):
    report = build(date(2026, 8, 31))
    assert report.staged["openrouter_rankings.daily"] == 91 * 7
    assert report.rejected.get("openrouter_rankings", 0) == 0
    con = connect()
    try:
        daily = query(con, "SELECT * FROM or_model_daily")
        free = daily.filter(pl.col("is_free"))
        assert free["est_spend_usd"].sum() == 0  # :free variants priced at zero, not blended
        retired = daily.filter(pl.col("model_permaslug") == "x-ai/retired-model")
        assert not retired["price_matched"].any() and retired["est_spend_usd"].is_null().all()
        a = daily.filter(pl.col("model_permaslug").str.starts_with("anthropic")).row(0, named=True)
        assert a["est_spend_usd"] == pytest.approx(a["total_tokens"] * (0.8 * 3e-6 + 0.2 * 15e-6))
        assert a["vendor_id"] == "anthropic" and a["price_date_stale"]  # priced with a later snapshot
        weekly = query(con, "SELECT * FROM or_vendor_weekly WHERE vendor_id = 'xai'")
        assert (weekly["unpriced_tokens"] == weekly["tokens"]).all()
        assert query(con, "SELECT count(*) AS n FROM or_model_daily WHERE vendor_id = '_unmapped'")["n"][0] == 0
    finally:
        con.close()


def test_render_wallet_share_on_synthetic_data(synthetic_raw, monkeypatch):
    from cachereg.render import render
    from cachereg.viz import motion

    real = motion.Timing
    monkeypatch.setattr(motion, "Timing", lambda: real(fps=10, move_frames=2, hold_frames=1, final_hold_s=0.2))
    build(date(2026, 8, 31))
    result = render(WALLET, date(2026, 8, 31), ["x_png", "blog_html", "linkedin_video"])
    out = result["out_dir"]
    assert (out / "x_png.png").stat().st_size > 10_000
    html = (out / "blog_html.html").read_text()
    assert "OpenRouter (openrouter.ai/rankings), as of 2026-08-31" in html  # required citation
    assert (out / "linkedin_video.mp4").stat().st_size > 10_000
    manifest = json.loads((out / "run_manifest.json").read_text())
    text = json.dumps(manifest)
    assert "/Users/" not in text and "/home/" not in text  # repo-relative only
    assert manifest["sources"]["openrouter_rankings"]["class"] == "Latest-only"
    assert "Anthropic" in result["title"]


def test_snapshot_source_never_backfills_but_revised_source_does(synthetic_raw):
    from cachereg.build import VintageGapError, cutoff

    before = date(2026, 8, 1)  # both synthetic fetches are dated 2026-08-31
    day, after = cutoff("openrouter_rankings", before)  # Latest-only: fall back, flagged
    assert day == date(2026, 8, 31) and after
    with pytest.raises(VintageGapError, match="snapshot"):
        cutoff("openrouter_models", before)  # Author-only: report the gap


def test_duplicate_catalog_slug_does_not_multiply_tokens(synthetic_raw):
    from datetime import UTC, datetime

    from cachereg.core.store import RawFetch
    from tests.conftest import synthetic_models

    models = synthetic_models()
    base = models["data"][0]
    models["data"].append(dict(base, id=base["id"] + ":batch", pricing={"prompt": "1e-9", "completion": "1e-9"}))
    m = RawFetch("openrouter_models", "1", fetched_at=datetime(2026, 8, 31, 13, tzinfo=UTC))
    m.add("models.json", json.dumps(models).encode(), "https://example.test", 200)
    m.write()
    build(date(2026, 8, 31))
    con = connect()
    try:
        n = query(con, "SELECT count(*) AS n FROM or_model_daily")["n"][0]
        px = query(
            con,
            "SELECT DISTINCT prompt_usd_per_token AS p FROM or_model_daily WHERE model_permaslug = ?",
            [base["canonical_slug"]],
        )["p"].to_list()
    finally:
        con.close()
    assert n == 91 * 7  # no fan-out
    assert px == [float(base["pricing"]["prompt"])]  # base price, not the :batch variant


def test_headline_verb_follows_the_data():
    from cachereg.render import load_analysis

    analysis, _ = load_analysis(WALLET)
    assert analysis.headline(0.69, 0.32, 12).startswith("Anthropic's share of OpenRouter spend fell from 69%")
    assert " rose from 20% to 35% in 1 week" in analysis.headline(0.20, 0.35, 1)
    assert "held at 50%" in analysis.headline(0.501, 0.499, 3)


def test_build_refuses_half_the_inputs_and_drops_stale_marts(synthetic_raw):
    import shutil

    from cachereg.core.paths import raw_dir

    build(date(2026, 8, 31))  # marts exist
    shutil.rmtree(raw_dir("openrouter_models"))
    with pytest.raises(RuntimeError, match="openrouter_models"):
        build(date(2026, 8, 31))
    con = connect()
    try:
        tables = set(query(con, "SELECT table_name FROM information_schema.tables")["table_name"])
    finally:
        con.close()
    assert "or_vendor_weekly" not in tables  # a stale mart can't be reused


def test_encode_reports_ffmpeg_failure(tmp_path, monkeypatch):
    import io as _io

    from PIL import Image

    from cachereg.viz import motion
    from cachereg.viz.layout import Frame

    buf = _io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    page = Frame(Image.new("RGB", (16, 16)), (0, 0, 8, 8))
    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        motion.encode([buf.getvalue()] * 300, page, tmp_path / "no-such-dir" / "x.mp4", fps=10)
