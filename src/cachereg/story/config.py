"""Folder configs: `receipts/<topic>/receipt.yaml` and `explore/<dated>/explore.yaml` (one schema).

```yaml
title: Who gets paid on OpenRouter?
sources: [openrouter_rankings, openrouter_models]
as_of: 2026-10-02                # receipts: data date of the committed outputs
promoted_from: explore/…          # receipts only, informational
link: a-topic                     # explorations only, optional: reserve a short link before promotion
config: {weeks: 13}               # passed to analysis.build and chart functions
visuals:
  - {name: share-lines, chart: line_chart, targets: [x_png, linkedin_png, blog_html]}
  - {name: share-race,  chart: race,       targets: [linkedin_video, x_video]}
  - {name: tokens, chart: tokens, targets: [x_png], sources: [openrouter_rankings]}  # its own credits
```

A visual's `sources` (optional, a subset of the folder's) are the sources that visual shows: its footer
credits them and the image licence gate checks them. Inlined data (`blog_html`, `data.json`) is shared by
every visual, so it is always gated on all of the folder's sources.
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
    sources: tuple[str, ...] | None = None  # None = the folder's sources


@dataclass(frozen=True)
class FolderConfig:
    path: Path
    kind: str  # "receipt" | "explore"
    title: str
    sources: tuple[str, ...]
    as_of: date | None
    config: dict = field(default_factory=dict)
    visuals: tuple[Visual, ...] = ()
    reserved_link: str | None = None  # explorations only: `link:` in explore.yaml

    @property
    def link(self) -> str | None:
        """Receipts: the folder name is the short link. Explorations: the link they reserve, if any (the site
        redirects it to the exploration until a receipt promoted from it takes the name over)."""
        return self.path.name if self.kind == "receipt" else self.reserved_link

    def visual_sources(self, visual: Visual) -> tuple[str, ...]:
        return visual.sources if visual.sources is not None else self.sources

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
        name, chart, targets = v.get("name", ""), v.get("chart"), tuple(v.get("targets") or ())
        if not VISUAL_NAME_RE.match(name):
            raise ValueError(f"{path.name}: visual name {name!r} must be lowercase-hyphenated")
        if not chart or not targets:
            raise ValueError(f"{path.name}: visual {name!r} needs a chart and at least one target")
        bad = [t for t in targets if t not in TARGETS]
        if bad:
            raise ValueError(f"{path.name}: visual {name!r} has unknown targets {bad}")
        v_sources = v.get("sources")
        if v_sources is not None:
            v_sources = tuple(v_sources)
            outside = [s for s in v_sources if s not in sources]
            if not v_sources or outside:
                raise ValueError(
                    f"{path.name}: visual {name!r} sources must be a non-empty subset of the folder's sources"
                    + (f" (not in it: {outside})" if outside else "")
                )
        visuals.append(Visual(name, chart, targets, v_sources))
    if len({v.name for v in visuals}) != len(visuals):
        raise ValueError(f"{path.name}: duplicate visual names")
    as_of = raw.get("as_of")
    if kind == "receipt":
        if not sources or not visuals or not isinstance(as_of, date):
            raise ValueError(f"{path.name}/receipt.yaml needs sources, visuals and an as_of date")
        if "link" in raw:
            raise ValueError(f"{path.name}/receipt.yaml: a receipt's link is its folder name; remove `link:`")
    reserved = raw.get("link") if kind == "explore" else None
    if reserved is not None:
        from cachereg.site import check_slug

        check_slug(str(reserved), path / "explore.yaml")
    return FolderConfig(
        path=path,
        kind=kind,
        title=str(raw.get("title") or path.name),
        sources=sources,
        as_of=as_of if isinstance(as_of, date) else None,
        config=dict(raw.get("config") or {}),
        visuals=tuple(visuals),
        reserved_link=str(reserved) if reserved is not None else None,
    )


def set_as_of(cfg: FolderConfig, as_of: date) -> None:
    """Rewrite only the `as_of:` line, keeping comments and layout."""
    text = cfg.file.read_text()
    new, n = re.subn(r"(?m)^as_of:.*$", f"as_of: {as_of.isoformat()}", text)
    if n != 1:
        raise ValueError(f"{cfg.file.name}: expected exactly one 'as_of:' line")
    cfg.file.write_text(new)
