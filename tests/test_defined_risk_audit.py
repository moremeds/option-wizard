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


def test_audit_recognizes_wide_paired_spread_as_defined_risk():
    # Regression: SMH 560/590 bear put debit spread ($30 wide) false-
    # positived under the old fixed-$20 pairing check (2026-06 book
    # reviews). Width must never gate protection — only net qty does.
    positions = [
        _pos(1, "SMH    JUL2026 590 P [SMH   260717P00590000 100]", +6),
        _pos(2, "SMH    JUL2026 560 P [SMH   260717P00560000 100]", -6),
    ]
    findings = audit_book(positions, cash_balance=0.0)
    assert findings == []


def test_audit_recognizes_broken_wing_fly_as_defined_risk():
    # Regression: MU 750/855/950 broken-wing fly (+2/-4/+2, wings 95/105
    # wide) false-positived under the old check. Net long qty (4) == net
    # short qty (4) in the same expiry bucket -> fully defined.
    positions = [
        _pos(1, "MU     JUN2026 750 P [MU    260612P00750000 100]", +2),
        _pos(2, "MU     JUN2026 855 P [MU    260612P00855000 100]", -4),
        _pos(3, "MU     JUN2026 950 P [MU    260612P00950000 100]", +2),
    ]
    findings = audit_book(positions, cash_balance=0.0)
    assert findings == []


def test_audit_flags_naked_residual_short_put_in_same_bucket():
    # A long put in the same expiry only partially offsets a larger short
    # qty -> the residual (short 20, long 10 = naked 10) must still flag.
    positions = [
        _pos(1, "NVDA   AUG2026 200 P [NVDA  260821P00200000 100]", -20),
        _pos(2, "NVDA   AUG2026 190 P [NVDA  260821P00190000 100]", +10),
    ]
    findings = audit_book(positions, cash_balance=0.0)
    nvda = next(f for f in findings if f["underlying"] == "NVDA")
    assert nvda["fails"] == "cash_secured_put"
    assert sum(abs(leg["position"]) for leg in nvda["short_legs"]) == 10


def test_audit_does_not_treat_calendar_as_protected():
    # A long put in a LATER expiry does not cover a short put expiring
    # first (strict mode, per 2026-06-04 book review design note) -- the
    # short leg has real gap risk between the two expiries.
    positions = [
        _pos(1, "TSLA   JUN2026 390 P [TSLA  260618P00390000 100]", -10),
        _pos(2, "TSLA   JAN2027 390 P [TSLA  270115P00390000 100]", +10),
    ]
    findings = audit_book(positions, cash_balance=0.0)
    tsla = next(f for f in findings if f["underlying"] == "TSLA")
    assert tsla["fails"] == "cash_secured_put"
    assert sum(abs(leg["position"]) for leg in tsla["short_legs"]) == 10
