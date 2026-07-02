import pytest
from scripts.term_curve import (
    atm_iv_from_chain_rows,
    label_regime,
    summarize_regime,
)

# ---------- label_regime ----------


def test_label_regime_pure_contango():
    pairs = label_regime({"2026-07-17": 0.40, "2026-08-21": 0.43, "2026-09-19": 0.46})
    assert [p["regime"] for p in pairs] == ["contango", "contango"]
    assert pairs[0]["basis"] == pytest.approx(0.03, abs=1e-9)


def test_label_regime_pure_inversion():
    # all later expiries cheaper — multiple stacked catalysts
    pairs = label_regime({"2026-07-17": 0.55, "2026-08-21": 0.48, "2026-09-19": 0.42})
    assert [p["regime"] for p in pairs] == ["inverted", "inverted"]
    assert pairs[1]["basis"] == pytest.approx(-0.06, abs=1e-9)


def test_label_regime_mixed_catalyst_isolated_to_middle():
    # 6/4 TSLA-like pattern: front cheap, middle catalyst rich, back cheap again
    pairs = label_regime(
        {
            "2026-07-17": 0.42,
            "2026-08-21": 0.55,  # ER expiry — inverted from front
            "2026-09-19": 0.46,  # back to normal after catalyst
            "2027-01-15": 0.48,
        }
    )
    regimes = [p["regime"] for p in pairs]
    assert regimes == ["contango", "inverted", "contango"]


def test_label_regime_flat_within_default_eps():
    pairs = label_regime({"2026-07-17": 0.400, "2026-08-21": 0.405})
    assert pairs[0]["regime"] == "flat"


def test_label_regime_eps_threshold_configurable():
    # tighter eps -> same 0.5pp diff now reads as contango
    atm = {"2026-07-17": 0.400, "2026-08-21": 0.405}
    assert label_regime(atm, eps_flat=0.001)[0]["regime"] == "contango"


def test_label_regime_sorts_input_by_expiry():
    # caller passes expiries out of order; helper must sort
    pairs = label_regime({"2026-09-19": 0.46, "2026-07-17": 0.40, "2026-08-21": 0.43})
    assert pairs[0]["from_expiry"] == "2026-07-17"
    assert pairs[0]["to_expiry"] == "2026-08-21"
    assert pairs[1]["from_expiry"] == "2026-08-21"
    assert pairs[1]["to_expiry"] == "2026-09-19"


def test_label_regime_carries_iv_and_basis_fields():
    pairs = label_regime({"2026-07-17": 0.40, "2026-08-21": 0.55})
    pair = pairs[0]
    assert pair["iv_from"] == 0.40
    assert pair["iv_to"] == 0.55
    assert pair["basis"] == pytest.approx(0.15, abs=1e-9)


def test_label_regime_raises_on_single_expiry():
    with pytest.raises(ValueError, match="at least 2"):
        label_regime({"2026-07-17": 0.40})


def test_label_regime_raises_on_negative_iv():
    with pytest.raises(ValueError, match="non-negative"):
        label_regime({"2026-07-17": 0.40, "2026-08-21": -0.05})


def test_label_regime_raises_on_nan_iv():
    with pytest.raises(ValueError, match="non-negative"):
        label_regime({"2026-07-17": 0.40, "2026-08-21": float("nan")})


def test_label_regime_raises_on_negative_eps():
    with pytest.raises(ValueError, match="eps_flat"):
        label_regime({"2026-07-17": 0.40, "2026-08-21": 0.43}, eps_flat=-0.01)


# ---------- summarize_regime ----------


def test_summarize_all_contango():
    pairs = label_regime({"2026-07-17": 0.40, "2026-08-21": 0.43, "2026-09-19": 0.46})
    assert summarize_regime(pairs) == "all_contango"


def test_summarize_all_inverted():
    pairs = label_regime({"2026-07-17": 0.55, "2026-08-21": 0.48, "2026-09-19": 0.42})
    assert summarize_regime(pairs) == "all_inverted"


def test_summarize_all_flat():
    pairs = label_regime({"2026-07-17": 0.400, "2026-08-21": 0.405})
    assert summarize_regime(pairs) == "all_flat"


def test_summarize_mixed_contango_inverted():
    pairs = label_regime({"2026-07-17": 0.42, "2026-08-21": 0.55, "2026-09-19": 0.46})
    assert summarize_regime(pairs) == "mixed_contango_inverted"


def test_summarize_mixed_with_flat_no_opposite_sign():
    # flat then contango, no inversion -> "mixed_with_flat"
    pairs = label_regime({"2026-07-17": 0.400, "2026-08-21": 0.405, "2026-09-19": 0.45})
    assert summarize_regime(pairs) == "mixed_with_flat"


def test_summarize_raises_on_empty():
    with pytest.raises(ValueError, match="empty"):
        summarize_regime([])


# ---------- atm_iv_from_chain_rows ----------


def test_atm_iv_from_chain_picks_closest_strike_and_averages():
    rows = [
        {"strike": 380, "call_iv": 0.35, "put_iv": 0.38},
        {"strike": 390, "call_iv": 0.34, "put_iv": 0.36},  # closest to spot 391
        {"strike": 400, "call_iv": 0.33, "put_iv": 0.35},
    ]
    assert atm_iv_from_chain_rows(rows, spot=391.0) == pytest.approx(0.35, abs=1e-9)


def test_atm_iv_falls_back_to_single_side_when_other_missing():
    rows = [
        {"strike": 100, "call_iv": 0.40, "put_iv": None},
    ]
    assert atm_iv_from_chain_rows(rows, spot=100) == pytest.approx(0.40, abs=1e-9)


def test_atm_iv_returns_none_when_both_sides_missing():
    rows = [
        {"strike": 100, "call_iv": None, "put_iv": None},
    ]
    assert atm_iv_from_chain_rows(rows, spot=100) is None


def test_atm_iv_skips_nan_and_negative_iv():
    rows = [
        {"strike": 100, "call_iv": float("nan"), "put_iv": -0.1},
    ]
    assert atm_iv_from_chain_rows(rows, spot=100) is None


def test_atm_iv_accepts_string_iv_field():
    # UW sometimes returns IV as a string-formatted decimal
    rows = [
        {"strike": 100, "call_iv": "0.40", "put_iv": "0.42"},
    ]
    assert atm_iv_from_chain_rows(rows, spot=100) == pytest.approx(0.41, abs=1e-9)


def test_atm_iv_custom_keys():
    rows = [
        {"k": 100, "cIV": 0.40, "pIV": 0.42},
    ]
    out = atm_iv_from_chain_rows(
        rows,
        spot=100,
        strike_key="k",
        call_iv_key="cIV",
        put_iv_key="pIV",
    )
    assert out == pytest.approx(0.41, abs=1e-9)


def test_atm_iv_raises_on_empty_rows():
    with pytest.raises(ValueError, match="empty"):
        atm_iv_from_chain_rows([], spot=100)


def test_atm_iv_raises_on_non_positive_spot():
    with pytest.raises(ValueError, match="positive"):
        atm_iv_from_chain_rows([{"strike": 100, "call_iv": 0.4}], spot=0)


# ---------- atm_iv_from_chain_rows: UW per-contract shape (U4) ----------


def test_atm_iv_auto_pivots_uw_per_contract_shape():
    # get_chains_for_expiry actual shape: one row per (strike, option_type),
    # strike as string, single `iv` field. Observed live 2026-07-02.
    rows = [
        {"strike": "380", "option_type": "call", "iv": 0.35},
        {"strike": "380", "option_type": "put", "iv": 0.38},
        {"strike": "390", "option_type": "call", "iv": 0.34},
        {"strike": "390", "option_type": "put", "iv": 0.36},
        {"strike": "400", "option_type": "call", "iv": 0.33},
        {"strike": "400", "option_type": "put", "iv": 0.35},
    ]
    assert atm_iv_from_chain_rows(rows, spot=391.0) == pytest.approx(0.35, abs=1e-9)


def test_atm_iv_auto_pivot_handles_null_iv_and_missing_side():
    rows = [
        {"strike": "100", "option_type": "call", "iv": None},
        {"strike": "100", "option_type": "put", "iv": 0.42},
    ]
    assert atm_iv_from_chain_rows(rows, spot=100) == pytest.approx(0.42, abs=1e-9)


def test_atm_iv_wide_shape_still_bypasses_pivot():
    # rows already carrying call_iv_key must NOT be pivoted (regression
    # guard: pivot only fires when call_iv_key is absent).
    rows = [
        {"strike": 100, "option_type": "call", "call_iv": 0.40, "put_iv": 0.42},
    ]
    assert atm_iv_from_chain_rows(rows, spot=100) == pytest.approx(0.41, abs=1e-9)


# ---------- atm_iv_by_expiry_from_term_structure (U4 / R6) ----------


def test_term_structure_extracts_held_expiries_only():
    from scripts.term_curve import atm_iv_by_expiry_from_term_structure

    rows = [
        {"expiry": "2026-07-17", "volatility": "0.368", "dte": 15},
        {"expiry": "2026-08-21", "volatility": "0.382", "dte": 50},
        {"expiry": "2026-12-18", "volatility": "0.418", "dte": 169},
    ]
    out = atm_iv_by_expiry_from_term_structure(
        rows, ["2026-07-17", "2026-12-18"]
    )
    assert out == {"2026-07-17": 0.368, "2026-12-18": 0.418}


def test_term_structure_missing_expiry_simply_absent():
    from scripts.term_curve import atm_iv_by_expiry_from_term_structure

    rows = [{"expiry": "2026-07-17", "volatility": "0.368", "dte": 15}]
    out = atm_iv_by_expiry_from_term_structure(
        rows, ["2026-07-10", "2026-07-17"]
    )
    assert out == {"2026-07-17": 0.368}  # 2026-07-10 not in rows -> absent


def test_term_structure_result_feeds_label_regime_directly():
    from scripts.term_curve import atm_iv_by_expiry_from_term_structure

    rows = [
        {"expiry": "2026-07-17", "volatility": "0.368"},
        {"expiry": "2026-08-21", "volatility": "0.382"},
    ]
    atm = atm_iv_by_expiry_from_term_structure(rows, ["2026-07-17", "2026-08-21"])
    pairs = label_regime(atm)
    assert pairs[0]["regime"] == "contango"


# ---------- Pass-2 codex-review fix: pivot honors custom key names ----------


def test_atm_iv_auto_pivot_honors_custom_call_put_keys():
    # Custom key names combined with per-contract-shaped rows previously
    # returned None: the pivot always wrote hardcoded call_iv/put_iv, so
    # the caller's lookup under cIV/pIV found nothing (codex-review finding).
    rows = [
        {"k": "390", "option_type": "call", "iv": 0.34},
        {"k": "390", "option_type": "put", "iv": 0.36},
    ]
    out = atm_iv_from_chain_rows(
        rows, spot=390, strike_key="k", call_iv_key="cIV", put_iv_key="pIV"
    )
    assert out == pytest.approx(0.35, abs=1e-9)
