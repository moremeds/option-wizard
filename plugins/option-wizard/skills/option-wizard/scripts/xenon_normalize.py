"""Pure functions mapping xenon Query-API JSON into option-wizard's
internal shapes. No network, no I/O.

IB /portfolio leg encoding (verified 2026-06-18):
  - leg.type ∈ {"Put","Call","Stock"}; map Put→P, Call→C.
  - leg carries conId, strike, avg_cost (per-contract $), market_price,
    contracts, direction.
  - symbol + expiry live on the POSITION (ticker; expiry ISO "YYYY-MM-DD"
    or "N/A" for stock), NOT the leg.
  - signed qty = leg.contracts × (+1 LONG / -1 SHORT).
Futu /futu/portfolio (verified):
  - positions[].normalized.{symbol,kind,right,strike,expiry(YYYYMMDD)},
    signed `quantity`.

The synthesized `contract_description` matches the regexes in
defined_risk_audit (_OPTION_RE + _OCC_RE) so audit_book is reused
unchanged.

EXPIRY MODEL (verified against xenon `ib_sync.collapse_positions`):
xenon groups legs by `(ticker, expiry)`, so every position's option legs
share ONE expiry. A diagonal / calendar (legs of different expiries) is
split by xenon into SEPARATE per-expiry positions — each carrying its own
correct expiry — so there is no collapse. The single cross-expiry merge is
a covered call (long stock `expiry="N/A"` + short call), re-keyed to the
OPTION expiry: the stock leg's expiry is irrelevant here (audit emits the
bare symbol; `to_manage_legs` skips stock), and the option leg correctly
takes the position = option expiry. Hence position-level expiry is correct
for every option leg this module emits.
"""

from __future__ import annotations

from typing import Any

_LEG_TYPE_TO_RIGHT = {"Put": "P", "Call": "C"}


def _to_yyyymmdd(s: str | None) -> str | None:
    """'2026-07-17'→'20260717'; '20260717'→'20260717'; 'N/A'/None/''→None."""
    if not s or s == "N/A":
        return None
    digits = s.replace("-", "")
    return digits if len(digits) == 8 and digits.isdigit() else None


def _occ_description(
    symbol: str, expiry_yyyymmdd: str, strike: float, right: str
) -> str:
    """IB-MCP-style description that defined_risk_audit parses, e.g.
    'QQQ   20260717 692 P [QQQ  260717P00692000 100]'."""
    strike_str = f"{strike:g}"
    occ_expiry = expiry_yyyymmdd[2:]  # YYMMDD
    occ_strike = f"{int(round(strike * 1000)):08d}"
    return (
        f"{symbol}   {expiry_yyyymmdd} {strike_str} {right} "
        f"[{symbol}  {occ_expiry}{right}{occ_strike} 100]"
    )


def _signed(qty_magnitude: Any, direction: Any) -> float:
    return float(qty_magnitude or 0.0) * (
        -1.0 if str(direction).upper() == "SHORT" else 1.0
    )


def to_audit_positions(
    ib_portfolio: dict[str, Any],
) -> tuple[list[dict[str, Any]], float]:
    out: list[dict[str, Any]] = []
    for p in ib_portfolio.get("positions") or []:
        symbol = str(p.get("ticker", "")).strip()
        expiry = _to_yyyymmdd(p.get("expiry"))
        for leg in p.get("legs") or []:
            qty = _signed(
                leg.get("contracts"), leg.get("direction", p.get("direction"))
            )
            if leg.get("type") == "Stock":
                out.append({"contract_description": symbol, "position": qty})
                continue
            right = _LEG_TYPE_TO_RIGHT.get(leg.get("type"))
            if right is None or expiry is None:
                continue
            desc = _occ_description(
                symbol, expiry, float(leg.get("strike", 0.0)), right
            )
            out.append({"contract_description": desc, "position": qty})
    acct = ib_portfolio.get("account_summary") or {}
    cash = float(acct.get("cash", acct.get("settled_cash", 0.0)) or 0.0)
    return out, cash


def to_manage_legs(ib_portfolio: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in ib_portfolio.get("positions") or []:
        symbol = str(p.get("ticker", "")).strip()
        expiry = _to_yyyymmdd(p.get("expiry"))
        for leg in p.get("legs") or []:
            right = _LEG_TYPE_TO_RIGHT.get(leg.get("type"))
            if right is None or expiry is None:
                continue  # skip stock + malformed
            out.append(
                {
                    "symbol": symbol,
                    "conId": leg.get("conId"),
                    "strike": float(leg.get("strike", 0.0)),
                    "right": right,
                    "expiry": expiry,
                    "qty": _signed(
                        leg.get("contracts"), leg.get("direction", p.get("direction"))
                    ),
                    "avg_cost": float(leg.get("avg_cost", 0.0) or 0.0),
                    "market_price": leg.get("market_price"),
                }
            )
    return out


def to_futu_audit_positions(
    futu_portfolio: dict[str, Any],
) -> tuple[list[dict[str, Any]], float]:
    out: list[dict[str, Any]] = []
    for p in futu_portfolio.get("positions") or []:
        nm = p.get("normalized") or {}
        symbol = str(nm.get("symbol", "")).strip()
        qty = float(p.get("quantity", 0.0) or 0.0)
        kind = str(nm.get("kind", "")).upper()
        if kind == "STK":
            out.append({"contract_description": symbol, "position": qty})
            continue
        if kind == "OPT":
            right = str(nm.get("right", "")).upper()
            expiry = _to_yyyymmdd(nm.get("expiry"))
            if right not in ("P", "C") or expiry is None:
                continue
            desc = _occ_description(symbol, expiry, float(nm.get("strike", 0.0)), right)
            out.append({"contract_description": desc, "position": qty})
    acct = futu_portfolio.get("account_summary") or {}
    cash = float(acct.get("cash", acct.get("settled_cash", 0.0)) or 0.0)
    return out, cash
