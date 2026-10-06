"""The companies to fetch: config/entities/tickers.yaml (ticker → CIK, name, group, vendor)."""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from cachereg.core.paths import REPO_ROOT

TICKERS_FILE = REPO_ROOT / "config" / "entities" / "tickers.yaml"  # tests point this at a synthetic file
GROUPS = {"hyperscaler", "neocloud", "supplier"}


@dataclass(frozen=True)
class Company:
    ticker: str
    cik: str  # 10 digits, zero-padded, as in EDGAR URLs
    name: str
    group: str
    vendor_id: str | None


def cik10(value: int | str) -> str:
    s = str(value).strip()
    if not s.isdigit() or len(s) > 10:
        raise ValueError(f"not a CIK: {value!r}")
    return s.zfill(10)


def load_companies() -> list[Company]:
    data = yaml.safe_load(TICKERS_FILE.read_text()) or {}
    out, seen = [], set()
    for ticker, c in (data.get("companies") or {}).items():
        cik = cik10(c["cik"])
        if cik in seen:
            raise ValueError(f"tickers.yaml: CIK {cik} listed twice")
        if c["group"] not in GROUPS:
            raise ValueError(f"tickers.yaml: {ticker} group must be one of {sorted(GROUPS)}")
        seen.add(cik)
        out.append(Company(ticker, cik, c["name"], c["group"], c.get("vendor")))
    return out
