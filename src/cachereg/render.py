"""`cachereg render`: a receipt or exploration → every declared visual × target, plus a manifest.

Receipts render into their committed `output/` folder at the pinned `as_of`; explorations render
into gitignored `outputs/`. See docs/plans/2026-10-03-explore-and-receipts.md.

Chart contract (functions in the folder's charts.py, named by a visual's `chart:`):
* static/HTML: ``<chart>(story, width, height, font_scale, interactive=False) -> alt.Chart``
* video:       ``<chart>_specs(story, width, height, font_scale, cfg) -> (list[dict], fps)``
Optional in analysis.py: ``table(story) -> pl.DataFrame`` (HTML data table) and
``TABLE_PERCENT_COLUMNS`` (columns shown as percentages).
"""

from __future__ import annotations

import hashlib
import html
import importlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import vl_convert as vlc

from cachereg import __version__
from cachereg.build import cutoff
from cachereg.core.paths import REPO_ROOT, outputs_dir, repo_relative
from cachereg.core.registry import load_sources, reproducibility_class
from cachereg.core.store import list_fetches
from cachereg.core.warehouse import connect
from cachereg.story import config as folder_config
from cachereg.story.hashing import data_hash, inputs_hash
from cachereg.story.model import TARGETS, Story, Target
from cachereg.viz import motion
from cachereg.viz.brand import brand, color, register_fonts
from cachereg.viz.layout import page
from cachereg.viz.stamp import Receipt, receipt

ALLOWED = {"allowed", "allowed-with-attribution"}
HTML_TEMPLATE = REPO_ROOT / "assets" / "templates" / "story.html"
MANIFEST = "manifest.json"


@dataclass
class RenderResult:
    out_dir: Path
    title: str
    as_of: date
    skipped: bool = False  # receipt outputs already up to date
    outputs: dict[str, str] = field(default_factory=dict)  # file -> sha256
    withheld: dict[str, str] = field(default_factory=dict)  # file -> reason
    manifest: dict = field(default_factory=dict)


def load_analysis(path: Path):
    """Import a folder's analysis.py and charts.py (folders aren't packages)."""
    sys.path.insert(0, str(path))
    try:
        for name in ("analysis", "charts"):
            sys.modules.pop(name, None)
        return importlib.import_module("analysis"), importlib.import_module("charts")
    finally:
        sys.path.remove(str(path))


def build_story(cfg: folder_config.FolderConfig, as_of: date):
    analysis, charts = load_analysis(cfg.path)
    con = connect()
    try:
        story: Story = analysis.build(con, as_of, cfg.config)
    finally:
        con.close()
    return story, analysis, charts


# ---- licensing ----------------------------------------------------------------------------


def licence_gate(source_ids) -> tuple[str | None, str | None]:
    """(reason images/video are blocked, reason data/HTML is blocked) — None means allowed."""
    sources = load_sources()
    charts_blocked = [s for s in source_ids if sources[s].derived_charts not in ALLOWED]
    data_blocked = [s for s in source_ids if sources[s].redistribution not in ALLOWED]
    charts_reason = f"derived_charts not allowed for: {', '.join(charts_blocked)}" if charts_blocked else None
    data_reason = f"redistribution not confirmed for: {', '.join(data_blocked)}" if data_blocked else None
    return charts_reason, data_reason or charts_reason


# ---- target renderers -------------------------------------------------------------------


def _chart_fn(charts, name: str, kind: str):
    fn_name = f"{name}_specs" if kind == "video" else name
    fn = getattr(charts, fn_name, None)
    if not callable(fn):
        raise ValueError(f"charts.py has no {fn_name}() for a {kind} target")
    return fn


def render_static(story, chart, target: Target, rec: Receipt, out: Path) -> None:
    if target.fmt != "png":
        raise ValueError(f"static target {target.name!r}: only PNG is supported (got {target.fmt!r})")
    frame = page(story, target, rec)
    _, _, w, h = frame.plot_box
    spec = chart(story, w, h, target.font_scale).to_dict()
    frame.compose(vlc.vegalite_to_png(vl_spec=json.dumps(spec), scale=1)).save(out, optimize=True)


def render_video(story, chart_specs, target: Target, rec: Receipt, out: Path, cfg: dict) -> None:
    frame = page(story, target, rec)
    _, _, w, h = frame.plot_box
    specs, fps = chart_specs(story, w, h, target.font_scale, cfg)
    motion.encode(motion.render_frames_vlconvert(specs), frame, out, fps, target.fmt)


def _table_html(analysis, story) -> str:
    table_fn = getattr(analysis, "table", None)
    if not callable(table_fn):
        return ""
    df: pl.DataFrame = table_fn(story)
    pct = set(getattr(analysis, "TABLE_PERCENT_COLUMNS", ()))

    def cell(col, v):
        if v is None:
            return ""
        if col in pct and isinstance(v, (int, float)):
            return f"{v:.1%}"
        if isinstance(v, float):
            return f"{v:,.4g}"
        return html.escape(str(v))

    head = "".join(f"<th>{html.escape(c)}</th>" for c in df.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell(c, r[c])}</td>" for c in df.columns) + "</tr>" for r in df.iter_rows(named=True)
    )
    return f"<details><summary>Data table</summary><table><tr>{head}</tr>{body}</table></details>"


def render_html(story, analysis, chart, target: Target, rec: Receipt, out: Path) -> None:
    spec = chart(story, "container", target.height, 1.0, interactive=True).to_dict()
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
        table=_table_html(analysis, story),
        caveats="".join(f"<li>{html.escape(c)}</li>" for c in story.caveats),
        bundle=vlc.javascript_bundle(),
        spec=json.dumps(spec),
    )
    out.write_text(page_html, encoding="utf-8")


# ---- manifest -------------------------------------------------------------------------------


def _git_sha() -> tuple[str, bool]:
    def run(*a):
        return subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()

    return run("rev-parse", "HEAD"), bool(run("status", "--porcelain"))


def source_vintages(source_ids, as_of: date) -> dict:
    sources = load_sources()
    out = {}
    for sid in source_ids:
        day, after = cutoff(sid, as_of)  # same selection rule as the build
        latest = [f for f in list_fetches(sid) if f.fetched_at.date() == day][-1]
        out[sid] = {
            "class": reproducibility_class(sources[sid]),
            "fetch_date": str(day),
            "vintage_after_as_of": after,
            "vintage": latest.manifest.get("vintage"),
            "content_sha256": hashlib.sha256(json.dumps(latest.manifest["files"], sort_keys=True).encode()).hexdigest(),
        }
    return out


def read_manifest(out_dir: Path) -> dict | None:
    f = out_dir / MANIFEST
    return json.loads(f.read_text()) if f.is_file() else None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _data_as_of(story: Story) -> str:
    """Latest data as-of reported by the story's sources themselves (for citations); else the analysis as-of."""
    values = []
    for sid in story.sources:
        fetches = [f for f in list_fetches(sid) if f.fetched_at.date() <= story.as_of]
        v = (fetches[-1].manifest.get("vintage") or {}) if fetches else {}
        if v.get("kind") == "api_as_of" and v.get("value"):
            values.append(v["value"][:10])
    return max(values) if values else str(story.as_of)


# ---- entry point ------------------------------------------------------------------------------


def render(
    folder: Path,
    as_of: date | None = None,
    *,
    targets: list[str] | None = None,
    force: bool = False,
    out_dir: Path | None = None,
) -> RenderResult:
    """Render a receipt or exploration.

    For a receipt with no ``out_dir``, outputs go to ``<receipt>/output/`` (committed): ``as_of``
    defaults to the pinned date and, if given and different, is written back to receipt.yaml;
    nothing is rewritten when the data and render-inputs hashes match the committed manifest,
    unless ``force``. ``out_dir`` renders anywhere else (e.g. a temp folder for ``reproduce``).
    """
    register_fonts()
    cfg = folder_config.load(Path(folder))
    is_receipt = cfg.kind == "receipt"
    committing = is_receipt and out_dir is None
    if is_receipt and targets and committing:
        raise ValueError("receipt outputs are rendered as a whole; use --targets only with explorations")
    as_of = as_of or cfg.as_of or datetime.now(UTC).date()

    story, analysis, charts = build_story(cfg, as_of)
    d_hash, i_hash = data_hash(story.frames), inputs_hash(cfg.path)
    rel = repo_relative(cfg.path)
    if out_dir is None:
        out_dir = cfg.path / "output" if is_receipt else outputs_dir() / cfg.path.name / str(as_of)
    result = RenderResult(out_dir=out_dir, title=story.title, as_of=as_of)

    if committing:
        prev = read_manifest(out_dir)
        if (
            prev
            and not force
            and prev.get("as_of") == str(as_of)
            and prev.get("data_hash") == d_hash
            and prev.get("inputs_hash") == i_hash
        ):
            result.skipped, result.manifest = True, prev
            return result
        if as_of != cfg.as_of:
            folder_config.set_as_of(cfg, as_of)
            i_hash = inputs_hash(cfg.path)

    charts_reason, data_reason = licence_gate(story.sources) if is_receipt else (None, None)
    rec = receipt(story.sources, _data_as_of(story), story.method, rel, cfg.link)
    out_dir.mkdir(parents=True, exist_ok=True)
    if committing:
        for old in out_dir.iterdir():  # outputs are regenerated as a set; no stale files survive
            if old.is_file():
                old.unlink()

    for visual in cfg.visuals:
        for name in visual.targets:
            if targets and name not in targets:
                continue
            target = TARGETS[name]
            out = out_dir / f"{visual.name}.{name}.{target.fmt}"
            blocked = data_reason if target.kind == "html" else charts_reason
            if blocked:
                result.withheld[out.name] = blocked
                continue
            chart = _chart_fn(charts, visual.chart, target.kind)
            if target.kind == "static":
                render_static(story, chart, target, rec, out)
            elif target.kind == "video":
                render_video(story, chart, target, rec, out, cfg.config)
            else:
                render_html(story, analysis, chart, target, rec, out)
            result.outputs[out.name] = _sha256(out)

    frames_json = json.dumps(
        {k: v.with_columns(pl.all().cast(pl.String)).to_dicts() for k, v in sorted(story.frames.items())}, indent=1
    )
    if not is_receipt:
        (out_dir / "story_frames.json").write_text(frames_json)  # gitignored outputs/: for inspection
    elif data_reason:
        result.withheld["data.json"] = data_reason
    else:
        (out_dir / "data.json").write_text(frames_json)
        result.outputs["data.json"] = _sha256(out_dir / "data.json")

    sha, dirty = _git_sha()
    result.manifest = {
        "kind": cfg.kind,
        "folder": rel,
        "as_of": str(as_of),
        "cache_register_version": __version__,
        "git_sha": sha,
        "git_dirty": dirty,
        "uv_lock_sha256": _sha256(REPO_ROOT / "uv.lock"),
        "data_hash": d_hash,
        "inputs_hash": i_hash,
        "sources": source_vintages(story.sources, as_of),
        "outputs": dict(sorted(result.outputs.items())),
        "withheld": dict(sorted(result.withheld.items())),
    }
    (out_dir / MANIFEST).write_text(json.dumps(result.manifest, indent=2, sort_keys=True) + "\n")
    return result
