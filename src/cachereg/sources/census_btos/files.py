"""The BTOS workbooks this source fetches, and where the AI rows are in each.

Each workbook is the full history of one breakdown (docs/plans/2026-10-07-census-btos.md). The
current downloads carry only the current AI wording ("in any of its business functions", from
2025-11-17); the original wording ("in producing goods or services", 2023-09 to 2025-10) lives in
the frozen `AI Core Questions.xlsx`. Adding a breakdown (e.g. State) is one more entry here.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

BASE_URL = "https://www.census.gov/hfp/btos/downloads/"
DATES = "Collection and Reference Dates"
SECTOR, SIZE = "Sector", "Empsize"
CURRENT_ESTIMATES = "Response Estimates"
CURRENT_ERRORS = "Response Standard Errors"


@dataclass(frozen=True)
class Table:
    breakdown: str  # national | sector | size | sector_size
    estimates: str  # sheet name
    errors: str  # sheet name, same layout
    keys: tuple[str, ...]  # header names of the key columns before `Question ID`


@dataclass(frozen=True)
class File:
    key: str
    name: str  # as published on census.gov
    wording: str  # original | current: the AI question wording this file must hold
    always_store: bool  # stored on every fetch (the release marker), else only when changed
    tables: tuple[Table, ...]

    @property
    def file_name(self) -> str:
        """Name in the raw store."""
        return f"{self.key}.xlsx"

    @property
    def url(self) -> str:
        return BASE_URL + urllib.parse.quote(self.name)

    @property
    def sheets(self) -> list[str]:
        return [s for t in self.tables for s in (t.estimates, t.errors)] + [DATES]


def _current(breakdown: str, keys: tuple[str, ...]) -> tuple[Table, ...]:
    return (Table(breakdown, CURRENT_ESTIMATES, CURRENT_ERRORS, keys),)


FILES = (
    File("national", "National.xlsx", "current", True, _current("national", ())),
    File("sector", "Sector.xlsx", "current", False, _current("sector", (SECTOR,))),
    File("size", "Employment Size Class.xlsx", "current", False, _current("size", (SIZE,))),
    File("sector_size", "Sector by Employment Size Class.xlsx", "current", False,
         _current("sector_size", (SECTOR, SIZE))),
    File(
        "ai_original",
        "AI Core Questions.xlsx",
        "original",
        False,
        (
            Table("national", "National Estimates", "National SE", ()),
            Table("sector", "Sector Estimates", "Sector SE", (SECTOR,)),
            Table("size", "Employment Size Estimates", "Employment Size SE", (SIZE,)),
            Table("sector_size", "Sector x Employment Estimates", "Sector x Employment SE", (SECTOR, SIZE)),
        ),
    ),
)  # fmt: skip
BY_KEY = {f.key: f for f in FILES}
