"""Fetch Epoch AI's "Data on AI models" zip (CC BY 4.0), stored as served."""

from __future__ import annotations

from cachereg.core.store import RawFetch
from cachereg.sources._epoch_zip import fetch_zip

SOURCE = "epoch_models"
ADAPTER_VERSION = "1"
URL = "https://epoch.ai/data/ai_models.zip"
FILE = "ai_models.zip"
SUBSETS = {  # staged as membership flags on all_ai_models.csv
    "in_notable": "notable_ai_models.csv",
    "in_frontier": "frontier_ai_models.csv",
    "in_large_scale": "large_scale_ai_models.csv",
}
REQUIRED = ("README.md", "all_ai_models.csv", *SUBSETS.values())


def fetch(full: bool = False, today=None) -> RawFetch:
    """`full` and `today` are unused: the dataset has no history to back-fill (Latest-only)."""
    return fetch_zip(SOURCE, ADAPTER_VERSION, URL, FILE, REQUIRED)
