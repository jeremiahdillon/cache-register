"""GPUs vs dark fiber: does anything keep its value after a bust, the way the fiber did? (exploration)

Reads the asset_values mart (100) only, picking rows by id from explore.yaml so each point traces to
its cited quote. Four views: price paths, book useful lives, what dot-com networks fetched, and
generations (capacity per fiber pair vs NVIDIA's claimed gain per GPU generation). See README.md.
`cachereg render explore/2026-10-14-gpu-vs-fiber` renders the visuals declared in explore.yaml.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

SOURCES = ["curated_asset_values"]
COLS = "id, entity, asset, metric, value, unit, qualifier, period_start, period_end, scope, source_kind"


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


def build(con, as_of: date, cfg: dict) -> Story:
    prices = price_paths(con, cfg["prices"])
    life = lives(con, cfg["lives"])
    rec = recovery(con, cfg["recovery"])
    cap = rows(con, cfg["capacity_ids"]).with_columns(
        day=pl.col("period_end"),
        gbps=pl.when(pl.col("unit") == "tbps").then(pl.col("value") * 1000).otherwise(pl.col("value")),
    )
    gen = rows(con, cfg["generation_ids"]).with_columns(day=pl.col("period_end"))

    last = prices.group_by("series", maintain_order=True).agg(
        pl.col("era").first(), pl.col("pct_of_first").last(), pl.col("years").last(), pl.col("first_year").first()
    )
    pct = {r["series"]: r for r in last.to_dicts()}
    transit, oc3, h100 = pct["US IP transit, per Mbps"], pct["OC-3 circuit, New York–LA"], pct["H100, market rate"]
    ai_servers = life.filter(pl.col("group").str.starts_with("AI servers"))
    electronics = life.filter(pl.col("group").str.starts_with("Dot-com network electronics"))
    fiber = life.filter(pl.col("group").str.starts_with("Dot-com fiber"))

    gc = rec.filter(pl.col("company") == "Global Crossing")
    gc_raised = gc.filter(pl.col("stage") == "raised / invested")["usd"][0]
    gc_sold = gc.filter(pl.col("stage") == "sold in bankruptcy")["usd"][0]
    gc_later = gc.filter(pl.col("stage") == "bought later")["usd"][0]
    cap0, cap1 = cap.sort("day")["gbps"][0], cap["gbps"].max()

    title = "So far, GPUs look like the electronics on the fiber, not the glass"
    ai_lo, ai_hi = ai_servers["low"].min(), ai_servers["high"].max()
    subtitle = (
        f"AI servers are written off over {ai_lo:g}–{ai_hi:g} years, like the dot-com "
        f"carriers' network electronics ({electronics['low'].min():g}–{electronics['high'].max():g}), not their fiber "
        f"(up to {fiber['high'].max():g}). Yet GPU rents have held up far better than bandwidth prices did."
    )
    by_visual = {
        "lives": {"title": title, "subtitle": subtitle},
        "prices": {
            "title": (
                f"{oc3['years']:.0f} years on, a coast-to-coast line cost {oc3['pct_of_first']:.0f}% "
                "of its 2000 price; "
                f"an H100 rents for {h100['pct_of_first']:.0f}% of its launch rate"
            ),
            "subtitle": (
                "Each line is one price series as a % of its own first quote, by years since that quote (log scale). "
                f"Dot-com bandwidth in grey: US IP transit reached {transit['pct_of_first']:.1f}% of its 1998 price "
                "by 2010. GPU rents per GPU-hour in colour: at Lambda, older GPUs cost more in 2026 than when first "
                "listed."
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
        "generations": {
            "title": f"The same fiber pair carries {cap1 / cap0:.0f}× more than in 2001; each GPU generation is "
            "claimed to be 10–30× better than the last",
            "subtitle": (
                "Left: capacity of one fiber pair with the optics of the day. Right: NVIDIA's own 'up to' claim "
                "for each generation against the one before, on its chosen workload. New optics made old glass "
                "worth more; new GPUs make old ones worth less."
            ),
        },
    }
    return Story(
        title=title,
        subtitle=subtitle,
        frames={"prices": prices, "lives": life, "recovery": rec, "capacity": cap, "generations": gen},
        sources=SOURCES,
        as_of=as_of,
        method="cited figures from filings, company statements and press (curated_asset_values); values as stated",
        caveats=[
            "Scattered quotes, not series: venues, tiers and configurations differ, so only same-source lines "
            "are joined (the H100 market line joins Latent Space's 2023–24 quotes to Silicon Data's neocloud index).",
            "Lit bandwidth is priced per unit of capacity, which the optics multiplied, so its fall overstates "
            "what happened to the fiber itself; there is no public dark-fiber price series for 1998–2010.",
            "Book useful lives are accounting choices, not observed lifetimes; ranges cover asset classes "
            "within a company. Buildings lives include offices.",
            "Bankruptcy figures differ in scope (Global Crossing's $250m bought 61.5% of the company; Velocita's "
            "$37m bought the network only); 'bought later' prices include new investment since.",
            "NVIDIA's multiples are vendor marketing claims on its own chosen workloads.",
        ],
        by_visual=by_visual,
        extra={
            "pct_last": {k: v["pct_of_first"] for k, v in pct.items()},
            "capacity_multiple": cap1 / cap0,
        },
    )


def table(story: Story) -> pl.DataFrame:
    p = story.frames["prices"]
    return p.select("series", "day", pl.col("price").round(2), pl.col("pct_of_first").round(1), "unit", "entity")
