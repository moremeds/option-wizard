from scripts.gex_levels import compute_levels, compute_levels_per_expiry


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


def test_call_wall_oi_cluster_picks_largest_call_gex_above_spot():
    # 'oi_cluster' definition: trader convention — largest CALL gamma
    # concentration above spot, ignoring put_gex. For a name where net GEX
    # is positive everywhere above spot, this is the only definition that
    # surfaces a tradeable resistance level.
    rows = [
        {"strike": 420.0, "call_gex": 11602.0, "put_gex": -10565.0},  # below spot
        {"strike": 425.0, "call_gex": 9253.0, "put_gex": -6852.0},
        {"strike": 430.0, "call_gex": 16492.0, "put_gex": -5483.0},  # peak above spot
        {"strike": 440.0, "call_gex": 13780.0, "put_gex": -4186.0},
        {"strike": 450.0, "call_gex": 9011.0, "put_gex": -960.0},
    ]
    result = compute_levels(rows, spot=423.74, call_wall_definition="oi_cluster")
    assert result["call_wall"] == 430.0


def test_call_wall_net_neg_gex_default_unchanged():
    # Same rows: net_neg_gex returns None because every strike above spot has
    # positive net (call_gex >> |put_gex|). Demonstrates why oi_cluster is
    # often the better tactical definition for near-expiry reads.
    rows = [
        {"strike": 420.0, "call_gex": 11602.0, "put_gex": -10565.0},
        {"strike": 425.0, "call_gex": 9253.0, "put_gex": -6852.0},
        {"strike": 430.0, "call_gex": 16492.0, "put_gex": -5483.0},
        {"strike": 440.0, "call_gex": 13780.0, "put_gex": -4186.0},
    ]
    result = compute_levels(rows, spot=423.74)  # default = net_neg_gex
    assert result["call_wall"] is None


def test_call_wall_unknown_definition_raises():
    rows = [{"strike": 100.0, "gex": 50.0}]
    try:
        compute_levels(rows, spot=90.0, call_wall_definition="invalid_mode")
    except ValueError as e:
        assert "invalid_mode" in str(e)
        return
    raise AssertionError("expected ValueError for unknown definition")


def test_compute_levels_per_expiry_groups_and_runs_per_expiry():
    # Two expiries, same ticker. Per-expiry walls should diverge because
    # near-expiry OI clusters are tighter than far-expiry.
    uw_rows = [
        # near expiry — call OI clustered at 430
        {"expiry": "2026-06-05", "strike": 420.0, "call_gex": 100.0, "put_gex": -500.0},
        {
            "expiry": "2026-06-05",
            "strike": 430.0,
            "call_gex": 5000.0,
            "put_gex": -200.0,
        },
        {"expiry": "2026-06-05", "strike": 440.0, "call_gex": 1000.0, "put_gex": -50.0},
        # far expiry — call OI clustered at 440
        {"expiry": "2026-07-10", "strike": 420.0, "call_gex": 50.0, "put_gex": -300.0},
        {"expiry": "2026-07-10", "strike": 430.0, "call_gex": 200.0, "put_gex": -100.0},
        {"expiry": "2026-07-10", "strike": 440.0, "call_gex": 3000.0, "put_gex": -80.0},
    ]
    result = compute_levels_per_expiry(
        uw_rows, spot=425.0, call_wall_definition="oi_cluster"
    )
    assert set(result.keys()) == {"2026-06-05", "2026-07-10"}
    assert result["2026-06-05"]["call_wall"] == 430.0
    assert result["2026-07-10"]["call_wall"] == 440.0


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


# ─── Phase D: data_provenance ───────────────────────────────


def test_compute_levels_includes_data_provenance():
    rows = [
        {"strike": 90.0, "call_gex": 100, "put_gex": -500},
        {"strike": 95.0, "call_gex": 200, "put_gex": -300},
        {"strike": 100.0, "call_gex": 800, "put_gex": -200},
        {"strike": 105.0, "call_gex": 1500, "put_gex": -100},
    ]
    from scripts.gex_levels import compute_levels

    result = compute_levels(rows, spot=100.0, chain_source="UW",
                            chain_timestamp="2026-06-05T10:00:00Z")
    assert "data_provenance" in result
    for key in ("gamma_flip", "put_wall", "call_wall"):
        entry = result["data_provenance"][key]
        assert entry["source"] == "computed"
        assert "UW" in entry["detail"]
        assert entry["timestamp"] == "2026-06-05T10:00:00Z"
        # Value mirrors the level (might be None if unidentifiable)
        assert entry["value"] == result[key]
