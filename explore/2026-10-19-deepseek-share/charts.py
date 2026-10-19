"""Charts for explore/2026-10-19-deepseek-share (render contract: src/cachereg/render.py). Static only.

* `lines`  — weekly tokens: DeepSeek (the accent) against closed US models and all US models (greys).
* `stack`  — closed US models as weekly bars stacked by developer (vendor colours), DeepSeek as a line over them.
* `latest` — the latest week as three horizontal bars: DeepSeek, closed US models (by developer), all US models.
Labels sit at the right edge (lines, stack) and are nudged apart so none overlap.
"""

from __future__ import annotations

import math
from datetime import timedelta
from functools import cache

import altair as alt
import polars as pl
from analysis import DEEPSEEK, LAB_ORDER, US_ALL, US_CLOSED, US_OPEN, T, fmt_t
from PIL import ImageFont

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color, font_path
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX = 22, 18  # at font_scale 1
SWATCH_GAP, TEXT_GAP = 18, 30  # px from the plot edge to the swatch centre / label text
GRID = "#1C1F27"
OPEN_GREY = "#30343F"  # US open-weight models: darker than muted (other US closed), so the two read apart
BAR_DAYS = 6  # each weekly bar spans 6 of the week's 7 days
VENDOR_KEY = {"OpenAI": "openai", "Anthropic": "anthropic", "Google": "google", "xAI (Grok)": "xai"}


def _fill(band: str) -> str:
    if band == DEEPSEEK:
        return color("accent")
    if band in VENDOR_KEY:
        return color("vendor_colors")[VENDOR_KEY[band]]
    if band == US_OPEN:
        return OPEN_GREY
    return color("muted")  # Other US closed


@cache
def _text_w(text: str, px: int) -> float:
    return ImageFont.truetype(str(font_path("body")), px).getlength(text)


def _pad(labels: list[str], fs: float, left: float = 72) -> dict:
    label_w = max(_text_w(t, round(LABEL_PX * fs)) for t in labels)
    return {
        "left": round(left * fs),
        "right": round(TEXT_GAP * fs + label_w + 8 * fs),
        "top": round(16 * fs),
        "bottom": round(44 * fs),
    }


def _nice_ticks(y_max: float, n: int = 4) -> list[float]:
    """Round tick values (in tokens) from 0 to at least y_max."""
    raw = y_max / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return [i * step for i in range(math.ceil(y_max / step) + 1)]


def _resolve(px: dict[str, float], plot_h: float, font_px: float) -> dict[str, float]:
    """Nudge labels apart (kept in their top-to-bottom order) so none overlap or leave the plot."""
    order = sorted(px, key=px.get)
    gap, out = font_px * 1.25, dict(px)
    out[order[0]] = max(out[order[0]], font_px * 0.6)
    for a, b in zip(order, order[1:], strict=False):
        out[b] = max(out[b], out[a] + gap)
    if out[order[-1]] > plot_h - font_px * 0.6:
        out[order[-1]] = plot_h - font_px * 0.6
        for a, b in zip(reversed(order[:-1]), reversed(order[1:]), strict=False):
            out[a] = min(out[a], out[b] - gap)
    return out


def _labels(values: dict[str, float], ticks: list[float], plot_h: float, fs: float) -> list[dict]:
    """Right-edge labels: each series' latest value in pixel space, resolved, back to token units."""
    y_max = ticks[-1]
    px = {k: plot_h * (1 - v / y_max) for k, v in values.items()}
    res = _resolve(px, plot_h, LABEL_PX * fs)
    return [{"band": k, "y": y_max * (1 - res[k] / plot_h)} for k in values]


def _frame(wide: pl.DataFrame, labels: list[dict], text: dict[str, str], ticks, edge: str, w, h, fs, y_title):
    """Shared layers: y tick labels, grid, right-edge swatches and labels. Returns (layers, x_scale, y_scale)."""
    fonts = brand()["fonts"]
    first = wide["week"].min().replace(day=1).isoformat()
    x_scale = alt.Scale(type="utc", domain=[first, edge])
    y_scale = alt.Scale(domain=[0, ticks[-1]], nice=False, zero=True)
    tick_rows = [{"v": v, "t": f"{v / T:g}T"} for v in ticks]
    tick_labels = (
        alt.Chart(alt.Data(values=tick_rows))
        .mark_text(align="right", baseline="middle", dx=-10 * fs, fontSize=AXIS_PX * fs, font=fonts["mono"])
        .encode(x=alt.value(0), y=alt.Y("v:Q", scale=y_scale), text="t:N", color=alt.value(color("text_secondary")))
    )
    grid = (
        alt.Chart(alt.Data(values=tick_rows[1:]))
        .mark_rule(color=GRID, strokeWidth=1)
        .encode(
            y=alt.Y("v:Q", scale=y_scale, axis=alt.Axis(labels=False, grid=False, title=y_title, titlePadding=58 * fs))
        )
    )
    rows = [{**r, "week": edge, "text": text[r["band"]]} for r in labels]
    bands = [r["band"] for r in rows]
    fills = alt.Scale(domain=bands, range=[_fill(b) for b in bands])
    swatch = (
        alt.Chart(alt.Data(values=rows))
        .mark_square(size=(0.55 * LABEL_PX * fs) ** 2, xOffset=SWATCH_GAP * fs, opacity=1)
        .encode(
            x=alt.X("week:T", scale=x_scale),
            y=alt.Y("y:Q", scale=y_scale),
            color=alt.Color("band:N", scale=fills, legend=None),
        )
    )
    ink = alt.Scale(domain=bands, range=[color("accent") if b == DEEPSEEK else color("text_secondary") for b in bands])
    label = (
        alt.Chart(alt.Data(values=rows))
        .mark_text(align="left", baseline="middle", dx=TEXT_GAP * fs, fontSize=LABEL_PX * fs, font=fonts["body"])
        .encode(
            x=alt.X("week:T", scale=x_scale),
            y=alt.Y("y:Q", scale=y_scale),
            text="text:N",
            color=alt.Color("band:N", scale=ink, legend=None),
        )
    )
    return [tick_labels, grid], [swatch, label], x_scale, y_scale


def _x_axis(edge: str, fs: float) -> alt.Axis:
    quarters = [f"{y}-{m:02d}-01" for y in (2025, 2026) for m in (1, 4, 7, 10) if f"{y}-{m:02d}-01" <= edge]
    year = "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
    return alt.Axis(values=quarters, labelExpr=year, labelFontSize=AXIS_PX * fs)


def _finish(layers, w, h, pad, fs) -> alt.Chart:
    spec = alt.layer(*layers).resolve_scale(color="independent").properties(width=w, height=h).to_dict()
    spec["config"] = vl_config(fs)
    spec["autosize"] = {"type": "none"}
    spec["padding"] = pad
    return alt.Chart.from_dict(spec)


def lines(story: Story, width, height, font_scale: float, interactive: bool = False) -> alt.Chart:
    fs = font_scale
    wide = story.frames["wide"]
    series = [US_ALL, US_CLOSED, DEEPSEEK]
    last = wide.row(-1, named=True)
    text = {s: f"{s.replace(' models', '')} {fmt_t(last[s])}" for s in series}
    text[US_ALL], text[US_CLOSED] = f"All US {fmt_t(last[US_ALL])}", f"US closed {fmt_t(last[US_CLOSED])}"
    pad = _pad(list(text.values()), fs)
    w, h = width - pad["left"] - pad["right"], height - pad["top"] - pad["bottom"]
    ticks = _nice_ticks(max(wide[s].max() for s in series))
    edge = wide["week"].max().isoformat()
    labels = _labels({s: last[s] for s in series}, ticks, h, fs)
    under, over, x_scale, y_scale = _frame(wide, labels, text, ticks, edge, w, h, fs, story.extra["y_title"])
    rows = [{"week": r["week"].isoformat(), "band": s, "v": r[s]} for r in wide.iter_rows(named=True) for s in series]
    style = {
        US_ALL: (color("text_secondary"), 2.2, [7, 5]),
        US_CLOSED: (color("text_secondary"), 2.6, []),
        DEEPSEEK: (color("accent"), 4.0, []),
    }
    marks = [
        alt.Chart(alt.Data(values=rows))
        .transform_filter(alt.datum.band == s)
        .mark_line(color=c, strokeWidth=sw * fs, strokeDash=dash, interpolate="monotone")
        .encode(x=alt.X("week:T", scale=x_scale, title=None, axis=_x_axis(edge, fs)), y=alt.Y("v:Q", scale=y_scale))
        for s, (c, sw, dash) in style.items()
    ]
    return _finish([*under, *marks, *over], w, h, pad, fs)


def stack(story: Story, width, height, font_scale: float, interactive: bool = False) -> alt.Chart:
    fs = font_scale
    wide = story.frames["wide"]
    last = wide.row(-1, named=True)
    text = {b: f"{b} {fmt_t(last[b])}" for b in [*LAB_ORDER, DEEPSEEK]}
    pad = _pad(list(text.values()), fs)
    w, h = width - pad["left"] - pad["right"], height - pad["top"] - pad["bottom"]
    ticks = _nice_ticks(max(wide[US_CLOSED].max(), wide[DEEPSEEK].max()))
    edge = (wide["week"].max() + timedelta(days=BAR_DAYS)).isoformat()
    # Label anchors: each band's middle in the last bar, DeepSeek at its last value.
    anchors, y = {}, 0.0
    for b in LAB_ORDER:
        anchors[b] = y + last[b] / 2
        y += last[b]
    anchors[DEEPSEEK] = last[DEEPSEEK]
    labels = _labels(anchors, ticks, h, fs)
    under, over, x_scale, y_scale = _frame(wide, labels, text, ticks, edge, w, h, fs, story.extra["y_title"])
    bars = []
    for r in wide.iter_rows(named=True):
        y = 0.0
        for b in LAB_ORDER:
            bars.append(
                {
                    "x0": r["week"].isoformat(),
                    "x1": (r["week"] + timedelta(days=BAR_DAYS)).isoformat(),
                    "band": b,
                    "y0": y,
                    "y1": y + r[b],
                }
            )
            y += r[b]
    fills = alt.Scale(domain=LAB_ORDER, range=[_fill(b) for b in LAB_ORDER])
    bar = (
        alt.Chart(alt.Data(values=bars))
        .mark_bar()
        .encode(
            x=alt.X("x0:T", scale=x_scale, title=None, axis=_x_axis(edge, fs)),
            x2="x1:T",
            y=alt.Y("y0:Q", scale=y_scale),
            y2="y1:Q",
            color=alt.Color("band:N", scale=fills, legend=None),
        )
    )
    # DeepSeek's line through the middle of each week's bar, with a canvas-coloured casing so it reads over bars.
    mid = BAR_DAYS / 2
    pts = [
        {"week": (r["week"] + timedelta(days=mid)).isoformat(), "v": r[DEEPSEEK]} for r in wide.iter_rows(named=True)
    ]
    casing = (
        alt.Chart(alt.Data(values=pts))
        .mark_line(color=color("canvas"), strokeWidth=8 * fs, interpolate="monotone")
        .encode(x=alt.X("week:T", scale=x_scale), y=alt.Y("v:Q", scale=y_scale))
    )
    line = casing.mark_line(color=color("accent"), strokeWidth=4 * fs, interpolate="monotone")
    return _finish([*under, bar, casing, line, *over], w, h, pad, fs)


def latest(story: Story, width, height, font_scale: float, interactive: bool = False) -> alt.Chart:
    """Latest week: DeepSeek, closed US models by developer, all US models (closed by developer + open)."""
    fs = font_scale
    fonts = brand()["fonts"]
    last = story.frames["wide"].row(-1, named=True)
    rows_order = [DEEPSEEK, US_CLOSED, US_ALL]
    names = {DEEPSEEK: "DeepSeek", US_CLOSED: "US closed", US_ALL: "All US"}
    segs = {DEEPSEEK: [DEEPSEEK], US_CLOSED: LAB_ORDER, US_ALL: [*LAB_ORDER, US_OPEN]}
    totals = {k: last[k] for k in rows_order}
    x_max = max(totals.values()) * 1.18  # room for the total at the bar end
    name_w = max(_text_w(n, round(LABEL_PX * fs)) for n in names.values())
    pad = {"left": round(name_w + 28 * fs), "right": round(24 * fs), "top": round(16 * fs), "bottom": round(96 * fs)}
    w, h = width - pad["left"] - pad["right"], height - pad["top"] - pad["bottom"]
    x_scale = alt.Scale(domain=[0, x_max], nice=False, zero=True)
    y_scale = alt.Scale(domain=rows_order, paddingInner=0.35, paddingOuter=0.2)
    bars = []
    for row in rows_order:
        x = 0.0
        for b in segs[row]:
            bars.append({"row": row, "band": b, "x0": x, "x1": x + last[b]})
            x += last[b]
    bands = [DEEPSEEK, *LAB_ORDER, US_OPEN]
    fills = alt.Scale(domain=bands, range=[_fill(b) for b in bands])
    y_enc = alt.Y("row:N", scale=y_scale, sort=rows_order, title=None, axis=None)
    bar = (
        alt.Chart(alt.Data(values=bars))
        .mark_bar(stroke=color("canvas"), strokeWidth=1.5 * fs)
        .encode(
            x=alt.X("x0:Q", scale=x_scale, axis=None),
            x2="x1:Q",
            y=y_enc,
            color=alt.Color("band:N", scale=fills, legend=None),
        )
    )
    row_names = (
        alt.Chart(alt.Data(values=[{"row": r, "t": names[r]} for r in rows_order]))
        .mark_text(align="right", baseline="middle", dx=-14 * fs, fontSize=LABEL_PX * fs, font=fonts["body"])
        .encode(
            x=alt.value(0),
            y=y_enc,
            text="t:N",
            color=alt.condition(
                alt.datum.row == DEEPSEEK, alt.value(color("accent")), alt.value(color("text_secondary"))
            ),
        )
    )
    total_text = (
        alt.Chart(alt.Data(values=[{"row": r, "x": totals[r], "t": fmt_t(totals[r])} for r in rows_order]))
        .mark_text(align="left", baseline="middle", dx=12 * fs, fontSize=LABEL_PX * 1.15 * fs, font=fonts["mono"])
        .encode(
            x=alt.X("x:Q", scale=x_scale),
            y=y_enc,
            text="t:N",
            color=alt.condition(alt.datum.row == DEEPSEEK, alt.value(color("accent")), alt.value(color("text"))),
        )
    )
    # Legend under the bars: one swatch + name per developer band (DeepSeek is named on its own bar).
    legend_px = round(LABEL_PX * 0.85 * fs)
    leg, x = [], 0.0
    for b in [*LAB_ORDER, US_OPEN]:
        t = "US open weights" if b == US_OPEN else b
        leg.append({"band": b, "px": x, "t": t})
        x += legend_px * 1.1 + _text_w(t, legend_px) + 26 * fs
    scale_px = min(1.0, w / x)  # shrink the gaps' pixel positions if the legend is wider than the plot (portrait)
    rows = []
    for i, r in enumerate(leg):
        line = 0 if scale_px == 1.0 else i // 3  # wrap after three entries on narrow targets
        start = leg[(i // 3) * 3]["px"] if line else 0
        rows.append({**r, "px": r["px"] - start, "py": h + (40 + line * 34) * fs})
    sw = (
        alt.Chart(alt.Data(values=rows))
        .mark_square(size=(0.55 * legend_px) ** 2, opacity=1)
        .encode(
            x=alt.X("px:Q", scale=None),
            y=alt.Y("py:Q", scale=None),
            color=alt.Color("band:N", scale=fills, legend=None),
        )
    )
    lt = (
        alt.Chart(alt.Data(values=rows))
        .mark_text(
            align="left",
            baseline="middle",
            dx=legend_px * 0.8,
            fontSize=legend_px,
            font=fonts["body"],
            color=color("text_secondary"),
        )
        .encode(x=alt.X("px:Q", scale=None), y=alt.Y("py:Q", scale=None), text="t:N")
    )
    return _finish([bar, row_names, total_text, sw, lt], w, h, pad, fs)


# ---- build: the motion chart -------------------------------------------------------------------------------
# Each step's bars grow up from the stack so far (DeepSeek's from the axis, in front), lifting a bold line; the
# previous bold grey line turns light as they rise. They hold, then their bottom edge wipes up into the line until
# they are gone, and the next step's bars grow on from there in one continuous upward motion. Bars are clipped to
# their bounding lines: each is a slice of the band between the line below and the line above, so its top and bottom
# edges lie on those lines everywhere (the first and last bars are half width, where the lines end). The final
# frame: light grey lines for each step, the bold grey line (all US models) and the lime DeepSeek line.

FPS = 30
LEAD, GROW, STAY, WIPE, HOLD = 12, 30, 30, 24, 75  # frames per phase (grey steps); STAY = 1 s at full height
DS_PAUSE, DS_GROW, DS_STAY, DS_WIPE = 45, 48, 30, 30  # a longer beat before DeepSeek; its step is slower
# Each step is one or more columns of the wide frame; xAI is rolled into other closed US models here.
BUILD_STEPS = [["Anthropic"], ["OpenAI"], ["Google"], ["xAI (Grok)", "Other US closed"], [US_OPEN]]
BAR_GREY = "#D3D7E0"  # bars a shade brighter than the bold line, so the incoming step stands out
BOLD_W, DS_W, LIGHT_W = 5.0, 6.0, 1.6  # the top US line and DeepSeek's are the heavy ones


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_cubic(t: float) -> float:
    return t**3


def _build_schedule() -> list[dict]:
    """Per frame: top progress per step (0..1), the step on stage and its wipe progress (0..1, bottom edge).

    The wipe accelerates into the line (ease-in) and the next growth leaves it at speed (ease-out), back to back,
    so the hand-over reads as one upward motion."""
    n = len(BUILD_STEPS) + 1  # + DeepSeek
    push = [0.0] * n
    idle = {"stage": None, "wipe": 0.0}
    frames = [{"push": list(push), **idle}] * LEAD
    for k in range(n):
        ds = k == n - 1
        grow, stay, wipe = (DS_GROW, DS_STAY, DS_WIPE) if ds else (GROW, STAY, WIPE)
        if ds:
            frames += [{"push": list(push), **idle}] * DS_PAUSE
        for i in range(1, grow + 1):
            push[k] = ease_out_cubic(i / grow)
            frames.append({"push": list(push), "stage": k, "wipe": 0.0})
        frames += [{"push": list(push), "stage": k, "wipe": 0.0}] * stay
        for i in range(1, wipe):  # the last wipe frame would be an empty bar: the next step's first frame follows
            frames.append({"push": list(push), "stage": k, "wipe": ease_in_cubic(i / wipe)})
        frames.append({"push": list(push), **idle})
    frames += [{"push": list(push), **idle}] * HOLD
    return frames


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


def _build_spec(wide, cum, ds, labels_text, state, ticks, pad, w, h, fs, y_title) -> dict:
    fonts = brand()["fonts"]
    first = wide["week"].min().replace(day=1)
    edge = (wide["week"].max() + timedelta(days=BAR_DAYS)).isoformat()
    x_scale = alt.Scale(type="utc", domain=[first.isoformat(), edge])
    y_scale = alt.Scale(domain=[0, ticks[-1]], nice=False, zero=True)
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
        label_vals[f"g{k}"] = (top[-1], lightness, min(1.0, push[k] * 1.5))
    k_ds = n_grey
    if push[k_ds] > 0:
        dtop = [push[k_ds] * v for v in ds]
        lines += [
            {"x": x, "v": v, "s": "ds", "sw": DS_W * fs, "c": color("accent")} for x, v in zip(mid, dtop, strict=True)
        ]
        label_vals["ds"] = (dtop[-1], 0.0, min(1.0, push[k_ds] * 1.5))

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
    # Right-edge labels, nudged apart; light lines get light labels.
    if label_vals:
        px = {s: h * (1 - v / ticks[-1]) for s, (v, _, _) in label_vals.items()}
        res = _resolve(px, h, LABEL_PX * fs)
        rows = []
        for s, (_, lightness, o) in label_vals.items():
            ink = color("accent") if s == "ds" else _mix(color("text"), color("muted"), lightness)
            rows.append({"x": edge, "y": ticks[-1] * (1 - res[s] / h), "t": labels_text[s], "c": ink, "o": o})
        layers.append(
            alt.Chart(alt.Data(values=rows))
            .mark_text(align="left", baseline="middle", dx=14 * fs, fontSize=LABEL_PX * fs, font=fonts["body"])
            .encode(
                x=alt.X("x:T", scale=x_scale),
                y=alt.Y("y:Q", scale=y_scale),
                text="t:N",
                color=alt.Color("c:N", scale=None),
                opacity=alt.Opacity("o:Q", scale=None),
            )
        )
    spec = alt.layer(*layers).properties(width=w, height=h).to_dict()
    spec["config"] = vl_config(fs)
    spec["autosize"] = {"type": "none"}
    spec["padding"] = pad
    return spec


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
        "g4": f"+ Open = All US {fmt_t(last[US_ALL])}",
        "ds": f"DeepSeek {fmt_t(last[DEEPSEEK])}",
    }
    label_w = max(_text_w(t, round(LABEL_PX * fs)) for t in text.values())
    pad = {
        "left": round(72 * fs),
        "right": round(14 * fs + label_w + 8 * fs),
        "top": round(16 * fs),
        "bottom": round(44 * fs),
    }
    w, h = width - pad["left"] - pad["right"], height - pad["top"] - pad["bottom"]
    ticks = _nice_ticks(max(max(cum[-1]), max(ds)))
    specs = [
        _build_spec(wide, cum, ds, text, s, ticks, pad, w, h, fs, story.extra["y_title"]) for s in _build_schedule()
    ]
    return specs, FPS
