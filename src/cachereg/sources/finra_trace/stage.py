"""Stage FINRA TRACE end-of-day bodies: one row per CUSIP × trade date × fetch (all vintages kept), plus
the bonds' terms. Days whose last sale carries no yield (FINRA leaves it empty, e.g. a bond's first
days of trading) keep the price with a null yield.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date

import polars as pl

from cachereg.core.store import list_fetches
from cachereg.sources.finra_trace.bonds import BONDS
from cachereg.sources.finra_trace.fetch import records

SOURCE = "finra_trace"
EOD_SCHEMA = {
    "cusip": pl.String,
    "symbol": pl.String,  # FINRA's issue symbol
    "date": pl.Date,
    "last_price": pl.Float64,  # price of the day's last reported trade, % of par
    "last_yield_pct": pl.Float64,  # FINRA's yield at that price
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
}
BONDS_SCHEMA = {"cusip": pl.String, "ticker": pl.String, "coupon_pct": pl.Float64, "maturity": pl.Date,
                "description": pl.String}  # fmt: skip


def _num(v) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) else None


def stage() -> dict[str, pl.DataFrame]:
    rows, rejected = [], 0
    for f in list_fetches(SOURCE):
        common = {"fetch_id": f.manifest["fetch_id"], "fetched_at": f.fetched_at.astimezone(UTC)}
        for name in f.manifest["files"]:
            try:
                recs = records(json.loads(f.read(name)))
            except (KeyError, TypeError, ValueError):
                rejected += 1
                continue
            for r in recs:
                try:
                    price = _num(r["lastSalePrice"])
                    if price is None:
                        raise ValueError
                    rows.append({"cusip": str(r["cusip"]), "symbol": r.get("issueSymbolIdentifier"),
                                 "date": date.fromisoformat(r["tradeDate"]), "last_price": price,
                                 "last_yield_pct": _num(r.get("lastSaleYield"))} | common)  # fmt: skip
                except (KeyError, TypeError, ValueError):
                    rejected += 1
    eod = pl.DataFrame(rows, schema=EOD_SCHEMA, orient="row").sort("cusip", "date", "fetch_id")
    bonds = pl.DataFrame(
        [(c, t, cp, date.fromisoformat(m), d) for c, (t, cp, m, d) in BONDS.items()], schema=BONDS_SCHEMA, orient="row"
    )
    return {"eod": eod, "bonds": bonds, "_rejected_rows": pl.DataFrame({"rejected": [rejected]})}
