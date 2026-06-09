"""Build long-45DTE put + short-1to2DTE put diagonal calendar on RUT.

Three modes:
  - calendar   (Ks = Kl)  — vega-positive theta income, NEUTRAL vol
  - protective (Ks < Kl)  — bearish bias, RICH vol
  - aggressive (Ks > Kl)  — bullish RICH vol, VIX < 25 hard limit

Defined-risk in all three: max loss at short-leg expiry =
max((Ks - Kl) * 100, 0) - net_credit (calendar collapses to long put
extrinsic decay; protective offsets dollar-for-dollar in [Ks, Kl] range).

Chain-vs-BSM fallback follows scripts.macro_hedge pattern using shared
scripts._market helpers; pricing_source ∈ {chain, mixed, bsm}.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from scipy.stats import norm

Mode = Literal["calendar", "protective", "aggressive"]

# Strike-selection policy per mode. Δ-only selection across 1-2DTE short
# + 45DTE long is mathematically broken for `calendar` (same Δ → different
# K across DTEs) and `protective` (1DTE 0.15Δ K ≈ 1.5% OTM, 45DTE 0.30Δ K
# ≈ 5% OTM, so Ks > Kl with default Δs — violates the spec's "Ks < Kl"
# protective layout). Fix: Kl picked by Δ in all modes; Ks derived
# relative to Kl per mode-specific anchor below.
DEFAULT_DELTAS: dict[Mode, dict[str, float]] = {
    "calendar": {"long": 0.30, "short": 0.30},  # short Δ unused; Ks = Kl
    "protective": {"long": 0.30, "short": 0.15},  # short Δ used as fallback
    "aggressive": {"long": 0.15, "short": 0.30},  # natural Ks > Kl with these Δs
}

# Mode-specific Ks selection AFTER Kl is fixed.
#   calendar:   Ks = Kl  (same strike)
#   protective: Ks = Kl * (1 - SHORT_STRIKE_OFFSET_PCT)  → Ks < Kl by ~2.5%
#   aggressive: Ks picked by short_delta (gives Ks > Kl naturally with
#               default 0.30 short Δ + 0.15 long Δ, since 1DTE 0.30Δ K is
#               ~1.5% OTM while 45DTE 0.15Δ K is ~9% OTM)
SHORT_STRIKE_OFFSET_PCT = {
    "protective": 0.025,
}

_R = 0.04  # risk-free rate assumption shared with macro_hedge


def _bs_put_greeks(
    spot: float, strike: float, t_years: float, r: float, sigma: float
) -> dict[str, float]:
    """Black-Scholes put greeks. Theta returned per calendar day, vega per 1pp IV."""
    if t_years <= 0 or sigma <= 0:
        intrinsic_delta = -1.0 if spot < strike else 0.0
        return {"delta": intrinsic_delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    delta = norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (spot * sigma * math.sqrt(t_years))
    theta_annual = -spot * norm.pdf(d1) * sigma / (
        2 * math.sqrt(t_years)
    ) + r * strike * math.exp(-r * t_years) * norm.cdf(-d2)
    vega_per_1 = spot * norm.pdf(d1) * math.sqrt(t_years)
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta_annual / 365,
        "vega": vega_per_1 / 100,
    }


def _strike_for_put_delta(
    spot: float, target_abs: float, t_years: float, iv: float, r: float = _R
) -> float:
    """Invert BSM to find strike with put |Δ| ≈ target_abs."""
    if not 0 < target_abs < 1:
        raise ValueError(f"target_abs must be in (0,1), got {target_abs}")
    z = norm.ppf(target_abs)
    return spot * math.exp((r + 0.5 * iv**2) * t_years + iv * math.sqrt(t_years) * z)
