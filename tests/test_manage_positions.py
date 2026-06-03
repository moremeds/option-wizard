from unittest.mock import MagicMock

from scripts.manage_positions import format_scan_report, scan_positions


def test_scan_returns_one_row_per_position():
    fake_positions = [
        MagicMock(
            contract=MagicMock(
                symbol="ORCL",
                strike=235,
                right="P",
                lastTradeDateOrContractMonth="20260725",
            ),
            position=-5,
            avgCost=4.20,
        ),
        MagicMock(
            contract=MagicMock(
                symbol="NVDA",
                strike=800,
                right="C",
                lastTradeDateOrContractMonth="20260725",
            ),
            position=-1,
            avgCost=12.00,
        ),
    ]
    fake_market = {
        "ORCL 235 P 20260725": {"current_price": 2.00, "delta": -0.18, "dte": 52},
        "NVDA 800 C 20260725": {"current_price": 28.00, "delta": -0.65, "dte": 52},
    }
    rows = scan_positions(
        positions=fake_positions, market=fake_market, today="2026-06-03"
    )
    assert len(rows) == 2
    assert {r["symbol"] for r in rows} == {"ORCL", "NVDA"}


def test_format_scan_report_prioritizes_REVIEW_rows():
    rows = [
        {"symbol": "AAA", "action": "HOLD", "dte": 50, "rationale": "fine"},
        {"symbol": "BBB", "action": "REVIEW", "dte": 19, "rationale": "21 DTE window"},
        {"symbol": "CCC", "action": "CLOSE", "dte": 40, "rationale": "take-profit"},
    ]
    report = format_scan_report(rows)
    review_idx = report.index("BBB")
    close_idx = report.index("CCC")
    hold_idx = report.index("AAA")
    assert review_idx < close_idx
    assert review_idx < hold_idx


def test_report_includes_no_action_line_when_empty():
    report = format_scan_report([])
    assert "no" in report.lower() or "0 positions" in report.lower()
