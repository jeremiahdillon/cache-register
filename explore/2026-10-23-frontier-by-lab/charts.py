"""Charts for the frontier-by-lab exploration (render contract: src/cachereg/render.py).

Two stacked panels on one time axis (Intelligence Index above, Terminal-Bench 4.0 below). Each line is a step
line of the best score released so far: the four labs in their vendor colours, the best open-weight model in the
accent. A dot marks each new record; each line ends in a dot with a direct label (series, current model, score).
"""

from __future__ import annotations

from datetime import UTC, datetime

import altair as alt
import polars as pl
from analysis import METRICS, OPEN

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit, split
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX, PANEL_PX = 16, 14, 17
VENDOR = {"Anthropic": "anthropic", "OpenAI": "openai", "Google": "google", "Meta": "meta"}


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _ink(series: str) -> str:
    return color("accent") if series == OPEN else brand()["colors"]["vendor_colors"][VENDOR[series]]


def _spread(values: list[float], gap: float, lo: float) -> list[float]:
    """Label positions (same order as values, sorted high to low) at least `gap` apart, pushed up from `lo`."""
    out: list[float] = []
    for v in values:
        out.append(min(v, out[-1] - gap) if out else v)
    shift = lo - out[-1] if out and out[-1] < lo else 0.0
    return [y + shift for y in out]


def frontier(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    return fit(lambda w, h: _frontier(story, w, h, font_scale, interactive), width, height)


def _frontier(story: Story, width: float, height: float, fs: float, interactive: bool) -> alt.Chart:
    fonts = brand()["fonts"]
    series = story.extra["series"]
    steps = story.frames["steps"]
    first, last = steps["date"].min(), story.as_of

    clr = alt.Color("series:N", scale=alt.Scale(domain=series, range=[_ink(s) for s in series]), legend=None)
    legend = alt.Legend(
        orient="top", direction="horizontal", title=None, labelFontSize=LABEL_PX * fs, symbolSize=110 * fs**2,
        symbolStrokeWidth=0, columnPadding=22 * fs, offset=6 * fs, labelColor=color("text"),
    )  # fmt: skip
    legend_clr = clr.legend(legend)
    ends_all = steps.group_by("metric", "series").last()
    label_chars = max(len(f"{m}  00.0") for m in ends_all["model"])
    label_px = (12 + label_chars * 0.56 * LABEL_PX + 6) * fs
    plot_px = max(width - label_px, 1.0)
    pad = (last - first) * (label_px / plot_px)
    x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(last + pad)])
    months = (1, 4, 7, 10) if plot_px >= 1000 * fs else (1, 7)  # half-yearly ticks on narrow charts
    quarters = [
        q for y in range(first.year, last.year + 1) for m in months if first <= (q := datetime(y, m, 1).date()) <= last
    ]  # fmt: skip
    spacing = 34 * fs
    heights = split(height, 2)

    def panel(metric: str, show_x: bool, panel_h: float, show_legend: bool = False) -> alt.LayerChart:
        title = story.extra["panels"][metric]
        d = steps.filter(pl.col("metric") == metric)
        hi = float(d["score"].max())
        top = (int(hi / 10) + 2) * 10  # headroom for the top end label
        x_axis = alt.Axis(
            values=[_ms(q) for q in quarters],
            labelExpr=(
                "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
            ),
            labelFontSize=AXIS_PX * fs,
            labels=show_x,
            ticks=show_x,
            grid=False,
        )
        y_axis = alt.Axis(values=list(range(0, top + 1, 10)), labelFontSize=AXIS_PX * fs, title=None, grid=True)
        x = alt.X("t:T", title=None, scale=x_scale, axis=x_axis)
        y = alt.Y("score:Q", scale=alt.Scale(domain=[0, top], nice=False), axis=y_axis)

        # Each line runs on to the as-of date at its last record.
        ends = (
            d.group_by("series", maintain_order=True)
            .last()
            .with_columns(date=pl.lit(last), carried=pl.lit(True))
            .select(d.columns)
        )
        line_rows = pl.concat([d, ends]).sort("series", "date")
        line_rows = line_rows.with_columns(t=pl.col("date").map_elements(_ms, return_dtype=pl.Int64))
        # The open-weight line is drawn last (on top).
        order = {s: i for i, s in enumerate(series)}
        line_rows = line_rows.with_columns(z=pl.col("series").replace_strict(order, return_dtype=pl.Int64)).sort(
            "z", "t"
        )
        lines = (
            alt.Chart(alt.Data(values=line_rows.drop("date").to_dicts()))
            .mark_line(interpolate="step-after", strokeWidth=2.4 * fs)
            .encode(x=x, y=y, color=legend_clr if show_legend else clr, detail="series:N", order="z:Q")
        )
        rec = d.filter(~pl.col("carried")).with_columns(t=pl.col("date").map_elements(_ms, return_dtype=pl.Int64))
        dots = (
            alt.Chart(alt.Data(values=rec.drop("date").to_dicts()))
            .mark_circle(size=34 * fs**2, opacity=1)
            .encode(x=x, y=y, color=clr)
        )
        if interactive:
            dots = dots.encode(
                tooltip=[
                    alt.Tooltip("series:N", title="Line"),
                    alt.Tooltip("variant:N", title="Model"),
                    alt.Tooltip("t:T", title="Released", format="%b %-d, %Y"),
                    alt.Tooltip("score:Q", title="Score", format=".1f"),
                ]
            )

        # End labels, one line each: "<model> <score>" in the line's colour (the legend names the lines).
        lab = ends.sort("score", descending=True).with_columns(t=pl.lit(_ms(last)))
        gap = 1.3 * LABEL_PX * fs * top / panel_h
        lab = lab.with_columns(
            label_y=pl.Series(_spread([min(v, top - 0.5 * gap) for v in lab["score"]], gap, 0.5 * gap)),
            text=pl.col("model") + "  " + pl.col("score").round(1).cast(pl.String),
        )
        lab_data = alt.Data(values=lab.drop("date").to_dicts())
        end_dot = (
            alt.Chart(lab_data)
            .mark_circle(size=70 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
            .encode(x=x, y=y, color=clr)
        )
        y_lab = alt.Y("label_y:Q", scale=alt.Scale(domain=[0, top], nice=False), axis=y_axis)
        text = (
            alt.Chart(lab_data)
            .mark_text(align="left", baseline="middle", dx=12 * fs, fontSize=LABEL_PX * fs, font=fonts["body"],
                       fontWeight=600)
            .encode(x=x, y=y_lab, text="text:N", color=clr)
        )  # fmt: skip
        return alt.layer(lines, dots, end_dot, text).properties(
            width=width,
            height=panel_h,
            title=alt.TitleParams(
                title, anchor="start", fontSize=PANEL_PX * fs, font=fonts["body"], color=color("text"), offset=10 * fs
            ),
        )

    metrics = list(METRICS)
    chart = alt.vconcat(
        panel(metrics[0], False, heights[0], show_legend=True), panel(metrics[1], True, heights[1]), spacing=spacing
    )
    return chart.configure(**vl_config(fs))
