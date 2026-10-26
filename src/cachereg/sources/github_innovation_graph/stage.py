"""Stage every stored Innovation Graph release into one long table (release × economy × quarter)."""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.store import list_fetches
from cachereg.sources.github_innovation_graph.fetch import SOURCE, parse_commits
from cachereg.sources.github_innovation_graph.files import AGGREGATES, FILES, parse, release_name


def releases() -> dict[str, date]:
    """Release commit → its date, from every stored listing (a commit never changes date)."""
    out = {}
    for f in list_fetches(SOURCE):
        if "commits.json" in f.manifest["files"]:
            out.update(dict(parse_commits(f.read("commits.json"))))
    return out


def vintage_at(as_of: date) -> dict | None:
    """The source revision used for ``as_of`` (PLAN §4.4): the newest release committed on or before it."""
    known = [(d, sha) for sha, d in releases().items() if d <= as_of]
    if not known:
        return None
    d, sha = max(known)
    return {"kind": "git_commit", "value": sha, "date": d.isoformat()}


def stage() -> dict[str, pl.DataFrame]:
    rel = releases()
    stored = {}
    for f in list_fetches(SOURCE):
        for name in f.manifest["files"]:
            stored[name] = f
    rows = []
    for sha, released in sorted(rel.items(), key=lambda x: x[1]):
        for name in FILES:
            fname = release_name(name, sha)
            if fname not in stored:
                raise ValueError(f"{SOURCE}: release {sha[:10]} ({released}) has no stored {name}; re-fetch")
            metric = name.removesuffix(".csv")
            for economy, year, quarter, value in parse(stored[fname].read(fname), name):
                rows.append((sha, released, economy, economy in AGGREGATES, year, quarter, metric, value))
    schema = {
        "release_sha": pl.String,
        "release_date": pl.Date,
        "economy": pl.String,
        "is_aggregate": pl.Boolean,
        "year": pl.Int32,
        "quarter": pl.Int32,
        "metric": pl.String,
        "value": pl.Int64,
    }
    listing = sorted(rel.items(), key=lambda x: x[1])
    return {
        "quarterly": pl.DataFrame(rows, schema=schema, orient="row"),
        "releases": pl.DataFrame(listing, schema={"release_sha": pl.String, "release_date": pl.Date}, orient="row"),
    }
