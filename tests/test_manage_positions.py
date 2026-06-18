from scripts.manage_positions import format_scan_report, scan_positions

FAKE_LEGS = [
    {
        "symbol": "ORCL",
        "strike": 235,
        "right": "P",
        "expiry": "20260725",
        "qty": -5,
        "avg_cost": 420.0,
        "conId": 1,
        "market_price": 2.0,
    },
    {
        "symbol": "NVDA",
        "strike": 800,
        "right": "C",
        "expiry": "20260725",
        "qty": -1,
        "avg_cost": 1200.0,
        "conId": 2,
        "market_price": 28.0,
    },
]


def test_scan_returns_one_row_per_leg():
    market = {
        "ORCL 235 P 20260725": {
            "current_price": 2.00,
            "delta": -0.18,
            "dte": 52,
            "source": "xenon",
        },
        "NVDA 800 C 20260725": {
            "current_price": 28.00,
            "delta": -0.65,
            "dte": 52,
            "source": "xenon",
        },
    }
    rows = scan_positions(legs=FAKE_LEGS, market=market, today="2026-06-03")
    assert len(rows) == 2
    assert {r["symbol"] for r in rows} == {"ORCL", "NVDA"}


def test_format_scan_report_prioritizes_REVIEW_rows():
    rows = [
        {"symbol": "AAA", "action": "HOLD", "dte": 50, "rationale": "fine"},
        {"symbol": "BBB", "action": "REVIEW", "dte": 19, "rationale": "21 DTE window"},
        {"symbol": "CCC", "action": "CLOSE", "dte": 40, "rationale": "take-profit"},
    ]
    report = format_scan_report(rows)
    assert report.index("BBB") < report.index("CCC")
    assert report.index("BBB") < report.index("AAA")


def test_report_includes_no_action_line_when_empty():
    report = format_scan_report([])
    assert "no" in report.lower() or "0 positions" in report.lower()
