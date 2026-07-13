import numpy as np
from scripts.fair_coupon import (
    analyze_fcn,
    analyze_fcn_basket,
    build_counter_offer_email,
    fair_coupon_chain,
    fair_coupon_proxy,
    joint_ki_prob_mc,
    single_name_ki_prob,
)


def test_single_name_ki_prob_matches_closed_form():
    p = single_name_ki_prob(vol=0.804, barrier=0.75, days=126)
    assert 0.60 <= p <= 0.63


def test_fair_coupon_proxy_basic():
    fc = fair_coupon_proxy(
        p_ki=0.50,
        expected_loss_given_ki=0.50,
        expected_alive_months=3.5,
        discount_rate=0.045,
        tenor_years=0.5,
    )
    assert 0.83 <= fc <= 0.85


def test_fair_coupon_proxy_zero_ki_returns_zero():
    assert (
        fair_coupon_proxy(
            p_ki=0.0,
            expected_loss_given_ki=0.5,
            expected_alive_months=3.5,
            discount_rate=0.045,
            tenor_years=0.5,
        )
        == 0.0
    )


def test_analyze_fcn_emits_strike_ladder_by_default():
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.70, 0.75, 0.80, 0.85],
        tenor_months=6,
        observation_months=3,
        snapshot=snapshot,
    )
    assert len(result["ladder"]) == 4
    rungs = {r["strike_pct"]: r for r in result["ladder"]}
    assert "below" in rungs[0.70]["dealer_zone"].lower()
    assert "above" in rungs[0.80]["dealer_zone"].lower()


def test_analyze_fcn_with_quoted_coupon_returns_verdict():
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.75],
        tenor_months=6,
        observation_months=3,
        pb_quoted_coupon=0.18,
        snapshot=snapshot,
    )
    rung = result["ladder"][0]
    assert rung["pb_quoted_coupon"] == 0.18
    assert rung["verdict"] in {"fair", "rich", "cheap"}


def test_analyze_fcn_surfaces_top_level_verdict_at_anchor_strike():
    # SKILL.md hard rule #5: "FCN output is ... a fair vs quoted verdict".
    # Top-level verdict mirrors the rung closest to the 75% anchor strike
    # (FCN industry default); anchor_strike_pct is reported so the caller
    # knows which rung drove the verdict.
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.70, 0.75, 0.80, 0.85],
        tenor_months=6,
        observation_months=3,
        pb_quoted_coupon=0.18,
        snapshot=snapshot,
    )
    assert result["anchor_strike_pct"] == 0.75
    anchor_rung = next(r for r in result["ladder"] if r["strike_pct"] == 0.75)
    assert result["verdict"] == anchor_rung["verdict"]
    assert result["verdict"] in {"fair", "rich", "cheap"}


def test_analyze_fcn_top_level_verdict_none_when_no_quoted_coupon():
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.70, 0.75, 0.80, 0.85],
        tenor_months=6,
        observation_months=3,
        snapshot=snapshot,
    )
    assert result["verdict"] is None
    assert result["anchor_strike_pct"] == 0.75


def test_analyze_fcn_checklist_flags_below_flip_strike():
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.70],
        tenor_months=6,
        observation_months=3,
        snapshot=snapshot,
    )
    flags = result["ladder"][0]["checklist"]
    item1 = next(f for f in flags if f["id"] == "strike_vs_gamma_flip")
    assert item1["status"] == "FAIL"


def test_analyze_fcn_attaches_counter_offer_email_on_fail():
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.70],
        tenor_months=6,
        observation_months=3,
        snapshot=snapshot,
    )
    rung = result["ladder"][0]
    assert "counter_offer_email" in rung
    assert "Hi" in rung["counter_offer_email"]
    assert (
        "您好" in rung["counter_offer_email"] or "你好" in rung["counter_offer_email"]
    )


def test_analyze_fcn_no_email_when_all_pass():
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 100.0, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.85],
        tenor_months=6,
        observation_months=3,
        snapshot=snapshot,
    )
    rung = result["ladder"][0]
    assert "counter_offer_email" not in rung


def test_counter_offer_email_contains_chinese_and_english_sections():
    rung = {
        "strike_pct": 0.75,
        "strike_dollar": 183.44,
        "p_ki_6m": 0.613,
        "fair_coupon_base": 1.027,
        "verdict": "rich",
        "pb_quoted_coupon": 0.18,
        "dealer_zone": "RISK: below gamma flip",
        "checklist": [
            {
                "id": "strike_vs_gamma_flip",
                "status": "FAIL",
                "detail": "strike $183 below flip $193",
            },
            {
                "id": "markup_vs_iv_rank",
                "status": "WARN",
                "detail": "quote at 18% of model",
            },
        ],
    }
    email = build_counter_offer_email(
        ticker="ORCL",
        rung=rung,
        recommended_strike_pct=0.80,
        recommended_coupon_low=0.24,
        recommended_coupon_high=0.28,
    )
    assert "Subject:" in email
    assert "你好" in email or "您好" in email
    assert "Hi" in email
    assert "ORCL" in email
    assert "0.80" in email or "80%" in email


# --- Task 2.4: basket FCN ---


def test_joint_ki_prob_at_full_correlation_equals_single_name():
    p_either, _, _ = joint_ki_prob_mc(
        vol_a=0.80,
        vol_b=0.80,
        rho=0.999,
        barrier=0.50,
        days=252,
        n_sims=5000,
        seed=42,
    )
    from scripts.fair_coupon import single_name_ki_prob

    single = single_name_ki_prob(0.80, 0.50, 252)
    assert abs(p_either - single) < 0.05


def test_joint_ki_prob_low_correlation_higher_than_single():
    p_either, _, _ = joint_ki_prob_mc(
        vol_a=0.40,
        vol_b=0.40,
        rho=0.0,
        barrier=0.70,
        days=126,
        n_sims=5000,
        seed=42,
    )
    from scripts.fair_coupon import single_name_ki_prob

    single = single_name_ki_prob(0.40, 0.70, 126)
    assert p_either > single


def test_basket_analyze_returns_per_name_and_basket():
    snapshots = {
        "INTC": {
            "spot": 109.33,
            "iv": 0.82,
            "rv": 1.01,
            "iv_rank": 76,
            "skew_25d": -0.15,
            "max_drawdown_5y": -0.643,
            "gex_levels": {"gamma_flip": 95.0, "put_wall": 100.0, "call_wall": 115.0},
        },
        "AMD": {
            "spot": 510.13,
            "iv": 0.70,
            "rv": 0.85,
            "iv_rank": 94,
            "skew_25d": -0.18,
            "max_drawdown_5y": -0.630,
            "gex_levels": {"gamma_flip": 460.0, "put_wall": 495.0, "call_wall": 520.0},
        },
    }
    corr = np.array([[1.0, 0.7], [0.7, 1.0]])
    result = analyze_fcn_basket(
        tickers=["INTC", "AMD"],
        snapshots=snapshots,
        corr_matrix=corr,
        strike_pct=0.55,
        tenor_months=6,
        observation_months=3,
    )
    assert "per_name" in result
    assert "basket" in result
    assert result["basket"]["p_ki_either"] > 0
    assert "diversification_premium_pp" in result["basket"]


# ─── Phase B: chain-aware fair coupon ──────────────────────


def test_fair_coupon_chain_basic_arithmetic():
    """put_mid $5.20 at strike $75, alive 3.5M → fair coupon ≈ 23.8% pa.

    fair_coupon_pa = put_mid / (strike_dollar × alive_yr)
                    = 5.20 / (75 × 3.5/12)
                    = 5.20 / 21.875
                    ≈ 0.2377
    """
    fc = fair_coupon_chain(
        put_mid_per_share=5.20,
        strike_dollar=75.0,
        expected_alive_months=3.5,
    )
    assert 0.23 < fc < 0.24


def test_fair_coupon_chain_zero_strike_returns_nan():
    fc = fair_coupon_chain(
        put_mid_per_share=5.20, strike_dollar=0.0, expected_alive_months=3.5
    )
    import math

    assert math.isnan(fc)


def test_fair_coupon_chain_none_mid_returns_nan():
    fc = fair_coupon_chain(
        put_mid_per_share=None, strike_dollar=75.0, expected_alive_months=3.5
    )
    import math

    assert math.isnan(fc)


def test_analyze_fcn_uses_chain_when_snapshot_includes_chain():
    """Snapshot with `chain` triggers chain-priced fair_coupon and tags
    provenance as 'chain'."""
    snapshot = {
        "spot": 100.0,
        "iv": 0.40,
        "rv": 0.30,
        "iv_rank": 60,
        "skew_25d": -0.10,
        "max_drawdown_5y": -0.50,
        "gex_levels": {"gamma_flip": 80.0, "put_wall": 90.0, "call_wall": 110.0},
        "chain": {
            "2026-12-18": {
                0.75: {"put": {"mid": 4.10, "iv": 0.45}},
                0.80: {"put": {"mid": 5.30, "iv": 0.42}},
            }
        },
        "chain_source": "UW",
        "chain_timestamps": {"2026-12-18": "2026-06-05T10:00:00Z"},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.75, 0.80],
        tenor_months=6,
        observation_months=3,
        snapshot=snapshot,
        quote_start_iso="2026-06-05T00:00:00Z",
    )
    for rung in result["ladder"]:
        assert rung["fair_coupon_source"] == "chain", (
            f"strike {rung['strike_pct']}: expected chain pricing, got "
            f"{rung['fair_coupon_source']}"
        )
        # Provenance leg points back to UW chain
        assert rung["fair_coupon_provenance"]["leg"]["source"] == "UW"
        assert "put" in rung["fair_coupon_provenance"]["leg"]["detail"]


def test_analyze_fcn_falls_back_to_model_when_chain_missing_strike():
    """Chain present but no listed mid at 0.70 strike → model fallback for
    that rung, chain pricing for the strike that IS listed."""
    snapshot = {
        "spot": 100.0,
        "iv": 0.40,
        "rv": 0.30,
        "iv_rank": 60,
        "skew_25d": -0.10,
        "max_drawdown_5y": -0.50,
        "gex_levels": {"gamma_flip": 80.0, "put_wall": 90.0, "call_wall": 110.0},
        "chain": {
            "2026-12-18": {
                # 0.70 deliberately missing
                0.80: {"put": {"mid": 5.30, "iv": 0.42}},
            }
        },
        "chain_source": "UW",
        "chain_timestamps": {"2026-12-18": "2026-06-05T10:00:00Z"},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.70, 0.80],
        tenor_months=6,
        observation_months=3,
        snapshot=snapshot,
        quote_start_iso="2026-06-05T00:00:00Z",
    )
    by_strike = {r["strike_pct"]: r for r in result["ladder"]}
    assert by_strike[0.70]["fair_coupon_source"] == "model"
    assert by_strike[0.70]["fair_coupon_provenance"]["leg"]["source"] == "fallback"
    assert by_strike[0.80]["fair_coupon_source"] == "chain"


def test_analyze_fcn_no_chain_keeps_model_path_unchanged():
    """Snapshot without `chain` key continues to use the model proxy —
    proves Phase B backward compatibility."""
    snapshot = {
        "spot": 244.58,
        "iv": 0.804,
        "rv": 0.610,
        "iv_rank": 91,
        "skew_25d": -0.20,
        "max_drawdown_5y": -0.582,
        "gex_levels": {"gamma_flip": 192.5, "put_wall": 240.0, "call_wall": 250.0},
    }
    result = analyze_fcn(
        ticker="ORCL",
        strike_pcts=[0.75],
        tenor_months=6,
        observation_months=3,
        snapshot=snapshot,
    )
    rung = result["ladder"][0]
    assert rung["fair_coupon_source"] == "model"
    # Provenance still attached so trader can see the model assumption
    assert rung["fair_coupon_provenance"]["leg"]["source"] == "fallback"
    assert "BSM" in rung["fair_coupon_provenance"]["leg"]["detail"]


def test_skill_md_fcn_chain_example_runs_end_to_end():
    """P6-Pass-6: lock in the SKILL.md FCN chain-path example so doc rot
    breaks the test. If someone edits the SKILL.md snippet, this test
    catches a divergence from what the script actually accepts."""
    snap = {
        "spot": 200.0,
        "iv": 0.35,
        "rv": 0.30,
        "iv_rank": 55,
        "skew_25d": 0.04,
        "max_drawdown_5y": -0.45,
        "gex_levels": {"gamma_flip": 195.0, "put_wall": 180.0, "call_wall": 220.0},
        "chain_source": "UW",
        "spot_timestamp": "2026-06-05T10:00:00Z",
        "chain_timestamps": {"2026-12-18": "2026-06-05T10:00:00Z"},
        "chain": {
            "2026-12-18": {
                0.70: {"put": {"mid": 1.20, "iv": 0.42}},
                0.75: {"put": {"mid": 2.40, "iv": 0.40}},
                0.80: {"put": {"mid": 4.80, "iv": 0.38}},
                0.85: {"put": {"mid": 9.10, "iv": 0.36}},
            }
        },
    }
    r = analyze_fcn(
        "ORCL",
        strike_pcts=(0.70, 0.75, 0.80, 0.85),
        tenor_months=6,
        observation_months=3,
        pb_quoted_coupon=0.12,
        snapshot=snap,
        quote_start_iso="2026-06-05T00:00:00Z",
    )
    # All 4 rungs should price off chain (exact match: chain keys equal request)
    assert len(r["ladder"]) == 4
    for rung in r["ladder"]:
        assert rung["fair_coupon_source"] == "chain", (
            f"SKILL.md example rung {rung['strike_pct']} fell back to model — "
            f"docs and code have diverged"
        )
        assert rung["fair_coupon_provenance"]["leg"]["source"] == "UW"
    assert r["verdict"] in {"fair", "rich", "cheap"}
