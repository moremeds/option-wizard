import pytest
from scripts.fair_coupon import (
    analyze_fcn,
    build_counter_offer_email,
    fair_coupon_proxy,
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
