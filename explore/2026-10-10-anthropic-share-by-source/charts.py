"""Charts for the Anthropic-share-by-source exploration (render contract: src/cachereg/render.py).

One layout for three visuals: Anthropic's share of each source's reported total, three sources on one 0–100%
axis (same measure in each; author decision), weekly dots and a trailing 4-week line per source, labelled at
the line ends. On `spend`, a faint band shows OpenRouter's sensitivity to its unpriced tokens. The render
contract passes no visual name, so each visual has a thin function over the shared helper.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import altair as alt
import polars as pl

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX = 17, 15
NAMES = {"ramp": "Ramp", "vercel": "Vercel", "openrouter": "OpenRouter"}
# Categorical slots for the sources (not Anthropic's orange: every line is Anthropic); fixed per source.
SOURCE_SLOT = {"ramp": 0, "vercel": 2, "openrouter": 3}  # cyan, magenta, gold
MONTH_LABEL = "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"


def _ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _color(source: str) -> str:
    return brand()["colors"]["categorical"][SOURCE_SLOT[source]]


def spend(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    return fit(lambda w, h: _share(story, w, h, font_scale, "spend"), width, height)


def tokens(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    return fit(lambda w, h: _share(story, w, h, font_scale, "tokens"), width, height)


def tokens_with_free(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False):
    return fit(lambda w, h: _share(story, w, h, font_scale, "tokens-with-free"), width, height)


def _share(story: Story, width: float, height: float, fs: float, visual: str) -> alt.LayerChart:
    fonts = brand()["fonts"]
    measure, variant = {"spend": ("spend", None), "tokens": ("tokens", "paid"), "tokens-with-free": ("tokens", "all")}[
        visual
    ]
    # every line ends at the week the headline describes (the latest week all three sources cover)
    end = date.fromisoformat(story.extra["visuals"][visual]["week"])
    w = story.frames["weekly"].filter((pl.col("measure") == measure) & (pl.col("week") <= end))
    if measure == "tokens":
        w = w.filter((pl.col("source") != "openrouter") | (pl.col("variant") == variant))
    first, last = w["week"].min(), w["week"].max()
    label_px = (len("OpenRouter 100%") * 0.55 * (LABEL_PX - 1) + 24) * fs
    plot_w = max(width - 60 * fs, 1.0)  # first guess; fit corrects for the axes
    plot_h = max(height - 40 * fs, 1.0)
    span = _ms(last) - _ms(first)
    x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(last) + span * label_px / max(plot_w - label_px, 1.0)])
    y_scale = alt.Scale(domain=[0, 100], nice=False)
    # quarterly ticks through the first month after the last week (e.g. Oct after 27 Sep), which the axis
    # reaches because it extends past the last week for the end labels
    after = date(last.year + last.month // 12, last.month % 12 + 1, 1)
    ticks = [date(y, m, 1) for y in range(first.year, last.year + 2) for m in (1, 4, 7, 10)]
    x_axis = alt.Axis(
        values=[_ms(t) for t in ticks if first <= t <= after],
        labelExpr=MONTH_LABEL,
        labelFontSize=AXIS_PX * fs,
        grid=False,
        title=None,
    )
    # fixed ticks: automatic ones change with the height and make the outer size jump during fitting
    y_axis = alt.Axis(
        values=[0, 25, 50, 75, 100], labelExpr="datum.value + '%'", labelFontSize=AXIS_PX * fs, title=None
    )
    x = alt.X("t:T", scale=x_scale, axis=x_axis)

    rows = w.with_columns(t=pl.col("week").map_elements(_ms, return_dtype=pl.Int64))
    layers = []
    if measure == "spend":
        b = story.frames["or_bound"].filter(pl.col("week") <= end).sort("week")
        # one area per unbroken run of 4-week values, so the band breaks where the line does
        b = b.with_columns(run=pl.col("computed_r4").is_null().cum_sum()).drop_nulls(["computed_r4", "sensitivity_r4"])
        for (_,), part in b.group_by("run", maintain_order=True):
            band = alt.Data(
                values=part.select(
                    t=pl.col("week").map_elements(_ms, return_dtype=pl.Int64), lo="sensitivity_r4", hi="computed_r4"
                ).to_dicts()
            )
            layers.append(
                alt.Chart(band)
                .mark_area(color=_color("openrouter"), opacity=0.18)
                .encode(x=x, y=alt.Y("lo:Q", scale=y_scale, axis=y_axis), y2="hi:Q")
            )
    ends = []
    for src in ("ramp", "vercel", "openrouter"):
        s = rows.filter(pl.col("source") == src)
        c = _color(src)
        layers += [
            alt.Chart(alt.Data(values=s.select("t", "share_pct").to_dicts()))
            .mark_circle(size=16 * fs**2, opacity=0.35, color=c)
            .encode(x=x, y=alt.Y("share_pct:Q", scale=y_scale, axis=y_axis)),
            alt.Chart(alt.Data(values=s.select("t", "rolling4_pct").to_dicts()))
            .mark_line(color=c, strokeWidth=2.6 * fs)
            .encode(x=x, y=alt.Y("rolling4_pct:Q", scale=y_scale, axis=y_axis)),
        ]
        e = s.drop_nulls("rolling4_pct").row(-1, named=True)
        ends.append({"t": e["t"], "v": e["rolling4_pct"], "src": src, "name": f"{NAMES[src]} {e['rolling4_pct']:.0f}%"})

    # end labels, nudged apart in pixels so close lines stay legible
    gap = (LABEL_PX - 1) * fs * 1.25 / plot_h * 100
    placed: list[float] = []
    for e in sorted(ends, key=lambda r: r["v"], reverse=True):
        y = e["v"] if not placed else min(e["v"], placed[-1] - gap)
        placed.append(y)
        e["ly"] = y
    low = min(placed)
    for e in ends:
        e["ly"] = e["ly"] - min(low, 0)
    for e in ends:
        c = _color(e["src"])
        d = alt.Data(values=[e])
        layers += [
            alt.Chart(d)
            .mark_circle(size=70 * fs**2, opacity=1, color=c, stroke=color("canvas"), strokeWidth=2)
            .encode(x=x, y=alt.Y("v:Q", scale=y_scale, axis=y_axis)),
            alt.Chart(d)
            .mark_text(
                align="left",
                baseline="middle",
                dx=10 * fs,
                fontSize=(LABEL_PX - 1) * fs,
                font=fonts["body"],
                fontWeight="bold",
                color=c,
            )
            .encode(x=x, y=alt.Y("ly:Q", scale=y_scale, axis=y_axis), text="name:N"),
        ]
    # the measure, stamped on the chart's face (upper right), just below the 100% gridline
    layers.append(
        alt.Chart(alt.Data(values=[{"s": story.extra["stamp"][visual]}]))
        .mark_text(
            align="right",
            baseline="top",
            fontSize=(LABEL_PX + 3) * fs,
            fontWeight="bold",
            font=fonts["body"],
            color=color("text"),
        )
        .encode(x=alt.value(plot_w), y=alt.value(10 * fs), text="s:N")
    )
    return alt.layer(*layers).properties(width=plot_w, height=plot_h).configure(**vl_config(fs))
