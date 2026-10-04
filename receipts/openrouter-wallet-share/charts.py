"""Chart definitions for the wallet-share story. One function per form; every target reuses them."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import altair as alt
import polars as pl
from analysis import GROUP_COLOR_KEY, GROUP_ORDER

from cachereg.story.model import Story
from cachereg.viz import motion
from cachereg.viz.brand import brand, color
from cachereg.viz.theme import vl_config


def group_scale() -> alt.Scale:
    vc = brand()["colors"]["vendor_colors"]
    rng = [vc[GROUP_COLOR_KEY[g]] if g in GROUP_COLOR_KEY else color("muted") for g in GROUP_ORDER]
    return alt.Scale(domain=GROUP_ORDER, range=rng)


def _repel(values: list[float], min_gap: float, lo: float, hi: float) -> list[float]:
    """Spread end-label positions so none overlap, keeping order and staying inside [lo, hi]."""
    order = sorted(range(len(values)), key=lambda i: -values[i])
    pos = [min(hi, values[i]) for i in order]
    for k in range(1, len(pos)):  # push down
        pos[k] = min(pos[k], pos[k - 1] - min_gap)
    if pos and pos[-1] < lo:  # then push back up from the floor
        pos[-1] = lo
        for k in range(len(pos) - 2, -1, -1):
            pos[k] = max(pos[k], pos[k + 1] + min_gap)
    out = values[:]
    for k, i in enumerate(order):
        out[i] = pos[k]
    return out


def line_chart(story: Story, width: int, height: int, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    g = story.frames["groups"].with_columns(pl.col("week").cast(pl.Date))
    weeks = sorted(g["week"].unique().to_list())
    last = weeks[-1]
    y_max = min(1.0, round(g["share"].max() * 1.12 + 0.05, 1))
    x_dom = [weeks[0].isoformat(), (last + timedelta(days=24)).isoformat()]  # room for end labels
    x_scale = alt.Scale(type="utc", domain=x_dom)
    if len(weeks) > 16:  # long windows: ticks on month starts, at most ~8 of them
        months = [d for d in (weeks[0] + timedelta(days=i) for i in range((last - weeks[0]).days + 1)) if d.day == 1]
        ticks, label = months[:: max(1, -(-len(months) // 8))], "%b '%y"
    else:  # ticks on data weeks
        ticks, label = weeks[:: 2 if len(weeks) > 8 else 1], "%b %-d"
    x_axis = alt.Axis(
        # formatType="utc" makes this Vega-Lite build ignore `format`; format labels explicitly in UTC.
        labelExpr=f'utcFormat(datum.value, "{label}")',
        values=[int(datetime(t.year, t.month, t.day, tzinfo=UTC).timestamp() * 1000) for t in ticks],  # UTC epoch ms
        labelFontSize=15 * font_scale,
    )

    def xenc(field: str) -> alt.X:
        # Every layer carries the same scale *and* axis: in a layered chart the first layer's axis
        # wins, so a bare "week:T" in any layer silently drops the format.
        return alt.X(f"{field}:T", title=None, scale=x_scale, axis=x_axis)

    x = xenc("week")
    y = alt.Y(
        "share:Q",
        title=None,
        scale=alt.Scale(domain=[0, y_max]),
        axis=alt.Axis(format=".0%", tickCount=5, labelFontSize=15 * font_scale),
    )
    clr = alt.Color(
        "group:N", scale=group_scale(), sort=GROUP_ORDER, legend=alt.Legend(title=None, labelFontSize=15 * font_scale)
    )

    layers = []
    flagged = story.frames["flagged"]
    if flagged.height:
        f = flagged.select(pl.col("week").cast(pl.Date)).with_columns(
            (pl.col("week") - timedelta(days=3)).alias("x0"), (pl.col("week") + timedelta(days=4)).alias("x1")
        )
        layers.append(
            alt.Chart(alt.Data(values=f.with_columns(pl.all().cast(pl.String)).to_dicts()))
            .mark_rect(color=color("text"), opacity=0.07)
            .encode(x=xenc("x0"), x2="x1:T")
        )

    data = alt.Data(values=g.with_columns(pl.col("week").cast(pl.String)).to_dicts())
    base = alt.Chart(data).encode(x=x, y=y, color=clr)
    layers.append(base.mark_line())

    end = g.filter(pl.col("week") == last).sort("share", descending=True)
    gap = 26 * font_scale * y_max / max(height - 90 * font_scale, 1)  # ~26px between end labels
    end = end.with_columns(
        pl.Series("label_y", _repel(end["share"].to_list(), gap, 0.012, y_max)), pl.col("week").cast(pl.String)
    )
    end_data = alt.Data(values=end.to_dicts())
    layers.append(
        alt.Chart(end_data)
        .mark_circle(size=90 * font_scale, opacity=1, stroke=color("canvas"), strokeWidth=2)
        .encode(x=x, y="share:Q", color=clr)
    )
    layers.append(
        alt.Chart(end_data)
        .mark_text(
            align="left",
            dx=14 * font_scale,
            fontSize=16 * font_scale,
            font=brand()["fonts"]["body"],
            color=color("text"),
        )
        .encode(x=x, y=alt.Y("label_y:Q", scale=alt.Scale(domain=[0, y_max])), text=alt.Text("label:N"))
        .transform_calculate(label="datum.group + '  ' + format(datum.share, '.0%')")
    )

    if interactive:
        hover = alt.selection_point(fields=["week"], nearest=True, on="pointerover", clear="pointerout", empty=False)
        layers.append(
            alt.Chart(data)
            .mark_rule(color=color("muted"), strokeWidth=1)
            .encode(
                x=x,
                opacity=alt.condition(hover, alt.value(1), alt.value(0)),
                tooltip=[alt.Tooltip("week_label:N", title="Week of")]
                + [alt.Tooltip(f"{grp}:Q", format=".1%") for grp in GROUP_ORDER],
            )
            .transform_pivot("group", value="share", groupby=["week"])
            .transform_calculate(week_label="utcFormat(toDate(datum.week), '%b %-d, %Y')")
            .add_params(hover)
        )
        layers.append(
            base.mark_point(filled=True, size=70)
            .encode(opacity=alt.condition(hover, alt.value(1), alt.value(0)))
            .transform_filter(hover)
        )

    chart = alt.layer(*layers).properties(width=width, height=height)
    return (
        chart.configure(**vl_config(font_scale))
        .configure_view(stroke=None)
        .properties(autosize=alt.AutoSizeParams(type="fit", contains="padding"))
    )


def race_keyframes(story: Story, top_n: int, every: int = 1) -> pl.DataFrame:
    """Vendor shares per keyframe week; ``every`` > 1 keeps every Nth week counted back from the last."""
    v = story.frames["vendors"]
    weeks = sorted(v["week"].unique().to_list())
    v = v.filter(pl.col("week").is_in(weeks[::-1][::every]))
    keep = (
        v.group_by("vendor_name")
        .agg(pl.col("share").max())
        .sort("share", descending=True)
        .head(top_n + 3)["vendor_name"]
        .to_list()
    )
    return v.filter(pl.col("vendor_name").is_in(keep)).select("week", "vendor_name", "group", "share")


def race_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    """Motion contract: one Vega-Lite spec per video frame (eased bar race), plus the frame rate."""
    top_n = cfg.get("race_top_n", 8)
    keys = race_keyframes(story, top_n, cfg.get("race_every_weeks", 1))
    groups = dict(zip(keys["vendor_name"], keys["group"], strict=False))
    timing = motion.Timing()
    frames = motion.bar_race_frames(keys, "vendor_name", "share", "week", top_n, timing)
    x_max = round(keys["share"].max() * 1.22, 2)
    specs = motion.build_specs(frames, lambda f: race_spec(f, groups, width, height, font_scale, top_n, x_max))
    return specs, timing.fps


def race_spec(
    frame: pl.DataFrame, groups: dict[str, str], width: int, height: int, font_scale: float, top_n: int, x_max: float
) -> dict:
    rows = frame.filter(pl.col("rank_pos") <= top_n + 0.75).with_columns(
        pl.col("vendor_name").replace_strict(groups, default="Everyone else").alias("group"),
        (pl.col("rank_pos") - 0.36).alias("y0"),
        (pl.col("rank_pos") + 0.36).alias("y1"),
        pl.lit(0.0).alias("x0"),
    )
    week = frame["label_time"][0]
    y_scale = alt.Scale(domain=[0.4, top_n + 0.6], reverse=True)
    x_scale = alt.Scale(domain=[0, x_max])
    data = alt.Data(values=rows.with_columns(pl.col("label_time").cast(pl.String)).to_dicts())
    bars = (
        alt.Chart(data)
        .mark_rect(cornerRadius=3, clip=True)
        .encode(
            x=alt.X(
                "x0:Q",
                scale=x_scale,
                title=None,
                axis=alt.Axis(format=".0%", tickCount=5, labelFontSize=15 * font_scale, grid=True),
            ),
            x2="share:Q",
            y=alt.Y("y0:Q", scale=y_scale, axis=None),
            y2="y1:Q",
            color=alt.Color("group:N", scale=group_scale(), legend=None),
        )
    )
    labels = (
        alt.Chart(data)
        .mark_text(
            align="left",
            dx=12 * font_scale,
            fontSize=19 * font_scale,
            font=brand()["fonts"]["body"],
            color=color("text"),
            clip=True,
        )
        .encode(x=alt.X("share:Q", scale=x_scale), y=alt.Y("rank_pos:Q", scale=y_scale), text="label:N")
        .transform_calculate(label="datum.vendor_name + '  ' + format(datum.share, '.0%')")
    )
    stamp = (
        alt.Chart(alt.Data(values=[{"t": f"WEEK OF {week:%b %-d}".upper()}]))
        .mark_text(
            align="right",
            baseline="bottom",
            fontSize=40 * font_scale,
            font=brand()["fonts"]["display"],
            color=color("muted"),
        )
        .encode(x=alt.datum(x_max, scale=x_scale), y=alt.datum(top_n + 0.55, scale=y_scale), text="t:N")
    )
    chart = alt.layer(bars, labels, stamp).properties(width=width, height=height)
    return (
        chart.configure(**vl_config(font_scale))
        .configure_view(stroke=None)
        .properties(autosize=alt.AutoSizeParams(type="fit", contains="padding"))
        .to_dict()
    )
