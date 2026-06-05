"""Smoke tests for fair_aq_dq.

Tests are organized by section (matching framework §6):
  1. Refusal red lines (this task)
  2. KO probability + accumulation math (later tasks)
  3. Integration (later tasks)
"""

from __future__ import annotations

import pytest
from scripts.fair_aq_dq import (
    Quote,
    Snapshot,
    _accumulation_pv,
    _check_refusal_red_lines,
    _doubling_tail_leg_pv,
    _expected_alive_obs,
    _ko_call_leg_pv,
    _ko_probability,
    _nearest_expiry_to_tenor,
    _read_chain_mid,
    _short_put_leg_pv,
)

# ─── Mock snapshot fixtures ────────────────────────────────


def _mock_snapshot(iv_rank: float = 60.0, atr_14_pct: float | None = 0.02) -> Snapshot:
    """Default mock snapshot — populated with realistic mid-IV-regime values."""
    return Snapshot(
        spot=200.0,
        spot_source="TV",
        spot_timestamp="2026-06-05T10:00:00Z",
        chain={},
        chain_source="UW",
        chain_timestamps={},
        rv_30d=0.30,
        rv_90d=0.32,
        iv_rank=iv_rank,
        atr_14_pct_of_spot=atr_14_pct,
        earnings_date_iso=None,
    )


def _mock_quote(**overrides) -> Quote:
    defaults = dict(
        direction="AQ",
        ticker="MEGA-S",
        spot=200.0,
        strike_pct=0.95,
        ko_pct=1.03,
        tenor_months=12,
        obs_freq="daily",
        doubling_factor=2.0,
        daily_notional_usd=10_000.0,
        pb_quoted_yield_pa=0.09,
        settlement="cash",
    )
    defaults.update(overrides)
    return Quote(**defaults)


# ─── Refusal red lines (framework §6) ──────────────────────


def test_refusal_doubling_3x():
    q = _mock_quote(doubling_factor=3.0)
    s = _mock_snapshot()
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("doubling" in r.lower() for r in reasons)


def test_refusal_aq_iv_rank_below_30():
    q = _mock_quote(direction="AQ")
    s = _mock_snapshot(iv_rank=25.0)
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("iv rank" in r.lower() and "aq" in r.lower() for r in reasons)


def test_refusal_dq_iv_rank_below_30_does_not_trigger():
    """Rule only applies to AQ — DQ in low-IV regime is allowed."""
    q = _mock_quote(direction="DQ", ko_pct=0.97, strike_pct=1.05)
    s = _mock_snapshot(iv_rank=25.0)
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert not any("iv rank" in r.lower() for r in reasons)


def test_refusal_ko_within_1_atr():
    """KO at 102% spot with ATR(14) at 3% → KO within 1 ATR → refuse."""
    q = _mock_quote(ko_pct=1.02)
    s = _mock_snapshot(atr_14_pct=0.03)
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("ko" in r.lower() and "atr" in r.lower() for r in reasons)


def test_refusal_notional_exceeds_10pct_nlv():
    """daily_notional × n_obs > 10% NLV → refuse."""
    # 10000 daily × 252 obs = $2.52M total notional; NLV $1M → 252% > 10%
    q = _mock_quote(daily_notional_usd=10_000.0)
    s = _mock_snapshot()
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("notional" in r.lower() for r in reasons)


def test_refusal_tenor_above_18m():
    q = _mock_quote(tenor_months=24)
    s = _mock_snapshot()
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("tenor" in r.lower() for r in reasons)


def test_refusal_earnings_in_tenor_mid():
    """ER falls in middle 50% of tenor (3M–9M for a 12M AQ) → refuse."""
    q = _mock_quote(tenor_months=12)
    s = _mock_snapshot()
    # Set ER ~6M from quote start (assume "today" = quote start)
    s.earnings_date_iso = "2026-12-05"  # ~6 months from spec date 2026-06-05
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("earning" in r.lower() for r in reasons)


def test_no_refusal_on_clean_quote():
    """Baseline: clean quote returns empty list.

    ER date placement: snapshot timestamp is 2026-06-05, tenor 12M.
    Middle 50% = days [90, 270] from start = [2026-09-03, 2027-03-02].
    Using 2026-07-05 puts ER at day 30 ≈ 8% → clearly outside.
    """
    q = _mock_quote(doubling_factor=2.0, tenor_months=12)
    s = _mock_snapshot(iv_rank=60.0, atr_14_pct=0.02)
    s.earnings_date_iso = "2026-07-05"  # 30 days in → 8% of tenor, outside middle 50%
    reasons = _check_refusal_red_lines(
        q,
        s,
        nlv_usd=50_000_000.0,  # huge NLV so notional is small %
    )
    assert reasons == []


# ─── KO probability ────────────────────────────────────────


def test_ko_prob_zero_when_tenor_zero():
    p = _ko_probability(
        spot=100.0, ko_barrier=103.0, iv=0.30, tenor_yr=0.0, obs_freq="daily"
    )
    assert p == 0.0


def test_ko_prob_increases_with_vol():
    """Higher vol → higher KO probability."""
    p_low = _ko_probability(
        spot=100.0, ko_barrier=103.0, iv=0.10, tenor_yr=1.0, obs_freq="daily"
    )
    p_high = _ko_probability(
        spot=100.0, ko_barrier=103.0, iv=0.40, tenor_yr=1.0, obs_freq="daily"
    )
    assert p_high > p_low


def test_ko_prob_increases_when_ko_closer_to_spot():
    """KO at 102% spot → higher hit prob than KO at 110% spot."""
    p_near = _ko_probability(
        spot=100.0, ko_barrier=102.0, iv=0.30, tenor_yr=1.0, obs_freq="daily"
    )
    p_far = _ko_probability(
        spot=100.0, ko_barrier=110.0, iv=0.30, tenor_yr=1.0, obs_freq="daily"
    )
    assert p_near > p_far


def test_ko_prob_discrete_correction_lowers_prob():
    """Broadie-Glasserman discrete correction should yield a LOWER hit prob
    than naive continuous monitoring would imply, because effective barrier
    is shifted away from spot."""
    p_daily = _ko_probability(
        spot=100.0, ko_barrier=103.0, iv=0.30, tenor_yr=1.0, obs_freq="daily"
    )
    p_monthly = _ko_probability(
        spot=100.0, ko_barrier=103.0, iv=0.30, tenor_yr=1.0, obs_freq="monthly"
    )
    # Fewer obs per year → larger barrier shift → lower hit prob
    assert p_monthly < p_daily


def test_ko_prob_in_unit_interval():
    """Output bounded in [0, 1]."""
    for iv in [0.05, 0.20, 0.50, 1.00, 2.00]:
        p = _ko_probability(
            spot=100.0, ko_barrier=103.0, iv=iv, tenor_yr=1.0, obs_freq="daily"
        )
        assert 0.0 <= p <= 1.0


# ─── Accumulation PV ───────────────────────────────────────


def test_accumulation_pv_zero_ko_prob_uses_all_obs():
    """With ko_prob=0, all observations contribute."""
    pv = _accumulation_pv(
        direction="AQ",
        spot=100.0,
        strike_pct=0.95,
        daily_notional=10_000.0,
        ko_prob=0.0,
        tenor_months=12,
        obs_freq="daily",
        r=0.04,
    )
    # 10000 × 252 × discount(0.5 yr @ 4%) ≈ 2,520,000 × 0.9802 ≈ 2,470,104
    assert 2_400_000 < pv < 2_550_000


def test_accumulation_pv_high_ko_prob_reduces_pv():
    """Higher ko_prob → fewer alive observations → smaller accumulation PV."""
    pv_no_ko = _accumulation_pv(
        direction="AQ",
        spot=100.0,
        strike_pct=0.95,
        daily_notional=10_000.0,
        ko_prob=0.0,
        tenor_months=12,
        obs_freq="daily",
        r=0.04,
    )
    pv_high_ko = _accumulation_pv(
        direction="AQ",
        spot=100.0,
        strike_pct=0.95,
        daily_notional=10_000.0,
        ko_prob=0.999,
        tenor_months=12,
        obs_freq="daily",
        r=0.04,
    )
    assert pv_high_ko < pv_no_ko * 0.25  # ratio expected ~14-16%


def test_accumulation_pv_increases_with_tenor():
    pv_6m = _accumulation_pv("AQ", 100.0, 0.95, 10_000.0, 0.0, 6, "daily", 0.04)
    pv_12m = _accumulation_pv("AQ", 100.0, 0.95, 10_000.0, 0.0, 12, "daily", 0.04)
    assert pv_12m > pv_6m


# ─── Chain leg helpers (Task 12) ───────────────────────────


def _mock_chain():
    """Mock chain at 1 expiry (12M from today)."""
    return {
        "2027-06-18": {
            0.50: {"put": {"mid": 0.50, "iv": 0.55}},
            0.80: {"put": {"mid": 1.80, "iv": 0.42}},
            0.95: {"put": {"mid": 5.20, "iv": 0.38}, "call": {"mid": 15.10, "iv": 0.30}},
            1.00: {"put": {"mid": 8.10, "iv": 0.36}, "call": {"mid": 8.20, "iv": 0.31}},
            1.03: {"put": {"mid": 10.40, "iv": 0.35}, "call": {"mid": 4.10, "iv": 0.34}},
            1.05: {"call": {"mid": 2.85, "iv": 0.34}},
            1.10: {"call": {"mid": 1.10, "iv": 0.33}},
        }
    }


def test_nearest_expiry_to_tenor():
    chain = {"2026-12-18": {}, "2027-06-18": {}, "2027-12-17": {}}
    # 12M from 2026-06-05 → ~2027-06-18 is closest
    nearest = _nearest_expiry_to_tenor(chain, tenor_months=12,
                                       quote_start_iso="2026-06-05T00:00:00Z")
    assert nearest == "2027-06-18"


def test_read_chain_mid_direct_hit():
    chain = _mock_chain()
    mid = _read_chain_mid(chain, expiry="2027-06-18",
                         strike_pct=0.95, right="put")
    assert mid == 5.20


def test_read_chain_mid_missing_returns_none():
    chain = _mock_chain()
    mid = _read_chain_mid(chain, expiry="2027-06-18",
                         strike_pct=0.30, right="put")
    assert mid is None


def test_short_put_leg_pv_doubling_adds_adverse_bonus():
    """Doubling scales the ADVERSE-region bonus, not the entire base premium.

    Pass-2 finding (Codex-4 + Gemini-1): blanket × doubling_factor over-credits
    the base notional. With adverse_region_prob=0.40, expect:
      pv_1x = base_premium  (no doubling bonus)
      pv_2x = base_premium × (1 + 1 × 0.40) = 1.40 × pv_1x  (not 2× pv_1x)
    """
    pv_1x = _short_put_leg_pv(put_mid=5.20, shares_per_obs=50.0,
                              alive_obs=180.0, doubling_factor=1.0)
    pv_2x = _short_put_leg_pv(put_mid=5.20, shares_per_obs=50.0,
                              alive_obs=180.0, doubling_factor=2.0)
    assert pv_2x == pytest.approx(1.40 * pv_1x, rel=1e-3)
    # And not 2× (the previously-broken behavior)
    assert pv_2x < 1.6 * pv_1x


def test_short_put_leg_pv_no_doubling_unchanged():
    """At doubling=1.0 the leg PV is purely base premium."""
    pv = _short_put_leg_pv(put_mid=5.20, shares_per_obs=50.0,
                           alive_obs=180.0, doubling_factor=1.0)
    expected_base = 5.20 * 50.0 * 180.0
    assert pv == pytest.approx(expected_base, rel=1e-6)


def test_ko_call_leg_pv_zero_when_forfeited_zero():
    """No KO → no forfeited observations → PB call leg value zero."""
    pv = _ko_call_leg_pv(call_mid=4.10, shares_per_obs=50.0,
                        forfeited_obs=0.0)
    assert pv == 0.0


def test_doubling_tail_leg_pv_zero_when_tail_prob_zero():
    pv = _doubling_tail_leg_pv(tail_leg_mid=0.50, cumulative_shares=12600.0,
                              doubling_factor=2.0, tail_activation_prob=0.0)
    assert pv == 0.0


def test_expected_alive_obs_edge_cases():
    """Verify the iid-survival expectation formula.

    Note on semantics: cumulative ko_prob_total = 1 − q^n where q is per-obs
    survival. A cumulative ko_prob = 0.9999 means "KO is near-certain
    *during the tenor*" but the iid model still admits ~28 alive observations
    in expectation (KO triggers on average around obs 28, not obs 1).
    """
    assert _expected_alive_obs(0.0, 252) == 252.0
    # ko_prob=0.9999 with n=252 → p_per_obs ≈ 0.0359, E[N_alive] ≈ 27.85
    alive_near_certain = _expected_alive_obs(0.9999, 252)
    assert 20.0 <= alive_near_certain <= 35.0
    # ko_prob=0.5, n=252 → E[N_alive] ≈ 182
    alive_half = _expected_alive_obs(0.5, 252)
    assert 170.0 <= alive_half <= 200.0
    assert alive_half > 252 * 0.5  # exact > simple "n × (1-ko_prob)" approximation
    assert alive_half < 252        # bounded above by n
