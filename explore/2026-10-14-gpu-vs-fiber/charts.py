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
from cachereg.viz.fit import fit, fit_size
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


# --- motion helpers ----------------------------------------------------------------------------
# The three story charts (years, split, exposure) draw from an animation `state`; the static chart is the final
# state, built through `fit` so its outer size is exactly the plot box. Their `_specs` fit the final frame once
# and draw every frame at that size with every mark present (hidden ones at opacity 0), so the canvas never moves.

FPS = 30
MIXED_INK = "#3A3F4B"


def _smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _n(seconds: float) -> int:
    return max(int(round(seconds * FPS)), 1)


def _lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def _texts(rows: list[dict], fs: float, x: alt.X, y: alt.Y, size: float, **kw) -> alt.Chart:
    """Text marks whose colour and opacity come from each row (`ink`, `op`)."""
    return (
        alt.Chart(alt.Data(values=rows or [{"x": 0, "y": 0, "text": "", "ink": "#000000", "op": 0}]))
        .mark_text(**_text(fs, size, **kw))
        .encode(
            x=x,
            y=y,
            text="text:N",
            color=alt.Color("ink:N", scale=None),
            opacity=alt.Opacity("op:Q", scale=None),
        )
    )


def _rects(rows: list[dict], x: alt.X, y: alt.Y) -> alt.Chart:
    return (
        alt.Chart(alt.Data(values=rows or [{"x": 0, "x2": 0, "y": 0, "y2": 0, "ink": "#000000", "op": 0}]))
        .mark_rect()
        .encode(
            x=x,
            x2="x2:Q",
            y=y,
            y2="y2:Q",
            color=alt.Color("ink:N", scale=None),
            opacity=alt.Opacity("op:Q", scale=None),
        )
    )


# --- years -------------------------------------------------------------------------------------

ERA_NAMES = {"dotcom": "Dot-com build-out, 1998–2002", "ai": "AI build-out, 2020s"}


def _years(story: Story, width: float, height: float, fs: float, state: dict | None = None, interactive=False):
    """One square per year of book life (a part square for a half year), a gap every five years, grouped by
    era; each era's headline asset (glass then, GPU servers now) in the accent, the rest in grey. Landscape: one
    line per asset, labels at the left. Portrait: lines of ten years, label above. `state`: t (years drawn so
    far, per era), era (the era the counter follows), counter (its opacity)."""
    d = story.frames["years"]
    inf = float("inf")
    portrait = height / width > 0.5
    per_line = 10 if portrait else 100
    gap = 0.45
    label_px = 0 if portrait else 300 * fs
    max_years = d["years"].max()
    n_cols = min(per_line, int(-(-max_years // 1)))
    max_x = (n_cols - 1) + ((n_cols - 1) // 5) * gap
    tail_cols = 9
    cell = (width - label_px) / (max_x + tail_cols + 1)
    # rows: era header, then per asset (a label line in portrait) and its lines of squares
    plan, top = [], 0.0
    era = None
    for r in d.to_dicts():
        if r["era"] != era:
            era = r["era"]
            plan.append(("era", top, era))
            top += 1.2
        n = int(-(-r["years"] // 1))
        lines = -(-n // per_line)
        if portrait:
            plan.append(("head", top, r))
            top += 1.0
        plan.append(("row", top, r))
        top += lines + 0.8
    cell = min(cell, height / top)
    spare = max(height / cell - top, 0.0) / max(len(plan), 1)
    x_scale = alt.Scale(domain=[-0.6 - label_px / cell, -0.6 + (width - label_px) / cell], nice=False, zero=False)
    y_scale = alt.Scale(domain=[-0.6, -0.6 + height / cell], reverse=True, nice=False, zero=False)
    x = alt.X("x:Q", scale=x_scale, axis=None)
    y = alt.Y("y:Q", scale=y_scale, axis=None)
    units, heads, eras, ends, era_y = [], [], [], [], {}
    shift = 0.0
    for kind, y0, item in plan:
        y0 += shift
        shift += spare
        if kind == "era":
            era_y[item] = y0
            eras.append(
                {"x": -0.9 if not portrait else -0.4, "y": y0, "text": ERA_NAMES[item], "ink": color("text"), "op": 1}
            )
            continue
        r = item
        if kind == "head":
            heads.append({"x": -0.4, "y": y0, "text": r["label"], "ink": color("text_secondary"), "op": 1})
            continue
        if not portrait:
            heads.append({"x": -0.9, "y": y0, "text": r["label"], "ink": color("text_secondary"), "op": 1})
        t = inf if state is None else state["t"][r["era"]]
        ink = color("accent") if r["highlight"] else GREYS[0]
        shown = min(t, r["years"])
        for i in range(int(-(-r["years"] // 1))):
            full = min(r["years"] - i, 1.0)  # a half year is a half-width square
            drawn = min(max(shown - i, 0.0), full)
            col = i % per_line
            x0 = col + (col // 5) * gap - 0.39
            yy = y0 + i // per_line
            units.append(
                {"x": x0, "x2": x0 + 0.78 * drawn, "y": yy - 0.39, "y2": yy + 0.39, "ink": ink, "op": 1 if drawn else 0}
            )
        last = int(-(-r["years"] // 1)) - 1
        col = last % per_line
        done = _smooth((t - r["years"]) / 0.8) if t != inf else 1.0
        text = f"{r['years']:g} years" + (f" · {r['tag']}" if r["tag"] else "")
        ends.append(
            {
                "x": col + (col // 5) * gap + 0.85,
                "y": y0 + last // per_line,
                "text": text,
                "ink": color("text"),
                "op": done,
                "range": f"{r['low']:g}–{r['high']:g} years across {r['companies']} companies ({r['who']})",
            }
        )
    layers = [_rects(units, x, y)]
    end_marks = _texts(ends, fs, x, y, LABEL_PX + 1, align="left", baseline="middle")
    if interactive:
        end_marks = end_marks.encode(
            tooltip=[alt.Tooltip("text:N", title="Book life"), alt.Tooltip("range:N", title="Stated")]
        )
    layers.append(end_marks)
    align = "left" if portrait else "right"
    layers.append(_texts(heads, fs, x, y, LABEL_PX + 1, align=align, baseline="middle"))
    layers.append(_texts(eras, fs, x, y, LABEL_PX + 3, align=align, baseline="middle", fontWeight="bold"))
    counter = []
    if state is not None:
        te = state["t"][state["era"]]
        counter = [
            {
                "x": -0.6 + (width - label_px) / cell - 0.2,
                "y": era_y[state["era"]],
                "text": f"year {min(int(-(-te // 1)), int(max_years // 1) + 1)}" if te > 0 else "year 0",
                "ink": color("text_secondary"),
                "op": state.get("counter", 0.0),
            }
        ]
    layers.append(
        _texts(
            counter or [{"x": 0, "y": 0, "text": "", "ink": "#000", "op": 0}],
            fs,
            x,
            y,
            LABEL_PX + 2,
            align="right",
            baseline="middle",
        )
    )
    return alt.layer(*layers).properties(width=width, height=height).configure(**vl_config(fs))


def years(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False):
    return fit(lambda w, h: _years(story, w, h, font_scale, None, interactive), width, height)


def years_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict):
    """Video: the dot-com era builds first (a year counter beside its header; the electronics stop at 7 years,
    the glass runs on to 22.5), a pause, then the AI era at the same speed (GPU servers stop at 5.5 while the
    buildings and the power plants and grid run on); each row's label fades in as it completes."""
    d = story.frames["years"]
    top = {e: d.filter(pl.col("era") == e)["years"].max() for e in ("dotcom", "ai")}
    speed = top["dotcom"] / 3.0  # years per second, the same in both eras
    final = {"t": {"dotcom": 1e9, "ai": 1e9}, "era": "ai", "counter": 0.0}
    w, h = fit_size(lambda a, b: _years(story, a, b, font_scale, final), width, height)
    states = [{"t": {"dotcom": 0.0, "ai": 0.0}, "era": "dotcom", "counter": 0.0} for _ in range(_n(0.5))]
    for era, before in (("dotcom", {"ai": 0.0}), ("ai", {"dotcom": 1e9})):
        n_in = _n(0.3)
        states += [{"t": {era: 0.0, **before}, "era": era, "counter": _smooth((i + 1) / n_in)} for i in range(n_in)]
        n = _n(top[era] / speed)
        states += [{"t": {era: top[era] * (i + 1) / n, **before}, "era": era, "counter": 1.0} for i in range(n)]
        n_out = _n(0.6)
        states += [
            {
                "t": {era: top[era] + 0.8 * (i + 1) / n_out, **before},
                "era": era,
                "counter": 1 - _smooth((i + 1) / n_out),
            }
            for i in range(n_out)
        ]
        if era == "dotcom":  # the pause between the eras
            states += [{"t": {"dotcom": 1e9, "ai": 0.0}, "era": "dotcom", "counter": 0.0} for _ in range(_n(1.0))]
    states += [final for _ in range(_n(3.0))]
    return [_years(story, w, h, font_scale, st).to_dict() for st in states], FPS


# --- split -------------------------------------------------------------------------------------

KIND_NAMES = {"glass": "Glass", "buildings": "Buildings", "shell": "Powered shell", "gear": "Electronics"}
AI_GEAR_NAME = "GPU servers and network gear"


def _kind_name(era: str, kind: str) -> str:
    return AI_GEAR_NAME if kind == "gear" and era.startswith("AI") else KIND_NAMES[kind]


def _split(story: Story, width: float, height: float, fs: float, state: dict | None = None, interactive=False):
    """Known additions per era as a bar by kind, the era's headline asset first and in the accent (glass then,
    GPU servers now); a bracket above each bar spans that asset's share if the unassigned additions went all
    one way. `state`: grow (0–1 bar length), s (0 =
    dollar scale, 1 = shares), x40 (opacity of the scale note), seg (segment labels), bracket."""
    st = state or {"grow": 1.0, "s": 1.0, "x40": 0.0, "seg": 1.0, "bracket": 1.0}
    k = story.frames["split"]
    eras = story.extra["eras"]
    names = list(eras)
    portrait = height / width > 0.5
    label_px = (0 if portrait else 250) * fs
    total_px = 120 * fs
    bar_px = width - label_px - total_px
    x_scale = alt.Scale(domain=[-label_px / bar_px, 1 + total_px / bar_px], nice=False, zero=False)
    rows_y = {e: i * (2.2 if portrait else 1.6) for i, e in enumerate(names)}
    y_scale = alt.Scale(domain=[-1.2, max(rows_y.values()) + 0.9], reverse=True, nice=False, zero=False)
    x = alt.X("x:Q", scale=x_scale, axis=None)
    y = alt.Y("y:Q", scale=y_scale, axis=None)
    known = {e: k.filter(pl.col("era") == e)["usd"].sum() for e in names}
    big = max(known.values())
    segs, labels, brackets, totals, heads = [], [], [], [], []
    for e in names:
        y0 = rows_y[e]
        headline = eras[e]["headline"]
        part = k.filter(pl.col("era") == e).sort(pl.col("kind") != headline, pl.col("share"), descending=[False, True])
        scale = _lerp(known[e] / big, 1.0, _smooth(st["s"])) * st["grow"]
        x0 = 0.0
        for r in part.to_dicts():
            wdt = r["share"] * scale
            ink = (
                color("accent")
                if r["kind"] == headline
                else GREYS[1]
                if r["kind"] in ("buildings", "shell")
                else GREYS[0]
            )
            segs.append({"x": x0, "x2": x0 + wdt, "y": y0 - 0.32, "y2": y0 + 0.32, "ink": ink, "op": 1})
            labels.append(
                {
                    "x": x0 + wdt / 2,
                    "y": y0,
                    "text": (
                        f"{_kind_name(e, r['kind'])} {r['share']:.0%}"
                        if r["share"] * bar_px > (len(_kind_name(e, r["kind"])) + 5) * 0.62 * LABEL_PX * fs + 16 * fs
                        else f"{r['share']:.0%}"
                    ),
                    "ink": color("canvas"),
                    "op": st["seg"] if r["share"] >= 0.06 else 0.0,
                }
            )
            x0 += wdt
        lo, hi = eras[e]["headline_low"], eras[e]["headline_high"]
        yb = y0 - 0.5
        op = st["bracket"]
        brackets += [
            {"x": lo, "x2": hi, "y": yb - 0.012, "y2": yb + 0.012, "ink": color("text_secondary"), "op": op},
            {"x": lo - 0.0015, "x2": lo + 0.0015, "y": yb, "y2": yb + 0.12, "ink": color("text_secondary"), "op": op},
            {"x": hi - 0.0015, "x2": hi + 0.0015, "y": yb, "y2": yb + 0.12, "ink": color("text_secondary"), "op": op},
        ]
        labels.append(
            {
                "x": hi + 0.012,
                "y": yb,
                "text": f"{lo:.0%}–{hi:.0%} counting unassigned spending",
                "ink": color("text_secondary"),
                "op": op,
            }
        )
        totals.append(
            {
                "x": x0 + 0.015,
                "y": y0,
                "text": f"{fmt_usd(eras[e]['total_usd'])} in all",
                "ink": color("text_secondary"),
                "op": st["grow"],
            }
        )
        if portrait:
            heads.append({"x": 0.0, "y": y0 - 0.95, "text": e, "ink": color("text"), "op": 1})
        else:
            heads.append({"x": -0.02, "y": y0, "text": e, "ink": color("text"), "op": 1})
    ratio = eras[names[-1]]["total_usd"] / eras[names[0]]["total_usd"]
    note = [
        {
            "x": 0.0,
            "y": rows_y[names[0]] + 0.75,
            "text": f"{ratio:.0f}× more added in a year now than by the fiber builders then",
            "ink": color("accent"),
            "op": st["x40"],
        }
    ]
    layers = [
        _rects(brackets, x, y),
        _rects(segs, x, y),
        _texts(
            [r for r in labels if r["ink"] == color("canvas")],
            fs,
            x,
            y,
            LABEL_PX,
            align="center",
            baseline="middle",
            fontWeight="bold",
        ),
        _texts(
            [r for r in labels if r["ink"] != color("canvas")], fs, x, y, LABEL_PX - 2, align="left", baseline="middle"
        ),
        _texts(totals, fs, x, y, LABEL_PX - 1, align="left", baseline="middle"),
        _texts(
            heads, fs, x, y, LABEL_PX + 1, align="left" if portrait else "right", baseline="middle", fontWeight="bold"
        ),
        _texts(note, fs, x, y, LABEL_PX, align="left", baseline="middle"),
    ]
    chart = alt.layer(*layers).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


def split(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False):
    return fit(lambda w, h: _split(story, w, h, font_scale, None, interactive), width, height)


def split_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict):
    """Video: both bars grow at dollar scale (the fiber builders' a sliver), the scale note shows; then both
    stretch to 100% of known additions, the kind labels fade in, then the brackets."""
    fs = font_scale
    w, h = fit_size(lambda a, b: _split(story, a, b, fs, None), width, height)
    base = {"grow": 0.0, "s": 0.0, "x40": 0.0, "seg": 0.0, "bracket": 0.0}
    states = [dict(base) for _ in range(_n(0.5))]
    states += [dict(base, grow=_smooth((i + 1) / _n(1.2))) for i in range(_n(1.2))]
    states += [dict(base, grow=1.0, x40=_smooth((i + 1) / _n(0.5))) for i in range(_n(0.5))]
    states += [dict(base, grow=1.0, x40=1.0) for _ in range(_n(1.8))]
    states += [dict(base, grow=1.0, x40=1.0 - (i + 1) / _n(0.4)) for i in range(_n(0.4))]
    states += [dict(base, grow=1.0, s=(i + 1) / _n(1.4)) for i in range(_n(1.4))]
    states += [dict(base, grow=1.0, s=1.0, seg=_smooth((i + 1) / _n(0.6))) for i in range(_n(0.6))]
    states += [dict(base, grow=1.0, s=1.0, seg=1.0, bracket=_smooth((i + 1) / _n(0.6))) for i in range(_n(0.6))]
    states += [dict(grow=1.0, s=1.0, x40=0.0, seg=1.0, bracket=1.0) for _ in range(_n(3.0))]
    return [_split(story, w, h, fs, st).to_dict() for st in states], FPS


# --- exposure ----------------------------------------------------------------------------------

EXPOSURE_KINDS = ["gear", "mixed", "shell"]
EXPOSURE_NAMES = {
    "gear": "GPU servers and network gear",
    "mixed": "Mixed or not yet in service",
    "shell": "Buildings and land (powered shell)",
}
EXPOSURE_INK = {"gear": None, "mixed": MIXED_INK, "shell": GREYS[1]}  # gear: the accent


def _exposure(story: Story, width: float, height: float, fs: float, state: dict | None = None, interactive=False):
    """Per company: gross PP&E by kind as a bar (estimates lighter), the total, and debt ÷ cash. `state`: grow,
    s (0 = dollar scale, 1 = shares), debt (column opacity). Rows stay in one order, by the GPU-server share."""
    st = state or {"grow": 1.0, "s": 1.0, "debt": 1.0}
    e = story.frames["exposure"]
    totals = e.group_by("company").agg(pl.col("usd").sum().alias("total"), pl.col("debt_to_cash").first())
    gear = e.filter(pl.col("kind") == "gear").group_by("company").agg(pl.col("share").sum())
    by_size = totals.sort("total", descending=True)["company"].to_list()
    by_shell = gear.sort("share", descending=True)["company"].to_list()
    portrait = height / width > 0.5
    label_px, total_px, debt_px = 130 * fs, 100 * fs, 120 * fs
    bar_px = width - label_px - total_px - debt_px
    x_scale = alt.Scale(domain=[-label_px / bar_px, 1 + (total_px + debt_px) / bar_px], nice=False, zero=False)
    n = len(by_size)
    step = 1.0
    y_scale = alt.Scale(domain=[-2.4 if portrait else -1.6, (n - 1) * step + 0.7], reverse=True, nice=False, zero=False)
    x = alt.X("x:Q", scale=x_scale, axis=None)
    y = alt.Y("y:Q", scale=y_scale, axis=None)
    big = totals["total"].max()
    u = _smooth(st["s"])
    segs, inside, names, tot_labels, debts = [], [], [], [], []
    for c in by_size:
        yy = by_shell.index(c) * step
        t = totals.filter(pl.col("company") == c).row(0, named=True)
        scale = _lerp(t["total"] / big, 1.0, u) * st["grow"]
        x0 = 0.0
        for kind in EXPOSURE_KINDS:
            for est in (False, True):
                part = e.filter((pl.col("company") == c) & (pl.col("kind") == kind) & (pl.col("estimated") == est))
                if part.is_empty():
                    continue
                share = part["share"].sum()
                wdt = share * scale
                ink = EXPOSURE_INK[kind] or color("accent")
                segs.append(
                    {"x": x0, "x2": x0 + wdt, "y": yy - 0.3, "y2": yy + 0.3, "ink": ink, "op": 0.5 if est else 1.0}
                )
                x0 += wdt
            k_rows = e.filter((pl.col("company") == c) & (pl.col("kind") == kind))
            k_share = k_rows["share"].sum()
            est_part = bool(k_rows["estimated"].any()) if k_rows.height else False
            if kind in ("shell", "gear") and k_share >= 0.07:
                inside.append(
                    {
                        "x": x0 - k_share * scale / 2,
                        "y": yy,
                        "text": f"{k_share:.0%}",
                        "ink": color("text") if est_part else color("canvas"),
                        "op": u,
                    }
                )
        names.append({"x": -0.02, "y": yy, "text": c, "ink": color("text"), "op": 1})
        tot_labels.append(
            {"x": x0 + 0.015, "y": yy, "text": fmt_usd(t["total"]), "ink": color("text_secondary"), "op": st["grow"]}
        )
        dc = t["debt_to_cash"]
        debts.append(
            {
                "x": 1 + (total_px + debt_px * 0.55) / bar_px,
                "y": yy,
                "text": f"{dc:.1f}×",
                "ink": color("accent") if dc >= 2 else color("text_secondary"),
                "op": st["debt"],
            }
        )
    head_y = -0.85
    debt_head = [
        {
            "x": 1 + (total_px + debt_px * 0.55) / bar_px,
            "y": head_y,
            "text": "Debt ÷ cash",
            "ink": color("text_secondary"),
            "op": st["debt"],
        }
    ]
    heads = []
    legend_y = -1.9 if portrait else -1.2
    legend, lx = [], 0.0
    sw = 0.025
    for i, kind in enumerate(EXPOSURE_KINDS):
        ink = EXPOSURE_INK[kind] or color("accent")
        ly = legend_y + (i * 0.33 if portrait else 0.0)
        legend.append({"x": lx, "x2": lx + sw, "y": ly - 0.11, "y2": ly + 0.11, "ink": ink, "op": 1})
        heads.append(
            {"x": lx + sw + 0.01, "y": ly, "text": EXPOSURE_NAMES[kind], "ink": color("text_secondary"), "op": 1}
        )
        if not portrait:
            lx += sw + 0.02 + len(EXPOSURE_NAMES[kind]) * 0.0105 * 1000 / bar_px
    layers = [
        _rects(segs, x, y),
        _rects(legend, x, y),
        _texts(inside, fs, x, y, LABEL_PX, align="center", baseline="middle", fontWeight="bold"),
        _texts(names, fs, x, y, LABEL_PX + 1, align="right", baseline="middle"),
        _texts(tot_labels, fs, x, y, LABEL_PX - 1, align="left", baseline="middle"),
        _texts(debts, fs, x, y, LABEL_PX + 1, align="center", baseline="middle", fontWeight="bold"),
        _texts(heads, fs, x, y, LABEL_PX - 1, align="left", baseline="middle"),
        _texts(debt_head, fs, x, y, LABEL_PX - 1, align="center", baseline="middle"),
    ]
    return alt.layer(*layers).properties(width=width, height=height).configure(**vl_config(fs))


def exposure(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False):
    return fit(lambda w, h: _exposure(story, w, h, font_scale, None, interactive), width, height)


def exposure_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict):
    """Video: bars grow at dollar scale (Amazon's $534bn to CoreWeave's $34bn); they stretch to 100% shares,
    CoreWeave's GPU-server share on top; debt ÷ cash fades in."""
    fs = font_scale
    w, h = fit_size(lambda a, b: _exposure(story, a, b, fs, None), width, height)
    base = {"grow": 0.0, "s": 0.0, "debt": 0.0}
    states = [dict(base) for _ in range(_n(0.5))]
    states += [dict(base, grow=_smooth((i + 1) / _n(1.2))) for i in range(_n(1.2))]
    states += [dict(base, grow=1.0) for _ in range(_n(1.4))]
    states += [dict(base, grow=1.0, s=(i + 1) / _n(1.4)) for i in range(_n(1.4))]
    states += [dict(base, grow=1.0, s=1.0) for _ in range(_n(0.6))]
    states += [dict(base, grow=1.0, s=1.0, debt=_smooth((i + 1) / _n(0.7))) for i in range(_n(0.7))]
    states += [dict(grow=1.0, s=1.0, debt=1.0) for _ in range(_n(3.0))]
    return [_exposure(story, w, h, fs, st).to_dict() for st in states], FPS
