"""Last fetch outcome per source, for `cachereg status` (PLAN §4.5).

A failed fetch writes nothing to the raw store, so its error is kept here instead:
data/state/fetch.json (gitignored, outside data/raw). Messages pass through `redact` and are cut to
one short line. Nothing in `build` reads this file, so it never affects a rebuild.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from cachereg.core.paths import data_dir
from cachereg.core.settings import redact

MAX_MESSAGE = 300


def state_file() -> Path:
    return data_dir() / "state" / "fetch.json"


def load() -> dict[str, dict]:
    """Per-source records; raises ValueError if the file exists but is not a JSON object."""
    f = state_file()
    if not f.is_file():
        return {}
    data = json.loads(f.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{f.name} is not a JSON object")
    return data


def clean(message: str) -> str:
    lines = redact(message).strip().splitlines()
    line = lines[0] if lines else ""
    return line if len(line) <= MAX_MESSAGE else line[: MAX_MESSAGE - 1] + "…"


def _save(data: dict) -> None:
    f = state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=f.parent, prefix=".fetch.", suffix=".tmp")  # unique per writer
    try:
        with os.fdopen(fd, "w") as out:
            out.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, f)  # atomic: a crash never leaves a half-written file
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def record(source: str, error: str | None = None, kind: str = "FAIL", at: datetime | None = None) -> None:
    """Record a fetch attempt: success clears the source's last error, failure stores a redacted one."""
    try:
        data = load()
    except ValueError:
        data = {}  # unreadable state is rebuilt rather than blocking a fetch
    stamp = (at or datetime.now(UTC)).isoformat(timespec="seconds")
    entry = data.get(source) if isinstance(data.get(source), dict) else {}
    entry["last_attempt"] = stamp
    if error is None:
        entry["last_ok"] = stamp
        entry["last_error"] = None
    else:
        entry["last_error"] = {"at": stamp, "kind": kind, "message": clean(error)}
    data[source] = entry
    _save(data)
