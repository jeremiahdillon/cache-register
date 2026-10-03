"""Folder configs: `receipts/<topic>/receipt.yaml` and `explore/<dated>/explore.yaml` (one schema).

```yaml
title: Who gets paid on OpenRouter?
sources: [openrouter_rankings, openrouter_models]
as_of: 2026-10-02                # receipts: data date of the committed outputs
promoted_from: explore/…          # receipts only, informational
config: {weeks: 13}               # passed to analysis.build and chart functions
visuals:
  - {name: share-lines, chart: line_chart, targets: [x_png, linkedin_png, blog_html]}
  - {name: share-race,  chart: race,       targets: [linkedin_video, x_video]}
```
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from cachereg.core.paths import REPO_ROOT
from cachereg.core.registry import load_sources
from cachereg.story.model import TARGETS

VISUAL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Visual:
    name: str
    chart: str
    targets: tuple[str, ...]


@dataclass(frozen=True)
class FolderConfig:
    path: Path
    kind: str  # "receipt" | "explore"
    title: str
    sources: tuple[str, ...]
    as_of: date | None
    config: dict = field(default_factory=dict)
    visuals: tuple[Visual, ...] = ()

    @property
    def link(self) -> str | None:
        """Receipts: the folder name is the short link. Explorations have none."""
        return self.path.name if self.kind == "receipt" else None

    @property
    def file(self) -> Path:
        return self.path / ("receipt.yaml" if self.kind == "receipt" else "explore.yaml")


def kind_of(path: Path, root: Path = REPO_ROOT) -> str:
    path = path.resolve()
    if (path / "receipt.yaml").is_file():
        return "receipt"
    if (path / "explore.yaml").is_file():
        return "explore"
    raise FileNotFoundError(f"{path} has neither receipt.yaml nor explore.yaml")


def load(path: Path) -> FolderConfig:
    path = path.resolve()
    kind = kind_of(path)
    raw = yaml.safe_load((path / f"{'receipt' if kind == 'receipt' else 'explore'}.yaml").read_text()) or {}
    known = load_sources()
    sources = tuple(raw.get("sources") or ())
    unknown = [s for s in sources if s not in known]
    if unknown:
        raise ValueError(f"{path.name}: unknown source(s) {unknown}")
    visuals = []
    for v in raw.get("visuals") or ():
        if not VISUAL_NAME_RE.match(v.get("name", "")):
            raise ValueError(f"{path.name}: visual name {v.get('name')!r} must be lowercase-hyphenated")
        bad = [t for t in v.get("targets", ()) if t not in TARGETS]
        if bad:
            raise ValueError(f"{path.name}: visual {v['name']!r} has unknown targets {bad}")
        visuals.append(Visual(v["name"], v["chart"], tuple(v["targets"])))
    if len({v.name for v in visuals}) != len(visuals):
        raise ValueError(f"{path.name}: duplicate visual names")
    as_of = raw.get("as_of")
    if kind == "receipt":
        if not sources or not visuals or not isinstance(as_of, date):
            raise ValueError(f"{path.name}/receipt.yaml needs sources, visuals and an as_of date")
    return FolderConfig(
        path=path,
        kind=kind,
        title=str(raw.get("title") or path.name),
        sources=sources,
        as_of=as_of if isinstance(as_of, date) else None,
        config=dict(raw.get("config") or {}),
        visuals=tuple(visuals),
    )


def set_as_of(cfg: FolderConfig, as_of: date) -> None:
    """Rewrite only the `as_of:` line, keeping comments and layout."""
    text = cfg.file.read_text()
    new, n = re.subn(r"(?m)^as_of:.*$", f"as_of: {as_of.isoformat()}", text)
    if n != 1:
        raise ValueError(f"{cfg.file.name}: expected exactly one 'as_of:' line")
    cfg.file.write_text(new)
