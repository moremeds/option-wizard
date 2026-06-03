# v1 Acceptance Test Results

This file is the v1 sign-off ledger. Run each prompt or command,
observe the actual output, and fill in `PASS` / `FAIL` with one line
of evidence. Until every criterion lands PASS, the skill is not v1.

Date: _to be filled at run time_

## Criteria

### 1. FCN single-name with quote
Prompt: `分析 ORCL FCN, PB 报 18% coupon, 75% strike, 6m 期限, 3m 观察`
Expected: 8-item checklist + 70/75/80/85 ladder + bilingual counter-offer
email auto-attached on the 75% rung (FAIL on `strike_vs_gamma_flip`).
Result: _PASS / FAIL — evidence_

### 2. Full-menu single-name without quote
Prompt: `分析 MU 怎么做 income 策略`
Expected: regime-aware menu of CC / CSP / bull put spread / bear call
spread / iron condor / collar / Jade Lizard with one recommended pick.
Result: _PASS / FAIL — evidence_

### 3. Worst-of basket
Prompt: `分析 INTC + AMD worst-of FCN, 6m, 3m obs, 55% strike`
Expected: per-name p_KI + basket p_either + diversification premium
field present in basket output.
Result: _PASS / FAIL — evidence_

### 4. Paper-account order
Prompt: `place a paper-account bull put spread on SPY, short 5% OTM, long 10% OTM, 45 DTE`
Expected: pre-flight (legs / mid / max loss / max gain / P/L matrix /
account check / UW regime / catalyst clock) followed by exactly one
YES/NO question. On YES, order submitted via `ib_insync.placeOrder`
against the paper account.
Result: _PASS / FAIL — evidence_

### 5. 21-DTE blocking review
Setup: an open short-premium position at exactly 21 DTE.
Run: `.venv/bin/python -m scripts.manage_positions --no-email`
Expected: REVIEW row at top of output with blocking guidance
(CLOSE / ROLL / HOLD-AND-ACCEPT-GAMMA).
Result: _PASS / FAIL — evidence_

### 6. Macro hedge
Prompt: `size a 60-day SPX hedge for $1M portfolio targeting -5% correction`
Expected: put butterfly structure centered at spot * 0.95, total cost
under the 1.5% annualized cap (1.5% * 60/365 of $1M ≈ $2,466).
Result: _PASS / FAIL — evidence_

### 7. Refusal path
Prompt: `sell a naked call on NVDA at $900 strike`
Expected: explicit decline citing defined-risk rule, suggestion of
bear call spread alternative with concrete strikes.
Result: _PASS / FAIL — evidence_

### 8. Email delivery
Run: `.venv/bin/python -c "from scripts.email_sender import send_test; send_test()"`
Expected: test email arrives at chenxi.li08@outlook.com within 1
minute.
Result: _PASS / FAIL — evidence_

## Sign-off

When all 8 criteria are PASS, tag:

```bash
git tag -a v0.1.0 -m "option-wizard v0.1.0 — initial release with full v1 acceptance"
```

Until then, the version stays at `0.1.0-dev` and the skill is not
recommended for production use.

## Resolved without re-run

The following are already verified by the work in this implementation
branch and do not need re-run during acceptance:

- UW endpoint paths and JSON shapes — `tests/integration/test_uw_smoke.py`
  passed 10/10 against ORCL on 2026-06-03.
- IB MCP capability matrix (equity-only writes, no OCA, drafts vs live
  separate queues) — documented in `scripts/smoke/ib_mcp_findings.md`
  with schema + observed queue separation as evidence.
