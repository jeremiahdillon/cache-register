"""Fetch the GitHub Innovation Graph data files at every release commit (CC0 1.0), kept as served.

Each quarterly release is a commit to github.com/github/innovationgraph that rewrites `data/*.csv`.
The commits that touched `data/git_pushes.csv` are listed from the GitHub API (no key); the files at
every release commit not already stored are downloaded from raw.githubusercontent.com at that commit,
so a stored release never changes. `commits.json` (the listing) is stored on every fetch.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta

from cachereg.core import http
from cachereg.core.store import RawFetch, list_fetches
from cachereg.sources.github_innovation_graph.files import FILES, parse, release_name

SOURCE = "github_innovation_graph"
ADAPTER_VERSION = "1"
REPO = "github/innovationgraph"
API = f"https://api.github.com/repos/{REPO}/commits"
RAW = f"https://raw.githubusercontent.com/{REPO}/{{sha}}/data/{{name}}"
PAUSE = 0.5  # seconds between downloads


def parse_commits(body: bytes) -> list[tuple[str, date]]:
    """(sha, committed date UTC) per release commit, oldest first."""
    data = json.loads(body)
    if not isinstance(data, list) or not data:
        raise ValueError("commits: not a non-empty JSON list")
    out = []
    for c in data:
        sha = c.get("sha") if isinstance(c, dict) else None
        when = ((c.get("commit") or {}).get("committer") or {}).get("date") if isinstance(c, dict) else None
        if not isinstance(sha, str) or len(sha) != 40 or not isinstance(when, str):
            raise ValueError("commits: an entry lacks a 40-character sha or a committer date")
        out.append((sha, datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone(UTC).date()))
    return sorted(out, key=lambda x: (x[1], x[0]))


def stored_shas() -> set[str]:
    out = set()
    for f in list_fetches(SOURCE):
        for name in f.manifest["files"]:
            if name.startswith(FILES[0].removesuffix(".csv") + "_"):
                out.add(name.rsplit("_", 1)[1].split(".")[0])
    return out


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    """`full` re-downloads every release; otherwise only releases not yet stored."""
    today = today or datetime.now(UTC).date()
    listing = http.get(
        API,
        params={"path": "data/git_pushes.csv", "per_page": "100"},
        headers={"Accept": "application/vnd.github+json"},
    )
    releases = parse_commits(listing.body)
    have = set() if full else stored_shas()
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    raw.add("commits.json", listing.body, listing.url, listing.status)
    new = [(sha, d) for sha, d in releases if sha not in have]
    for i, (sha, _) in enumerate(new):
        for j, name in enumerate(FILES):
            if i or j:
                time.sleep(PAUSE)
            resp = http.get(RAW.format(sha=sha, name=name), headers={"Accept": "text/csv, */*"})
            try:
                parse(resp.body, name)  # validate before storing
            except ValueError as e:
                raise ValueError(f"{name} at {sha[:10]}: {e}") from None
            raw.add(release_name(name, sha), resp.body, resp.url, resp.status)
    newest_sha, newest_day = releases[-1]
    raw.vintage = {
        "kind": "git_commit",
        "value": newest_sha,
        "date": newest_day.isoformat(),
        "window": [releases[0][1].isoformat(), (today - timedelta(days=1)).isoformat()],
        "new_releases": [sha for sha, _ in new],
    }
    return raw
