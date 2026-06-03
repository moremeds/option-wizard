"""Live UW API smoke test. Requires UW_API_KEY env var. Pytest skips if missing.

This test calls each endpoint option-wizard depends on against a stable
ticker (ORCL) and asserts the response structure exists. It does NOT
assert specific values (they change daily). Run manually:

    UW_API_KEY=... .venv/bin/pytest tests/integration/test_uw_smoke.py -v
"""

import os

import pytest
from scripts._clients.uw import UWClient

pytestmark = pytest.mark.skipif(
    "UW_API_KEY" not in os.environ,
    reason="UW_API_KEY not set; skip live smoke test",
)

TICKER = "ORCL"


@pytest.fixture(scope="module")
def client():
    return UWClient()


def test_iv_rank(client):
    resp = client.iv_rank(TICKER)
    assert isinstance(resp, dict), "expected JSON object"
    print("iv_rank response shape:", list(resp.keys()))


def test_realized_volatility(client):
    resp = client.realized_volatility(TICKER)
    assert isinstance(resp, dict)
    print("realized_volatility response shape:", list(resp.keys()))


def test_skew(client):
    resp = client.historical_risk_reversal_skew(TICKER)
    assert isinstance(resp, dict)
    print("skew response shape:", list(resp.keys()))


def test_iv_term_structure(client):
    resp = client.iv_term_structure(TICKER)
    assert isinstance(resp, dict)
    print("iv_term_structure response shape:", list(resp.keys()))


def test_max_pain(client):
    resp = client.max_pain(TICKER)
    assert isinstance(resp, dict)
    print("max_pain response shape:", list(resp.keys()))


def test_spot_gex_by_strike(client):
    resp = client.spot_gex_by_strike(TICKER)
    assert isinstance(resp, dict)
    assert "data" in resp or len(resp) > 0
    print("spot_gex_by_strike response shape:", list(resp.keys()))


def test_interpolated_iv(client):
    resp = client.interpolated_iv(TICKER)
    assert isinstance(resp, dict)
    print("interpolated_iv response shape:", list(resp.keys()))


def test_greeks_by_strike(client):
    resp = client.greeks_by_strike(TICKER)
    assert isinstance(resp, dict)
    print("greeks_by_strike response shape:", list(resp.keys()))


def test_dark_pool(client):
    resp = client.dark_pool(TICKER)
    assert isinstance(resp, dict)
    print("dark_pool response shape:", list(resp.keys()))


def test_technical_indicator_sma(client):
    resp = client.technical_indicator(TICKER, "sma")
    assert isinstance(resp, dict)
    print("technical_indicator/sma response shape:", list(resp.keys()))
