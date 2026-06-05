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
    _check_refusal_red_lines,
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
