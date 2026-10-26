# GitHub Innovation Graph (`github_innovation_graph`)

**Repository:** [github.com/github/innovationgraph](https://github.com/github/innovationgraph)
(datasheet: `docs/datasheet.md`); files `data/git_pushes.csv` and `data/developers.csv`.
**API:** `https://api.github.com/repos/github/innovationgraph/commits?path=data/git_pushes.csv` lists the
release commits; files are read from `https://raw.githubusercontent.com/github/innovationgraph/<sha>/data/<file>`.
**License:** CC0 1.0 (repository `LICENSE.md`: "This project is released under CC0-1.0").
**Attribution:** "GitHub Innovation Graph (github.com/github/innovationgraph), CC0 1.0, as of {as_of}"
(not required by CC0; given anyway).
**Auth:** none (the unauthenticated GitHub API allows 60 requests an hour; a fetch makes one).
**Last verified:** 2026-10-26

## What it contains
Quarterly figures per economy (ISO 3166 two-letter codes, plus `EU`, an aggregate) from 2020 Q1:
- `git_pushes`: pushes to GitHub by developers located in the economy during the quarter (a push may
  hold many commits; edits made on github.com are pushes).
- `developers`: developer accounts located in the economy at the end of the quarter (active or not).
The repository also has organisations, repositories, languages, licences, topics and economy
collaborators; this source keeps only the two files above.

## Classification
- history: native · revisions: none → **Exact**: a release is a commit and never changes; a fetch
  stores the files at every release commit it has not stored, and the mart uses the newest release
  committed on or before as-of (`stage.vintage_at`).
- redistribution: allowed · derived_charts: allowed (CC0).

## Vintage rule
`vintage = {kind: git_commit, value: <newest release sha>, date: <its commit date>, window: [<first
release date>, <fetch date − 1>], new_releases: [...]}`.

## Fetch strategy
One API request for the release list (stored as `commits.json` on every fetch), then both files at
each new release commit, validated (header, integer values, two-letter codes, no duplicate economy
quarter) before storing as `git_pushes_<sha>.csv` / `developers_<sha>.csv`. Weekly: releases are
quarterly, three to four months after the quarter ends (2026 Q1 on 2026-07-07).

## Known quirks and caveats
- **Public activity only**: private repositories are out of scope, so company work is under-counted
  and hobby and open-source work over-weighted; seasonal patterns can differ from paid engineering
  (e.g. October's Hacktoberfest and December's Advent of Code are public-repository events).
- GitHub excludes bots and accounts with activity "that could be reasonably attributed" to non-human
  volumes, and withholds an economy's metric in a quarter with fewer than 100 active developers.
- Location is each account's mode daily location (developers) or its push location; `_world` in the
  mart sums the reported economies, so it misses suppressed ones and never adds `EU`.
- Releases so far have only appended quarters: the US values of 2020–2025 are identical in the
  releases of 2023-09-20, 2025-04-21, 2026-01-28 and 2026-07-07 (checked 2026-10-26). Commit
  pinning makes a past as-of exact either way.
- 2025–26 pushes rise far faster than developers (US pushes +40% in 2026 Q1 alone), plausibly AI
  coding agents pushing on developers' behalf; a structural break for any seasonal estimate.
