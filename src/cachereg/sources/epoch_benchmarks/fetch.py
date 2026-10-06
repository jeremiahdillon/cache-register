"""Fetch Epoch AI's "Capabilities & benchmarking" zip (CC BY 4.0), stored as served."""

from __future__ import annotations

from cachereg.core.store import RawFetch
from cachereg.sources._epoch_zip import fetch_zip

SOURCE = "epoch_benchmarks"
ADAPTER_VERSION = "1"
URL = "https://epoch.ai/data/benchmark_data.zip"
FILE = "benchmark_data.zip"
REQUIRED = (
    "README.md",
    "benchmark_metadata.csv",
    "model_metadata.csv",
    "epoch_capabilities_index/eci_scores.csv",
)


def fetch(full: bool = False, today=None) -> RawFetch:
    """`full` and `today` are unused: the dataset has no history to back-fill (Latest-only)."""
    return fetch_zip(SOURCE, ADAPTER_VERSION, URL, FILE, REQUIRED)
