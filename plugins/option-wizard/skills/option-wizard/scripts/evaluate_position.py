"""Single short-premium position decision tree.

Order of evaluation:
  1. DTE <= 21 -> REVIEW (hard rule, regardless of P/L)
  2. P/L hit take-profit threshold -> CLOSE
  3. P/L hit stop-loss threshold -> CLOSE or ROLL (caller chooses)
  4. Otherwise -> HOLD
"""

from __future__ import annotations

SPREAD_STRUCTURES = {
    "bull_put_spread",
    "bear_call_spread",
    "iron_condor",
    "put_butterfly",
}
SHORT_PREMIUM_STRUCTURES = SPREAD_STRUCTURES | {
    "covered_call",
    "cash_secured_put",
    "jade_lizard",
}


def evaluate_short_premium(
    opening_credit: float,
    current_price: float,
    dte: int,
    delta: float,
    structure: str,
    take_profit_pct: float = 0.50,
    stop_loss_multiplier: float = 2.0,
) -> dict:
    if structure not in SHORT_PREMIUM_STRUCTURES:
        raise ValueError(f"evaluate_short_premium does not apply to {structure}")

    if dte <= 21:
        return {
            "recommended_action": "REVIEW",
            "rationale": (
                f"DTE {dte} <= 21 — gamma window. Hard rule: pick CLOSE / ROLL / "
                "HOLD-AND-ACCEPT-GAMMA before any other request."
            ),
            "current_price": current_price,
            "opening_credit": opening_credit,
            "delta": delta,
            "dte": dte,
        }

    decay_pct = (
        (opening_credit - current_price) / opening_credit if opening_credit else 0.0
    )

    if decay_pct >= take_profit_pct:
        return {
            "recommended_action": "CLOSE",
            "rationale": (
                f"take-profit hit: {decay_pct:.0%} of credit decayed "
                f"(threshold {int(take_profit_pct * 100)}%)"
            ),
            "current_price": current_price,
            "opening_credit": opening_credit,
            "delta": delta,
            "dte": dte,
        }

    stop_trigger = opening_credit * stop_loss_multiplier
    if current_price >= stop_trigger:
        return {
            "recommended_action": "CLOSE",
            "rationale": (
                f"stop-loss hit: current price ${current_price:.2f} >= "
                f"{stop_loss_multiplier:.0f}x opening credit ${opening_credit:.2f}"
            ),
            "current_price": current_price,
            "opening_credit": opening_credit,
            "delta": delta,
            "dte": dte,
        }

    return {
        "recommended_action": "HOLD",
        "rationale": (
            f"{decay_pct:.0%} of credit decayed; DTE {dte} above 21; delta {delta:+.2f} healthy"
        ),
        "current_price": current_price,
        "opening_credit": opening_credit,
        "delta": delta,
        "dte": dte,
    }
