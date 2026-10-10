"""Developer wallet vs enterprise wallet: three separately labelled lenses on the same AI labs (exploration).

Reads marts 091 (gateway_lenses), 080 (disclosures), 010 (or_model_daily, for the unpriced-token check
only) and dim_vendor_alias (display names); never cachereg.sources. See README.md for method and
docs/plans/2026-10-09-wallet-lenses.md for the design and the author's decisions.
`cachereg render explore/2026-10-09-wallet-lenses` renders the visuals declared in explore.yaml.

The lenses measure different things in different populations: they are never put on one axis, never
converted into each other and never turned into ratios or differences. Only the *order* of two labs within
a lens is compared across lenses (pairwise "settled" orders among the labs Ramp names); the run-rate lens
is a separate view with no ranking claim.
"""

from __future__ import annotations

import itertools
from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

VERCEL, OPENROUTER, RAMP = "vercel_spend", "openrouter_est_spend", "ramp_paying"
MAIN = [VERCEL, OPENROUTER, RAMP]  # the compared lenses: developer gateways (1) and enterprise adoption (2)
GATEWAYS = [VERCEL, OPENROUTER]
CONTEXT = ["vercel_tokens", "openrouter_tokens"]  # lens 1's token shares, context only
SENSITIVITY = ["openrouter_tokens_volume_weighted"]
RUN_RATE_METRICS = ["revenue_run_rate", "revenue_monthly"]


def _month(value) -> date:
    if isinstance(value, date):
        return value.replace(day=1)
    y, m = str(value).split("-")[:2]
    return date(int(y), int(m), 1)


def _add_months(d: date, n: int) -> date:
    k = d.year * 12 + d.month - 1 + n
    return date(k // 12, k % 12 + 1, 1)


def _period(end: date, span: bool) -> str:
    """'for 2025' for a figure that spans a year, else 'May 2026'."""
    return f"for {end.year}" if span else f"{end:%B %Y}"


def ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh"}.get(n, f"#{n}")


# ---- lenses -----------------------------------------------------------------------------------


def load_lenses(con, start: date) -> pl.DataFrame:
    """Mart 091 rows from `start`, with canonical vendor names and a partial-month flag."""
    df = query(
        con,
        """
        SELECT g.month, g.lens, g.vendor_id, n.vendor_name, g.label, g.value_pct, g.vendor_rank AS rank_all,
               g.days, g.period_days, g.coverage_pct
        FROM gateway_lenses g
        LEFT JOIN (SELECT vendor_id, any_value(vendor_name) AS vendor_name FROM dim_vendor_alias GROUP BY 1) n
            USING (vendor_id)
        WHERE g.month >= ? AND g.lens IN (SELECT unnest(?))
        ORDER BY g.month, g.lens, g.vendor_id
        """,
        [start, [*MAIN, *CONTEXT, *SENSITIVITY]],
    )
    return df.with_columns(
        vendor_name=pl.coalesce("vendor_name", "label", "vendor_id"),
        named=~pl.col("vendor_id").str.starts_with("_"),
        partial=pl.col("days").is_not_null() & (pl.col("days") < pl.col("period_days")),
    )


def complete_months(lenses: pl.DataFrame, lens: str) -> set[date]:
    """Months where `lens` has rows and none of them is partial (Ramp has no partial months)."""
    m = lenses.filter(pl.col("lens") == lens).group_by("month").agg(partial=pl.col("partial").any())
    return set(m.filter(~pl.col("partial"))["month"])


def headline_month(lenses: pl.DataFrame, cfg: dict) -> date:
    """Latest month where every compared lens is complete (config `headline_month`: latest or YYYY-MM)."""
    months = set.intersection(*(complete_months(lenses, lens) for lens in MAIN))
    if not months:
        raise ValueError("no month where Vercel spend, OpenRouter est. spend and Ramp paying are all complete")
    want = cfg.get("headline_month", "latest")
    if want == "latest":
        return max(months)
    m = _month(want)
    if m not in months:
        raise ValueError(f"headline_month {want}: not a month all three compared lenses cover in full")
    return m


def settle_window(lenses: pl.DataFrame, month: date, n: int) -> list[date]:
    """The n months ending at the headline month; each must be complete in every compared lens."""
    window = [_add_months(month, -k) for k in range(n - 1, -1, -1)]
    for lens in MAIN:
        missing = set(window) - complete_months(lenses, lens)
        if missing:
            raise ValueError(f"settle window: {lens} lacks complete months {sorted(map(str, missing))}")
    return window


def ramp_labs(lenses: pl.DataFrame, month: date) -> list[str]:
    """The named labs Ramp reports in the headline month, in Ramp's order (the common set)."""
    r = lenses.filter((pl.col("lens") == RAMP) & (pl.col("month") == month) & pl.col("named"))
    return r.sort("value_pct", descending=True)["vendor_id"].to_list()


def with_ranks(lenses: pl.DataFrame, labs: list[str]) -> pl.DataFrame:
    """Add `rank_six` (rank among Ramp's labs, per month and lens; ties share the lowest rank) and `in_ramp`."""
    six = lenses.filter(pl.col("vendor_id").is_in(labs)).with_columns(
        rank_six=pl.col("value_pct").rank("min", descending=True).over("month", "lens").cast(pl.Int64)
    )
    return lenses.join(
        six.select("month", "lens", "vendor_id", "rank_six"), on=["month", "lens", "vendor_id"], how="left"
    ).with_columns(in_ramp=pl.col("vendor_id").is_in(labs))


# ---- pairwise orders ---------------------------------------------------------------------------


def order(va: float | None, vb: float | None, floor: float) -> str:
    """One lens-month: `>`/`<`, `tie`, `unranked` (both under the floor) or `absent` (a lab has no row)."""
    if va is None or vb is None:
        return "absent"
    if va < floor and vb < floor:
        return "unranked"
    if va == vb:
        return "tie"
    return ">" if va > vb else "<"


def pair_history(lenses: pl.DataFrame, labs: list[str], months: list[date], floor: float) -> pl.DataFrame:
    """Per month, pair (in Ramp's order) and compared lens: the order of the two labs."""
    v = {
        (r["month"], r["lens"], r["vendor_id"]): r["value_pct"]
        for r in lenses.filter(pl.col("lens").is_in(MAIN) & pl.col("vendor_id").is_in(labs)).iter_rows(named=True)
    }
    present = {(m, lens) for (m, lens, _) in v}
    rows = []
    for a, b in itertools.combinations(labs, 2):
        for lens in MAIN:
            for m in months:
                if (m, lens) not in present:
                    continue  # the lens does not cover this month at all (e.g. Ramp after its last month)
                rows.append(
                    {
                        "a": a,
                        "b": b,
                        "lens": lens,
                        "month": m,
                        "order": order(v.get((m, lens, a)), v.get((m, lens, b)), floor),
                    }
                )
    return pl.DataFrame(rows)


def settled(orders: list[str]) -> str:
    """Over the window: the order when the same `>`/`<` holds every month; `unranked` when any month is
    unranked or absent; otherwise `unsettled` (a flip or a tie)."""
    if any(o in ("unranked", "absent") for o in orders):
        return "unranked"
    return orders[0] if len(set(orders)) == 1 and orders[0] in (">", "<") else "unsettled"


def status(by_lens: dict[str, str], lenses: list[str]) -> str:
    """`agree` / `disagree` / `unsettled` over the ranked lenses, or `not comparable`.

    Developer vs enterprise (lenses = MAIN): comparable only when ranked on Ramp and on at least one gateway.
    Gateway vs gateway (lenses = GATEWAYS): comparable only when ranked on both.
    """
    ranked = {k: o for k, o in by_lens.items() if k in lenses and o != "unranked"}
    if lenses == MAIN:
        comparable = RAMP in ranked and any(g in ranked for g in GATEWAYS)
    else:
        comparable = len(ranked) == len(lenses)
    if not comparable:
        return "not comparable"
    vals = set(ranked.values())
    if {">", "<"} <= vals:
        return "disagree"
    return "unsettled" if "unsettled" in vals else "agree"


def pairs(history: pl.DataFrame, window: list[date]) -> pl.DataFrame:
    """Per pair: the settled order in each compared lens over the window, and the two statuses."""
    h = history.filter(pl.col("month").is_in(window)).sort("month")
    rows = []
    for (a, b), g in h.group_by(["a", "b"], maintain_order=True):
        by_lens = {lens: settled(g.filter(pl.col("lens") == lens)["order"].to_list()) for lens in MAIN}
        rows.append(
            {"a": a, "b": b, **by_lens, "status": status(by_lens, MAIN), "gateways_status": status(by_lens, GATEWAYS)}
        )
    return pl.DataFrame(rows)


def rank_correlation(lenses: pl.DataFrame, labs: list[str], months: list[date]) -> pl.DataFrame:
    """Spearman ρ across Ramp's labs between Ramp and each gateway, per month (context only: with six labs,
    two near zero everywhere, ρ mostly says the tail is last everywhere). A lab missing from a lens counts 0."""
    six = lenses.filter(pl.col("vendor_id").is_in(labs) & pl.col("lens").is_in(MAIN) & pl.col("month").is_in(months))
    grid = pl.DataFrame({"vendor_id": labs}).join(pl.DataFrame({"month": months}), how="cross")
    rows = []
    for lens in GATEWAYS:
        w = grid.join(
            six.filter(pl.col("lens") == lens).select("month", "vendor_id", g=pl.col("value_pct")),
            on=["month", "vendor_id"],
            how="left",
        ).join(
            six.filter(pl.col("lens") == RAMP).select("month", "vendor_id", r=pl.col("value_pct")),
            on=["month", "vendor_id"],
            how="left",
        )
        for (m,), d in w.group_by("month"):
            if d["r"].is_null().all():
                continue
            d = d.fill_null(0.0)
            rho = d.select(pl.corr(pl.col("g").rank(), pl.col("r").rank())).item()
            rows.append({"month": m, "lens": lens, "spearman": rho})
    return pl.DataFrame(rows).sort("month", "lens")


# ---- leaders over time ------------------------------------------------------------------------


def leaders(lenses: pl.DataFrame) -> pl.DataFrame:
    """Per compared lens: the leading lab (rank among named vendors; for Ramp, among its labs) in its latest
    complete month, and the first month of that lab's unbroken run in first place."""
    rows = []
    for lens in MAIN:
        done = sorted(complete_months(lenses, lens))
        first = (
            lenses.filter((pl.col("lens") == lens) & pl.col("named") & pl.col("month").is_in(done))
            .sort("value_pct", descending=True)
            .group_by("month", maintain_order=True)
            .first()
            .sort("month")
        )
        lead = first["vendor_id"][-1]
        since = first["month"][-1]
        for m, v in zip(reversed(first["month"].to_list()), reversed(first["vendor_id"].to_list()), strict=True):
            if v != lead:
                break
            since = m
        rows.append({"lens": lens, "leader": lead, "since": since, "through": done[-1], "window_start": done[0]})
    return pl.DataFrame(rows)


# ---- lens 3: run-rates -----------------------------------------------------------------------


def money(value: float, qualifier: str) -> str:
    """A short label for a stated dollar figure, keeping the qualifier ("$47B+", "~$9B")."""
    b = value / 1e9
    s = f"${b:g}B"
    return {"over": s + "+", "about": "~" + s, "under": "nearly " + s, "up_to": "up to " + s}.get(qualifier, s)


def run_rates(con) -> pl.DataFrame:
    """Revenue run-rate statements (and OpenAI's monthly revenue figure, never annualised), without quotes or URLs."""
    df = query(
        con,
        """
        SELECT d.vendor_id, d.vendor_name, d.metric, d.value, d.unit, d.qualifier, d.value_as_stated,
               d.period_start, d.period_end, d.statement_date, d.source_kind, d.scope
        FROM disclosures d
        WHERE d.metric IN (SELECT unnest(?))
        ORDER BY d.vendor_id, d.period_end, d.statement_date
        """,
        [RUN_RATE_METRICS],
    )
    return df.with_columns(
        plotted=pl.col("metric") == "revenue_run_rate",
        span=pl.col("period_end") > pl.col("period_start") + pl.duration(days=31),  # a year figure: no point in time
        label=pl.struct("value", "qualifier").map_elements(
            lambda r: money(r["value"], r["qualifier"]), return_dtype=pl.String
        ),
    )


# ---- checks ---------------------------------------------------------------------------------


def checks(con, lenses: pl.DataFrame, labs: list[str], window: list[date], month: date) -> pl.DataFrame:
    """One row per check. The analysis stops if any of Ramp's labs holds > 1% of OpenRouter's unpriced
    tokens in the window (then pricing them would change the labs' order, not rescale them together)."""
    lo, hi = window[0], _add_months(window[-1], 1)
    unpriced = query(
        con,
        """
        SELECT vendor_id, 100.0 * sum(total_tokens) / sum(sum(total_tokens)) OVER () AS pct
        FROM or_model_daily
        WHERE NOT is_free AND NOT price_matched AND date >= ? AND date < ?
        GROUP BY vendor_id
        """,
        [lo, hi],
    )
    six_unpriced = unpriced.filter(pl.col("vendor_id").is_in(labs))["pct"].sum()
    if six_unpriced > 1.0:
        raise ValueError(
            f"Ramp's labs hold {six_unpriced:.1f}% of OpenRouter's unpriced tokens: the est. spend order is not robust"
        )
    cov = (
        lenses.filter((pl.col("lens") == OPENROUTER) & pl.col("month").is_in(window))
        .group_by("month")
        .agg(pl.col("coverage_pct").first())
    )
    unm = lenses.filter(
        (pl.col("month") == month) & (pl.col("vendor_id") == "_unmapped") & pl.col("lens").is_in(GATEWAYS)
    )
    dropped = lenses.filter(pl.col("partial")).select("lens", "month").unique()
    top_unpriced = unpriced.sort("pct", descending=True).head(3)
    return pl.DataFrame(
        [
            {
                "headline_month": month,
                "settle_window": f"{window[0]:%Y-%m} → {window[-1]:%Y-%m}",
                "ramp_labs": ", ".join(labs),
                "openrouter_coverage_pct_min": cov["coverage_pct"].min(),
                "openrouter_coverage_pct_max": cov["coverage_pct"].max(),
                "unpriced_tokens_pct_in_ramp_labs": six_unpriced,
                "unpriced_tokens_top": ", ".join(f"{v} {p:.0f}%" for v, p in top_unpriced.iter_rows()),
                "unmapped_pct_vercel_spend": unm.filter(pl.col("lens") == VERCEL)["value_pct"].sum(),
                "unmapped_pct_openrouter_est_spend": unm.filter(pl.col("lens") == OPENROUTER)["value_pct"].sum(),
                "partial_months_dropped": ", ".join(
                    sorted({f"{r['lens']} {r['month']:%Y-%m}" for r in dropped.iter_rows(named=True)})
                ),
            }
        ]
    )


# ---- story -----------------------------------------------------------------------------------


def build(con, as_of: date, cfg: dict) -> Story:
    start = _month(cfg.get("start", "2025-10-01"))
    floor = float(cfg.get("floor_pct", 1.0))
    n_settle = int(cfg.get("settle_months", 3))
    min_gw = float(cfg.get("not_reported_min_pct", 3.0))

    raw = load_lenses(con, start)
    month = headline_month(raw, cfg)
    window = settle_window(raw, month, n_settle)
    labs = ramp_labs(raw, month)
    lenses = with_ranks(raw, labs)
    names = dict(lenses.select("vendor_id", "vendor_name").unique("vendor_id").iter_rows())

    common = sorted(set.intersection(*(complete_months(lenses, lens) for lens in MAIN)))
    complete = lenses.filter(~pl.col("partial"))  # partial months are never ordered
    hist = pair_history(complete, labs, sorted(set(complete.filter(pl.col("lens").is_in(MAIN))["month"])), floor)
    pr = pairs(hist, window)
    rr = run_rates(con)

    at = lenses.filter(pl.col("month") == month)
    gw_spend = at.filter(pl.col("lens").is_in(GATEWAYS) & pl.col("named") & ~pl.col("in_ramp"))
    not_reported = (
        gw_spend.group_by("vendor_id")
        .agg(pl.col("value_pct").max())
        .filter(pl.col("value_pct") >= min_gw)
        .sort("value_pct", descending=True)["vendor_id"]
        .to_list()
    )
    gw_all = at.filter(pl.col("lens").is_in([*GATEWAYS, *CONTEXT]) & pl.col("named"))
    token_rows = (
        gw_all.group_by("vendor_id")
        .agg(pl.col("value_pct").max())
        .filter(pl.col("value_pct") >= min_gw)["vendor_id"]
        .to_list()
    )
    vercel_order = at.filter(pl.col("lens") == VERCEL).sort("value_pct", descending=True)["vendor_id"].to_list()
    token_rows = [v for v in vercel_order if v in token_rows] + [v for v in token_rows if v not in vercel_order]

    ld = leaders(lenses)
    frames = {
        "lenses": lenses,
        "pairs": pr,
        "pair_history": hist,
        "rank_correlation": rank_correlation(lenses, labs, common),
        "leaders": ld,
        "run_rates": rr,
        "checks": checks(con, lenses, labs, window, month),
    }

    mon = f"{month:%B %Y}"
    win = f"{window[0]:%B}–{window[-1]:%B %Y}"
    agree = pr.filter(pl.col("status") == "agree").height
    split = pr.filter(pl.col("status") == "disagree")
    top3 = {
        lens: at.filter((pl.col("lens") == lens) & pl.col("in_ramp")).sort("rank_six").head(3)["vendor_id"].to_list()
        for lens in MAIN
    }
    same_top = len({frozenset(v) for v in top3.values()}) == 1

    def who(v: str) -> str:
        return names.get(v, v)

    if same_top and split.height:
        pair_txt = "; ".join(f"{who(a)} and {who(b)}" for a, b in split.select("a", "b").iter_rows())
        title = f"Developer gateways and Ramp's businesses put the same three AI labs on top; they split on {pair_txt}"
    elif same_top:
        title = (
            "Developer gateways and Ramp's businesses put the same three AI labs on top, "
            "and agree on every settled pair"
        )
    else:
        title = "Where developer gateways and Ramp's businesses agree, and split, on AI labs"
    subtitle = (
        f"{mon}. Three measures of three populations, each in its own panel; only the order of labs is compared. "
        f"Ranks among the {len(labs)} labs Ramp reports. Highlighted: an order that differs between lenses in every "
        f"month {win}."
    )
    notes = [
        f"{agree} of {pr.height} pairs of Ramp's labs keep one order in all three lenses, {win}. "
        f"Under {floor:g}%: no rank shown. Not reported: Ramp does not list the lab.",
    ]

    by_visual: dict[str, dict] = {}
    lv = {r["lens"]: r for r in ld.iter_rows(named=True)}
    gw_lead = {lv[g]["leader"] for g in GATEWAYS}
    if len(gw_lead) == 1 and lv[RAMP]["leader"] in gw_lead:
        lead = who(lv[RAMP]["leader"])
        g_since = max(lv[g]["since"] for g in GATEWAYS)
        g_txt = (
            f"in every month since {g_since:%B %Y}"
            if all(lv[g]["since"] == lv[g]["window_start"] for g in GATEWAYS)
            else f"since {g_since:%B %Y}"
        )
        r_since = f"{lv[RAMP]['since']:%B %Y}"
        lt = f"Both gateways have put {lead} first in spend {g_txt}; Ramp's businesses only since {r_since}"
    else:
        lt = "Which lab leads each lens, month by month"
    by_visual["leaders"] = {
        "title": lt,
        "subtitle": (
            "Monthly. Each panel its own measure and scale. Gateways: means of daily shares; Ramp: share of "
            "businesses on Ramp paying the lab."
        ),
        "notes": ["Partial months are not drawn."],
    }

    tok = {}
    for g, t in zip(GATEWAYS, CONTEXT, strict=True):
        top_t = at.filter((pl.col("lens") == t) & pl.col("named")).sort("value_pct", descending=True)["vendor_id"][0]
        tok[g] = top_t
    if len(set(tok.values())) == 1:
        lab = next(iter(tok.values()))
        sr = [at.filter((pl.col("lens") == g) & (pl.col("vendor_id") == lab))["rank_all"][0] for g in GATEWAYS]
        sr_txt = (
            f"{ordinal(sr[0])} in spend on both"
            if sr[0] == sr[1]
            else f"{ordinal(sr[0])} and {ordinal(sr[1])} in spend"
        )
        tt = f"{who(lab)} carries the most tokens on both developer gateways, but ranks {sr_txt}"
    else:
        tt = "Token share and spend share on two developer gateways"
    by_visual["tokens-spend"] = {
        "title": tt,
        "subtitle": (
            f"{mon}. Each panel its own measure; ranks among all named labs on that gateway. Spend is tokens × price, "
            "so labs with cheap models rank lower in spend than in tokens."
        ),
        "notes": ["Tokens are counted by each provider's tokenizer. OpenRouter spend: list prices, caching ignored."],
    }

    plotted = rr.filter(pl.col("plotted"))
    last = plotted.sort("period_end").group_by("vendor_id", maintain_order=True).last().sort("vendor_name")
    parts = [
        f"{r['vendor_name']} {r['label']} ({_period(r['period_end'], r['span'])})" for r in last.iter_rows(named=True)
    ]
    by_visual["run-rates"] = {
        "title": "The labs' stated revenue run-rates for their most recent periods: "
        + (", ".join(parts) if parts else "none"),
        "subtitle": (
            "Revenue run-rate or ARR as each company stated it, by the period it describes. Self-reported and "
            "unaudited; definitions differ between the companies. Company-wide revenue (subscriptions included), not "
            "developer or business spending."
        ),
        "notes": [
            "Sources: Anthropic news posts (2025–26); OpenAI CFO post (Jan 2026); CNBC (Jun 2025, secondary). "
            'OpenAI\'s "$2B in revenue per month" (Mar 2026) is a different measure and is not annualised.',
        ],
    }

    return Story(
        title=title,
        subtitle=subtitle,
        frames=frames,
        sources=["vercel_ai_gateway", "openrouter_rankings", "litellm_prices", "ramp_ai_index", "curated_disclosures"],
        as_of=as_of,
        method=(
            f"Lenses never combined; a pair's order counts only if it holds in each of the {n_settle} months to {mon}"
        ),
        notes=notes,
        caveats=[
            "Three populations and measures: Vercel's measured gateway spend; Cache Register's list-price estimate of "
            "OpenRouter spend (caching ignored); the share of businesses on Ramp paying the lab (a seat counts like a "
            "contract; cloud-marketplace purchases invisible); company-stated revenue run-rates.",
            "Ranks, not levels: no value, gap or ratio is compared across lenses.",
            "Ramp reports six labs; others are not reported, not zero. Ramp and both gateways are Latest-only.",
        ],
        extra={
            "month": str(month),
            "window": [str(m) for m in window],
            "labs": labs,
            "not_reported": not_reported,
            "token_rows": token_rows,
            "floor_pct": floor,
            "start": str(start),
        },
        by_visual=by_visual,
    )
