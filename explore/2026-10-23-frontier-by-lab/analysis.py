"""Frontier by lab: the best model so far from Anthropic, OpenAI, Google and Meta, and the best open-weight model
from anyone, on the Artificial Analysis Intelligence Index and on Terminal-Bench 4.0 (as run by AA).

Reads marts only (aa_models, aa_evals). Open-weight status is tagged per model (open_weights.yaml). See README.md
for method and caveats. `cachereg render explore/2026-10-23-frontier-by-lab` renders the visuals in explore.yaml.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import polars as pl
import yaml

from cachereg.core.warehouse import query
from cachereg.story.model import Story

HERE = Path(__file__).parent
OPEN = "Best open-weight"
LABS = ["Anthropic", "OpenAI", "Google", "Meta"]  # AA creator names
SERIES = [*LABS, OPEN]
II, TB = "artificial_analysis_intelligence_index", "terminalbench_v4_0"
METRICS = {  # AA eval key -> (y-axis title, multiplier to the plotted scale, visual name = key of config `start`)
    II: ("Intelligence Index", 1.0, "intelligence"),
    TB: ("% of tasks solved", 100.0, "terminal-bench"),
}
# AA creator name -> the lab as named on the charts (where AA uses a brand rather than the company)
LAB_NAMES = {"Kimi": "Moonshot", "Z AI": "Z.ai"}
TABLE_PERCENT_COLUMNS: list[str] = []


def short_name(name: str) -> str:
    """AA's variant name without the effort suffix: 'Claude Opus 5.5 (Max, Default Fallback)' -> 'Claude Opus 5.5'."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


def open_status(slug: str, creator: str, rules: dict) -> bool | None:
    if creator in rules["closed_creators"]:
        return False
    if creator in rules["open_prefixes"]:
        return slug.startswith(tuple(rules["open_prefixes"][creator]))
    s = rules["models"].get(slug)
    return None if s is None else s == "open"


def _scores(con, metric: str) -> pl.DataFrame:
    return query(
        con,
        """
        SELECT e.slug, m.name, m.creator_name AS creator, m.release_date, e.value
        FROM aa_evals e JOIN aa_models m USING (slug, fetch_id)
        WHERE e.metric = ?
        ORDER BY m.release_date, e.value DESC, e.slug
        """,
        [metric],
    )


def frontier(df: pl.DataFrame) -> list[dict]:
    """Steps of 'best released so far': one row each time the record is beaten (ties do not step)."""
    best, out = None, []
    for r in df.iter_rows(named=True):
        if best is None or r["value"] > best:
            best = r["value"]
            out.append(r)
    return out


def open_frontier(df: pl.DataFrame, rules: dict, start: date) -> list[dict]:
    """Best open-weight model so far; fails on any model that would set it but has no status (a new contender).

    Before ``start`` only the record held at ``start`` matters: models are checked from the top score down until
    the first open one, so older open/closed status is needed only above it.
    """
    best, out, unknown = None, [], []
    for r in df.filter(pl.col("release_date") < start).sort("value", descending=True).iter_rows(named=True):
        status = open_status(r["slug"], r["creator"], rules)
        if status is None:
            unknown.append(f"{r['slug']} ({r['creator']}, {r['release_date']}, {r['value']:.3g})")
        elif status:
            best = r["value"]
            out.append(r)
            break
    for r in df.filter(pl.col("release_date") >= start).iter_rows(named=True):
        if best is not None and r["value"] <= best:
            continue
        status = open_status(r["slug"], r["creator"], rules)
        if status is None:
            unknown.append(f"{r['slug']} ({r['creator']}, {r['release_date']}, {r['value']:.3g})")
        elif status:
            best = r["value"]
            out.append(r)
    if unknown:
        raise ValueError("open-weight status needed in open_weights.yaml for: " + "; ".join(unknown))
    return out


def build(con, as_of: date, cfg: dict) -> Story:
    rules = yaml.safe_load((HERE / "open_weights.yaml").read_text())
    snapshot = query(con, "SELECT DISTINCT snapshot_date FROM aa_models")["snapshot_date"][0]
    rows, latest = [], {}
    starts = {}
    for metric, (_, mult, visual) in METRICS.items():
        start = starts[metric] = date.fromisoformat(str(cfg["start"][visual]))
        df = _scores(con, metric)
        steps = {lab: frontier(df.filter(pl.col("creator") == lab)) for lab in LABS}
        steps[OPEN] = open_frontier(df, rules, start)
        for series, st in steps.items():
            if not st:
                raise ValueError(f"no {metric} score for {series} on or before {as_of}")
            # Carry the record held at the window's start in as the first point; later steps as released.
            before = [r for r in st if r["release_date"] < start]
            inside = [r for r in st if r["release_date"] >= start]
            pts = ([before[-1] | {"release_date": start, "carried": True}] if before else []) + inside
            for r in pts:
                rows.append(
                    {
                        "metric": metric,
                        "series": series,
                        "date": r["release_date"],
                        "score": r["value"] * mult,
                        "model": short_name(r["name"]),
                        "variant": r["name"],
                        "creator": r["creator"],
                        "lab": LAB_NAMES.get(r["creator"], r["creator"]),
                        "carried": bool(r.get("carried", False)),
                    }
                )
            lead = st[-1]
            latest[(metric, series)] = {"score": lead["value"] * mult, "model": short_name(lead["name"]),
                                        "creator": lead["creator"], "released": str(lead["release_date"])}  # fmt: skip
    steps_df = pl.DataFrame(rows).sort("metric", "series", "date")

    # Where the open-weight line stands among the five lines today, per metric.
    standing = {}
    for metric in METRICS:
        ranked = sorted(SERIES, key=lambda s: -latest[(metric, s)]["score"])
        leader = ranked[0]
        gap = latest[(metric, leader)]["score"] - latest[(metric, OPEN)]["score"]
        standing[metric] = {"rank": ranked.index(OPEN) + 1, "leader": leader, "gap": gap, "order": ranked}

    ii, tb = standing[II], standing[TB]
    lt = latest[(TB, OPEN)]
    # Headlines follow the data: where the open-weight line stands among the five lines today.
    if tb["rank"] == 1:
        tb_claim = f"An open-weight model now leads Terminal-Bench:\n{lt['model']} beats every big US lab's best"
    else:
        tb_claim = f"The best open-weight model is {tb['gap']:.1f} points behind\nthe leader on Terminal-Bench"
    if ii["rank"] == 1:
        ii_claim = "The best open-weight model now leads\nthe Artificial Analysis Intelligence Index"
    else:
        ii_claim = (
            f"The best open-weight model is {ii['gap']:.1f} points behind {ii['leader']}\n"
            f"on the Artificial Analysis Intelligence Index"
        )
    who = "Best model released so far by Anthropic, OpenAI, Google and Meta, and by anyone with open weights"
    measured = f"as measured by Artificial Analysis on {snapshot:%B %-d, %Y}"
    by_visual = {
        "intelligence": {"title": ii_claim, "subtitle": f"{who}; Intelligence Index {measured}."},
        "terminal-bench": {"title": tb_claim, "subtitle": f"{who}; Terminal-Bench 4.0, {measured}."},
    }
    return Story(
        title=ii_claim,
        subtitle=by_visual["intelligence"]["subtitle"],
        by_visual=by_visual,
        frames={"steps": steps_df},
        sources=["artificial_analysis"],
        as_of=as_of,
        method=(
            "one Artificial Analysis snapshot; each line is the best score among models released so far "
            "(best reasoning-effort variant), placed at AA's release date; open weights tagged per model"
        ),
        caveats=[
            "Today's scores placed at each model's release date: AA re-runs models and re-versions its "
            "index and evals, so this is not what the leaderboard showed at the time.",
            "Terminal-Bench 4.0 is new and hard: models from 2025 score near zero on it, so its chart starts in 2026.",
            "Open-weight status comes from our own tagging (open_weights.yaml), counted from the AA release "
            "date even where weights came days or weeks later. Kimi K3.1 Pro counts on announcement; its "
            "weights are promised by November 4, 2026.",
            "Terminal-Bench scores are AA's own runs (AA's harness), and differ from labs' self-reported "
            "figures and from the tbench.ai leaderboard, where agents are compared.",
            "Each lab's line is its single best model at each date, any size or price; Meta's line is "
            "from Meta Superintelligence Labs' closed Muse models since April 2026.",
        ],
        extra={
            "y_titles": {m: t for m, (t, _, _) in METRICS.items()},
            "series": SERIES,
            "start": {m: str(d) for m, d in starts.items()},
            "snapshot": str(snapshot),
            "latest": {f"{m}|{s}": v for (m, s), v in latest.items()},
            "standing": standing,
        },
    )


def table(story: Story) -> pl.DataFrame:
    """Every step of every line."""
    return story.frames["steps"].select("metric", "series", "date", "model", "variant", "lab", "score")
