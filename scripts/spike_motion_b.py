"""Phase 0.5 motion spike: renderer A (vl-convert per frame) vs B (one live Vega view in headless Chrome).

Both render the *same* Altair spec from the analysis's charts.race_spec; B swaps each frame's rows into
named datasets instead of re-parsing a spec. Decision rule (PLAN §6.3): frames must match visually;
the faster wins; tie → A. Usage:

    uv run --group spike python scripts/spike_motion_b.py analyses/explore/2026-10-02-openrouter-wallet-share
"""

from __future__ import annotations

import io
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import vl_convert as vlc
import yaml
from PIL import Image, ImageChops

from cachereg.core.paths import REPO_ROOT
from cachereg.core.warehouse import connect
from cachereg.render import load_analysis
from cachereg.story.model import TARGETS
from cachereg.viz import motion
from cachereg.viz.brand import FONT_DIR, register_fonts
from cachereg.viz.layout import page
from cachereg.viz.stamp import receipt

FONT_FACES = "\n".join(
    f"@font-face{{font-family:'{fam}';src:url('{(FONT_DIR / f).as_uri()}');font-weight:{w}}}"
    for fam, f, w in [
        ("Inter", "Inter-Regular.ttf", 400),
        ("Inter", "Inter-SemiBold.ttf", 600),
        ("JetBrains Mono", "JetBrainsMono-Regular.ttf", 400),
        ("Space Grotesk", "SpaceGrotesk-Bold.ttf", 700),
    ]
)


def named(spec: dict) -> dict:
    """Point the bar/label layers at dataset 'frame' and the week stamp at dataset 'stamp'."""
    spec = json.loads(json.dumps(spec))
    for i, layer in enumerate(spec["layer"]):
        layer["data"] = {"name": "stamp" if i == 2 else "frame"}
    return spec


def main(analysis_dir: str) -> None:
    from playwright.sync_api import sync_playwright

    register_fonts()
    path = Path(analysis_dir).resolve()
    cfg = yaml.safe_load((path / "story.yaml").read_text())
    analysis, charts = load_analysis(path)
    con = connect()
    story = analysis.build(con, datetime.now(UTC).date(), cfg)
    con.close()
    target = TARGETS["linkedin_video"]
    frame_page = page(story, target, receipt(story.sources, story.as_of, story.method, "x"))
    _, _, w, h = frame_page.plot_box
    top_n = cfg["race_top_n"]
    keys = charts.race_keyframes(story, top_n)
    groups = dict(zip(keys["vendor_name"], keys["group"], strict=False))
    frames = motion.bar_race_frames(keys, "vendor_name", "share", "week", top_n)
    x_max = round(keys["share"].max() * 1.22, 2)
    specs = motion.build_specs(frames, lambda f: charts.race_spec(f, groups, w, h, target.font_scale, top_n, x_max))
    n = len(specs)

    t0 = time.perf_counter()
    a_pngs = motion.render_frames_vlconvert(specs)
    t_a = time.perf_counter() - t0

    html = (
        f"<html><head><style>{FONT_FACES} body{{margin:0;background:#0A0B0F}}</style></head>"
        f"<body><div id=c></div><script>{vlc.javascript_bundle()}</script></body></html>"
    )
    tmp = REPO_ROOT / "outputs" / "_spike_b.html"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(html)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        try:
            pg = browser.new_page(viewport={"width": w, "height": h})
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.evaluate(
                "async (spec) => { window.view ="
                " (await vegaEmbed('#c', spec, {actions:false, renderer:'canvas'})).view; }",
                named(specs[0]),
            )
            t0 = time.perf_counter()
            b_pngs = []
            for i in range(n):
                rows = specs[i]["layer"][0]["data"]["values"]
                stamp = specs[i]["layer"][2]["data"]["values"]
                url = pg.evaluate(
                    "async ([rows, stamp]) => { await view.data('frame', rows).data('stamp', stamp).runAsync();"
                    " return await view.toImageURL('png'); }",
                    [rows, stamp],
                )
                b_pngs.append(__import__("base64").b64decode(url.split(",", 1)[1]))
            t_b = time.perf_counter() - t0
        finally:
            browser.close()
            tmp.unlink(missing_ok=True)

    diffs = []
    for i in range(0, n, max(1, n // 12)):
        a = Image.open(io.BytesIO(a_pngs[i])).convert("RGB")
        b = Image.open(io.BytesIO(b_pngs[i])).convert("RGB").resize(a.size)
        px = list(ImageChops.difference(a, b).convert("L").get_flattened_data())
        diffs.append(sum(px) / len(px) / 255)
    print(f"frames: {n}  plot box: {w}x{h}")
    print(f"A vl-convert : {t_a:6.1f}s  ({n / t_a:5.1f} fps)")
    print(f"B Chrome view: {t_b:6.1f}s  ({n / t_b:5.1f} fps)")
    print(f"mean |A-B| pixel difference over sampled frames: {statistics.mean(diffs):.4f} (max {max(diffs):.4f})")


if __name__ == "__main__":
    main(sys.argv[1])
