"""Charts for the open-middle receipt (render contract: src/cachereg/render.py).

The video is precomputed frame by frame (Vega-Lite has no tweening):
  1. sweep — closed-model bands draw left to right, quickly; the y-axis tops out at the closed peak.
  2. beat  — a pause to take in the layout.
  3. push  — open-weight bands grow in from the x-axis under the closed bands, lifting them, with a
             slow-start, long-settle ease so it feels heavy; the y-axis expands so nothing clips.
  4. hold.
Bands are stacked explicitly (y0/y1 per band) so order and scale are under our control. Labels sit
at the right edge throughout and blend between two solved layouts, so they never jump; gridlines are
drawn here (not by Vega) so they fade instead of popping as the axis grows.
"""

from __future__ import annotations

from datetime import timedelta
from functools import cache

import altair as alt
import polars as pl
from analysis import CLOSED_BANDS, MID
from PIL import ImageFont

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color, font_path
from cachereg.viz.theme import vl_config

FPS = 30
SWEEP, BEAT, PUSH, HOLD = 75, 45, 150, 90  # frames: 2.5 s, 1.5 s, 5 s, 3 s
T = 1e12
# Sizes at font_scale 1 (targets scale them: x_video 1.3, linkedin 1.2). Labels are sized to stay
# readable when a 1080-wide video is shown ~390 pt wide on a phone (≈10 pt).
LABEL_PX, AXIS_PX = 24, 18
SWATCH_GAP, TEXT_GAP = 18, 30  # px from the plot edge to the swatch centre / label text

# Monochrome greys on one lightness ramp: "other" darkest (on top), then lightest-to-darkest going
# down the stack from Anthropic. The accent is the only colour.
FILL = {
    "Other closed": "#30333C",
    "Anthropic": "#C3C8D3",
    "OpenAI": "#A3A9B7",
    "Google": "#858B9B",
    "Flagship open": "#6A7080",
    "Small open": "#535867",
    "Unattributed": "#24272F",
}
GRID = "#1C1F27"


def _fill(band: str) -> str:
    return color("accent") if band == MID else FILL[band]


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


def _rows(wide: pl.DataFrame, bands: list[str], reveal: float, scale: dict[str, float]) -> list[dict]:
    """Stacked rows for weeks up to `reveal` (fractional week index), with an interpolated edge."""
    weeks = wide["week"].to_list()
    vals = {b: (wide[b] / T).to_list() for b in bands}
    k = int(reveal)
    pts = [(weeks[i].isoformat(), {b: vals[b][i] for b in bands}) for i in range(k + 1)]
    frac = reveal - k
    if frac > 1e-6 and k + 1 < len(weeks):
        d = weeks[k] + timedelta(days=7 * frac)
        pts.append((d.isoformat(), {b: vals[b][k] + (vals[b][k + 1] - vals[b][k]) * frac for b in bands}))
    rows = []
    for d, v in pts:
        y = 0.0
        for b in bands:
            h = v[b] * scale.get(b, 1.0)
            rows.append({"week": d, "band": b, "y0": y, "y1": y + h})
            y += h
    return rows


def _stack_max(wide: pl.DataFrame, bands: list[str], scale: dict[str, float]) -> float:
    return max(sum(float(r[b]) / T * scale.get(b, 1.0) for b in bands) for r in wide.iter_rows(named=True))


def _raw_px(wide, bands, scale, y_max, plot_h) -> dict[str, float]:
    """Pixel y of each band's middle at the latest week (continuous in scale and y_max)."""
    last = wide.row(-1, named=True)
    y, out = 0.0, {}
    for b in bands:
        h = float(last[b]) / T * scale.get(b, 1.0)
        out[b] = plot_h * (1 - (y + h / 2) / y_max)
        y += h
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
    """Label offsets solved once before the push and once after, then blended with the push's ease.

    Each frame a label sits at its band's true middle plus the blended offset, so labels follow their
    bands continuously and never re-sort or pop.
    """

    def __init__(self, wide, bands, entering, closed_max, full_max, plot_h, font_px):
        top_first = list(reversed(bands))
        raw0 = _raw_px(wide, bands, {b: 0.0 for b in entering}, closed_max, plot_h)
        vis0 = [b for b in top_first if b not in entering]
        res0 = _resolve(raw0, vis0, plot_h, font_px)
        raw1 = _raw_px(wide, bands, {}, full_max, plot_h)
        res1 = _resolve(raw1, top_first, plot_h, font_px)
        self.off0 = {b: res0[b] - raw0[b] if b in vis0 else 0.0 for b in bands}
        self.off1 = {b: res1[b] - raw1[b] for b in bands}
        self.wide, self.bands, self.entering, self.plot_h = wide, bands, set(entering), plot_h

    def at(self, scale, y_max, e: float) -> list[dict]:
        raw = _raw_px(self.wide, self.bands, scale, y_max, self.plot_h)
        edge = self.wide["week"].max().isoformat()
        out = []
        for b in self.bands:
            opacity = min(1.0, e * 1.6) if b in self.entering else 1.0
            if opacity <= 0:
                continue
            px = raw[b] + self.off0[b] + (self.off1[b] - self.off0[b]) * e
            out.append({"week": edge, "band": b, "y": y_max * (1 - px / self.plot_h), "opacity": opacity})
        return out


def _ticks(y_max: float, plot_h: float, fade_odd: float) -> list[dict]:
    """Gridlines every 10T. Odd tens fade out over the push (`fade_odd` 0→1) when they would crowd the
    final axis; a new line appears as the top of the axis reaches it."""
    out = []
    for v in range(0, int(y_max) + 1, 10):
        o = 1.0 if v % 20 == 0 else 1.0 - fade_odd
        if v > 0:
            o *= max(0.0, min(1.0, (y_max - v) / y_max * plot_h / 1.5))  # appears within 1.5 px of the top
        if o > 0:
            out.append({"v": v, "t": f"{v}T", "o": o})
    return out


def _spec(wide, bands, rows, labels, y_max, width, height, fs, fade_odd: float) -> dict:
    fonts = brand()["fonts"]
    first, last = wide["week"].min().isoformat(), wide["week"].max().isoformat()
    pad = _pad(bands, fs)
    w, h = width - pad["left"] - pad["right"], height - pad["top"] - pad["bottom"]
    x_scale = alt.Scale(type="utc", domain=[first, last])
    y_scale = alt.Scale(domain=[0, y_max], nice=False, zero=True)
    fills = alt.Scale(domain=bands, range=[_fill(b) for b in bands])
    ink = alt.Scale(domain=bands, range=[color("accent") if b == MID else color("text_secondary") for b in bands])
    opacity = alt.Opacity("opacity:Q", scale=None, legend=None)
    quarters = [f"{y}-{m:02d}-01" for y in (2025, 2026) for m in (1, 4, 7, 10) if f"{y}-{m:02d}-01" <= last]
    year_expr = "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"

    ticks = alt.Data(values=_ticks(y_max, h, fade_odd))
    grid = (
        alt.Chart(ticks)
        .mark_rule(color=GRID, strokeWidth=1)
        .encode(y=alt.Y("v:Q", scale=y_scale), opacity=alt.Opacity("o:Q", scale=None, legend=None))
    )
    tick_labels = (
        alt.Chart(ticks)
        .mark_text(align="right", baseline="middle", dx=-10 * fs, fontSize=AXIS_PX * fs, font=fonts["mono"])
        .encode(
            x=alt.value(0),
            y=alt.Y("v:Q", scale=y_scale),
            text="t:N",
            opacity=alt.Opacity("o:Q", scale=None, legend=None),
            color=alt.value(color("text_secondary")),
        )
    )
    area = (
        alt.Chart(alt.Data(values=rows))
        .mark_area(interpolate="monotone", stroke=color("canvas"), strokeWidth=1.2 * fs)
        .encode(
            x=alt.X(
                "week:T",
                scale=x_scale,
                title=None,
                axis=alt.Axis(values=quarters, labelExpr=year_expr, labelFontSize=AXIS_PX * fs),
            ),
            y=alt.Y(
                "y0:Q",
                scale=y_scale,
                axis=alt.Axis(labels=False, grid=False, title="Weekly tokens", titlePadding=58 * fs),
            ),
            y2="y1:Q",
            color=alt.Color("band:N", scale=fills, legend=None),
        )
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
    spec = alt.layer(grid, tick_labels, area, swatch, text).resolve_scale(color="independent")
    spec = spec.properties(width=w, height=h).to_dict()
    spec["config"] = vl_config(fs)
    spec["autosize"] = {"type": "none"}
    spec["padding"] = pad
    return spec


def _schedule(wide, bands) -> list[tuple[float, dict[str, float], float, float]]:
    """(reveal position, per-band scale, y-axis max, push progress) for every frame."""
    n = wide.height - 1
    entering = [b for b in bands if b not in CLOSED_BANDS]
    hidden, shown = {b: 0.0 for b in entering}, {b: 1.0 for b in entering}
    closed_max, full_max = _stack_max(wide, bands, hidden), _stack_max(wide, bands, shown)
    out = [(n * ease_out_cubic(f / (SWEEP - 1)), hidden, closed_max, 0.0) for f in range(SWEEP)]
    out += [(n, hidden, closed_max, 0.0)] * BEAT
    for f in range(1, PUSH + 1):
        e = ease_in_out_quart(f / PUSH)
        s = {b: e for b in entering}
        out.append((n, s, max(closed_max, _stack_max(wide, bands, s)), e))
    out += [(n, shown, full_max, 1.0)] * HOLD
    return out


def _specs(story: Story, width: int, height: int, fs: float) -> tuple[list[dict], int]:
    wide, bands = story.frames["display"], list(story.extra["bands_order"])
    pad = _pad(bands, fs)
    plot_h = height - pad["top"] - pad["bottom"]
    entering = [b for b in bands if b not in CLOSED_BANDS]
    closed_max, full_max = _stack_max(wide, bands, {b: 0.0 for b in entering}), _stack_max(wide, bands, {})
    layout = LabelLayout(wide, bands, entering, closed_max, full_max, plot_h, LABEL_PX * fs)
    crowded = plot_h * 10 / full_max < 60 * fs  # 10T gridlines too dense on the final axis
    specs = []
    for reveal, scale, y_max, e in _schedule(wide, bands):
        rows = _rows(wide, bands, reveal, scale)
        labels = layout.at(scale, y_max, e)
        specs.append(_spec(wide, bands, rows, labels, y_max, width, height, fs, e if crowded else 0.0))
    return specs, FPS


def push_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    return _specs(story, width, height, font_scale)


def stack(story: Story, width, height, font_scale: float, interactive: bool = False) -> alt.Chart:
    """Static: the final frame (everything stacked)."""
    specs, _ = _specs(story, width, height, font_scale)
    return alt.Chart.from_dict(specs[-1])
