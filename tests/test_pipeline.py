"""End-to-end on synthetic data: raw → staged → marts → story → rendered targets."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from cachereg.build import build
from cachereg.core.warehouse import connect, query
from cachereg.sources.openrouter_rankings.fetch import month_windows

ROOT = Path(__file__).resolve().parents[1]
WALLET = ROOT / "receipts" / "openrouter-wallet-share"


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
        assert a["vendor_id"] == "anthropic" and a["price_basis"] == "current" and not a["price_date_stale"]
        assert daily.height == daily.select("date", "model_permaslug").unique().height  # no fan-out

        def row(slug, day):
            return daily.filter((pl.col("model_permaslug") == slug) & (pl.col("date") == day)).row(0, named=True)

        before, after = date(2026, 7, 14), date(2026, 7, 15)  # synthetic LiteLLM commit on Jul 15
        # preferred key not listed yet: the rank-2 key that *is* listed that day wins, unflagged
        o = row("openai/gpt-9-20260101", before)
        assert (o["price_key"], o["price_basis"], o["prompt_usd_per_token"]) == ("gpt-9-20260101", "current", 1.25e-6)
        o = row("openai/gpt-9-20260101", after)
        assert (o["price_key"], o["prompt_usd_per_token"]) == ("openrouter/openai/gpt-9", 1e-6)
        assert o["price_commit"] == "c_mid"
        k = row("moonshotai/kimi-9", before)  # not in LiteLLM yet: first later listing, flagged
        assert k["price_basis"] == "before_listing" and k["price_date_stale"] and k["prompt_usd_per_token"] == 0.6e-6
        assert row("moonshotai/kimi-9", after)["price_basis"] == "current"
        g = row("google/gemini-9-pro", after)  # removed upstream: last known price, flagged
        assert g["price_basis"] == "after_removal" and g["price_date_stale"] and g["prompt_usd_per_token"] == 1.25e-6
        weekly = query(con, "SELECT * FROM or_vendor_weekly WHERE vendor_id = 'xai'")
        assert (weekly["unpriced_tokens"] == weekly["tokens"]).all()
        kimi = query(con, "SELECT * FROM or_vendor_weekly WHERE vendor_id = 'moonshot' ORDER BY week")
        assert kimi["stale_priced_tokens"][0] == kimi["tokens"][0] and kimi["stale_priced_tokens"][-1] == 0
        assert query(con, "SELECT count(*) AS n FROM or_model_daily WHERE vendor_id = '_unmapped'")["n"][0] == 0
    finally:
        con.close()


def _fast_video(monkeypatch):
    from cachereg.viz import motion

    real = motion.Timing
    monkeypatch.setattr(motion, "Timing", lambda: real(fps=10, move_frames=2, hold_frames=1, final_hold_s=0.2))


def _receipt_copy(tmp_path) -> Path:
    """A copy of the real receipt (code + config) in a temp repo-like folder, without its outputs."""
    import shutil

    dest = tmp_path / "receipts" / "openrouter-wallet-share"
    dest.mkdir(parents=True)
    for name in ("analysis.py", "charts.py", "receipt.yaml"):
        shutil.copy(WALLET / name, dest / name)
    text = (dest / "receipt.yaml").read_text()
    (dest / "receipt.yaml").write_text(re.sub(r"(?m)^as_of:.*$", "as_of: 2026-08-31", text))
    return dest


def test_render_receipt_on_synthetic_data(synthetic_raw, monkeypatch, tmp_path):
    from cachereg.render import render

    _fast_video(monkeypatch)
    build(date(2026, 8, 31))
    receipt = _receipt_copy(tmp_path)
    result = render(receipt)
    out = receipt / "output"
    assert result.out_dir == out and not result.skipped
    assert (out / "share-lines.x_png.png").stat().st_size > 10_000
    assert (out / "share-race.linkedin_video.mp4").stat().st_size > 10_000
    # licence gate: both sources allow redistribution with attribution -> HTML and data committed
    assert (out / "share-lines.blog_html.html").exists() and (out / "data.json").exists()
    assert not (out / "story_frames.json").exists()
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["withheld"] == {}
    text = json.dumps(manifest)
    assert "/Users/" not in text and "/home/" not in text  # repo-relative only
    assert manifest["sources"]["openrouter_rankings"]["class"] == "Latest-only"
    lp = manifest["sources"]["litellm_prices"]
    assert lp["class"] == "Exact" and "fetch_date" not in lp and lp["revision_date"] == "2026-08-30"
    assert lp["vintage"] == {"kind": "git_commit", "value": "c_mid", "date": "2026-08-30"}
    assert "Anthropic" in result.title
    # unchanged data and code -> nothing rewritten
    assert render(receipt).skipped


def test_exploration_renders_html_with_data_and_citation(synthetic_raw, tmp_path, monkeypatch):
    import shutil

    from cachereg.render import render

    monkeypatch.setenv("CACHEREG_OUTPUTS_DIR", str(tmp_path / "outputs"))
    build(date(2026, 8, 31))
    ex = tmp_path / "explore" / "2026-08-01-test"
    ex.mkdir(parents=True)
    for name in ("analysis.py", "charts.py"):
        shutil.copy(WALLET / name, ex / name)
    (ex / "explore.yaml").write_text(
        "sources: [openrouter_rankings, litellm_prices]\n"
        "config: {weeks: 13, unpriced_flag: 0.03, race_top_n: 8}\n"
        "visuals:\n  - {name: share-lines, chart: line_chart, targets: [blog_html]}\n"
    )
    result = render(ex, date(2026, 8, 31))
    html = (result.out_dir / "share-lines.blog_html.html").read_text()
    assert "OpenRouter (openrouter.ai/rankings), as of 2026-08-31" in html  # required citation
    assert "cacheregister.dev" not in html  # explorations have no short link
    assert (result.out_dir / "story_frames.json").exists() and not result.withheld


def _add_source(receipt: Path, sid: str) -> None:
    """Add a source to a receipt copy's receipt.yaml and its analysis (they must match)."""
    for name, old, new in (
        ("receipt.yaml", "litellm_prices]", f"litellm_prices, {sid}]"),
        ("analysis.py", '"litellm_prices"]', f'"litellm_prices", "{sid}"]'),
    ):
        f = receipt / name
        assert old in f.read_text()
        f.write_text(f.read_text().replace(old, new))


def test_reproduce_identical_then_differs(synthetic_raw, monkeypatch, tmp_path):
    from datetime import UTC, datetime

    from cachereg.core.store import RawFetch
    from cachereg.render import render
    from cachereg.reproduce import reproduce
    from tests.conftest import synthetic_rankings

    _fast_video(monkeypatch)
    build(date(2026, 8, 31))
    receipt = _receipt_copy(tmp_path)
    render(receipt)
    assert reproduce(receipt, no_fetch=True).status == "identical"

    revised = synthetic_rankings(date(2026, 6, 1), 91)
    revised["data"][0]["total_tokens"] = str(int(revised["data"][0]["total_tokens"]) * 3)  # a revision
    r = RawFetch("openrouter_rankings", "1", fetched_at=datetime(2026, 8, 31, 18, tzinfo=UTC))
    r.add("rankings.json", json.dumps(revised).encode(), "https://example.test", 200)
    r.write()
    result = reproduce(receipt, no_fetch=True)
    assert result.status == "differs"
    assert any("openrouter_rankings" in reason for reason in result.reasons)
    assert (receipt / "output" / "manifest.json").exists()  # committed outputs untouched


def test_reproduce_reports_missing_snapshot(synthetic_raw, monkeypatch, tmp_path):
    from cachereg.render import render
    from cachereg.reproduce import reproduce

    _fast_video(monkeypatch)
    build(date(2026, 8, 31))
    receipt = _receipt_copy(tmp_path)
    _add_source(receipt, "openrouter_models")  # a receipt that also uses a snapshot source
    render(receipt)
    text = (receipt / "receipt.yaml").read_text()
    (receipt / "receipt.yaml").write_text(re.sub(r"(?m)^as_of:.*$", "as_of: 2026-08-01", text))
    result = reproduce(receipt, no_fetch=True)
    assert result.status == "cannot-reproduce"
    assert "openrouter_models" in result.reasons[0] and "--latest" in result.reasons[0]


def test_build_sources_scope(synthetic_raw):
    report = build(date(2026, 8, 31), [])
    assert report.marts_built == [] and report.marts_skipped == ["005_openrouter_tokens", "010_openrouter_usage"]
    con = connect()
    try:
        tables = set(query(con, "SELECT table_name FROM information_schema.tables")["table_name"])
    finally:
        con.close()
    assert "or_vendor_weekly" not in tables  # skipped mart's tables are dropped, never stale
    with pytest.raises(RuntimeError, match="missing: openrouter_rankings"):
        build(date(2026, 8, 31), ["litellm_prices"])
    assert build(date(2026, 8, 31), ["openrouter_models"]).marts_skipped == [
        "005_openrouter_tokens",
        "010_openrouter_usage",
    ]
    tokens_only = build(date(2026, 8, 31), ["openrouter_rankings"])  # token mart runs; pricing mart skipped
    assert tokens_only.marts_built == ["005_openrouter_tokens"] and tokens_only.marts_skipped == [
        "010_openrouter_usage"
    ]
    assert build(date(2026, 8, 31), ["openrouter_rankings", "litellm_prices"]).marts_built == [
        "005_openrouter_tokens",
        "010_openrouter_usage",
    ]


def test_snapshot_source_never_backfills_but_revised_source_does(synthetic_raw):
    from cachereg.build import VintageGapError, cutoff

    before = date(2026, 8, 1)  # both synthetic fetches are dated 2026-08-31
    day, after = cutoff("openrouter_rankings", before)  # Latest-only: fall back, flagged
    assert day == date(2026, 8, 31) and after
    with pytest.raises(VintageGapError, match="snapshot"):
        cutoff("openrouter_models", before)  # Author-only: report the gap


def test_price_join_never_fans_out_and_ignores_post_as_of_data(synthetic_raw):
    # as_of before the synthetic LiteLLM commit of Jul 15: its entries must be invisible, so kimi
    # (listed only from Jul 15) is unpriced rather than priced from the future, and the two openai
    # keys can't both match.
    build(date(2026, 7, 1), ["openrouter_rankings", "litellm_prices"])
    con = connect()
    try:
        daily = query(con, "SELECT * FROM or_model_daily")
    finally:
        con.close()
    assert daily.height == daily.select("date", "model_permaslug").unique().height
    kimi = daily.filter(pl.col("model_permaslug") == "moonshotai/kimi-9")
    assert not kimi["price_matched"].any()
    assert set(daily.filter(pl.col("model_permaslug") == "openai/gpt-9-20260101")["price_key"]) == {"gpt-9-20260101"}


def test_dates_after_the_litellm_history_are_flagged(data_env, synthetic_entities):
    from datetime import UTC, datetime

    from cachereg.core.store import RawFetch
    from tests.conftest import synthetic_rankings, write_synthetic_litellm

    fetched = datetime(2026, 8, 31, 12, tzinfo=UTC)
    r = RawFetch("openrouter_rankings", "1", fetched_at=fetched)
    r.add("rankings.json", json.dumps(synthetic_rankings(date(2026, 6, 1), 91)).encode(), "https://example.test", 200)
    r.write()
    write_synthetic_litellm(datetime(2026, 8, 16, 6, tzinfo=UTC), date(2026, 8, 15))  # history ends Aug 15
    build(date(2026, 8, 31))
    con = connect()
    try:
        a = query(
            con,
            "SELECT date, price_basis, price_date_stale FROM or_model_daily WHERE model_permaslug LIKE 'anthropic%'",
        )
    finally:
        con.close()
    late = a.filter(pl.col("date") > date(2026, 8, 15))
    assert set(late["price_basis"]) == {"beyond_history"} and late["price_date_stale"].all()
    assert set(a.filter(pl.col("date") <= date(2026, 8, 15))["price_basis"]) == {"current"}


def test_exact_source_is_selected_by_source_time(synthetic_raw):
    from datetime import UTC, datetime

    from cachereg.build import cutoff, exact_vintage
    from tests.conftest import write_synthetic_litellm

    # A replicator's only fetch is long after as_of: no "vintage after as-of", same revision.
    assert exact_vintage("litellm_prices", date(2026, 7, 20)) == {
        "kind": "git_commit",
        "value": "c_mid",
        "date": "2026-07-20",
    }
    assert exact_vintage("litellm_prices", date(2026, 7, 1))["value"] == "c_early"
    assert exact_vintage("openrouter_rankings", date(2026, 7, 1)) is None  # other classes: unchanged
    write_synthetic_litellm(datetime(2026, 9, 20, 6, tzinfo=UTC), date(2026, 9, 19))
    assert cutoff("litellm_prices", date(2026, 7, 1)) == (date(2026, 8, 31), False)  # earliest covering
    assert cutoff("litellm_prices", date(2026, 9, 10)) == (date(2026, 9, 20), False)
    assert cutoff("litellm_prices", date(2026, 12, 1)) == (date(2026, 9, 20), False)  # none covers: latest


def test_long_windows_tick_on_month_starts():
    from cachereg.render import load_analysis

    _, charts = load_analysis(WALLET)
    weeks = [date(2025, 1, 6) + timedelta(weeks=i) for i in range(88)]
    ticks, label = charts.x_ticks(weeks)
    assert label == "%b '%y" and 1 < len(ticks) <= 8 and all(t.day == 1 for t in ticks)
    assert ticks[0] == date(2025, 2, 1) and ticks[-1] <= weeks[-1]
    short, label = charts.x_ticks(weeks[:13])
    assert label == "%b %-d" and short == weeks[:13:2]


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
    shutil.rmtree(raw_dir("litellm_prices"))
    with pytest.raises(RuntimeError, match="litellm_prices"):
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


def test_reproduce_leaves_the_authors_warehouse_alone(synthetic_raw, monkeypatch, tmp_path):
    from cachereg.render import render
    from cachereg.reproduce import reproduce

    _fast_video(monkeypatch)
    build(date(2026, 8, 31))
    receipt = _receipt_copy(tmp_path)
    render(receipt)
    import duckdb

    from cachereg.core.paths import warehouse_path

    with duckdb.connect(str(warehouse_path())) as rw:
        rw.execute("CREATE TABLE author_scratch AS SELECT 1 AS x")
    reproduce(receipt, no_fetch=True)
    con = connect()
    try:
        tables = set(query(con, "SELECT table_name FROM information_schema.tables")["table_name"])
    finally:
        con.close()
    assert {"author_scratch", "or_vendor_weekly"} <= tables


def test_reproduce_rejects_sources_that_dont_cover_the_marts(synthetic_raw, tmp_path):
    from cachereg.reproduce import check_mart_coverage
    from cachereg.story import config as folder_config

    receipt = _receipt_copy(tmp_path)
    text = (receipt / "receipt.yaml").read_text()
    (receipt / "receipt.yaml").write_text(
        text.replace("sources: [openrouter_rankings, litellm_prices]", "sources: [openrouter_rankings]")
    )
    with pytest.raises(ValueError, match="add litellm_prices"):
        check_mart_coverage(folder_config.load(receipt))


def test_receipt_sources_must_match_story_sources(synthetic_raw, monkeypatch, tmp_path):
    from cachereg.render import render

    build(date(2026, 8, 31))
    receipt = _receipt_copy(tmp_path)
    analysis = receipt / "analysis.py"
    analysis.write_text(
        analysis.read_text().replace(
            'sources=["openrouter_rankings", "litellm_prices"]', 'sources=["openrouter_rankings"]'
        )
    )
    with pytest.raises(ValueError, match="differ from the analysis"):
        render(receipt)


def test_reproduce_reports_fetch_failure_by_source(synthetic_raw, monkeypatch, tmp_path):
    from cachereg.render import render
    from cachereg.reproduce import reproduce

    _fast_video(monkeypatch)
    build(date(2026, 8, 31))
    receipt = _receipt_copy(tmp_path)
    render(receipt)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("CACHEREG_SECRETS_FILE", str(tmp_path / "none.env"))
    result = reproduce(receipt)  # fetch needs a key that isn't set
    assert result.status == "fetch-failed"
    assert result.reasons[0].startswith("fetch failed for openrouter_rankings: MissingSecretError")


def test_flagged_days_use_the_nearest_listing_before_preference_order(data_env, synthetic_entities):
    """Before any key is listed, the earliest listing of *any* of the model's keys prices it (a later
    rank-1 listing may carry a different, later price); once listed, preference order decides."""
    from datetime import UTC, datetime

    import yaml

    from cachereg.core.store import RawFetch
    from tests.conftest import synthetic_rankings

    models = yaml.safe_load((synthetic_entities / "models.yaml").read_text())
    models["models"]["moonshotai/kimi-9"]["aliases"]["litellm"] = ["openrouter/moonshotai/kimi-9", "moonshot/kimi-9"]
    (synthetic_entities / "models.yaml").write_text(yaml.safe_dump(models))

    fetched = datetime(2026, 8, 31, 12, tzinfo=UTC)
    r = RawFetch("openrouter_rankings", "1", fetched_at=fetched)
    r.add("rankings.json", json.dumps(synthetic_rankings(date(2026, 6, 1), 91)).encode(), "https://example.test", 200)
    r.write()

    def entry(i, o):
        return {"input_cost_per_token": i, "output_cost_per_token": o}

    states = {  # sha -> (commit day, file)
        "c1": (date(2024, 12, 31), {"other": entry(1e-6, 1e-6)}),
        "c2": (date(2026, 7, 1), {"moonshot/kimi-9": entry(0.5e-6, 2e-6)}),  # vendor key first
        "c3": (
            date(2026, 8, 1),
            {"moonshot/kimi-9": entry(0.5e-6, 2e-6), "openrouter/moonshotai/kimi-9": entry(2e-6, 8e-6)},
        ),
    }
    lp = RawFetch("litellm_prices", "1", fetched_at=fetched)
    ts = {
        s: int(datetime.combine(d, datetime.min.time(), tzinfo=UTC).timestamp()) + 3600 for s, (d, _) in states.items()
    }
    lp.add("first_parent.tsv", "".join(f"{s}\t{ts[s]}\n" for s in ("c3", "c2", "c1")).encode(), "https://x.test", 200)
    for s, (_, body) in states.items():
        lp.add(f"prices_{s}.json", json.dumps(body).encode(), "https://x.test", 200)
    lp.vintage = {"kind": "git_commit", "value": "c3", "window": ["2025-01-01", "2026-08-30"]}
    lp.write()

    build(date(2026, 8, 31), ["openrouter_rankings", "litellm_prices"])
    con = connect()
    try:
        k = query(
            con, "SELECT date, price_key, price_basis FROM or_model_daily WHERE model_permaslug = 'moonshotai/kimi-9'"
        )
    finally:
        con.close()

    def at(day):
        return k.filter(pl.col("date") == day).row(0, named=True)

    assert (at(date(2026, 6, 15))["price_key"], at(date(2026, 6, 15))["price_basis"]) == (
        "moonshot/kimi-9",
        "before_listing",
    )
    assert (at(date(2026, 7, 15))["price_key"], at(date(2026, 7, 15))["price_basis"]) == ("moonshot/kimi-9", "current")
    assert (at(date(2026, 8, 15))["price_key"], at(date(2026, 8, 15))["price_basis"]) == (
        "openrouter/moonshotai/kimi-9",
        "current",
    )


def test_licence_gate_charts_need_explicit_forbidden_data_needs_explicit_allowed(tmp_path, monkeypatch):
    from cachereg import render as render_mod
    from cachereg.core.registry import load_sources

    reg = tmp_path / "sources.yaml"
    base = "history: snapshot\n    revisions: none\n    attribution: x\n    cadence: daily\n    requires: []\n"
    reg.write_text(
        "sources:\n"
        f"  - id: a\n    redistribution: unknown\n    derived_charts: unknown\n    {base}"
        f"  - id: b\n    redistribution: allowed\n    derived_charts: forbidden\n    {base}"
    )
    monkeypatch.setattr(render_mod, "load_sources", lambda: load_sources(reg))
    assert render_mod.licence_gate(["a"]) == (None, "redistribution not allowed for: a")
    charts, data = render_mod.licence_gate(["b"])
    assert charts == "derived_charts forbidden for: b" and data == charts  # no data where no charts


def test_published_floats_are_rounded_but_the_data_hash_is_not(synthetic_raw, tmp_path, monkeypatch):
    from cachereg.render import FLOAT_SIG_FIGS, build_story, render
    from cachereg.story import config as folder_config
    from cachereg.story.hashing import data_hash

    _fast_video(monkeypatch)
    build(date(2026, 8, 31))
    receipt = _receipt_copy(tmp_path)
    story, _, _ = build_story(folder_config.load(receipt), date(2026, 8, 31))
    result = render(receipt)
    assert result.manifest["data_hash"] == data_hash(story.frames)  # hash of the unrounded data
    shares = [float(r["share"]) for r in json.loads((receipt / "output" / "data.json").read_text())["groups"]]
    assert shares and all(float(f"{s:.{FLOAT_SIG_FIGS}g}") == s for s in shares)


def test_git_dirty_ignores_the_output_folder_being_written(tmp_path, monkeypatch):
    import subprocess

    from cachereg import render as render_mod

    repo = tmp_path / "repo"
    (repo / "receipts" / "t" / "output").mkdir(parents=True)
    (repo / "a.txt").write_text("a")
    for args in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    monkeypatch.setattr(render_mod, "REPO_ROOT", repo)
    monkeypatch.setattr("cachereg.core.paths.REPO_ROOT", repo)
    out = repo / "receipts" / "t" / "output"
    (out / "x.png").write_bytes(b"new output")
    assert render_mod._git_sha(out)[1] is False  # only the output folder changed
    assert render_mod._git_sha()[1] is True
    (repo / "a.txt").write_text("edited")
    assert render_mod._git_sha(out)[1] is True
