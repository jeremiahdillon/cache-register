"""Immutable raw store: data/raw/<source>/<YYYY-MM-DD>/<fetch_id>/ with a manifest.json.

A fetch writes every file once and never modifies it (PLAN §4.1). Manifests hold no secrets,
no absolute paths and only repo-relative or public URLs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cachereg.core.paths import raw_dir

MAX_ID_BUMPS = 60


@dataclass
class RawFetch:
    source: str
    adapter_version: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    files: dict[str, bytes] = field(default_factory=dict)
    requests: list[dict] = field(default_factory=list)  # {"url": public URL, "status": int, "file": name}
    vintage: dict = field(default_factory=dict)  # most specific source revision available (PLAN §4.4)

    @property
    def fetch_id(self) -> str:
        return self.fetched_at.strftime("%Y%m%dT%H%M%SZ")

    def add(self, name: str, body: bytes, url: str, status: int | None) -> None:
        """`status` is None for manual imports (no HTTP request was made)."""
        if name in self.files:
            raise ValueError(f"duplicate raw file name {name!r}")
        self.files[name] = body
        self.requests.append({"url": url, "status": status, "file": name})

    def write(self) -> Path:
        # Immutable: never overwrite a fetch. Two fetches of one source in the same second (e.g. a
        # scripted loop of manual imports) would share a fetch id, so the later one moves forward a
        # second at a time until its folder is free; the id format and its ordering are unchanged.
        for _ in range(MAX_ID_BUMPS):
            out = raw_dir(self.source) / self.fetched_at.strftime("%Y-%m-%d") / self.fetch_id
            try:
                out.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                self.fetched_at += timedelta(seconds=1)
        else:
            raise FileExistsError(f"{self.source}: no free fetch id after {MAX_ID_BUMPS} tries")
        for name, body in self.files.items():
            (out / name).write_bytes(body)
        manifest = {
            "source": self.source,
            "adapter_version": self.adapter_version,
            "fetch_id": self.fetch_id,
            "fetched_at": self.fetched_at.isoformat(timespec="seconds"),
            "vintage": self.vintage,
            "requests": self.requests,
            "files": {n: hashlib.sha256(b).hexdigest() for n, b in self.files.items()},
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return out


@dataclass(frozen=True)
class StoredFetch:
    path: Path
    manifest: dict

    @property
    def fetched_at(self) -> datetime:
        return datetime.fromisoformat(self.manifest["fetched_at"])

    def read(self, name: str) -> bytes:
        return (self.path / name).read_bytes()


def list_fetches(source: str) -> list[StoredFetch]:
    """All fetches for a source, oldest first."""
    root = raw_dir(source)
    fetches = [StoredFetch(m.parent, json.loads(m.read_text())) for m in root.glob("*/*/manifest.json")]
    return sorted(fetches, key=lambda f: f.manifest["fetch_id"])
