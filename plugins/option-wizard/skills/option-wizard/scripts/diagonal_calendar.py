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

from scripts._market import (
    chain_leg_provenance,
    fallback_provenance,
    read_chain_mid,
)

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


def _bs_put(
    spot: float, strike: float, t_years: float, r: float, sigma: float
) -> float:
    """BSM put price (same closed form as scripts.macro_hedge._bs_put)."""
    if t_years <= 0 or sigma <= 0:
        return max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    return strike * math.exp(-r * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def _build_leg_bsm(
    *, spot: float, strike: float, action: str, qty: int, t_years: float, iv: float
) -> dict[str, Any]:
    """Build one leg dict using BSM mid (no chain available)."""
    price = _bs_put(spot, strike, t_years, _R, iv)
    greeks = _bs_put_greeks(spot, strike, t_years, _R, iv)
    return {
        "right": "put",
        "action": action,
        "strike": strike,
        "qty": qty,
        "limit_price": round(price, 2),
        "mid_source": "fallback",
        "mid_provenance": {
            "source": "fallback",
            "reason": f"BSM mid (no chain); IV={iv * 100:.0f}%, DTE={t_years * 365:.0f}",
        },
        "greeks": greeks,
        "greeks_source": "bsm",
    }


def _read_chain_greeks(chain: dict, expiry: str, strike_pct: float) -> dict | None:
    """Read greeks dict from chain[expiry][matching_strike_pct]['put'] if
    present. Uses same 0.005 tolerance as read_chain_mid. Returns None if
    not provided — caller falls back to BSM recompute."""
    expiry_chain = chain.get(expiry, {})
    for k_pct, payload in expiry_chain.items():
        if abs(k_pct - strike_pct) <= 0.005:
            put_leg = payload.get("put", {})
            g = put_leg.get("greeks")
            if g and all(k in g for k in ("delta", "gamma", "theta", "vega")):
                return g
    return None


def _build_leg_chain_first(
    *,
    spot: float,
    strike: float,
    action: str,
    qty: int,
    t_years: float,
    iv: float,
    chain: dict | None,
    chain_source: str,
    chain_expiry: str | None,
    chain_timestamp: str | None,
) -> dict[str, Any]:
    """Build leg with chain mid + chain greeks if available, BSM fallback otherwise.

    Per hard rule #2 'if a source serves it directly, never recompute':
    when chain provides greeks, USE them. BSM recompute only when chain
    leg lacks greeks (mid + iv but no delta/gamma/theta/vega)."""
    if chain and chain_expiry:
        strike_pct = round(strike / spot, 4)
        mid = read_chain_mid(chain, chain_expiry, strike_pct, "put")
        if mid is not None:
            provenance = chain_leg_provenance(
                value=mid,
                chain_source=chain_source,
                expiry=chain_expiry,
                strike_pct=strike_pct,
                right="put",
                field="mid",
                timestamp=chain_timestamp,
            )
            chain_greeks = _read_chain_greeks(chain, chain_expiry, strike_pct)
            if chain_greeks is not None:
                greeks = chain_greeks
                greeks_source = chain_source
            else:
                greeks = _bs_put_greeks(spot, strike, t_years, _R, iv)
                greeks_source = "bsm_fallback"
            return {
                "right": "put",
                "action": action,
                "strike": strike,
                "qty": qty,
                "limit_price": round(mid, 2),
                "mid_source": chain_source,
                "mid_provenance": provenance,
                "greeks": greeks,
                "greeks_source": greeks_source,
            }
    return _build_leg_bsm(
        spot=spot, strike=strike, action=action, qty=qty, t_years=t_years, iv=iv
    )


def _resolve_chain_expiries(
    snapshot: dict, dte_short: int, dte_long: int
) -> tuple[dict | None, str, str | None, str | None, str | None, str | None]:
    """Return (chain, chain_source, short_expiry, short_ts, long_expiry, long_ts)
    or (None, ..., None, None, None, None) if no chain. Picks nearest listed
    expiry by sorted iso key (caller builds chain with exactly the expiries
    we want priced)."""
    chain = snapshot.get("chain")
    chain_source = snapshot.get("chain_source", "UW")
    if not chain:
        return None, chain_source, None, None, None, None
    timestamps = snapshot.get("chain_timestamps", {})
    sorted_expiries = sorted(chain.keys())
    if len(sorted_expiries) < 2:
        return None, chain_source, None, None, None, None
    short_expiry = sorted_expiries[0]
    long_expiry = sorted_expiries[-1]
    return (
        chain,
        chain_source,
        short_expiry,
        timestamps.get(short_expiry),
        long_expiry,
        timestamps.get(long_expiry),
    )


def _snap_to_listed_strike(target_k: float, spot: float, expiry_chain: dict) -> float:
    """Given a theoretical strike K_theo, find the listed strike (in $) closest
    to it from the chain's strike grid. Chain keys are strike_pct floats."""
    if not expiry_chain:
        return target_k
    listed_dollars = [k_pct * spot for k_pct in expiry_chain.keys()]
    return min(listed_dollars, key=lambda k: abs(k - target_k))


_REGIME_MODE_TABLE = {
    # (vrp_label, iv_rank_bucket) → recommended mode (or None = no sell)
    ("RICH", "high"): "aggressive",
    ("RICH", "mid"): "protective",
    ("NEUTRAL", "high"): "calendar",
    ("NEUTRAL", "mid"): "calendar",
    ("NEUTRAL", "low"): "calendar",
    ("CHEAP", "high"): None,
    ("CHEAP", "mid"): None,
    ("CHEAP", "low"): None,
}


def _regime_check(mode: str, snapshot: dict) -> dict[str, Any]:
    """Compare chosen mode against regime recommendation. Warns but does not abort."""
    vrp = snapshot.get("vrp_label", "NEUTRAL")
    iv_rank = snapshot.get("iv_rank", 50)
    bucket = "high" if iv_rank >= 60 else "mid" if iv_rank >= 30 else "low"
    recommended = _REGIME_MODE_TABLE.get((vrp, bucket))
    matches = recommended == mode
    warning = None
    if not matches and recommended is not None:
        warning = (
            f"VRP={vrp} + IV rank {iv_rank} ({bucket}) suggests {recommended!r} mode; "
            f"chose {mode!r} — proceeds but accept lower expected edge"
        )
    elif recommended is None:
        warning = (
            f"VRP={vrp} indicates no sell-premium regime; chose {mode!r} — "
            f"consider deferring entry until VRP turns NEUTRAL or RICH"
        )
    return {
        "recommended_mode_for_regime": recommended,
        "matches_chosen_mode": matches,
        "warning": warning,
    }


def _pricing_source(legs: list[dict]) -> str:
    """Roll up per-leg mid_source to top-level pricing_source."""
    sources = {leg["mid_source"] for leg in legs}
    if sources in ({"UW"}, {"IB"}):
        return "chain"
    if "fallback" in sources and len(sources) > 1:
        return "mixed"
    return "bsm"


def _net_debit_dollar(legs: list[dict]) -> float:
    """Positive = net debit paid; negative = net credit received. Multiplier 100."""
    total = 0.0
    for leg in legs:
        sign = 1 if leg["action"] == "buy" else -1
        total += sign * leg["limit_price"] * leg["qty"] * 100
    return round(total, 2)


def _max_loss_at_short_expiry(
    legs: list[dict], net_debit: float, dte_long: int, dte_short: int
) -> float:
    """At short-leg expiry, close everything. Per spec §10 #1.

    calendar (Ks=Kl):   worst case S >> K → both worthless → loss = net_debit
    protective (Ks<Kl): worst case S > Kl → both worthless → loss = net_debit.
                        When S < Ks, long put offsets short put dollar-for-
                        dollar in [Ks, Kl] range. Discount-carry correction:
                        long mark at S=0 is Kl·e^(-r·T_remain), not Kl, so
                        protective COULD have a small crash loss if Ks > Kl·DF.
    aggressive (Ks>Kl): worst case S → 0 → long ITM by ~Kl·e^(-r·T_remain),
                        short ITM by Ks. Loss = (Ks - Kl·DF)*100 + net_debit.

    Sign convention: net_debit > 0 = paid; net_debit < 0 = received credit.
    """
    long_leg = next(l for l in legs if l["action"] == "buy")
    short_leg = next(l for l in legs if l["action"] == "sell")
    kl, ks = long_leg["strike"], short_leg["strike"]
    qty = long_leg["qty"]
    t_remain = (dte_long - dte_short) / 365.0
    discount_factor = math.exp(-_R * t_remain)
    long_at_zero = kl * discount_factor

    if ks <= kl:  # calendar OR protective
        # When S >> Kl, both worthless → loss = net_debit.
        # When S << Ks ≤ Kl, long pays Kl·DF, short pays Ks. Loss = max(0, (Ks - Kl·DF)*100).
        crash_loss = (ks - long_at_zero) * 100 * qty if long_at_zero < ks else 0.0
        return max(net_debit, crash_loss + net_debit)
    # aggressive (ks > kl)
    return (ks - long_at_zero) * 100 * qty + net_debit


def _net_greeks(legs: list[dict]) -> dict[str, float]:
    """Sum greeks across legs (sign by action: sell flips). theta_daily in $/day,
    vega in $ per 1pp IV move."""
    net = {"delta": 0.0, "gamma": 0.0, "theta_daily": 0.0, "vega": 0.0}
    for leg in legs:
        sign = 1 if leg["action"] == "buy" else -1
        g = leg["greeks"]
        qty = leg["qty"]
        net["delta"] += sign * g["delta"] * qty
        net["gamma"] += sign * g["gamma"] * qty
        net["theta_daily"] += sign * g["theta"] * qty * 100
        net["vega"] += sign * g["vega"] * qty * 100
    return {k: round(v, 4) for k, v in net.items()}


def _breakevens_at_short_expiry(
    legs: list[dict], iv_long: float, dte_long: int, dte_short: int, spot: float
) -> dict[str, float | None]:
    """Find ALL breakevens (sign changes) of P/L(S) at short expiry on a fine grid
    spanning [spot*0.60, spot*1.10]. Diagonal calendars typically have two BE
    points bracketing a profit zone."""
    long_leg = next(l for l in legs if l["action"] == "buy")
    short_leg = next(l for l in legs if l["action"] == "sell")
    kl, ks = long_leg["strike"], short_leg["strike"]
    long_cost = long_leg["limit_price"] * long_leg["qty"] * 100
    short_credit = short_leg["limit_price"] * short_leg["qty"] * 100
    t_remain = max((dte_long - dte_short) / 365.0, 1 / 365.0)

    def net_at(s: float) -> float:
        short_loss = max(ks - s, 0) * 100 * short_leg["qty"]
        long_mark = _bs_put(s, kl, t_remain, _R, iv_long) * 100 * long_leg["qty"]
        return short_credit - short_loss + (long_mark - long_cost)

    n_steps = 200
    lo_bound, hi_bound = spot * 0.60, spot * 1.10
    grid = [lo_bound + i * (hi_bound - lo_bound) / n_steps for i in range(n_steps + 1)]
    sign_changes: list[float] = []
    prev = net_at(grid[0])
    for s in grid[1:]:
        cur = net_at(s)
        if (prev <= 0 and cur > 0) or (prev >= 0 and cur < 0):
            sign_changes.append(s)
        prev = cur
    lower = round(sign_changes[0], 2) if len(sign_changes) >= 1 else None
    upper = round(sign_changes[-1], 2) if len(sign_changes) >= 2 else None
    return {"lower": lower, "upper": upper}


def _roll_matrix(
    legs: list[dict],
    spot: float,
    iv_long: float,
    dte_long: int,
    dte_short: int,
) -> list[dict[str, float]]:
    """P/L if we close everything at short-leg expiry, across 7 spot scenarios."""
    long_leg = next(l for l in legs if l["action"] == "buy")
    short_leg = next(l for l in legs if l["action"] == "sell")
    kl, ks = long_leg["strike"], short_leg["strike"]
    long_cost = long_leg["limit_price"] * long_leg["qty"] * 100
    short_credit = short_leg["limit_price"] * short_leg["qty"] * 100
    t_remain = (dte_long - dte_short) / 365.0

    out = []
    for s_scenario in (-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10):
        s_T = spot * (1 + s_scenario)
        short_intrinsic = max(ks - s_T, 0) * short_leg["qty"] * 100
        short_pl = short_credit - short_intrinsic
        long_mark = _bs_put(s_T, kl, t_remain, _R, iv_long) * long_leg["qty"] * 100
        net_pl = short_pl + (long_mark - long_cost)
        out.append(
            {
                "spot_scenario": s_scenario,
                "spot_at_expiry": round(s_T, 2),
                "short_put_pl": round(short_pl, 2),
                "long_put_mark": round(long_mark, 2),
                "net_pl": round(net_pl, 2),
            }
        )
    return out


def build_diagonal_calendar(
    spot: float,
    mode: Mode,
    snapshot: dict[str, Any],
    dte_long: int = 45,
    dte_short: int = 1,
    target_deltas: dict[str, float] | None = None,
    qty: int = 1,
    underlying: str = "RUT",
) -> dict[str, Any]:
    """Build a put diagonal calendar (long Kl 45DTE + short Ks 1-2DTE).

    Chain-first: if snapshot contains 'chain', pulls mid + greeks from listed
    strikes (snap-to-listed). Falls back to BSM mid + recomputed greeks per
    leg when chain missing. pricing_source ∈ {chain, mixed, bsm}.

    Mode-specific Ks selection enforces invariants:
      calendar:   Ks == Kl
      protective: Ks < Kl  (anchor: Kl × (1 - SHORT_STRIKE_OFFSET_PCT))
      aggressive: Ks > Kl  (Δ-based; natural with 0.30 short + 0.15 long Δs)
    """
    if mode not in DEFAULT_DELTAS:
        raise ValueError(
            f"unknown mode {mode!r}; expected one of {list(DEFAULT_DELTAS)}"
        )
    deltas = target_deltas or DEFAULT_DELTAS[mode]

    iv_short = float(snapshot["iv_atm_short"])
    iv_long = float(snapshot["iv_atm_long"])
    t_short = dte_short / 365.0
    t_long = dte_long / 365.0

    k_long = _strike_for_put_delta(spot, deltas["long"], t_long, iv_long)
    if mode == "calendar":
        k_short = k_long
    elif mode == "protective":
        k_short = k_long * (1 - SHORT_STRIKE_OFFSET_PCT["protective"])
    else:  # aggressive
        k_short = _strike_for_put_delta(spot, deltas["short"], t_short, iv_short)

    (
        chain,
        chain_source,
        short_expiry,
        short_ts,
        long_expiry,
        long_ts,
    ) = _resolve_chain_expiries(snapshot, dte_short, dte_long)

    # Snap to nearest listed strike when chain available
    if chain:
        if long_expiry and long_expiry in chain:
            k_long = _snap_to_listed_strike(k_long, spot, chain[long_expiry])
        if short_expiry and short_expiry in chain:
            k_short = _snap_to_listed_strike(k_short, spot, chain[short_expiry])
        # Re-enforce mode invariants after snapping
        if mode == "calendar" and abs(k_short - k_long) > 1e-6:
            # If expiries have different listed grids, snap short to long's K
            if short_expiry and short_expiry in chain:
                k_short = _snap_to_listed_strike(k_long, spot, chain[short_expiry])
        if mode == "protective" and not k_short < k_long:
            k_short = k_long * (1 - SHORT_STRIKE_OFFSET_PCT["protective"])
            if short_expiry and short_expiry in chain:
                k_short = _snap_to_listed_strike(k_short, spot, chain[short_expiry])

    if mode == "protective" and not k_short < k_long:
        raise ValueError(
            f"protective mode invariant violated: Ks={k_short:.2f} not < Kl={k_long:.2f}"
        )
    if mode == "aggressive" and not k_short > k_long:
        raise ValueError(
            f"aggressive mode invariant violated: Ks={k_short:.2f} not > Kl={k_long:.2f}"
        )

    long_leg = _build_leg_chain_first(
        spot=spot,
        strike=k_long,
        action="buy",
        qty=qty,
        t_years=t_long,
        iv=iv_long,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=long_expiry,
        chain_timestamp=long_ts,
    )
    short_leg = _build_leg_chain_first(
        spot=spot,
        strike=k_short,
        action="sell",
        qty=qty,
        t_years=t_short,
        iv=iv_short,
        chain=chain,
        chain_source=chain_source,
        chain_expiry=short_expiry,
        chain_timestamp=short_ts,
    )

    net_debit = _net_debit_dollar([long_leg, short_leg])
    max_loss = _max_loss_at_short_expiry(
        [long_leg, short_leg], net_debit, dte_long, dte_short
    )
    breakevens = _breakevens_at_short_expiry(
        [long_leg, short_leg], iv_long, dte_long, dte_short, spot
    )
    net_greeks = _net_greeks([long_leg, short_leg])
    roll_matrix = _roll_matrix(
        [long_leg, short_leg], spot, iv_long, dte_long, dte_short
    )

    return {
        "underlying": underlying,
        "mode": mode,
        "spot": spot,
        "dte_long": dte_long,
        "dte_short": dte_short,
        "legs": [long_leg, short_leg],
        "net_debit_dollar": net_debit,
        "max_loss_dollar": round(max_loss, 2),
        "breakevens_at_short_expiry": breakevens,
        "net_greeks_entry": net_greeks,
        "roll_matrix": roll_matrix,
        "pricing_source": _pricing_source([long_leg, short_leg]),
        "regime_check": _regime_check(mode, snapshot),
    }
