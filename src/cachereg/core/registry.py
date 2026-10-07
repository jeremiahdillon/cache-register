"""Source registry: config/sources.yaml + one package per source under cachereg.sources."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType

import yaml

from cachereg.core.paths import REPO_ROOT

FIELDS = {"id", "history", "revisions", "redistribution", "derived_charts", "attribution", "cadence", "requires"}
RIGHTS = {"allowed", "allowed-with-attribution", "forbidden", "unknown"}
CADENCES = ("daily", "weekly", "monthly")  # PLAN §4.5; core/schedule.py turns each into a next-due date
INPUTS = ("api", "manual")  # manual: imported by the author with `fetch --from-clipboard/--from-file`


@dataclass(frozen=True)
class Source:
    id: str
    history: str
    revisions: str
    redistribution: str
    derived_charts: str
    attribution: str
    cadence: str
    requires: tuple[str, ...]
    enabled: bool
    input: str = "api"

    def module(self, name: str) -> ModuleType:
        return importlib.import_module(f"cachereg.sources.{self.id}.{name}")


def reproducibility_class(src: Source) -> str:
    """PLAN §4.4: Exact (native, not revised) · Latest-only (revised in place) · Author-only (snapshot)."""
    if src.history == "snapshot":
        return "Author-only"
    return "Latest-only" if src.revisions == "revised" else "Exact"


def load_sources(path=None) -> dict[str, Source]:
    data = yaml.safe_load((path or REPO_ROOT / "config" / "sources.yaml").read_text()) or {}
    out = {}
    for entry in data.get("sources") or []:
        missing = FIELDS - entry.keys()
        if missing:
            raise ValueError(f"source {entry.get('id')!r} missing fields: {sorted(missing)}")
        for right in ("redistribution", "derived_charts"):
            if entry[right] not in RIGHTS:
                raise ValueError(f"source {entry['id']!r}: {right} must be one of {sorted(RIGHTS)}")
        if entry["cadence"] not in CADENCES:
            raise ValueError(
                f"source {entry['id']!r}: unknown cadence {entry['cadence']!r}; use one of {', '.join(CADENCES)}"
            )
        if entry.get("input", "api") not in INPUTS:
            raise ValueError(f"source {entry['id']!r}: input must be one of {', '.join(INPUTS)}")
        out[entry["id"]] = Source(
            id=entry["id"],
            history=entry["history"],
            revisions=entry["revisions"],
            redistribution=entry["redistribution"],
            derived_charts=entry["derived_charts"],
            attribution=entry["attribution"].strip(),
            cadence=entry["cadence"],
            requires=tuple(entry.get("requires") or ()),
            enabled=bool(entry.get("enabled", True)),
            input=entry.get("input", "api"),
        )
    return out
