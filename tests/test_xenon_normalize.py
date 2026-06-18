from scripts.defined_risk_audit import audit_book
from scripts.xenon_normalize import (
    to_audit_positions,
    to_futu_audit_positions,
    to_manage_legs,
)

# Real-shape IB /portfolio fixture (representative values).
IB_PORTFOLIO = {
    "last_sync": "2026-06-18T10:30:19.387534",
    "account_summary": {
        "cash": 44316.81,
        "settled_cash": 44316.81,
        "net_liquidation": 65876.66,
        "maintenance_margin": 3576.41,
    },
    "positions": [
        {
            "ticker": "QQQ",
            "structure_type": "Short Put",
            "direction": "SHORT",
            "expiry": "2026-07-17",
            "contracts": 1,
            "legs": [
                {
                    "type": "Put",
                    "conId": 884159412,
                    "strike": 692.0,
                    "avg_cost": 1277.9196,
                    "contracts": 1,
                    "direction": "SHORT",
                    "market_price": 10.74,
                }
            ],
        },
        {
            "ticker": "QQQ",
            "structure_type": "Stock",
            "direction": "LONG",
            "expiry": "N/A",
            "contracts": 18,
            "legs": [
                {
                    "type": "Stock",
                    "conId": 320227571,
                    "strike": 0.0,
                    "avg_cost": 640.20,
                    "contracts": 18,
                    "direction": "LONG",
                    "market_price": 734.41,
                }
            ],
        },
        {
            "ticker": "SPX",
            "structure_type": "Long Put",
            "direction": "LONG",
            "expiry": "2026-07-17",
            "contracts": 1,
            "legs": [
                {
                    "type": "Put",
                    "conId": 873618680,
                    "strike": 6855.0,
                    "avg_cost": 1441.64,
                    "contracts": 1,
                    "direction": "LONG",
                    "market_price": 15.7,
                }
            ],
        },
    ],
}

FUTU_PORTFOLIO = {
    "is_stale": False,
    "fetched_at": "2026-06-18T10:30:36.694Z",
    "account_summary": {"cash": 12000.0, "settled_cash": 12000.0},
    "positions": [
        {
            "futu_code": "US.TSLA270115C650000",
            "quantity": -1.0,
            "avg_cost": 50.0,
            "market_price": 60.0,
            "position_side": "SHORT",
            "normalized": {
                "kind": "OPT",
                "symbol": "TSLA",
                "right": "C",
                "strike": 650.0,
                "expiry": "20270115",
            },
        },
        {
            "futu_code": "US.AAPL",
            "quantity": 100.0,
            "avg_cost": 150.0,
            "market_price": 210.0,
            "position_side": "LONG",
            "normalized": {
                "kind": "STK",
                "symbol": "AAPL",
                "right": None,
                "strike": None,
                "expiry": None,
            },
        },
    ],
}


def test_to_audit_positions_emits_parseable_descriptions_and_cash():
    rows, cash = to_audit_positions(IB_PORTFOLIO)
    assert cash == 44316.81
    # short put leg, signed negative
    qqq_put = next(
        r for r in rows if r["contract_description"].startswith("QQQ   2026")
    )
    assert qqq_put["position"] == -1.0
    # stock leg → bare symbol, positive qty
    assert {"contract_description": "QQQ", "position": 18.0} in rows


def test_to_audit_positions_round_trips_through_audit_book():
    rows, cash = to_audit_positions(IB_PORTFOLIO)
    # cash 44316 < QQQ 692 short put assignment (69_200) → flagged uncovered CSP
    findings = audit_book(rows, cash_balance=cash)
    qqq = next(f for f in findings if f["underlying"] == "QQQ")
    assert qqq["fails"] == "cash_secured_put"
    assert qqq["coverage_ratio"] < 1.0


def test_to_manage_legs_options_only_with_signed_qty_and_yyyymmdd():
    legs = to_manage_legs(IB_PORTFOLIO)
    syms = [(l["symbol"], l["right"], l["expiry"], l["qty"]) for l in legs]
    assert ("QQQ", "P", "20260717", -1.0) in syms
    assert ("SPX", "P", "20260717", 1.0) in syms
    # stock excluded
    assert all(l["right"] in ("P", "C") for l in legs)
    qqq = next(l for l in legs if l["symbol"] == "QQQ")
    assert qqq["conId"] == 884159412
    assert qqq["strike"] == 692.0
    assert qqq["market_price"] == 10.74


def test_to_futu_audit_positions():
    rows, cash = to_futu_audit_positions(FUTU_PORTFOLIO)
    assert cash == 12000.0
    tsla = next(r for r in rows if "TSLA" in r["contract_description"])
    assert tsla["position"] == -1.0
    assert "270115C00650000" in tsla["contract_description"]
    assert {"contract_description": "AAPL", "position": 100.0} in rows
