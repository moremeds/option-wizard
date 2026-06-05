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


# ─── Phase C: chain-aware leg pricing ──────────────────────


SPX_CHAIN_SNAPSHOT = {
    "spot": 6200.0,
    "iv_atm_90d": 0.18,
    "chain_source": "UW",
    "spot_timestamp": "2026-06-05T10:00:00Z",
    "chain_timestamps": {"2026-08-15": "2026-06-05T10:00:00Z"},
    "chain": {
        "2026-08-15": {
            # strike_pct keys (strike_dollar / spot=6200)
            # long_put uses 0.90; put_spread uses 1.00 + 0.90
            # butterfly uses 0.92 + 0.95 + 0.98
            0.90: {"put": {"mid": 18.50, "iv": 0.21}},
            0.92: {"put": {"mid": 26.40, "iv": 0.20}},
            0.95: {"put": {"mid": 45.20, "iv": 0.19}},
            0.98: {"put": {"mid": 75.10, "iv": 0.18}},
            1.00: {"put": {"mid": 100.30, "iv": 0.18}},
        }
    },
}


def test_long_put_uses_chain_mid_when_chain_present():
    result = build_macro_hedge(
        portfolio_notional=5_000_000,
        hedge_horizon_days=70,  # ~2.3 months → resolves to 2026-08-15
        scenario="crash_-20",
        underlying="SPX",
        structure="long_put",
        snapshot=SPX_CHAIN_SNAPSHOT,
    )
    assert result["pricing_source"] == "chain"
    leg = result["legs"][0]
    assert leg["mid_source"] == "UW"
    assert leg["limit_price"] == 18.50  # from chain[0.90].put.mid
    assert "UW chain" in leg["mid_provenance"]["detail"]


def test_put_spread_uses_chain_mid_for_both_legs():
    result = build_macro_hedge(
        portfolio_notional=50_000_000,
        hedge_horizon_days=70,
        scenario="deep_correction_-10",
        underlying="SPX",
        structure="put_spread",
        snapshot=SPX_CHAIN_SNAPSHOT,
    )
    assert result["pricing_source"] == "chain"
    prices = {leg["strike"]: leg["limit_price"] for leg in result["legs"]}
    assert prices[6200.0] == 100.30   # 1.00 strike
    assert prices[6200.0 * 0.90] == 18.50  # 0.90 strike


def test_falls_back_to_bsm_when_chain_missing_strike():
    """Chain has 0.95 + 0.98 but not 0.92 → mixed: some chain, one BSM."""
    snapshot = dict(SPX_CHAIN_SNAPSHOT)
    snapshot["chain"] = {
        "2026-08-15": {
            0.95: {"put": {"mid": 45.20, "iv": 0.19}},
            0.98: {"put": {"mid": 75.10, "iv": 0.18}},
            # 0.92 deliberately missing
        }
    }
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=70,
        scenario="mild_correction_-5",
        underlying="SPX",
        structure="butterfly",
        snapshot=snapshot,
    )
    assert result["pricing_source"] == "mixed"
    by_strike = {leg["strike"]: leg for leg in result["legs"]}
    # 0.92 leg fell back to BSM
    leg_092 = by_strike[6200.0 * 0.92]
    assert leg_092["mid_source"] == "fallback"
    assert "BSM fallback" in leg_092["mid_provenance"]["detail"]
    # 0.95 and 0.98 legs got chain mid
    assert by_strike[6200.0 * 0.95]["mid_source"] == "UW"
    assert by_strike[6200.0 * 0.98]["mid_source"] == "UW"


def test_no_chain_in_snapshot_uses_pure_bsm():
    """Pure BSM mode tags pricing_source='bsm' so trader knows the cost
    estimate is heuristic, not market-priced."""
    result = build_macro_hedge(
        portfolio_notional=1_000_000,
        hedge_horizon_days=60,
        scenario="crash_-20",
        underlying="SPX",
        structure="long_put",
        snapshot={"spot": 6200.0, "iv_atm_90d": 0.18},  # no chain
    )
    assert result["pricing_source"] == "bsm"
    leg = result["legs"][0]
    assert leg["mid_source"] == "fallback"
    assert "BSM fallback" in leg["mid_provenance"]["detail"]
