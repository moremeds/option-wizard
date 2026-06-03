from scripts.gex_levels import compute_levels


def test_gamma_flip_is_zero_crossing_of_cumulative_gex():
    gex_by_strike = [
        {"strike": 170.0, "gex": -100.0},
        {"strike": 180.0, "gex": -200.0},
        {"strike": 190.0, "gex": -150.0},
        {"strike": 195.0, "gex": 200.0},
        {"strike": 200.0, "gex": 300.0},
        {"strike": 240.0, "gex": 500.0},
    ]
    result = compute_levels(gex_by_strike, spot=210.0)
    assert 195.0 <= result["gamma_flip"] <= 200.0


def test_put_wall_is_strike_with_largest_positive_gex_below_spot():
    gex_by_strike = [
        {"strike": 230.0, "gex": 100.0},
        {"strike": 240.0, "gex": 500.0},
        {"strike": 245.0, "gex": 50.0},
        {"strike": 250.0, "gex": -400.0},
    ]
    result = compute_levels(gex_by_strike, spot=244.0)
    assert result["put_wall"] == 240.0


def test_call_wall_is_strike_with_largest_negative_gex_above_spot():
    gex_by_strike = [
        {"strike": 240.0, "gex": 200.0},
        {"strike": 250.0, "gex": -800.0},
        {"strike": 260.0, "gex": -100.0},
    ]
    result = compute_levels(gex_by_strike, spot=244.0)
    assert result["call_wall"] == 250.0


def test_handles_empty_input():
    result = compute_levels([], spot=100.0)
    assert result["gamma_flip"] is None
    assert result["put_wall"] is None
    assert result["call_wall"] is None


def test_gamma_flip_prefers_crossing_nearest_to_spot():
    # Deep-OTM put concentration creates a low-strike crossing AND a
    # near-spot crossing. The trading-relevant flip is the one near spot
    # (where dealer hedging behavior actually changes), not the one $300
    # below spot.
    gex_by_strike = [
        {"strike": 100.0, "gex": -500.0},  # deep OTM puts dominate here
        {
            "strike": 120.0,
            "gex": +600.0,
        },  # cumsum crosses from -500 to +100 between these
        {"strike": 200.0, "gex": -800.0},  # cumsum: 100 -> -700
        {"strike": 425.0, "gex": +1200.0},  # cumsum: -700 -> +500 (near-spot crossing)
        {"strike": 500.0, "gex": +400.0},
    ]
    result = compute_levels(gex_by_strike, spot=423.74)
    # Two crossings exist (~115 and ~245); the near-spot crossing wins.
    assert result["gamma_flip"] is not None
    assert 200.0 < result["gamma_flip"] < 425.0, (
        f"expected near-spot crossing, got {result['gamma_flip']}"
    )
