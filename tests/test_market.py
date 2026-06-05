"""Tests for the shared market primitives in scripts/_market.py.

Most behavior is exercised indirectly via test_fair_aq_dq.py (the AQ/DQ
script uses these helpers heavily). This file adds direct coverage for
the provenance builders and re-asserts the chain-lookup contract so
future callers (fair_coupon, macro_hedge) don't accidentally diverge.
"""

from __future__ import annotations

import pytest
from scripts._market import (
    SOURCE_COMPUTED,
    SOURCE_FALLBACK,
    SOURCE_IB,
    SOURCE_UW,
    chain_leg_provenance,
    fallback_provenance,
    nearest_expiry_to_tenor,
    provenance_entry,
    read_chain_iv,
    read_chain_mid,
)


def _chain():
    return {
        "2027-06-18": {
            0.95: {
                "put": {"mid": 5.20, "iv": 0.38},
                "call": {"mid": 15.10, "iv": 0.30},
            },
            1.03: {
                "put": {"mid": 10.40, "iv": 0.35},
                "call": {"mid": 4.10, "iv": 0.34},
            },
        }
    }


# ─── Chain lookup ───────────────────────────────────────────


def test_read_chain_mid_hit():
    assert read_chain_mid(_chain(), "2027-06-18", 0.95, "put") == 5.20


def test_read_chain_mid_miss_returns_none_not_zero():
    """Missing strikes return None, NOT 0.0 — caller must distinguish
    'no quote' from 'priced at zero'."""
    assert read_chain_mid(_chain(), "2027-06-18", 0.70, "put") is None
    assert read_chain_mid(_chain(), "2030-01-01", 0.95, "put") is None


def test_read_chain_iv_hit():
    assert read_chain_iv(_chain(), "2027-06-18", 1.03, "call") == 0.34


def test_nearest_expiry_picks_closest_future():
    chain = {"2026-12-18": {}, "2027-06-18": {}, "2027-12-17": {}}
    # 12M forward from 2026-06-05 → ~2027-06-05 → 2027-06-18 is closest
    got = nearest_expiry_to_tenor(
        chain, tenor_months=12, quote_start_iso="2026-06-05T00:00:00Z"
    )
    assert got == "2027-06-18"


def test_nearest_expiry_skips_past_expiries():
    """Past-dated chain entries are filtered out (Pass-3 A4)."""
    chain = {
        "2024-06-18": {},  # past
        "2027-06-18": {},
    }
    got = nearest_expiry_to_tenor(
        chain, tenor_months=12, quote_start_iso="2026-06-05T00:00:00Z"
    )
    assert got == "2027-06-18"


def test_nearest_expiry_raises_when_all_expired():
    chain = {"2024-06-18": {}, "2025-01-18": {}}
    with pytest.raises(ValueError, match="No future-dated"):
        nearest_expiry_to_tenor(
            chain, tenor_months=12, quote_start_iso="2026-06-05T00:00:00Z"
        )


# ─── Provenance builders ────────────────────────────────────


def test_provenance_entry_minimal():
    entry = provenance_entry(value=5.20, source=SOURCE_UW)
    assert entry == {"value": 5.20, "source": "UW"}


def test_provenance_entry_full():
    entry = provenance_entry(
        value=0.42,
        source=SOURCE_COMPUTED,
        timestamp="2026-06-05T10:00:00Z",
        detail="BSM first-passage",
    )
    assert entry["timestamp"] == "2026-06-05T10:00:00Z"
    assert entry["detail"] == "BSM first-passage"


def test_chain_leg_provenance_encodes_full_path():
    entry = chain_leg_provenance(
        value=5.20,
        chain_source="UW",
        expiry="2027-06-18",
        strike_pct=0.95,
        right="put",
        field="mid",
        timestamp="2026-06-05T10:00:00Z",
    )
    assert entry["value"] == 5.20
    assert entry["source"] == "UW"
    assert "0.95" in entry["detail"]
    assert "put" in entry["detail"]
    assert "mid" in entry["detail"]
    assert entry["timestamp"] == "2026-06-05T10:00:00Z"


def test_fallback_provenance_tags_source_fallback():
    entry = fallback_provenance(
        value=4.55, reason="BSM fallback — chain missing 0.50 strike"
    )
    assert entry["source"] == SOURCE_FALLBACK
    assert "BSM fallback" in entry["detail"]
    assert entry["value"] == 4.55


def test_source_constants_exposed():
    """Callers should import SOURCE_* constants for consistency, not
    hard-code the strings."""
    assert SOURCE_UW == "UW"
    assert SOURCE_IB == "IB"
    assert SOURCE_FALLBACK == "fallback"
    assert SOURCE_COMPUTED == "computed"
