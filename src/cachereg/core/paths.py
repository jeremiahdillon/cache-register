"""Filesystem layout. Everything under ``data/`` and ``outputs/`` is gitignored."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    return Path(os.environ.get("CACHEREG_DATA_DIR", REPO_ROOT / "data"))


def raw_dir(source: str) -> Path:
    return data_dir() / "raw" / source


def staged_dir(source: str) -> Path:
    return data_dir() / "staged" / source


def warehouse_path() -> Path:
    return data_dir() / "warehouse.duckdb"


def outputs_dir() -> Path:
    return Path(os.environ.get("CACHEREG_OUTPUTS_DIR", REPO_ROOT / "outputs"))


def repo_relative(path: Path) -> str:
    """Repo-relative POSIX path for manifests (never absolute — PLAN §4.4)."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name
