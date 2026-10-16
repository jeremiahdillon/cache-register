"""Charts for the GPUs-vs-fiber exploration (render contract: src/cachereg/render.py).

* years: book lives as a unit chart, one square per year (the median of the companies' longest stated
  life per group); AI servers in the accent, everything else in greys.
* book_life: one bar per GPU generation from announcement to the end of its book life, later
  announcements as vertical rules, today as a dashed rule.
* ladder: January and October 2026 rents per GPU generation at one venue, as a dumbbell.
* glut: the first years of each price path as % of its first quote (log axis); the H100 in the accent.
* recovery: what four dot-com networks raised, owed and fetched over time, log dollars; Global Crossing
  in the accent with every point labelled.
* buyers: cash and short-term investments vs debt per company, paired bars.
"""

from __future__ import annotations

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


def years(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    """One square per year of book life, a small gap every five years, grouped by era under a header;
    short-lived gear in the accent, long-lived assets in grey. Landscape: one line per asset, labels at the
    left. Portrait: lines of ten years (a decade each), label above."""
    fs = font_scale
    width, height = _size(width, height)
    d = story.frames["years"]
    portrait = height / width > 0.5  # the plot area of a portrait image is still wider than tall
    per_line = 10 if portrait else 100
    gap = 0.45  # extra columns between groups of five years
    era_names = {"dotcom": "Dot-com build-out, 1998–2002", "ai": "AI build-out, 2020s"}
    units, heads, eras, ends, top = [], [], [], [], 0.0
    era = None
    for r in d.to_dicts():
        if r["era"] != era:
            era = r["era"]
            top += 0.4 if eras else 0.0
            eras.append({"x": -0.9 if not portrait else -0.4, "y": top, "text": era_names[era]})
            top += 1.15
        n = int(round(r["years"]))
        ink = color("accent") if r["lifespan"] == "short" else GREYS[0]
        lines = -(-n // per_line)
        if portrait:
            heads.append({"x": -0.4, "y": top, "text": r["label"]})
            top += 1.0
        for i in range(n):
            col = i % per_line
            units.append(
                {"label": r["label"], "x": col + (col // 5) * gap, "y": top + i // per_line, "ink": ink, "year": i + 1}
            )
        last = n - 1
        ends.append(
            {
                "label": r["label"],
                "x": (last % per_line) + ((last % per_line) // 5) * gap,
                "y": top + last // per_line,
                "text": f"{r['years']:g} years",
                "range": f"{r['low']:g}–{r['high']:g} across {r['companies']} companies ({r['who']})",
            }
        )
        if not portrait:
            heads.append({"x": -0.9, "y": top, "text": r["label"]})
        top += lines + (0.9 if portrait else 1.0)
    label_px = 0 if portrait else 290 * fs
    max_x = max(u["x"] for u in units)
    tail_cols = 7
    plot_w = width - label_px
    cell = plot_w / (max_x + tail_cols + 1)
    cell = min(cell, (height / top) * (1.0 if portrait else 0.75))
    size = (cell * 0.78) ** 2
    left = label_px / cell  # label room, in squares, left of the first square
    x_scale = alt.Scale(domain=[-0.6 - left, -0.6 + plot_w / cell])
    y_scale = alt.Scale(domain=[-0.6, max(top - 0.4, -0.6 + height / cell * 0.5)], reverse=True)
    x = alt.X("x:Q", scale=x_scale, axis=None)
    y = alt.Y("y:Q", scale=y_scale, axis=None)
    sq = (
        alt.Chart(alt.Data(values=units))
        .mark_square(size=size, opacity=1)
        .encode(x=x, y=y, color=alt.Color("ink:N", scale=None))
    )
    lab = (
        alt.Chart(alt.Data(values=ends))
        .mark_text(align="left", dx=cell * 0.5 + 8 * fs, **_text(fs, LABEL_PX + 1, color=color("text")))
        .encode(x=x, y=y, text="text:N")
    )
    if interactive:
        lab = lab.encode(tooltip=["label:N", "text:N", alt.Tooltip("range:N", title="Stated range")])
    head = (
        alt.Chart(alt.Data(values=heads))
        .mark_text(
            align="left" if portrait else "right",
            baseline="middle",
            **_text(fs, LABEL_PX + 1, color=color("text_secondary")),
        )
        .encode(x=x, y=y, text="text:N")
    )
    era_head = (
        alt.Chart(alt.Data(values=eras))
        .mark_text(
            align="left" if portrait else "right",
            baseline="middle",
            **_text(fs, LABEL_PX + 3, color=color("text"), fontWeight="bold"),
        )
        .encode(x=x, y=y, text="text:N")
    )
    chart = alt.layer(sq, lab, head, era_head).properties(width=width, height=height)
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


# --- book life ----------------------------------------------------------------------------------


def book_life(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    fs = font_scale
    width, height = _size(width, height)
    d = story.frames["book_life"].with_columns(
        t0=pl.col("announced").map_elements(_ms, return_dtype=pl.Int64),
        t1=pl.col("book_end").map_elements(_ms, return_dtype=pl.Int64),
        label=pl.when(pl.col("n_later") == 0)
        .then(pl.format("on the books to {}", pl.col("book_end").dt.year()))
        .otherwise(
            pl.format(
                "to {} · {} newer generation{} so far",
                pl.col("book_end").dt.year(),
                pl.col("n_later"),
                pl.when(pl.col("n_later") == 1).then(pl.lit("")).otherwise(pl.lit("s")),
            )
        ),
    )
    order = d["gpu"].to_list()
    x_scale = alt.Scale(type="utc", domain=[_ms(datetime(2019, 7, 1)), _ms(datetime(2036, 6, 30))])
    x = alt.X(
        "t0:T",
        scale=x_scale,
        title=None,
        axis=alt.Axis(
            values=[_ms(datetime(y, 1, 1)) for y in range(2020, 2034, 2)],
            format="%Y",
            labelFontSize=AXIS_PX * fs,
            grid=False,
        ),
    )
    y = alt.Y(
        "gpu:N",
        sort=order,
        title=None,
        axis=alt.Axis(labelFontSize=(AXIS_PX + 2) * fs, labelFont=brand()["fonts"]["body"], grid=False),
    )
    data = alt.Data(values=d.select("gpu", "t0", "t1", "label", "later").to_dicts())
    base = alt.Chart(data).encode(y=y)
    bar = base.mark_bar(height=min(height / len(order) * 0.38, 26 * fs), cornerRadius=4 * fs).encode(
        x=x, x2="t1:T", color=alt.value(GREYS[0])
    )
    first = (
        base.transform_filter(alt.datum.gpu == order[0])
        .mark_bar(height=min(height / len(order) * 0.38, 26 * fs), cornerRadius=4 * fs, color=color("accent"))
        .encode(x=x, x2="t1:T")
    )
    if interactive:
        bar = bar.encode(
            tooltip=[
                "gpu:N",
                alt.Tooltip("t0:T", title="Announced"),
                alt.Tooltip("t1:T", title="Book life ends"),
                "later:N",
            ]
        )
    lab = base.mark_text(align="left", dx=10 * fs, **_text(fs, LABEL_PX - 1, color=color("text_secondary"))).encode(
        x=alt.X("t1:T", scale=x_scale), text="label:N"
    )
    rules_data = alt.Data(values=d.select("gpu", "t0").to_dicts()[1:])
    rules = (
        alt.Chart(rules_data)
        .mark_rule(color=color("muted"), strokeDash=[3, 4], strokeWidth=1.2 * fs)
        .encode(x=alt.X("t0:T", scale=x_scale))
    )
    today = alt.Chart(alt.Data(values=[{"t": _ms(story.as_of), "label": "today"}]))
    now_rule = today.mark_rule(color=color("text_secondary"), strokeWidth=1.2 * fs, opacity=0.45).encode(
        x=alt.X("t:T", scale=x_scale)
    )
    now_lab = today.mark_text(
        align="left", baseline="top", dx=6 * fs, y=0, **_text(fs, LABEL_PX - 2, color=color("text_secondary"))
    ).encode(x=alt.X("t:T", scale=x_scale), text="label:N")
    chart = alt.layer(rules, now_rule, now_lab, bar, first, lab).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


# --- ladder ------------------------------------------------------------------------------------


def ladder(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    fs = font_scale
    width, height = _size(width, height)
    d = story.frames["ladder"].with_columns(
        change_label=pl.col("change").map_elements(lambda v: f"{v:+.0%}", return_dtype=pl.String),
        from_label=pl.col("from_price").map_elements(lambda v: f"${v:.2f}", return_dtype=pl.String),
        to_label=pl.col("to_price").map_elements(lambda v: f"${v:.2f}", return_dtype=pl.String),
    )
    order = d["gpu"].to_list()
    xmax = d["to_price"].max() * 1.3
    x_scale = alt.Scale(domain=[0, xmax])
    x = alt.X(
        "from_price:Q",
        scale=x_scale,
        title="Dollars per GPU-hour, Lambda on-demand",
        axis=alt.Axis(labelExpr="'$' + format(datum.value, '.0f')", labelFontSize=AXIS_PX * fs, tickCount=4),
    )
    y = alt.Y(
        "gpu:N",
        sort=order,
        title=None,
        axis=alt.Axis(labelFontSize=(AXIS_PX + 2) * fs, labelFont=brand()["fonts"]["body"], grid=False),
    )
    data = alt.Data(
        values=d.select("gpu", "from_price", "to_price", "from_label", "to_label", "change_label").to_dicts()
    )
    base = alt.Chart(data).encode(y=y)
    link = base.mark_rule(color=color("muted"), strokeWidth=3 * fs).encode(x=x, x2="to_price:Q")
    jan = base.mark_circle(size=170 * fs**2, opacity=1, color=GREYS[0]).encode(x=x)
    octo = base.mark_circle(size=170 * fs**2, opacity=1, color=color("accent")).encode(
        x=alt.X("to_price:Q", scale=x_scale)
    )
    if interactive:
        octo = octo.encode(
            tooltip=[
                "gpu:N",
                alt.Tooltip("from_label:N", title="January 2026"),
                alt.Tooltip("to_label:N", title="October 2026"),
                alt.Tooltip("change_label:N", title="Change"),
            ]
        )
    jan_lab = base.mark_text(
        align="right", dx=-14 * fs, **_text(fs, LABEL_PX - 1, color=color("text_secondary"))
    ).encode(x=x, text="from_label:N")
    oct_lab = base.mark_text(align="left", dx=14 * fs, **_text(fs, LABEL_PX, color=color("text"))).encode(
        x=alt.X("to_price:Q", scale=x_scale), text=alt.Text("to_label:N")
    )
    chg = base.mark_text(
        align="left", dx=72 * fs, **_text(fs, LABEL_PX, color=color("accent"), fontWeight="bold")
    ).encode(x=alt.X("to_price:Q", scale=x_scale), text="change_label:N")
    key = alt.Data(values=[{"x": d["from_price"][-1], "t": "Jan 2026"}, {"x": d["to_price"][-1], "t": "Oct 2026"}])
    key_lab = (
        alt.Chart(key)
        .mark_text(baseline="bottom", dy=-22 * fs, **_text(fs, LABEL_PX - 2, color=color("text_secondary")))
        .encode(x=alt.X("x:Q", scale=x_scale), y=alt.datum(order[-1]), text="t:N")
    )
    chart = alt.layer(link, jan, octo, jan_lab, oct_lab, chg, key_lab).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


# --- glut --------------------------------------------------------------------------------------


def glut(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    fs = font_scale
    width, height = _size(width, height)
    d = story.frames["glut"].with_columns(
        label=pl.format("{} ({})", pl.col("series"), pl.col("first_year").cast(pl.String))
    )
    names = list(dict.fromkeys(d["label"]))
    ink = {n: (color("accent") if n.startswith("H100") else GREYS[i % 2]) for i, n in enumerate(names)}
    clr = alt.Color("label:N", scale=alt.Scale(domain=names, range=[ink[n] for n in names]), legend=None)
    lo, hi = 8.0, 160.0
    label_px = 300 * fs
    xmax = 5
    x_scale = alt.Scale(domain=[0, xmax * (1 + label_px / max(width - label_px, 1))])
    y_scale = alt.Scale(type="log", domain=[lo, hi], nice=False)
    x = alt.X(
        "years:Q",
        scale=x_scale,
        title="Years since the series' first quote",
        axis=alt.Axis(values=list(range(0, xmax + 1)), format="d", labelFontSize=AXIS_PX * fs, grid=False),
    )
    y = alt.Y(
        "pct_of_first:Q",
        scale=y_scale,
        title="% of first quote (log)",
        axis=alt.Axis(values=[10, 20, 50, 100], labelExpr="datum.value + '%'", labelFontSize=AXIS_PX * fs),
    )
    d = d.filter(pl.col("years") <= xmax)
    data = alt.Data(values=d.select("label", "series", "years", "pct_of_first", "price", "unit", "entity").to_dicts())
    base = alt.Chart(data).encode(x=x, y=y, color=clr)
    line = base.mark_line(strokeWidth=2.8 * fs, point=alt.OverlayMarkDef(size=80 * fs**2, filled=True)).encode(
        detail="label:N"
    )
    if interactive:
        line = line.encode(
            tooltip=[
                "series:N",
                alt.Tooltip("pct_of_first:Q", title="% of first", format=".0f"),
                alt.Tooltip("price:Q", format=",.2f"),
                "unit:N",
                alt.Tooltip("entity:N", title="Source"),
            ]
        )
    ends = (
        d.group_by("label", maintain_order=True)
        .last()
        .with_columns(
            text=pl.col("label")
            + " · "
            + pl.col("pct_of_first").map_elements(lambda v: f"{v:.0f}%", return_dtype=pl.String)
        )
    )
    tags = (
        alt.Chart(alt.Data(values=ends.select("label", "years", "pct_of_first", "text").to_dicts()))
        .mark_text(align="left", baseline="middle", dx=12 * fs, **_text(fs, LABEL_PX - 1))
        .encode(x=alt.X("years:Q", scale=x_scale), y=alt.Y("pct_of_first:Q", scale=y_scale), text="text:N", color=clr)
    )
    ref = (
        alt.Chart(alt.Data(values=[{"v": 100}]))
        .mark_rule(color=color("muted"), strokeDash=[4, 4])
        .encode(y=alt.Y("v:Q", scale=y_scale))
    )
    lit = story.frames["glut"].filter(pl.col("series").str.starts_with("OC-3") & (pl.col("years").round(0) == 1))
    note = alt.Data(
        values=[
            {
                "years": lit["years"][0],
                "pct": lit["pct_of_first"][0],
                "t": f"2001: {story.extra['lit_pct']:g}% of lit capacity in use",
            }
        ]
    )
    note_lab = (
        alt.Chart(note)
        .mark_text(
            align="left",
            baseline="top",
            dx=16 * fs,
            dy=2 * fs,
            **_text(fs, LABEL_PX - 2, color=color("text_secondary")),
        )
        .encode(x=alt.X("years:Q", scale=x_scale), y=alt.Y("pct:Q", scale=y_scale), text="t:N")
    )
    chart = alt.layer(ref, line, tags, note_lab).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


# --- buyers ------------------------------------------------------------------------------------


def buyers(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    fs = font_scale
    width, height = _size(width, height)
    cats = brand()["colors"]["categorical"]
    w = story.frames["buyers"].sort("net_usd", descending=True)
    order = w["company"].to_list()
    long = pl.concat(
        [
            w.select(
                "company",
                pl.lit("Cash and short-term investments").alias("what"),
                (pl.col("liquidity_usd") / 1e9).alias("bn"),
                "period_end",
            ),
            w.select("company", pl.lit("Debt").alias("what"), (pl.col("debt_usd") / 1e9).alias("bn"), "period_end"),
        ]
    ).with_columns(
        label=pl.col("bn").map_elements(lambda v: f"${v:.0f}bn", return_dtype=pl.String),
        period=pl.col("period_end").cast(pl.String),
    )
    whats = ["Cash and short-term investments", "Debt"]
    clr = alt.Color(
        "what:N",
        scale=alt.Scale(domain=whats, range=[cats[0], cats[1]]),
        legend=alt.Legend(
            title=None,
            labelLimit=600,
            orient="top",
            direction="horizontal",
            labelFontSize=(AXIS_PX + 1) * fs,
            symbolSize=160 * fs**2,
        ),
    )
    xmax = long["bn"].max() * 1.18
    x = alt.X(
        "bn:Q",
        title="US$ billions, latest balance sheet",
        scale=alt.Scale(domain=[0, xmax]),
        axis=alt.Axis(labelFontSize=AXIS_PX * fs, tickCount=5),
    )
    y = alt.Y(
        "company:N",
        sort=order,
        title=None,
        axis=alt.Axis(labelFontSize=(AXIS_PX + 1) * fs, labelFont=brand()["fonts"]["body"], grid=False),
    )
    yoff = alt.YOffset("what:N", sort=whats)
    data = alt.Data(values=long.select("company", "what", "bn", "label", "period").to_dicts())
    base = alt.Chart(data).encode(y=y, yOffset=yoff)
    bars = base.mark_bar(cornerRadiusTopRight=3 * fs, cornerRadiusBottomRight=3 * fs).encode(x=x, color=clr)
    if interactive:
        bars = bars.encode(tooltip=["company:N", "what:N", "label:N", alt.Tooltip("period:N", title="Balance sheet")])
    lab = base.mark_text(align="left", dx=6 * fs, **_text(fs, LABEL_PX - 2, color=color("text_secondary"))).encode(
        x=x, text="label:N"
    )
    chart = alt.layer(bars, lab).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


# --- glass -------------------------------------------------------------------------------------

BUCKETS = {
    "long": "Land and buildings (long-lived)",
    "mixed": "Mixed or not yet in service",
    "short": "Servers and network gear (short-lived)",
}


def glass(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    """100%-stacked bars of gross property and equipment per company; the long-lived share in the accent."""
    fs = font_scale
    width, height = _size(width, height)
    g = story.frames["glass"]
    long_share = {c: s for c, b, s in g.select("company", "bucket", "share").iter_rows() if b == "long"}
    order = sorted(long_share, key=long_share.get, reverse=True)
    stack = ["long", "mixed", "short"]
    d = (
        g.with_columns(
            what=pl.col("bucket").replace_strict(BUCKETS, return_dtype=pl.String),
            k=pl.col("bucket").replace_strict({b: i for i, b in enumerate(stack)}, return_dtype=pl.Int64),
            pct=pl.col("share").map_elements(lambda v: f"{v:.0%}", return_dtype=pl.String),
            total_label=(pl.col("total") / 1e9).map_elements(lambda v: f"${v:,.0f}bn", return_dtype=pl.String),
            asof=pl.col("period_end").cast(pl.String),
        )
        .sort("company", "k")
        .with_columns(x1=pl.col("share").cum_sum().over("company"))
        .with_columns(x0=pl.col("x1") - pl.col("share"), xm=pl.col("x1") - pl.col("share") / 2)
    )
    ink = {"long": color("accent"), "mixed": "#3A3F4B", "short": GREYS[0]}
    whats = [BUCKETS[b] for b in stack]
    clr = alt.Color(
        "what:N",
        scale=alt.Scale(domain=whats, range=[ink[b] for b in stack]),
        legend=alt.Legend(
            title=None,
            orient="top",
            direction="horizontal",
            labelLimit=600,
            labelFontSize=(AXIS_PX + 1) * fs,
            symbolType="square",
            symbolSize=180 * fs**2,
        ),
    )
    label_px = 150 * fs
    total_px = 110 * fs
    x_scale = alt.Scale(domain=[0, 1])
    y = alt.Y(
        "company:N",
        sort=order,
        title=None,
        axis=alt.Axis(labelFontSize=(AXIS_PX + 2) * fs, labelFont=brand()["fonts"]["body"], grid=False),
    )
    rows = d.select("company", "what", "bucket", "x0", "x1", "xm", "pct", "share", "total_label", "asof", "lines")
    base = alt.Chart(alt.Data(values=rows.to_dicts())).encode(y=y)
    bar_h = min(height / len(order) * 0.62, 44 * fs)
    bars = base.mark_bar(height=bar_h, stroke=color("canvas"), strokeWidth=2).encode(
        x=alt.X("x0:Q", scale=x_scale, axis=None), x2="x1:Q", color=clr
    )
    if interactive:
        bars = bars.encode(
            tooltip=["company:N", "what:N", "pct:N", alt.Tooltip("asof:N", title="Balance sheet"), "lines:N"]
        )
    big = "datum.share >= 0.07"
    on_lime = base.transform_filter(f"{big} && datum.bucket == 'long'").mark_text(
        **_text(fs, LABEL_PX, color=color("canvas"), fontWeight="bold")
    )
    on_grey = base.transform_filter(f"{big} && datum.bucket != 'long'").mark_text(
        **_text(fs, LABEL_PX, color=color("text"))
    )
    pcts = [m.encode(x=alt.X("xm:Q", scale=x_scale), text="pct:N") for m in (on_lime, on_grey)]
    totals = (
        alt.Chart(alt.Data(values=d.unique("company").select("company", "total_label").to_dicts()))
        .mark_text(align="left", dx=12 * fs, **_text(fs, LABEL_PX - 1, color=color("text_secondary")))
        .encode(y=y, x=alt.datum(1.0), text="total_label:N")
    )
    chart = alt.layer(bars, *pcts, totals).properties(width=width - label_px - total_px, height=height)
    return chart.configure(**vl_config(fs))
