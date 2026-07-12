import pytest
from scripts.ib_order import (
    build_brackets,
    build_pl_matrix,
    build_preflight,
    validate_structure,
)


def test_rejects_naked_short_call():
    with pytest.raises(ValueError, match="naked"):
        validate_structure(
            structure="naked_short_call",
            legs=[
                {
                    "action": "sell",
                    "right": "call",
                    "strike": 250,
                    "expiry": "2026-07-17",
                    "qty": 1,
                }
            ],
        )


def test_rejects_unhedged_ratio_spread():
    with pytest.raises(ValueError, match="ratio"):
        validate_structure(
            structure="ratio_spread",
            legs=[
                {
                    "action": "sell",
                    "right": "put",
                    "strike": 230,
                    "expiry": "2026-07-17",
                    "qty": 2,
                },
                {
                    "action": "buy",
                    "right": "put",
                    "strike": 220,
                    "expiry": "2026-07-17",
                    "qty": 1,
                },
            ],
        )


def test_accepts_bull_put_spread():
    validate_structure(
        structure="bull_put_spread",
        legs=[
            {
                "action": "sell",
                "right": "put",
                "strike": 235,
                "expiry": "2026-07-17",
                "qty": 5,
            },
            {
                "action": "buy",
                "right": "put",
                "strike": 225,
                "expiry": "2026-07-17",
                "qty": 5,
            },
        ],
    )


def test_jade_lizard_requires_net_credit_ge_call_spread_width():
    with pytest.raises(ValueError, match="net credit"):
        validate_structure(
            structure="jade_lizard",
            legs=[
                {
                    "action": "sell",
                    "right": "put",
                    "strike": 230,
                    "expiry": "2026-07-17",
                    "qty": 5,
                    "limit_price": 4.00,
                },
                {
                    "action": "sell",
                    "right": "call",
                    "strike": 260,
                    "expiry": "2026-07-17",
                    "qty": 5,
                    "limit_price": 1.50,
                },
                {
                    "action": "buy",
                    "right": "call",
                    "strike": 265,
                    "expiry": "2026-07-17",
                    "qty": 5,
                    "limit_price": 0.70,
                },
            ],
        )


def test_pl_matrix_for_bull_put_spread():
    legs = [
        {
            "action": "sell",
            "right": "put",
            "strike": 235,
            "qty": 5,
            "limit_price": 4.20,
        },
        {"action": "buy", "right": "put", "strike": 225, "qty": 5, "limit_price": 2.10},
    ]
    matrix = build_pl_matrix(
        structure="bull_put_spread",
        legs=legs,
        spot=244.58,
        moves_pct=[-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20],
    )
    plus_5 = next(row for row in matrix if row["move_pct"] == 0.05)
    assert plus_5["pl_dollar"] == pytest.approx(1050, abs=1)


def test_preflight_includes_required_blocks():
    preflight = build_preflight(
        structure="bull_put_spread",
        ticker="ORCL",
        spot=244.58,
        legs=[
            {
                "action": "sell",
                "right": "put",
                "strike": 235,
                "expiry": "2026-07-17",
                "qty": 5,
                "limit_price": 4.20,
            },
            {
                "action": "buy",
                "right": "put",
                "strike": 225,
                "expiry": "2026-07-17",
                "qty": 5,
                "limit_price": 2.10,
            },
        ],
        uw_regime={
            "iv_rank": 91,
            "gamma_flip": 192.5,
            "put_wall": 240.0,
            "call_wall": 250.0,
            "max_pain": 245.0,
        },
        account={"buying_power": 50000, "positions": []},
    )
    assert "legs" in preflight
    assert "pl_matrix" in preflight
    assert "max_loss" in preflight
    assert "max_gain" in preflight
    assert "uw_regime" in preflight
    assert "account_check" in preflight
    assert preflight["account_check"]["sufficient_buying_power"] is True


def test_brackets_default_50pct_take_profit_and_full_stop_for_spread():
    opening = {
        "structure": "bull_put_spread",
        "net_credit_dollar": 1050.0,
        "max_loss": -3950.0,
        "spread_width_dollar": 5000.0,
        "ticker": "ORCL",
    }
    brackets = build_brackets(opening)
    tp = next(b for b in brackets if b["bracket_type"] == "take_profit")
    sl = next(b for b in brackets if b["bracket_type"] == "stop_loss")
    assert tp["close_at_debit_or_credit"] == pytest.approx(525.0, abs=1)
    assert sl["close_at_debit_or_credit"] == pytest.approx(5000.0, abs=1)
    assert tp["oca_group"] == sl["oca_group"]


def test_brackets_for_csp_use_2x_credit_rule():
    opening = {
        "structure": "cash_secured_put",
        "net_credit_dollar": 500.0,
        "max_loss": -50000.0,
        "ticker": "AMD",
    }
    brackets = build_brackets(opening)
    sl = next(b for b in brackets if b["bracket_type"] == "stop_loss")
    assert sl["close_at_debit_or_credit"] == pytest.approx(1000.0, abs=1)


# ─── Phase D: mid_source provenance on legs ─────────────────


def test_build_preflight_tags_mid_source_unspecified_by_default():
    """Legs without a mid_source get tagged 'unspecified' so the trader
    sees the gap rather than silently trusting an unknown source."""
    from scripts.ib_order import build_preflight

    legs = [
        {
            "action": "SELL",
            "right": "P",
            "strike": 420.0,
            "qty": 1,
            "limit_price": 1.50,
        },
        {"action": "BUY", "right": "P", "strike": 415.0, "qty": 1, "limit_price": 0.50},
    ]
    pf = build_preflight(
        structure="bull_put_spread",
        ticker="SPY",
        spot=430.0,
        legs=legs,
        uw_regime={"label": "NEUTRAL"},
        account={"NLV": 1_000_000, "buying_power": 500_000, "cash": 100_000},
    )
    assert pf["mid_sources"] == ["unspecified"]
    for leg in pf["legs"]:
        assert leg["mid_source"] == "unspecified"


def test_build_preflight_preserves_caller_supplied_mid_source():
    """When the orchestrator passes mid_source per leg (e.g., 'IB' for
    broker-feed mids, 'UW' for analytical), preflight preserves the tag
    and surfaces the rollup in mid_sources."""
    from scripts.ib_order import build_preflight

    legs = [
        {
            "action": "SELL",
            "right": "P",
            "strike": 420.0,
            "qty": 1,
            "limit_price": 1.50,
            "mid_source": "IB",
        },
        {
            "action": "BUY",
            "right": "P",
            "strike": 415.0,
            "qty": 1,
            "limit_price": 0.50,
            "mid_source": "IB",
        },
    ]
    pf = build_preflight(
        structure="bull_put_spread",
        ticker="SPY",
        spot=430.0,
        legs=legs,
        uw_regime={"label": "NEUTRAL"},
        account={"NLV": 1_000_000, "buying_power": 500_000, "cash": 100_000},
    )
    assert pf["mid_sources"] == ["IB"]


def test_build_preflight_preserves_mid_provenance_from_macro_hedge():
    """P2-D: when macro_hedge feeds its leg list (with full mid_provenance
    objects) into build_preflight, the rich provenance survives the
    handoff. Gemini's tribunal review flagged this as a CRITICAL drop;
    this test refutes the claim and locks in the contract.
    """
    from scripts.ib_order import build_preflight
    from scripts.macro_hedge import build_macro_hedge

    snapshot = {
        "spot": 6200.0,
        "iv_atm_90d": 0.18,
        "chain_source": "UW",
        "spot_timestamp": "2026-06-05T10:00:00Z",
        "chain_timestamps": {"2026-08-15": "2026-06-05T10:00:00Z"},
        "chain": {
            "2026-08-15": {
                0.90: {"put": {"mid": 18.50, "iv": 0.21}},
                1.00: {"put": {"mid": 100.30, "iv": 0.18}},
            }
        },
    }
    hedge = build_macro_hedge(
        portfolio_notional=50_000_000,
        hedge_horizon_days=70,
        scenario="deep_correction_-10",
        structure="put_spread",
        snapshot=snapshot,
    )
    # Sanity: macro_hedge legs carry mid_provenance with UW source
    for leg in hedge["legs"]:
        assert leg["mid_source"] == "UW"
        assert "mid_provenance" in leg
        assert leg["mid_provenance"]["source"] == "UW"

    # Convert macro_hedge leg dicts to build_preflight's expected shape.
    # build_preflight needs 'action' in upper case ('BUY'/'SELL') and 'right'
    # in upper case ('P'/'C'); spread it through with overrides.
    pf_legs = [
        {
            **leg,
            "action": "BUY" if leg["action"] == "buy" else "SELL",
            "right": "P",
        }
        for leg in hedge["legs"]
    ]
    pf = build_preflight(
        structure="bull_put_spread",
        ticker="SPX",
        spot=6200.0,
        legs=pf_legs,
        uw_regime={"label": "NEUTRAL"},
        account={"NLV": 50_000_000, "buying_power": 25_000_000, "cash": 1_000_000},
    )
    # mid_provenance should ride through into preflight legs (Gemini G1 refutation)
    for leg in pf["legs"]:
        assert "mid_provenance" in leg, "build_preflight dropped mid_provenance"
        assert leg["mid_provenance"]["source"] == "UW"
        assert leg["mid_source"] == "UW"
    # Rollup at preflight level
    assert pf["mid_sources"] == ["UW"]
