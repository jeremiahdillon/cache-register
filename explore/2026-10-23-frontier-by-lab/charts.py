"""Charts for the frontier-by-lab exploration (render contract: src/cachereg/render.py).

Two visuals, one per benchmark (`intelligence`, `terminal_bench`). Each line is a step line of the best score
released so far: the four labs in their vendor colours, the best open-weight model in the accent. A dot marks each
new record; each line ends in a dot labelled with its current model and score; a legend above names the lines. On
Terminal-Bench the open-weight line names the lab each time the record changes hands (too many changes to do so on
the index).
"""

from __future__ import annotations

from datetime import UTC, datetime

import altair as alt
import polars as pl
from analysis import II, OPEN, TB

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX = 16, 14
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


def intelligence(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    # No holder labels: the record changes hands 14 times (five in Sep–Nov 2025 alone); labels there collide.
    return fit(lambda w, h: _chart(story, II, w, h, font_scale, interactive, holders=False), width, height)


def terminal_bench(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    return fit(lambda w, h: _chart(story, TB, w, h, font_scale, interactive, holders=True), width, height)


def holder_labels(rec: pl.DataFrame, first, last) -> pl.DataFrame:
    """The open-weight line's records where the record passes to another lab (the first record included), except
    one in the last 5% of the window: the end label beside it already names the model."""
    o = rec.filter(pl.col("series") == OPEN).sort("date")
    o = o.filter(pl.col("lab") != pl.col("lab").shift(1).fill_null(""))
    return o.filter(pl.col("date") < last - (last - first) * 0.05)


def _chart(
    story: Story, metric: str, width: float, height: float, fs: float, interactive: bool, holders: bool
) -> alt.Chart:
    fonts = brand()["fonts"]
    series = story.extra["series"]
    d = story.frames["steps"].filter(pl.col("metric") == metric)
    first, last = d["date"].min(), story.as_of

    clr = alt.Color("series:N", scale=alt.Scale(domain=series, range=[_ink(s) for s in series]), legend=None)
    legend = alt.Legend(
        orient="top", direction="horizontal", title=None, labelFontSize=LABEL_PX * fs, symbolSize=110 * fs**2,
        symbolStrokeWidth=0, columnPadding=22 * fs, offset=14 * fs, labelColor=color("text"),
    )  # fmt: skip
    ends = d.group_by("series", maintain_order=True).last().with_columns(date=pl.lit(last), carried=pl.lit(True))
    ends = ends.select(d.columns)
    label_chars = max(len(f"{m}  00.0") for m in ends["model"])
    label_px = (12 + label_chars * 0.56 * LABEL_PX + 6) * fs
    plot_px = max(width - label_px, 1.0)
    pad = (last - first) * (label_px / plot_px)
    x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(last + pad)])
    months = (1, 4, 7, 10) if plot_px >= 1000 * fs or last.year == first.year else (1, 7)
    ticks = [
        q for y in range(first.year, last.year + 1) for m in months if first <= (q := datetime(y, m, 1).date()) <= last
    ]  # fmt: skip
    top = (int(float(d["score"].max()) / 10) + 2) * 10  # headroom for the top end label
    x_axis = alt.Axis(
        values=[_ms(q) for q in ticks],
        labelExpr=(
            "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
        ),
        labelFontSize=AXIS_PX * fs,
        grid=False,
    )
    y_axis = alt.Axis(
        values=list(range(0, top + 1, 10)),
        labelFontSize=AXIS_PX * fs,
        title=story.extra["y_titles"][metric],
        titlePadding=12 * fs,
        grid=True,
    )
    x = alt.X("t:T", title=None, scale=x_scale, axis=x_axis)
    y_scale = alt.Scale(domain=[0, top], nice=False)
    y = alt.Y("score:Q", scale=y_scale, axis=y_axis)

    def with_t(df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(t=pl.col("date").map_elements(_ms, return_dtype=pl.Int64)).drop("date")

    # Each line runs on to the as-of date at its last record; the open-weight line is drawn last (on top).
    order = {s: i for i, s in enumerate(series)}
    line_rows = with_t(pl.concat([d, ends])).with_columns(
        z=pl.col("series").replace_strict(order, return_dtype=pl.Int64)
    )
    lines = (
        alt.Chart(alt.Data(values=line_rows.sort("z", "t").to_dicts()))
        .mark_line(interpolate="step-after", strokeWidth=2.4 * fs)
        .encode(x=x, y=y, color=clr.legend(legend), detail="series:N", order="z:Q")
    )
    rec = d.filter(~pl.col("carried"))
    dots = (
        alt.Chart(alt.Data(values=with_t(rec).to_dicts()))
        .mark_circle(size=34 * fs**2, opacity=1)
        .encode(x=x, y=y, color=clr)
    )
    if interactive:
        dots = dots.encode(
            tooltip=[
                alt.Tooltip("series:N", title="Line"),
                alt.Tooltip("variant:N", title="Model"),
                alt.Tooltip("lab:N", title="Lab"),
                alt.Tooltip("t:T", title="Released", format="%b %-d, %Y"),
                alt.Tooltip("score:Q", title="Score", format=".1f"),
            ]
        )

    # Who holds the open-weight record: the lab's name above the dot each time the record changes hands.
    held = with_t(holder_labels(rec, first, last) if holders else rec.clear())
    holder_text = (
        alt.Chart(alt.Data(values=held.to_dicts()))
        .mark_text(align="left", baseline="bottom", dx=-2 * fs, dy=-7 * fs, fontSize=(LABEL_PX - 3) * fs,
                   font=fonts["body"], color=color("accent"))
        .encode(x=x, y=y, text="lab:N")
    )  # fmt: skip

    # End labels, one line each: "<model> <score>" in the line's colour (the legend names the lines).
    lab = with_t(ends.sort("score", descending=True))
    gap = 1.3 * LABEL_PX * fs * top / height
    lab = lab.with_columns(
        label_y=pl.Series(_spread([min(v, top - 0.5 * gap) for v in lab["score"]], gap, 0.5 * gap)),
        text=pl.col("model") + "  " + pl.col("score").round(1).cast(pl.String),
    )
    lab_data = alt.Data(values=lab.to_dicts())
    end_dot = (
        alt.Chart(lab_data)
        .mark_circle(size=70 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
        .encode(x=x, y=y, color=clr)
    )
    text = (
        alt.Chart(lab_data)
        .mark_text(align="left", baseline="middle", dx=12 * fs, fontSize=LABEL_PX * fs, font=fonts["body"],
                   fontWeight=600)
        .encode(x=x, y=alt.Y("label_y:Q", scale=y_scale, axis=y_axis), text="text:N", color=clr)
    )  # fmt: skip
    chart = alt.layer(lines, dots, holder_text, end_dot, text).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))
