"""Harnesses: config/entities/apps.yaml (session-cost `app_slug` → app-rankings `app_id`, name, vendor)."""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from cachereg.core.paths import entities_dir


@dataclass(frozen=True)
class Harness:
    app_slug: str
    app_id: int
    name: str
    vendor_id: str | None  # the model maker that publishes the harness ("first-party"), if any


def load_harnesses() -> list[Harness]:
    f = entities_dir() / "apps.yaml"
    data = (yaml.safe_load(f.read_text()) or {}) if f.is_file() else {}
    vendors = set((yaml.safe_load((entities_dir() / "vendors.yaml").read_text()) or {}).get("vendors") or {})
    out, ids = [], set()
    for slug, h in (data.get("harnesses") or {}).items():
        app_id = h.get("app_id")
        if isinstance(app_id, bool) or not isinstance(app_id, int):
            raise ValueError(f"apps.yaml: {slug} app_id must be an integer")
        if app_id in ids:
            raise ValueError(f"apps.yaml: app_id {app_id} listed twice")
        if h.get("vendor") is not None and h["vendor"] not in vendors:
            raise ValueError(f"apps.yaml: {slug} vendor {h['vendor']!r} is not in vendors.yaml")
        ids.add(app_id)
        out.append(Harness(slug, app_id, h["name"], h.get("vendor")))
    return out
