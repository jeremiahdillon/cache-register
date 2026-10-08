"""Charts for receipts/china-spend-share and china-token-share (render contract: src/cachereg/render.py).

The two folders' charts.py are identical; analysis.py differs (spend vs tokens) and sets extra["y_title"].
Two forms of each visual: stacked areas from the smoothed frame (`push`, `stack`) and stacked weekly bars from
the raw, unsmoothed frame (`push_bars`, `stack_bars`).

Adapted from receipts/open-middle/charts.py, but stacked to 100%. The video is precomputed frame by frame
(Vega-Lite has no tweening):
  1. sweep — the WSJ-style two-way split (OpenAI below, Anthropic above) draws left to right, quickly.
  2. beat  — a pause to take in the layout.
  3. push  — the Chinese-labs band grows in from zero thickness at the OpenAI/Anthropic boundary. Every
             frame is renormalised to 100%, so Anthropic and OpenAI are squeezed as it grows; same
             slow-start, long-settle ease as open-middle.
  4. hold.
In the bar form the sweep reveals one bar at a time (the next bar fades in), and weeks missing from the data
are gaps. Bands are stacked explicitly (y0/y1 per band) so order is under our control. Labels sit at the right
edge throughout and blend between two solved layouts (two bands, then three), so they never jump.
"""

from __future__ import annotations

from datetime import timedelta
from functools import cache

import altair as alt
import polars as pl
from analysis import CHINA, CLOSED_BANDS
from PIL import ImageFont

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color, font_path
from cachereg.viz.theme import vl_config

FPS = 30
SWEEP, BEAT, PUSH, HOLD = 75, 45, 150, 90  # frames: 2.5 s, 1.5 s, 5 s, 3 s
# Sizes at font_scale 1 (targets scale them: x_video 1.3, linkedin 1.2), as in open-middle.
LABEL_PX, AXIS_PX = 24, 18
SWATCH_GAP, TEXT_GAP = 18, 30  # px from the plot edge to the swatch centre / label text

# Darker greys than open-middle's for the two closed labs, so the accent carries the chart; the accent is
# the only colour.
FILL = {"Anthropic": "#6A7080", "OpenAI": "#4A4F5C"}
GRID = "#1C1F27"
BAR_DAYS = 6  # each weekly bar spans 6 of the week's 7 days, leaving a one-day gap


def _fill(band: str) -> str:
    return color("accent") if band == CHINA else FILL[band]


def ease_in_out_quart(t: float) -> float:
    return 8 * t**4 if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


@cache
def _text_w(text: str, px: int) -> float:
    return ImageFont.truetype(str(font_path("body")), px).getlength(text)


def _pad(bands: list[str], fs: float) -> dict:
    label_w = max(_text_w(b, round(LABEL_PX * fs)) for b in bands)
    right = round(TEXT_GAP * fs + label_w + 8 * fs)
    return {"left": round(72 * fs), "right": right, "top": round(16 * fs), "bottom": round(44 * fs)}


def _shares(v: dict[str, float], bands: list[str], scale: dict[str, float]) -> dict[str, float]:
    """Each band's share of the visible (scaled) total: the stack always sums to 1."""
    h = {b: v[b] * scale.get(b, 1.0) for b in bands}
    total = sum(h.values())
    return {b: h[b] / total if total else 0.0 for b in bands}


def _rows(wide: pl.DataFrame, bands: list[str], reveal: float, scale: dict[str, float]) -> list[dict]:
    """Stacked 100% rows for weeks up to `reveal` (fractional week index), with an interpolated edge."""
    weeks = wide["week"].to_list()
    vals = {b: wide[b].to_list() for b in bands}
    k = int(reveal)
    pts = [(weeks[i].isoformat(), {b: vals[b][i] for b in bands}) for i in range(k + 1)]
    frac = reveal - k
    if frac > 1e-6 and k + 1 < len(weeks):
        d = weeks[k] + (weeks[k + 1] - weeks[k]) * frac
        pts.append((d.isoformat(), {b: vals[b][k] + (vals[b][k + 1] - vals[b][k]) * frac for b in bands}))
    rows = []
    for d, v in pts:
        y = 0.0
        for b, s in _shares(v, bands, scale).items():
            rows.append({"week": d, "band": b, "y0": y, "y1": y + s})
            y += s
    return rows


def _bar_rows(wide: pl.DataFrame, bands: list[str], reveal: float, scale: dict[str, float]) -> list[dict]:
    """Stacked 100% bars for weeks up to `reveal`; the next bar fades in with the fractional part."""
    rows = []
    for i, r in enumerate(wide.iter_rows(named=True)):
        o = 1.0 if i <= reveal else reveal - (i - 1)
        if o <= 1e-6:
            break
        x0, x1 = r["week"].isoformat(), (r["week"] + timedelta(days=BAR_DAYS)).isoformat()
        y = 0.0
        for b, s in _shares(r, bands, scale).items():
            rows.append({"x0": x0, "x1": x1, "band": b, "y0": y, "y1": y + s, "o": o})
            y += s
    return rows


def _raw_px(wide, bands, scale, plot_h) -> dict[str, float]:
    """Pixel y of each band's middle at the latest week (continuous in scale)."""
    last = wide.row(-1, named=True)
    y, out = 0.0, {}
    for b, s in _shares(last, bands, scale).items():
        out[b] = plot_h * (1 - (y + s / 2))
        y += s
    return out


def _resolve(px: dict[str, float], order: list[str], plot_h: float, font_px: float) -> dict[str, float]:
    """Nudge labels apart (fixed top-to-bottom order) so none overlap and none fall outside the plot."""
    gap, out = font_px * 1.25, dict(px)
    if order:
        out[order[0]] = max(out[order[0]], font_px * 0.6)
    for a, b in zip(order, order[1:], strict=False):
        out[b] = max(out[b], out[a] + gap)
    if order and out[order[-1]] > plot_h - font_px * 0.6:
        out[order[-1]] = plot_h - font_px * 0.6
        for a, b in zip(reversed(order[:-1]), reversed(order[1:]), strict=False):
            out[a] = min(out[a], out[b] - gap)
    return out


class LabelLayout:
    """Label offsets solved once before the push and once after, then blended with the push's ease."""

    def __init__(self, wide, bands, entering, plot_h, font_px, edge: str):
        top_first = list(reversed(bands))
        raw0 = _raw_px(wide, bands, {b: 0.0 for b in entering}, plot_h)
        vis0 = [b for b in top_first if b not in entering]
        res0 = _resolve(raw0, vis0, plot_h, font_px)
        raw1 = _raw_px(wide, bands, {}, plot_h)
        res1 = _resolve(raw1, top_first, plot_h, font_px)
        self.off0 = {b: res0[b] - raw0[b] if b in vis0 else 0.0 for b in bands}
        self.off1 = {b: res1[b] - raw1[b] for b in bands}
        self.wide, self.bands, self.entering, self.plot_h, self.edge = wide, bands, set(entering), plot_h, edge

    def at(self, scale, e: float) -> list[dict]:
        raw = _raw_px(self.wide, self.bands, scale, self.plot_h)
        out = []
        for b in self.bands:
            opacity = min(1.0, e * 1.6) if b in self.entering else 1.0
            if opacity <= 0:
                continue
            px = raw[b] + self.off0[b] + (self.off1[b] - self.off0[b]) * e
            out.append({"week": self.edge, "band": b, "y": 1 - px / self.plot_h, "opacity": opacity})
        return out


TICKS = [{"v": v / 100, "t": f"{v}%"} for v in (0, 25, 50, 75, 100)]


def _spec(wide, bands, rows, labels, width, height, fs, y_title: str, bars: bool) -> dict:
    fonts = brand()["fonts"]
    first, last = wide["week"].min().isoformat(), _edge(wide, bars)
    pad = _pad(bands, fs)
    w, h = width - pad["left"] - pad["right"], height - pad["top"] - pad["bottom"]
    x_scale = alt.Scale(type="utc", domain=[first, last])
    y_scale = alt.Scale(domain=[0, 1], nice=False, zero=True)
    fills = alt.Scale(domain=bands, range=[_fill(b) for b in bands])
    ink = alt.Scale(domain=bands, range=[color("accent") if b == CHINA else color("text_secondary") for b in bands])
    opacity = alt.Opacity("opacity:Q", scale=None, legend=None)
    quarters = [f"{y}-{m:02d}-01" for y in (2025, 2026) for m in (1, 4, 7, 10) if f"{y}-{m:02d}-01" <= last]
    year_expr = "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"

    ticks = alt.Data(values=TICKS)
    tick_labels = (
        alt.Chart(ticks)
        .mark_text(align="right", baseline="middle", dx=-10 * fs, fontSize=AXIS_PX * fs, font=fonts["mono"])
        .encode(x=alt.value(0), y=alt.Y("v:Q", scale=y_scale), text="t:N", color=alt.value(color("text_secondary")))
    )
    x_axis = alt.Axis(values=quarters, labelExpr=year_expr, labelFontSize=AXIS_PX * fs)
    y_enc = alt.Y("y0:Q", scale=y_scale, axis=alt.Axis(labels=False, grid=False, title=y_title, titlePadding=58 * fs))
    band_fill = alt.Color("band:N", scale=fills, legend=None)
    if bars:
        area = (
            alt.Chart(alt.Data(values=rows))
            .mark_bar()
            .encode(
                x=alt.X("x0:T", scale=x_scale, title=None, axis=x_axis),
                x2="x1:T",
                y=y_enc,
                y2="y1:Q",
                color=band_fill,
                opacity=alt.Opacity("o:Q", scale=None, legend=None),
            )
        )
    else:
        area = (
            alt.Chart(alt.Data(values=rows))
            .mark_area(interpolate="monotone", stroke=color("canvas"), strokeWidth=1.2 * fs)
            .encode(x=alt.X("week:T", scale=x_scale, title=None, axis=x_axis), y=y_enc, y2="y1:Q", color=band_fill)
        )
    # Gridlines over the areas (a full stack hides anything drawn beneath it), in the canvas colour.
    grid = (
        alt.Chart(alt.Data(values=TICKS[1:-1]))
        .mark_rule(color=GRID, strokeWidth=1, opacity=0.6)
        .encode(y=alt.Y("v:Q", scale=y_scale))
    )
    swatch = (
        alt.Chart(alt.Data(values=labels))
        .mark_square(size=(0.55 * LABEL_PX * fs) ** 2, xOffset=SWATCH_GAP * fs, opacity=1)
        .encode(
            x=alt.X("week:T", scale=x_scale),
            y=alt.Y("y:Q", scale=y_scale),
            color=alt.Color("band:N", scale=fills, legend=None),
            opacity=opacity,
        )
    )
    text = (
        alt.Chart(alt.Data(values=labels))
        .mark_text(align="left", baseline="middle", dx=TEXT_GAP * fs, fontSize=LABEL_PX * fs, font=fonts["body"])
        .encode(
            x=alt.X("week:T", scale=x_scale),
            y=alt.Y("y:Q", scale=y_scale),
            text="band:N",
            opacity=opacity,
            color=alt.Color("band:N", scale=ink, legend=None),
        )
    )
    spec = alt.layer(tick_labels, area, grid, swatch, text).resolve_scale(color="independent")
    spec = spec.properties(width=w, height=h).to_dict()
    spec["config"] = vl_config(fs)
    spec["autosize"] = {"type": "none"}
    spec["padding"] = pad
    return spec


def _schedule(wide, bands) -> list[tuple[float, dict[str, float], float]]:
    """(reveal position, per-band scale, push progress) for every frame."""
    n = wide.height - 1
    entering = [b for b in bands if b not in CLOSED_BANDS]
    hidden, shown = {b: 0.0 for b in entering}, {b: 1.0 for b in entering}
    out = [(n * ease_out_cubic(f / (SWEEP - 1)), hidden, 0.0) for f in range(SWEEP)]
    out += [(n, hidden, 0.0)] * BEAT
    for f in range(1, PUSH + 1):
        e = ease_in_out_quart(f / PUSH)
        out.append((n, {b: e for b in entering}, e))
    out += [(n, shown, 1.0)] * HOLD
    return out


def _edge(wide: pl.DataFrame, bars: bool) -> str:
    """Right end of the x-axis (and where labels sit): the last week, or the end of its bar."""
    last = wide["week"].max()
    return (last + timedelta(days=BAR_DAYS) if bars else last).isoformat()


def _specs(story: Story, width: int, height: int, fs: float, bars: bool) -> tuple[list[dict], int]:
    # Bars show each week's actual values; areas use the smoothed frame.
    wide, bands = story.frames["wide" if bars else "display"], list(story.extra["bands_order"])
    pad = _pad(bands, fs)
    plot_h = height - pad["top"] - pad["bottom"]
    entering = [b for b in bands if b not in CLOSED_BANDS]
    layout = LabelLayout(wide, bands, entering, plot_h, LABEL_PX * fs, _edge(wide, bars))
    rows_of = _bar_rows if bars else _rows
    specs = []
    for reveal, scale, e in _schedule(wide, bands):
        rows = rows_of(wide, bands, reveal, scale)
        labels = layout.at(scale, e)
        specs.append(_spec(wide, bands, rows, labels, width, height, fs, story.extra["y_title"], bars))
    return specs, FPS


def push_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    return _specs(story, width, height, font_scale, bars=False)


def stack(story: Story, width, height, font_scale: float, interactive: bool = False) -> alt.Chart:
    """Static: the final frame (all three stacked)."""
    specs, _ = _specs(story, width, height, font_scale, bars=False)
    return alt.Chart.from_dict(specs[-1])


def push_bars_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    return _specs(story, width, height, font_scale, bars=True)


def stack_bars(story: Story, width, height, font_scale: float, interactive: bool = False) -> alt.Chart:
    """Static: the final frame of the bar form (raw weekly values, all three stacked)."""
    specs, _ = _specs(story, width, height, font_scale, bars=True)
    return alt.Chart.from_dict(specs[-1])
