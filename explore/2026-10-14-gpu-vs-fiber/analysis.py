"""GPUs vs dark fiber: does anything keep its value after a bust, the way the fiber did? (exploration)

Reads the asset_values mart (110) only, picking rows by id from explore.yaml so each point traces to
its cited quote. Four views: price paths, book useful lives, what dot-com networks fetched, and
generations (capacity per fiber pair vs NVIDIA's claimed gain per GPU generation). See README.md.
`cachereg render explore/2026-10-14-gpu-vs-fiber` renders the visuals declared in explore.yaml.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

SOURCES = ["curated_asset_values", "sec_edgar"]
STRETCHED = 2.0  # debt at least this multiple of cash and short-term investments
COLS = "id, statement_date, entity, asset, metric, value, unit, qualifier, period_start, period_end, scope, source_kind"


def rows(con, ids: list[str]) -> pl.DataFrame:
    """The mart rows with these ids, in the given order; every id must exist as of the build."""
    got = query(con, f"SELECT {COLS} FROM asset_values WHERE list_contains(?, id)", [ids])  # noqa: S608
    missing = set(ids) - set(got["id"])
    if missing:
        raise ValueError(f"explore.yaml names rows missing from asset_values: {sorted(missing)}")
    order = pl.DataFrame({"id": ids, "pos": range(len(ids))})
    return got.join(order, on="id").sort("pos").drop("pos")


def midpoint(start: date, end: date) -> date:
    return start + (end - start) / 2


def years(a: date, b: date) -> float:
    return (b - a).days / 365.25


def price_paths(con, series: list[dict]) -> pl.DataFrame:
    """One row per point: price (per GPU where `per` is set), % of the series' first quote, years since it."""
    out = []
    for s in series:
        picks = [p if isinstance(p, dict) else {"id": p} for p in s["ids"]]
        r = rows(con, [p["id"] for p in picks])
        per = {p["id"]: p.get("per", 1) for p in picks}
        pts = [
            {
                "series": s["name"],
                "era": s["era"],
                "id": x["id"],
                "entity": x["entity"],
                "day": midpoint(x["period_start"], x["period_end"]),
                "price": x["value"] / per[x["id"]],
                "unit": x["unit"].replace("usd_per_instance_hour", "usd_per_gpu_hour")
                if per[x["id"]] > 1
                else x["unit"],
                "source_kind": x["source_kind"],
            }
            for x in r.to_dicts()
        ]
        pts.sort(key=lambda p: p["day"])
        units = {p["unit"] for p in pts}
        if len(units) != 1:
            raise ValueError(f"price series {s['name']!r} mixes units {sorted(units)}")
        first = pts[0]
        for p in pts:
            p["pct_of_first"] = 100 * p["price"] / first["price"]
            p["years"] = years(first["day"], p["day"])
            p["first_year"] = first["day"].year
        out += pts
    return pl.DataFrame(out)


def years_on_books(life: pl.DataFrame, groups: list[dict]) -> pl.DataFrame:
    """Per group: the median across companies of the midpoint of each company's stated life (a single figure
    is its own midpoint), ordered by era (dot-com first) and then by years."""
    meta = {g["group"]: (g["short"], g["lifespan"], g.get("tag")) for g in groups}
    return (
        life.with_columns(mid=(pl.col("low") + pl.col("high")) / 2)
        .group_by("group", "era", maintain_order=True)
        .agg(
            years=pl.col("mid").median(),
            companies=pl.len(),
            low=pl.col("low").min(),
            high=pl.col("high").max(),
            who=pl.col("entity").str.join(", "),
        )
        .with_columns(
            label=pl.col("group").map_elements(lambda g: meta[g][0], return_dtype=pl.String),
            lifespan=pl.col("group").map_elements(lambda g: meta[g][1], return_dtype=pl.String),
            tag=pl.col("group").map_elements(lambda g: meta[g][2], return_dtype=pl.String),
            era_order=pl.col("era").replace_strict({"dotcom": 0, "ai": 1}, return_dtype=pl.Int64),
        )
        .sort("era_order", "years")
    )


def lives(con, groups: list[dict]) -> pl.DataFrame:
    """One row per (group, company figure): low and high years (equal for a single figure)."""
    out = []
    for g in groups:
        r = rows(con, g["ids"])
        for (entity, scope), part in r.group_by("entity", "scope", maintain_order=True):
            out.append(
                {
                    "group": g["group"],
                    "era": g["era"],
                    "entity": entity,
                    "scope": scope,
                    "metric": part["metric"][0],
                    "low": part["value"].min(),
                    "high": part["value"].max(),
                    "ids": ", ".join(part["id"]),
                }
            )
    return pl.DataFrame(out)


STAGE = {
    "capital_invested": "raised / invested",
    "debt_at_bankruptcy": "debt at bankruptcy",
    "distressed_sale_price": "sold in bankruptcy",
    "deal_value": "bought later",
}


def recovery(con, tracks: list[dict]) -> pl.DataFrame:
    out = []
    for t in tracks:
        for x in rows(con, t["ids"]).to_dicts():
            out.append(
                {
                    "company": t["company"],
                    "stage": STAGE[x["metric"]],
                    "day": midpoint(x["period_start"], x["period_end"]),
                    "usd": x["value"],
                    "scope": x["scope"],
                    "id": x["id"],
                }
            )
    return pl.DataFrame(out).sort("company", "day")


def fmt_usd(v: float) -> str:
    if v >= 1e9:
        return f"${v / 1e9:.3g}bn"
    if v >= 1e6:
        return f"${v / 1e6:.3g}m"
    return f"${v:,.0f}"


def ladder(con, pairs: list[dict]) -> pl.DataFrame:
    """Per GPU generation: the January and October 2026 prices (one venue, one configuration) and the change."""
    out = []
    for p in pairs:
        a, b = rows(con, [p["from"], p["to"]]).to_dicts()
        if a["unit"] != b["unit"] or a["entity"] != b["entity"]:
            raise ValueError(f"ladder {p['gpu']}: the two prices differ in venue or unit")
        out.append(
            {
                "gpu": p["gpu"],
                "entity": a["entity"],
                "from_day": a["period_end"],
                "to_day": b["period_end"],
                "from_price": a["value"],
                "to_price": b["value"],
                "change": b["value"] / a["value"] - 1,
                "from_id": a["id"],
                "to_id": b["id"],
            }
        )
    return pl.DataFrame(out)


def book_life(con, launches: list[dict], years_on_books: int, life_ids: list[str]) -> pl.DataFrame:
    """Per generation: announcement, end of a `years_on_books` book life, and the later generations announced
    before that end (as of today: only announcements already made)."""
    lives_ = rows(con, life_ids)
    if set(lives_["value"]) != {float(years_on_books)}:
        raise ValueError(f"book_life_ids do not all state {years_on_books} years")
    days = {x["gpu"]: rows(con, [x["id"]])["statement_date"][0] for x in launches}
    out = []
    for g, d in days.items():
        end = d.replace(year=d.year + years_on_books)
        later = [h for h, e in days.items() if d < e < end]
        out.append({"gpu": g, "announced": d, "book_end": end, "later": ", ".join(later), "n_later": len(later)})
    return pl.DataFrame(out)


SCALE = {"usd": 1.0, "usd_thousands": 1e3, "usd_millions": 1e6}


def ppe_rows(con, companies: list[str], cfg: dict) -> pl.DataFrame:
    """Gross PP&E per (company, balance-sheet date, kind) in dollars, with `estimated` for the parts of a line
    split by the company's own stated mix (`allocate` in explore.yaml). For a date reported in several filings
    (restatements), the latest filing's figures."""
    g = query(
        con,
        """SELECT entity AS company, asset, scope, unit, value, period_end, statement_date FROM asset_values
           WHERE metric = 'ppe_gross' AND list_contains(?, entity)
           QUALIFY statement_date = max(statement_date) OVER (PARTITION BY entity, period_end)""",
        [companies],
    )
    unknown = set(g["asset"]) - set(cfg["kinds"])
    if unknown:
        raise ValueError(f"no kind for assets {sorted(unknown)}")
    g = g.with_columns(
        kind=pl.col("asset").replace_strict(cfg["kinds"], return_dtype=pl.String),
        usd=pl.col("value") * pl.col("unit").replace_strict(SCALE, return_dtype=pl.Float64),
        estimated=pl.lit(False),
    )
    for a in cfg.get("allocate", []):
        if a["company"] not in companies:
            continue
        hit = (pl.col("company") == a["company"]) & pl.col("scope").str.starts_with(a["line"])
        if g.filter(hit).is_empty():
            raise ValueError(f"allocate: no line {a['line']!r} for {a['company']}")
        shares = {k: v for k, v in a.items() if k not in ("company", "line")}
        if abs(sum(shares.values()) - 1) > 1e-9:
            raise ValueError(f"allocate: shares for {a['company']} do not sum to 1")
        parts = [
            g.filter(hit).with_columns(kind=pl.lit(k), usd=pl.col("usd") * v, estimated=pl.lit(True))
            for k, v in shares.items()
        ]
        g = pl.concat([g.filter(~hit), *parts])
    return g.group_by("company", "period_end", "kind", "estimated").agg(pl.col("usd").sum())


LONG = ("glass", "buildings", "shell")


def era_split(con, cfg: dict) -> tuple[pl.DataFrame, dict]:
    """Additions to gross PP&E over one year, per era and kind (the change between two balance sheets a year
    apart, summed over the era's companies), with each kind's share of the known (non-mixed) additions; and per
    era the totals and the range of the long-lived share if the mixed additions went all one way."""
    to_date = lambda x: x if isinstance(x, date) else date.fromisoformat(x)  # noqa: E731
    d = cfg["split_dotcom"]
    eras = {
        "Dot-com fiber builders, 2000": (
            d["carriers"],
            {c: (to_date(d["now"]), to_date(d["prior"])) for c in d["carriers"]},
        ),
    }
    ai = ppe_rows(con, cfg["glass_companies"], cfg)
    ai_dates = {}
    for c in cfg["glass_companies"]:
        ends = sorted(ai.filter(pl.col("company") == c)["period_end"].unique())
        ai_dates[c] = (ends[-1], ends[-2])
    eras["AI builders, latest year"] = (cfg["glass_companies"], ai_dates)
    out, totals = [], {}
    for era, (companies, dates) in eras.items():
        g = ppe_rows(con, companies, cfg)
        used = []
        for c in companies:
            now, prior = dates[c]
            a = g.filter((pl.col("company") == c) & (pl.col("period_end") == now))
            b = g.filter((pl.col("company") == c) & (pl.col("period_end") == prior))
            if a.is_empty():
                raise ValueError(f"split: no PP&E for {c} at {now}")
            if b.is_empty():
                continue  # no prior column: no additions to measure
            used.append(c)
            for kind in sorted(set(a["kind"]) | set(b["kind"])):
                for est in (False, True):
                    v = a.filter((pl.col("kind") == kind) & (pl.col("estimated") == est))["usd"].sum()
                    w = b.filter((pl.col("kind") == kind) & (pl.col("estimated") == est))["usd"].sum()
                    if v or w:
                        out.append({"era": era, "company": c, "kind": kind, "estimated": est, "usd": v - w})
        e = pl.DataFrame([r for r in out if r["era"] == era])
        total, mixed = e["usd"].sum(), e.filter(pl.col("kind") == "mixed")["usd"].sum()
        long_ = e.filter(pl.col("kind").is_in(LONG))["usd"].sum()
        known = total - mixed
        totals[era] = {
            "companies": used,
            "total_usd": total,
            "mixed_usd": mixed,
            "long_share": long_ / known,
            "long_low": long_ / total,
            "long_high": (long_ + mixed) / total,
        }
    per = pl.DataFrame(out)
    kinds = (
        per.filter(pl.col("kind") != "mixed")
        .group_by("era", "kind", maintain_order=True)
        .agg(pl.col("usd").sum(), estimated_usd=pl.col("usd").filter(pl.col("estimated")).sum())
        .with_columns(share=pl.col("usd") / pl.col("usd").sum().over("era"))
    )
    return kinds, totals


def exposure(con, cfg: dict, who: pl.DataFrame) -> pl.DataFrame:
    """Per company and kind (gear / shell / mixed): gross PP&E on its latest balance sheet as a share of the
    total (estimated parts flagged), with the company's debt ÷ cash and short-term investments (mart 111)."""
    g = ppe_rows(con, cfg["glass_companies"], cfg)
    g = g.filter(pl.col("period_end") == pl.col("period_end").max().over("company"))
    out = g.with_columns(total=pl.col("usd").sum().over("company")).with_columns(share=pl.col("usd") / pl.col("total"))
    debt = who.select("company", (pl.col("debt_usd") / pl.col("liquidity_usd")).alias("debt_to_cash"))
    missing = set(cfg["glass_companies"]) - set(debt["company"])
    if missing:
        raise ValueError(f"exposure: no balance sheet for {sorted(missing)}")
    return out.join(debt, on="company", how="left")


def buyers(con, tickers: list[str]) -> pl.DataFrame:
    return query(
        con,
        """SELECT ticker, company, company_group, period_end, liquidity_usd, debt_usd,
                  operating_lease_liability_usd, liquidity_tags, debt_tags
           FROM balance_sheet_latest WHERE list_contains(?, ticker)""",
        [tickers],
    ).with_columns(net_usd=pl.col("liquidity_usd") - pl.col("debt_usd"))


def build(con, as_of: date, cfg: dict) -> Story:
    prices = price_paths(con, cfg["prices"])
    life = lives(con, cfg["lives"])
    rec = recovery(con, cfg["recovery"])
    lad = ladder(con, cfg["ladder"])
    books = book_life(con, cfg["launches"], int(cfg["book_life_years"]), cfg["book_life_ids"])
    glut = prices.filter(pl.col("series").is_in(cfg["glut_series"]) & (pl.col("years") <= cfg["glut_years"]))
    lit = rows(con, [cfg["glut_utilization_id"]]).to_dicts()[0]
    who = buyers(con, cfg["buyers"])
    kinds, eras = era_split(con, cfg)
    who = who.with_columns(times=pl.col("debt_usd") / pl.col("liquidity_usd"))
    exp = exposure(con, cfg, who)
    dot, ai = (eras[k] for k in eras)
    dot_era, ai_era = list(eras)

    def kind_share(era: str, kind: str) -> float:
        v = kinds.filter((pl.col("era") == era) & (pl.col("kind") == kind))["share"]
        return v[0] if v.len() else 0.0

    shell = {
        c: exp.filter((pl.col("company") == c) & (pl.col("kind") == "shell"))["share"].sum()
        for c in cfg["glass_companies"]
    }
    least = min(shell, key=shell.get)
    most = max(shell, key=shell.get)
    least_debt = exp.filter(pl.col("company") == least)["debt_to_cash"][0]

    ai_servers = life.filter(pl.col("group").str.starts_with("AI servers"))
    electronics = life.filter(pl.col("group").str.starts_with("Dot-com network electronics"))
    fiber = life.filter(pl.col("group").str.starts_with("Dot-com fiber"))
    gc = rec.filter(pl.col("company") == "Global Crossing")
    gc_raised = gc.filter(pl.col("stage") == "raised / invested")["usd"][0]
    gc_sold = gc.filter(pl.col("stage") == "sold in bankruptcy")["usd"][0]
    gc_later = gc.filter(pl.col("stage") == "bought later")["usd"][0]

    def path(series: str) -> pl.DataFrame:
        return glut.filter(pl.col("series") == series).sort("years")

    oc3, h100 = path("OC-3 circuit, New York–LA"), path("H100, market rate")
    oc3_1y = oc3.filter(pl.col("years").round(0) == 1)["pct_of_first"][0]
    h100_low = h100["pct_of_first"].min()
    h100_last = h100["pct_of_first"][-1]
    oldest, newest = lad.row(0, named=True), lad.row(-1, named=True)
    first_gen = books.row(0, named=True)
    stretched = who.filter(pl.col("times") >= STRETCHED)
    rich = who.filter(pl.col("times") < STRETCHED)
    rich_names = ", ".join(rich.sort("liquidity_usd", descending=True)["company"])
    stretched_names = " and ".join(stretched.sort("times")["company"])

    yrs = years_on_books(life, cfg["lives"])
    span = {
        p: yrs.filter(pl.col("group").str.starts_with(p))["years"][0]
        for p in ("AI servers", "Dot-com fiber", "Dot-com network", "Data-centre")
    }
    title = "So far, GPUs look like the electronics on the fiber, not the glass"
    ai_lo, ai_hi = ai_servers["low"].min(), ai_servers["high"].max()
    subtitle = (
        f"AI servers are written off over {ai_lo:g}–{ai_hi:g} years, like the dot-com "
        f"carriers' network electronics ({electronics['low'].min():g}–{electronics['high'].max():g}), not their fiber "
        f"(up to {fiber['high'].max():g}). The long-lived AI assets are buildings and power."
    )
    by_visual = {
        "years": {
            "title": (
                f"GPUs get {span['AI servers']:g} years on the books, like the dot-com era's network gear "
                f"({span['Dot-com network']:g}); its glass got {span['Dot-com fiber']:g}"
            ),
            "subtitle": (
                "One square per year of book life: the median across companies of the midpoint of each stated "
                "life. Each build-out paired short-lived gear (lime) with long-lived assets (grey): then the glass, "
                "now the powered shell and the power plants and grid behind it."
            ),
        },
        "book-life": {
            "title": (
                f"An {first_gen['gpu']} stays on the books for {cfg['book_life_years']} years; NVIDIA announced "
                f"{first_gen['n_later']} newer generations in that time"
            ),
            "subtitle": (
                f"Each bar runs from NVIDIA's announcement to the end of a {cfg['book_life_years']}-year book life, "
                "the life Microsoft, Alphabet, Oracle and CoreWeave give servers, and CoreWeave's lenders give GPU "
                "collateral. Vertical lines mark later announcements. Chips bought after launch stay on the books "
                "longer still."
            ),
        },
        "ladder": {
            "title": (
                f"Every GPU generation got dearer to rent in 2026, even the {oldest['gpu']} ({oldest['change']:+.0%})"
            ),
            "subtitle": (
                f"Lambda's on-demand price per GPU-hour on 8-GPU machines, January vs October 2026. The newest, the "
                f"{newest['gpu']}, rose {newest['change']:.0%}; the oldest, the {oldest['gpu']}, rose "
                f"{oldest['change']:.0%}, to {oldest['to_price']:.2f} dollars an hour."
            ),
        },
        "glut": {
            "title": (
                f"In 2001 a glut showed in prices within a year; H100 rents fell to {h100_low:.0f}%, then rose to "
                f"{h100_last:.0f}%"
            ),
            "subtitle": (
                f"Price as % of each series' first quote, by years since that quote (log scale). A New York–LA "
                f"line lost {100 - oc3_1y:.0f}% of its price in its first year, when carriers used about "
                f"{lit['value']:g}% of their lit capacity (Merrill Lynch, July 2001). H100 rents are rising again."
            ),
        },
        "recovery": {
            "title": (
                f"Global Crossing raised {fmt_usd(gc_raised)}, sold in bankruptcy for {fmt_usd(gc_sold)}, "
                f"and was bought for {fmt_usd(gc_later)} nine years later"
            ),
            "subtitle": (
                "What four dot-com fiber networks raised, owed and fetched, in dollars (log scale). Investors lost "
                "almost everything; the networks kept working for their new owners. No GPU fleet has yet been sold "
                "in bankruptcy."
            ),
        },
        "split": {
            "title": (
                f"In 2000 the fiber builders spent {kind_share(dot_era, 'glass'):.0%} of their known additions on "
                f"glass; the AI builders spend {kind_share(ai_era, 'gear'):.0%} on short-lived gear"
            ),
            "subtitle": (
                f"Additions to gross property and equipment in one year: {fmt_usd(dot['total_usd'])} at "
                f"{len(dot['companies'])} fiber carriers in 2000, {fmt_usd(ai['total_usd'])} at Microsoft, "
                "Alphabet, Amazon, Meta, Oracle and "
                f"CoreWeave in their latest year ({ai['total_usd'] / dot['total_usd']:.0f}×). Bars: known spending; "
                "brackets: the long-lived share if the unassigned spending went all one way."
            ),
            "notes": [
                "Unassigned: construction in progress and lines that lump kinds. Alphabet's technical infrastructure "
                "is split 60/40 by its own statement (estimate). The carriers report fiber and electronics apart; "
                "nationally, US communications-equipment spending ran far above fiber and structures in 2000."
            ],
        },
        "exposure": {
            "title": (
                f"{least} owns little of the powered shell: {shell[least]:.0%} of its property is buildings and "
                f"land, and it owes {least_debt:.0f}× its cash"
            ),
            "subtitle": (
                "Gross property and equipment on each latest 10-K: buildings and land (the powered shell), mixed or "
                "not yet in service, and servers and network gear. Right: debt ÷ cash and short-term investments "
                f"(leases excluded). {least} rents its data centres; its landlords own the shell. "
                f"{most}: {shell[most]:.0%} shell."
            ),
            "notes": [
                "Alphabet reports servers and data centres as one line, split 60/40 by its own statement (lighter: "
                "estimate). Buildings include offices at Amazon, Microsoft and Alphabet."
            ],
        },
        "buyers": {
            "title": (
                f"{len(rich)} firms hold {fmt_usd(rich['liquidity_usd'].sum())} in cash; {stretched_names} "
                f"owe {stretched['times'].min():.0f}–{stretched['times'].max():.0f}× what they hold"
            ),
            "subtitle": (
                f"Cash and short-term investments vs debt (leases excluded) on each company's latest balance sheet. "
                f"{rich_names} could fund purchases; {stretched_names} owe at least {STRETCHED:g}× their cash. "
                "In 2002–05 the buyers of bankrupt networks were the survivors with cash."
            ),
        },
    }
    return Story(
        title=title,
        subtitle=subtitle,
        frames={
            "prices": prices,
            "glut": glut,
            "lives": life,
            "years": yrs,
            "recovery": rec,
            "ladder": lad,
            "book_life": books,
            "buyers": who,
            "split": kinds,
            "exposure": exp,
        },
        sources=SOURCES,
        as_of=as_of,
        method="cited figures (curated_asset_values) and XBRL balance sheets (SEC EDGAR); values as stated",
        caveats=[
            "Scattered quotes, not series: venues, tiers and configurations differ, so only same-source lines "
            "are joined (the H100 market line joins Latent Space's 2023–24 quotes to Silicon Data's neocloud index).",
            "Lit bandwidth is priced per unit of capacity, which the optics multiplied, so its fall overstates "
            "what happened to the fiber itself; there is no public dark-fiber price series for 1998–2010.",
            "Book useful lives are accounting choices, not observed lifetimes; ranges cover asset classes "
            "within a company. Buildings lives include offices.",
            "Bankruptcy figures differ in scope (Global Crossing's $250m bought 61.5% of the company; Velocita's "
            "$37m bought the network only); 'bought later' prices include new investment since.",
            "The 2026 price ladder is one venue (Lambda) on two dates; hyperscalers' list prices barely move.",
            "Announcement dates mark generations; volume shipments came months later.",
            "Balance sheets as filed in XBRL (tag choices in mart 111); leases, which are large for CoreWeave and "
            "Oracle, are excluded from debt. Alphabet's cash and short-term investments doubled in its Q2 2026 10-Q.",
        ],
        by_visual=by_visual,
        extra={"h100_low": h100_low, "h100_last": h100_last, "oc3_1y": oc3_1y, "lit_pct": lit["value"], "eras": eras},
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["ladder"].select("gpu", "entity", "from_day", "from_price", "to_day", "to_price", "change")
