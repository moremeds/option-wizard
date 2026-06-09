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
