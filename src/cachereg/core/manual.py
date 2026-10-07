"""Manual input for sources with `input: manual` (PLAN §4.2): bytes the author pastes or saves.

`cachereg fetch <source> --from-clipboard | --from-file PATH [--cut NAME]` hands the adapter a
`ManualInput`; the adapter validates it and builds the RawFetch as usual. Nothing here knows any
source. The clipboard is read through `read_clipboard`, which tests replace (CI has no `pbpaste`).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 10_000_000


@dataclass(frozen=True)
class ManualInput:
    body: bytes
    via: str  # "clipboard" | "file" (never the file's path: manifests hold no local paths)
    cut: str | None  # which part of the source this input is, as the source defines it


def read_clipboard() -> bytes:
    """The clipboard as bytes (macOS `pbpaste`)."""
    try:
        done = subprocess.run(["pbpaste"], capture_output=True, check=True, timeout=10)  # noqa: S607
    except FileNotFoundError as e:
        raise ValueError("no clipboard reader (pbpaste is macOS only); save the data and use --from-file") from e
    return done.stdout


def read_input(clipboard: bool, file: Path | None, cut: str | None) -> ManualInput:
    if clipboard == (file is not None):
        raise ValueError("give exactly one of --from-clipboard and --from-file")
    if file is not None:
        if not file.is_file():
            raise ValueError(f"--from-file: {file.name} is not a file")
        if file.stat().st_size > MAX_BYTES:
            raise ValueError(f"--from-file: larger than {MAX_BYTES:,} bytes")
        body, via = file.read_bytes(), "file"
    else:
        body, via = read_clipboard(), "clipboard"
    if len(body) > MAX_BYTES:
        raise ValueError(f"input larger than {MAX_BYTES:,} bytes")
    if not body.strip():
        raise ValueError(f"the {via} is empty")
    return ManualInput(body, via, cut)
