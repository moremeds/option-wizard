from scripts.evaluate_position import evaluate_short_premium


def test_take_profit_when_above_50pct_decay():
    result = evaluate_short_premium(
        opening_credit=4.20,
        current_price=2.00,
        dte=52,
        delta=-0.18,
        structure="bull_put_spread",
    )
    assert result["recommended_action"] == "CLOSE"
    assert "take-profit" in result["rationale"].lower()


def test_stop_loss_when_loss_exceeds_2x_credit():
    result = evaluate_short_premium(
        opening_credit=4.20,
        current_price=10.00,
        dte=52,
        delta=-0.55,
        structure="cash_secured_put",
    )
    assert result["recommended_action"] in {"CLOSE", "ROLL"}
    rationale = result["rationale"].lower()
    assert "stop" in rationale or "loss" in rationale


def test_21_dte_forces_review():
    result = evaluate_short_premium(
        opening_credit=4.20,
        current_price=2.80,
        dte=21,
        delta=-0.30,
        structure="bull_put_spread",
    )
    assert result["recommended_action"] == "REVIEW"
    assert "21" in result["rationale"]


def test_below_21_dte_still_review():
    result = evaluate_short_premium(
        opening_credit=4.20,
        current_price=2.80,
        dte=15,
        delta=-0.30,
        structure="bull_put_spread",
    )
    assert result["recommended_action"] == "REVIEW"
    assert "gamma" in result["rationale"].lower()


def test_healthy_position_holds():
    result = evaluate_short_premium(
        opening_credit=4.20,
        current_price=3.80,
        dte=45,
        delta=-0.20,
        structure="bull_put_spread",
    )
    assert result["recommended_action"] == "HOLD"
