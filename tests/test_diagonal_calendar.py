"""Tests for scripts.diagonal_calendar."""

import math

import pytest
from scripts.diagonal_calendar import (
    _bs_put_greeks,
    _strike_for_put_delta,
)


def test_bs_put_greeks_atm():
    """ATM put: delta near -0.5, positive gamma + vega, negative theta."""
    g = _bs_put_greeks(spot=2300.0, strike=2300.0, t_years=45 / 365, r=0.04, sigma=0.28)
    assert -0.55 < g["delta"] < -0.40, f"ATM put delta ≈ -0.5, got {g['delta']}"
    assert g["gamma"] > 0
    assert g["vega"] > 0
    # Long put loses time value (theta as we define it is the d/dt of value;
    # BSM convention for a non-deep-ITM put gives negative theta near ATM)
    assert g["theta"] < 0


def test_bs_put_greeks_deep_otm():
    """Deep OTM put: small delta magnitude."""
    g = _bs_put_greeks(spot=2300.0, strike=2070.0, t_years=45 / 365, r=0.04, sigma=0.28)
    assert -0.20 < g["delta"] < 0


def test_strike_for_put_delta_round_trip():
    """Pick strike for target |Δ| = 0.30 then check Greeks deliver that delta."""
    spot, t, iv = 2300.0, 45 / 365, 0.28
    strike = _strike_for_put_delta(spot=spot, target_abs=0.30, t_years=t, iv=iv)
    assert strike < spot, "30Δ put strike must be OTM (below spot)"
    g = _bs_put_greeks(spot=spot, strike=strike, t_years=t, r=0.04, sigma=iv)
    assert abs(abs(g["delta"]) - 0.30) < 0.01


def test_strike_for_put_delta_invalid_target_raises():
    with pytest.raises(ValueError, match="target_abs"):
        _strike_for_put_delta(spot=2300.0, target_abs=0.0, t_years=0.1, iv=0.28)
    with pytest.raises(ValueError, match="target_abs"):
        _strike_for_put_delta(spot=2300.0, target_abs=1.5, t_years=0.1, iv=0.28)


# --- Tasks 5+6+7 — mode dispatch, max_loss, breakevens, greeks, roll matrix ---

from scripts.diagonal_calendar import build_diagonal_calendar

RUT_SNAPSHOT_BSM = {
    "iv_atm_short": 0.28,
    "iv_atm_long": 0.30,
    "iv_rank": 35,
    "vrp_label": "NEUTRAL",
}


def test_calendar_mode_same_strike():
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    assert out["mode"] == "calendar"
    assert len(out["legs"]) == 2
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    assert long_leg["strike"] == pytest.approx(short_leg["strike"], rel=1e-6), (
        "calendar mode requires Ks == Kl"
    )


def test_protective_strike_invariant_ks_below_kl():
    """Protective mode MUST produce Ks < Kl regardless of default Δs."""
    out = build_diagonal_calendar(
        spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM
    )
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    assert short_leg["strike"] < long_leg["strike"]


def test_aggressive_mode_short_above_long():
    out = build_diagonal_calendar(
        spot=2300.0, mode="aggressive", snapshot=RUT_SNAPSHOT_BSM
    )
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    assert short_leg["strike"] > long_leg["strike"], "aggressive: Ks > Kl"


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="mode"):
        build_diagonal_calendar(
            spot=2300.0, mode="butterfly", snapshot=RUT_SNAPSHOT_BSM
        )


def test_pricing_source_bsm_when_no_chain():
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    assert out["pricing_source"] == "bsm"
    for leg in out["legs"]:
        assert leg["mid_source"] == "fallback"


def test_calendar_net_debit_positive():
    """Calendar mode (Ks=Kl): long 45DTE >> short 1DTE premium at same K → net debit."""
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    assert out["net_debit_dollar"] > 0, "calendar should be net debit (long > short)"


def test_calendar_max_loss_close_to_net_debit():
    """Calendar max loss = net_debit + Kl(1-DF)*100 discount-carry term.
    Worst case is S=0: long pays Kl·DF, short pays Kl. Extra loss = Kl(1-DF).
    For RUT Kl ≈ 2185, 44d at 4%: ≈ $1,050. Test bound: net_debit ≤ max_loss
    ≤ net_debit + 1% of strike notional."""
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    discount_carry_ceiling = long_leg["strike"] * 0.01 * 100
    assert (
        out["net_debit_dollar"]
        <= out["max_loss_dollar"]
        <= out["net_debit_dollar"] + discount_carry_ceiling
    )


def test_protective_max_loss_close_to_net_debit():
    """Protective max loss ≈ net_debit (S > Kl worst case, both worthless).
    Width (Kl - Ks) does NOT add — when S < Ks both legs are ITM and offset
    in [Ks, Kl] range. Discount-carry correction can add a small term."""
    out = build_diagonal_calendar(
        spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM
    )
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    width_dollars = (long_leg["strike"] - short_leg["strike"]) * 100
    # Must be ≪ width (would be off by ~$5,000+ if width term incorrectly added)
    assert out["max_loss_dollar"] < out["net_debit_dollar"] + width_dollars * 0.5


def test_aggressive_max_loss_width_plus_debit_plus_discount_carry():
    """Aggressive max loss = (Ks - Kl·DF)*100 + net_debit
       = (Ks - Kl)*100 + Kl(1-DF)*100 + net_debit.
    The Kl(1-DF) term ADDS to the naive width formula (worst case S→0,
    long pays Kl·DF, short pays Ks). Test bounds:
      lower = (Ks-Kl)*100 + net_debit  (no discount carry edge case)
      upper = (Ks-Kl)*100 + net_debit + Kl*1%*100  (full discount carry)"""
    out = build_diagonal_calendar(
        spot=2300.0, mode="aggressive", snapshot=RUT_SNAPSHOT_BSM
    )
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    width = short_leg["strike"] - long_leg["strike"]
    lower_bound = width * 100 + out["net_debit_dollar"]
    upper_bound = lower_bound + long_leg["strike"] * 0.01 * 100
    assert lower_bound <= out["max_loss_dollar"] <= upper_bound


def test_net_greeks_keys_present():
    """Net greeks dict has all 4 keys with finite values.

    NOTE: at default Δs (calendar long=0.30, short Δ unused with Ks=Kl),
    K lands ~5% OTM for both legs. Short 1-DTE at 5% OTM is near-worthless,
    so its positive theta (from being short) is tiny. Long 45-DTE put's
    negative theta dominates → NET theta is NEGATIVE for default-Δ calendar.
    Trader who wants theta-positive calendar must override target_deltas
    to push K closer to ATM (e.g., long Δ ~0.45-0.50)."""
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    for k in ("delta", "gamma", "theta_daily", "vega"):
        assert k in out["net_greeks_entry"]
        assert isinstance(out["net_greeks_entry"][k], (int, float))
    # Long-leg vega should dominate → net vega POSITIVE for calendar
    assert out["net_greeks_entry"]["vega"] > 0, (
        "calendar long-leg vega should dominate; positive net vega is the edge"
    )


def test_calendar_atm_overrides_positive_theta():
    """When trader overrides target_deltas to push K toward ATM (long Δ 0.50),
    short 1-DTE is closer to ATM, has meaningful theta. Net theta SHOULD then
    flip positive (the classic 'calendar income' picture)."""
    out = build_diagonal_calendar(
        spot=2300.0,
        mode="calendar",
        snapshot=RUT_SNAPSHOT_BSM,
        target_deltas={"long": 0.50, "short": 0.50},
    )
    assert out["net_greeks_entry"]["theta_daily"] > 0, (
        f"ATM calendar should be theta-positive; got {out['net_greeks_entry']['theta_daily']}"
    )


def test_breakevens_dict_shape():
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    assert "breakevens_at_short_expiry" in out
    assert "lower" in out["breakevens_at_short_expiry"]
    assert "upper" in out["breakevens_at_short_expiry"]


def test_roll_matrix_has_seven_scenarios():
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    assert len(out["roll_matrix"]) == 7
    scenarios = [r["spot_scenario"] for r in out["roll_matrix"]]
    assert scenarios == [-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10]


def test_roll_matrix_protective_higher_pl_on_crash():
    """For protective, net_pl should be higher at -10% than at 0% (long pays off)."""
    out = build_diagonal_calendar(
        spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM
    )
    rows = out["roll_matrix"]
    pl_down10 = next(r["net_pl"] for r in rows if r["spot_scenario"] == -0.10)
    pl_flat = next(r["net_pl"] for r in rows if r["spot_scenario"] == 0.0)
    assert pl_down10 > pl_flat


def test_roll_matrix_short_put_pl_at_credit_above_strike():
    """If spot at short expiry > short strike Ks, short_put_pl ≈ credit received."""
    out = build_diagonal_calendar(
        spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM
    )
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    ks = short_leg["strike"]
    short_credit = short_leg["limit_price"] * 100
    up_row = next(r for r in out["roll_matrix"] if r["spot_scenario"] == 0.10)
    assert up_row["spot_at_expiry"] > ks
    assert up_row["short_put_pl"] == pytest.approx(short_credit, abs=1.0)


# --- Task 8 — chain path + regime_check + snap-to-listed ---

RUT_SNAPSHOT_CHAIN = {
    "iv_atm_short": 0.28,
    "iv_atm_long": 0.30,
    "iv_rank": 35,
    "vrp_label": "NEUTRAL",
    "chain_source": "UW",
    "spot_timestamp": "2026-06-09T10:00:00Z",
    "chain_timestamps": {
        "2026-06-10": "2026-06-09T10:00:00Z",
        "2026-07-24": "2026-06-09T10:00:00Z",
    },
    "chain": {
        # 1-DTE
        "2026-06-10": {
            1.00: {"put": {"mid": 9.50, "iv": 0.28}},
            0.99: {"put": {"mid": 4.20, "iv": 0.30}},
            0.97: {"put": {"mid": 1.80, "iv": 0.33}},
            0.95: {"put": {"mid": 0.50, "iv": 0.35}},
        },
        # 45-DTE
        "2026-07-24": {
            1.00: {"put": {"mid": 38.00, "iv": 0.30}},
            0.95: {"put": {"mid": 18.50, "iv": 0.32}},
            0.93: {"put": {"mid": 12.20, "iv": 0.33}},
        },
    },
}


def test_chain_path_used_when_available():
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_CHAIN
    )
    assert out["pricing_source"] in ("chain", "mixed")
    sources = {leg["mid_source"] for leg in out["legs"]}
    assert "UW" in sources or "IB" in sources


def test_chain_path_consumes_greeks_when_provided():
    """When chain leg includes a greeks dict, the leg's greeks_source must be
    the chain source (UW/IB), NOT 'bsm_fallback'. Per hard rule #2."""
    snap = {
        **RUT_SNAPSHOT_CHAIN,
        "chain": {
            "2026-06-10": {
                0.95: {
                    "put": {
                        "mid": 0.50,
                        "iv": 0.35,
                        "greeks": {
                            "delta": -0.10,
                            "gamma": 0.001,
                            "theta": -0.05,
                            "vega": 0.05,
                        },
                    }
                },
            },
            "2026-07-24": {
                0.95: {
                    "put": {
                        "mid": 18.50,
                        "iv": 0.32,
                        "greeks": {
                            "delta": -0.30,
                            "gamma": 0.002,
                            "theta": -0.10,
                            "vega": 0.50,
                        },
                    }
                },
            },
        },
    }
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=snap)
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    assert long_leg["greeks_source"] == "UW", (
        f"long leg should consume chain greeks; got {long_leg['greeks_source']}"
    )
    # Verify the actual greek value came from chain, not BSM (delta = -0.30)
    assert long_leg["greeks"]["delta"] == pytest.approx(-0.30)


def test_regime_check_warns_on_mismatch():
    """Aggressive mode + CHEAP VRP → regime_check.warning populated."""
    cheap_snap = {**RUT_SNAPSHOT_BSM, "iv_rank": 12, "vrp_label": "CHEAP"}
    out = build_diagonal_calendar(spot=2300.0, mode="aggressive", snapshot=cheap_snap)
    assert out["regime_check"]["matches_chosen_mode"] is False
    assert out["regime_check"]["warning"] is not None


def test_regime_check_no_warning_when_match():
    out = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    assert out["regime_check"]["matches_chosen_mode"] is True
    assert out["regime_check"]["warning"] is None


# --- Task 9 — build_short_leg_roll ---

from scripts.diagonal_calendar import build_short_leg_roll


def test_roll_triggers_close_when_long_dte_too_short():
    """Long leg DTE remaining < 21 → action_required = 'close_all_long_dte_too_short'."""
    pos = build_diagonal_calendar(
        spot=2300.0,
        mode="calendar",
        snapshot=RUT_SNAPSHOT_BSM,
        dte_long=24,
        dte_short=1,
    )
    # 4 days elapsed: long_dte_remaining_when_roll_done = 24 - 4 - 1 = 19 < 21
    roll = build_short_leg_roll(
        existing_position=pos,
        new_dte_short=1,
        snapshot=RUT_SNAPSHOT_BSM,
        days_elapsed=4,
    )
    assert roll["action_required"] == "close_all_long_dte_too_short"


def test_roll_returns_close_old_and_open_new():
    pos = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    snap_after = {**RUT_SNAPSHOT_BSM, "iv_atm_short": 0.30}
    roll = build_short_leg_roll(
        existing_position=pos,
        new_dte_short=1,
        snapshot=snap_after,
        days_elapsed=1,
    )
    assert "close_old_short_leg" in roll
    assert "open_new_short_leg" in roll
    assert roll["action_required"] == "roll_short"


def test_roll_recommends_mode_switch_on_drift():
    """Calendar mode but short put ITM by 1+ RUT strike width →
    switch_mode_recommendation = 'protective'."""
    pos = build_diagonal_calendar(
        spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM
    )
    # Spot dropped enough to put calendar K (≈ 2185) above spot by ≥ 5
    snap_after = {**RUT_SNAPSHOT_BSM, "spot": 2170.0}
    roll = build_short_leg_roll(
        existing_position=pos,
        new_dte_short=1,
        snapshot=snap_after,
        days_elapsed=1,
    )
    assert roll["action_required"] == "switch_mode"
    assert roll["switch_mode_recommendation"] == "protective"


@pytest.mark.parametrize("mode", ["calendar", "protective", "aggressive"])
def test_roll_matrix_non_monotonic_shape(mode):
    """Diagonal calendar P/L is GENERALLY non-monotonic in spot — typically has a
    profit zone near the strike cluster with two breakevens flanking it. Expect
    ≤ 2 sign changes in net_pl across the 7 spot scenarios."""
    out = build_diagonal_calendar(spot=2300.0, mode=mode, snapshot=RUT_SNAPSHOT_BSM)
    pls = [r["net_pl"] for r in out["roll_matrix"]]
    sign_changes = sum(
        1
        for i in range(1, len(pls))
        if (pls[i - 1] > 0 and pls[i] < 0) or (pls[i - 1] < 0 and pls[i] > 0)
    )
    assert sign_changes <= 2, (
        f"{mode} roll matrix has {sign_changes} sign changes; expected ≤ 2. P/L: {pls}"
    )
