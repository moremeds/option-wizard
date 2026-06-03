"""Build SPX / SPY / NDX / QQQ macro hedge structures.

Three structures supported, picked by scenario:
  - mild_correction_-5  -> put butterfly centered at spot * 0.95
  - deep_correction_-10 -> put spread (long ATM, short -10% OTM)
  - crash_-20           -> long OTM put at spot * 0.90 (insurance)

Cost cap enforced: total premium <= portfolio_notional *
max_annual_cost_pct * (horizon_days / 365).
"""

from __future__ import annotations

import math
from typing import Any

from scipy.stats import norm


def _bs_put(
    spot: float, strike: float, t_years: float, r: float, sigma: float
) -> float:
    """Black-Scholes put price. Sufficient approximation for hedge sizing."""
    if t_years <= 0 or sigma <= 0:
        return max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    return strike * math.exp(-r * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def _butterfly(spot: float, t_years: float, iv: float, qty: int) -> list[dict]:
    """Standard 3-leg put butterfly centered at body strike."""
    body = spot * 0.95
    wing_up = spot * 0.98
    wing_dn = spot * 0.92
    return [
        {
            "right": "put",
            "action": "buy",
            "strike": wing_up,
            "qty": qty,
            "limit_price": _bs_put(spot, wing_up, t_years, 0.04, iv),
        },
        {
            "right": "put",
            "action": "sell",
            "strike": body,
            "qty": 2 * qty,
            "limit_price": _bs_put(spot, body, t_years, 0.04, iv),
        },
        {
            "right": "put",
            "action": "buy",
            "strike": wing_dn,
            "qty": qty,
            "limit_price": _bs_put(spot, wing_dn, t_years, 0.04, iv),
        },
    ]


def _put_spread(spot: float, t_years: float, iv: float, qty: int) -> list[dict]:
    long_strike = spot
    short_strike = spot * 0.90
    return [
        {
            "right": "put",
            "action": "buy",
            "strike": long_strike,
            "qty": qty,
            "limit_price": _bs_put(spot, long_strike, t_years, 0.04, iv),
        },
        {
            "right": "put",
            "action": "sell",
            "strike": short_strike,
            "qty": qty,
            "limit_price": _bs_put(spot, short_strike, t_years, 0.04, iv),
        },
    ]


def _long_put(spot: float, t_years: float, iv: float, qty: int) -> list[dict]:
    strike = spot * 0.90
    return [
        {
            "right": "put",
            "action": "buy",
            "strike": strike,
            "qty": qty,
            "limit_price": _bs_put(spot, strike, t_years, 0.04, iv),
        },
    ]


def _net_premium(legs: list[dict]) -> float:
    total = 0.0
    multiplier = 100
    for leg in legs:
        sign = -1 if leg["action"] == "buy" else 1
        total += sign * leg["limit_price"] * leg["qty"] * multiplier
    return (
        -total
    )  # convert net credit (positive in our sign convention) to net cost paid


def build_macro_hedge(
    portfolio_notional: float,
    hedge_horizon_days: int,
    scenario: str,
    underlying: str = "SPX",
    structure: str = "auto",
    snapshot: dict | None = None,
    max_annual_cost_pct: float = 0.015,
    qty: int = 1,
) -> dict[str, Any]:
    if snapshot is None:
        raise ValueError("snapshot is required: {spot, iv_atm_90d}")
    if structure == "auto":
        structure = {
            "mild_correction_-5": "butterfly",
            "deep_correction_-10": "put_spread",
            "crash_-20": "long_put",
        }.get(scenario, "put_spread")

    t_years = hedge_horizon_days / 365.0
    spot = float(snapshot["spot"])
    iv = float(snapshot["iv_atm_90d"])

    if structure == "butterfly":
        legs = _butterfly(spot, t_years, iv, qty)
        structure_label = "put_butterfly"
    elif structure == "put_spread":
        legs = _put_spread(spot, t_years, iv, qty)
        structure_label = "put_spread"
    elif structure == "long_put":
        legs = _long_put(spot, t_years, iv, qty)
        structure_label = "long_put"
    else:
        raise ValueError(f"unknown structure {structure}")

    cost = _net_premium(legs)
    cost_cap = portfolio_notional * max_annual_cost_pct * t_years
    if cost > cost_cap:
        raise ValueError(
            f"hedge cost ${cost:,.0f} exceeds cost cap ${cost_cap:,.0f} "
            f"({max_annual_cost_pct * 100:.1f}% annualized of ${portfolio_notional:,.0f} over {hedge_horizon_days}d)"
        )

    return {
        "underlying": underlying,
        "structure": structure_label,
        "scenario": scenario,
        "spot": spot,
        "horizon_days": hedge_horizon_days,
        "legs": [l for l in legs if l["qty"] > 0],
        "cost_dollar": round(cost, 2),
        "cost_pct_of_portfolio_annualized": (
            round(cost / portfolio_notional / t_years, 4) if t_years > 0 else None
        ),
        "cost_cap_dollar": round(cost_cap, 2),
    }
