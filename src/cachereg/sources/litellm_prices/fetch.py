"""Fetch LiteLLM's model price file as it stood at the end of each UTC day (git history, MIT).

1. A commits-only clone of upstream `main` lists the first-parent history (`first_parent.tsv`).
2. Each day in the window resolves to a commit (history.day_end_commits); the file at every commit
   not already stored by an earlier fetch is downloaded from raw.githubusercontent.com, kept as
   returned (gzip when the server compresses it).
Only complete UTC days are fetched, so a day's commit can never change after it is stored.
"""

from __future__ import annotations

import gzip
import json
import subprocess
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from cachereg.core import http
from cachereg.core.store import RawFetch, list_fetches
from cachereg.sources.litellm_prices.history import (
    BRANCH,
    FILE,
    FLOOR,
    LOOKBACK_DAYS,
    REPO,
    day_end_commits,
    parse_first_parent,
)

SOURCE = "litellm_prices"
ADAPTER_VERSION = "1"
RAW_URL = "https://raw.githubusercontent.com/BerriAI/litellm/{sha}/" + FILE
GIT_TIMEOUT = 600


def _git(*args: str, cwd: Path | None = None) -> str:
    """Run git with a fixed argv (no shell); stdout as text."""
    r = subprocess.run(  # noqa: S603 (fixed argv, no shell)
        ["git", *args],  # noqa: S607 (git from PATH is a documented requirement)
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {r.stderr.strip()[:500]}")
    return r.stdout


def list_first_parent(since: date) -> str:
    """First-parent history of upstream main since ``since`` (sha TAB committer epoch, newest first)."""
    with tempfile.TemporaryDirectory(prefix="cachereg-litellm-") as tmp:
        repo = Path(tmp) / "litellm.git"
        _git("clone", "--quiet", "--bare", "--filter=tree:0", "--single-branch", "--branch", BRANCH, REPO, str(repo))
        return _git("log", "--first-parent", "--format=%H%x09%ct", f"--since={since.isoformat()}", BRANCH, cwd=repo)


def stored_shas() -> set[str]:
    """Commits whose price file is already in the raw store."""
    out = set()
    for f in list_fetches(SOURCE):
        for name in f.manifest["files"]:
            if name.startswith("prices_"):
                out.add(name.removeprefix("prices_").split(".")[0])
    return out


def covered_until() -> date | None:
    ends = [(f.manifest.get("vintage") or {}).get("window", [None, None])[1] for f in list_fetches(SOURCE)]
    ends = [date.fromisoformat(e) for e in ends if e]
    return max(ends) if ends else None


def plan_window(today: date, full: bool) -> tuple[date, date]:
    end = today - timedelta(days=1)  # most recent complete UTC day
    last = None if full else covered_until()
    start = FLOOR if last is None else last + timedelta(days=1)
    return start, end


def _decode(body: bytes) -> dict:
    data = json.loads(gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body)
    if not isinstance(data, dict):
        raise ValueError("price file is not a JSON object")
    return data


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    today = today or datetime.now(UTC).date()
    start, end = plan_window(today, full)
    listing = list_first_parent(FLOOR - timedelta(days=LOOKBACK_DAYS))
    first_parent = parse_first_parent(listing)
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    raw.add("first_parent.tsv", listing.encode(), REPO, 200)
    days = day_end_commits(first_parent, FLOOR, end)  # always from FLOOR: proves the listing is complete
    have = set() if full else stored_shas()
    wanted = sorted({sha for d, (sha, _) in days.items() if d >= start} - have)
    for sha in wanted:
        resp = http.get(RAW_URL.format(sha=sha), headers={"Accept-Encoding": "gzip"})
        _decode(resp.body)  # validate before storing
        suffix = ".json.gz" if resp.body[:2] == b"\x1f\x8b" else ".json"
        raw.add(f"prices_{sha}{suffix}", resp.body, resp.url, resp.status)
    last_sha = days[end][0] if end >= FLOOR else None
    # A repeat fetch on the same day adds no days; its window is then just the last complete day.
    window = [min(start, end).isoformat(), end.isoformat()]
    raw.vintage = {"kind": "git_commit", "value": last_sha, "window": window}
    return raw
