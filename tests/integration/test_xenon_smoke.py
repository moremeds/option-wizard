"""Live xenon Query-API smoke test. Requires XENON_KEY (+ XENON_BASE) env.
Pytest skips if XENON_KEY is missing. Asserts structure, not values.

    XENON_KEY=... XENON_BASE=http://100.66.147.98:8321 \\
      .venv/bin/pytest tests/integration/test_xenon_smoke.py -v -s
"""

import os

import pytest
from scripts._clients.xenon import XenonClient

pytestmark = pytest.mark.skipif(
    "XENON_KEY" not in os.environ,
    reason="XENON_KEY not set; skip live xenon smoke test",
)


@pytest.fixture(scope="module")
def client():
    return XenonClient()


def test_health(client):
    h = client.health()
    assert h.get("status") == "ok"
    print("health ib_gateway:", h.get("ib_gateway", {}).get("service_state"))


def test_ib_portfolio_shape(client):
    p = client.ib_portfolio()
    assert "account_summary" in p and "positions" in p
    assert "cash" in p["account_summary"]
    print(
        "portfolio positions:",
        p.get("position_count"),
        "last_sync:",
        p.get("last_sync"),
    )


def test_futu_portfolio_shape(client):
    f = client.futu_portfolio()
    assert "positions" in f and "account_summary" in f
    print("futu is_stale:", f.get("is_stale"), "count:", f.get("count"))


def test_blotter_shape(client):
    b = client.blotter()
    assert "closed_trades" in b and "open_trades" in b
    print("blotter source:", b.get("source"), "as_of:", b.get("as_of"))


def test_market_depth_empty_book_is_200(client):
    d = client.market_depth("AAPL", num_rows=5)
    assert "entitled" in d and "bids" in d and "asks" in d
    print("AAPL depth entitled:", d.get("entitled"), "note:", d.get("note"))


def test_option_greeks_live(client):
    # QQQ 600C 20260717 — deep ITM, greeks populate around the clock (frozen mode).
    g = client.option_greeks("QQQ", "20260717", 600, "C")
    assert g.get("secType") == "OPT"
    assert "greeks" in g  # may be a dict or None (note "no greeks returned")
    print("QQQ 600C greeks:", g.get("greeks"), "bid/ask:", g.get("bid"), g.get("ask"))
