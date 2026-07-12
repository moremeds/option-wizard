"""Build SPX / SPY / NDX / QQQ / IWM / VIX macro hedge structures.

Six structures supported:
  - butterfly             -> put butterfly centered at -5% (legacy; deprecated for tail purpose)
  - put_spread            -> long ATM / short -10% put spread (100% win-rate but high carry)
  - long_put              -> single long put, delta-targeted or pct-targeted
  - vix_call_ladder       -> VIX 30-DTE long calls at K=25, 35, 45 (no shorts)
  - iwm_putspread         -> IWM ATM/-10% put spread (cross-index variant)
  - qqq_longput           -> QQQ -10% long put (tech-catalyst variant)

Forbidden:
  - put_ratio_backspread  -> raises ValueError citing Pitfall 03

Regime gates (optional `regime_check` in snapshot):
  - vix_call_ladder requires VIX9D/VIX >= 1.04 AND VIX < 20
  - iwm_putspread requires VVIX > 130 (HY OAS rising recommended; not auto-enforced)
  - put_spread (when tactical_window_days unset) requires projected
    annual carry <= 5% NLV

Backward-compatible scenario auto-routing:
  - mild_correction_-5  -> put butterfly
  - deep_correction_-10 -> put spread
  - crash_-20           -> long put (pct-targeted by default, delta-targeted if `target_delta` set)

Cost cap enforced: total premium <= portfolio_notional *
max_annual_cost_pct * (horizon_days / 365).

Empirical basis: references/research/2026-06-10-convex-macro-hedges.md
Framework:       references/macro-hedge-convexity.md
Pitfall 03:      references/pitfalls/03-ratio-backspreads-not-tail-hedges.md
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

# ─── Empirical thresholds (Pass-6 confidence-calibration extraction) ────
# These are RESEARCH artifacts, not BSM derivations. The values come from
# references/research/2026-06-10-convex-macro-hedges.md §11 (7-event panel
# 2011-2025). Move them here so the math layer has a single auditable
# source of truth + the citation lives with the number, not orphaned in
# error strings.
#
# WARNING: changing any value here changes the gate behavior of every
# structure that fires its branch. Treat as load-bearing constants;
# changes require backtest evidence, not "this looks better."

# VIX9D / VIX ratio at which the short-end term structure has inverted
# enough to mark a deployable vol-event entry. Anchored to 6/7 events at
# T-5 (2011-08 US downgrade, 2018-02 vol-mageddon, 2018-10 Q4 drawdown,
# 2020-03 COVID-1, 2022 Fed-hike cycle, 2024-08 JPY unwind; miss: 2015-08
# China Black Monday — FX-driven, equity vol stayed compressed).
VIX_TERM_INVERSION_RATIO = 1.04

# VIX absolute level above which long-vol entry is past peak (COVID-2
# precedent: VIX 35 → 80 was money-losing despite continued index decline
# because entering long-vol at peak vol mean-reverts against you).
VIX_CALL_LADDER_VIX_CEILING = 20.0

# VVIX level above which fast-deleveraging regime activates IWM-outperforms
# -SPX-as-hedge. COVID-1 hit 200+, JPY 2024 unwind hit 145-155, calm
# regimes sit 90-110. 130 is the empirical threshold between "regular
# correction" and "deleveraging cascade" per the 7-event panel.
VVIX_FAST_DELEVERAGING_THRESHOLD = 130.0

# Projected-annualized carry above which put_spread / iwm_putspread are
# REFUSED unless caller passes tactical_window_days explicitly. 5% is the
# trader's risk budget for tactical (1-3 week) deployments — anything
# higher should be a standing hedge using long_put with target_delta=0.05
# instead.
TACTICAL_CARRY_CEILING = 0.05

# ─── Black-Scholes pricing ─────────────────────────────────


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


def _bs_call(
    spot: float, strike: float, t_years: float, r: float, sigma: float
) -> float:
    """Black-Scholes call price. Used for VIX call structures."""
    if t_years <= 0 or sigma <= 0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    return spot * norm.cdf(d1) - strike * math.exp(-r * t_years) * norm.cdf(d2)


def _bs_put_delta(
    spot: float, strike: float, t_years: float, r: float, sigma: float
) -> float:
    """Put delta (negative). Used for delta-targeted strike selection."""
    if t_years <= 0 or sigma <= 0:
        return -1.0 if strike > spot else 0.0
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    return norm.cdf(d1) - 1.0


def _solve_strike_for_put_delta(
    spot: float,
    target_delta_magnitude: float,
    t_years: float,
    r: float,
    sigma: float,
) -> float:
    """Find OTM put strike whose |delta| matches target. Returns strike.

    target_delta_magnitude is a positive number (e.g., 0.05 = 5-delta put).
    Walks DOWN from spot in 0.5%-of-spot steps until |delta| <= target.
    Resolution good enough for hedge sizing; live execution rounds to the
    nearest listed strike anyway.
    """
    if not 0.001 < target_delta_magnitude < 0.5:
        raise ValueError(
            f"target_delta_magnitude must be in (0.001, 0.5); got {target_delta_magnitude}"
        )
    step = spot * 0.005
    strike = spot
    for _ in range(400):  # max walk 200% of spot — far past any realistic 5d strike
        delta = _bs_put_delta(spot, strike, t_years, r, sigma)
        if abs(delta) <= target_delta_magnitude:
            return strike
        strike -= step
        if strike <= 0:
            # Degenerate: walked the strike below zero without ever
            # crossing target_delta. Only happens with corrupt inputs
            # (sigma effectively 0 OR t_years near 0 OR target unreachable).
            # Returning a sub-pennystock "strike" silently passes garbage
            # downstream — raise so the caller sees the bad input.
            raise ValueError(
                f"target_delta_magnitude={target_delta_magnitude} is "
                f"unreachable at spot={spot}, sigma={sigma}, "
                f"t_years={t_years} — strike walked below zero. "
                f"Check that IV is non-trivially positive and the hedge "
                f"horizon is at least a week."
            )
    return strike


# ─── Chain pricing (puts + calls) ───────────────────────────


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
    """Price one put leg via chain mid if available, BSM otherwise."""
    if chain and chain_expiry:
        strike_pct = round(strike_dollar / spot, 4)
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


def _price_call_leg(
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
    """Price one call leg via chain mid if available, BSM otherwise.

    Used for VIX call structures. The chain key is strike_pct = strike /
    spot — for VIX with spot ~ 17 and strike 25, strike_pct = 1.47.
    """
    if chain and chain_expiry:
        strike_pct = round(strike_dollar / spot, 4)
        mid = read_chain_mid(chain, chain_expiry, strike_pct, "call")
        if mid is not None:
            return mid, chain_leg_provenance(
                value=mid,
                chain_source=chain_source,
                expiry=chain_expiry,
                strike_pct=strike_pct,
                right="call",
                field="mid",
                timestamp=chain_timestamp,
            )
    price = _bs_call(spot, strike_dollar, t_years, 0.04, iv)
    strike_pct_of_spot = strike_dollar / spot * 100
    # Empirical calm-regime calibration (2026-06-10, vix_calibration_history.json,
    # VIX9D/VIX = 0.978 — NOT inverted):
    #   K=25 (≈122% spot) → real mid 22% above BSM(VVIX)   [source: UW `theo`]
    #   K=35 (≈171% spot) → real mid 78% above BSM(VVIX)   [source: `last_price`, T-1]
    #   K=45 (≈220% spot) → real mid 96% above BSM(VVIX)   [source: `last_price`, T-1]
    # K=25 number is intraday model-fit (UW `theo`); K=35/K=45 numbers are
    # derived from end-of-day `last_price` (stale by design) — treat the
    # deep-OTM brackets as lower bounds with wider uncertainty. Inversion
    # regimes likely widen the gap further (TBD on next VIX9D/VIX > 1.04 event).
    # Bucket boundaries align with the 2026-06-10 calibration points:
    #   K=25  (143% spot)  → 1.22×
    #   K=35  (~200% spot) → 1.78×
    #   K=45  (~220% spot) → 1.96×  ← last calibrated point
    # Anything > 250% is EXTRAPOLATION beyond data — flagged in the label.
    if strike_pct_of_spot > 250:
        approx_multiplier = "~2× (extrapolated — no calibration beyond K≈220% spot)"
    elif strike_pct_of_spot > 175:
        approx_multiplier = "~1.8-2×"
    elif strike_pct_of_spot > 150:
        approx_multiplier = "~1.5-1.8×"
    else:
        approx_multiplier = "~1.2-1.3×"
    return price, fallback_provenance(
        value=price,
        reason=(
            f"BSM fallback — chain missing call at strike ${strike_dollar:.2f} "
            f"({strike_pct_of_spot:.0f}% spot); cost estimate uses VVIX-as-IV "
            f"{iv * 100:.0f}%. Calibration (2026-06-10 calm regime): real mid "
            f"≈ {approx_multiplier} this BSM estimate due to VIX call skew + "
            f"VX-futures-vs-spot basis (Pitfall 01). Pull live UW chain to "
            f"replace this estimate before sizing the trade."
        ),
    )


def _resolve_chain_context(
    snapshot: dict, hedge_horizon_days: int
) -> tuple[dict | None, str, str | None, str | None]:
    """Pull (chain, chain_source, nearest_expiry, expiry_timestamp) from
    the snapshot for the macro hedge tenor."""
    chain = snapshot.get("chain")
    chain_source = snapshot.get("chain_source", "UW")
    if not chain:
        return None, chain_source, None, None
    tenor_months = max(1, round(hedge_horizon_days / 30))
    quote_start_iso = snapshot.get("spot_timestamp")
    if quote_start_iso is None:
        from datetime import datetime, timezone

        quote_start_iso = datetime.now(timezone.utc).isoformat()
    try:
        expiry = nearest_expiry_to_tenor(chain, tenor_months, quote_start_iso)
    except ValueError:
        return None, chain_source, None, None
    timestamp = snapshot.get("chain_timestamps", {}).get(expiry)
    return chain, chain_source, expiry, timestamp


# ─── Regime gating ──────────────────────────────────────────


def _check_regime_gate(structure: str, regime: dict | None) -> None:
    """Validate that the requested structure matches the regime.

    Per references/macro-hedge-convexity.md decision tree, each structure
    has empirical regime preconditions. If `regime` is supplied AND the
    gate fails, raise ValueError naming the gate. If `regime` is absent,
    skip — orchestrator may be in research/backtest mode.

    Gates are intentionally STRICT — caller can override by not passing
    regime_check at all. The point is to surface mistakes when the
    full snapshot IS available.
    """
    if regime is None:
        return

    if structure == "vix_call_ladder":
        vix = regime.get("vix")
        vix9d = regime.get("vix9d")
        if vix is None or vix9d is None:
            raise ValueError(
                "vix_call_ladder gate requires regime_check.vix and "
                "regime_check.vix9d — both missing"
            )
        ratio = vix9d / vix
        if ratio < VIX_TERM_INVERSION_RATIO:
            raise ValueError(
                f"vix_call_ladder gate FAILED: VIX9D/VIX = {ratio:.3f} "
                f"(needs >= {VIX_TERM_INVERSION_RATIO}). Per "
                f"macro-hedge-convexity.md, deploy only when the short-end "
                f"term inverts. Current ratio means no near-term event "
                f"premium loaded — VIX ladder will carry ~4.5% NLV/yr "
                f"with no payoff."
            )
        if vix >= VIX_CALL_LADDER_VIX_CEILING:
            raise ValueError(
                f"vix_call_ladder gate FAILED: VIX = {vix:.1f} (needs < "
                f"{VIX_CALL_LADDER_VIX_CEILING}). At VIX >= "
                f"{VIX_CALL_LADDER_VIX_CEILING} the convexity premium is "
                f"already priced; see COVID-2 case study — entering "
                f"long-vol at peak vol loses money even if index keeps "
                f"dropping."
            )
        return

    if structure == "iwm_putspread":
        vvix = regime.get("vvix")
        if vvix is None:
            raise ValueError("iwm_putspread gate requires regime_check.vvix — missing")
        if vvix <= VVIX_FAST_DELEVERAGING_THRESHOLD:
            raise ValueError(
                f"iwm_putspread gate FAILED: VVIX = {vvix:.1f} (needs > "
                f"{VVIX_FAST_DELEVERAGING_THRESHOLD}). IWM outperforms "
                f"SPX as hedge only in fast-deleveraging regimes "
                f"(COVID-1, JPY unwind); otherwise IV ratio is already "
                f"loaded and SPX is cheaper. Use SPX put spread instead."
            )
        return

    if structure == "qqq_longput":
        tech_catalyst = regime.get("tech_specific_catalyst", False)
        if not tech_catalyst:
            raise ValueError(
                "qqq_longput gate FAILED: regime_check.tech_specific_catalyst "
                "is False. QQQ beats SPX as hedge only when catalyst is "
                "tech-specific (FOMC hawkish, semi cycle, AI rotation). "
                "Empirically only 2022 hike-cycle qualified out of 5 events."
            )
        return

    if structure == "put_ratio_backspread":
        raise ValueError(
            "put_ratio_backspread is FORBIDDEN — see "
            "references/pitfalls/03-ratio-backspreads-not-tail-hedges.md. "
            "The structure has a max-loss valley between short and long "
            "strikes that aligns with the typical 5-12% M7 vol-shock "
            "drawdown range. Win rate 20-40% across 5 anchor events; "
            "loses $3-21K per $1M when it misses. Use long_put or "
            "put_spread instead."
        )


# ─── Convexity scorecard ────────────────────────────────────


def _compute_convexity_scorecard(
    legs: list[dict],
    spot: float,
    t_years: float,
    iv: float,
    *,
    is_call_structure: bool = False,
) -> dict:
    """Compute payoff at -5%, -10%, -20%, -30% scenarios and the
    payoff-per-cost-dollar ratio.

    For put structures, "scenario" = downside spot drop. For VIX call
    structures, "scenario" = VIX SPIKE (positive moves on the underlying).
    The scoreboard semantics are reversed for VIX calls so the trader
    reads "+100% VIX = $X payoff."

    Payoff at scenario assumes immediate mark (T-0 valuation at new spot)
    with IV held flat — this UNDERSTATES payoff in fast crashes (IV
    actually expands) and OVERSTATES in calm grinds (IV stays low). Treat
    as directional ranking, not absolute P&L forecast.
    """
    if is_call_structure:
        scenarios_pct = [0.50, 1.00, 2.00, 4.00]  # VIX +50%, +100%, +200%, +400%
        pricer = _bs_call
    else:
        scenarios_pct = [-0.05, -0.10, -0.20, -0.30]
        pricer = _bs_put

    multiplier = 100
    initial_cost = 0.0
    for leg in legs:
        sign = -1 if leg["action"] == "buy" else 1
        initial_cost += -sign * leg["limit_price"] * leg["qty"] * multiplier

    scorecard = {"initial_cost_dollar": round(initial_cost, 2), "scenarios": {}}
    for pct in scenarios_pct:
        scen_spot = spot * (1 + pct)
        payoff = 0.0
        for leg in legs:
            sign = 1 if leg["action"] == "buy" else -1
            # Mark each leg at the new spot with flat IV
            leg_value = pricer(scen_spot, leg["strike"], t_years, 0.04, iv)
            payoff += sign * leg_value * leg["qty"] * multiplier
        net = payoff - initial_cost
        ratio = (net / initial_cost) if initial_cost > 0 else None
        label = f"{int(pct * 100):+d}%"
        scorecard["scenarios"][label] = {
            "scenario_spot": round(scen_spot, 2),
            "payoff_dollar": round(payoff, 2),
            "net_pnl_dollar": round(net, 2),
            "payoff_per_cost_dollar": round(ratio, 2) if ratio is not None else None,
        }
    # Max convexity = best payoff_per_cost_dollar across scenarios
    ratios = [
        s["payoff_per_cost_dollar"]
        for s in scorecard["scenarios"].values()
        if s["payoff_per_cost_dollar"] is not None
    ]
    scorecard["max_convexity_ratio"] = round(max(ratios), 2) if ratios else None

    # VIX-call calibration disclosure (F1 from review-cycle math audit;
    # direction-corrected by Pass-2 C-MED1).
    # The scorecard above prices BOTH entry cost AND scenario marks via
    # BSM-with-VVIX-as-IV. Per 2026-06-10 calibration, real VIX call mids
    # run ≈ 1.2-2× BSM in calm regimes (K-dependent — see _price_call_leg
    # docstring). Net effect on payoff_per_cost_dollar ratio:
    #   - pricing_source='bsm' (no chain available): BOTH entry cost AND
    #     scenario payoff are BSM-under-stated by similar factors. At deep
    #     scenarios (+200%/+400%) payoff ≈ intrinsic so payoff is close to
    #     real, but cost is still BSM-under by ~2× → ratio OVERSTATED at
    #     deep scenarios. At small scenarios (+50%) both biased similarly
    #     → ratio approximately preserved.
    #   - pricing_source='chain': entry cost is REAL chain mid (correctly
    #     calibrated). Scenario payoff is still BSM-based, which UNDER-
    #     states real mark at all spike depths (especially small spikes
    #     where time value dominates). → ratio is a LOWER bound; real
    #     convexity is HIGHER than reported.
    # Comparing VIX-ladder max_convexity_ratio directly to put-ladder
    # ratios (which use chain-mid entry cost when available) is therefore
    # apples-to-oranges. The trader MUST read the note before picking
    # between structures on convexity alone.
    if is_call_structure:
        scorecard["cost_calibration_note"] = (
            "VIX ladder scorecard uses BSM(VVIX-as-IV) for both entry cost "
            "and scenario marks. Per 2026-06-10 calm-regime calibration, "
            "real VIX call mids are ≈ 1.2-2× BSM (K-dependent). Ratio "
            "interpretation depends on pricing_source: "
            "(a) pricing_source='bsm' → at deep scenarios (+200%/+400%), "
            "max_convexity_ratio OVERSTATES real convexity by ~2× because "
            "entry cost is BSM-under but payoff is intrinsic-dominated. "
            "Halve max_convexity_ratio before comparing to put structures. "
            "(b) pricing_source='chain' → entry cost is real but scenario "
            "marks are BSM-under at all depths, so max_convexity_ratio is "
            "a LOWER bound; real convexity is higher than reported. Use as "
            "conservative floor when comparing structures."
        )
    return scorecard


# ─── Leg builders ───────────────────────────────────────────


def _build_put_leg(
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


def _build_call_leg(
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
    price, provenance = _price_call_leg(
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
        "right": "call",
        "action": action,
        "strike": strike_dollar,
        "qty": qty,
        "limit_price": price,
        "mid_source": provenance["source"],
        "mid_provenance": provenance,
    }


# ─── Structure builders ─────────────────────────────────────


def _butterfly(
    spot, t_years, iv, qty, chain, chain_source, chain_expiry, chain_timestamp
):
    """Put butterfly -2%/-5%/-8%. Legacy structure; deprecated for tail purpose
    per references/pitfalls/03 — body at -5% gets passed through in fast crashes."""
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
        _build_put_leg(strike_dollar=wing_up, action="buy", qty=qty, **ctx),
        _build_put_leg(strike_dollar=body, action="sell", qty=2 * qty, **ctx),
        _build_put_leg(strike_dollar=wing_dn, action="buy", qty=qty, **ctx),
    ]


def _put_spread(
    spot, t_years, iv, qty, chain, chain_source, chain_expiry, chain_timestamp
):
    """ATM/-10% put spread. 100% win-rate workhorse but carries 10-12% NLV/yr.
    Tactical deployment only; gated by tactical_window_days at the entry point."""
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
        _build_put_leg(strike_dollar=long_strike, action="buy", qty=qty, **ctx),
        _build_put_leg(strike_dollar=short_strike, action="sell", qty=qty, **ctx),
    ]


def _long_put(
    spot,
    t_years,
    iv,
    qty,
    chain,
    chain_source,
    chain_expiry,
    chain_timestamp,
    *,
    target_delta: float | None = None,
    pct_strike: float = 0.90,
):
    """Single long put. Default fixed pct strike (backward compat); when
    target_delta is provided, walk to that delta instead.

    Empirical primary standing hedge — carries 0.01-0.54% NLV/yr at
    5-delta strike, monthly roll."""
    if target_delta is not None:
        strike = _solve_strike_for_put_delta(spot, target_delta, t_years, 0.04, iv)
    else:
        strike = spot * pct_strike
    ctx = dict(
        spot=spot,
        t_years=t_years,
        iv=iv,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=chain_expiry,
        chain_timestamp=chain_timestamp,
    )
    return [_build_put_leg(strike_dollar=strike, action="buy", qty=qty, **ctx)]


def _vix_call_ladder(
    vix_underlying,
    t_years,
    vvix_iv,
    qty,
    chain,
    chain_source,
    chain_expiry,
    chain_timestamp,
    *,
    strikes: tuple[float, ...] = (25.0, 35.0, 45.0),
):
    """VIX 30-DTE long calls at K=25, 35, 45 — three legs all LONG, no shorts.

    Per Pitfall 01, VIX call SPREADS suffer cross-leg vega cancellation +
    back-month VX-futures basis. The ladder avoids both: pure stacked
    vega/gamma, each strike activates at the next vol shelf.

    Underlying is VIX (spot or VX1 proxy = (VIX+VIX3M)/2). IV is VVIX/100."""
    ctx = dict(
        spot=vix_underlying,
        t_years=t_years,
        iv=vvix_iv,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=chain_expiry,
        chain_timestamp=chain_timestamp,
    )
    return [
        _build_call_leg(strike_dollar=k, action="buy", qty=qty, **ctx) for k in strikes
    ]


def _iwm_putspread(
    spot, t_years, iv, qty, chain, chain_source, chain_expiry, chain_timestamp
):
    """IWM ATM/-10% put spread — cross-index variant. Beats SPX put spread
    by $30-60K per $1M in fast-deleveraging regimes (COVID-1, JPY unwind)
    where small-cap drawdown ratio exceeded IV ratio."""
    # Mechanically identical to SPX put_spread; separate builder so the
    # cost cap + scorecard can be computed against IWM spot specifically.
    return _put_spread(
        spot, t_years, iv, qty, chain, chain_source, chain_expiry, chain_timestamp
    )


def _qqq_longput(
    spot,
    t_years,
    iv,
    qty,
    chain,
    chain_source,
    chain_expiry,
    chain_timestamp,
    *,
    target_delta: float | None = None,
    pct_strike: float = 0.90,
):
    """QQQ long put — tech-catalyst variant. Beats SPX long put when
    catalyst is tech-specific (FOMC hawkish, semi cycle, AI rotation)
    AND VXN-vs-VIX ratio < 1.5 (IV not yet pricing the tech beta)."""
    return _long_put(
        spot,
        t_years,
        iv,
        qty,
        chain,
        chain_source,
        chain_expiry,
        chain_timestamp,
        target_delta=target_delta,
        pct_strike=pct_strike,
    )


# ─── Net premium ───────────────────────────────────────────


def _net_premium(legs: list[dict]) -> float:
    total = 0.0
    multiplier = 100
    for leg in legs:
        sign = -1 if leg["action"] == "buy" else 1
        total += sign * leg["limit_price"] * leg["qty"] * multiplier
    return (
        -total
    )  # convert net credit (positive in our sign convention) to net cost paid


def _resolve_pricing_source(legs: list[dict]) -> str:
    sources = {leg["mid_source"] for leg in legs}
    if sources == {"UW"} or sources == {"IB"} or sources == {"TV"}:
        return "chain"
    if "fallback" in sources and len(sources) > 1:
        return "mixed"
    return "bsm"


# ─── Main entry point ──────────────────────────────────────


def build_macro_hedge(
    portfolio_notional: float,
    hedge_horizon_days: int,
    scenario: str,
    underlying: str = "SPX",
    structure: str = "auto",
    snapshot: dict | None = None,
    max_annual_cost_pct: float = 0.015,
    qty: int = 1,
    *,
    target_delta: float | None = None,
    tactical_window_days: int | None = None,
) -> dict[str, Any]:
    """Build a macro hedge structure and return legs + cost + scorecard.

    Parameters
    ----------
    portfolio_notional : float
        NLV in dollars; used for cost-cap enforcement and scorecard sizing.
    hedge_horizon_days : int
        Tenor in days (used to compute t_years and select chain expiry).
    scenario : str
        Backward-compat routing key. Values: "mild_correction_-5",
        "deep_correction_-10", "crash_-20", or "custom" when caller
        explicitly picks structure.
    underlying : str
        "SPX" (default), "SPY", "QQQ", "IWM", "RUT", "NDX" for equity
        structures; "VIX" for VIX-based structures.
    structure : str
        "auto" (default — picks from scenario), "butterfly", "put_spread",
        "long_put", "vix_call_ladder", "iwm_putspread", "qqq_longput",
        or "put_ratio_backspread" (raises ValueError citing Pitfall 03).
    snapshot : dict
        Must contain "spot" and "iv_atm_90d" for equity structures.
        For VIX structures, must contain "vix_spot" (or "spot" treated as
        VIX), "vix_underlying" (VX1 proxy, optional — defaults to vix_spot),
        and "vvix" (used as VIX option IV).
        Optional: "chain", "chain_source", "spot_timestamp",
        "chain_timestamps" — enables chain-mid pricing.
        Optional: "regime_check" dict — enables regime-gate enforcement.
    max_annual_cost_pct : float
        Default 0.015 (1.5% NLV/yr) per trader profile.
    qty : int
        Contract multiplier for each leg (default 1; overridden internally
        for sizing). For VIX ladder, qty applies to each of 3 long-call
        legs.
    target_delta : float, optional
        When set on long_put or qqq_longput, walks strike to match
        |delta| = target_delta. Recommended: 0.05 for 5-delta tail hedge.
        Backward compat: if None, uses fixed -10% pct strike.
    tactical_window_days : int, optional
        When set, enables put_spread / iwm_putspread / vix_call_ladder
        without the projected-carry check. Required for these tactical
        structures unless the projected annual carry stays under 5% NLV.

    Returns
    -------
    dict with: underlying, structure, scenario, spot, horizon_days, legs,
    cost_dollar, cost_pct_of_portfolio_annualized, cost_cap_dollar,
    pricing_source, convexity_scorecard, regime_gate_status.

    Raises
    ------
    ValueError
        - Cost exceeds annualized cap
        - structure="put_ratio_backspread" (forbidden, see Pitfall 03)
        - Regime gate fails (when regime_check supplied)
        - put_spread without tactical_window_days when projected carry > 5%
    """
    if snapshot is None:
        raise ValueError("snapshot is required: {spot, iv_atm_90d}")

    # Pass-3 A1 guard: hedge_horizon_days=0 silently produces a degenerate
    # hedge (BSM = intrinsic = 0 at ATM; solver returns spot since |delta|=0
    # at t=0; cost=0 trivially passes the cost cap). Trader sees a result
    # that looks valid but pays nothing. Refuse at entry so a typo
    # (`--horizon-days 0` instead of `60`) doesn't slip through.
    if hedge_horizon_days <= 0:
        raise ValueError(
            f"hedge_horizon_days must be > 0, got {hedge_horizon_days}. "
            f"A zero-or-negative horizon collapses BSM to intrinsic and "
            f"produces a meaningless zero-cost result — likely a typo or "
            f"upstream snapshot bug."
        )

    # Auto-route scenario → structure (backward compat)
    if structure == "auto":
        structure = {
            "mild_correction_-5": "butterfly",
            "deep_correction_-10": "put_spread",
            "crash_-20": "long_put",
        }.get(scenario, "put_spread")

    # Regime gate (raises ValueError if fail)
    regime_check = snapshot.get("regime_check")
    _check_regime_gate(structure, regime_check)

    # Deprecation note for butterfly when used outside its sanctioned scenario
    deprecation_warning = None
    if structure == "butterfly" and scenario != "mild_correction_-5":
        deprecation_warning = (
            "put_butterfly is DEPRECATED for tail-hedge purpose (40% win rate, "
            "body strike at -5% gets passed through in fast crashes per "
            "Pitfall 03). Keep only for the literal `mild_correction_-5` "
            "scenario. Consider `long_put` (delta-targeted) or `put_spread` "
            "(tactical) instead."
        )

    t_years = hedge_horizon_days / 365.0

    # Resolve underlying spot + IV based on structure
    if structure == "vix_call_ladder":
        vix_spot = float(snapshot.get("vix_spot", snapshot.get("spot")))
        vix_underlying = float(snapshot.get("vix_underlying", vix_spot))
        vvix_iv = float(snapshot["vvix"]) / 100.0 if "vvix" in snapshot else 1.0
        spot = vix_underlying
        iv = vvix_iv
    else:
        spot = float(snapshot["spot"])
        iv = float(snapshot["iv_atm_90d"])

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
        legs = _long_put(**builder_kwargs, target_delta=target_delta)
        structure_label = (
            f"long_put_delta_{int(target_delta * 100)}"
            if target_delta is not None
            else "long_put"
        )
    elif structure == "vix_call_ladder":
        legs = _vix_call_ladder(
            vix_underlying=spot,
            t_years=t_years,
            vvix_iv=iv,
            qty=qty,
            chain=chain,
            chain_source=chain_source,
            chain_expiry=chain_expiry,
            chain_timestamp=chain_timestamp,
        )
        structure_label = "vix_call_ladder_25_35_45"
    elif structure == "iwm_putspread":
        legs = _iwm_putspread(**builder_kwargs)
        structure_label = "iwm_put_spread"
    elif structure == "qqq_longput":
        legs = _qqq_longput(**builder_kwargs, target_delta=target_delta)
        structure_label = (
            f"qqq_long_put_delta_{int(target_delta * 100)}"
            if target_delta is not None
            else "qqq_long_put"
        )
    elif structure == "put_ratio_backspread":
        # Defense in depth — the regime gate above already rejected this
        # without a regime_check passed; this branch keeps the error
        # consistent when regime_check is None.
        raise ValueError(
            "put_ratio_backspread is FORBIDDEN — see "
            "references/pitfalls/03-ratio-backspreads-not-tail-hedges.md."
        )
    else:
        raise ValueError(f"unknown structure {structure}")

    cost = _net_premium(legs)

    # Tactical-window guard for high-carry structures
    if structure in ("put_spread", "iwm_putspread") and tactical_window_days is None:
        projected_annual_pct = (
            (cost / portfolio_notional) / t_years if t_years > 0 else 0
        )
        if projected_annual_pct > TACTICAL_CARRY_CEILING:
            raise ValueError(
                f"{structure} projected annualized carry "
                f"{projected_annual_pct * 100:.1f}% NLV exceeds "
                f"{TACTICAL_CARRY_CEILING * 100:.0f}% — this structure is "
                f"tactical only (1-3 week deployment). Pass "
                f"`tactical_window_days=14` to confirm intent. "
                f"Standing hedge alternative: long_put with target_delta=0.05."
            )

    cost_cap = portfolio_notional * max_annual_cost_pct * t_years
    pricing_source = _resolve_pricing_source(legs)

    if cost > cost_cap:
        raise ValueError(
            f"hedge cost ${cost:,.0f} exceeds cost cap ${cost_cap:,.0f} "
            f"({max_annual_cost_pct * 100:.1f}% annualized of "
            f"${portfolio_notional:,.0f} over {hedge_horizon_days}d). "
            f"pricing_source={pricing_source!r} — "
            f"{'chain mids' if pricing_source == 'chain' else 'BSM fallback (cost may differ from market)'}"
        )

    scorecard = _compute_convexity_scorecard(
        legs,
        spot,
        t_years,
        iv,
        is_call_structure=(structure == "vix_call_ladder"),
    )

    result: dict[str, Any] = {
        "underlying": underlying,
        "structure": structure_label,
        "scenario": scenario,
        "spot": spot,
        "horizon_days": hedge_horizon_days,
        "legs": [leg for leg in legs if leg["qty"] > 0],
        "cost_dollar": round(cost, 2),
        "cost_pct_of_portfolio_annualized": (
            round(cost / portfolio_notional / t_years, 4) if t_years > 0 else None
        ),
        "cost_cap_dollar": round(cost_cap, 2),
        "pricing_source": pricing_source,
        "convexity_scorecard": scorecard,
    }
    if regime_check is not None:
        result["regime_gate_status"] = "passed"
    if deprecation_warning is not None:
        result["deprecation_warning"] = deprecation_warning
    if tactical_window_days is not None:
        result["tactical_window_days"] = tactical_window_days

    return result
