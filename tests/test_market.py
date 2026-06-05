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


# ─── Pass-3 adversarial: 0.0 mid handling (A2) ─────────────


def test_read_chain_mid_treats_zero_as_no_quote():
    """UW chains return mid=0.0 for illiquid / no-bid strikes. If accepted
    as a real price, hedge legs would be priced at $0 and silently pass
    cost-cap checks. Return None so caller falls back to BSM."""
    chain = {
        "2027-06-18": {
            0.50: {"put": {"mid": 0.0, "iv": 0.55}},   # no bid
            0.95: {"put": {"mid": 5.20, "iv": 0.38}},  # liquid
        }
    }
    assert read_chain_mid(chain, "2027-06-18", 0.50, "put") is None
    assert read_chain_mid(chain, "2027-06-18", 0.95, "put") == 5.20


def test_read_chain_mid_treats_negative_as_no_quote():
    """Defensive: negative mid is data corruption; treat as no quote."""
    chain = {"2027-06-18": {0.95: {"put": {"mid": -1.0, "iv": 0.38}}}}
    assert read_chain_mid(chain, "2027-06-18", 0.95, "put") is None


# ─── Pass-5 live verification: UW row normalization ────────


# These rows are a verbatim subset of a live UW get_options_chain response
# for SPY pulled 2026-06-05 during the chain-mid sweep review-cycle.
# Lock in the real-source shape so future UW API changes break the test
# explicitly rather than silently rejecting rows in production.
LIVE_UW_SPY_ROWS = [
    {
        "option_symbol": "SPY260604C00757000",
        "implied_volatility": "0.0943661796566746",
        "nbbo_ask": "0.03",
        "nbbo_bid": "0.02",
        "last_price": "0.02",
        "open_interest": 11890,
    },
    {
        "option_symbol": "SPY260604P00755000",
        "implied_volatility": "0.2036794717660341",
        "nbbo_ask": "0.02",
        "nbbo_bid": "0.01",
        "last_price": "0.01",
        "open_interest": 6767,
    },
    {
        "option_symbol": "SPY260604P00758000",
        "implied_volatility": "0.3289664353277521",
        "nbbo_ask": "1.58",
        "nbbo_bid": "1.29",
        "last_price": "1.42",
        "open_interest": 3029,
    },
]


def test_parse_occ_symbol_live_uw_shape():
    from scripts._market import _parse_occ_symbol

    ticker, expiry, right, strike = _parse_occ_symbol("SPY260604C00757000")
    assert ticker == "SPY"
    assert expiry == "2026-06-04"
    assert right == "call"
    assert strike == 757.0


def test_parse_occ_symbol_put_strike_with_decimals():
    """Some strikes are non-integer (e.g., $1.50). OCC encodes as 00001500."""
    from scripts._market import _parse_occ_symbol

    ticker, expiry, right, strike = _parse_occ_symbol("AAPL260117P00185500")
    assert ticker == "AAPL"
    assert expiry == "2026-01-17"
    assert right == "put"
    assert strike == 185.5


def test_normalize_uw_chain_rows_produces_consumer_shape():
    """Live UW rows → normalized chain shape that fair_coupon / macro_hedge
    can consume. Verified end-to-end: the same shape my mock chains use."""
    from scripts._market import normalize_uw_chain_rows

    spot = 757.0  # spot ≈ ATM strike from the live pull
    chain = normalize_uw_chain_rows(LIVE_UW_SPY_ROWS, spot=spot)

    # Shape: chain[expiry][strike_pct][right] = {'mid': ..., 'iv': ...}
    assert "2026-06-04" in chain
    by_strike = chain["2026-06-04"]

    # 757 / 757 = 1.0 — ATM call
    assert 1.0 in by_strike
    assert by_strike[1.0]["call"]["mid"] == 0.025  # (0.02 + 0.03) / 2
    assert abs(by_strike[1.0]["call"]["iv"] - 0.0943661796566746) < 1e-12

    # 755 / 757 ≈ 0.9974 (rounded to 4 decimals) — OTM put
    assert 0.9974 in by_strike
    assert by_strike[0.9974]["put"]["mid"] == 0.015  # (0.01 + 0.02) / 2

    # 758 / 757 ≈ 1.0013 — OTM put
    assert 1.0013 in by_strike
    assert by_strike[1.0013]["put"]["mid"] == 1.435  # (1.29 + 1.58) / 2


def test_normalize_uw_chain_rows_then_read_round_trip():
    """End-to-end: live UW rows → normalized → read_chain_mid back out.
    Proves the chain shape from normalization is consumable by the
    chain-mid scripts without further massaging."""
    from scripts._market import normalize_uw_chain_rows, read_chain_mid

    chain = normalize_uw_chain_rows(LIVE_UW_SPY_ROWS, spot=757.0)
    mid = read_chain_mid(chain, "2026-06-04", 1.0, "call")
    assert mid == 0.025

    # Missing strike returns None (cleanly falls back to BSM in callers)
    assert read_chain_mid(chain, "2026-06-04", 0.50, "put") is None


def test_normalize_uw_chain_rows_skips_unquoted_rows():
    """Halted / unquoted strikes have non-numeric bid/ask. Skip them
    silently so the chain has only real quotes."""
    from scripts._market import normalize_uw_chain_rows

    rows = LIVE_UW_SPY_ROWS + [
        {
            "option_symbol": "SPY260604C00800000",
            "implied_volatility": "0.50",
            "nbbo_bid": None,
            "nbbo_ask": None,
            "last_price": "0.0",
        },
        {
            "option_symbol": "MALFORMED",
            "implied_volatility": "0.50",
            "nbbo_bid": "0.10",
            "nbbo_ask": "0.20",
        },
    ]
    chain = normalize_uw_chain_rows(rows, spot=757.0)
    # The 3 live rows are present
    assert "2026-06-04" in chain
    assert len(chain["2026-06-04"]) == 3
