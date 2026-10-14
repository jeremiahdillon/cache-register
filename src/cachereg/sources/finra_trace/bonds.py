"""Bonds fetched from FINRA TRACE, with their terms (FINRA's end-of-day rows carry no coupon or maturity).

Terms are from CoreWeave's pricing releases and indentures (SOURCE.md); the CUSIPs are FINRA's bond
search for "CRWV" (the 144A lines, which carry the yields; the Reg S lines report prices only). Each
CUSIP ↔ terms pairing was checked by recomputing FINRA's 2026-10-13 yield from its price (within 0.01 pt).
Convertible notes are left out: their yields reflect the conversion option, not credit.
"""

from __future__ import annotations

BONDS = {
    # cusip: (issuer ticker, coupon %, maturity, description)
    "21873SAB4": ("CRWV", 9.25, "2030-06-01", "CoreWeave 9.25% senior notes due 2030"),
    "21873SAC2": ("CRWV", 9.00, "2031-02-01", "CoreWeave 9.00% senior notes due Feb. 2031"),
    "21873SAG3": ("CRWV", 9.75, "2031-10-01", "CoreWeave 9.75% senior notes due Oct. 2031"),
    "21873SAK4": ("CRWV", 9.625, "2032-07-15", "CoreWeave 9.625% senior notes due 2032"),
}
