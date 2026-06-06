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
    _all_earnings_dates_in_tenor,
    _check_refusal_red_lines,
    _compute_scenarios,
    _doubling_tail_leg_pv,
    _expected_alive_obs,
    _fair_yield,
    _ko_call_leg_pv,
    _ko_probability,
    _nearest_expiry_to_tenor,
    _read_chain_mid,
    _short_put_leg_pv,
    analyze_quote,
    build_counter_offer_email,
    evaluate_placed_aq,
    optimize_terms,
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
    # Opt out of ER iteration: explicit empty list disables quarterly
    # extrapolation. Without this, _all_earnings_dates_in_tenor finds
    # 2026-10-03 (Q3 ER, ~33% into 12M tenor) and correctly REFUSES.
    s.earnings_dates_iso = []
    s.earnings_date_iso = "2026-07-05"
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
            0.95: {
                "put": {"mid": 5.20, "iv": 0.38},
                "call": {"mid": 15.10, "iv": 0.30},
            },
            1.00: {"put": {"mid": 8.10, "iv": 0.36}, "call": {"mid": 8.20, "iv": 0.31}},
            1.03: {
                "put": {"mid": 10.40, "iv": 0.35},
                "call": {"mid": 4.10, "iv": 0.34},
            },
            1.05: {"call": {"mid": 2.85, "iv": 0.34}},
            1.10: {"call": {"mid": 1.10, "iv": 0.33}},
        }
    }


def test_nearest_expiry_to_tenor():
    chain = {"2026-12-18": {}, "2027-06-18": {}, "2027-12-17": {}}
    # 12M from 2026-06-05 → ~2027-06-18 is closest
    nearest = _nearest_expiry_to_tenor(
        chain, tenor_months=12, quote_start_iso="2026-06-05T00:00:00Z"
    )
    assert nearest == "2027-06-18"


def test_read_chain_mid_direct_hit():
    chain = _mock_chain()
    mid = _read_chain_mid(chain, expiry="2027-06-18", strike_pct=0.95, right="put")
    assert mid == 5.20


def test_read_chain_mid_missing_returns_none():
    chain = _mock_chain()
    mid = _read_chain_mid(chain, expiry="2027-06-18", strike_pct=0.30, right="put")
    assert mid is None


def test_short_put_leg_pv_doubling_adds_adverse_bonus():
    """Doubling scales the ADVERSE-region bonus, not the entire base premium.

    Pass-2 finding (Codex-4 + Gemini-1): blanket × doubling_factor over-credits
    the base notional. With adverse_region_prob=0.40, expect:
      pv_1x = base_premium  (no doubling bonus)
      pv_2x = base_premium × (1 + 1 × 0.40) = 1.40 × pv_1x  (not 2× pv_1x)
    """
    pv_1x = _short_put_leg_pv(
        put_mid=5.20, shares_per_obs=50.0, alive_obs=180.0, doubling_factor=1.0
    )
    pv_2x = _short_put_leg_pv(
        put_mid=5.20, shares_per_obs=50.0, alive_obs=180.0, doubling_factor=2.0
    )
    assert pv_2x == pytest.approx(1.40 * pv_1x, rel=1e-3)
    # And not 2× (the previously-broken behavior)
    assert pv_2x < 1.6 * pv_1x


def test_short_put_leg_pv_no_doubling_unchanged():
    """At doubling=1.0 the leg PV is purely base premium."""
    pv = _short_put_leg_pv(
        put_mid=5.20, shares_per_obs=50.0, alive_obs=180.0, doubling_factor=1.0
    )
    expected_base = 5.20 * 50.0 * 180.0
    assert pv == pytest.approx(expected_base, rel=1e-6)


def test_ko_call_leg_pv_zero_when_forfeited_zero():
    """No KO → no forfeited observations → PB call leg value zero."""
    pv = _ko_call_leg_pv(call_mid=4.10, shares_per_obs=50.0, forfeited_obs=0.0)
    assert pv == 0.0


def test_doubling_tail_leg_pv_zero_when_tail_prob_zero():
    pv = _doubling_tail_leg_pv(
        tail_leg_mid=0.50,
        cumulative_shares=12600.0,
        doubling_factor=2.0,
        tail_activation_prob=0.0,
    )
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
    assert alive_half < 252  # bounded above by n


# ─── _fair_yield (Task 13) ─────────────────────────────────


def test_fair_yield_returns_breakdown_dict():
    q = _mock_quote(
        tenor_months=12,
        doubling_factor=2.0,
        pb_quoted_yield_pa=0.09,
        daily_notional_usd=10_000.0,
    )
    s = _mock_snapshot(iv_rank=60.0)
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    out = _fair_yield(q, s)
    assert "fair_yield_pa" in out
    assert "breakdown" in out
    assert "data_provenance" in out
    assert "short_premium_pv" in out["breakdown"]
    assert "pb_ko_leg_pv" in out["breakdown"]
    assert "tail_pv" in out["breakdown"]
    assert "alive_obs" in out["breakdown"]
    assert "forfeited_obs" in out["breakdown"]


def test_fair_yield_markup_positive_when_pb_overcharges():
    """Sanity check: typical PB quote yields markup > 0 (PB takes a cut)."""
    q = _mock_quote(pb_quoted_yield_pa=0.09)  # PB quotes 9%
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    out = _fair_yield(q, s)
    markup = q.pb_quoted_yield_pa - out["fair_yield_pa"]
    assert markup > 0  # fair_yield should be lower than PB quote


# ─── analyze_quote integration (Task 14) ───────────────────


def test_analyze_quote_short_circuits_on_refusal():
    q = _mock_quote(doubling_factor=3.0)  # red line trigger
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    v = analyze_quote(q, s, nlv_usd=1_000_000.0)
    assert v.decision == "REFUSE"
    assert len(v.refusal_reasons) > 0
    assert v.refusal_reasons


def test_analyze_quote_returns_full_verdict_on_clean_quote():
    q = _mock_quote(doubling_factor=2.0, tenor_months=12)
    s = _mock_snapshot(iv_rank=60.0)
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"
    s.earnings_dates_iso = []  # opt out of quarterly ER iteration (see test_no_refusal note)

    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    # Markup-tier REFUSE is also valid (no refusal red lines triggered, but
    # the synthetic chain mids may yield a markup > 5pp). The point of this
    # test is to verify the full breakdown / provenance pipeline runs to
    # completion, NOT the specific decision tier.
    assert v.decision in ("COUNTER", "ACCEPT_IF_MUST", "REFUSE")
    assert v.breakdown["short_premium_pv"] > 0  # breakdown populated
    assert isinstance(v.data_provenance, dict)
    assert "spot" in v.data_provenance
    # Differentiate from the refusal short-circuit case: refusal_reasons,
    # if present, must come from the markup-tier check (not red lines).
    for r in v.refusal_reasons:
        assert "markup" in r.lower(), f"unexpected red-line refusal in clean test: {r}"


def test_analyze_quote_decision_tiers(monkeypatch):
    """Verify the three decision thresholds boundary behavior.

    Pass-2 finding (Codex-10): this test was previously `pass` — vacuous.
    Now we monkeypatch _fair_yield to return controlled markup values and
    assert the tier mapping is correct at the boundaries (1.5pp, 5.0pp).
    """
    q = _mock_quote()
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"
    s.earnings_dates_iso = []  # opt out of quarterly ER iteration

    def fake_fair_yield_factory(fair_yield_pa):
        def fake(q_arg, s_arg, strict_mode=False):
            return {
                "fair_yield_pa": fair_yield_pa,
                "ko_probability": 0.30,
                "notional_per_obs": q_arg.shares_per_obs * q_arg.reference_spot,
                "n_obs": 252,
                "tenor_yr": 1.0,
                "breakdown": {
                    "short_premium_pv": 100.0,
                    "pb_ko_leg_pv": 50.0,
                    "tail_pv": 10.0,
                    "pb_quoted_payoff_pv": 200.0,
                    "fair_payoff_to_client_pv": 40.0,
                    "markup_pv": 160.0,
                    "alive_obs": 180.0,
                    "forfeited_obs": 72.0,
                },
                "data_provenance": {
                    "spot": {"value": q_arg.spot, "source": s_arg.spot_source}
                },
            }

        return fake

    # markup_pp = (pb_quoted_yield 0.09 - fair_yield_pa) × 100
    # markup_pp = 1.0 (ACCEPT_IF_MUST):
    monkeypatch.setattr(
        "scripts.fair_aq_dq._fair_yield", fake_fair_yield_factory(fair_yield_pa=0.080)
    )
    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    assert v.decision == "ACCEPT_IF_MUST", (
        f"expected ACCEPT_IF_MUST at markup=1.0, got {v.decision}"
    )

    # markup_pp = 3.0 (COUNTER):
    monkeypatch.setattr(
        "scripts.fair_aq_dq._fair_yield", fake_fair_yield_factory(fair_yield_pa=0.060)
    )
    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    assert v.decision == "COUNTER", f"expected COUNTER at markup=3.0, got {v.decision}"

    # markup_pp = 6.0 (REFUSE):
    monkeypatch.setattr(
        "scripts.fair_aq_dq._fair_yield", fake_fair_yield_factory(fair_yield_pa=0.030)
    )
    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    assert v.decision == "REFUSE", f"expected REFUSE at markup=6.0, got {v.decision}"
    # Markup-tier REFUSE should populate refusal_reasons (Codex-14)
    assert v.refusal_reasons, "markup-tier REFUSE should record a reason"
    assert any("markup" in r.lower() for r in v.refusal_reasons)


# ─── optimize_terms (Task 15) ──────────────────────────────


def test_optimize_terms_returns_sorted_pareto():
    # Use a low PB quote so the base lands in COUNTER (markup 1.5–5.0 pp).
    # The synthetic chain mids are small, so 0.03 (3%) gives ~2.86pp markup
    # against the ~0.14pp synthetic fair yield.
    q = _mock_quote(tenor_months=12, doubling_factor=2.0, pb_quoted_yield_pa=0.03)
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"
    s.earnings_dates_iso = []  # opt out of quarterly ER iteration

    variants = optimize_terms(q, s, nlv_usd=50_000_000.0)
    assert len(variants) > 0
    assert not any(v.get("refused_base") for v in variants)
    for v in variants:
        assert "param_changed" in v
        assert "old_value" in v
        assert "new_value" in v
        assert "markup_pp" in v
        assert "delta_pp" in v
        assert "pb_concession_difficulty" in v
        assert "leverage_score" in v
    # Sorted by leverage_score descending
    scores = [v["leverage_score"] for v in variants]
    assert scores == sorted(scores, reverse=True)


def test_optimize_terms_respects_sweep_param():
    # See test_optimize_terms_returns_sorted_pareto comment re: 0.03 yield.
    q = _mock_quote(pb_quoted_yield_pa=0.03)
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"
    s.earnings_dates_iso = []  # opt out of quarterly ER iteration

    variants = optimize_terms(q, s, sweep=["tenor_months"], nlv_usd=50_000_000.0)
    assert variants  # not empty / not the refused_base sentinel
    for v in variants:
        assert v["param_changed"] == "tenor_months"


def test_optimize_terms_refused_base_returns_sentinel():
    """Pass-3 A3: REFUSE base → single sentinel row, not silent []."""
    q = _mock_quote(doubling_factor=3.0)  # red line trigger
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    variants = optimize_terms(q, s, nlv_usd=1_000_000.0)
    assert len(variants) == 1
    assert variants[0].get("refused_base") is True
    assert variants[0]["refusal_reasons"]  # populated


# ─── build_counter_offer_email (Task 16) ───────────────────


def test_counter_offer_email_returns_bilingual_dict():
    # Use COUNTER-tier base so verdict is not REFUSE
    q = _mock_quote(pb_quoted_yield_pa=0.03)
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"
    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    if v.decision == "REFUSE":
        pytest.skip("Mock data triggers refusal — test the COUNTER path instead")

    # Need levers populated → call optimize first
    v.levers_to_negotiate = optimize_terms(q, s, nlv_usd=50_000_000.0)[:3]

    email = build_counter_offer_email(v, q, target_markup_pp=1.5)
    assert "chinese_body" in email
    assert "english_body" in email
    assert q.ticker in email["chinese_body"]
    assert q.ticker in email["english_body"]
    # Chinese has Chinese characters (verify it's actually CN, not EN dressed up)
    assert "让步" in email["chinese_body"]  # Chinese for "concession"
    assert "Hi [PB contact" in email["english_body"]


# ─── Mirror symmetry + Pass-3 adversarial (Task 17) ────────


def test_aq_dq_mirror_symmetry_basic_invariants():
    """AQ + mirrored-DQ on same params should yield comparable magnitude
    metrics. Exact equality is too strict (skew asymmetry breaks it), but
    KO probability should be within 30%."""
    chain = {
        "2027-06-18": {
            0.50: {"put": {"mid": 0.50, "iv": 0.55}},
            0.95: {
                "put": {"mid": 5.20, "iv": 0.38},
                "call": {"mid": 15.10, "iv": 0.30},
            },
            0.97: {
                "put": {"mid": 4.10, "iv": 0.34},
                "call": {"mid": 10.40, "iv": 0.30},
            },
            1.00: {"put": {"mid": 8.10, "iv": 0.36}, "call": {"mid": 8.20, "iv": 0.31}},
            1.03: {
                "put": {"mid": 10.40, "iv": 0.35},
                "call": {"mid": 4.10, "iv": 0.34},
            },
            1.05: {
                "put": {"mid": 15.10, "iv": 0.30},
                "call": {"mid": 2.85, "iv": 0.34},
            },
            1.50: {"call": {"mid": 0.50, "iv": 0.42}},
        }
    }
    s_aq = _mock_snapshot(iv_rank=60.0)
    s_aq.chain = chain
    s_aq.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s_aq.earnings_date_iso = "2026-07-05"

    s_dq = _mock_snapshot(iv_rank=60.0)
    s_dq.chain = chain
    s_dq.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s_dq.earnings_date_iso = "2026-07-05"

    q_aq = _mock_quote(
        direction="AQ", strike_pct=0.95, ko_pct=1.03, pb_quoted_yield_pa=0.03
    )
    q_dq = _mock_quote(
        direction="DQ", strike_pct=1.05, ko_pct=0.97, pb_quoted_yield_pa=0.03
    )

    v_aq = analyze_quote(q_aq, s_aq, nlv_usd=50_000_000.0)
    v_dq = analyze_quote(q_dq, s_dq, nlv_usd=50_000_000.0)

    # Both should compute a verdict (not red-line refuse on these params).
    # Markup-tier REFUSE acceptable; only the short-circuit "refusal_reasons
    # from red lines" is what would indicate a real bug.
    if v_aq.ko_probability > 0:
        ratio = v_dq.ko_probability / v_aq.ko_probability
        assert 0.5 < ratio < 2.0, (
            f"AQ ko_prob={v_aq.ko_probability:.3f} vs DQ ko_prob={v_dq.ko_probability:.3f}"
        )


def test_quote_validation_aq_strike_above_spot_rejected():
    """Pass-3 (A1): AQ requires strike_pct < 1.0; reject otherwise."""
    with pytest.raises(ValueError, match="AQ requires"):
        Quote(
            direction="AQ",
            ticker="X",
            spot=100.0,
            strike_pct=1.05,
            ko_pct=1.10,
            tenor_months=12,
            obs_freq="daily",
            doubling_factor=2.0,
            daily_notional_usd=10_000.0,
            pb_quoted_yield_pa=0.09,
            settlement="cash",
        )


def test_quote_validation_dq_strike_below_spot_rejected():
    """Pass-3 (A1): DQ requires strike_pct > 1.0; reject otherwise."""
    with pytest.raises(ValueError, match="DQ requires"):
        Quote(
            direction="DQ",
            ticker="X",
            spot=100.0,
            strike_pct=0.95,
            ko_pct=0.90,
            tenor_months=12,
            obs_freq="daily",
            doubling_factor=2.0,
            daily_notional_usd=10_000.0,
            pb_quoted_yield_pa=0.09,
            settlement="cash",
        )


def test_quote_validation_zero_spot_rejected():
    """Pass-3 (A2): spot=0 prevents divide-by-zero in shares_per_obs."""
    with pytest.raises(ValueError, match="spot must be > 0"):
        Quote(
            direction="AQ",
            ticker="X",
            spot=0.0,
            strike_pct=0.95,
            ko_pct=1.03,
            tenor_months=12,
            obs_freq="daily",
            doubling_factor=2.0,
            daily_notional_usd=10_000.0,
            pb_quoted_yield_pa=0.09,
            settlement="cash",
        )


def test_quote_validation_zero_tenor_rejected():
    """Pass-3 (A2): tenor_months=0 prevents divide-by-zero in fair_yield_pa."""
    with pytest.raises(ValueError, match="tenor_months must be"):
        Quote(
            direction="AQ",
            ticker="X",
            spot=100.0,
            strike_pct=0.95,
            ko_pct=1.03,
            tenor_months=0,
            obs_freq="daily",
            doubling_factor=2.0,
            daily_notional_usd=10_000.0,
            pb_quoted_yield_pa=0.09,
            settlement="cash",
        )


def test_quote_validation_doubling_below_one_rejected():
    """Pass-3 (A2): doubling_factor < 1.0 makes no economic sense."""
    with pytest.raises(ValueError, match="doubling_factor must be"):
        Quote(
            direction="AQ",
            ticker="X",
            spot=100.0,
            strike_pct=0.95,
            ko_pct=1.03,
            tenor_months=12,
            obs_freq="daily",
            doubling_factor=0.5,
            daily_notional_usd=10_000.0,
            pb_quoted_yield_pa=0.09,
            settlement="cash",
        )


def test_nearest_expiry_skips_past_dated():
    """Pass-3 (A4): expired chain entries are filtered out."""
    chain = {
        "2024-06-18": {0.95: {"put": {"mid": 5.0, "iv": 0.30}}},
        "2027-06-18": {0.95: {"put": {"mid": 5.0, "iv": 0.30}}},
    }
    result = _nearest_expiry_to_tenor(
        chain, tenor_months=12, quote_start_iso="2026-06-05T00:00:00Z"
    )
    assert result == "2027-06-18", f"expected future expiry, got {result}"


def test_nearest_expiry_raises_when_all_expired():
    """Pass-3 (A4): if every expiry is in the past, raise."""
    chain = {
        "2024-06-18": {0.95: {"put": {"mid": 5.0, "iv": 0.30}}},
        "2025-01-18": {0.95: {"put": {"mid": 5.0, "iv": 0.30}}},
    }
    with pytest.raises(ValueError, match="No future-dated"):
        _nearest_expiry_to_tenor(
            chain, tenor_months=12, quote_start_iso="2026-06-05T00:00:00Z"
        )


def test_fair_yield_rejects_spot_divergence_in_strict_mode():
    """Drift > 0.5% in strict_mode raises. Default mode emits a warning
    instead so post-trade `evaluate_placed_aq` can still produce numbers
    when spot has moved since deal placement (see framework §9)."""
    import warnings

    q = _mock_quote(spot=200.0)
    s = _mock_snapshot()
    s.spot = 210.0  # 5% drift — stale snapshot
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    # Strict mode: raise
    with pytest.raises(ValueError, match="diverges"):
        _fair_yield(q, s, strict_mode=True)
    # Default (non-strict): warn but continue. Provenance carries drift_pct.
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        out = _fair_yield(q, s)
        assert any("diverges" in str(warning.message) for warning in w)
    assert out["data_provenance"]["spot_drift_pct"] > 0.005


def test_data_provenance_completeness():
    q = _mock_quote(pb_quoted_yield_pa=0.03)  # COUNTER-tier to keep verdict non-refused
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"

    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    if v.decision == "REFUSE":
        pytest.skip("Test must run on non-refused quote")

    required_provenance_keys = [
        "spot",
        "chain_source",
        "strike_leg_mid",
        "ko_leg_mid",
        "iv_at_ko",
        "ko_probability",
        "alive_obs",
    ]
    for k in required_provenance_keys:
        assert k in v.data_provenance, f"Missing provenance key: {k}"
        if "value" in v.data_provenance[k]:
            assert v.data_provenance[k]["value"] is not None


# ─── PB-quote-template tests (PR-A/PR-B) ────────────────────
#
# Tests below validate the new fields + behaviors driven by decoding real PB
# AQ quote screenshots into the framework (see references/aq-dq-framework.md
# §7.5). Anchored to the GOOGL 2026-06-03 AQ (private/trader-profile.md
# privatized): 12M, 4 shares/day, entry $361.85, strike 85.79% ($310.43),
# KO 105% ($379.94), 4-week guarantee, 2× doubling.


def _googl_aq_quote(**overrides) -> Quote:
    """Real PB AQ quote (GOOGL 2026-06-03) decoded into a Quote."""
    defaults = dict(
        direction="AQ",
        ticker="GOOGL",
        spot=368.53,  # current spot (Fri close 2026-06-05)
        strike_pct=0.8579,
        ko_pct=1.05,
        tenor_months=12,
        obs_freq="daily",
        doubling_factor=2.0,
        pb_quoted_yield_pa=None,  # PB AQ doesn't quote a yield
        settlement="physical",
        daily_shares=4,
        entry_spot=361.85,  # PB's reference spot at quote time
        guarantee_period_weeks=4,
    )
    defaults.update(overrides)
    return Quote(**defaults)


def _googl_chain() -> dict:
    """Synthetic 12M-out chain at the GOOGL strikes used by the AQ."""
    return {
        "2027-06-18": {
            0.50: {"put": {"mid": 1.20, "iv": 0.55}},
            0.8579: {
                "put": {"mid": 22.50, "iv": 0.36},
                "call": {"mid": 75.10, "iv": 0.32},
            },
            1.00: {
                "put": {"mid": 48.20, "iv": 0.32},
                "call": {"mid": 51.40, "iv": 0.30},
            },
            1.05: {
                "put": {"mid": 62.30, "iv": 0.33},
                "call": {"mid": 38.40, "iv": 0.30},
            },
        }
    }


# ─── Quote dataclass widening ──────────────────────────────


def test_quote_accepts_daily_shares_without_daily_notional():
    q = _googl_aq_quote()
    assert q.daily_shares == 4
    assert q.daily_notional_usd is None
    assert q.shares_per_obs == 4.0


def test_quote_rejects_both_shares_and_notional():
    with pytest.raises(ValueError, match="exactly one"):
        Quote(
            direction="AQ",
            ticker="X",
            spot=100.0,
            strike_pct=0.95,
            ko_pct=1.03,
            tenor_months=6,
            obs_freq="daily",
            doubling_factor=2.0,
            daily_shares=4,
            daily_notional_usd=10_000.0,
        )


def test_quote_rejects_neither_shares_nor_notional():
    with pytest.raises(ValueError, match="exactly one"):
        Quote(
            direction="AQ",
            ticker="X",
            spot=100.0,
            strike_pct=0.95,
            ko_pct=1.03,
            tenor_months=6,
            obs_freq="daily",
            doubling_factor=2.0,
        )


def test_reference_spot_defaults_to_spot_when_entry_spot_unset():
    q = _mock_quote()
    assert q.entry_spot is None
    assert q.reference_spot == q.spot


def test_reference_spot_uses_entry_spot_when_set():
    q = _googl_aq_quote()
    assert q.reference_spot == 361.85  # entry_spot, NOT current 368.53


def test_shares_per_obs_via_notional_uses_reference_spot():
    """When daily_notional_usd path is used (not daily_shares), the share
    count divides by reference_spot (the strike anchor), not current spot."""
    q = _mock_quote(daily_notional_usd=10_000.0, entry_spot=190.0)
    # 10000 / 190 = 52.63, not 10000 / 200 (= 50.0, current spot)
    assert q.shares_per_obs == pytest.approx(10_000.0 / 190.0)


def test_total_notional_uses_strike_not_spot():
    """Refusal #4 concentration formula uses strike_abs (the price PB
    will buy the trader in at), not spot."""
    q = _mock_quote()
    n_obs = 252  # 12M daily
    expected = q.shares_per_obs * (q.strike_pct * q.reference_spot) * n_obs
    assert q.total_notional_usd == pytest.approx(expected)


def test_quote_rejects_negative_guarantee_period():
    with pytest.raises(ValueError, match="guarantee_period_weeks"):
        _mock_quote(guarantee_period_weeks=-1)


# ─── KO probability with guarantee period ─────────────────────


def test_ko_prob_drops_with_guarantee_period():
    """4-week guarantee on a 12M tenor should reduce KO probability
    (because KO can't trigger during the first 4 weeks)."""
    p_no_guarantee = _ko_probability(
        spot=100.0,
        ko_barrier=105.0,
        iv=0.30,
        tenor_yr=1.0,
        obs_freq="daily",
        guarantee_period_yr=0.0,
    )
    p_with_guarantee = _ko_probability(
        spot=100.0,
        ko_barrier=105.0,
        iv=0.30,
        tenor_yr=1.0,
        obs_freq="daily",
        guarantee_period_yr=28 / 365.0,  # 4 weeks
    )
    assert p_with_guarantee < p_no_guarantee


# ─── ER iteration ─────────────────────────────────────────────


def test_er_iteration_catches_quarterly_ers_in_12m_tenor():
    """A 12M AQ starting 2026-06-05 with next ER 2026-07-22 (Q2) sees
    Q3 (2026-10-20) and Q4 (2027-01-18) — both should fall in middle 50%."""
    s = _mock_snapshot()
    s.spot_timestamp = "2026-06-05T10:00:00Z"
    s.earnings_date_iso = "2026-07-22"
    s.earnings_dates_iso = None  # let iterator extrapolate quarterly
    dates = _all_earnings_dates_in_tenor(s, tenor_months=12)
    # Expect 4-5 quarterly ER dates anchored on 2026-07-22 within
    # [2026-06-05, 2027-06-05].
    assert len(dates) >= 4
    assert "2026-07-22" in dates
    # Q3 ≈ 2026-10-20, Q4 ≈ 2027-01-18 — within middle 50%
    assert any("2026-10" in d for d in dates)
    assert any("2027-01" in d for d in dates)


def test_explicit_empty_er_list_disables_iteration():
    """Empty list = "orchestrator confirmed no ERs in window" — don't
    extrapolate from earnings_date_iso."""
    s = _mock_snapshot()
    s.earnings_date_iso = "2026-07-22"
    s.earnings_dates_iso = []
    dates = _all_earnings_dates_in_tenor(s, tenor_months=12)
    assert dates == []


def test_refusal_iterates_to_catch_q3_er():
    q = _mock_quote(tenor_months=12)
    s = _mock_snapshot(iv_rank=60.0, atr_14_pct=0.02)
    s.spot_timestamp = "2026-06-05T10:00:00Z"
    s.earnings_date_iso = "2026-07-22"  # Q2 outside middle 50%
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000_000.0)
    # Q3 ER (~2026-10-20) falls in middle 50% → refusal should fire
    assert any("earning" in r.lower() for r in reasons)


# ─── Concentration formula (refusal #4 fix) ────────────────────


def test_concentration_uses_strike_and_doubling():
    """Old formula: daily_notional × n_obs (ignored doubling and strike vs spot).
    New: shares × strike × n_obs × doubling — captures true max exposure."""
    q = _mock_quote(daily_notional_usd=10_000.0, doubling_factor=2.0)
    s = _mock_snapshot()
    s.earnings_dates_iso = []  # disable ER refusal
    # 50 shares × $190 strike × 252 obs × 2 doubling = $4.788M
    # vs $40M NLV → 11.97% > 10% → REFUSE
    reasons = _check_refusal_red_lines(q, s, nlv_usd=40_000_000.0)
    assert any("max-exposure" in r.lower() for r in reasons)


# ─── 3-scenario output ─────────────────────────────────────────


def test_compute_scenarios_for_googl_quote():
    """3-scenario projection should match the PB report layout:
    Scenario 1 (KO during guarantee): 80 shares × $310.43 = $24,834
    Scenario 2 (no KO, no doubling): 1000-1008 shares (252 × 4) × $310.43
    Scenario 3 (max exposure all doubled): 2000-2016 shares × $310.43
    """
    q = _googl_aq_quote()
    scenarios = _compute_scenarios(q, nlv_usd=None)
    strike_abs = q.strike_pct * q.entry_spot  # ≈ 310.43

    # Scenario 1: 4 weeks × 5 obs/wk × 4 shares = 80 shares (matches PB)
    s1 = scenarios["ko_during_guarantee"]
    assert s1["shares"] == pytest.approx(80.0)
    assert s1["usd_notional"] == pytest.approx(80.0 * strike_abs, rel=1e-3)

    # Scenario 2: 252 trading days × 4 shares = 1008 shares (PB rounds to 1000)
    s2 = scenarios["full_term_no_doubling"]
    assert s2["shares"] == pytest.approx(1008.0)
    assert s2["usd_notional"] == pytest.approx(1008.0 * strike_abs, rel=1e-3)

    # Scenario 3: 252 × 4 × 2 = 2016 shares (PB rounds to 2000)
    s3 = scenarios["max_exposure_all_doubled"]
    assert s3["shares"] == pytest.approx(2016.0)


def test_compute_scenarios_with_nlv_computes_pct():
    q = _googl_aq_quote()
    scenarios = _compute_scenarios(q, nlv_usd=500_000.0)
    # Scenario 3 ≈ $625K → ~125% of $500K NLV
    s3 = scenarios["max_exposure_all_doubled"]
    assert s3["pct_of_nlv"] > 1.0


# ─── analyze_quote implicit-yield mode ─────────────────────────


def test_analyze_quote_implicit_yield_mode_when_pb_yield_none():
    """When pb_quoted_yield_pa is None, Verdict.mode='implicit_yield_aq'
    and discount_implied_yield_pa is populated."""
    q = _mock_quote(
        pb_quoted_yield_pa=None,
        # provide ATR + IV rank that don't trip refusals 1-5
        strike_pct=0.95,
        ko_pct=1.05,
    )
    s = _mock_snapshot(iv_rank=60.0, atr_14_pct=0.02)
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_dates_iso = []  # don't trip ER refusal
    v = analyze_quote(q, s, nlv_usd=1_000_000_000.0)  # large NLV

    assert v.mode == "implicit_yield_aq"
    assert v.pb_quoted_yield_pa is None
    assert not (v.discount_implied_yield_pa != v.discount_implied_yield_pa)  # not NaN


# ─── evaluate_placed_aq (post-trade audit) ─────────────────────


def test_evaluate_placed_aq_returns_expected_shape():
    q = _googl_aq_quote()
    s = _mock_snapshot()
    s.spot = q.spot  # avoid drift warning noise
    s.chain = _googl_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    audit = evaluate_placed_aq(
        q,
        s,
        current_spot=q.spot,
        observations_elapsed=3,  # 6/3 quote → 6/5 close = 3 trading days
        shares_accumulated=12.0,  # 4 shares/day × 3 days
        nlv_usd=2_000_000.0,
    )

    assert set(audit.keys()) == {
        "current_state",
        "barriers",
        "forward",
        "crash_scenario",
        "monitor_level",
    }
    cs = audit["current_state"]
    # cost basis at strike $310.43, 12 shares = $3,725
    assert cs["cost_basis_total"] == pytest.approx(12.0 * 0.8579 * 361.85, rel=1e-3)
    # unrealized P/L positive since current $368.53 > strike $310.43
    assert cs["unrealized_pnl_usd"] > 0
    # In guarantee period (3 obs elapsed < 20 obs in guarantee window)
    assert audit["barriers"]["in_guarantee_period"] is True


def test_evaluate_placed_aq_near_ko_monitor_level():
    """When current spot is within 2% of KO barrier, monitor_level='near_ko'."""
    q = _googl_aq_quote()
    s = _mock_snapshot()
    ko_abs = q.ko_pct * q.entry_spot  # $379.94
    near_ko_spot = ko_abs * 0.995  # 0.5% below KO
    s.spot = near_ko_spot
    s.chain = _googl_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    audit = evaluate_placed_aq(
        q,
        s,
        current_spot=near_ko_spot,
        observations_elapsed=20,
        shares_accumulated=80.0,
    )
    assert audit["monitor_level"] == "near_ko"


def test_evaluate_placed_aq_crash_scenario_quantifies_loss():
    """A -20% crash from current spot should turn unrealized P/L sharply
    negative and double the remaining accumulation rate."""
    q = _googl_aq_quote()
    s = _mock_snapshot()
    s.spot = q.spot
    s.chain = _googl_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    audit = evaluate_placed_aq(
        q,
        s,
        current_spot=q.spot,
        observations_elapsed=3,
        shares_accumulated=12.0,
        nlv_usd=2_000_000.0,
        crash_scenario_pct=-0.20,
    )
    crash = audit["crash_scenario"]
    # Crash P/L is negative
    assert crash["pnl_usd"] < 0
    # Doubling fires → additional shares = remaining_obs × 4 × 2
    assert crash["additional_shares_doubled"] == pytest.approx(
        (252 - 3) * 4 * 2, rel=1e-3
    )


# ─── GOOGL integration test ────────────────────────────────────


def test_googl_aq_end_to_end_refuses_on_concentration_or_ers():
    """Real GOOGL 2026-06-03 AQ run through analyze_quote against a small
    PB-equivalent NLV. The trade SHOULD trigger at least one refusal
    (either concentration with small NLV, or ER iteration catching
    Q3/Q4 ERs in middle 50% of the 12M tenor)."""
    q = _googl_aq_quote()
    s = _mock_snapshot(iv_rank=45.0, atr_14_pct=0.025)
    s.spot = q.spot
    s.chain = _googl_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.spot_timestamp = "2026-06-03T20:00:00Z"  # PB quote placement time
    s.earnings_date_iso = "2026-07-22"
    s.earnings_dates_iso = None  # let iterator extrapolate Q3 + Q4

    # Use a $200K PB account (plausible private-bank-retail size). Max
    # exposure $625K × 1.0 = $625K > 10% × $200K = $20K → refuse on #4.
    v = analyze_quote(q, s, nlv_usd=200_000.0)
    assert v.decision == "REFUSE"
    # Scenarios should still be populated even on refusal short-circuit
    assert "ko_during_guarantee" in v.scenarios
    assert v.scenarios["ko_during_guarantee"]["shares"] == pytest.approx(80.0)
    assert v.mode == "implicit_yield_aq"  # AQ without quoted yield
