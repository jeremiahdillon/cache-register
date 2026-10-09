"""Charts for the Opus isolines exploration (render contract: src/cachereg/render.py).

One step line per Claude Opus on a log price axis: the lowest price at which that Opus's capability could be
bought, from its launch. A dot and a direct label ("model price") mark the Opus itself and each later model
that set a new low; price cuts by the model already holding the low are unlabelled steps. No legend: the
start label names each line. Labels are placed once by a small greedy pass that avoids other labels, dots and
lines. Video: the lines draw one after another; finished lines dim, and the last frame is the static chart.
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
# Motion (video targets): seconds, frames and the opacity finished lines dim to.
FPS = 30
# DRAW_S is shared by all lines in proportion to their span (one pace in days per second).
INTRO_S, DRAW_S, HOLD_S, FINAL_HOLD_S = 0.6, 20.0, 1.5, 3.0
DIM, DIM_FRAMES, LABEL_FADE_FRAMES = 0.25, 12, 8


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
    """Drop Epoch's bracketed notes (version dates, hosting) so labels stay one short line; tooltips keep them."""
    return name.removeprefix("Claude ").split(" (")[0]


def _place(points: list[dict], obstacles: list[tuple], plot_w: float, plot_h: float, fs: float) -> list[dict]:
    """Greedy label placement in pixel space: try positions around each dot, keep the first that fits.

    Each point has x, y (pixels), text and size; `obstacles` are thin boxes along the step lines, which labels
    should not sit on. Returns the chosen offset (dx, dy) and alignment per point.
    """
    char_w = 0.52  # Inter, average glyph width per px of font size (digits run wide)
    boxes = [(p["x"] - 6 * fs, p["y"] - 6 * fs, p["x"] + 6 * fs, p["y"] + 6 * fs) for p in points]  # the dots
    line = 1.25
    # Offsets in label heights from the dot, nearest first; negative = above.
    cands = [(side, v * (1.0 + k * line)) for k in (0, 1, 2, 3) for side in ("right", "left") for v in (-1, 1)]
    out = []
    for p in points:
        w, h = len(p["text"]) * char_w * p["size"] + 4 * fs, p["size"] * 1.15
        best, best_cost = None, math.inf
        # A line's start label always sits above its dot, so it reads as the line's title.
        mine = [c for c in cands if c[1] < 0] if p["kind"] == "anchor" else cands
        for side, lines in mine:
            dx = 9 * fs if side == "right" else -9 * fs
            cy = p["y"] + lines * p["size"] * 0.75
            x0 = p["x"] + dx if side == "right" else p["x"] + dx - w
            box = (x0, cy - h / 2, x0 + w, cy + h / 2)
            off = max(0, -box[0]) + max(0, box[2] - plot_w) + max(0, -box[1]) + max(0, box[3] - plot_h)
            hits = sum(_overlap(box, b) for b in boxes) + 25 * sum(_overlap(box, b) for b in obstacles)
            cost = hits + 50 * off + 0.01 * abs(lines)
            if cost < best_cost:
                best, best_cost = (side, dx, cy - p["y"], box), cost
            if hits == 0 and off == 0:
                break
        side, dx, dy, box = best
        boxes.append(box)
        out.append({"align": "left" if side == "right" else "right", "dx": dx, "dy": dy})
    return out


def _overlap(a: tuple, b: tuple) -> float:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


@dataclass(frozen=True)
class Geometry:
    """Everything that stays fixed across frames: scales, encodings, line rows and placed labels."""

    anchors: list[str]
    rows: pl.DataFrame  # daily line points: t, day, anchor, usd_per_mtok, display_name
    labels: pl.DataFrame  # one row per dot/label, with its placed position
    x_scale: alt.Scale
    x_axis: alt.Axis
    y_scale: alt.Scale
    y_axis: alt.Axis
    color: alt.Color
    first: date
    last: date


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
    pad_days = (last - first).days * 0.16  # room on the right for the last labels
    x0, x1 = first - timedelta(days=10), last + timedelta(days=pad_days)
    lo, hi = d["usd_per_mtok"].min() * 0.4, d["usd_per_mtok"].max() * 2.0
    plot_w, plot_h = px_w, px_h  # Altair width/height are the plot area; axes sit outside it

    x_scale = alt.Scale(type="utc", domain=[_ms(x0), _ms(x1)])
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

    def to_px(day, v: float) -> tuple[float, float]:
        x = (day - x0).days / (x1 - x0).days * plot_w
        y = (math.log10(hi) - math.log10(v)) / (math.log10(hi) - math.log10(lo)) * plot_h
        return x, y

    rows = d.with_columns(t=pl.col("day").map_elements(_ms, return_dtype=pl.Int64)).select(
        "t", "day", "anchor", "usd_per_mtok", "display_name"
    )

    # Labels: the Opus start (name, ECI and price, larger) and each new model ("name price").
    pts = []
    for r in ev.sort("anchor", "day").iter_rows(named=True):
        x, y = to_px(r["day"], r["usd_per_mtok"])
        if r["kind"] == "anchor":
            text = f"{_short(r['anchor'])} · ECI {r['anchor_eci']:.0f} · {fmt_usd(r['usd_per_mtok'])}"
            size = START_PX * fs
        else:
            text = f"{_short(r['display_name'])} {fmt_usd(r['usd_per_mtok'])}"
            size = LABEL_PX * fs
        pts.append({**r, "x": x, "y": y, "text": text, "size": size, "t": _ms(r["day"])})
    # Starts first so they get the best spots, then left to right.
    order = sorted(range(len(pts)), key=lambda i: (pts[i]["kind"] != "anchor", pts[i]["x"]))
    # Thin boxes along every step line (horizontal runs and the vertical drops between them).
    segs, half = [], 2 * fs
    for a in anchors:
        s = d.filter(pl.col("anchor") == a).sort("day")
        chg = s.filter(pl.col("usd_per_mtok").ne_missing(pl.col("usd_per_mtok").shift(1))).vstack(s.tail(1))
        pts_px = [to_px(r["day"], r["usd_per_mtok"]) for r in chg.iter_rows(named=True)]
        for (xa, ya), (xb, yb) in zip(pts_px, pts_px[1:], strict=False):
            segs.append((xa, ya - half, xb, ya + half))
            segs.append((xb - half, min(ya, yb), xb + half, max(ya, yb)))
    # Placed once on the full chart, so labels never move between video frames.
    placed = _place([pts[i] for i in order], segs, plot_w, plot_h, fs)
    lab = []
    for i, pl_ in zip(order, placed, strict=True):
        p = pts[i]
        # Convert the pixel offset back to a price so the label rides with the scale.
        y_px = p["y"] + pl_["dy"]
        ly = 10 ** (math.log10(hi) - y_px / plot_h * (math.log10(hi) - math.log10(lo)))
        lab.append(
            {
                "t": p["t"],
                "day": p["day"],
                "anchor": p["anchor"],
                "usd_per_mtok": p["usd_per_mtok"],
                "label_y": ly,
                "text": p["text"],
                "kind": p["kind"],
                "align": pl_["align"],
                "display_name": p["display_name"],
            }
        )
    return Geometry(anchors, rows, pl.DataFrame(lab), x_scale, x_axis, y_scale, y_axis, clr, first, last)


def _chart(story: Story, width, height, fs: float, interactive: bool = False, state: dict | None = None) -> alt.Chart:
    """The chart, fully drawn (state=None) or as one animation frame.

    state: {anchor: (reveal_through, opacity, label_fade)}: each anchor's line and labels up to that day (None =
    not drawn yet), its opacity, and how many days a just-revealed label takes to fade in. Optional key "_head":
    (anchor, day) draws a moving dot at the tip of the line being drawn.
    """
    g = _geometry(story, width, height, fs)
    fonts = brand()["fonts"]

    def xenc(field: str = "t") -> alt.X:
        return alt.X(f"{field}:T", title=None, scale=g.x_scale, axis=g.x_axis)

    def yenc(field: str = "usd_per_mtok") -> alt.Y:
        return alt.Y(f"{field}:Q", scale=g.y_scale, axis=g.y_axis)

    rows, lab = g.rows, g.labels
    if state is None:
        rows, lab = rows.with_columns(op=pl.lit(1.0)), lab.with_columns(op=pl.lit(1.0))
    else:
        rparts, lparts = [], []
        for a in g.anchors:
            through, op, fade = state.get(a, (None, 0.0, 1))
            if through is None:
                continue
            rparts.append(rows.filter((pl.col("anchor") == a) & (pl.col("day") <= through)).with_columns(op=pl.lit(op)))
            age = (pl.lit(through) - pl.col("day")).dt.total_days()
            lparts.append(
                lab.filter((pl.col("anchor") == a) & (pl.col("day") <= through)).with_columns(
                    op=pl.min_horizontal((age + 1) / max(fade, 1), pl.lit(1.0)) * op
                )
            )
        rows = pl.concat(rparts) if rparts else rows.clear().with_columns(op=pl.lit(1.0))
        lab = pl.concat(lparts) if lparts else lab.clear().with_columns(op=pl.lit(1.0))

    opacity = alt.Opacity("op:Q", scale=None, legend=None)
    line = (
        alt.Chart(alt.Data(values=rows.drop("day").to_dicts()))
        .mark_line(interpolate="step-after", strokeWidth=2.4 * fs)
        .encode(x=xenc(), y=yenc(), color=g.color, detail="anchor:N", opacity=opacity)
    )
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
        alt.Chart(alt.Data(values=lab.drop("day").to_dicts()))
        .mark_circle(stroke=color("canvas"), strokeWidth=2)
        .encode(
            x=xenc(),
            y=yenc(),
            color=g.color,
            opacity=opacity,
            size=alt.Size(
                "kind:N", scale=alt.Scale(domain=["anchor", "new model"], range=[150 * fs**2, 70 * fs**2]), legend=None
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
    head = (state or {}).get("_head")
    if head is not None:
        a, day = head
        tip = g.rows.filter((pl.col("anchor") == a) & (pl.col("day") <= day)).tail(1)
        layers.append(
            alt.Chart(alt.Data(values=tip.drop("day").to_dicts()))
            .mark_circle(size=60 * fs**2, opacity=1)
            .encode(x=xenc(), y=yenc(), color=g.color)
        )
    for align in ("left", "right"):
        for kind, size, ink_name, weight in (
            ("anchor", START_PX, "text", 600),
            ("new model", LABEL_PX, "text_secondary", 400),
        ):
            sub = lab.filter((pl.col("align") == align) & (pl.col("kind") == kind))
            dx = 9 * fs if align == "left" else -9 * fs
            layers.append(
                alt.Chart(alt.Data(values=sub.drop("day").to_dicts()))
                .mark_text(
                    align=align,
                    baseline="middle",
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
    """Video: the lines draw one after another, left to right in time; finished lines dim, then all return.

    Time on each line runs at a constant pace (days per frame), so a longer history takes longer to draw.
    """
    g = _geometry(story, width, height, font_scale)
    span = {a: g.rows.filter(pl.col("anchor") == a)["day"] for a in g.anchors}
    total_days = sum((s.max() - s.min()).days for s in span.values())
    days_per_frame = total_days / (DRAW_S * FPS)
    fade = LABEL_FADE_FRAMES * days_per_frame
    done: dict[str, tuple] = {}  # finished anchors -> their final state
    states: list[dict] = [{} for _ in range(int(INTRO_S * FPS))]

    def dim(k: float) -> dict:
        return {a: (s[0], 1 - (1 - DIM) * k, s[2]) for a, s in done.items()}

    for a in g.anchors:
        start, end = span[a].min(), span[a].max()
        n = max(int(math.ceil((end - start).days / days_per_frame)), 1)
        # Dim the finished lines while the next start label fades in.
        for i in range(DIM_FRAMES if done else 0):
            states.append(dim((i + 1) / DIM_FRAMES) | {a: (start, 1.0, fade)})
        for i in range(n + 1):
            day = min(start + timedelta(days=round(i * days_per_frame)), end)
            states.append(dim(1.0) | {a: (day, 1.0, fade), "_head": (a, day)})
        for _ in range(int(HOLD_S * FPS)):
            states.append(dim(1.0) | {a: (end, 1.0, fade)})
        done[a] = (end, 1.0, fade)
    for i in range(DIM_FRAMES):
        states.append(dim(1 - (i + 1) / DIM_FRAMES))
    states += [None] * int(FINAL_HOLD_S * FPS)
    return [_chart(story, width, height, font_scale, state=s).to_dict() for s in states], FPS
