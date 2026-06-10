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
    # Without tactical_window_days, the tactical-window guard fires first
    # (projected carry > 5% NLV is the new gate per the empirical study).
    with pytest.raises(ValueError, match="tactical"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=60,
            scenario="deep_correction_-10",
            underlying="SPX",
            structure="put_spread",
            snapshot=SPX_SNAPSHOT,
        )
    # With tactical_window_days set (caller confirms intent), the cost cap
    # still rejects a $1M account on this structure.
    with pytest.raises(ValueError, match="cost"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=60,
            scenario="deep_correction_-10",
            underlying="SPX",
            structure="put_spread",
            snapshot=SPX_SNAPSHOT,
            tactical_window_days=14,
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
    assert prices[6200.0] == 100.30  # 1.00 strike
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


# ─── Pass-3 adversarial: cost-cap error discloses pricing source (A4) ──


def test_cost_cap_error_includes_pricing_source():
    """When cost cap fires, the error must say whether the cost came from
    chain mids (real) or BSM fallback (approximate) so the trader knows
    whether the cap-breach is real."""
    import pytest as _pt

    # No chain in snapshot → pure BSM path
    with _pt.raises(ValueError, match="BSM fallback"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=60,
            scenario="crash_-20",
            structure="long_put",
            snapshot={"spot": 6200.0, "iv_atm_90d": 0.50},  # high IV → over cap
            max_annual_cost_pct=0.015,
        )


def test_chain_with_zero_mid_falls_back_to_bsm():
    """P3-A2: mid=0.0 from real chain (illiquid strike) should NOT silently
    price the leg at $0. Falls back to BSM so the cost estimate reflects
    actual market risk."""
    snapshot = {
        "spot": 6200.0,
        "iv_atm_90d": 0.18,
        "chain_source": "UW",
        "spot_timestamp": "2026-06-05T10:00:00Z",
        "chain_timestamps": {"2026-08-15": "2026-06-05T10:00:00Z"},
        "chain": {
            "2026-08-15": {
                0.90: {"put": {"mid": 0.0, "iv": 0.21}},  # no bid
            }
        },
    }
    result = build_macro_hedge(
        portfolio_notional=5_000_000,
        hedge_horizon_days=70,
        scenario="crash_-20",
        structure="long_put",
        snapshot=snapshot,
    )
    # Should fall back to BSM, not price at $0
    leg_price = result["legs"][0]["limit_price"]
    assert leg_price > 0
    # Pass-2 C-LOW5: bound the BSM price so silent regression in _bs_put
    # (e.g., sign flip, missing exp(-rT) factor, wrong d1 d2 ordering)
    # is caught. SPX -10% put at 70d / 18% IV is ~$30-150 per share.
    # Wide band catches gross errors without being brittle on minor IV
    # / rate tweaks.
    assert 5 < leg_price < 500, (
        f"BSM fallback price {leg_price} is outside the sane band "
        f"[5, 500] for SPX -10% put at 70d / 18% IV — likely a silent "
        f"BSM regression"
    )
    assert result["legs"][0]["mid_source"] == "fallback"
    assert result["pricing_source"] == "bsm"


# ─── Empirical-update tests: new structures + regime gates ──


def test_put_ratio_backspread_is_forbidden():
    """Pitfall 03: structure refuses to build regardless of inputs."""
    with pytest.raises(ValueError, match="FORBIDDEN.*pitfalls/03"):
        build_macro_hedge(
            portfolio_notional=10_000_000,
            hedge_horizon_days=45,
            scenario="custom",
            structure="put_ratio_backspread",
            snapshot=SPX_SNAPSHOT,
        )


def test_put_ratio_backspread_forbidden_even_with_regime_pass():
    """Defense in depth — even if regime gate signals look right, the
    forbidden-structure check fires."""
    snapshot = dict(SPX_SNAPSHOT)
    snapshot["regime_check"] = {"vix": 16, "vix9d": 17.5, "vvix": 95, "skew": 142}
    with pytest.raises(ValueError, match="FORBIDDEN|pitfalls/03"):
        build_macro_hedge(
            portfolio_notional=10_000_000,
            hedge_horizon_days=45,
            scenario="custom",
            structure="put_ratio_backspread",
            snapshot=snapshot,
        )


def test_vix_call_ladder_succeeds_with_passing_regime():
    """VIX9D/VIX = 1.06 + VIX = 16 → both gates pass."""
    snapshot = {
        "vix_spot": 16.0,
        "vix_underlying": 17.5,  # (VIX + VIX3M) / 2 proxy
        "vvix": 100.0,
        "regime_check": {"vix": 16.0, "vix9d": 17.0, "vvix": 100},
    }
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=30,
        scenario="custom",
        underlying="VIX",
        structure="vix_call_ladder",
        snapshot=snapshot,
        tactical_window_days=14,
    )
    assert result["structure"] == "vix_call_ladder_25_35_45"
    assert len(result["legs"]) == 3
    strikes = sorted(leg["strike"] for leg in result["legs"])
    assert strikes == [25.0, 35.0, 45.0]
    assert all(leg["action"] == "buy" for leg in result["legs"])
    assert all(leg["right"] == "call" for leg in result["legs"])


def test_vix_call_ladder_rejected_no_term_inversion():
    """VIX9D/VIX = 0.99 → gate fails."""
    snapshot = {
        "vix_spot": 16.0,
        "vvix": 95.0,
        "regime_check": {"vix": 16.0, "vix9d": 15.8, "vvix": 95},
    }
    with pytest.raises(ValueError, match="VIX9D/VIX"):
        build_macro_hedge(
            portfolio_notional=10_000_000,
            hedge_horizon_days=30,
            scenario="custom",
            underlying="VIX",
            structure="vix_call_ladder",
            snapshot=snapshot,
            tactical_window_days=14,
        )


def test_vix_call_ladder_rejected_at_high_vix():
    """VIX = 22 → past the entry window, gate fails."""
    snapshot = {
        "vix_spot": 22.0,
        "vvix": 110.0,
        "regime_check": {"vix": 22.0, "vix9d": 25.0, "vvix": 110},
    }
    with pytest.raises(ValueError, match="VIX = 22"):
        build_macro_hedge(
            portfolio_notional=10_000_000,
            hedge_horizon_days=30,
            scenario="custom",
            underlying="VIX",
            structure="vix_call_ladder",
            snapshot=snapshot,
            tactical_window_days=14,
        )


def test_iwm_putspread_rejected_when_vvix_calm():
    """VVIX = 95 → not a fast-deleveraging regime, gate fails."""
    snapshot = {
        "spot": 200.0,
        "iv_atm_90d": 0.22,
        "regime_check": {"vvix": 95.0},
    }
    with pytest.raises(ValueError, match="VVIX"):
        build_macro_hedge(
            portfolio_notional=10_000_000,
            hedge_horizon_days=35,
            scenario="custom",
            underlying="IWM",
            structure="iwm_putspread",
            snapshot=snapshot,
            tactical_window_days=14,
        )


def test_iwm_putspread_passes_when_vvix_elevated():
    """VVIX = 145 → gate passes, structure builds."""
    snapshot = {
        "spot": 200.0,
        "iv_atm_90d": 0.32,
        "regime_check": {"vvix": 145.0},
    }
    result = build_macro_hedge(
        portfolio_notional=50_000_000,
        hedge_horizon_days=35,
        scenario="custom",
        underlying="IWM",
        structure="iwm_putspread",
        snapshot=snapshot,
        tactical_window_days=14,
    )
    assert result["structure"] == "iwm_put_spread"
    assert len(result["legs"]) == 2


def test_qqq_longput_rejected_without_tech_catalyst():
    snapshot = {
        "spot": 540.0,
        "iv_atm_90d": 0.22,
        "regime_check": {"tech_specific_catalyst": False},
    }
    with pytest.raises(ValueError, match="tech_specific_catalyst"):
        build_macro_hedge(
            portfolio_notional=10_000_000,
            hedge_horizon_days=35,
            scenario="custom",
            underlying="QQQ",
            structure="qqq_longput",
            snapshot=snapshot,
        )


def test_qqq_longput_passes_with_tech_catalyst():
    snapshot = {
        "spot": 540.0,
        "iv_atm_90d": 0.22,
        "regime_check": {"tech_specific_catalyst": True},
    }
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=35,
        scenario="custom",
        underlying="QQQ",
        structure="qqq_longput",
        snapshot=snapshot,
        target_delta=0.05,
    )
    assert result["structure"] == "qqq_long_put_delta_5"
    assert len(result["legs"]) == 1


def test_long_put_with_target_delta_walks_strike_with_iv():
    """target_delta=0.05 = 5-delta tail. Carry scales with regime:
    - low IV (14%) → 5-delta strike CLOSER to spot than -10% pct (tight distribution)
    - high IV (30%) → 5-delta strike FURTHER from spot than -10% pct (wide distribution)
    This is the empirical benefit of delta-targeting vs fixed pct: cost
    stays constant in delta-space across regimes."""
    spot = 6200.0
    pct_10_strike = spot * 0.90  # 5580 — the legacy default

    low_iv = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=35,
        scenario="custom",
        underlying="SPX",
        structure="long_put",
        snapshot={"spot": spot, "iv_atm_90d": 0.14},
        target_delta=0.05,
    )["legs"][0]["strike"]
    high_iv = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=35,
        scenario="custom",
        underlying="SPX",
        structure="long_put",
        snapshot={"spot": spot, "iv_atm_90d": 0.30},
        target_delta=0.05,
    )["legs"][0]["strike"]
    # At low IV, 5-delta walks LESS far OTM than the legacy -10% strike.
    # Pass-2 C-LOW6: tighten bound. Hand BSM: σ√T=0.0434, d1=1.645 →
    # log(spot/K) ≈ 0.067 → K ≈ 5798. Solver returns 5797 (one step short
    # of exact). Bound at 5700 to catch direction-preserving regressions
    # where the magnitude is off by >$100.
    assert low_iv > 5700, (
        f"At 14% IV, 5-delta strike {low_iv} should be > 5700 (theoretical "
        f"≈5798); got {low_iv}"
    )
    # At high IV, 5-delta walks MORE far OTM than -10% strike. Hand BSM
    # at 30% IV: σ√T=0.0929, log(spot/K) ≈ 0.139 → K ≈ 5397. Solver
    # returns ~5394. Bound at 5500.
    assert high_iv < 5500, (
        f"At 30% IV, 5-delta strike {high_iv} should be < 5500 (theoretical "
        f"≈5397); got {high_iv}"
    )


def test_convexity_scorecard_present_in_output():
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=35,
        scenario="crash_-20",
        underlying="SPX",
        structure="long_put",
        snapshot={"spot": 6200.0, "iv_atm_90d": 0.18},
    )
    sc = result["convexity_scorecard"]
    assert set(sc["scenarios"].keys()) == {"-5%", "-10%", "-20%", "-30%"}
    # Convexity increases as scenario gets worse for a long put
    ratios = [
        sc["scenarios"][k]["payoff_per_cost_dollar"]
        for k in ["-5%", "-10%", "-20%", "-30%"]
    ]
    assert ratios[0] < ratios[3], f"-30% ratio should exceed -5% ratio, got {ratios}"
    assert sc["max_convexity_ratio"] == ratios[3]


def test_convexity_scorecard_uses_call_scenarios_for_vix_ladder():
    snapshot = {
        "vix_spot": 16.0,
        "vix_underlying": 17.5,
        "vvix": 100.0,
        "regime_check": {"vix": 16.0, "vix9d": 17.0, "vvix": 100},
    }
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=30,
        scenario="custom",
        underlying="VIX",
        structure="vix_call_ladder",
        snapshot=snapshot,
        tactical_window_days=14,
    )
    sc = result["convexity_scorecard"]
    assert set(sc["scenarios"].keys()) == {"+50%", "+100%", "+200%", "+400%"}
    # F1 from /review-cycle audit (+ Pass-2 C-MED1 direction correction):
    # VIX scorecard must disclose the BSM-vs-real-mid calibration gap so
    # trader can't directly compare max_convexity_ratio to put-structure
    # ratios. The note must distinguish BSM-pricing (ratio OVERSTATED at
    # deep scenarios) from chain-pricing (ratio is a LOWER bound).
    assert "cost_calibration_note" in sc
    note = sc["cost_calibration_note"]
    assert "1.2-2×" in note
    assert "pricing_source" in note
    # Direction: BSM case overstates → "halve" guidance must appear
    assert "Halve" in note or "halve" in note
    # Direction: chain case understates → "lower bound" / "floor" guidance
    assert "LOWER bound" in note or "lower bound" in note or "floor" in note


def test_put_scorecard_has_no_vix_calibration_note():
    """Put structures use chain-mid (or BSM-no-skew) entry cost without the
    VIX-specific 2× calibration gap. The note must NOT appear on put
    scorecards — its presence on puts would mislead the trader."""
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=35,
        scenario="crash_-20",
        underlying="SPX",
        structure="long_put",
        snapshot={"spot": 6200.0, "iv_atm_90d": 0.18},
    )
    assert "cost_calibration_note" not in result["convexity_scorecard"]


def test_butterfly_emits_deprecation_warning_when_misused():
    """Butterfly outside its sanctioned scenario gets a deprecation note."""
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=60,
        scenario="crash_-20",  # NOT mild_correction_-5
        underlying="SPX",
        structure="butterfly",
        snapshot=SPX_SNAPSHOT,
    )
    assert "deprecation_warning" in result
    assert "Pitfall 03" in result["deprecation_warning"]


def test_butterfly_no_warning_when_used_for_sanctioned_scenario():
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=60,
        scenario="mild_correction_-5",
        underlying="SPX",
        structure="butterfly",
        snapshot=SPX_SNAPSHOT,
    )
    assert "deprecation_warning" not in result


def test_hedge_horizon_zero_is_refused():
    """Pass-3 A1: hedge_horizon_days=0 collapses BSM to intrinsic and
    silently produces a zero-cost zero-protection hedge. Must refuse
    at entry so typos don't slip through."""
    with pytest.raises(ValueError, match="hedge_horizon_days"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=0,
            scenario="crash_-20",
            structure="long_put",
            snapshot=SPX_SNAPSHOT,
        )
    with pytest.raises(ValueError, match="hedge_horizon_days"):
        build_macro_hedge(
            portfolio_notional=1_000_000,
            hedge_horizon_days=-5,
            scenario="crash_-20",
            structure="long_put",
            snapshot=SPX_SNAPSHOT,
        )


def test_regime_gate_skipped_when_no_regime_check():
    """No regime_check → gates skip entirely. Allows backtest/research mode."""
    result = build_macro_hedge(
        portfolio_notional=10_000_000,
        hedge_horizon_days=30,
        scenario="custom",
        underlying="VIX",
        structure="vix_call_ladder",
        snapshot={
            "vix_spot": 30.0,  # VIX = 30, would fail gate if regime_check present
            "vix_underlying": 28.0,
            "vvix": 130.0,
        },
        tactical_window_days=14,
    )
    assert result["structure"] == "vix_call_ladder_25_35_45"
    assert "regime_gate_status" not in result
