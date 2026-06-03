"""Derive gamma flip, put wall, and call wall from UW spot-exposures/strike output.

UW does not pre-compute these named levels; this module reads the raw
strike-level GEX list and identifies them by definition:

  - gamma flip: zero crossing of cumulative GEX from low strike to high
  - put wall:  strike below spot with the largest positive GEX
  - call wall: strike above spot with the largest negative GEX (in absolute
              terms; dealers short here will sell into rallies)
"""

from __future__ import annotations

from typing import Iterable, Optional


def _sorted_by_strike(rows: Iterable[dict]) -> list[dict]:
    """Sort rows by strike, dropping rows with non-finite strike or gex."""
    import math

    cleaned = []
    for r in rows:
        try:
            s = float(r["strike"])
            g = float(r["gex"])
            if math.isfinite(s) and math.isfinite(g):
                cleaned.append({"strike": s, "gex": g})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(cleaned, key=lambda r: r["strike"])


def _gamma_flip(rows: list[dict], spot: float) -> Optional[float]:
    """Linear-interpolated strike at which cumulative GEX crosses zero.

    When the cumulative-GEX curve has multiple zero crossings — common when
    deep-OTM put OI is large enough to push the running sum negative at low
    strikes before call OI dominates near spot — returns the crossing
    nearest to spot. That is the trading-relevant flip: dealer hedging
    behavior changes around spot, not 80% below it.
    """
    if not rows:
        return None
    crossings: list[float] = []
    cum = 0.0
    prev_strike, prev_cum = None, 0.0
    for r in rows:
        strike = float(r["strike"])
        cum += float(r["gex"])
        if prev_strike is not None and prev_cum * cum < 0:
            span = strike - prev_strike
            frac = -prev_cum / (cum - prev_cum) if cum != prev_cum else 0.5
            crossings.append(prev_strike + frac * span)
        prev_strike, prev_cum = strike, cum
    if not crossings:
        return None
    return min(crossings, key=lambda x: abs(x - spot))


def _put_wall(rows: list[dict], spot: float) -> Optional[float]:
    below = [r for r in rows if float(r["strike"]) < spot and float(r["gex"]) > 0]
    if not below:
        return None
    return float(max(below, key=lambda r: float(r["gex"]))["strike"])


def _call_wall(rows: list[dict], spot: float) -> Optional[float]:
    above = [r for r in rows if float(r["strike"]) > spot and float(r["gex"]) < 0]
    if not above:
        return None
    return float(min(above, key=lambda r: float(r["gex"]))["strike"])


def compute_levels(gex_by_strike: Iterable[dict], spot: float) -> dict:
    """Return dict with keys gamma_flip, put_wall, call_wall.

    Each input row must have keys 'strike' and 'gex'. Spot is the current
    underlying price. Returns None for any level that cannot be identified.
    """
    rows = _sorted_by_strike(list(gex_by_strike))
    return {
        "gamma_flip": _gamma_flip(rows, spot),
        "put_wall": _put_wall(rows, spot),
        "call_wall": _call_wall(rows, spot),
    }
