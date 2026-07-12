# Flywheel Ops & Doc Coherence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the flywheel's broken automation legs (cron alerting, CI tests) and eliminate the 8 documented doc/code contradictions, per `docs/audits/2026-07-13-gap-audit.md` P0+P1.

**Architecture:** Three independent mechanical fixes (failure alerting in the daily scan, a pytest+ruff CI job, repo hygiene) plus one doc-coherence sweep. No new abstractions; every change is the minimum diff.

**Tech Stack:** Python 3.13 / uv / pytest / GitHub Actions.

## Global Constraints

- Never commit without explicit user request; branch + PR before merging to main (global CLAUDE.md).
- One PR for this whole plan (it is one topic: flywheel ops repair).
- `uv` exclusively — never bare python/pip.
- Failure alerts must email even when the routine report is suppressed — that is their entire purpose (the live cron runs `--no-email`).

---

### Task 1: Failure alerting in the daily scan

The cron job has died silently 45 times (`~/.config/option-wizard/daily.log`); last run crashed on `httpx.ReadTimeout` in `XenonClient._get("/portfolio")` with no alert.

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/manage_positions.py:263-315` (the `try/finally` in `main()`)
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/email_sender.py` (add `send_failure_alert`)
- Test: `tests/test_manage_positions_failure_alert.py` (create)

**Interfaces:**
- Consumes: `email_sender.load_credentials()` / `build_email_message()` / `send()` (existing internals, `email_sender.py:27-113`).
- Produces: `email_sender.send_failure_alert(body: str, to_addr: str = DEFAULT_RECIPIENT) -> bool` with its own 🔴 subject — a failure alert must NOT reuse `send_daily_scan`, whose subject for `rows=[]` is "no positions, no action" (trader would ignore it). `main()` returns 1 on unhandled scan failure (was: raised), emails the traceback regardless of `--no-email`.

- [ ] **Step 1: Write the failing test**

```python
"""Failure-alert path: any unhandled exception inside the scan must
(a) return exit code 1, (b) email the traceback even under --no-email."""

import scripts.manage_positions as mp


class _BoomClient:
    def __init__(self, *a, **k):
        pass

    def ib_portfolio(self):
        raise RuntimeError("xenon down (simulated)")


def test_scan_failure_emails_traceback_and_exits_1(monkeypatch, tmp_path):
    sent = {}

    def fake_alert(body):
        sent["body"] = body
        return True

    monkeypatch.setattr(mp, "XenonClient", _BoomClient)
    monkeypatch.setattr(mp, "LOCK_PATH", tmp_path / "test.lock")
    import scripts.email_sender as es

    monkeypatch.setattr(es, "send_failure_alert", fake_alert)

    rc = mp.main(["--no-email"])

    assert rc == 1
    assert "RuntimeError: xenon down (simulated)" in sent["body"]


def test_failure_alert_subject_is_not_the_no_action_subject():
    from scripts.email_sender import build_failure_message

    msg = build_failure_message("to@x.com", "from@x.com", "Traceback ...")
    assert "FAILED" in msg["Subject"]
    assert "no action" not in msg["Subject"]


def test_clean_run_unaffected(monkeypatch, tmp_path):
    # audit-only happy path with an empty book must still return 0
    class _EmptyClient:
        def __init__(self, *a, **k):
            pass

        def ib_portfolio(self):
            # Real xenon /portfolio shape (see tests/test_xenon_normalize.py
            # IB_PORTFOLIO fixture): account_summary key is "cash", positions
            # is a list of ticker dicts with legs.
            return {"positions": [], "account_summary": {"cash": 0.0}}

    monkeypatch.setattr(mp, "XenonClient", _EmptyClient)
    monkeypatch.setattr(mp, "LOCK_PATH", tmp_path / "test.lock")
    rc = mp.main(["--audit-only", "--no-email"])
    assert rc == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_manage_positions_failure_alert.py -v`
Expected: `test_scan_failure_emails_traceback_and_exits_1` FAILS (the RuntimeError propagates out of `main()` instead of returning 1).

- [ ] **Step 3: Implement — new email function + except branch**

3a. In `email_sender.py`, add after `send_daily_scan` (reuses `load_credentials`/`send`; a
dedicated subject because `build_email_message(rows=[])` would title the alert
"no positions, no action"):

```python
def build_failure_message(to_addr: str, from_addr: str, body: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"[option-wizard]🔴 {datetime.utcnow().date().isoformat()} — DAILY SCAN FAILED"
    )
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain", "utf-8"))
    return msg


def send_failure_alert(body: str, to_addr: str = DEFAULT_RECIPIENT) -> bool:
    """Page the trader when the daily scan itself crashes. 45 silent
    tracebacks in daily.log preceded this (2026-07-13 gap audit P0)."""
    try:
        creds = load_credentials()
    except RuntimeError as e:
        _log_error(str(e))
        return False
    msg = build_failure_message(to_addr, creds["sender"], body)
    return send(msg, creds["password"], retries=1)
```

3b. In `manage_positions.py`, the current structure is `try: ... finally: _release_lock()`. Insert an `except` between them:

```python
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
```

Import style note: the test monkeypatches `scripts.email_sender.send_failure_alert`, so
the implementation must call it as `email_sender.send_failure_alert(...)` (module
attribute at call time), NOT `from scripts.email_sender import send_failure_alert`
(binds too early for the monkeypatch).

- [ ] **Step 4: Verify email credentials actually exist (checked 2026-07-13: they DON'T)**

`~/.config/option-wizard/gmail.json` is absent and `.env` has no `GMAIL_APP_PASSWORD`/`GMAIL_SENDER_ADDRESS` — without them `send_failure_alert` silently returns False and this whole fix is a no-op that logs to `~/.config/option-wizard/email-errors.log`. Set up per `docs/setup/gmail-app-password.md`, then prove delivery end-to-end:

```bash
.venv/bin/python -c "from scripts.email_sender import send_test; print(send_test())"
```

Expected: `True` and a real email in the inbox. If the trader declines to configure Gmail, say so in the PR body — the alert then only reaches the error log, which nobody watches (that's the current failure mode, unchanged).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_manage_positions_failure_alert.py tests/test_manage_positions.py -v` (second file if it exists; `ls tests/ | grep manage` first)
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/manage_positions.py plugins/option-wizard/skills/option-wizard/scripts/email_sender.py tests/test_manage_positions_failure_alert.py
git commit -m "fix(scan): email traceback on scan failure instead of dying silently"
```

---

### Task 2: CI runs the test suite

CI today is skill-lint only — 491 tests and ruff never run on PR.

**Files:**
- Modify: `.github/workflows/skill-lint.yml`

**Interfaces:**
- Consumes: existing `pyproject.toml` dev extras (pytest, ruff), `uv.lock` (committed in Task 3).
- **Execution order is 1 → 3 → 2 → 4** (Task 3 commits `uv.lock` before this CI task lands, so `uv sync` on CI resolves against the pinned lockfile from its first run).

- [ ] **Step 1: Add the tests job**

Append to the existing workflow (keep the `skill-lint` job untouched):

```yaml
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.13"
      - run: uv sync --all-extras
      - run: uv run ruff check .
      - run: uv run pytest tests/ -q
```

Integration tests self-skip without `XENON_KEY`/`UW_API_KEY`/`GMAIL_APP_PASSWORD` — no secrets needed in CI.

- [ ] **Step 2: Verify locally**

Run: `uv sync --all-extras && uv run ruff check . && uv run pytest tests/ -q`
Expected: ruff clean; `475 passed, 21 skipped` (± the new Task 1 tests).

- [ ] **Step 3: Commit, then verify on the PR**

```bash
git add .github/workflows/skill-lint.yml
git commit -m "ci: run pytest + ruff on every PR"
```

After the branch is pushed and the PR opened, confirm the `tests` job appears and passes before merge (never merge before CI is green).

---

### Task 3: Repo hygiene 三件套

**Files:**
- Add: `uv.lock` (already exists untracked, 417 lines, matches pyproject)
- Modify: `AGENTS.md` (untracked; missing hard rules 9–10 that CLAUDE.md has)
- Delete from this repo: `docs/superpowers/plans/2026-07-06-signal-lab.md` (belongs to `~/projects/signal-lab`)

- [ ] **Step 1: Sync AGENTS.md from CLAUDE.md**

Diff the two files: `diff AGENTS.md CLAUDE.md`. Port the missing hard-rule summaries 9 (复盘 source separation) and 10 (decision doctrine) from `CLAUDE.md` into `AGENTS.md`'s hard-rules section verbatim, keeping AGENTS.md's Codex-specific framing otherwise intact.

- [ ] **Step 2: Move the signal-lab plan to its own repo**

```bash
mkdir -p ~/projects/signal-lab/docs/superpowers/plans
git -C ~/projects/signal-lab status   # confirm it's a repo; if dirty, just move the file, don't commit there
mv docs/superpowers/plans/2026-07-06-signal-lab.md ~/projects/signal-lab/docs/superpowers/plans/
```

- [ ] **Step 3: Track the files and commit**

```bash
git add uv.lock AGENTS.md
git commit -m "chore: track uv.lock, sync AGENTS.md hard rules 9-10, relocate signal-lab plan"
```

---

### Task 4: Doc-coherence sweep (8 items)

Rules docs are runtime code for an LLM-orchestrated skill — stale text = stale behavior. All paths relative to `plugins/option-wizard/skills/option-wizard/`.

**Files:**
- Modify: `SKILL.md`, `references/analysis-runbook.md`, `references/workflows-overview.md`, `references/index.md`, `references/macro-hedge-convexity.md`, `scripts/fair_aq_dq.py`, repo-root `README.md`, repo-root `CHANGELOG.md`

- [ ] **Step 1: Apply the eight edits**

| # | File / anchor | Change |
|---|---|---|
| 1 | `SKILL.md:168` | Delete the parenthetical "(with script false-positive callouts where the $20 strike-width limit misfires)" — bug fixed in PR #29; audit verdict line needs no callout instruction. Also fix the same instruction in `references/workflows-overview.md:113`. |
| 2 | `references/analysis-runbook.md:17-27, 40, 56-74` | L0 account state: replace "IB MCP" primary with "xenon `/portfolio` + `/futu/portfolio` (IB MCP fallback)" and `IBClient.get_positions()` examples with `XenonClient.ib_portfolio()` — mirror the wording already in `workflows-overview.md:46`. |
| 3 | root `README.md` §Data sources + §bring-your-own-broker | Insert xenon as the primary account-state/live-greeks source (copy the four-source invariant sentence from root `CLAUDE.md` §Data source order); demote IB MCP to fallback. Add one line that AQ/DQ framework exists. |
| 4 | `SKILL.md:139`, `references/workflows-overview.md:3,11`, `references/index.md:35` | Unify workflow count: "the 7 workflows (W1 ticker / W2a macro hedge / W2b index premium / W3 positions / W4 FCN / W5 AQ-DQ / W6 复盘)". |
| 5 | `SKILL.md:78`, `references/workflows-overview.md:153`, `references/index.md:28` | "6 refusal red lines" → "7 refusal red lines (R0–R6)" (three files — index.md's aq-dq row has the same stale count). |
| 6 | `scripts/fair_aq_dq.py:259` | Comment "Public API (stubs — implemented in subsequent tasks)" → "Public API". |
| 7 | root `CHANGELOG.md` | Add `[0.3.0] — 2026-07-13` section: xenon migration, macro-hedge convexity, index premium selling, OKF alignment, decision doctrine v1 + U1-U6, audit bucket-check fix, pitfalls 06/07 (one line each, from `git log --oneline` since 2026-06-23). Bump BOTH manifests to `0.3.0`: `plugins/option-wizard/plugin.json` AND `pyproject.toml:3` (they must never diverge — verify with `grep -h '"version"\|^version' plugins/option-wizard/plugin.json pyproject.toml`). |
| 8 | `references/macro-hedge-convexity.md:304-311` | Open-questions table: mark HY OAS ingestion DONE (`_clients/fred.py::hy_oas_signal`, wired via `add_fred_signals_to_snapshot`); leave the genuinely-open rows (VIX inversion-regime calibration, 2015/2011 re-run, bid-ask drag) untouched. |

- [ ] **Step 2: Verify no stale references remain**

Run: `grep -rn "\$20 strike-width\|stubs — implemented\|6 refusal\|the 4 workflows\|the 6 distinct" plugins/ README.md`
Expected: zero matches.

Run: `.venv/bin/pytest tests/ -q` — expected: no regressions (edit #6 touches a .py comment only).

- [ ] **Step 3: Commit**

```bash
git add -A plugins README.md CHANGELOG.md
git commit -m "docs: eliminate 8 doc/code contradictions from 2026-07-13 gap audit"
```

---

## Execution wrap-up

Branch: `fix/flywheel-ops-and-docs`. One PR containing Tasks 1–4; body links `docs/audits/2026-07-13-gap-audit.md`. Merge only when the new `tests` CI job is green. After merge, manually verify the next 9:30 ET cron run writes a clean entry to `~/.config/option-wizard/daily.log` (or emails a failure — either proves the alerting works).
