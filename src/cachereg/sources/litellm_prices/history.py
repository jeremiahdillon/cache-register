"""The day → commit rule shared by fetch and stage (PLAN §4.4, Exact class).

The price state of day D is the file at the newest first-parent commit of upstream `main` whose
committer time is on or before D 23:59:59 UTC. It depends only on upstream history, so the author
and a replicator who fetches later resolve the same commit for every past day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

REPO = "https://github.com/BerriAI/litellm.git"
BRANCH = "main"
FILE = "model_prices_and_context_window.json"
FLOOR = date(2025, 1, 1)  # first day staged; OpenRouter rankings history starts here too
LOOKBACK_DAYS = 30  # first_parent.tsv starts this long before FLOOR so FLOOR always resolves


def parse_first_parent(text: str) -> list[tuple[str, int]]:
    """`git log --first-parent --format=%H%x09%ct` output → [(sha, committer epoch)], newest first."""
    out = []
    for line in text.splitlines():
        if line.strip():
            sha, ct = line.split("\t")
            out.append((sha, int(ct)))
    return out


def day_end(d: date) -> int:
    return int(datetime.combine(d, time(23, 59, 59), tzinfo=UTC).timestamp())


def day_end_commits(first_parent: list[tuple[str, int]], start: date, end: date) -> dict[date, tuple[str, int]]:
    """For each day in [start, end]: the first commit in first-parent order with time ≤ day end.

    Raises if a day resolves to nothing (the listing does not reach back far enough).
    """
    out = {}
    d = start
    while d <= end:
        cutoff = day_end(d)
        hit = next(((sha, ct) for sha, ct in first_parent if ct <= cutoff), None)
        if hit is None:
            raise ValueError(f"first-parent history does not reach back to {d}")
        out[d] = hit
        d += timedelta(days=1)
    return out
