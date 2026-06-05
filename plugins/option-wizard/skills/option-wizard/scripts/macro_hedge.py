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

from scripts._market import (
    chain_leg_provenance,
    fallback_provenance,
    nearest_expiry_to_tenor,
    read_chain_mid,
)


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


def _price_put_leg(
    spot: float,
    strike_dollar: float,
    t_years: float,
    iv: float,
    *,
    chain: dict | None,
    chain_source: str,
    chain_expiry: str | None,
    chain_timestamp: str | None,
) -> tuple[float, dict[str, Any]]:
    """Price one put leg via chain mid if available, BSM otherwise.

    Returns (price_per_share, provenance_entry). Chain lookup keys by
    strike_pct (= strike_dollar / spot) — caller pre-resolves expiry.
    Falling back to BSM is fine for hedge sizing (cost is a heuristic),
    but provenance flags it so the trader knows the cost estimate is
    approximate.
    """
    if chain and chain_expiry:
        strike_pct = strike_dollar / spot
        mid = read_chain_mid(chain, chain_expiry, strike_pct, "put")
        if mid is not None:
            return mid, chain_leg_provenance(
                value=mid,
                chain_source=chain_source,
                expiry=chain_expiry,
                strike_pct=strike_pct,
                right="put",
                field="mid",
                timestamp=chain_timestamp,
            )
    price = _bs_put(spot, strike_dollar, t_years, 0.04, iv)
    return price, fallback_provenance(
        value=price,
        reason=(
            f"BSM fallback — chain missing put at strike ${strike_dollar:.2f} "
            f"({strike_dollar / spot * 100:.0f}% spot); cost estimate uses "
            f"flat ATM IV {iv * 100:.0f}%."
        ),
    )


def _resolve_chain_context(
    snapshot: dict, hedge_horizon_days: int
) -> tuple[dict | None, str, str | None, str | None]:
    """Pull (chain, chain_source, nearest_expiry, expiry_timestamp) from
    the snapshot for the macro hedge tenor. Returns (None, ...) if no
    chain is present so the legs all fall back to BSM cleanly."""
    chain = snapshot.get("chain")
    chain_source = snapshot.get("chain_source", "UW")
    if not chain:
        return None, chain_source, None, None
    # Convert horizon-days → tenor-months for nearest_expiry_to_tenor.
    # 30-day month is the shared convention with fair_aq_dq / fair_coupon.
    tenor_months = max(1, round(hedge_horizon_days / 30))
    quote_start_iso = snapshot.get("spot_timestamp", "2026-06-05T00:00:00Z")
    try:
        expiry = nearest_expiry_to_tenor(chain, tenor_months, quote_start_iso)
    except ValueError:
        return None, chain_source, None, None
    timestamp = snapshot.get("chain_timestamps", {}).get(expiry)
    return chain, chain_source, expiry, timestamp


def _build_leg(
    *,
    spot: float,
    strike_dollar: float,
    action: str,
    qty: int,
    t_years: float,
    iv: float,
    chain: dict | None,
    chain_source: str,
    chain_expiry: str | None,
    chain_timestamp: str | None,
) -> dict:
    """Build one leg dict with chain-priced mid (if available) plus
    provenance. Centralizes the per-leg construction so all three
    structures share the same chain-vs-BSM fallback logic."""
    price, provenance = _price_put_leg(
        spot=spot,
        strike_dollar=strike_dollar,
        t_years=t_years,
        iv=iv,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=chain_expiry,
        chain_timestamp=chain_timestamp,
    )
    return {
        "right": "put",
        "action": action,
        "strike": strike_dollar,
        "qty": qty,
        "limit_price": price,
        "mid_source": provenance["source"],
        "mid_provenance": provenance,
    }


def _butterfly(
    spot: float,
    t_years: float,
    iv: float,
    qty: int,
    chain: dict | None,
    chain_source: str,
    chain_expiry: str | None,
    chain_timestamp: str | None,
) -> list[dict]:
    """Standard 3-leg put butterfly centered at body strike."""
    body = spot * 0.95
    wing_up = spot * 0.98
    wing_dn = spot * 0.92
    ctx = dict(
        spot=spot,
        t_years=t_years,
        iv=iv,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=chain_expiry,
        chain_timestamp=chain_timestamp,
    )
    return [
        _build_leg(strike_dollar=wing_up, action="buy", qty=qty, **ctx),
        _build_leg(strike_dollar=body, action="sell", qty=2 * qty, **ctx),
        _build_leg(strike_dollar=wing_dn, action="buy", qty=qty, **ctx),
    ]


def _put_spread(
    spot: float,
    t_years: float,
    iv: float,
    qty: int,
    chain: dict | None,
    chain_source: str,
    chain_expiry: str | None,
    chain_timestamp: str | None,
) -> list[dict]:
    long_strike = spot
    short_strike = spot * 0.90
    ctx = dict(
        spot=spot,
        t_years=t_years,
        iv=iv,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=chain_expiry,
        chain_timestamp=chain_timestamp,
    )
    return [
        _build_leg(strike_dollar=long_strike, action="buy", qty=qty, **ctx),
        _build_leg(strike_dollar=short_strike, action="sell", qty=qty, **ctx),
    ]


def _long_put(
    spot: float,
    t_years: float,
    iv: float,
    qty: int,
    chain: dict | None,
    chain_source: str,
    chain_expiry: str | None,
    chain_timestamp: str | None,
) -> list[dict]:
    strike = spot * 0.90
    ctx = dict(
        spot=spot,
        t_years=t_years,
        iv=iv,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=chain_expiry,
        chain_timestamp=chain_timestamp,
    )
    return [_build_leg(strike_dollar=strike, action="buy", qty=qty, **ctx)]


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

    # Phase C: prefer listed mid from chain; fall back to BSM per leg.
    chain, chain_source, chain_expiry, chain_timestamp = _resolve_chain_context(
        snapshot, hedge_horizon_days
    )

    builder_kwargs = dict(
        spot=spot,
        t_years=t_years,
        iv=iv,
        qty=qty,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=chain_expiry,
        chain_timestamp=chain_timestamp,
    )
    if structure == "butterfly":
        legs = _butterfly(**builder_kwargs)
        structure_label = "put_butterfly"
    elif structure == "put_spread":
        legs = _put_spread(**builder_kwargs)
        structure_label = "put_spread"
    elif structure == "long_put":
        legs = _long_put(**builder_kwargs)
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

    # Per-output `pricing_source` rollup: 'chain' if every leg priced off
    # the chain, 'mixed' if some legs fell back to BSM, 'bsm' if no legs
    # used the chain. Lets the trader see at a glance whether the cost
    # estimate is market-real or model-approximated.
    sources = {leg["mid_source"] for leg in legs}
    if sources == {"UW"} or sources == {"IB"}:
        pricing_source = "chain"
    elif "fallback" in sources and len(sources) > 1:
        pricing_source = "mixed"
    else:
        pricing_source = "bsm"

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
        "pricing_source": pricing_source,
    }
