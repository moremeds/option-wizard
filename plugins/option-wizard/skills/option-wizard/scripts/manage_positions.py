"""Daily position scan entrypoint.

Reads positions from IB, prices each option (placeholder for v1: caller
supplies market dict), evaluates each via evaluate_position, and produces
a human-readable report. The report is delivered to:

  - the current Claude Code session via SessionStart context block
  - chenxi.li08@outlook.com via Gmail SMTP (scripts/email_sender.py)
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts._clients import tv as tv_client
from scripts.defined_risk_audit import audit_book, format_audit_findings
from scripts.evaluate_position import (
    SHORT_PREMIUM_STRUCTURES,
    evaluate_short_premium,
)

LOCK_PATH = Path.home() / ".config" / "option-wizard" / "manage_positions.lock"
LOCK_STALE_SECONDS = 600  # if a lock is older than this, ignore it (stuck process)


def _position_key(pos: Any) -> str:
    c = pos.contract
    # Preserve fractional strikes (weekly $252.50 etc.) — int() would silently truncate.
    strike_str = f"{c.strike:g}"
    return f"{c.symbol} {strike_str} {c.right} {c.lastTradeDateOrContractMonth}"


def _infer_structure(pos: Any) -> str:
    # Heuristic for v1: short put -> cash_secured_put unless tagged otherwise.
    # Future work: read from a local positions metadata sidecar.
    qty = pos.position
    right = pos.contract.right.upper()
    if qty < 0 and right == "P":
        return "cash_secured_put"
    if qty < 0 and right == "C":
        return "covered_call"
    return "unknown"


def scan_positions(positions: list, market: dict[str, dict], today: str) -> list[dict]:
    rows = []
    for pos in positions:
        key = _position_key(pos)
        m = market.get(key, {})
        structure = _infer_structure(pos)
        if structure not in SHORT_PREMIUM_STRUCTURES:
            rows.append(
                {
                    "symbol": pos.contract.symbol,
                    "key": key,
                    "action": "HOLD",
                    "dte": m.get("dte", -1),
                    "rationale": "non-short-premium position; manual review",
                }
            )
            continue
        try:
            evaluation = evaluate_short_premium(
                opening_credit=abs(float(pos.avgCost)) / 100,
                current_price=m.get("current_price"),
                dte=m.get("dte", 0),
                delta=m.get("delta"),
                structure=structure,
            )
            rationale = evaluation["rationale"]
            source = m.get("source")
            if source and m.get("current_price") is not None:
                rationale = f"{rationale} [{source}]"
            rows.append(
                {
                    "symbol": pos.contract.symbol,
                    "key": key,
                    "action": evaluation["recommended_action"],
                    "dte": evaluation["dte"],
                    "rationale": rationale,
                }
            )
        except Exception as e:
            rows.append(
                {
                    "symbol": pos.contract.symbol,
                    "key": key,
                    "action": "REVIEW",
                    "dte": m.get("dte", -1),
                    "rationale": f"evaluation error: {e}",
                }
            )
    return rows


def _fetch_market_data(ib: Any, positions: list) -> dict[str, dict]:
    """Pull mid price, delta, DTE for every option position via ib_insync.

    Uses reqMktData with snapshot=False to get a streaming subscription, then
    waits up to 3 seconds for greek+price fields to populate. Returns a dict
    keyed by `_position_key(pos)`. Subscriptions are cancelled in finally
    so a killed process does not leak them on IB Gateway.
    """
    market = {}
    pending = []
    try:
        for pos in positions:
            if not pos.contract.exchange:
                pos.contract.exchange = "SMART"
            ticker = ib._ib.reqMktData(pos.contract, genericTickList="", snapshot=False)
            pending.append((pos, ticker))
        ib._ib.sleep(3)
        for pos, t in pending:
            c = pos.contract
            try:
                expiry = datetime.strptime(
                    c.lastTradeDateOrContractMonth, "%Y%m%d"
                ).date()
                dte = (expiry - datetime.utcnow().date()).days
            except Exception:
                dte = 0
            mid = None
            source = None
            if t.bid is not None and t.ask is not None and t.bid > 0 and t.ask > 0:
                mid = (t.bid + t.ask) / 2
                source = "ib"
            elif t.last is not None and not math.isnan(t.last) and t.last > 0:
                mid = t.last
                source = "ib"
            delta_raw = getattr(t.modelGreeks, "delta", None) if t.modelGreeks else None
            delta = (
                delta_raw
                if delta_raw is not None and not math.isnan(delta_raw)
                else None
            )
            if mid is None:
                tv_quote = tv_client.get_option_quote(
                    symbol=c.symbol,
                    expiry_yyyymmdd=c.lastTradeDateOrContractMonth,
                    strike=c.strike,
                    right=c.right,
                )
                if tv_quote is not None:
                    mid = tv_quote["mid"]
                    source = "tv"
                    if delta is None:
                        delta = tv_quote.get("delta")
            market[_position_key(pos)] = {
                "current_price": mid,
                "delta": delta,
                "dte": dte,
                "source": source,
            }
    finally:
        for _, ticker in pending:
            try:
                ib._ib.cancelMktData(ticker.contract)
            except Exception:
                pass
    return market


def format_scan_report(rows: list[dict]) -> str:
    if not rows:
        return (
            "Daily position scan: no positions found (0 positions). No action needed."
        )

    priority = {"REVIEW": 0, "CLOSE": 1, "ROLL": 2, "HOLD": 3}
    sorted_rows = sorted(rows, key=lambda r: priority.get(r["action"], 99))

    lines = [f"Daily position scan ({datetime.utcnow().date()}):", ""]
    review_count = sum(1 for r in sorted_rows if r["action"] == "REVIEW")
    close_count = sum(1 for r in sorted_rows if r["action"] == "CLOSE")
    lines.append(
        f"  {review_count} require review (21 DTE / blocking), {close_count} ready to close"
    )
    lines.append("")
    for r in sorted_rows:
        if r["action"] == "REVIEW":
            marker = "!"
        elif r["action"] == "HOLD":
            marker = "."
        else:
            marker = "->"
        lines.append(
            f"  {marker} {r['symbol']:6} [{r['action']:6}] DTE {r['dte']:3}  {r['rationale']}"
        )
    return "\n".join(lines)


def _acquire_lock() -> bool:
    """File-based lock prevents cron + SessionStart from running in parallel.

    Returns True if we acquired the lock (and should proceed); False if a
    fresh lock exists (another run is in flight, we should exit quietly).
    """
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        age = (
            datetime.utcnow() - datetime.utcfromtimestamp(LOCK_PATH.stat().st_mtime)
        ).total_seconds()
        if age < LOCK_STALE_SECONDS:
            return False
    LOCK_PATH.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    LOCK_PATH.unlink(missing_ok=True)


def _ib_positions_to_audit_format(
    positions: list, account_summary: dict
) -> tuple[list[dict], float]:
    """Map ib_insync positions into the {contract_description, position}
    shape that audit_book expects.

    The audit module was designed against the IB MCP get_account_positions
    payload (descriptions like `"QQQ    JUN2026 665 P [QQQ   260630P00665000 100]"`).
    ib_insync positions expose the contract directly, so we synthesize a
    matching description per leg.
    """
    audit_positions = []
    for pos in positions:
        c = pos.contract
        secType = getattr(c, "secType", "")
        if secType == "STK":
            desc = c.symbol
        elif secType == "OPT":
            strike_str = f"{c.strike:g}"
            expiry = c.lastTradeDateOrContractMonth
            occ_expiry = expiry[2:] if expiry.startswith("20") else expiry
            occ_strike = f"{int(round(c.strike * 1000)):08d}"
            desc = (
                f"{c.symbol}   {expiry} {strike_str} {c.right} "
                f"[{c.symbol}  {occ_expiry}{c.right}{occ_strike} 100]"
            )
        else:
            continue
        audit_positions.append(
            {"contract_description": desc, "position": float(pos.position)}
        )
    cash = float(
        account_summary.get("TotalCashValue", account_summary.get("CashBalance", 0))
    )
    return audit_positions, cash


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="skip email delivery")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="IB Gateway port (overrides IB_PORT env; falls back to 4001)",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="run the defined-risk audit and exit; skip per-position routine review",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore lockfile (override if you know another run is stuck)",
    )
    args = parser.parse_args(argv)

    if not args.force and not _acquire_lock():
        print("manage_positions: another run is in progress (lockfile fresh); skipping")
        return 0

    from scripts._clients.ib import IBClient

    try:
        ib_kwargs = {"port": args.port} if args.port is not None else {}
        with IBClient(**ib_kwargs) as ib:
            positions = ib.get_positions()
            account_summary = ib.get_account_summary()
            audit_positions, cash = _ib_positions_to_audit_format(
                positions, account_summary
            )
            audit_findings = audit_book(audit_positions, cash_balance=cash)
            audit_section = format_audit_findings(audit_findings)

            if args.audit_only:
                print(audit_section or "Defined-risk audit: no failures (clean book).")
                return 0

            market = _fetch_market_data(ib, positions)
            rows = scan_positions(
                positions, market, today=str(datetime.utcnow().date())
            )
            scan_section = format_scan_report(rows)
            report = (
                (audit_section + "\n" + scan_section) if audit_section else scan_section
            )
        print(report)

        if not args.no_email:
            from scripts.email_sender import send_daily_scan

            send_daily_scan(report, rows)
    finally:
        _release_lock()

    return 0


if __name__ == "__main__":
    sys.exit(main())
