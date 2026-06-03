import pytest
from scripts.macro_hedge import build_macro_hedge

SPX_SNAPSHOT = {
    "spot": 6200.0,
    "iv_atm_90d": 0.18,
}


def test_butterfly_for_mild_correction_target():
    result = build_macro_hedge(
        portfolio_notional=1_000_000,
        hedge_horizon_days=60,
        scenario="mild_correction_-5",
        underlying="SPX",
        structure="butterfly",
        snapshot=SPX_SNAPSHOT,
    )
    assert result["structure"] == "put_butterfly"
    assert len(result["legs"]) == 3
    body_strike = [l["strike"] for l in result["legs"] if l["qty"] == 2][0]
    assert body_strike == pytest.approx(SPX_SNAPSHOT["spot"] * 0.95, abs=1)


def test_put_spread_for_deep_correction():
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=60,
        scenario="deep_correction_-10",
        underlying="SPX",
        structure="put_spread",
        snapshot=SPX_SNAPSHOT,
    )
    assert result["structure"] == "put_spread"
    assert len(result["legs"]) == 2


def test_put_spread_rejected_on_small_account():
    with pytest.raises(ValueError, match="cost"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=60,
            scenario="deep_correction_-10",
            underlying="SPX",
            structure="put_spread",
            snapshot=SPX_SNAPSHOT,
        )


def test_long_put_for_crash_scenario():
    result = build_macro_hedge(
        portfolio_notional=1_000_000,
        hedge_horizon_days=60,
        scenario="crash_-20",
        underlying="SPX",
        structure="long_put",
        snapshot=SPX_SNAPSHOT,
    )
    assert result["structure"] == "long_put"
    assert len(result["legs"]) == 1


def test_cost_cap_enforced():
    with pytest.raises(ValueError, match="cost"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=60,
            scenario="crash_-20",
            underlying="SPX",
            structure="long_put",
            snapshot={"spot": 6200.0, "iv_atm_90d": 0.50},
            max_annual_cost_pct=0.015,
        )


def test_auto_structure_routes_by_scenario():
    result = build_macro_hedge(
        portfolio_notional=1_000_000,
        hedge_horizon_days=60,
        scenario="mild_correction_-5",
        underlying="SPX",
        structure="auto",
        snapshot=SPX_SNAPSHOT,
    )
    assert result["structure"] == "put_butterfly"
