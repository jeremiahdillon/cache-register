"""Charts for the Opus isolines exploration (render contract: src/cachereg/render.py).

One step line per Claude Opus on a log price axis: the lowest price at which that Opus's capability could be
bought, from its launch. A dot and a direct label mark the Opus itself (name, ECI, launch price) and each later
model that set a new low (name only; the last one also carries today's price). Price cuts by the model already
holding the low are unlabelled steps. No legend: the start label names each line. Labels are placed once by a
small greedy pass that avoids other labels, dots and lines.

Video: the lines draw one after another at one speed along the drawn path (pixels per second), so a drop in
price takes as long to draw as a run of the same length in time. Each finished line dims and stays dim; all
return together at the end, on a frame identical to the static chart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import altair as alt
import polars as pl
from analysis import fmt_usd

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.theme import vl_config

# One hue (the brand accent), light to dark by capability: the lines are ordered levels, not categories.
RAMP = ["#FFD9C9", "#FF9E78", "#FF6A3D", "#C7401A"]
LABEL_PX, START_PX, AXIS_PX = 14, 16, 15
CHAR_W = 0.52  # Inter: average glyph width per px of font size (digits run wide)
LINE_HEIGHT = 1.2  # multi-line labels, in font sizes
# Motion (video targets): seconds, frames and the opacity finished lines dim to.
FPS = 30
# DRAW_S is shared by all lines in proportion to their drawn length (one speed along the path).
INTRO_S, DRAW_S, HOLD_S, FINAL_HOLD_S = 0.8, 22.0, 1.2, 3.5
DIM, DIM_FRAMES, RESTORE_FRAMES, LABEL_FADE_FRAMES = 0.25, 18, 24, 10
# Labels for long Epoch names; the README keeps the full names.
SHORT_NAMES = {
    "Qwen3-235B-A22B-Thinking (Jul 2025)": "Qwen3 235B",
    "DeepSeek V4 Flash 0731": "DeepSeek V4 Flash",
    "GLM-5.3-Flash": "GLM 5.3 Flash",
    "DeepSeek-V3.2-Exp": "DeepSeek V3.2",
}


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _ticks(lo: float, hi: float) -> list[float]:
    out = []
    for e in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1):
        for m in (1, 3):
            v = m * 10**e
            if lo <= v <= hi:
                out.append(v)
    return out


def _short(name: str) -> str:
    """A one-line label: SHORT_NAMES, else drop "Claude " and Epoch's bracketed notes; tooltips keep the full name."""
    return SHORT_NAMES.get(name) or name.removeprefix("Claude ").split(" (")[0]


def _smooth(u: float) -> float:
    """Ease in and out (smoothstep): a line starts and finishes gently."""
    return u * u * (3 - 2 * u)


def _text_box(text: str, size: float, fs: float) -> tuple[float, float]:
    """Estimated (width, height) in pixels of a label, one line per "\n"."""
    lines = text.split("\n")
    return max(len(t) for t in lines) * CHAR_W * size + 4 * fs, len(lines) * size * LINE_HEIGHT


def _place(points: list[dict], obstacles: list[tuple], plot_w: float, plot_h: float, fs: float) -> list[dict]:
    """Greedy label placement in pixel space: try positions around each dot, nearest first, keep the first that fits.

    Each point has x, y (pixels), text, size and kind; `obstacles` are thin boxes along the lines, which labels
    should not sit on. Start labels ("anchor") sit just above their dot, as the line's title; the last label
    on each line ("end") sits to the right of its dot, where the line ends. Returns alignment and dy per point.
    """
    boxes = [(p["x"] - 6 * fs, p["y"] - 6 * fs, p["x"] + 6 * fs, p["y"] + 6 * fs) for p in points]  # the dots
    out = []
    for p in points:
        w, h = _text_box(p["text"], p["size"], fs)
        gap, step = 0.15 * p["size"], 0.95 * p["size"]  # from the dot to the label's edge; per extra tier
        tiers = (0, 1) if p["kind"] == "anchor" else (0, 1, 2, 3)
        sides = ("right",) if p["kind"] == "end" else ("right", "left")
        above = (-1,) if p["kind"] == "anchor" else (-1, 1)
        best, best_cost = None, math.inf
        for k in tiers:
            for side in sides:
                for v in above:
                    dx = 9 * fs if side == "right" else -9 * fs
                    cy = p["y"] + v * (h / 2 + gap + k * step)
                    x0 = p["x"] + dx if side == "right" else p["x"] + dx - w
                    box = (x0, cy - h / 2, x0 + w, cy + h / 2)
                    off = max(0, -box[0]) + max(0, box[2] - plot_w) + max(0, -box[1]) + max(0, box[3] - plot_h)
                    hits = sum(_overlap(box, b) for b in boxes) + 25 * sum(_overlap(box, b) for b in obstacles)
                    cost = hits + 50 * off + k
                    if cost < best_cost:
                        best, best_cost = (side, cy - p["y"], box), cost
                    if hits == 0 and off == 0:
                        break
                else:
                    continue
                break
            else:
                continue
            break
        side, dy, box = best
        boxes.append(box)
        out.append({"align": "left" if side == "right" else "right", "dy": dy})
    return out


def _overlap(a: tuple, b: tuple) -> float:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


@dataclass(frozen=True)
class Geometry:
    """Everything that stays fixed across frames: scales, encodings, line paths and placed labels."""

    anchors: list[str]
    rows: pl.DataFrame  # daily line points (static/HTML): t, day, anchor, usd_per_mtok, display_name
    paths: dict[str, list[tuple[float, float, float]]]  # anchor -> corners (t ms, price, distance along path px)
    labels: pl.DataFrame  # one row per dot/label: placed position, and `s`, its distance along its line's path
    x_scale: alt.Scale
    x_axis: alt.Axis
    y_scale: alt.Scale
    y_axis: alt.Axis
    color: alt.Color


_GEOMETRY: dict[tuple, Geometry] = {}  # per (story, size, font scale): placement runs once, not once per frame


def _geometry(story: Story, width, height, fs: float) -> Geometry:
    key = (id(story), width, height, fs)
    if key not in _GEOMETRY:
        _GEOMETRY[key] = _build_geometry(story, width, height, fs)
    return _GEOMETRY[key]


def _build_geometry(story: Story, width, height, fs: float) -> Geometry:
    anchors = story.extra["anchors"]
    d = story.frames["daily"].sort("anchor", "day")
    ev = story.frames["events"]
    first, last = d["day"].min(), d["day"].max()

    ink = dict(zip(anchors, RAMP, strict=False))
    clr = alt.Color("anchor:N", scale=alt.Scale(domain=anchors, range=[ink[a] for a in anchors]), legend=None)

    px_w = width if isinstance(width, int | float) else 900
    px_h = height if isinstance(height, int | float) else 520
    lo, hi = d["usd_per_mtok"].min() * 0.4, d["usd_per_mtok"].max() * 2.0
    plot_w, plot_h = px_w, px_h  # Altair width/height are the plot area; axes sit outside it

    # Label text and kind: the Opus start (name; ECI and launch price), each new model (name), and the last
    # new model on each line ("end": name and today's price).
    last_event = ev.group_by("anchor").agg(pl.col("day").max().alias("last_day"))
    ev = ev.join(last_event, on="anchor").sort("anchor", "day")
    texts = []
    for r in ev.iter_rows(named=True):
        if r["kind"] == "anchor":
            texts.append(("anchor", f"{_short(r['anchor'])}\nECI {r['anchor_eci']:.0f} · {fmt_usd(r['usd_per_mtok'])}"))
        elif r["day"] == r["last_day"]:
            texts.append(("end", f"{_short(r['display_name'])} {fmt_usd(r['usd_per_mtok'])}"))
        else:
            texts.append(("new model", _short(r["display_name"])))

    # x domain: a little room on the left; on the right, enough that every end label fits right of its dot.
    t0 = _ms(first - timedelta(days=10))
    t1 = _ms(last + timedelta(days=(last - first).days * 0.03))
    for (kind, text), r in zip(texts, ev.iter_rows(named=True), strict=True):
        if kind == "end":
            need = 9 * fs + _text_box(text, LABEL_PX * fs, fs)[0] + 4 * fs
            t = _ms(r["day"])
            t1 = max(t1, t0 + (t - t0) * plot_w / max(plot_w - need, 1.0))

    x_scale = alt.Scale(type="utc", domain=[t0, t1])
    quarters = [q for y in (2025, 2026) for m in (1, 4, 7, 10) if first <= (q := date(y, m, 1)) <= last]
    x_axis = alt.Axis(
        values=[_ms(q) for q in quarters],
        labelExpr=(
            "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
        ),
        labelFontSize=AXIS_PX * fs,
        grid=False,
    )
    y_scale = alt.Scale(type="log", domain=[lo, hi], nice=False)
    y_axis = alt.Axis(
        values=_ticks(lo, hi),
        labelExpr="datum.value >= 1 ? '$' + format(datum.value, ',.0f') : '$' + format(datum.value, '.2~f')",
        labelFontSize=AXIS_PX * fs,
        title="List price per million tokens (log scale)",
        titlePadding=14 * fs,
    )

    def to_px(t: float, v: float) -> tuple[float, float]:
        x = (t - t0) / (t1 - t0) * plot_w
        y = (math.log10(hi) - math.log10(v)) / (math.log10(hi) - math.log10(lo)) * plot_h
        return x, y

    rows = d.with_columns(t=pl.col("day").map_elements(_ms, return_dtype=pl.Int64)).select(
        "t", "day", "anchor", "usd_per_mtok", "display_name"
    )

    # Each line as explicit corners (the step drawn as horizontal runs and vertical drops), with the distance
    # along the path in pixels: the video draws at one speed along this distance.
    paths: dict[str, list[tuple[float, float, float]]] = {}
    for a in anchors:
        s = rows.filter(pl.col("anchor") == a).sort("t")
        chg = s.filter(pl.col("usd_per_mtok").ne_missing(pl.col("usd_per_mtok").shift(1)))
        corners = []
        for r in chg.iter_rows(named=True):
            if corners:
                corners.append((r["t"], corners[-1][1]))
            corners.append((r["t"], r["usd_per_mtok"]))
        corners.append((s["t"][-1], corners[-1][1]))
        path, dist, prev = [], 0.0, None
        for t, v in corners:
            xy = to_px(t, v)
            if prev is not None:
                dist += math.hypot(xy[0] - prev[0], xy[1] - prev[1])
            path.append((float(t), v, dist))
            prev = xy
        paths[a] = path

    pts = []
    for (kind, text), r in zip(texts, ev.iter_rows(named=True), strict=True):
        t = _ms(r["day"])
        x, y = to_px(t, r["usd_per_mtok"])
        size = (START_PX if kind == "anchor" else LABEL_PX) * fs
        # The dot is reached when the line arrives at this price on this day (after any drop into it).
        s_at = next(p[2] for p in paths[r["anchor"]] if p[0] == t and p[1] == r["usd_per_mtok"])
        pts.append({**r, "kind": kind, "x": x, "y": y, "text": text, "size": size, "t": t, "s": s_at})
    # Starts first so they get the best spots, then the ends, then the rest left to right.
    rank = {"anchor": 0, "end": 1, "new model": 2}
    order = sorted(range(len(pts)), key=lambda i: (rank[pts[i]["kind"]], pts[i]["x"]))
    # Thin boxes along every line (horizontal runs and the vertical drops between them).
    segs, half = [], 2 * fs
    for path in paths.values():
        xy = [to_px(t, v) for t, v, _ in path]
        for (xa, ya), (xb, yb) in zip(xy, xy[1:], strict=False):
            segs.append((min(xa, xb) - half, min(ya, yb) - half, max(xa, xb) + half, max(ya, yb) + half))
    # Placed once on the full chart, so labels never move between video frames.
    placed = _place([pts[i] for i in order], segs, plot_w, plot_h, fs)
    lab = []
    for i, pl_ in zip(order, placed, strict=True):
        p = pts[i]
        # Convert the pixel offset back to a price so the label rides with the scale. Vega anchors a multi-line
        # label at its first line, so move that line up by half the block's extra height to centre the block.
        y_px = p["y"] + pl_["dy"] - (p["text"].count("\n") * p["size"] * LINE_HEIGHT) / 2
        ly = 10 ** (math.log10(hi) - y_px / plot_h * (math.log10(hi) - math.log10(lo)))
        lab.append(
            {
                "key": i,
                "t": p["t"],
                "s": p["s"],
                "anchor": p["anchor"],
                "usd_per_mtok": p["usd_per_mtok"],
                "label_y": ly,
                "text": p["text"],
                "kind": p["kind"],
                "align": pl_["align"],
                "display_name": p["display_name"],
            }
        )
    return Geometry(anchors, rows, paths, pl.DataFrame(lab), x_scale, x_axis, y_scale, y_axis, clr)


def _partial(path: list[tuple[float, float, float]], s: float) -> list[tuple[float, float]]:
    """The path's corners up to distance s, ending at the interpolated tip (price interpolated on the log scale)."""
    out = []
    for (ta, va, sa), (tb, vb, sb) in zip(path, path[1:], strict=False):
        out.append((ta, va))
        if s < sb:
            k = (s - sa) / (sb - sa) if sb > sa else 1.0
            out.append((ta + (tb - ta) * k, 10 ** (math.log10(va) + (math.log10(vb) - math.log10(va)) * k)))
            return out
    out.append(path[-1][:2])
    return out


def _chart(story: Story, width, height, fs: float, interactive: bool = False, state: dict | None = None) -> alt.Chart:
    """The chart, fully drawn (state=None) or as one animation frame.

    state: {"lines": {anchor: (distance drawn along its path, opacity)}, "labels": {label key: opacity},
    "head": anchor whose tip gets a moving dot, or None}. Anchors and labels not listed are not drawn.
    """
    g = _geometry(story, width, height, fs)
    fonts = brand()["fonts"]

    def xenc(field: str = "t") -> alt.X:
        return alt.X(f"{field}:T", title=None, scale=g.x_scale, axis=g.x_axis)

    def yenc(field: str = "usd_per_mtok") -> alt.Y:
        return alt.Y(f"{field}:Q", scale=g.y_scale, axis=g.y_axis)

    opacity = alt.Opacity("op:Q", scale=None, legend=None)
    if state is None:
        rows = g.rows.drop("day").with_columns(op=pl.lit(1.0)).to_dicts()
        lab = g.labels.with_columns(op=pl.lit(1.0))
        line = alt.Chart(alt.Data(values=rows)).mark_line(interpolate="step-after", strokeWidth=2.4 * fs)
    else:
        rows = [
            {"t": t, "usd_per_mtok": v, "anchor": a, "op": op, "i": i}
            for a, (s, op) in state["lines"].items()
            for i, (t, v) in enumerate(_partial(g.paths[a], s))
        ]
        ops = state["labels"]
        lab = g.labels.filter(pl.col("key").is_in(list(ops))).with_columns(
            op=pl.col("key").replace_strict(ops, return_dtype=pl.Float64)
        )
        line = alt.Chart(alt.Data(values=rows)).mark_line(strokeWidth=2.4 * fs).encode(order="i:Q")
    line = line.encode(x=xenc(), y=yenc(), color=g.color, detail="anchor:N", opacity=opacity)
    if interactive:
        line = line.encode(
            tooltip=[
                alt.Tooltip("anchor:N", title="Capability of"),
                alt.Tooltip("t:T", title="Date", format="%b %-d, %Y"),
                alt.Tooltip("usd_per_mtok:Q", title="$ / M tokens", format=".3f"),
                alt.Tooltip("display_name:N", title="Cheapest model"),
            ]
        )

    dots = (
        alt.Chart(alt.Data(values=lab.to_dicts()))
        .mark_circle(stroke=color("canvas"), strokeWidth=2)
        .encode(
            x=xenc(),
            y=yenc(),
            color=g.color,
            opacity=opacity,
            size=alt.Size(
                "kind:N",
                scale=alt.Scale(domain=["anchor", "end", "new model"], range=[150 * fs**2, 70 * fs**2, 70 * fs**2]),
                legend=None,
            ),
        )
    )
    if interactive:
        dots = dots.encode(
            tooltip=[
                alt.Tooltip("display_name:N", title="Model"),
                alt.Tooltip("anchor:N", title="Matches"),
                alt.Tooltip("t:T", title="New low on", format="%b %-d, %Y"),
                alt.Tooltip("usd_per_mtok:Q", title="$ / M tokens", format=".3f"),
            ]
        )

    layers = [line, dots]
    head = (state or {}).get("head")
    if head is not None:
        t, v = _partial(g.paths[head], state["lines"][head][0])[-1]
        layers.append(
            alt.Chart(alt.Data(values=[{"t": t, "usd_per_mtok": v, "anchor": head}]))
            .mark_circle(size=60 * fs**2, opacity=1)
            .encode(x=xenc(), y=yenc(), color=g.color)
        )
    for align in ("left", "right"):
        # Start and end labels bold in primary ink; the models in between regular, in secondary ink.
        for kind, size, ink_name, weight in (
            ("anchor", START_PX, "text", 600),
            ("end", LABEL_PX, "text", 600),
            ("new model", LABEL_PX, "text_secondary", 400),
        ):
            sub = lab.filter((pl.col("align") == align) & (pl.col("kind") == kind))
            dx = 9 * fs if align == "left" else -9 * fs
            layers.append(
                alt.Chart(alt.Data(values=sub.to_dicts()))
                .mark_text(
                    align=align,
                    baseline="middle",
                    lineBreak="\n",
                    lineHeight=size * fs * LINE_HEIGHT,
                    dx=dx,
                    fontSize=size * fs,
                    fontWeight=weight,
                    font=fonts["body"],
                    color=color(ink_name),
                )
                .encode(x=xenc(), y=yenc("label_y"), text="text:N", opacity=opacity)
            )

    chart = alt.layer(*layers).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


def isolines(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    """Static and HTML: every line fully drawn (the animation's final frame)."""
    return _chart(story, width, height, font_scale, interactive)


def isolines_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    """Video: draw each line in turn at one speed along its path; dim it once drawn; restore all at the end.

    A line's opacity only ever goes 1 -> DIM (after it is drawn) -> 1 (at the end), so nothing flashes.
    """
    g = _geometry(story, width, height, font_scale)
    length = {a: g.paths[a][-1][2] for a in g.anchors}
    px_per_frame = sum(length.values()) / (DRAW_S * FPS)
    labels = {a: g.labels.filter(pl.col("anchor") == a).select("key", "s").rows() for a in g.anchors}

    lines: dict[str, list] = {}  # anchor -> [distance drawn, opacity]
    seen: dict[int, int] = {}  # label key -> frame it appeared on
    states: list[dict] = []

    def snap(head: str | None = None) -> None:
        f = len(states)
        ops = {}
        for a, (_, op) in lines.items():
            for key, _ in labels[a]:
                if key in seen:
                    ops[key] = min((f - seen[key] + 1) / LABEL_FADE_FRAMES, 1.0) * op
        states.append({"lines": {a: tuple(v) for a, v in lines.items()}, "labels": ops, "head": head})

    for _ in range(int(INTRO_S * FPS)):
        snap()
    for n, a in enumerate(g.anchors):
        frames = max(int(round(length[a] / px_per_frame)), 1)
        lines[a] = [0.0, 1.0]
        for i in range(frames + 1):
            lines[a][0] = length[a] * _smooth(i / frames)
            for key, s in labels[a]:
                if key not in seen and s <= lines[a][0] + 1e-6:
                    seen[key] = len(states)
            snap(head=a if i < frames else None)
        for _ in range(int(HOLD_S * FPS)):
            snap()
        if n < len(g.anchors) - 1:  # the last line stays bright; the others come back up to meet it
            for i in range(DIM_FRAMES):
                lines[a][1] = 1 - (1 - DIM) * _smooth((i + 1) / DIM_FRAMES)
                snap()
    for i in range(RESTORE_FRAMES):
        k = _smooth((i + 1) / RESTORE_FRAMES)
        for a in g.anchors[:-1]:
            lines[a][1] = DIM + (1 - DIM) * k
        snap()
    for _ in range(int(FINAL_HOLD_S * FPS)):
        snap()
    return [_chart(story, width, height, font_scale, state=s).to_dict() for s in states], FPS
