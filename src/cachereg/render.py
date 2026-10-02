"""`cachereg render`: one analysis → every declared target, plus a sanitized run manifest (PLAN §6, §4.4)."""

from __future__ import annotations

import hashlib
import html
import importlib
import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import polars as pl
import vl_convert as vlc
import yaml

from cachereg import __version__
from cachereg.core.paths import REPO_ROOT, outputs_dir, repo_relative
from cachereg.core.registry import load_sources
from cachereg.core.store import list_fetches
from cachereg.core.warehouse import connect
from cachereg.story.model import TARGETS, Story, Target
from cachereg.viz import motion
from cachereg.viz.brand import brand, color, register_fonts
from cachereg.viz.layout import page
from cachereg.viz.stamp import receipt


def load_analysis(path: Path):
    """Import an analysis folder's analysis.py and charts.py (folders aren't packages)."""
    sys.path.insert(0, str(path))
    try:
        for name in ("analysis", "charts"):
            sys.modules.pop(name, None)
        return importlib.import_module("analysis"), importlib.import_module("charts")
    finally:
        sys.path.remove(str(path))


def _git_sha() -> tuple[str, bool]:
    def run(*a):
        return subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()

    return run("rev-parse", "HEAD"), bool(run("status", "--porcelain"))


def _manifest(story: Story, analysis_path: Path, outputs: dict[str, str], timings: dict) -> dict:
    sha, dirty = _git_sha()
    sources = load_sources()
    vintages = {}
    for sid in story.sources:
        fetches = [f for f in list_fetches(sid) if f.fetched_at.date() <= story.as_of] or list_fetches(sid)[:1]
        latest = fetches[-1] if fetches else None
        vintages[sid] = {
            "class": {
                "revised": "Latest-only",
                "none": "Author-only" if sources[sid].history == "snapshot" else "Exact",
                "append-only": "Exact",
            }[sources[sid].revisions],
            "fetch_date": str(latest.fetched_at.date()) if latest else None,
            "vintage": latest.manifest.get("vintage") if latest else None,
            "content_sha256": hashlib.sha256(json.dumps(latest.manifest["files"], sort_keys=True).encode()).hexdigest()
            if latest
            else None,
        }
    lock = (REPO_ROOT / "uv.lock").read_bytes()
    return {
        "analysis": repo_relative(analysis_path),
        "as_of": str(story.as_of),
        "cache_register_version": __version__,
        "git_sha": sha,
        "git_dirty": dirty,
        "uv_lock_sha256": hashlib.sha256(lock).hexdigest(),
        "sources": vintages,
        "outputs": outputs,
        "render_seconds": timings,
    }


# ---- target renderers -------------------------------------------------------------------


def render_static(story, charts, target: Target, rec, out: Path) -> None:
    frame = page(story, target, rec)
    _, _, w, h = frame.plot_box
    spec = charts.line_chart(story, w, h, target.font_scale).to_dict()
    png = vlc.vegalite_to_png(vl_spec=json.dumps(spec), scale=1)
    frame.compose(png).save(out, optimize=True)


def render_video(story, charts, target: Target, rec, out: Path, cfg: dict) -> None:
    frame = page(story, target, rec)
    _, _, w, h = frame.plot_box
    top_n = cfg.get("race_top_n", 8)
    keys = charts.race_keyframes(story, top_n)
    groups = dict(zip(keys["vendor_name"], keys["group"], strict=False))
    timing = motion.Timing()
    frames = motion.bar_race_frames(keys, "vendor_name", "share", "week", top_n, timing)
    x_max = round(keys["share"].max() * 1.22, 2)
    specs = motion.build_specs(frames, lambda f: charts.race_spec(f, groups, w, h, target.font_scale, top_n, x_max))
    pngs = motion.render_frames_vlconvert(specs)
    motion.encode(pngs, frame, out, timing.fps, target.fmt)


HTML_TEMPLATE = REPO_ROOT / "assets" / "templates" / "story.html"


def render_html(story, charts, target: Target, rec, out: Path) -> None:
    spec = charts.line_chart(story, "container", target.height, 1.0, interactive=True).to_dict()
    groups = story.frames["groups"]
    pivot = groups.pivot(on="group", index="week", values="share").sort("week")
    cols = ["week", *[c for c in charts.GROUP_ORDER if c in pivot.columns]]
    table = (
        "<table><tr>"
        + "".join(f"<th>{html.escape(c)}</th>" for c in cols)
        + "</tr>"
        + "".join(
            "<tr>"
            + "".join(f"<td>{r[c]:.1%}</td>" if isinstance(r[c], float) else f"<td>{r[c]}</td>" for c in cols)
            + "</tr>"
            for r in pivot.select(cols).to_dicts()
        )
        + "</table>"
    )
    rec_html = "<br>".join(
        f"<b>{label}</b>{html.escape(text) if label != 'RECEIPTS' else f'<a href=https://{text}>{html.escape(text)}</a>'}"
        for label, text in rec.lines()
    )
    page_html = HTML_TEMPLATE.read_text(encoding="utf-8").format(
        title=html.escape(story.title),
        subtitle=html.escape(story.subtitle),
        brand_name=brand()["name"].upper(),
        canvas=color("canvas"),
        ink=color("text"),
        ink2=color("text_secondary"),
        muted=color("muted"),
        signal=color("signal"),
        receipt_html=rec_html,
        table=table,
        caveats="".join(f"<li>{html.escape(c)}</li>" for c in story.caveats),
        bundle=vlc.javascript_bundle(),
        spec=json.dumps(spec),
    )
    out.write_text(page_html, encoding="utf-8")


def render(analysis_path: Path, as_of: date, only: list[str] | None = None) -> dict:
    register_fonts()
    analysis_path = analysis_path.resolve()
    cfg = yaml.safe_load((analysis_path / "story.yaml").read_text())
    analysis, charts = load_analysis(analysis_path)
    con = connect()
    try:
        story: Story = analysis.build(con, as_of, cfg)
    finally:
        con.close()
    rel = repo_relative(analysis_path)
    rec = receipt(story.sources, _data_as_of(story), story.method, rel)
    out_dir = outputs_dir() / analysis_path.name / str(as_of)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs, timings = {}, {}
    for name in only or cfg["targets"]:
        target = TARGETS[name]
        out = out_dir / f"{name}.{target.fmt}"
        t0 = time.perf_counter()
        if target.kind == "static":
            render_static(story, charts, target, rec, out)
        elif target.kind == "video":
            render_video(story, charts, target, rec, out, cfg)
        else:
            render_html(story, charts, target, rec, out)
        timings[name] = round(time.perf_counter() - t0, 1)
        outputs[name] = out.name
    manifest = _manifest(story, analysis_path, outputs, timings)
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out_dir / "story_frames.json").write_text(
        json.dumps({k: v.with_columns(pl.all().cast(pl.String)).to_dicts() for k, v in story.frames.items()}, indent=1)
    )
    return {"out_dir": out_dir, "outputs": outputs, "timings": timings, "title": story.title}


def _data_as_of(story: Story) -> str:
    """Latest data as-of reported by the story's sources themselves (for citations); else the analysis as-of."""
    values = []
    for sid in story.sources:
        fetches = [f for f in list_fetches(sid) if f.fetched_at.date() <= story.as_of]
        v = (fetches[-1].manifest.get("vintage") or {}) if fetches else {}
        if v.get("kind") == "api_as_of" and v.get("value"):
            values.append(v["value"][:10])
    return max(values) if values else str(story.as_of)
