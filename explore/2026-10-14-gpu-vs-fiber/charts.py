"""Charts for the GPUs-vs-fiber exploration (render contract: src/cachereg/render.py).

* lives: book useful lives as range bars, one panel per group on a shared years axis; AI servers in
  the accent, everything else in greys, each bar labelled with its range.
* prices: each price series as % of its first quote by years since it, log axis; dot-com bandwidth
  in greys, GPU rents in the categorical slots (fixed order), direct labels at line ends.
* recovery: what four dot-com networks raised, owed and fetched over time, log dollars; Global Crossing
  in the accent with every point labelled.
* generations: two panels, each with one y-axis: capacity per fiber pair (log Gbps) over time, and
  NVIDIA's claimed gain per GPU generation as bars.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import altair as alt
import polars as pl
from analysis import fmt_usd

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.theme import vl_config

GREYS = ["#858B9B", "#C3C8D3"]
LABEL_PX, AXIS_PX = 16, 15


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _size(width, height) -> tuple[float, float]:
    return (width if isinstance(width, int | float) else 880, height if isinstance(height, int | float) else 560)


def _text(fs: float, size: float = LABEL_PX, **kw) -> dict:
    return {"font": brand()["fonts"]["body"], "fontSize": size * fs, **kw}


# --- lives -------------------------------------------------------------------------------------


LIVES_COLUMNS = (("AI servers", "Dot-com network electronics"), ("Dot-com fiber", "Data-centre", "Nuclear"))
SHORT = {"Williams Communications": "Williams"}


def lives(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.HConcatChart:
    fs = font_scale
    width, height = _size(width, height)
    fmt = {"return_dtype": pl.String}
    d = story.frames["lives"].with_columns(
        entity=pl.col("entity").replace(SHORT),
        label=pl.when(pl.col("low") == pl.col("high"))
        .then(pl.col("high").map_elements(lambda v: f"{v:g}", **fmt))
        .otherwise(
            pl.format(
                "{}–{}",
                pl.col("low").map_elements(lambda v: f"{v:g}", **fmt),
                pl.col("high").map_elements(lambda v: f"{v:g}", **fmt),
            )
        ),
        ink=pl.when(pl.col("group").str.starts_with("AI servers"))
        .then(pl.lit(color("accent")))
        .when(pl.col("era") == "dotcom")
        .then(pl.lit(GREYS[1]))
        .otherwise(pl.lit(GREYS[0])),
    )
    groups = list(dict.fromkeys(d["group"]))
    columns = (
        [[g for g in groups if g.startswith(prefix)] for prefix in LIVES_COLUMNS[0]],
        [[g for g in groups if g.startswith(prefix)] for prefix in LIVES_COLUMNS[1]],
    )
    columns = [[g for sub in col for g in sub] for col in columns]
    title_px, spacing, col_gap = 30 * fs, 14 * fs, 56 * fs
    label_w = 120 * fs
    col_w = (width - col_gap) / 2 - label_w
    xmax = math.ceil(d["high"].max() / 10) * 10
    x_scale = alt.Scale(domain=[0, xmax + 8])

    def column(gs: list[str]) -> alt.VConcatChart:
        n = d.filter(pl.col("group").is_in(gs)).height
        row_h = (height - 40 * fs - len(gs) * (title_px + spacing)) / max(n, 1)
        panels = []
        for i, g in enumerate(gs):
            part = d.filter(pl.col("group") == g)
            data = alt.Data(values=part.select("entity", "low", "high", "label", "ink", "scope").to_dicts())
            last = i == len(gs) - 1
            x_axis = alt.Axis(
                title="Years" if last else None,
                labels=last,
                grid=True,
                gridColor="#1C1F27",
                values=list(range(0, xmax + 1, 10)),
                labelFontSize=AXIS_PX * fs,
            )
            y = alt.Y(
                "entity:N",
                sort=None,
                title=None,
                axis=alt.Axis(
                    labelFontSize=(AXIS_PX - 1) * fs, labelFont=brand()["fonts"]["body"], labelLimit=label_w, grid=False
                ),
            )
            base = alt.Chart(data).encode(y=y)
            bar = base.mark_bar(height=min(max(row_h * 0.45, 5), 12 * fs), cornerRadius=3 * fs).encode(
                x=alt.X("low:Q", scale=x_scale, axis=x_axis), x2="high:Q", color=alt.Color("ink:N", scale=None)
            )
            dot = (
                base.mark_circle(size=90 * fs**2, opacity=1)
                .encode(x=alt.X("high:Q", scale=x_scale), color=alt.Color("ink:N", scale=None))
                .transform_filter("datum.low == datum.high")
            )
            lab = base.mark_text(
                align="left", dx=9 * fs, **_text(fs, LABEL_PX - 2, color=color("text_secondary"))
            ).encode(x=alt.X("high:Q", scale=x_scale), text="label:N")
            layer = alt.layer(bar, dot, lab)
            if interactive:
                layer = layer.encode(tooltip=["entity:N", "scope:N", "label:N"])
            panels.append(
                layer.properties(
                    width=col_w,
                    height=row_h * part.height,
                    title=alt.TitleParams(
                        g,
                        anchor="start",
                        fontSize=16 * fs,
                        font=brand()["fonts"]["body"],
                        fontWeight="bold",
                        color=color("text"),
                    ),
                )
            )
        return alt.vconcat(*panels, spacing=spacing)

    chart = alt.hconcat(column(columns[0]), column(columns[1]), spacing=col_gap).resolve_scale(x="shared")
    return chart.configure(**vl_config(fs))


# --- prices ------------------------------------------------------------------------------------


def prices(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    fs = font_scale
    width, height = _size(width, height)
    d = story.frames["prices"].with_columns(
        label=pl.format("{} ({})", pl.col("series"), pl.col("first_year").cast(pl.String))
    )
    names = list(dict.fromkeys(d["label"]))
    eras = dict(zip(d["label"], d["era"], strict=False))
    cats = brand()["colors"]["categorical"]
    ink, gi, ci = {}, 0, 0
    for n in names:
        if eras[n] == "dotcom":
            ink[n], gi = GREYS[gi % 2], gi + 1
        else:
            ink[n], ci = cats[ci], ci + 1
    clr = alt.Color("label:N", scale=alt.Scale(domain=names, range=[ink[n] for n in names]), legend=None)
    lo, hi = 0.2, 400.0
    label_px = 330 * fs
    xmax = math.ceil(d["years"].max())
    x_scale = alt.Scale(domain=[0, xmax * (1 + label_px / max(width - label_px, 1))])
    y_scale = alt.Scale(type="log", domain=[lo, hi], nice=False)
    ticks = [v for v in (0.3, 1, 3, 10, 30, 100, 300) if lo <= v <= hi]
    x = alt.X(
        "years:Q",
        scale=x_scale,
        title="Years since the series' first quote",
        axis=alt.Axis(values=list(range(0, xmax + 1, 2)), format="d", labelFontSize=AXIS_PX * fs, grid=False),
    )
    y = alt.Y(
        "pct_of_first:Q",
        scale=y_scale,
        title="% of first quote (log)",
        axis=alt.Axis(values=ticks, labelExpr="format(datum.value, '~g') + '%'", labelFontSize=AXIS_PX * fs),
    )
    data = alt.Data(
        values=d.select("label", "series", "years", "pct_of_first", "price", "unit", "entity", "day")
        .with_columns(pl.col("day").cast(pl.String))
        .to_dicts()
    )
    base = alt.Chart(data).encode(x=x, y=y, color=clr)
    ref = alt.Chart(alt.Data(values=[{"v": 100}])).mark_rule(color=color("muted"), strokeDash=[4, 4]).encode(y="v:Q")
    line = base.mark_line(strokeWidth=2.6 * fs, point=alt.OverlayMarkDef(size=70 * fs**2, filled=True)).encode(
        detail="label:N"
    )
    if interactive:
        line = line.encode(
            tooltip=[
                alt.Tooltip("series:N"),
                alt.Tooltip("day:N", title="Date"),
                alt.Tooltip("price:Q", format=",.2f"),
                alt.Tooltip("unit:N"),
                alt.Tooltip("pct_of_first:Q", title="% of first", format=".1f"),
                alt.Tooltip("entity:N", title="Source"),
            ]
        )
    ends = d.group_by("label", maintain_order=True).last().sort("pct_of_first", descending=True)
    span = math.log10(hi) - math.log10(lo)
    gap = 1.25 * LABEL_PX * fs * span / max(height, 1.0)
    ys, prev = [], None
    for v in ends["pct_of_first"]:
        yv = math.log10(v) if prev is None else min(math.log10(v), prev - gap)
        ys.append(yv)
        prev = yv
    ends = ends.with_columns(
        label_y=pl.Series([10**v for v in ys]),
        text=pl.col("label")
        + " · "
        + pl.col("pct_of_first").map_elements(lambda v: f"{v:.3g}%", return_dtype=pl.String),
    )
    end_data = alt.Data(values=ends.select("label", "years", "label_y", "text").to_dicts())
    tags = (
        alt.Chart(end_data)
        .mark_text(align="left", baseline="middle", dx=12 * fs, **_text(fs, LABEL_PX - 1))
        .encode(x=alt.X("years:Q", scale=x_scale), y=alt.Y("label_y:Q", scale=y_scale), text="text:N", color=clr)
    )
    chart = alt.layer(ref, line, tags).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


# --- recovery ----------------------------------------------------------------------------------


def recovery(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    fs = font_scale
    width, height = _size(width, height)
    d = (
        story.frames["recovery"]
        .with_columns(
            t=pl.col("day").map_elements(_ms, return_dtype=pl.Int64),
            amount=pl.col("usd").map_elements(fmt_usd, return_dtype=pl.String),
            hero=pl.col("company") == "Global Crossing",
        )
        .with_columns(
            text=pl.when(pl.col("hero")).then(pl.col("amount") + " " + pl.col("stage")).otherwise(pl.col("amount"))
        )
    )
    companies = list(dict.fromkeys(d.sort("hero", descending=True)["company"]))
    ink = {c: (color("accent") if c == "Global Crossing" else GREYS[i % 2]) for i, c in enumerate(companies)}
    clr = alt.Color("company:N", scale=alt.Scale(domain=companies, range=[ink[c] for c in companies]), legend=None)
    t0, t1 = _ms(datetime(1998, 1, 1)), _ms(datetime(2013, 6, 1))
    x_scale = alt.Scale(type="utc", domain=[t0, t1])
    y_scale = alt.Scale(type="log", domain=[1e7, 6e10], nice=False)
    x = alt.X(
        "t:T",
        scale=x_scale,
        title=None,
        axis=alt.Axis(format="%Y", labelFontSize=AXIS_PX * fs, grid=False, tickCount=8),
    )
    y = alt.Y(
        "usd:Q",
        scale=y_scale,
        title="US dollars (log)",
        axis=alt.Axis(
            values=[1e7, 1e8, 1e9, 1e10],
            labelExpr="datum.value >= 1e9 ? '$' + datum.value / 1e9 + 'bn' : '$' + datum.value / 1e6 + 'm'",
            labelFontSize=AXIS_PX * fs,
        ),
    )
    data = alt.Data(values=d.select("company", "stage", "t", "usd", "amount", "text", "hero", "scope").to_dicts())
    base = alt.Chart(data).encode(x=x, y=y, color=clr)
    line = base.mark_line(strokeWidth=2.2 * fs, opacity=0.9).encode(detail="company:N")
    pts = base.mark_circle(size=110 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
    if interactive:
        pts = pts.encode(tooltip=["company:N", "stage:N", "amount:N", "scope:N"])
    # label placement per point, so the 2002 cluster does not collide: (align, dx, dy) in px before scaling
    place = {
        ("FLAG Telecom", "debt at bankruptcy"): ("right", -11, 2),
        ("Global Crossing", "sold in bankruptcy"): ("right", -11, 14),
        ("FLAG Telecom", "sold in bankruptcy"): ("left", 11, -11),
        ("Velocita", "debt at bankruptcy"): ("left", 11, -11),
    }
    d = d.with_columns(
        pos=pl.struct("company", "stage").map_elements(
            lambda r: "|".join(map(str, place.get((r["company"], r["stage"]), ("left", 11, -11)))),
            return_dtype=pl.String,
        )
    )
    labels = []
    for pos in d["pos"].unique().sort():
        align, dx, dy = pos.split("|")
        part = d.filter(pl.col("pos") == pos)
        for hero in (True, False):
            sub = part.filter(pl.col("hero") == hero)
            if sub.is_empty():
                continue
            labels.append(
                alt.Chart(alt.Data(values=sub.select("t", "usd", "text").to_dicts()))
                .mark_text(
                    align=align,
                    dx=float(dx) * fs,
                    dy=float(dy) * fs,
                    **_text(fs, LABEL_PX - 1, color=color("text") if hero else color("text_secondary")),
                )
                .encode(x=x, y=y, text="text:N")
            )
    names = d.group_by("company", maintain_order=True).last()
    name_data = alt.Data(values=names.select("company", "t", "usd").to_dicts())
    name = (
        alt.Chart(name_data)
        .mark_text(align="left", dx=11 * fs, dy=12 * fs, **_text(fs, LABEL_PX, fontWeight="bold"))
        .encode(x=x, y=y, text="company:N", color=clr)
    )
    chart = alt.layer(line, pts, *labels, name).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


# --- generations -------------------------------------------------------------------------------

GEN_LABELS = {
    "gpu_a100": "A100 vs V100",
    "gpu_h100": "H100 vs A100",
    "gpu_gb200": "GB200 vs H100",
    "gpu_rubin": "Rubin vs Blackwell",
}


def generations(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.HConcatChart:
    fs = font_scale
    width, height = _size(width, height)
    spacing = 60 * fs
    w = (width - spacing) / 2
    cap = story.frames["capacity"].with_columns(
        t=pl.col("day").map_elements(_ms, return_dtype=pl.Int64),
        label=pl.col("gbps").map_elements(
            lambda g: f"{g / 1000:g} Tbps" if g >= 1000 else f"{g:g} Gbps", return_dtype=pl.String
        ),
        who=pl.col("entity").str.replace(r" \(.*\)$", ""),
    )
    x_cap = alt.X(
        "t:T",
        title=None,
        scale=alt.Scale(type="utc", domain=[_ms(datetime(2000, 1, 1)), _ms(datetime(2030, 12, 31))]),
        axis=alt.Axis(
            values=[_ms(datetime(y, 1, 1)) for y in (2000, 2010, 2020, 2030)],
            format="%Y",
            labelFontSize=AXIS_PX * fs,
            grid=False,
        ),
    )
    y_cap = alt.Y(
        "gbps:Q",
        title="Capacity of one fiber pair (log)",
        scale=alt.Scale(type="log", domain=[300, 100000], nice=False),
        axis=alt.Axis(
            values=[1000, 10000, 100000],
            labelExpr="datum.value / 1000 + ' Tbps'",
            labelFontSize=AXIS_PX * fs,
        ),
    )
    cbase = alt.Chart(alt.Data(values=cap.select("t", "gbps", "label", "who", "scope").to_dicts())).encode(
        x=x_cap, y=y_cap
    )
    cline = cbase.mark_line(color=color("accent"), strokeWidth=2.6 * fs)
    cpts = cbase.mark_circle(color=color("accent"), size=110 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
    if interactive:
        cpts = cpts.encode(tooltip=["who:N", "label:N", "scope:N"])
    clab = cbase.mark_text(align="left", dx=8 * fs, dy=20 * fs, **_text(fs, LABEL_PX - 1, color=color("text"))).encode(
        text="label:N"
    )
    cwho = cbase.mark_text(
        align="left", dx=8 * fs, dy=38 * fs, **_text(fs, LABEL_PX - 3, color=color("text_secondary"))
    ).encode(text="who:N")
    left = alt.layer(cline, cpts, clab, cwho).properties(
        width=w,
        height=height,
        title=alt.TitleParams("Same glass, new optics", anchor="start", fontSize=17 * fs, color=color("text")),
    )

    gen = story.frames["generations"].with_columns(
        gen=pl.col("asset").replace_strict(GEN_LABELS, return_dtype=pl.String),
        label=pl.format("up to {}×", pl.col("value").cast(pl.Int64)),
    )
    order = [GEN_LABELS[a] for a in gen["asset"]]
    gbase = alt.Chart(alt.Data(values=gen.select("gen", "value", "label", "scope").to_dicts())).encode(
        x=alt.X(
            "gen:N",
            sort=order,
            title=None,
            axis=alt.Axis(
                labelAngle=0,
                labelFontSize=(AXIS_PX - 1) * fs,
                labelExpr="split(datum.label, ' vs ')",
                labelLineHeight=(AXIS_PX + 3) * fs,
            ),
        ),
        y=alt.Y(
            "value:Q",
            title="Claimed gain over the previous generation (×)",
            scale=alt.Scale(domain=[0, 40]),
            axis=alt.Axis(values=[0, 10, 20, 30, 40], labelFontSize=AXIS_PX * fs),
        ),
    )
    bars = gbase.mark_bar(color=GREYS[0], cornerRadiusTopLeft=4 * fs, cornerRadiusTopRight=4 * fs, size=w / 7)
    if interactive:
        bars = bars.encode(tooltip=["gen:N", "label:N", "scope:N"])
    blab = gbase.mark_text(baseline="bottom", dy=-6 * fs, **_text(fs, LABEL_PX - 1, color=color("text"))).encode(
        text="label:N"
    )
    right = alt.layer(bars, blab).properties(
        width=w,
        height=height,
        title=alt.TitleParams("New GPU, old GPU worth less", anchor="start", fontSize=17 * fs, color=color("text")),
    )
    return alt.hconcat(left, right, spacing=spacing).configure(**vl_config(fs))
