"""Chart for receipts/deepseek-vs-us (render contract: src/cachereg/render.py): `build`, in motion.

Each step's bars grow up from the stack so far (DeepSeek's from the axis, in front), lifting a bold line; the
previous bold grey line turns light as they rise. They hold, then their bottom edge wipes up into the line until
they are gone, and the next step's bars grow on from there in one continuous upward motion. Bars are clipped to
their bounding lines: each is a slice of the band between the line below and the line above, so its top and bottom
edges lie on those lines everywhere (the first and last bars are half width, where the lines end). The final
frame: light grey lines for each step, the bold grey line (all US models) and the lime DeepSeek line. Grey labels
settle once as their step grows, each sliding out from behind the one above it.

The y-axis is set by the US lines first (the smallest 25T multiple above them) and grows, camera-style, during
DeepSeek's step: one smooth ease-in-out from AXIS_START of the step that lands on the smallest 25T multiple above
DeepSeek as the line lands, so the final frame is the still. DeepSeek's rise is defined on screen, not in tokens:
its line end climbs the plot on the `weighty` path it would follow on the final axis, and the axis stretches
underneath, so the line's token value is the product of the two. Both land together with zero velocity, and the
line never moves down (a product of two non-decreasing motions), so it cannot seem to shrink as the axis finishes.
Gridlines keep their values (25T steps) and slide down; new ones enter from the top. The DeepSeek label rides the
end of its line, hidden until it emerges from behind the all-US label.
"""

from __future__ import annotations

import math
from datetime import timedelta
from functools import cache

import altair as alt
import polars as pl
from analysis import DEEPSEEK, US_ALL, US_OPEN, T, fmt_t
from PIL import ImageFont

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color, font_path
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX = 22, 18  # at font_scale 1
GRID = "#1C1F27"
BAR_DAYS = 6  # each weekly bar spans 6 of the week's 7 days


@cache
def _text_w(text: str, px: int) -> float:
    return ImageFont.truetype(str(font_path("body")), px).getlength(text)


def _axis_ceiling(y_max: float) -> float:
    """The smallest multiple of TICK_STEP above y_max (at least one step)."""
    return max(1, math.ceil(y_max / TICK_STEP - 1e-9)) * TICK_STEP


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _axis_at(ds_t: float, base: float, final: float) -> float:
    """The y-axis maximum at `ds_t` (DeepSeek's growth, 0..1 in time): `base` until AXIS_START, then one
    ease-in-out to `final`, landing as the line lands (ds_t = 1)."""
    if final <= base:
        return base
    return base + (final - base) * smoothstep((ds_t - AXIS_START) / (1 - AXIS_START))


def _x_axis(edge: str, fs: float) -> alt.Axis:
    quarters = [f"{y}-{m:02d}-01" for y in (2025, 2026) for m in (1, 4, 7, 10) if f"{y}-{m:02d}-01" <= edge]
    year = "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
    return alt.Axis(values=quarters, labelExpr=year, labelFontSize=AXIS_PX * fs)


FPS = 30
LEAD, GROW, STAY, WIPE, HOLD = 12, 30, 15, 24, 75  # frames per phase (grey steps); STAY = 0.5 s at full height
DS_PAUSE, DS_GROW, DS_STAY, DS_WIPE = 45, 72, 20, 30  # a longer beat before DeepSeek; its step is slower
DIM = 15  # frames, at the start of the pause, over which "+ Open" dims once All US has landed
# Each step is one or more columns of the wide frame; xAI is rolled into other closed US models here.
BUILD_STEPS = [["Anthropic"], ["OpenAI"], ["Google"], ["xAI (Grok)", "Other US closed"], [US_OPEN]]
BAR_GREY = "#D3D7E0"  # bars a shade brighter than the bold line, so the incoming step stands out
BOLD_W, DS_W, LIGHT_W = 5.0, 6.0, 1.6  # the top US line and DeepSeek's are the heavy ones
TICK_STEP = 25 * T  # y-axis gridlines, before and after the axis grows
AXIS_START = 0.4  # the axis starts growing this far (in time) into DeepSeek's step


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_cubic(t: float) -> float:
    return t**3


def weighty(t: float, t0: float = 0.7, y0: float = 0.8, p: float = 2.4) -> float:
    """DeepSeek's growth: a slow start, accelerating hard to near its final height, then a short settle. Never passes 1.

    Up to `t0` it is ease-in (power `p`) to `y0`; after it, an ease-out whose starting speed matches, so there is no
    jolt where the two meet, decelerating into place."""
    if t < t0:
        return y0 * (t / t0) ** p
    q = p * y0 / t0 * (1 - t0) / (1 - y0)  # ease-out power whose initial speed equals the ease-in's final speed
    u = (t - t0) / (1 - t0)
    return y0 + (1 - y0) * (1 - (1 - u) ** q)


def _build_schedule() -> list[dict]:
    """Per frame: top progress per step (0..1), the step on stage and its wipe progress (0..1, bottom edge).

    The wipe accelerates into the line (ease-in) and the next growth leaves it at speed (ease-out), back to back,
    so the hand-over reads as one upward motion."""
    n = len(BUILD_STEPS) + 1  # + DeepSeek
    push = [0.0] * n
    idle = {"stage": None, "wipe": 0.0, "dim": 0.0, "ds_t": 0.0}
    frames = [{"push": list(push), **idle}] * LEAD
    for k in range(n):
        ds = k == n - 1
        grow, stay, wipe = (DS_GROW, DS_STAY, DS_WIPE) if ds else (GROW, STAY, WIPE)
        dim = 1.0 if ds else 0.0  # "+ Open" dims in the pause and stays dim
        if ds:
            frames += [
                {"push": list(push), **idle, "dim": ease_in_out(min(1.0, i / DIM))} for i in range(1, DS_PAUSE + 1)
            ]
        ds_t = 1.0 if k == n - 1 else 0.0  # DeepSeek's growth in time, for the axis (1 once it has grown)
        for i in range(1, grow + 1):
            push[k] = weighty(i / grow) if ds else ease_out_cubic(i / grow)
            frames.append({"push": list(push), "stage": k, "wipe": 0.0, "dim": dim, "ds_t": i / grow if ds else 0.0})
        frames += [{"push": list(push), "stage": k, "wipe": 0.0, "dim": dim, "ds_t": ds_t}] * stay
        for i in range(1, wipe):  # the last wipe frame would be an empty bar: the next step's first frame follows
            frames.append({"push": list(push), "stage": k, "wipe": ease_in_cubic(i / wipe), "dim": dim, "ds_t": ds_t})
        frames.append({"push": list(push), **idle, "dim": dim, "ds_t": ds_t})
    frames += [{"push": list(push), **idle, "dim": 1.0, "ds_t": 1.0}] * HOLD
    return frames


def ease_in_out(t: float) -> float:
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _bar_slices(weeks, lo: list[float], hi: list[float], wipe: float) -> list[dict]:
    """Bars as slices of the band between two lines (lines join week midpoints, linearly).

    Each bar spans BAR_DAYS around its week's midpoint, with 3 points: left edge, midpoint, right edge; the line
    values at the edges are interpolated toward the neighbouring weeks, so the bar's edges lie on the lines. The
    first and last bars stop at the midpoint (the lines end there). `wipe` lifts the bottom edge toward the top."""
    half = BAR_DAYS / 2
    step = 7.0  # days between week midpoints
    rows, n = [], len(weeks)
    for i, d in enumerate(weeks):
        m = d + timedelta(days=half)
        pts = []
        if i > 0:
            f = half / step
            pts.append((m - timedelta(days=half), lo[i] + (lo[i - 1] - lo[i]) * f, hi[i] + (hi[i - 1] - hi[i]) * f))
        pts.append((m, lo[i], hi[i]))
        if i < n - 1:
            f = half / step
            pts.append((m + timedelta(days=half), lo[i] + (lo[i + 1] - lo[i]) * f, hi[i] + (hi[i + 1] - hi[i]) * f))
        for x, a, b in pts:
            rows.append({"bar": i, "x": x.isoformat(), "y0": a + (b - a) * wipe, "y1": b})
    return rows


def _build_spec(wide, cum, ds, labels, state, axis, pad, w, h, fs, y_title) -> dict:
    fonts = brand()["fonts"]
    first = wide["week"].min().replace(day=1)
    edge = (wide["week"].max() + timedelta(days=BAR_DAYS)).isoformat()
    x_scale = alt.Scale(type="utc", domain=[first.isoformat(), edge])
    y_scale = alt.Scale(domain=[0, axis], nice=False, zero=True)
    ticks = [i * TICK_STEP for i in range(int(axis / TICK_STEP + 1e-9) + 1)]  # 25T steps up to the axis
    weeks = wide["week"].to_list()
    mid = [(d + timedelta(days=BAR_DAYS / 2)).isoformat() for d in weeks]
    push, stage = state["push"], state["stage"]
    n_grey = len(BUILD_STEPS)

    # Lines: grey step k sits at cum[k-1] + push[k] * step value; it is bold until step k+1 pushes, then light.
    lines, label_vals = [], {}
    for k in range(n_grey):
        if push[k] <= 0:
            continue
        base = cum[k - 1] if k else [0.0] * len(weeks)
        top = [b + push[k] * (c - b) for b, c in zip(base, cum[k], strict=True)]
        lightness = push[k + 1] if k + 1 < n_grey else 0.0  # the all-US line stays bold
        sw = BOLD_W + (LIGHT_W - BOLD_W) * lightness
        lines += [
            {"x": x, "v": v, "s": f"g{k}", "sw": sw * fs, "c": _mix(color("text_secondary"), color("muted"), lightness)}
            for x, v in zip(mid, top, strict=True)
        ]
        label_vals[f"g{k}"] = (push[k], lightness)
    k_ds = n_grey
    if push[k_ds] > 0:
        dtop = [push[k_ds] * v for v in ds]
        lines += [
            {"x": x, "v": v, "s": "ds", "sw": DS_W * fs, "c": color("accent")} for x, v in zip(mid, dtop, strict=True)
        ]
        label_vals["ds"] = (push[k_ds], 0.0)

    # Bars of the step on stage: from the line below (DeepSeek: the axis) to its current top, bottom wiping up.
    bars = []
    if stage is not None:
        if stage == k_ds:
            lo, hi, fill = [0.0] * len(weeks), [push[k_ds] * v for v in ds], color("accent")
        else:
            lo = cum[stage - 1] if stage else [0.0] * len(weeks)
            hi = [b + push[stage] * (c - b) for b, c in zip(lo, cum[stage], strict=True)]
            fill = BAR_GREY
        bars = _bar_slices(weeks, lo, hi, state["wipe"])

    tick_rows = [{"v": v, "t": f"{v / T:g}T"} for v in ticks]
    layers = [
        alt.Chart(alt.Data(values=tick_rows))
        .mark_text(align="right", baseline="middle", dx=-10 * fs, fontSize=AXIS_PX * fs, font=fonts["mono"])
        .encode(x=alt.value(0), y=alt.Y("v:Q", scale=y_scale), text="t:N", color=alt.value(color("text_secondary"))),
        alt.Chart(alt.Data(values=tick_rows[1:]))
        .mark_rule(color=GRID, strokeWidth=1)
        .encode(
            y=alt.Y("v:Q", scale=y_scale, axis=alt.Axis(labels=False, grid=False, title=y_title, titlePadding=58 * fs))
        ),
        # An invisible rule carries the x axis, so it shows from the first frame.
        alt.Chart(alt.Data(values=[{"x": first.isoformat()}]))
        .mark_rule(opacity=0)
        .encode(x=alt.X("x:T", scale=x_scale, title=None, axis=_x_axis(edge, fs))),
    ]
    # Grey bars sit under the lines (the line they lift stays visible on top); DeepSeek's are in front.
    bar_layer = (
        alt.Chart(alt.Data(values=bars))
        .mark_area(color=fill, interpolate="linear", opacity=1)
        .encode(x=alt.X("x:T", scale=x_scale), y=alt.Y("y0:Q", scale=y_scale), y2="y1:Q", detail="bar:N")
        if bars
        else None
    )
    if bar_layer and stage != k_ds:
        layers.append(bar_layer)
    # One layer per grey line, with a constant width and colour: a data-driven strokeWidth is applied per mark,
    # not per series, so every line would take the first one's width.
    for k in range(n_grey):
        pts = [r for r in lines if r["s"] == f"g{k}"]
        if pts:
            layers.append(
                alt.Chart(alt.Data(values=pts))
                .mark_line(interpolate="linear", color=pts[0]["c"], strokeWidth=pts[0]["sw"])
                .encode(x=alt.X("x:T", scale=x_scale), y=alt.Y("v:Q", scale=y_scale))
            )
    if bar_layer and stage == k_ds:
        layers.append(bar_layer)
    dsl = [r for r in lines if r["s"] == "ds"]
    if dsl:
        layers += [
            alt.Chart(alt.Data(values=dsl))
            .mark_line(interpolate="linear", color=color("canvas"), strokeWidth=(DS_W + 4) * fs)
            .encode(x=alt.X("x:T", scale=x_scale), y=alt.Y("v:Q", scale=y_scale)),
            alt.Chart(alt.Data(values=dsl))
            .mark_line(interpolate="linear", color=color("accent"), strokeWidth=DS_W * fs)
            .encode(x=alt.X("x:T", scale=x_scale), y=alt.Y("v:Q", scale=y_scale)),
        ]
    # Right-edge labels at fixed final positions (see _label_layout). Each slides from where it starts to where it
    # settles as its step grows, and never moves again. Drawn newest first, each on a canvas-coloured plate, so a
    # label sliding out from behind a settled one stays hidden until it clears it. Light lines get light labels.
    font_px, gap = LABEL_PX * fs, LABEL_PX * fs * ROW
    for s in reversed(list(label_vals)):
        _, lightness = label_vals[s]
        lab = labels[s]
        y = lab["y"]
        ink = color("accent") if s == "ds" else _mix(color("text"), color("muted"), lightness)
        # The second row of the all-US label ("+ Open") names a step, so it dims like the others; "All US" stays.
        inks = [ink, _mix(color("text"), color("muted"), state["dim"])]
        n_rows = len(lab["rows"])
        layers.append(
            alt.Chart(alt.Data(values=[{}]))
            .mark_rect(color=color("canvas"))
            .encode(
                x=alt.value(w + 4 * fs),
                x2=alt.value(w + pad["right"]),
                y=alt.value(y - gap / 2),
                y2=alt.value(y + gap * (n_rows - 0.5)),
            )
        )
        for i, t in enumerate(lab["rows"]):
            layers.append(
                alt.Chart(alt.Data(values=[{"t": t}]))
                .mark_text(
                    align="left",
                    baseline="middle",
                    fontSize=font_px,
                    font=fonts["body"],
                    color=inks[i],
                    opacity=lab["opacity"],
                )
                .encode(x=alt.value(w + 14 * fs), y=alt.value(y + gap * i), text="t:N")
            )
    spec = alt.layer(*layers).properties(width=w, height=h).to_dict()
    spec["config"] = vl_config(fs)
    spec["autosize"] = {"type": "none"}
    spec["padding"] = pad
    return spec


ROW = 1.25  # label row pitch, in font sizes


def _label_layout(finals: dict[str, float], rows: dict[str, list[str]], axis: float, h: float, fs: float) -> dict:
    """Each label's settled pixel position at this frame's y-axis, and where it slides in from.

    Labels are kept in their top-to-bottom order and nudged apart by whole rows (a two-row label takes two). A grey
    step's label slides out from behind the previous step's settled label (Anthropic's from the axis); DeepSeek's
    (if present) from behind the all-US label. Only the labels that start in the open fade in."""
    gap = LABEL_PX * fs * ROW
    px = {s: h * (1 - v / axis) for s, v in finals.items()}
    order = sorted(px, key=px.get)
    out = dict(px)
    out[order[0]] = max(out[order[0]], gap / 2)
    for a, b in zip(order, order[1:], strict=False):
        out[b] = max(out[b], out[a] + gap * len(rows[a]))
    last = order[-1]
    limit = h - gap / 2 - gap * (len(rows[last]) - 1)
    if out[last] > limit:
        out[last] = limit
        for a, b in zip(reversed(order[:-1]), reversed(order[1:]), strict=False):
            out[a] = min(out[a], out[b] - gap * len(rows[a]))
    grey = [s for s in finals if s != "ds"]
    starts = {g: (out[grey[i - 1]] if i else h) for i, g in enumerate(grey)}
    if "ds" in finals:
        starts["ds"] = out[grey[-1]]
    return {s: {"to": out[s], "from": starts[s], "rows": rows[s], "fade": s == grey[0]} for s in finals}


def _labels_at(finals: dict[str, float], rows, state, axis: float, ds_vals: tuple[float, float, float], h, fs):
    """Label positions and opacities for one frame.

    Grey labels slide from `from` to `to` as their step grows (the layout is re-solved at the frame's axis, so they
    compress with their lines once the axis grows). DeepSeek's label rides the end of its line, plus the nudge its
    settled layout needs at the final axis; it is hidden until it emerges from behind the all-US label, fading in
    over one row as it clears that label's centre."""
    ds_top, ds_max, final_axis = ds_vals
    grey = {s: v for s, v in finals.items() if s != "ds"}
    lay = _label_layout(grey, rows, axis, h, fs)
    out = {}
    for k, s in enumerate(grey):
        e = state["push"][k]
        if e <= 0:
            continue
        lab = lay[s]
        y = lab["from"] + (lab["to"] - lab["from"]) * e
        out[s] = {"y": y, "rows": rows[s], "opacity": min(1.0, e * 1.5) if lab["fade"] else 1.0}
    e_ds = state["push"][len(grey)]
    if e_ds > 0:
        settled = _label_layout(finals, rows, final_axis, h, fs)["ds"]["to"]
        nudge = settled - h * (1 - ds_max / final_axis)
        y = h * (1 - ds_top / axis) + nudge * e_ds
        gap = LABEL_PX * fs * ROW
        last_grey = list(grey)[-1]
        out["ds"] = {"y": y, "rows": rows["ds"], "opacity": max(0.0, min(1.0, (out[last_grey]["y"] - y) / gap))}
    return out


def _mix(a: str, b: str, t: float) -> str:
    """Blend two #RRGGBB colours: t=0 → a, t=1 → b."""
    ca, cb = (tuple(int(c[i : i + 2], 16) for i in (1, 3, 5)) for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb, strict=True))


def build_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    fs = font_scale
    wide = story.frames["wide"]
    last = wide.row(-1, named=True)
    cum, run = [], [0.0] * wide.height
    for cols in BUILD_STEPS:
        run = [r + v for r, v in zip(run, wide.select(pl.sum_horizontal(cols))[:, 0].to_list(), strict=True)]
        cum.append(run)
    ds = wide[DEEPSEEK].to_list()
    text = {
        "g0": "Anthropic",
        "g1": "+ OpenAI",
        "g2": "+ Google",
        "g3": "+ Other closed",
        "g4": [f"All US {fmt_t(last[US_ALL])}", "+ Open"],  # "All US" next to its line, the step on the row below
        "ds": f"DeepSeek {fmt_t(last[DEEPSEEK])}",
    }
    rows = {k: v if isinstance(v, list) else [v] for k, v in text.items()}
    label_w = max(_text_w(t, round(LABEL_PX * fs)) for r in rows.values() for t in r)
    pad = {
        "left": round(72 * fs),
        "right": round(14 * fs + label_w + 8 * fs),
        "top": round(16 * fs),
        "bottom": round(44 * fs),
    }
    w, h = width - pad["left"] - pad["right"], height - pad["top"] - pad["bottom"]
    base, ds_max, k_ds = _axis_ceiling(max(cum[-1])), max(ds), len(BUILD_STEPS)
    final = max(base, _axis_ceiling(ds_max))
    finals = {f"g{k}": cum[k][-1] for k in range(len(BUILD_STEPS))} | {"ds": ds[-1]}
    specs = []
    for s in _build_schedule():
        axis = _axis_at(s["ds_t"], base, final)
        # DeepSeek's push is its line end's height on the final axis (screen space); in tokens it is that times
        # axis / final, so the line climbs the plot on its own path while the axis stretches beneath it.
        push = [*s["push"][:k_ds], s["push"][k_ds] * axis / final]
        s = {**s, "push": push}
        labels = _labels_at(finals, rows, s, axis, (s["push"][len(BUILD_STEPS)] * ds[-1], ds[-1], final), h, fs)
        specs.append(_build_spec(wide, cum, ds, labels, s, axis, pad, w, h, fs, story.extra["y_title"]))
    return specs, FPS
