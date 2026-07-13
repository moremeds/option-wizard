"""Defined-risk audit (spec §10.3).

Reads positions in the shape returned by IB MCP get_account_positions:
    {"contract_id": int, "contract_description": str, "position": float,
     "market_price": float, ...}

Parses option descriptions of the form:
    "QQQ    JUN2026 665 P [QQQ   260630P00665000 100]"

Per underlying, checks:
  - aggregate cash-secured coverage on net-short puts
  - share coverage on net-short calls
  - whether short options are quantity-covered by long options in the same
    (underlying, expiry, right) bucket — no strike-width limit. A bucket
    with long qty >= short qty is fully defined-risk regardless of how wide
    the spread is; any residual short qty is uncovered. Buckets never cross
    expiry (strict mode) — a calendar/diagonal's long leg in a later expiry
    does not protect a short leg expiring first (real gap risk).

Returns a list of findings ready to format into the daily report.

Defect note vs the plan-as-written: the plan's reference impl flagged
fully cash-secured short puts as failures because it appended findings
unconditionally on `if uncovered_puts:`. Fixed below — we only flag when
coverage_ratio < 1.0, so test_audit_passes_fully_cash_secured_short_put
holds (positions: -1 ORCL 200P, cash $25k > $20k assignment → pass).

Prior defect (fixed 2026-07): a fixed $20 strike-width pairing check
false-positived on any wide spread (SMH $30, MU broken-wing fly $95/105,
LLY $40 — flagged 3 times independently across 2026-06 book reviews).
Replaced with the quantity-conservation bucket check above.
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


def _uncovered_legs(legs: list[dict[str, Any]], right: str) -> list[dict[str, Any]]:
    """Net short vs long qty per (expiry, right) bucket — never across
    expiries. Returns the residual short legs (worst-strike-first for puts,
    so downstream assignment-cost math stays conservative) if the bucket
    isn't fully covered; empty if it is."""
    by_expiry: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for leg in legs:
        if leg["right"] == right:
            by_expiry[leg["expiry"]].append(leg)

    uncovered: list[dict[str, Any]] = []
    for expiry_legs in by_expiry.values():
        shorts = [leg for leg in expiry_legs if leg["position"] < 0]
        longs = [leg for leg in expiry_legs if leg["position"] > 0]
        residual = sum(abs(leg["position"]) for leg in shorts) - sum(
            leg["position"] for leg in longs
        )
        if residual <= 0:
            continue
        for leg in sorted(shorts, key=lambda x: -x["strike"]):
            if residual <= 0:
                break
            take = min(residual, abs(leg["position"]))
            uncovered.append({**leg, "position": -take})
            residual -= take
    return uncovered


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
        uncovered_puts = _uncovered_legs(legs, right="P")
        uncovered_calls = _uncovered_legs(legs, right="C")

        if uncovered_puts:
            assignment_cost = sum(
                leg["strike"] * abs(leg["position"]) * 100 for leg in uncovered_puts
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
            short_qty = sum(abs(leg["position"]) * 100 for leg in uncovered_calls)
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
