"""Build IB option order instructions with defined-risk guardrails.

Pure logic — no IB connection here. Use scripts._clients.ib.IBClient to
actually submit. The split keeps this module testable in isolation.
"""

from __future__ import annotations

from typing import Any, Iterable

REJECTED_STRUCTURES = {
    "naked_short_call",
    "naked_short_put_margin",
    "ratio_spread",
    "diagonal_inverted",
    "calendar_inverted",
}

SUPPORTED_STRUCTURES = {
    "covered_call",
    "cash_secured_put",
    "bull_put_spread",
    "bear_call_spread",
    "iron_condor",
    "collar",
    "jade_lizard",
    "put_butterfly",
    "long_put",
    "put_spread",
    "put_credit_spread",
}

# Credit-spread structures: max gain == net credit; require BP based on width.
SPREAD_STRUCTURES = {
    "bull_put_spread",
    "bear_call_spread",
    "iron_condor",
    "put_credit_spread",
}


def _signed_qty(leg: dict) -> int:
    sign = 1 if leg["action"].lower() == "buy" else -1
    return sign * int(leg["qty"])


def _net_credit(legs: Iterable[dict]) -> float:
    """Dollar credit received (positive) or debit paid (negative)."""
    total = 0.0
    for leg in legs:
        price = float(leg.get("limit_price", 0.0))
        sign = -1 if leg["action"].lower() == "buy" else 1
        total += sign * price * int(leg["qty"]) * 100
    return total


def validate_structure(structure: str, legs: list[dict]) -> None:
    if structure in REJECTED_STRUCTURES:
        raise ValueError(
            f"{structure} is rejected by the defined-risk policy (naked / ratio / inverted calendar)."
        )
    if structure not in SUPPORTED_STRUCTURES:
        raise ValueError(f"{structure} is not a supported structure.")

    if structure == "ratio_spread":
        raise ValueError(
            "ratio_spread rejected: unhedged short side has unbounded risk."
        )

    if structure == "jade_lizard":
        short_calls = [
            l
            for l in legs
            if l["right"].lower() == "call" and l["action"].lower() == "sell"
        ]
        long_calls = [
            l
            for l in legs
            if l["right"].lower() == "call" and l["action"].lower() == "buy"
        ]
        short_puts = [
            l
            for l in legs
            if l["right"].lower() == "put" and l["action"].lower() == "sell"
        ]
        if not (short_calls and long_calls and short_puts):
            raise ValueError(
                "jade_lizard requires short put + short call + long call (further OTM)"
            )
        call_spread_width = abs(
            float(long_calls[0]["strike"]) - float(short_calls[0]["strike"])
        )
        net_credit_per_contract = (
            _net_credit(legs) / max(int(legs[0]["qty"]), 1) / 100.0
        )
        if net_credit_per_contract < call_spread_width:
            raise ValueError(
                f"jade_lizard net credit ${net_credit_per_contract:.2f}/contract is less than "
                f"call spread width ${call_spread_width:.2f}; upside is not risk-free"
            )

    if structure == "covered_call":
        if not any(
            l["right"].lower() == "call" and l["action"].lower() == "sell" for l in legs
        ):
            raise ValueError("covered_call requires a short call leg")


def _payoff_at_expiry(spot_at_expiry: float, legs: list[dict]) -> float:
    pnl = 0.0
    for leg in legs:
        strike = float(leg["strike"])
        qty = int(leg["qty"])
        price = float(leg.get("limit_price", 0.0))
        is_call = leg["right"].lower() == "call"
        is_long = leg["action"].lower() == "buy"
        intrinsic = (
            max(spot_at_expiry - strike, 0.0)
            if is_call
            else max(strike - spot_at_expiry, 0.0)
        )
        sign = 1 if is_long else -1
        pnl += sign * (intrinsic - price) * qty * 100
    return pnl


def build_pl_matrix(
    structure: str,
    legs: list[dict],
    spot: float,
    moves_pct: list[float] | None = None,
) -> list[dict]:
    if moves_pct is None:
        moves_pct = [-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20]
    rows = []
    for mv in moves_pct:
        s = spot * (1 + mv)
        rows.append(
            {
                "move_pct": mv,
                "spot": round(s, 2),
                "pl_dollar": round(_payoff_at_expiry(s, legs), 2),
            }
        )
    return rows


def _account_check(
    structure: str,
    legs: list[dict],
    account: dict,
    max_loss: float | None = None,
) -> dict:
    """Verify the trader can support the trade.

    For CSP: cash needed = sum of (strike * 100 * qty) on short put legs.
    For CC / Collar: holdings >= short call contracts * 100.
    For credit spreads (bull put, bear call, iron condor, butterfly):
      buying power required = |max_loss|. Caller must pass `max_loss`.
    """
    bp = float(account.get("buying_power", 0))
    positions = account.get("positions", [])
    if structure == "cash_secured_put":
        need = sum(
            float(l["strike"]) * int(l["qty"]) * 100
            for l in legs
            if l["action"].lower() == "sell" and l["right"].lower() == "put"
        )
    elif structure in {"covered_call", "collar"}:
        ticker = legs[0].get("symbol") or legs[0].get("ticker")
        held = sum(
            int(p.get("position", 0)) for p in positions if p.get("symbol") == ticker
        )
        contracts = sum(
            int(l["qty"])
            for l in legs
            if l["right"].lower() == "call" and l["action"].lower() == "sell"
        )
        return {
            "sufficient_shares_for_cover": held >= contracts * 100,
            "shares_held": held,
            "contracts": contracts,
        }
    else:
        if max_loss is None:
            raise ValueError(
                f"_account_check requires max_loss for {structure}; "
                "compute from structure formula or matrix min"
            )
        need = abs(min(0.0, float(max_loss)))
    return {
        "buying_power_required": round(need, 2),
        "buying_power_available": bp,
        "sufficient_buying_power": bp >= need,
    }


def _exact_max_loss(structure: str, legs: list[dict], pl_matrix: list[dict]) -> float:
    """Structure-specific max loss; falls back to matrix minimum."""
    if structure in {"bull_put_spread", "put_credit_spread"}:
        puts = [l for l in legs if l["right"].lower() == "put"]
        short_strikes = [
            float(l["strike"]) for l in puts if l["action"].lower() == "sell"
        ]
        long_strikes = [
            float(l["strike"]) for l in puts if l["action"].lower() == "buy"
        ]
        if short_strikes and long_strikes:
            width = max(short_strikes) - min(long_strikes)
            qty = int(puts[0]["qty"])
            credit = sum(
                (1 if l["action"].lower() == "sell" else -1)
                * float(l.get("limit_price", 0))
                * int(l["qty"])
                * 100
                for l in puts
            )
            return -(width * qty * 100 - credit)
    if structure == "bear_call_spread":
        calls = [l for l in legs if l["right"].lower() == "call"]
        short_strikes = [
            float(l["strike"]) for l in calls if l["action"].lower() == "sell"
        ]
        long_strikes = [
            float(l["strike"]) for l in calls if l["action"].lower() == "buy"
        ]
        if short_strikes and long_strikes:
            width = max(long_strikes) - min(short_strikes)
            qty = int(calls[0]["qty"])
            credit = sum(
                (1 if l["action"].lower() == "sell" else -1)
                * float(l.get("limit_price", 0))
                * int(l["qty"])
                * 100
                for l in calls
            )
            return -(width * qty * 100 - credit)
    return min(r["pl_dollar"] for r in pl_matrix)


def _exact_max_gain(structure: str, legs: list[dict], pl_matrix: list[dict]) -> float:
    """For credit spreads: max gain = net credit. Falls back to matrix max otherwise."""
    if structure in SPREAD_STRUCTURES:
        credit = sum(
            (1 if l["action"].lower() == "sell" else -1)
            * float(l.get("limit_price", 0))
            * int(l["qty"])
            * 100
            for l in legs
        )
        return max(0.0, credit)
    return max(r["pl_dollar"] for r in pl_matrix)


def build_preflight(
    structure: str,
    ticker: str,
    spot: float,
    legs: list[dict],
    uw_regime: dict,
    account: dict,
) -> dict[str, Any]:
    validate_structure(structure, legs)
    matrix = build_pl_matrix(structure, legs, spot)
    max_loss = _exact_max_loss(structure, legs, matrix)
    max_gain = _exact_max_gain(structure, legs, matrix)
    net_credit = _net_credit(legs)
    extras = {}
    if structure in SPREAD_STRUCTURES:
        strikes = sorted({float(l["strike"]) for l in legs})
        if len(strikes) >= 2:
            qty = int(legs[0]["qty"])
            extras["spread_width_dollar"] = (max(strikes) - min(strikes)) * qty * 100
    return {
        "ticker": ticker,
        "structure": structure,
        "spot": spot,
        "legs": legs,
        "net_credit_dollar": round(net_credit, 2),
        "pl_matrix": matrix,
        "max_loss": round(max_loss, 2),
        "max_gain": round(max_gain, 2),
        "uw_regime": uw_regime,
        "account_check": _account_check(structure, legs, account, max_loss=max_loss),
        **extras,
    }
