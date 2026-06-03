"""Daily position scan entrypoint.

Reads positions from IB, prices each option (placeholder for v1: caller
supplies market dict), evaluates each via evaluate_position, and produces
a human-readable report. The report is delivered to:

  - the current Claude Code session via SessionStart context block
  - chenxi.li08@outlook.com via Gmail SMTP (scripts/email_sender.py)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
                current_price=m.get("current_price", 0.0),
                dte=m.get("dte", 0),
                delta=m.get("delta", 0.0),
                structure=structure,
            )
            rows.append(
                {
                    "symbol": pos.contract.symbol,
                    "key": key,
                    "action": evaluation["recommended_action"],
                    "dte": evaluation["dte"],
                    "rationale": evaluation["rationale"],
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
            if t.bid is not None and t.ask is not None and t.bid > 0 and t.ask > 0:
                mid = (t.bid + t.ask) / 2
            elif t.last is not None:
                mid = t.last
            delta = getattr(t.modelGreeks, "delta", 0.0) if t.modelGreeks else 0.0
            market[_position_key(pos)] = {
                "current_price": mid or 0.0,
                "delta": delta,
                "dte": dte,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="skip email delivery")
    parser.add_argument("--port", type=int, default=4001, help="IB Gateway port")
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
        with IBClient(port=args.port) as ib:
            positions = ib.get_positions()
            market = _fetch_market_data(ib, positions)
            rows = scan_positions(
                positions, market, today=str(datetime.utcnow().date())
            )
            report = format_scan_report(rows)
        print(report)

        if not args.no_email:
            from scripts.email_sender import send_daily_scan

            send_daily_scan(report, rows)
    finally:
        _release_lock()

    return 0


if __name__ == "__main__":
    sys.exit(main())
