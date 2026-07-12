"""Daily position scan entrypoint.

Reads the book + account from the xenon read-only Query API (`/portfolio`),
prices each option leg via live_quote (xenon `/options/greeks` modelGreeks
primary, ib_insync `reqMktData` fallback only with `--ib-fallback`),
evaluates each via evaluate_position, and produces a human-readable report.
The report is delivered to:

  - the current Claude Code session via SessionStart context block
  - chenxi.li08@outlook.com via Gmail SMTP (scripts/email_sender.py)

The daily scan no longer opens IB Gateway in the happy path — xenon serves
greeks around the clock (IB frozen mode). The IB-MCP / ib_insync direct path
is a documented fallback (`--ib-fallback`).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts._clients.xenon import XenonClient
from scripts.defined_risk_audit import audit_book, format_audit_findings
from scripts.evaluate_position import (
    SHORT_PREMIUM_STRUCTURES,
    evaluate_short_premium,
)
from scripts.ledger import default_ledger_path, load_ledger, render_open_items_block
from scripts.live_quote import live_quote
from scripts.xenon_normalize import to_audit_positions, to_manage_legs

LOCK_PATH = Path.home() / ".config" / "option-wizard" / "manage_positions.lock"
LOCK_STALE_SECONDS = 600  # if a lock is older than this, ignore it (stuck process)


def _position_key(leg: dict[str, Any]) -> str:
    # Preserve fractional strikes (weekly $252.50 etc.) — :g avoids truncation.
    strike_str = f"{leg['strike']:g}"
    return f"{leg['symbol']} {strike_str} {leg['right']} {leg['expiry']}"


def _infer_structure(leg: dict[str, Any]) -> str:
    # Heuristic for v1: short put -> cash_secured_put unless tagged otherwise.
    qty = leg["qty"]
    right = leg["right"].upper()
    if qty < 0 and right == "P":
        return "cash_secured_put"
    if qty < 0 and right == "C":
        return "covered_call"
    return "unknown"


def scan_positions(
    legs: list[dict[str, Any]], market: dict[str, dict], today: str
) -> list[dict]:
    rows = []
    for leg in legs:
        key = _position_key(leg)
        m = market.get(key, {})
        structure = _infer_structure(leg)
        symbol = leg["symbol"]
        if structure not in SHORT_PREMIUM_STRUCTURES:
            rows.append(
                {
                    "symbol": symbol,
                    "key": key,
                    "action": "HOLD",
                    "dte": m.get("dte", -1),
                    "rationale": "non-short-premium position; manual review",
                }
            )
            continue
        try:
            evaluation = evaluate_short_premium(
                opening_credit=abs(float(leg["avg_cost"])) / 100,
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
                    "symbol": symbol,
                    "key": key,
                    "action": evaluation["recommended_action"],
                    "dte": evaluation["dte"],
                    "rationale": rationale,
                }
            )
        except Exception as e:
            rows.append(
                {
                    "symbol": symbol,
                    "key": key,
                    "action": "REVIEW",
                    "dte": m.get("dte", -1),
                    "rationale": f"evaluation error: {e}",
                }
            )
    return rows


def _fetch_market_data(
    legs: list[dict[str, Any]], client: Any, ib: Any = None
) -> dict[str, dict]:
    """Price each option leg via live_quote (xenon /options/greeks primary,
    ib_insync reqMktData fallback only when `ib` is supplied). Mid falls back
    to the held leg's market_price, then to a gap — never fabricated. Keyed
    by `_position_key(leg)`."""
    market: dict[str, dict] = {}
    today = datetime.utcnow().date()
    for leg in legs:
        try:
            expiry = datetime.strptime(leg["expiry"], "%Y%m%d").date()
            dte = (expiry - today).days
        except Exception:
            dte = 0
        q = live_quote(
            leg["symbol"],
            leg["expiry"],
            leg["strike"],
            leg["right"],
            client=client,
            ib=ib,
            fallback_market_price=leg.get("market_price"),
        )
        market[_position_key(leg)] = {
            "current_price": q["mid"],
            "delta": q["delta"],
            "dte": dte,
            "source": q["mid_source"],
        }
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
    """FALLBACK ONLY (ib_insync direct path). main() now sources the book
    from xenon via scripts.xenon_normalize.to_audit_positions. Retained for
    the documented offline / ib_insync fallback ladder; not called in the
    happy path.

    Maps ib_insync positions into the {contract_description, position} shape
    audit_book expects (descriptions like
    `"QQQ    JUN2026 665 P [QQQ   260630P00665000 100]"`).
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
        "--audit-only",
        action="store_true",
        help="run the defined-risk audit and exit; skip per-position routine review",
    )
    parser.add_argument(
        "--ib-fallback",
        action="store_true",
        help="open ib_insync as a greeks fallback when xenon returns null greeks "
        "(default: xenon-only — the daily scan no longer needs IB Gateway)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="IB Gateway port for --ib-fallback (overrides IB_PORT env; default 4001)",
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

    rows: list[dict] = []
    try:
        # Open decision-ledger items (references/decision-doctrine.md
        # §"Dynamic risk management") surface here so a prior 决策块 action
        # item ("roll TSLA 400/390 down by 6/25") doesn't only live in a
        # one-off report the trader has to remember to reread.
        ledger_block = render_open_items_block(load_ledger(default_ledger_path()))

        client = XenonClient()
        ib_portfolio = client.ib_portfolio()
        audit_positions, cash = to_audit_positions(ib_portfolio)
        audit_findings = audit_book(audit_positions, cash_balance=cash)
        audit_section = format_audit_findings(audit_findings)

        if args.audit_only:
            body = audit_section or "Defined-risk audit: no failures (clean book)."
            print(f"{ledger_block}\n\n{body}" if ledger_block else body)
            return 0

        legs = to_manage_legs(ib_portfolio)

        ib_ctx = None
        ib = None
        if args.ib_fallback:
            from scripts._clients.ib import IBClient

            ib_kwargs = {"port": args.port} if args.port is not None else {}
            ib_ctx = IBClient(**ib_kwargs)
            ib_ctx.connect()
            ib = ib_ctx
        try:
            market = _fetch_market_data(legs, client, ib=ib)
        finally:
            if ib_ctx is not None:
                ib_ctx.disconnect()

        rows = scan_positions(legs, market, today=str(datetime.utcnow().date()))
        scan_section = format_scan_report(rows)
        report = (
            (audit_section + "\n" + scan_section) if audit_section else scan_section
        )
        if ledger_block:
            report = f"{ledger_block}\n\n{report}"
        print(report)

        if not args.no_email:
            from scripts.email_sender import send_daily_scan

            send_daily_scan(report, rows)
    except Exception:
        import traceback

        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        # Failure alert bypasses --no-email deliberately: the live cron runs
        # --no-email (report goes to the SessionStart hook), but a dead scan
        # must still page the trader.
        try:
            from scripts import email_sender

            email_sender.send_failure_alert(tb)
        except Exception as mail_err:  # alert must never mask the original error
            print(f"failure-alert email also failed: {mail_err}", file=sys.stderr)
        return 1
    finally:
        _release_lock()

    return 0


if __name__ == "__main__":
    sys.exit(main())
