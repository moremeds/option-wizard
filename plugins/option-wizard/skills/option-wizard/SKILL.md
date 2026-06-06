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
2. **Source discipline (3-source taxonomy).** Three sources, each canonical for non-overlapping core territory + overlapping zones where freshness picks the winner.

   **Canonical per source:**
   - **UW** — options-derivative metrics no one else serves: IV rank, skew, GEX by strike, max pain, RV, dark pool, flow, interpolated IV
   - **IB Gateway** — account state (positions / balances / orders / trades / margin); paid broker-feed real-time chain (mid / IV / greeks); `get_price_snapshot`
   - **TradingView** — spot, OHLCV, technical indicators (SMA / EMA / RSI / MACD / BBANDS / ATR / volume bars), news, alerts, watchlists, charts

   **Overlapping zones priority:**

   | Data point | Primary | Fallback | Why |
   |---|---|---|---|
   | Spot | TV | IB `get_price_snapshot` | TV intra-minute fresh + chart-verifiable; IB broker-feed authoritative for live-trade gating |
   | Option chain mid / IV / greeks | **IB** (live trade <60s decision) / **UW** (analytical context) | mutual fallback | IB seconds-fresh from broker feed; UW better for skew/term analytical context |
   | OHLCV historical | TV (chart context) | IB `get_price_history` (backtest precision) | — |

   **Forbidden:**
   - UW `get_extended_technical_indicator` / `get_ticker_indicator_series` for analysis (series lagged by weeks)
   - IB for IV rank / skew / GEX / max pain (IB doesn't compute these derivative metrics)

   **Rule of thumb:** if any of the three serves it directly, never recompute. Verdict / analysis output must carry `data_provenance` for every quoted metric so the trader can audit the source.

   **Skill-wide chain-mid path:** `scripts.fair_aq_dq`, `scripts.fair_coupon`, `scripts.macro_hedge` ALL accept an optional `chain` field on their snapshot input. When provided, listed-strike option mids are read directly from the chain (per workflow §2 source-selection: UW analytical default / IB live-trade) instead of recomputed via BSM. Output fields tag the source: `fair_coupon_source` ∈ {chain, model}, `pricing_source` ∈ {chain, mixed, bsm}, leg-level `mid_source` and `mid_provenance`. Orchestrator MUST pull a chain into the snapshot before calling these scripts when the trader is in live-trade or fair-value-comparison mode.
3. Every order shows the pre-flight (legs, mid price, net debit/credit, max loss, max gain, breakeven, margin, P/L matrix at expiry across spot −20 / −10 / −5 / 0 / +5 / +10 / +20 percent, account verification, UW regime check, liquidity check, catalyst clock) before submission. Exactly one YES/NO question. YES → submit via `ib_insync.placeOrder` (IB option orders) or `create_order_instruction` (IB stock drafts for tap-to-approve). Non-IB broker orders (any secondary broker configured in `private/trader-profile.md`) typically have no auto-submit path — flag "manual entry in the broker's trading app" in the preflight. Anything else → abort. Live-account preflight is the safety boundary — do **not** propose paper-account (IB TWS paper instance) tests, and do not treat paper-account criteria as a blocker.
4. Any short-premium position at 21 DTE surfaces as an entry in the consolidated **Action items** section at the end of the book review (see §"Book-review output structure"). It is **not** a mid-flow blocking YES/NO prompt — the trader picks close / roll / hold-and-accept-gamma from the action-items menu, and only then does the full hard-rule-#3 preflight expand.
5. **PB structured products (FCN / AQ / DQ): no IB ORDER ROUTING; IB MARKET DATA is allowed.** This is two separate concerns:
   - **Order routing (forbidden):** Never submit / structure / book a PB product via IB. PB products are OTC bilateral; IB execution doesn't apply.
   - **Market data (allowed):** IB Gateway broker-feed chain (mid / IV / greeks) is a valid `Snapshot.chain` source when in live-trade mode (per hard rule #2 overlap-zone priority).

   Output is product-specific:
   - **FCN**: 8-item PB checklist + 70/75/80/85% strike ladder + fair vs quoted verdict + bilingual counter-offer email (Chinese first, English second)
   - **AQ / DQ**: 6 refusal red-line check FIRST (may short-circuit to REFUSE before any chain pull) → 8-item PB checklist + fair-value breakdown with `data_provenance` per number + term-optimizer Pareto frontier (4-param sweep) + bilingual counter-offer email
6. Bracket order defaults: take-profit at 50% of max gain, stop-loss at 2× credit received (100% of max loss for spreads). Per-order override allowed.
7. **Freshness gate.** Every data point quoted in an analysis must be **≤ 1 trading day stale** (live or T-1 close). Older = **gap**, not signal — list under "What this analysis is missing" and do **not** extrapolate forward. Always check UW response timestamps (`price_data.date`, indicator series last date, chain `last_price.date`) before quoting any number; if stale, treat as gap and either re-pull from a fresh source or flag explicitly.
8. **Ticker analysis structure is non-negotiable.** Every "分析 <TICKER>" / "evaluate <ticker>" response opens with a **Layer Coverage table** (template in `references/analysis-runbook.md`) declaring per-layer source + freshness + ✓/skipped status. Skipping is allowed only when the layer's data is unreachable; it must appear as `skipped` in the table AND under "What this analysis is missing" — never silently dropped. Following the full 8-layer runbook end-to-end is the structural baseline; the trader has explicitly flagged "miss or skip" as a recurring problem and the Layer Coverage table is the structural counter.

## Triggers

For any ticker analysis ("分析 <TICKER>" / "evaluate <ticker> for <structure>"),
follow `references/analysis-runbook.md` end-to-end. The runbook lists the
data source per layer, the compute step, and the decision output; do NOT
skip a layer silently — report any data-source gap explicitly.

Chinese:
- "分析 <TICKER>"
- "PB 给我报了 <TICKER> 的 FCN, X% coupon"
- "PB 给我报了 <TICKER> 的 AQ, X% strike, Y% KO"
- "PB 给我报了 DQ"
- "评估这个 accumulator 报价"
- "decumulator 怎么 counter"
- "<TICKER> 怎么做 sell put / covered call / jade lizard"
- "我账户里这些仓位有没有问题"
- "SPX 大盘对冲"
- "<TICKER> 现在该 close 还是 roll"
- "复盘" / "本周复盘" / "本月复盘"

English:
- "negotiate fcn quote"
- "evaluate aq quote"
- "evaluate dq quote"
- "negotiate accumulator"
- "evaluate <ticker> for <structure>"
- "size spx hedge"
- "review positions"
- "weekly review" / "monthly review" / "review my recent calls"

## When to read which file

Routing table — match the trader's request to the files to load. Lazy-load
discipline: read only the rows that fire for the current request, not the
entire references directory. The full 8-layer recipe in
`references/analysis-runbook.md` is the spine; the other rows are entry
points into specific layers without re-reading the whole runbook.

| Situation | Files to load |
|---|---|
| **Any trader request — match it to a workflow first** | `references/workflows-overview.md` (routing index for the 4 workflows: analyze stock / analyze index / analyze positions / analyze FCN). Read this **first** to pick the workflow, then drill into the deep-reference file the workflow points to |
| Full ticker analysis ("分析 <TICKER>", "evaluate <ticker> for <structure>") | `references/analysis-runbook.md` end-to-end — every layer in order, with the per-layer data source and decision output |
| Picking structure once vol regime + direction are known | `references/strategies.md` (regime × structure matrix); apply §"Strong bullish conviction veto" before recommending jade lizard / iron condor / calendar |
| **About to recommend jade lizard / iron condor / calendar / diagonal** | **MANDATORY**: `references/strategies.md` §"Strong bullish conviction veto" — run the 4-signal check FIRST. If ≥3 fire, refuse and recommend long call / bull put spread / risk reversal / CSP instead |
| Computing gamma flip / put wall / call wall from UW GEX | `references/gamma-framework.md`; invoke `scripts.gex_levels::compute_levels_per_expiry` with `call_wall_definition='oi_cluster'` for short-dated trades (aggregate `compute_levels` is misleading for short windows — see runbook Layer 1) |
| Labelling vol regime (RICH / NEUTRAL / CHEAP) | `scripts.vrp::compute_vrp` — IV − RV with ±5pp thresholds |
| Reading TV chart, tape, news, catalyst-clock validation | `references/price-action-framework.md`; `references/data-sources.md` for TV setup gotchas (opencli ≥ 1.8.0, port 9222 collision with chrome-devtools-mcp, stale TV process recovery) |
| FCN / ELN quote evaluation ("PB 给我报了 X% coupon on Y") | `references/fcn-framework.md`; `scripts.fair_coupon::analyze_fcn`. Output is the 8-item PB checklist + 70/75/80/85% strike ladder + bilingual counter-offer email — do NOT route through IB (hard rule #5) |
| AQ/DQ quote evaluation ("PB 给我报了 AQ", "evaluate aq quote") | `references/aq-dq-framework.md`; `scripts.fair_aq_dq::analyze_quote` + `optimize_terms` + `build_counter_offer_email`. Output: 6-refusal-check → 8-item PB checklist → fair-value breakdown w/ provenance → Pareto frontier → bilingual email. Do NOT route through IB (hard rule #5). |
| SPX macro hedge sizing | `scripts.macro_hedge::build_macro_hedge`. Respect the 1.5% NLV annualized cost cap (hard rule #5). Trigger heuristics in `references/strategies.md` §"Macro hedge trigger heuristics" |
| Position book review ("我账户里这些仓位有没有问题") | Pull **every configured broker** — IB MCP primary (`get_account_summary` + `get_account_positions` + `get_account_orders`), plus any secondary brokers documented in `private/trader-profile.md` using the pull command(s) specified there (e.g., a CLI script, MCP server, or Python wrapper the user provides). Translate non-IB positions into the IB-shape dict (`contract_description` / `position` / `market_price`) before feeding into `scripts.defined_risk_audit::audit_book` and `scripts.manage_positions` (orchestrator CLI: `.venv/bin/python -m scripts.manage_positions --audit-only --no-email`). Report which broker(s) succeeded and any pull-time data gaps. Output follows §"Book-review output structure" — action items consolidated at the END of the report, not drilled into mid-flow. |
| 21 DTE review on short-premium positions | `scripts.evaluate_position`; hard rule #4 — surfaces in the Action items section at the end of the book review (close / roll / hold-and-accept-gamma). Trader picks from the menu; only then expand into hard-rule-#3 preflight. |
| Pre-submission preflight + YES/NO gate | `references/execution.md`; `scripts.ib_order::build_preflight`. Hard rule #3 — must show legs + mid + max loss + max gain + breakeven + margin + P/L matrix (spot ±5/10/20%) + account verification + UW regime check + liquidity + catalyst clock before exactly one YES/NO question |
| Honest gap reporting when a data source is unreachable | `references/analysis-runbook.md` §"Honest reporting of gaps" — list every missing layer under "What this analysis is missing" rather than fabricating signals |
| Pattern match against a prior FCN deal | `references/ticker/orcl-2026-06-fcn.md` (public, anonymized) |
| Pattern match against a prior personal trade / analysis | `references/ticker/private/*.md` — trader's local archive (gitignored). List the directory and pick by date / event / ticker |
| Capturing a new pitfall from a closed trade | `references/pitfalls/_template.md` → copy to `NN-slug.md`; add row to `references/pitfalls/README.md` (index currently empty — backfill from trade history is tracked as H1). Strip all account-specific numbers before promoting from `private/` |
| Weekly / monthly review ("复盘" / "weekly review" / "review my recent calls") | `references/review-framework.md`; `scripts.retrospective::run_review` (pure functions) + `python -m scripts.retrospective --window weekly|monthly` (orchestrator CLI). Markout (T+1/5/10/21/45d) on directional / vol regime / structure calls + actual trades. Side-by-side avg-call vs avg-trade markout. 4-quadrant discipline scorecard (followed/ignored × correct/wrong). Monthly adds pattern analysis. Action items at END (S/P/T/D). Auto-writeback of verdict to source Outcome / Lesson section. Auto pitfall draft generation to `references/pitfalls/_drafts/`. **FCN / AQ / DQ are out of scope** — those audit separately. |

## Book-review output structure

Every position book review follows the same four-stage layout. **Do not interrupt stages 1-3 to demand a per-position YES/NO** — that pattern produced a session-long detour during a multi-broker review and is no longer the workflow.

1. **Data pull** — every configured broker (IB MCP for the primary IB account, plus any secondary brokers per `private/trader-profile.md` using the pull command specified there). Report which broker(s) succeeded and any pull-time data gaps (e.g., a CLI report that doesn't include cash balance).
2. **Book-level analysis** — concentration (abs MV % and Δ-1 notional vs NLV), Greeks (net Δ / Γ / Θ / V, plus Δ-1 single-name bars), every leg laid out, defined-risk audit verdict (with script false-positive callouts where the $20 strike-width limit misfires), 22-45 DTE watchlist, catalyst clock, data quality flags.
3. **No mid-flow decision prompts.** 21 DTE short-premium positions, approaching-21-DTE positions, ER catalysts, large shorts, data anomalies — all of these are *observed* in stage 2 but **not** acted on yet.
4. **One consolidated "Action items" block at the END.** Grouped into Position-level decisions (P1, P2, …), Data quality (D1, D2, …), Book-level risks (R1, R2, …), Infrastructure (I1, I2, …). Each item is one line with the choice menu inline (close/roll/hold, verify, fix, etc.). Include trigger phrases ("P1 submit", "D2 verify", "R3 fix") so the trader can pick fast. **Wait** for the trader to pick — then expand the chosen item(s) into preflight / drill-down / fix in the next turn.

Two reinforcing rules under stage 4:
- **AT THE END** — never interrupt the broader analysis with a single position's YES/NO.
- **ALL TOGETHER** — never drill into action items one at a time (P1 → wait → P2 → wait …). Present the full menu; trader picks one or many.

The full hard-rule-#3 preflight (legs, mids, P/L matrix, UW regime, liquidity, brackets, gaps, archive write) only runs when the trader explicitly picks an item from the menu and says "build it" / "submit" / "show me the roll" / "drill into P1". Hard rules are not weakened — they just don't auto-trigger from the book review alone.

Edge case — structurally dangerous position (naked short call discovered, undefined risk found, gamma blow-up imminent): surface as URGENT at the top of the Action items block. Still no auto-preflight; trader still picks.

## Reporting & archive

**Output the analysis to the screen first.** Do NOT auto-write to `private/` by default. The trader explicitly requests save with phrases like "保存这份" / "save this" / "archive" / "存档" — only then write to `references/ticker/private/<slug>-YYYY-MM-DD-<event>.md`.

Reports that the trader typically wants saved (but still requires explicit ask):

- Full ticker analysis (`分析 <TICKER>`)
- Position book review / `持仓 review`
- FCN/ELN/AQ/DQ evaluation with concrete deal numbers
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

**Save is explicit, not default.** The trader prefers to review the screen output first and decide whether it's worth preserving. Surface a one-line "want me to save this?" hint at the very end of substantive reports if you think the artifact is worth keeping, but do not write the file until they say yes.

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

# FCN ladder analysis (model path — no chain in snapshot)
.venv/bin/python -c '
from scripts.fair_coupon import analyze_fcn
snap = {"spot": 200.0, "iv": 0.35, "rv": 0.30, "iv_rank": 55,
        "skew_25d": 0.04, "max_drawdown_5y": -0.45,
        "gex_levels": {"gamma_flip": 195.0, "put_wall": 180.0, "call_wall": 220.0}}
r = analyze_fcn("ORCL", strike_pcts=(0.70, 0.75, 0.80, 0.85),
                tenor_months=6, observation_months=3,
                pb_quoted_coupon=0.12, snapshot=snap)
print(r["verdict"], "at", r["anchor_strike_pct"])
# Each rung carries r["ladder"][i]["fair_coupon_source"] = "model" here.
'

# FCN ladder analysis (chain path — preferred when chain available).
# Adding "chain" + "chain_source" + "chain_timestamps" + "spot_timestamp"
# to the snapshot activates chain-priced fair coupon. Each rung output gets
# fair_coupon_source="chain" and fair_coupon_provenance.leg.source="UW"|"IB"
# pointing back to the exact listed strike that priced the rung.
.venv/bin/python -c '
from scripts.fair_coupon import analyze_fcn
snap = {"spot": 200.0, "iv": 0.35, "rv": 0.30, "iv_rank": 55,
        "skew_25d": 0.04, "max_drawdown_5y": -0.45,
        "gex_levels": {"gamma_flip": 195.0, "put_wall": 180.0, "call_wall": 220.0},
        "chain_source": "UW", "spot_timestamp": "2026-06-05T10:00:00Z",
        "chain_timestamps": {"2026-12-18": "2026-06-05T10:00:00Z"},
        "chain": {"2026-12-18": {
            0.70: {"put": {"mid": 1.20, "iv": 0.42}},
            0.75: {"put": {"mid": 2.40, "iv": 0.40}},
            0.80: {"put": {"mid": 4.80, "iv": 0.38}},
            0.85: {"put": {"mid": 9.10, "iv": 0.36}},
        }}}
r = analyze_fcn("ORCL", strike_pcts=(0.70, 0.75, 0.80, 0.85),
                tenor_months=6, observation_months=3,
                pb_quoted_coupon=0.12, snapshot=snap,
                quote_start_iso="2026-06-05T00:00:00Z")
for rung in r["ladder"]:
    print(rung["strike_pct"], rung["fair_coupon_base"], rung["fair_coupon_source"])
'

# AQ / DQ quote evaluation
.venv/bin/python -c '
from scripts.fair_aq_dq import analyze_quote, optimize_terms, Quote, Snapshot
q = Quote(direction="AQ", ticker="ORCL", spot=234.91, strike_pct=0.95,
          ko_pct=1.03, tenor_months=12, obs_freq="daily",
          doubling_factor=2.0, daily_notional_usd=10000,
          pb_quoted_yield_pa=0.08, settlement="cash")
# snapshot = Snapshot(...)  # orchestrator builds from IB or UW chains + UW metrics
v = analyze_quote(q, snapshot, nlv_usd=1_000_000)
print(v.markup_pp, v.decision, v.refusal_reasons)
print(optimize_terms(q, snapshot)[:5])
'

# SPX macro hedge sizing (BSM path — no chain in snapshot).
# Each leg gets mid_source="fallback"; pricing_source="bsm" at top level.
.venv/bin/python -c '
from scripts.macro_hedge import build_macro_hedge
print(build_macro_hedge(portfolio_notional=1_000_000, hedge_horizon_days=60,
                        scenario="deep_correction_-10", structure="put_spread",
                        snapshot={"spot": 6000.0, "iv_atm_90d": 0.18}))
'

# SPX macro hedge sizing (chain path — preferred when chain available).
# Adding "chain" + "chain_source" + "spot_timestamp" + "chain_timestamps"
# activates per-leg chain mid lookup. Top-level pricing_source rolls up to
# "chain" if every leg priced off the chain, "mixed" if some fell back to
# BSM, "bsm" if none used chain. Each leg gets mid_source + mid_provenance
# (full path back to chain[expiry][strike_pct][right]["mid"] for audit).
.venv/bin/python -c '
from scripts.macro_hedge import build_macro_hedge
snap = {"spot": 6000.0, "iv_atm_90d": 0.18,
        "chain_source": "UW", "spot_timestamp": "2026-06-05T10:00:00Z",
        "chain_timestamps": {"2026-08-15": "2026-06-05T10:00:00Z"},
        "chain": {"2026-08-15": {
            0.90: {"put": {"mid": 18.50, "iv": 0.21}},
            1.00: {"put": {"mid": 100.30, "iv": 0.18}},
        }}}
out = build_macro_hedge(portfolio_notional=10_000_000, hedge_horizon_days=70,
                        scenario="deep_correction_-10", structure="put_spread",
                        snapshot=snap)
print(out["pricing_source"], out["cost_dollar"])
for leg in out["legs"]:
    print(leg["action"], leg["strike"], leg["limit_price"], leg["mid_source"])
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
