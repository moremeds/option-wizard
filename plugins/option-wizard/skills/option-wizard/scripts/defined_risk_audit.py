"""Defined-risk audit (spec §10.3).

Reads positions in the shape returned by IB MCP get_account_positions:
    {"contract_id": int, "contract_description": str, "position": float,
     "market_price": float, ...}

Parses option descriptions of the form:
    "QQQ    JUN2026 665 P [QQQ   260630P00665000 100]"

Per underlying, checks:
  - aggregate cash-secured coverage on net-short puts
  - share coverage on net-short calls
  - whether each short option is paired with a long protective option of
    the same expiry within $20 of strike (defined-risk spread)

Returns a list of findings ready to format into the daily report.

Defect note vs the plan-as-written: the plan's reference impl flagged
fully cash-secured short puts as failures because it appended findings
unconditionally on `if uncovered_puts:`. Fixed below — we only flag when
coverage_ratio < 1.0, so test_audit_passes_fully_cash_secured_short_put
holds (positions: -1 ORCL 200P, cash $25k > $20k assignment → pass).
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

_OPTION_RE = re.compile(
    r"^(?P<underlying>\S+)\s+(?P<expiry_label>\S+)\s+(?P<strike>\d+(?:\.\d+)?)\s+(?P<right>[PC])"
)
_OCC_RE = re.compile(
    r"\[(?P<occ_underlying>\S+)\s+(?P<occ_expiry>\d{6})(?P<occ_right>[PC])(?P<occ_strike>\d{8})\s+\d+\]"
)


def _parse_option(description: str) -> dict[str, Any] | None:
    m = _OPTION_RE.match(description)
    if not m:
        return None
    occ = _OCC_RE.search(description)
    expiry = None
    if occ:
        expiry = "20" + occ.group("occ_expiry")
    return {
        "underlying": m.group("underlying"),
        "strike": float(m.group("strike")),
        "right": m.group("right"),
        "expiry": expiry,
    }


def _is_stock(description: str) -> bool:
    return _OPTION_RE.match(description) is None and "[" not in description


def audit_book(
    positions: list[dict[str, Any]],
    cash_balance: float,
) -> list[dict[str, Any]]:
    shares_by_underlying: dict[str, float] = defaultdict(float)
    options_by_underlying: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for p in positions:
        desc = p.get("contract_description", "")
        qty = float(p.get("position", 0.0))
        if _is_stock(desc):
            shares_by_underlying[desc.strip()] += qty
            continue
        opt = _parse_option(desc)
        if opt is None:
            continue
        opt["position"] = qty
        options_by_underlying[opt["underlying"]].append(opt)

    findings: list[dict[str, Any]] = []
    for underlying, legs in options_by_underlying.items():
        shorts_puts = [l for l in legs if l["right"] == "P" and l["position"] < 0]
        longs_puts = [l for l in legs if l["right"] == "P" and l["position"] > 0]
        shorts_calls = [l for l in legs if l["right"] == "C" and l["position"] < 0]
        longs_calls = [l for l in legs if l["right"] == "C" and l["position"] > 0]

        def _is_protected(
            short_leg: dict[str, Any], pool: list[dict[str, Any]]
        ) -> bool:
            return any(
                l["expiry"] == short_leg["expiry"]
                and abs(l["strike"] - short_leg["strike"]) <= 20.0
                for l in pool
            )

        uncovered_puts = [l for l in shorts_puts if not _is_protected(l, longs_puts)]
        uncovered_calls = [l for l in shorts_calls if not _is_protected(l, longs_calls)]

        if uncovered_puts:
            assignment_cost = sum(
                l["strike"] * abs(l["position"]) * 100 for l in uncovered_puts
            )
            coverage_ratio = (
                cash_balance / assignment_cost if assignment_cost else float("inf")
            )
            if coverage_ratio < 1.0:
                findings.append(
                    {
                        "underlying": underlying,
                        "fails": "cash_secured_put",
                        "short_legs": uncovered_puts,
                        "assignment_cost": assignment_cost,
                        "coverage_ratio": coverage_ratio,
                    }
                )

        if uncovered_calls:
            shares = shares_by_underlying.get(underlying, 0.0)
            short_qty = sum(abs(l["position"]) * 100 for l in uncovered_calls)
            if shares < short_qty:
                findings.append(
                    {
                        "underlying": underlying,
                        "fails": "covered_call",
                        "short_legs": uncovered_calls,
                        "shares_held": shares,
                        "shares_needed": short_qty,
                    }
                )

    return findings


def format_audit_findings(findings: list[dict[str, Any]]) -> str:
    """Render findings as a daily-report section."""
    if not findings:
        return ""
    lines = ["Defined-Risk Audit (existing book):", ""]
    for f in findings:
        if f["fails"] == "cash_secured_put":
            lines.append(
                f"  ! {f['underlying']:6} FAILS cash-secured-put "
                f"(assignment ${f['assignment_cost']:,.0f} vs cash "
                f"{f['coverage_ratio'] * 100:.1f}% coverage)"
            )
        elif f["fails"] == "covered_call":
            lines.append(
                f"  ! {f['underlying']:6} FAILS covered-call "
                f"(holds {int(f['shares_held'])} shares, needs {int(f['shares_needed'])})"
            )
    lines.append("")
    return "\n".join(lines)
