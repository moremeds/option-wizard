from scripts.defined_risk_audit import audit_book


def _pos(contract_id, description, position, market_price=0.0):
    return {
        "contract_id": contract_id,
        "contract_description": description,
        "position": position,
        "market_price": market_price,
    }


def test_audit_flags_uncovered_short_puts_by_underlying():
    positions = [
        _pos(1, "QQQ    JUN2026 665 P [QQQ   260630P00665000 100]", -2),
        _pos(2, "QQQ    JUN2026 695 P [QQQ   260630P00695000 100]", -1),
    ]
    cash = 38_177.0
    findings = audit_book(positions, cash_balance=cash)
    qqq = next(f for f in findings if f["underlying"] == "QQQ")
    assert qqq["assignment_cost"] == 665 * 200 + 695 * 100
    assert qqq["coverage_ratio"] < 1.0
    assert qqq["fails"] == "cash_secured_put"


def test_audit_passes_fully_cash_secured_short_put():
    positions = [_pos(1, "ORCL   JUN2026 200 P [ORCL  260619P00200000 100]", -1)]
    findings = audit_book(positions, cash_balance=25_000.0)
    assert findings == []


def test_audit_passes_covered_call():
    positions = [
        _pos(1, "ORCL", 300, market_price=170.0),
        _pos(2, "ORCL   JUN2026 250 C [ORCL  260619C00250000 100]", -2),
    ]
    findings = audit_book(positions, cash_balance=0.0)
    assert findings == []


def test_audit_flags_uncovered_short_call():
    positions = [
        _pos(1, "ORCL", 100, market_price=170.0),
        _pos(2, "ORCL   JUN2026 250 C [ORCL  260619C00250000 100]", -2),
    ]
    findings = audit_book(positions, cash_balance=0.0)
    orcl = next(f for f in findings if f["underlying"] == "ORCL")
    assert orcl["fails"] == "covered_call"


def test_audit_recognizes_a_paired_spread_as_defined_risk():
    positions = [
        _pos(1, "QQQ    JUN2026 695 P [QQQ   260630P00695000 100]", -1),
        _pos(2, "QQQ    JUN2026 685 P [QQQ   260630P00685000 100]", +1),
    ]
    findings = audit_book(positions, cash_balance=0.0)
    assert findings == []
