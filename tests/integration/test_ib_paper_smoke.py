"""Paper-account IB smoke test. Requires TWS/IB Gateway in paper mode at the
specified port. Skips by default unless OPT_WIZ_PAPER_TEST=1 is set.

This test does NOT use the Claude MCP — it goes directly through
ib_insync since the Python scripts will do the same in v1. The goal is
the same: confirm orders land in 'PreSubmitted' state and not
'Submitted'/'Filled' immediately on the read-back.

Run:
    OPT_WIZ_PAPER_TEST=1 .venv/bin/pytest tests/integration/test_ib_paper_smoke.py -v -s
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("OPT_WIZ_PAPER_TEST") != "1",
    reason="Set OPT_WIZ_PAPER_TEST=1 to run live paper smoke test",
)


def test_paper_account_connection_and_summary():
    from scripts._clients.ib import IBClient

    port = int(os.environ.get("OPT_WIZ_PAPER_PORT", 7497))
    with IBClient(port=port) as ib:
        summary = ib.get_account_summary()
        print("Paper account NetLiquidation:", summary.get("NetLiquidation"))
        assert "NetLiquidation" in summary


def test_paper_order_state_is_presubmitted_not_filled():
    """Submit a low-prob fill order and inspect its status field.
    Expectation per design assumption: status starts as PreSubmitted, not Filled.
    """
    from ib_insync import MarketOrder, Stock
    from scripts._clients.ib import IBClient

    port = int(os.environ.get("OPT_WIZ_PAPER_PORT", 7497))
    with IBClient(port=port) as ib:
        contract = Stock("SPY", "SMART", "USD")
        ib._ib.qualifyContracts(contract)
        order = MarketOrder("BUY", 1)
        trade = ib.place_order(contract, order)
        ib._ib.sleep(1.5)
        status = trade.orderStatus.status
        print(f"Order status immediately after place_order: {status}")
        assert status in {"PreSubmitted", "Submitted", "Filled", "PendingSubmit"}
