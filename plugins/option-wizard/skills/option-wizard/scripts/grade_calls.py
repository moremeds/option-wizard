"""Weekly automated call grading — Layer A of 复盘, unattended.

Wires the live fetchers the retrospective CLI scaffold never had (audit R3):
spot_history from xenon daily bars, iv_rank_history from the regime log.
Layer B (broker trades) intentionally stays with the interactive 复盘 flow —
this runner grades CALLS, writes verdicts back to archives, and emits pitfall
drafts, so the loop closes even when the trader skips a week.

Cron (Friday evening, after regime_snapshot; same proven pattern — repo-root
cd + .env sourcing, TZ set crontab-wide):
  0 18 * * 5  cd /Users/chenxi/projects/option-wizard && set -a && . ./.env && set +a && .venv/bin/python -m scripts.grade_calls --window weekly >> /Users/chenxi/.config/option-wizard/grade.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from scripts._clients.xenon import XenonClient
from scripts.retrospective import (
    _default_archive_dir,
    _default_drafts_dir,
    extract_calls_from_archive,
    render_report,
    run_review,
    save_review_report,
)

INDEX_SEC_TYPES = {"SPX": "IND", "VIX": "IND", "NDX": "IND", "RUT": "IND"}

# ≈45 trading days + buffer — covers the longest MARKOUT_HORIZON so calls are
# re-scanned until their verdict horizon matures (see "Maturity window" above).
LOOKBACK_DAYS = 70


def _default_regime_log() -> Path:
    return _default_archive_dir() / "market" / "regime-log.jsonl"


def tickers_in_window(
    archive_dir: Path, start: date, end: date, *, include_archive: bool = False
) -> set[str]:
    calls, _ = extract_calls_from_archive(
        archive_dir, start, end, include_archive=include_archive
    )
    return {c.ticker for c in calls}


def iv_rank_history_from_regime_log(log_path: Path) -> dict[str, dict[date, float]]:
    hist: dict[str, dict[date, float]] = {}
    if not log_path.exists():
        return hist
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        snap = json.loads(line)
        d = date.fromisoformat(snap["date"])
        for t, row in (snap.get("iv_rank") or {}).items():
            r = row.get("iv_rank_1y")
            if r is not None:
                hist.setdefault(t, {})[d] = float(r)
    return hist


def build_spot_history(
    tickers: set[str],
) -> tuple[dict[str, dict[date, float]], list[str]]:
    """xenon daily bars per ticker; failures reported, never fabricated.

    `daily_closes` doesn't raise for an unsupported index route (e.g. RUT —
    xenon `/historical/bars` has no working exchange for it and returns
    `{"bars": []}`, "a documented gap, not an error" per
    `_clients/xenon.py:historical_bars`) — it just comes back empty. An
    empty result is therefore treated the same as an exception here: logged
    as a gap, never silently fed into `spot_history` where it would render
    every markout for that ticker as `n/a` with no explanation.
    """
    client = XenonClient()
    spot: dict[str, dict[date, float]] = {}
    failures: list[str] = []
    for t in sorted(tickers):
        try:
            closes = client.daily_closes(
                t, duration="3 M", sec_type=INDEX_SEC_TYPES.get(t, "STK")
            )
        except Exception as e:
            failures.append(f"{t}: {e}")
            continue
        if not closes:
            failures.append(f"{t}: no daily bars returned (unsupported index route?)")
            continue
        spot[t] = closes
    return spot, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Automated Layer-A call grading")
    parser.add_argument("--window", choices=["weekly", "monthly"], required=True)
    parser.add_argument("--today", type=str, default=None)
    parser.add_argument("--archive-dir", type=Path, default=_default_archive_dir())
    parser.add_argument("--regime-log", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="no write-back, no drafts, no report archive",
    )
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else date.today()

    # Maturity lookback, not the report window: extraction always spans
    # LOOKBACK_DAYS so T+21/T+45 verdicts get written once they mature.
    start = today - timedelta(days=LOOKBACK_DAYS)
    include_archive = True  # lookback crosses the 30-day cold-storage TTL
    tickers = tickers_in_window(
        args.archive_dir, start, today, include_archive=include_archive
    )
    spot_history, failures = build_spot_history(tickers)
    iv_hist = iv_rank_history_from_regime_log(args.regime_log or _default_regime_log())

    report = run_review(
        window=args.window,  # labels the report; extraction uses window_dates
        today=today,
        archive_dir=args.archive_dir,
        spot_history=spot_history,
        iv_rank_history=iv_hist or None,
        trades=[],  # Layer B stays interactive — see module docstring
        trade_sources=[],
        # run_review only writes drafts when drafts_dir is non-None
        # (retrospective.py — the `if generate_drafts and drafts_dir is not
        # None:` gate) — generate_drafts alone is not enough.
        drafts_dir=None if args.dry_run else _default_drafts_dir(),
        write_back=not args.dry_run,
        generate_drafts=not args.dry_run,
        include_archive=include_archive,
        window_dates=(start, today),
    )
    rendered = render_report(report)
    if failures:
        rendered += "\n\n## Grading data gaps\n\n" + "\n".join(
            f"- {f}" for f in failures
        )
    print(rendered)
    if not args.dry_run:
        path = save_review_report(report, rendered, base_dir=args.archive_dir)
        print(f"\n[graded report archived to {path}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
