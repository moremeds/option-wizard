"""Regenerate worked-example numbers in references/index-premium-selling.md §8.

Run this after any change to scripts.diagonal_calendar or its math to refresh
the doc with actual pricer output (instead of hand-computed values that
inevitably drift). Uses live 2026-06-08 UW snapshot data.

Usage:
    .venv/bin/python -m scripts.regen_index_premium_worked_examples
"""

from __future__ import annotations

import math

from scripts.diagonal_calendar import (
    _bs_put,
    _bs_put_greeks,
    _strike_for_put_delta,
    build_diagonal_calendar,
)

_R = 0.04


def example_8_1_qqq_csp():
    """QQQ CSP — 0.25Δ 35-DTE put. Standalone (not a diagonal)."""
    spot = 716.07
    iv = 0.239
    target_delta = 0.25
    dte = 35
    t = dte / 365.0
    slippage = 0.05

    strike = _strike_for_put_delta(spot, target_delta, t, iv)
    strike_listed = round(strike)  # QQQ has $1-spaced strikes
    credit_per_share = _bs_put(spot, strike_listed, t, _R, iv) - slippage
    credit_dollar = credit_per_share * 100  # 1 contract = 100 shares
    notional = strike_listed * 100
    contracts = max(1, int(50_000 / notional))
    cash_reserve = strike_listed * 100 * contracts
    max_loss = cash_reserve - credit_dollar * contracts
    max_gain = credit_dollar * contracts
    breakeven = strike_listed - credit_per_share
    tp_exit_mid = credit_per_share * 0.50
    sl_exit_mid = credit_per_share * 3.0  # 2x credit loss = 3x credit mark

    return {
        "spot": spot,
        "iv": iv,
        "strike_theo": round(strike, 2),
        "strike_listed": strike_listed,
        "credit_per_share": round(credit_per_share, 2),
        "credit_dollar": round(credit_dollar, 2),
        "contracts": contracts,
        "cash_reserve": cash_reserve,
        "max_loss": round(max_loss, 2),
        "max_gain": round(max_gain, 2),
        "breakeven": round(breakeven, 2),
        "tp_exit_mid": round(tp_exit_mid, 2),
        "sl_exit_mid": round(sl_exit_mid, 2),
    }


def example_8_2_rut_calendar():
    """RUT diagonal calendar — default 0.30Δ_long, Ks=Kl."""
    spot = 2841.0
    snap = {
        "iv_atm_short": 0.235,
        "iv_atm_long": 0.233,
        "iv_rank": 38,
        "vrp_label": "NEUTRAL",
    }
    out = build_diagonal_calendar(spot=spot, mode="calendar", snapshot=snap)
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    return {
        "spot": spot,
        "kl_theo_rounded_to_5": round(long_leg["strike"] / 5) * 5,
        "kl_actual": long_leg["strike"],
        "long_mid": long_leg["limit_price"],
        "short_mid": short_leg["limit_price"],
        "net_debit": out["net_debit_dollar"],
        "max_loss": out["max_loss_dollar"],
        "net_greeks": out["net_greeks_entry"],
        "breakevens": out["breakevens_at_short_expiry"],
        "regime_check": out["regime_check"],
    }


def example_8_3_rut_protective():
    """RUT diagonal protective — Kl 0.30Δ, Ks = Kl × (1 − 0.025)."""
    spot = 2841.0
    snap = {
        "iv_atm_short": 0.235,
        "iv_atm_long": 0.233,
        "iv_rank": 38,
        "vrp_label": "NEUTRAL",
    }
    out = build_diagonal_calendar(spot=spot, mode="protective", snapshot=snap)
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    # Roll matrix at -10%, 0%, +5%
    rm = {r["spot_scenario"]: r for r in out["roll_matrix"]}
    return {
        "spot": spot,
        "kl": long_leg["strike"],
        "ks": short_leg["strike"],
        "long_mid": long_leg["limit_price"],
        "short_mid": short_leg["limit_price"],
        "net_debit": out["net_debit_dollar"],
        "max_loss": out["max_loss_dollar"],
        "pl_at_minus_10pct": rm[-0.10]["net_pl"],
        "pl_at_flat": rm[0.0]["net_pl"],
        "pl_at_plus_5pct": rm[0.05]["net_pl"],
        "regime_check": out["regime_check"],
    }


def example_8_4_rut_aggressive():
    """RUT diagonal aggressive — Kl 0.15Δ 45DTE, Ks 0.30Δ 1DTE (Ks > Kl)."""
    spot = 2841.0
    snap = {
        "iv_atm_short": 0.235,
        "iv_atm_long": 0.233,
        "iv_rank": 38,
        "vrp_label": "NEUTRAL",
    }
    out = build_diagonal_calendar(spot=spot, mode="aggressive", snapshot=snap)
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    return {
        "spot": spot,
        "kl": long_leg["strike"],
        "ks": short_leg["strike"],
        "long_mid": long_leg["limit_price"],
        "short_mid": short_leg["limit_price"],
        "net_debit": out["net_debit_dollar"],
        "max_loss": out["max_loss_dollar"],
        "regime_check": out["regime_check"],
    }


def main() -> None:
    import json

    print("=== §8.1 QQQ CSP ===")
    print(json.dumps(example_8_1_qqq_csp(), indent=2))
    print("\n=== §8.2 RUT calendar ===")
    print(json.dumps(example_8_2_rut_calendar(), indent=2))
    print("\n=== §8.3 RUT protective ===")
    print(json.dumps(example_8_3_rut_protective(), indent=2))
    print("\n=== §8.4 RUT aggressive ===")
    print(json.dumps(example_8_4_rut_aggressive(), indent=2))


if __name__ == "__main__":
    main()
