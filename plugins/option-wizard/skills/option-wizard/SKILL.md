---
name: option-wizard
description: >
  Personal US-equity options trading, private bank FCN/ELN evaluation, and IB
  execution. Use for FCN coupon negotiation ("PB quoted me X% on Y"),
  vol-regime-based option structure picks (covered call, sell put, defined-risk
  spreads, jade lizard, collar), SPX macro hedge sizing, position management
  (take-profit/stop-loss brackets, 21 DTE review, roll suggestions), and
  IB order placement. Data: Unusual Whales (IV rank, GEX, skew, term
  structure, max pain, dark pool), TradingView via finance-data-providers
  reader (spot, charts, technicals, news), IB MCP (positions, balances,
  order instructions). Triggers on ticker mentions in trading context,
  FCN/ELN quote review, "should I sell put on X", "covered call on Y",
  "is this FCN deal good", "macro hedge", "check my positions", "place
  this order". Chinese response with English technical terms. Defined-risk
  only — never naked short calls, never margin-leveraged short puts.
---

# option-wizard

Domain knowledge lives in `references/`; numeric work in `scripts/`. See
§"When to read which file" below for the situation → files map (LLM uses
this to pick what to load); see §"How to invoke scripts" for the script
incantations.

## Hard rules (apply to every response)

1. Defined-risk only. Refuse naked short calls and margin-leveraged short puts; explain why when refusing.
2. UW first for numeric metrics: IV rank, RV, skew, IV term structure, max pain, GEX by strike, greeks by strike, dark pool, interpolated IV. Do not recompute these client-side. Compute only what UW lacks (gamma flip from GEX, put/call walls from GEX, VRP from IV−RV, FCN fair coupon).
3. Every order shows the pre-flight (legs, mid price, net debit/credit, max loss, max gain, breakeven, margin, P/L matrix at expiry across spot −20 / −10 / −5 / 0 / +5 / +10 / +20 percent, account verification, UW regime check, liquidity check, catalyst clock) before submission. Exactly one YES/NO question. YES → submit via `ib_insync.placeOrder` (IB option orders) or `create_order_instruction` (IB stock drafts for tap-to-approve); Futu orders have no auto-submit path — flag "manual entry in Moo Moo / OpenD trade" in the preflight. Anything else → abort. Live-account preflight is the safety boundary — do **not** propose paper-account (IB TWS paper instance) tests, and do not treat paper-account criteria as a blocker.
4. Any short-premium position at 21 DTE surfaces as an entry in the consolidated **Action items** section at the end of the book review (see §"Book-review output structure"). It is **not** a mid-flow blocking YES/NO prompt — the trader picks close / roll / hold-and-accept-gamma from the action-items menu, and only then does the full hard-rule-#3 preflight expand.
5. FCN does not go through IB. FCN output is the 8-item PB checklist, a 70/75/80/85% strike ladder, a fair vs quoted verdict, and a bilingual counter-offer email (Chinese first, English second).
6. Bracket order defaults: take-profit at 50% of max gain, stop-loss at 2× credit received (100% of max loss for spreads). Per-order override allowed.

## Triggers

For any ticker analysis ("分析 <TICKER>" / "evaluate <ticker> for <structure>"),
follow `references/analysis-runbook.md` end-to-end. The runbook lists the
data source per layer, the compute step, and the decision output; do NOT
skip a layer silently — report any data-source gap explicitly.

Chinese:
- "分析 <TICKER>"
- "PB 给我报了 <TICKER> 的 FCN, X% coupon"
- "<TICKER> 怎么做 sell put / covered call / jade lizard"
- "我账户里这些仓位有没有问题"
- "SPX 大盘对冲"
- "<TICKER> 现在该 close 还是 roll"

English:
- "negotiate fcn quote"
- "evaluate <ticker> for <structure>"
- "size spx hedge"
- "review positions"

## When to read which file

Routing table — match the trader's request to the files to load. Lazy-load
discipline: read only the rows that fire for the current request, not the
entire references directory. The full 8-layer recipe in
`references/analysis-runbook.md` is the spine; the other rows are entry
points into specific layers without re-reading the whole runbook.

| Situation | Files to load |
|---|---|
| Full ticker analysis ("分析 <TICKER>", "evaluate <ticker> for <structure>") | `references/analysis-runbook.md` end-to-end — every layer in order, with the per-layer data source and decision output |
| Picking structure once vol regime + direction are known | `references/strategies.md` (regime × structure matrix); apply §"Strong bullish conviction veto" before recommending jade lizard / iron condor / calendar |
| **About to recommend jade lizard / iron condor / calendar / diagonal** | **MANDATORY**: `references/strategies.md` §"Strong bullish conviction veto" — run the 4-signal check FIRST. If ≥3 fire, refuse and recommend long call / bull put spread / risk reversal / CSP instead |
| Computing gamma flip / put wall / call wall from UW GEX | `references/gamma-framework.md`; invoke `scripts.gex_levels::compute_levels_per_expiry` with `call_wall_definition='oi_cluster'` for short-dated trades (aggregate `compute_levels` is misleading for short windows — see runbook Layer 1) |
| Labelling vol regime (RICH / NEUTRAL / CHEAP) | `scripts.vrp::compute_vrp` — IV − RV with ±5pp thresholds |
| Reading TV chart, tape, news, catalyst-clock validation | `references/price-action-framework.md`; `references/data-sources.md` for TV setup gotchas (opencli ≥ 1.8.0, port 9222 collision with chrome-devtools-mcp, stale TV process recovery) |
| FCN / ELN quote evaluation ("PB 给我报了 X% coupon on Y") | `references/fcn-framework.md`; `scripts.fair_coupon::analyze_fcn`. Output is the 8-item PB checklist + 70/75/80/85% strike ladder + bilingual counter-offer email — do NOT route through IB (hard rule #5) |
| SPX macro hedge sizing | `scripts.macro_hedge::build_macro_hedge`. Respect the 1.5% NLV annualized cost cap (hard rule #5). Trigger heuristics in `references/strategies.md` §"Macro hedge trigger heuristics" |
| Position book review ("我账户里这些仓位有没有问题") | Pull **both brokers**: IB MCP first, then Futu via `cd ~/projects/portfolio-analyser && npx tsx src/cli.ts ft --range 1y` (OpenD on :11111) — read just the positions block from the JSON, skip the 3-persona HTML enrichment. Translate Futu positions to IB-shape (`contract_description` / `position` / `market_price`) before feeding into `scripts.defined_risk_audit::audit_book` and `scripts.manage_positions` (orchestrator CLI: `.venv/bin/python -m scripts.manage_positions --audit-only --no-email`). Output follows §"Book-review output structure" — action items consolidated at the END of the report, not drilled into mid-flow. |
| 21 DTE review on short-premium positions | `scripts.evaluate_position`; hard rule #4 — surfaces in the Action items section at the end of the book review (close / roll / hold-and-accept-gamma). Trader picks from the menu; only then expand into hard-rule-#3 preflight. |
| Pre-submission preflight + YES/NO gate | `references/execution.md`; `scripts.ib_order::build_preflight`. Hard rule #3 — must show legs + mid + max loss + max gain + breakeven + margin + P/L matrix (spot ±5/10/20%) + account verification + UW regime check + liquidity + catalyst clock before exactly one YES/NO question |
| Honest gap reporting when a data source is unreachable | `references/analysis-runbook.md` §"Honest reporting of gaps" — list every missing layer under "What this analysis is missing" rather than fabricating signals |
| Pattern match against a prior FCN deal | `references/ticker/orcl-2026-06-fcn.md` (public, anonymized) |
| Pattern match against a prior personal trade / analysis | `references/ticker/private/*.md` — trader's local archive (gitignored). List the directory and pick by date / event / ticker |
| Capturing a new pitfall from a closed trade | `references/pitfalls/_template.md` → copy to `NN-slug.md`; add row to `references/pitfalls/README.md` (index currently empty — backfill from trade history is tracked as H1). Strip all account-specific numbers before promoting from `private/` |

## Book-review output structure

Every position book review follows the same four-stage layout. **Do not interrupt stages 1-3 to demand a per-position YES/NO** — that pattern produced a session-long detour on the 2026-06-03 Futu review and is no longer the workflow.

1. **Data pull** — both brokers (IB MCP + Futu via portfolio-analyser CLI). Report which broker(s) succeeded and any pull-time data gaps (e.g., cash balance not in Futu report).
2. **Book-level analysis** — concentration (abs MV % and Δ-1 notional vs NLV), Greeks (net Δ / Γ / Θ / V, plus Δ-1 single-name bars), every leg laid out, defined-risk audit verdict (with script false-positive callouts where the $20 strike-width limit misfires), 22-45 DTE watchlist, catalyst clock, data quality flags.
3. **No mid-flow decision prompts.** 21 DTE short-premium positions, approaching-21-DTE positions, ER catalysts, large shorts, data anomalies — all of these are *observed* in stage 2 but **not** acted on yet.
4. **One consolidated "Action items" block at the END.** Grouped into Position-level decisions (P1, P2, …), Data quality (D1, D2, …), Book-level risks (R1, R2, …), Infrastructure (I1, I2, …). Each item is one line with the choice menu inline (close/roll/hold, verify, fix, etc.). Include trigger phrases ("P1 submit", "D2 verify", "R3 fix") so the trader can pick fast. **Wait** for the trader to pick — then expand the chosen item(s) into preflight / drill-down / fix in the next turn.

Two reinforcing rules under stage 4:
- **AT THE END** — never interrupt the broader analysis with a single position's YES/NO.
- **ALL TOGETHER** — never drill into action items one at a time (P1 → wait → P2 → wait …). Present the full menu; trader picks one or many.

The full hard-rule-#3 preflight (legs, mids, P/L matrix, UW regime, liquidity, brackets, gaps, archive write) only runs when the trader explicitly picks an item from the menu and says "build it" / "submit" / "show me the roll" / "drill into P1". Hard rules are not weakened — they just don't auto-trigger from the book review alone.

Edge case — structurally dangerous position (naked short call discovered, undefined risk found, gamma blow-up imminent): surface as URGENT at the top of the Action items block. Still no auto-preflight; trader still picks.

## Reporting & archive

**After producing any substantive analysis report, auto-write to `references/ticker/private/<slug>-YYYY-MM-DD-<event>.md`** — without asking, before responding-done. This is the default for:

- Full ticker analysis (`分析 <TICKER>`) — even if conclusion is WAIT / no trade
- Position book review / `持仓 review`
- FCN/ELN evaluation with concrete deal numbers
- Macro / SPX hedge decision
- Pre-flight + YES/NO order trace (regardless of YES, NO, or abort)
- Roll / close decision on existing positions

The `private/` subdirectory is **gitignored** at project root; it's the trader's personal trade journal containing NLV / positions / fills. The public `references/ticker/` tree only holds anonymized framework-teaching case studies (e.g., `orcl-2026-06-fcn.md`).

**File format** (trade-skills frontmatter convention):
```yaml
---
ticker: <SYMBOL or comma-list for macro>
event: <one-line context>
date: YYYY-MM-DD
status: open | closed | analysis-only | decision-pending | pending-<reason>
result: profit | loss | breakeven | pending
structures: [list]
tags: [list]
---
```

Body must capture: TL;DR, Data snapshot (point-in-time, with sources), Analysis, Decision + reasoning, Gaps in data, empty **Outcome / Lesson** section for audit fill-in.

**Audit cadence**: trader (or skill on re-invocation against same ticker) revisits each `private/` file at its named checkpoint (next ER / expiry / 30d for macro) and fills in the outcome section. Lessons that generalize get promoted to `references/pitfalls/NN-slug.md` (account-stripped).

**Don't ask permission per report — auto-archive is the default behavior.** The single exception: if user explicitly says "don't save this" or "don't archive", skip and confirm.

## How to invoke scripts

The skill prompt orchestrates the LLM. Numeric work is delegated to the Python modules under `scripts/`. Only `scripts.manage_positions` has a CLI — every other module exposes pure Python functions that you call via `python -c`, passing the UW data you already fetched as a Python literal.

Daily position scan (orchestrator entrypoint, has argparse):

```bash
.venv/bin/python -m scripts.manage_positions          # full scan + email
.venv/bin/python -m scripts.manage_positions --audit-only --no-email
```

The other scripts are imported as functions:

```bash
# Gamma flip + put/call walls from UW GEX-by-strike output
.venv/bin/python -c '
import json, sys
from scripts.gex_levels import compute_levels
raw = json.load(open(sys.argv[1]))
rows = [{"strike": float(r["strike"]),
         "gex": float(r["call_gex"]) + float(r["put_gex"])}
        for r in raw["result"]]
print(compute_levels(rows, spot=423.74))
' /path/to/uw_gex.json

# VRP regime label
.venv/bin/python -c 'from scripts.vrp import compute_vrp; print(compute_vrp(0.50, 0.40, with_label=True))'

# FCN ladder analysis
.venv/bin/python -c '
from scripts.fair_coupon import analyze_fcn
snap = {"spot": 200.0, "iv": 0.35, "rv": 0.30, "iv_rank": 55,
        "skew_25d": 0.04, "max_drawdown_5y": -0.45,
        "gex_levels": {"gamma_flip": 195.0, "put_wall": 180.0, "call_wall": 220.0}}
r = analyze_fcn("ORCL", strike_pcts=(0.70, 0.75, 0.80, 0.85),
                tenor_months=6, observation_months=3,
                pb_quoted_coupon=0.12, snapshot=snap)
print(r["verdict"], "at", r["anchor_strike_pct"])
'

# SPX macro hedge sizing
.venv/bin/python -c '
from scripts.macro_hedge import build_macro_hedge
print(build_macro_hedge(portfolio_notional=1_000_000, hedge_horizon_days=60,
                        scenario="deep_correction_-10", structure="put_spread",
                        snapshot={"spot": 6000.0, "iv_atm_90d": 0.18}))
'

# IB order preflight (no submission)
.venv/bin/python -c '
from scripts.ib_order import build_preflight
# legs = [{"action": "SELL", "strike": 420, "right": "P", ...}, ...]
# preflight = build_preflight(structure="bull_put_spread", legs=legs, ...)
'

# Defined-risk audit (standalone)
.venv/bin/python -c '
from scripts.defined_risk_audit import audit_book, format_audit_findings
findings = audit_book(positions=[...], cash_balance=38177)
print(format_audit_findings(findings))
'
```

All function signatures accept the exact UW snapshot/positions shapes documented in `references/data-sources.md`. The orchestrator is responsible for fetching UW data first and passing it in — scripts do not call UW themselves (kept pure for testability).
