"""The receipt footer: source credits, method and a link back to the code (PLAN §6.4).

Attributions come from config/sources.yaml so required credits can't be forgotten.
"""

from __future__ import annotations

from dataclasses import dataclass

from cachereg.core.registry import load_sources
from cachereg.viz.brand import brand


@dataclass(frozen=True)
class Receipt:
    source: str
    method: str
    link: str

    def lines(self) -> list[tuple[str, str]]:
        return [("SOURCE", self.source), ("METHOD", self.method), ("RECEIPTS", self.link)]


def long_url(analysis_path: str) -> str:
    repo = brand()["repo_url"].removeprefix("https://")
    return f"{repo}/tree/main/{analysis_path}"


def receipt(source_ids: list[str], as_of, method: str, analysis_path: str, link: str | None = None) -> Receipt:
    """``link`` is the analysis's short slug (story.yaml); without one, the long GitHub URL is used."""
    from cachereg.site import short_url

    sources = load_sources()
    credits = []
    for sid in source_ids:
        text = sources[sid].attribution.replace("{as_of}", str(as_of))
        if text not in credits:
            credits.append(text)
    return Receipt(source="; ".join(credits), method=method, link=short_url(link) if link else long_url(analysis_path))
