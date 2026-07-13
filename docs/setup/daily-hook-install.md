# Daily Position Scan Hook

The option-wizard daily run is delivered two ways. The cron job is the
authoritative schedule (runs even when Claude Code is closed). The
SessionStart hook is an optional convenience for trading-day mornings
when the trader is opening a session anyway.

Both paths are protected by the lockfile at
`~/.config/option-wizard/manage_positions.lock` (see Task 5.2 in the
implementation plan) so they cannot race.

## Canonical path: cron job

The cron entry is the authoritative daily run.

```bash
crontab -e
# 9:30 AM US/Eastern, Monday-Friday. macOS cron honors TZ:
TZ=America/New_York
30 9 * * 1-5  cd /Users/chenxi/projects/option-wizard && .venv/bin/python -m scripts.manage_positions  >> ~/.config/option-wizard/daily.log 2>&1
```

DST handling: `TZ=America/New_York` automatically follows
daylight-saving transitions so the run stays at 9:30 ET year-round.
Verify with `crontab -l` and check `~/.config/option-wizard/daily.log`
the next trading morning.

## Optional path: Claude Code SessionStart hook

Triggers a fresh run when you open a Claude Code session, but only if
the cron run for the day has not happened (lockfile + a short
throttle).

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "command": "/Users/chenxi/projects/option-wizard/.venv/bin/python -m scripts.manage_positions --no-email",
        "throttle_minutes": 960
      }
    ]
  }
}
```

If your `settings.json` already has a `hooks` block, merge the
`SessionStart` array. The `--no-email` flag is recommended for the
hook so you don't get a duplicate email on the days both cron and
SessionStart fire (the lockfile prevents both from doing real work
but the email arm runs on the path that wins).

## Disabling

Set `OPTION_WIZARD_SKIP_DAILY=1` in the shell environment to skip the
hook for one session. To disable cron permanently, comment out the
crontab line.

## Verifying it works

Day-1 checklist:

- `crontab -l` shows the entry above.
- Wait for the next 9:30am ET (or run manually:
  `cd /Users/chenxi/projects/option-wizard && .venv/bin/python -m scripts.manage_positions --no-email`).
- Check the log: `tail ~/.config/option-wizard/daily.log` — should
  show today's scan output.
- If `--no-email` was omitted, an email should arrive at
  chenxi.li08@outlook.com within ~1 minute.
- Lockfile: `ls -la ~/.config/option-wizard/manage_positions.lock` —
  should be absent after a successful run. If present and older than
  10 minutes, a stuck process; remove manually.

## Troubleshooting

- No log appears → cron PATH issue. Try absolute path to the venv
  Python: `/Users/chenxi/projects/option-wizard/.venv/bin/python`.
- Connection refused → IB Gateway not running. Start IB Gateway in
  live mode (port 4001) before the daily window.
- Email not arriving → check
  `~/.config/option-wizard/email-errors.log` and re-run
  `docs/setup/gmail-app-password.md` setup steps.

## Second cron job: daily regime snapshot

`scripts/regime_snapshot.py` (capability audit R1) persists a daily regime
state vector — IV rank per ticker, term-structure regime label, GEX levels,
market-tide EOD, HY OAS — to
`plugins/option-wizard/skills/option-wizard/references/private/market/regime-log.jsonl`
(gitignored). This is a separate cron entry from the 9:30 AM position scan
above: it runs after the 16:00 ET close so the day's IV rank / term
structure / GEX reads are final settle values, not an intraday snapshot.

```bash
crontab -e
# 16:35 ET (after close), Monday-Friday. Sourcing .env is required — UW_API_KEY
# / FRED_API_KEY live there, and UWClient()/FREDClient() raise RuntimeError
# without them.
TZ=America/New_York
35 16 * * 1-5  cd /Users/chenxi/projects/option-wizard && set -a && . ./.env && set +a && .venv/bin/python -m scripts.regime_snapshot >> /Users/chenxi/.config/option-wizard/regime.log 2>&1
```

Verify: `crontab -l` shows the entry; the next trading day after 16:35 ET,
`tail /Users/chenxi/.config/option-wizard/regime.log` shows a line like
`regime snapshot 2026-07-13 -> .../regime-log.jsonl (N gaps: [...])`, and the
JSONL log has a new line for that date. Gaps are expected and honest — e.g.
FRED (HY OAS) is a known-flaky dependency from this network; the script
still writes the rest of the snapshot and records the miss in `gaps` rather
than failing the whole run.

## Third cron job: weekly automated call grading

`scripts/grade_calls.py` (capability audit R3) closes the 46/52-ungraded
feedback hole by running Layer A (archive call) grading unattended, weekly.
It extracts calls over a 70-day maturity lookback (so T+21/T+45 verdicts get
written once they mature, not just calls made in the last 7 days), fetches
real spot history from xenon `/historical/bars` (`daily_closes`) and IV-rank
history from the `regime_snapshot.py` log
(`references/private/market/regime-log.jsonl`), writes verdicts back to the
source archive files, and emits pitfall drafts for WRONG calls. Layer B
(broker trade markout) intentionally stays with the interactive 复盘 flow —
this job never touches broker state.

Run it after `regime_snapshot.py`'s Friday close so the week's IV rank /
term structure reads are already in the log:

```bash
crontab -e
# 18:00 ET, Fridays only. Sourcing .env is required — XENON_KEY/XENON_BASE
# live there, and XenonClient() raises RuntimeError without them.
TZ=America/New_York
0 18 * * 5  cd /Users/chenxi/projects/option-wizard && set -a && . ./.env && set +a && .venv/bin/python -m scripts.grade_calls --window weekly >> /Users/chenxi/.config/option-wizard/grade.log 2>&1
```

Verify: `crontab -l` shows the entry; the following Friday evening,
`tail /Users/chenxi/.config/option-wizard/grade.log` shows a rendered 复盘
report with real CORRECT/WRONG/NEUTRAL/UNKNOWN verdicts (not all UNKNOWN —
xenon `daily_closes` is live per Task 2) and a `## Grading data gaps`
section for any ticker `daily_closes` couldn't resolve. RUT is a known,
permanent gap (xenon `/historical/bars` has no working exchange route for
it) and will always appear there — that's expected, not a bug. Dry-run first
with `--dry-run` (no write-back, no drafts) before trusting it unattended.
