"""Two lenses on adoption: Ramp's paid AI adoption beside Census BTOS's self-reported AI use (exploration).

Reads marts 060 (ramp_adoption), 070 (btos_ai_use, btos_series_breaks, btos_revision_check), 071
(btos_ai_monthly) and 072 (adoption_two_lenses, btos_ramp_census_check); never cachereg.sources. See
README.md for method and docs/plans/2026-10-08-two-lenses-adoption.md for the design.
`cachereg render explore/2026-10-08-two-lenses-adoption` renders the visuals declared in explore.yaml.

The lenses measure different things and are never combined into one series, ratio or difference; the
two BTOS wordings are separate series (break at Nov 2025) and are never averaged, ranked or differenced
across. Config `ramp: false` (with `sources: [census_btos]`) is the BTOS-only fallback.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

RAMP, CUR, EXP = "ramp_paid", "btos_use_current", "btos_use_expected"
SIZE_LABELS = {"A": "1–4", "B": "5–9", "C": "10–19", "D": "20–49", "E": "50–99", "F": "100–249", "G": "250+"}
RAMP_SIZES = ["Small", "Medium", "Large"]


def _has_table(con, name: str) -> bool:
    return query(con, "SELECT count(*) AS n FROM information_schema.tables WHERE table_name = ?", [name])["n"][0] > 0


def _month(value) -> date:
    if isinstance(value, date):
        return value.replace(day=1)
    y, m = str(value).split("-")[:2]
    return date(int(y), int(m), 1)


def _add_months(d: date, n: int) -> date:
    k = d.year * 12 + d.month - 1 + n
    return date(k // 12, k % 12 + 1, 1)


def btos_monthly(con, breakdown: str) -> pl.DataFrame:
    """BTOS `yes` monthly series (mart 071) for one breakdown, both questions, both wordings."""
    return query(
        con,
        """
        SELECT month, wording, question, breakdown, naics, naics_title, size_class, pct, se,
               low90_pct AS low90, high90_pct AS high90, partial, has_suppression, n_suppressed, cycles
        FROM btos_ai_monthly WHERE breakdown = ? ORDER BY month
        """,
        [breakdown],
    )


def two_lenses(con) -> pl.DataFrame:
    """Mart 072, current use and paid adoption (plus expected use), with Ramp's sector labels."""
    t = query(
        con,
        """
        SELECT month, scope, naics, naics_title, naics_assumed, role, lens, wording, pct, se,
               low90_pct AS low90, high90_pct AS high90, partial, has_suppression
        FROM adoption_two_lenses ORDER BY month
        """,
    )
    labels = query(
        con,
        "SELECT DISTINCT naics, series_label AS label FROM ramp_adoption "
        "WHERE series_kind = 'sector' AND naics IS NOT NULL",
    )
    t = t.join(labels, on="naics", how="left").with_columns(
        label=pl.when(pl.col("scope") == "overall")
        .then(pl.lit("All businesses"))
        .when(pl.col("label").is_not_null())
        .then(pl.col("label") + pl.when(pl.col("naics_assumed")).then(pl.lit("*")).otherwise(pl.lit("")))
        .otherwise(pl.col("naics_title"))
    )
    return t


def headline_month(lenses: pl.DataFrame | None, national: pl.DataFrame, cfg: dict) -> date:
    """Latest month with Ramp overall and a complete (not partial) BTOS national current-use month."""
    want = cfg.get("headline_month", "latest")
    btos = national.filter((pl.col("question") == "ai_current") & ~pl.col("partial"))["month"]
    months = set(btos)
    if lenses is not None:
        months &= set(lenses.filter((pl.col("lens") == RAMP) & (pl.col("scope") == "overall"))["month"])
    if not months:
        raise ValueError("no month has both a Ramp value and a complete BTOS month")
    if want == "latest":
        return max(months)
    m = _month(want)
    if m not in months:
        raise ValueError(f"headline_month {want}: not a month both lenses cover in full")
    return m


def _ranked(df: pl.DataFrame) -> pl.DataFrame:
    """Rank (1 = highest) of the matched sectors per month and lens; ties share the average rank."""
    return df.with_columns(rank=pl.col("pct").rank("average", descending=True).over("month", "lens"))


def rank_agreement(lenses: pl.DataFrame) -> pl.DataFrame:
    """Spearman ρ between the two lenses' ranks of Ramp's sectors, per month (one BTOS wording per month)."""
    s = lenses.filter((pl.col("scope") == "sector") & (pl.col("role") == "matched") & pl.col("lens").is_in([RAMP, CUR]))
    wording = s.filter(pl.col("lens") == CUR).group_by("month").agg(wording=pl.col("wording").unique())
    if (wording["wording"].list.len() > 1).any():
        raise ValueError("a month holds both BTOS wordings; they must never be ranked together")
    n_all = s.filter(pl.col("lens") == RAMP)["naics"].n_unique()
    wide = (
        _ranked(s.filter(pl.col("pct").is_not_null()))
        .pivot(on="lens", index=["month", "naics", "label"], values="rank")
        .drop_nulls([RAMP, CUR])
    )
    rows = []
    for (month,), g in wide.group_by("month"):
        if g.height < n_all:
            continue  # a month where either lens lacks a sector is not compared
        d2 = ((g[RAMP] - g[CUR]) ** 2).sum()
        n = g.height
        differs = g.filter(pl.col(RAMP) != pl.col(CUR)).sort(RAMP)
        rows.append(
            {
                "month": month,
                "spearman": 1 - 6 * d2 / (n * (n * n - 1)),
                "n_sectors": n,
                "differs": ", ".join(
                    f"{lbl} {r:.0f}/{b:.0f}"
                    for lbl, r, b in zip(differs["label"], differs[RAMP], differs[CUR], strict=True)
                ),
            }
        )
    out = pl.DataFrame(rows).join(wording.with_columns(pl.col("wording").list.first()), on="month").sort("month")
    return out.select("month", "wording", "spearman", "n_sectors", "differs")


def levels(lenses: pl.DataFrame, month: date) -> pl.DataFrame:
    """Both lenses at the headline month: overall, the matched sectors (ranked), and BTOS 54 (sensitivity)."""
    at = lenses.filter((pl.col("month") == month) & pl.col("lens").is_in([RAMP, CUR]))
    ranked = _ranked(at.filter((pl.col("scope") == "sector") & (pl.col("role") == "matched")))
    rest = at.filter((pl.col("scope") == "overall") | (pl.col("role") != "matched")).with_columns(
        rank=pl.lit(None, pl.Float64)
    )
    out = pl.concat([ranked, rest]).select(
        "month", "scope", "naics", "label", "naics_assumed", "role", "lens", "wording", "pct", "low90", "high90", "rank"
    )
    rank_wide = ranked.pivot(on="lens", index="naics", values="rank")
    differs = rank_wide.filter(pl.col(RAMP) != pl.col(CUR))["naics"].to_list()
    return out.with_columns(rank_differs=pl.col("naics").is_in(differs)).sort("scope", "lens", "rank", nulls_last=True)


def trend(lenses: pl.DataFrame | None, national: pl.DataFrame) -> pl.DataFrame:
    """Monthly paid adoption and current use, overall and per sector, each BTOS wording its own segment."""
    if lenses is None:
        return national.filter(pl.col("question") == "ai_current").select(
            "month",
            pl.lit(CUR).alias("lens"),
            "wording",
            pl.lit("overall").alias("scope"),
            pl.lit(None, pl.String).alias("naics"),
            pl.lit("All businesses").alias("label"),
            "pct",
            "low90",
            "high90",
            "partial",
            "has_suppression",
        )
    return lenses.filter(pl.col("lens").is_in([RAMP, CUR])).select(
        "month", "lens", "wording", "scope", "naics", "label", "pct", "low90", "high90", "partial", "has_suppression"
    )


def sizes(con, size: pl.DataFrame, month: date, with_ramp: bool) -> pl.DataFrame:
    """BTOS's seven size classes (employee bounds from mart 070) and Ramp's three bands at the month."""
    bounds = query(
        con,
        "SELECT DISTINCT size_class, min_employees, max_employees FROM btos_ai_use WHERE size_class IS NOT NULL",
    )
    b = (
        size.filter((pl.col("month") == month) & (pl.col("question") == "ai_current"))
        .join(bounds, on="size_class", how="left")
        .with_columns(
            lens=pl.lit(CUR),
            size_label=pl.col("size_class").replace_strict(SIZE_LABELS),
            order=pl.col("size_class").replace_strict({k: i for i, k in enumerate(SIZE_LABELS)}),
        )
        .select(
            "lens",
            "size_class",
            "size_label",
            "order",
            "min_employees",
            "max_employees",
            "pct",
            "low90",
            "high90",
            "has_suppression",
        )
    )
    if not with_ramp:
        return b.sort("order")
    r = query(
        con,
        "SELECT series_label AS size_label, adoption_pct AS pct FROM ramp_adoption "
        "WHERE series_kind = 'size' AND month = ?",
        [month],
    ).with_columns(
        lens=pl.lit(RAMP),
        size_class=pl.lit(None, pl.String),
        order=pl.col("size_label").replace_strict({k: i for i, k in enumerate(RAMP_SIZES)}, default=len(RAMP_SIZES)),
        min_employees=pl.lit(None, pl.Int64),
        max_employees=pl.lit(None, pl.Int64),
        low90=pl.lit(None, pl.Float64),
        high90=pl.lit(None, pl.Float64),
        has_suppression=pl.lit(None, pl.Boolean),
    )
    return pl.concat([b, r.select(b.columns)], how="vertical_relaxed").sort("lens", "order")


def size_bound(
    con, lenses: pl.DataFrame | None, national: pl.DataFrame, size: pl.DataFrame, month: date
) -> pl.DataFrame:
    """Per group: BTOS's lowest and highest size class at the month (by value) beside the Ramp level.

    Any reweighting of BTOS's classes stays within [min, max], so a Ramp level above the max class's 90%
    upper bound cannot be reached by BTOS's size mix alone. Per sector the max class is not always 250+.
    """

    def ends(df: pl.DataFrame) -> dict:
        pub = df.filter(pl.col("pct").is_not_null())
        lo, hi = pub.sort("pct").row(0, named=True), pub.sort("pct").row(-1, named=True)
        return {
            "min_class": SIZE_LABELS[lo["size_class"]],
            "min_pct": lo["pct"],
            "max_class": SIZE_LABELS[hi["size_class"]],
            "max_pct": hi["pct"],
            "max_se": hi["se"],
            "max_high90": hi["high90"],
            "max_has_suppression": hi["has_suppression"],
        }

    ramp = (
        {}
        if lenses is None
        else {
            (r["naics"]): r["pct"]
            for r in lenses.filter((pl.col("month") == month) & (pl.col("lens") == RAMP)).iter_rows(named=True)
        }
    )
    nat = national.filter((pl.col("month") == month) & (pl.col("question") == "ai_current")).row(0, named=True)
    rows = [
        {
            "group": "All businesses",
            "naics": None,
            "btos_pct": nat["pct"],
            **ends(size.filter((pl.col("month") == month) & (pl.col("question") == "ai_current"))),
            "ramp_pct": ramp.get(None),
        }
    ]
    if lenses is not None:
        ss = btos_monthly(con, "sector_size").filter((pl.col("month") == month) & (pl.col("question") == "ai_current"))
        sectors = lenses.filter(
            (pl.col("month") == month)
            & (pl.col("lens") == CUR)
            & (pl.col("scope") == "sector")
            & (pl.col("role") == "matched")
        )
        for r in sectors.iter_rows(named=True):
            g = ss.filter(pl.col("naics") == r["naics"])
            if g.filter(pl.col("pct").is_not_null()).height:
                rows.append(
                    {
                        "group": r["label"],
                        "naics": r["naics"],
                        "btos_pct": r["pct"],
                        **ends(g),
                        "ramp_pct": ramp.get(r["naics"]),
                    }
                )
    out = pl.DataFrame(rows)
    return out.with_columns(
        ramp_above_btos_max=pl.col("ramp_pct") > pl.col("max_high90"),
        # Cache Register's derivations (README only): the Ramp level left above BTOS's highest class's
        # upper bound, and the most of the national level difference a size reweighting could close.
        residual_pp=pl.col("ramp_pct") - pl.col("max_high90"),
        max_closable_point=(pl.col("max_pct") - pl.col("btos_pct")) / (pl.col("ramp_pct") - pl.col("btos_pct")),
        max_closable_upper=(pl.col("max_high90") - pl.col("btos_pct")) / (pl.col("ramp_pct") - pl.col("btos_pct")),
    )


def expectations(monthly: pl.DataFrame) -> pl.DataFrame:
    """BTOS expected use at m beside current use at m+6, same group and wording, complete months only."""
    m = monthly.filter(~pl.col("partial"))
    exp = m.filter(pl.col("lens") == EXP).select("label", "wording", "month", pl.col("pct").alias("expected"))
    cur = m.filter(pl.col("lens") == CUR).select(
        "label", "wording", pl.col("month").alias("month_6"), pl.col("pct").alias("current_6")
    )
    pairs = exp.with_columns(
        month_6=pl.col("month").map_elements(lambda d: _add_months(d, 6), return_dtype=pl.Date)
    ).join(cur, on=["label", "wording", "month_6"])
    return pairs.with_columns(realised_minus_expected=pl.col("current_6") - pl.col("expected")).sort(
        "label", "wording", "month"
    )


def changes(tr: pl.DataFrame, base: date, month: date) -> pl.DataFrame:
    """Each lens's own change in pp from the first current-wording month to the headline month."""
    t = tr.filter(pl.col("month").is_in([base, month]) & ((pl.col("lens") == RAMP) | (pl.col("wording") == "current")))
    w = t.pivot(on="month", index=["label", "naics", "lens"], values="pct").rename(
        {str(base): "base_pct", str(month): "pct"}
    )
    return w.with_columns(change_pp=pl.col("pct") - pl.col("base_pct"), base_month=pl.lit(base), month=pl.lit(month))


def checks(con, with_ramp: bool) -> pl.DataFrame:
    row = {
        "btos_revision_rows": query(con, "SELECT count(*) AS n FROM btos_revision_check")["n"][0],
        "btos_last_cycle": query(con, "SELECT max(cycle) AS c FROM btos_ai_use WHERE breakdown = 'national'")["c"][0],
    }
    if with_ramp:
        c = query(con, "SELECT count(*) FILTER (WHERE agree) AS ok, count(agree) AS n FROM btos_ramp_census_check")
        row |= {
            "ramp_census_months_agree": c["ok"][0],
            "ramp_census_months": c["n"][0],
            "ramp_import": query(
                con, "SELECT max(imported_on) AS d FROM ramp_cut_coverage WHERE cut LIKE 'adoption/%'"
            )["d"][0],
        }
    return pl.DataFrame([row])


def build(con, as_of: date, cfg: dict) -> Story:
    with_ramp = bool(cfg.get("ramp", True))
    if with_ramp and not _has_table(con, "adoption_two_lenses"):
        raise ValueError(
            "mart 072 (adoption_two_lenses) is missing: import ramp_ai_index and build both sources, or use the "
            "BTOS-only fallback (config `ramp: false`, `sources: [census_btos]`, visuals trends and sizes)"
        )
    national, size = btos_monthly(con, "national"), btos_monthly(con, "size")
    lenses = two_lenses(con) if with_ramp else None
    month = headline_month(lenses, national, cfg)
    base = national.filter(pl.col("wording") == "current")["month"].min()  # first month of the new wording
    tr = trend(lenses, national)
    sz = sizes(con, size, month, with_ramp)
    sb = size_bound(con, lenses, national, size, month)
    frames = {"trend": tr, "sizes": sz, "size_bound": sb, "checks": checks(con, with_ramp)}
    nat_monthly = national.with_columns(
        lens=pl.when(pl.col("question") == "ai_current").then(pl.lit(CUR)).otherwise(pl.lit(EXP)),
        label=pl.lit("All businesses"),
    )
    if with_ramp:
        ra = rank_agreement(lenses)
        lv = levels(lenses, month)
        frames |= {
            "levels": lv,
            "rank_agreement": ra,
            "changes": changes(tr, base, month),
            "expectations": expectations(lenses.filter(pl.col("lens").is_in([CUR, EXP]))),
        }
    else:
        frames |= {"expectations": expectations(nat_monthly), "changes": changes(tr, base, month)}

    mon = f"{month:%B %Y}"
    nat_sb = sb.row(0, named=True)
    bands = sz.filter(pl.col("lens") == RAMP)
    ramp_def = "share of businesses on Ramp with AI spend in the month (cards and bill pay)"
    btos_def = (
        "share of U.S. employer businesses that used AI in any business function in the last two weeks "
        "(Census BTOS, 90% interval)"
    )
    by_visual: dict[str, dict] = {}
    if with_ramp:
        ra_m = ra.filter(pl.col("month") == month).row(0, named=True)
        title = "Ramp and the Census Bureau's survey rank sectors' AI adoption almost the same way"
        subtitle = (
            f"{mon}. Left: {ramp_def}. Right: {btos_def}. Rank agreement ρ = {ra_m['spearman']:.2f}; "
            f"{ra['spearman'].min():.2f}–{ra['spearman'].max():.2f} in every month since {ra['month'].min():%b %Y}. "
            "Highlighted: sectors the two rank differently."
        )
        notes = [
            '* Ramp\'s "Technology and media", taken as NAICS 51 (Information); '
            "BTOS 54 (professional services) shown in the README."
        ]
        by_visual["trends"] = {
            "title": "Both measures of business AI adoption have risen since the Census question changed",
            "subtitle": (
                "Monthly, each panel its own measure (not comparable across panels). The Census question's new "
                "wording (November 2025) started a new series, so the two wordings are drawn apart."
            ),
            "notes": ["Oct 2025: no BTOS data (government shutdown). Shaded: since the new wording."],
        }
        above_all = bands.height == len(RAMP_SIZES) and (bands["pct"] > nat_sb["max_high90"]).all()
        by_visual["sizes"] = {
            "title": (
                "Every Ramp size band is above the Census survey's largest size class"
                if above_all
                else "Ramp's size bands beside the Census survey's size classes"
            ),
            "subtitle": (
                f"{mon}. Left: {btos_def}, by employees. Right: {ramp_def}, by Ramp's size band. However BTOS's "
                f"classes are weighted, the result stays inside the band "
                f"({nat_sb['min_pct']:.0f}–{nat_sb['max_pct']:.0f}%), "
                "so its weighting by business count does not explain the difference on its own."
            ),
            "notes": ["Ramp does not publish the employee thresholds of its size bands."],
        }
    else:
        title = "U.S. businesses' self-reported AI use, by month and size class"
        subtitle = f"Through {mon}. {btos_def[0].upper() + btos_def[1:]}."
        notes = []
        by_visual["sizes"] = {
            "title": f"Businesses with {nat_sb['max_class']} employees report the most AI use ({mon})",
            "notes": [],
        }

    sources = ["ramp_ai_index", "census_btos"] if with_ramp else ["census_btos"]
    return Story(
        title=title,
        subtitle=subtitle,
        frames=frames,
        sources=sources,
        as_of=as_of,
        method=(
            "BTOS monthly values are Cache Register's day-weighted averages of Census biweekly estimates "
            "(not Census estimates); the lenses are shown side by side, never combined"
        ),
        notes=notes,
        caveats=[
            "Different questions and populations: Ramp observes paid AI spend by businesses on Ramp (early-adopter "
            "skew, free tools invisible); BTOS asks all U.S. employer businesses about use, weighted by firm count, "
            "with 'Do not know' in the denominator. Neither measures the other.",
            "The November 2025 BTOS wording change started a new series; the two wordings are never joined.",
            "Ramp revises past months (Latest-only); BTOS is Latest-only until revisions are ruled out.",
            "Ramp's size bands have no published thresholds; BTOS's business-count weights are not published.",
        ],
        extra={
            "month": str(month),
            "base_month": str(base),
            "ramp": with_ramp,
            "trend_start": str(cfg.get("trend_start", "2023-01-01")),
        },
        by_visual=by_visual,
    )
