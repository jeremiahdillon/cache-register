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
