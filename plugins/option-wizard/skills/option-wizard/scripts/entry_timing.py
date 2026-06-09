"""Entry timing decision tree for short-dated short-premium structures.

5-step tree: VIX gate → premarket gap → dealer GEX → 0DTE flow → mode window.
Day-specific overrides (FOMC / Monday open / OPEX Friday) take priority.

All thresholds in the THRESHOLDS dict at module top — first-draft heuristics,
calibrate via scripts.entry_timing --calibrate against the JSONL audit log.

Mode strings:
  - "csp"             — QQQ/SPY cash-secured put (morning window)
  - "rut_calendar"    — RUT diagonal calendar mode (EOD window)
  - "rut_protective"  — RUT diagonal protective mode (morning window)
  - "rut_aggressive"  — RUT diagonal aggressive mode (EOD only)
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

THRESHOLDS = {
    "vix_abort_high": 18.0,
    "vix_event_ratio": 1.05,
    "vix_abort_low": 12.0,
    "gap_wait_pct": 0.010,
    "gap_wait_pct_rut": 0.015,
    "gex_flip_proximity": 0.010,
    "odte_put_buyer_ratio": 3.0,
    "aggressive_mode_vix_cap": 25.0,
    "event_proximity_days": 2,
    "iv_term_inversion_event_window_days": 5,
}

# HIGH-severity scheduled macro events that move the whole tape (CPI / NFP /
# FOMC / PPI / Fed Chair speeches). Selling premium within
# THRESHOLDS["event_proximity_days"] of one of these = paying for the binary
# print with no IV-crush edge. Orchestrator computes
# (next_event_severity, next_event_days_away, next_event_name) from
# unusual-whales:get_market_events and passes via the snapshot.
HIGH_SEVERITY_EVENT_NAMES = (
    "CPI",
    "Core CPI",
    "PPI",
    "Core PPI",
    "NFP",
    "Non-Farm Payrolls",
    "FOMC",
    "FOMC Statement",
    "FOMC Minutes",
    "Fed Chair Powell",
    "Fed Chair Speech",
)

# Resolve audit log path relative to this module so the file works across
# users and machines (was: hardcoded ~/projects/option-wizard/... which only
# worked for one user; the try/except in _write_audit_log silently swallowed
# failures for everyone else, making calibrate() report 0 decisions forever).
# Layout: <skill_root>/scripts/entry_timing.py → skill_root = parent.parent;
#   AUDIT_LOG_PATH = <skill_root>/references/private/market/entry-timing-log.jsonl
_SKILL_ROOT = Path(__file__).resolve().parent.parent
AUDIT_LOG_PATH = str(
    _SKILL_ROOT / "references" / "private" / "market" / "entry-timing-log.jsonl"
)

# Full set of threshold trigger names (kept in sync with branch labels in
# _step1..._step5 / _day_specific_override / _aggressive_mode_vix_check /
# _check_snapshot_freshness). calibrate() seeds with this list so never-fired
# thresholds appear with count=0 + tuning hint.
ALL_TRIGGER_NAMES = (
    "vix_event_backwardation",
    "vix_too_low_cheap_vrp",
    "premarket_gap",
    "gex_short_flip_proximity",
    "odte_put_buyer_imbalance",
    "mode_window_morning",
    "mode_window_morning_pending",
    "mode_window_morning_missed",
    "mode_window_eod",
    "fomc_presser",
    "monday_open_unwind",
    "opex_friday_pin_csp",
    "opex_friday_anchor_max_pain",
    "aggressive_mode_vix_cap",
    "event_proximity_high_severity",
    "iv_term_inverted_event_pricing",
    "iv_term_inverted_morning_downgrade",
    "freshness_stale_snapshot",
    "freshness_missing_timestamp",
    "freshness_invalid_timestamp",
    "none",
)


def _is_rut_mode(mode: str) -> bool:
    return mode.startswith("rut_")


def _check_snapshot_freshness(snap: dict) -> dict | None:
    """Per spec §10 hard rule #7: snapshot must be ≤ 15 min stale for entry
    decisions (tighter than the 1-trading-day default because dealer GEX +
    0DTE flow + premarket gap move minute-by-minute)."""
    ts_iso = snap.get("snapshot_taken_at")
    if not ts_iso:
        return {
            "action": "abort",
            "reason": "snapshot.snapshot_taken_at missing; cannot verify freshness",
            "triggered_threshold": "freshness_missing_timestamp",
            "retry_at_iso": None,
        }
    try:
        snap_ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    except ValueError:
        return {
            "action": "abort",
            "reason": f"snapshot.snapshot_taken_at {ts_iso!r} not valid ISO8601",
            "triggered_threshold": "freshness_invalid_timestamp",
            "retry_at_iso": None,
        }
    age = datetime.now(timezone.utc) - snap_ts
    if age > timedelta(minutes=15):
        return {
            "action": "abort",
            "reason": (
                f"snapshot {age.total_seconds() / 60:.0f} min stale (> 15 min); "
                "re-pull UW + TV"
            ),
            "triggered_threshold": "freshness_stale_snapshot",
            "retry_at_iso": None,
        }
    return None


def _step_event_clock(snap: dict) -> dict | None:
    """ABORT if a HIGH-severity macro event is within event_proximity_days.

    Live-run gap surfaced 2026-06-09: entry_timing only gated `is_fomc_day`
    (today IS the FOMC presser), so a CPI scheduled for the next morning
    silently passed. The day-specific override fires the day of an FOMC
    presser; this gate fires the day(s) BEFORE any high-severity binary
    print (CPI / NFP / PPI / FOMC / Fed Chair). Orchestrator computes the
    next-event triple from unusual-whales:get_market_events.

    Snapshot fields:
      - next_event_name        : str | None (e.g., "CPI", "FOMC", "NFP")
      - next_event_severity    : "HIGH" | "MEDIUM" | "LOW" | None
      - next_event_days_away   : int | None (1 = tomorrow, 0 = today)

    Today's catch is "tomorrow" — but 0 is also a fail-fast: the day's
    presser handling lives in _day_specific_override, but if orchestrator
    passes next_event_days_away=0 with severity HIGH we still want to abort
    here in case the day-flag (is_fomc_day) wasn't computed.
    """
    sev = snap.get("next_event_severity")
    days = snap.get("next_event_days_away")
    name = snap.get("next_event_name", "HIGH-severity macro event")
    if sev != "HIGH" or days is None:
        return None
    if days > THRESHOLDS["event_proximity_days"]:
        return None
    return {
        "action": "abort",
        "reason": (
            f"{name} in {days}d (≤ {THRESHOLDS['event_proximity_days']}d "
            "event_proximity gate) — selling premium into a binary print pays "
            "for the move with no edge; defer entry until event passes"
        ),
        "triggered_threshold": "event_proximity_high_severity",
        "retry_at_iso": None,
    }


def _step_iv_term_inversion(snap: dict, mode: str) -> dict | None:
    """Gate inverted IV term structure (front-month richer than back-month).

    Inverted term = market explicitly pricing event-driven vol concentration
    in the front. Combined with a near-term event (≤ 5 trading days), it's
    confirmation that selling premium pays for known vol. Alone, it's a
    weaker signal — downgrade morning-window entries to EOD where the
    event-IV has had more hours to crush.

    Snapshot field:
      - iv_term_inverted : bool — orchestrator sets True when
        iv_atm_short > iv_atm_long (or per UW IV term structure response).

    This gate sits below _step_event_clock so it never fires when event_clock
    already aborted; standalone inversion still flows through.
    """
    if not snap.get("iv_term_inverted"):
        return None
    days = snap.get("next_event_days_away")
    if days is not None and days <= THRESHOLDS["iv_term_inversion_event_window_days"]:
        return {
            "action": "abort",
            "reason": (
                f"IV term inverted (front > back) + event in {days}d — "
                "market explicitly pricing event vol; defer until resolution"
            ),
            "triggered_threshold": "iv_term_inverted_event_pricing",
            "retry_at_iso": None,
        }
    # Inversion without a flagged catalyst: downgrade morning entries to EOD.
    # Mode-window decoding mirrors _step5_mode_window so we only downgrade
    # modes that would otherwise enter in the morning.
    time_et = snap.get("time_et", "10:00")
    hour = int(time_et.split(":")[0])
    minute = int(time_et.split(":")[1])
    minutes_into_day = hour * 60 + minute
    morning_end = 10 * 60 + 30
    is_morning_mode = mode in ("csp", "rut_protective")
    if is_morning_mode and minutes_into_day <= morning_end:
        return {
            "action": "wait_eod",
            "reason": (
                "IV term inverted; defer morning entry to EOD where event-driven "
                "front-month IV has more time to normalize"
            ),
            "triggered_threshold": "iv_term_inverted_morning_downgrade",
            "retry_at_iso": None,
        }
    return None


def _day_specific_override(snap: dict, mode: str) -> dict | None:
    """FOMC presser / Monday open / OPEX Friday overrides (priority above all)."""
    time_et = snap.get("time_et", "10:00")
    hour = int(time_et.split(":")[0])
    minute = int(time_et.split(":")[1])
    if snap.get("is_fomc_day") and hour < 14:
        return {
            "action": "wait_minutes",
            "reason": "FOMC presser day; wait until 14:30 ET",
            "triggered_threshold": "fomc_presser",
            "retry_at_iso": None,
            "wait_minutes": (14 * 60 + 30) - (hour * 60 + minute),
        }
    if snap.get("is_monday_open") and hour == 9 and minute < 60:
        return {
            "action": "wait_minutes",
            "reason": "Monday open: wait 30 min for weekend gamma unwind",
            "triggered_threshold": "monday_open_unwind",
            "retry_at_iso": None,
            "wait_minutes": 30,
        }
    if snap.get("is_opex_friday") and hour >= 12:
        if mode == "csp":
            return {
                "action": "wait_eod",
                "reason": (
                    "OPEX Friday afternoon: pin trading active; defer CSP entry "
                    "to EOD window"
                ),
                "triggered_threshold": "opex_friday_pin_csp",
                "retry_at_iso": None,
            }
        return {
            "action": "enter_now",
            "reason": (
                "OPEX Friday afternoon: anchor short strike to UW max pain "
                "(orchestrator verifies)"
            ),
            "triggered_threshold": "opex_friday_anchor_max_pain",
            "retry_at_iso": None,
        }
    return None


def _aggressive_mode_vix_check(snap: dict, mode: str) -> dict | None:
    """RUT aggressive mode hard limit: VIX < 25."""
    if (
        mode == "rut_aggressive"
        and snap.get("vix", 0) >= THRESHOLDS["aggressive_mode_vix_cap"]
    ):
        return {
            "action": "abort",
            "reason": (
                f"RUT aggressive mode requires VIX < {THRESHOLDS['aggressive_mode_vix_cap']}; "
                f"current {snap.get('vix'):.1f} — fall back to protective mode"
            ),
            "triggered_threshold": "aggressive_mode_vix_cap",
            "retry_at_iso": None,
        }
    return None


def _step1_vix_gate(snap: dict) -> dict | None:
    """ABORT on VIX event backwardation or too-low + CHEAP VRP."""
    vix = snap.get("vix", 15.0)
    vix1d = snap.get("vix1d", vix)
    vix9d = snap.get("vix9d", vix)
    if (
        vix1d > vix > THRESHOLDS["vix_abort_high"]
        and vix9d > 0
        and (vix1d / vix9d) > THRESHOLDS["vix_event_ratio"]
    ):
        return {
            "action": "abort",
            "reason": (
                f"VIX1D {vix1d:.1f} > VIX {vix:.1f} > {THRESHOLDS['vix_abort_high']} + "
                f"backwardation ratio {vix1d / vix9d:.2f} > {THRESHOLDS['vix_event_ratio']}"
            ),
            "triggered_threshold": "vix_event_backwardation",
            "retry_at_iso": None,
        }
    if vix < THRESHOLDS["vix_abort_low"] and snap.get("vrp_label") == "CHEAP":
        return {
            "action": "abort",
            "reason": (
                f"VIX {vix:.1f} < {THRESHOLDS['vix_abort_low']} + VRP=CHEAP — "
                "no risk premium to capture"
            ),
            "triggered_threshold": "vix_too_low_cheap_vrp",
            "retry_at_iso": None,
        }
    return None


def _step2_premarket_gap(snap: dict, mode: str) -> dict | None:
    """WAIT 30 min if absolute premarket gap exceeds mode-specific threshold."""
    gap = abs(snap.get("premarket_gap", 0.0))
    threshold = (
        THRESHOLDS["gap_wait_pct_rut"]
        if _is_rut_mode(mode)
        else THRESHOLDS["gap_wait_pct"]
    )
    if gap > threshold:
        return {
            "action": "wait_minutes",
            "reason": f"premarket gap {gap * 100:.2f}% > {threshold * 100:.1f}% — wait 30 min",
            "triggered_threshold": "premarket_gap",
            "retry_at_iso": None,
            "wait_minutes": 30,
        }
    return None


def _step3_gex_state(snap: dict) -> dict | None:
    """WAIT_EOD if dealers short gamma AND spot within 1% of gamma flip."""
    spot = snap["spot"]
    flip = snap.get("gex_flip")
    gex = snap.get("net_dealer_gex", 0.0)
    if flip is None or spot == 0:
        return None
    proximity = abs(flip - spot) / spot
    if gex < 0 and proximity < THRESHOLDS["gex_flip_proximity"]:
        return {
            "action": "wait_eod",
            "reason": (
                f"short dealer gamma ({gex:.1e}) + flip @ {flip:.0f} within "
                f"{proximity * 100:.2f}% of spot {spot:.0f} — positioning unstable"
            ),
            "triggered_threshold": "gex_short_flip_proximity",
            "retry_at_iso": None,
        }
    return None


def _step4_odte_flow(snap: dict) -> dict | None:
    """WAIT if 0DTE put-buyer ratio exceeds threshold."""
    pp = snap.get("odte_put_premium", 0.0)
    cp = snap.get("odte_call_premium", 0.0)
    if cp <= 0:
        return None
    ratio = pp / cp
    if ratio > THRESHOLDS["odte_put_buyer_ratio"]:
        return {
            "action": "wait_minutes",
            "reason": (
                f"0DTE put/call premium ratio {ratio:.1f} > "
                f"{THRESHOLDS['odte_put_buyer_ratio']} — wait for whale flow to clear"
            ),
            "triggered_threshold": "odte_put_buyer_imbalance",
            "retry_at_iso": None,
            "wait_minutes": 30,
        }
    return None


def _step5_mode_window(snap: dict, mode: str) -> dict:
    """Final gate: pick window by mode. Compare current time to target window."""
    time_et = snap.get("time_et", "10:00")
    hour = int(time_et.split(":")[0])
    minute = int(time_et.split(":")[1])
    minutes_into_day = hour * 60 + minute

    morning_start, morning_end = 9 * 60 + 45, 10 * 60 + 30
    eod_start, eod_end = 15 * 60 + 30, 15 * 60 + 55

    mode_window = {
        "csp": "morning",
        "rut_calendar": "eod",
        "rut_protective": "morning",
        "rut_aggressive": "eod",
    }.get(mode, "morning")

    if mode_window == "morning":
        if morning_start <= minutes_into_day <= morning_end:
            return {
                "action": "enter_now",
                "reason": f"in morning window for {mode}",
                "triggered_threshold": "mode_window_morning",
                "retry_at_iso": None,
            }
        if minutes_into_day < morning_start:
            return {
                "action": "wait_minutes",
                "reason": "morning window opens at 09:45 ET",
                "triggered_threshold": "mode_window_morning_pending",
                "retry_at_iso": None,
                "wait_minutes": morning_start - minutes_into_day,
            }
        return {
            "action": "wait_eod",
            "reason": "morning window passed; defer to next session or EOD review",
            "triggered_threshold": "mode_window_morning_missed",
            "retry_at_iso": None,
        }
    # eod
    if eod_start <= minutes_into_day <= eod_end:
        return {
            "action": "enter_now",
            "reason": f"in EOD window for {mode}",
            "triggered_threshold": "mode_window_eod",
            "retry_at_iso": None,
        }
    return {
        "action": "wait_eod",
        "reason": f"EOD window {mode}: 15:30-15:55 ET",
        "triggered_threshold": "mode_window_eod",
        "retry_at_iso": None,
    }


def _write_audit_log(snapshot: dict, mode: str, decision: dict) -> None:
    """Append one JSONL line to AUDIT_LOG_PATH. Silently no-op if path unwritable.

    `snapshot_hash` = SHA-256[:16] of canonical-ordered snapshot_summary
    (spec §8.4). Lets calibrate() detect duplicate decisions on the same input
    without false-positive 'threshold fired N times'.
    """
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        snapshot_summary = {
            k: snapshot.get(k)
            for k in (
                "spot",
                "vix",
                "vix1d",
                "vix9d",
                "premarket_gap",
                "net_dealer_gex",
                "gex_flip",
                "odte_put_premium",
                "odte_call_premium",
                "is_fomc_day",
                "is_monday_open",
                "is_opex_friday",
                "snapshot_taken_at",
            )
        }
        snap_hash = hashlib.sha256(
            json.dumps(snapshot_summary, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        line = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "decision": decision["action"],
            "triggered_threshold": decision.get("triggered_threshold", "unknown"),
            "snapshot_hash": snap_hash,
            "snapshot_summary": snapshot_summary,
        }
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(line) + "\n")
    except (OSError, PermissionError):
        pass  # audit log is best-effort


def decide(snapshot: dict[str, Any], mode: str) -> dict[str, Any]:
    """Return one of: enter_now, wait_eod, wait_minutes, abort.

    Side effect: appends JSONL line to AUDIT_LOG_PATH (best-effort).
    """
    # Priority: freshness → event clock (HIGH severity event within N days)
    # → IV term inversion → day-specific override → mode hard limits →
    # vix gate → gap → gex → 0dte → mode window
    for step in (
        _check_snapshot_freshness,
        _step_event_clock,
        lambda s: _step_iv_term_inversion(s, mode),
        lambda s: _day_specific_override(s, mode),
        lambda s: _aggressive_mode_vix_check(s, mode),
        _step1_vix_gate,
        lambda s: _step2_premarket_gap(s, mode),
        _step3_gex_state,
        _step4_odte_flow,
    ):
        result = step(snapshot)
        if result is not None:
            _write_audit_log(snapshot, mode, result)
            return result
    final = _step5_mode_window(snapshot, mode)
    _write_audit_log(snapshot, mode, final)
    return final


def calibrate(log_path: str | None = None) -> dict[str, Any]:
    """Walk audit log, return per-threshold fire counts + tuning hints.

    Seeds with ALL_TRIGGER_NAMES so never-fired thresholds appear with
    count=0 + 'never fired' hint (spec gap #8)."""
    path = log_path or AUDIT_LOG_PATH
    fire_count: dict[str, int] = {t: 0 for t in ALL_TRIGGER_NAMES}
    total = 0
    unique_snapshots: set[str] = set()
    if os.path.exists(path):
        with open(path) as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                total += 1
                snap_h = entry.get("snapshot_hash", "")
                if snap_h:
                    unique_snapshots.add(snap_h)
                t = entry.get("triggered_threshold", "unknown")
                fire_count[t] = fire_count.get(t, 0) + 1
    tuning_hints = []
    duplicate_count = total - len(unique_snapshots) if unique_snapshots else 0
    if duplicate_count > 0:
        tuning_hints.append(
            f"{duplicate_count} duplicate-snapshot decisions detected — "
            "orchestrator may be calling decide() multiple times on the same input"
        )
    for t, c in fire_count.items():
        pct = c / total if total else 0
        if c == 0 and total > 10:
            tuning_hints.append(
                f"threshold {t!r} NEVER FIRED in {total} decisions — "
                "consider tightening (raise the bar) or removing entirely"
            )
        elif pct > 0.5 and t not in ("mode_window_morning", "mode_window_eod"):
            tuning_hints.append(
                f"threshold {t!r} fires {pct * 100:.0f}% — consider loosening"
            )
    return {
        "total_decisions": total,
        "unique_snapshot_count": len(unique_snapshots) if unique_snapshots else None,
        "per_threshold_fire_count": fire_count,
        "tuning_hints": tuning_hints,
    }


def _cli() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Entry timing decision tree")
    sub = parser.add_subparsers(dest="cmd", required=True)

    decide_p = sub.add_parser(
        "decide", help="Run decision tree on a snapshot JSON file"
    )
    decide_p.add_argument("--snapshot", required=True, help="Path to snapshot JSON")
    decide_p.add_argument(
        "--mode",
        required=True,
        choices=["csp", "rut_calendar", "rut_protective", "rut_aggressive"],
    )

    cal_p = sub.add_parser("calibrate", help="Aggregate audit log thresholds")
    cal_p.add_argument("--log", default=None)

    args = parser.parse_args()
    if args.cmd == "decide":
        with open(args.snapshot) as f:
            snap = json.load(f)
        out = decide(snap, mode=args.mode)
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.cmd == "calibrate":
        stats = calibrate(log_path=args.log)
        json.dump(stats, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    _cli()
