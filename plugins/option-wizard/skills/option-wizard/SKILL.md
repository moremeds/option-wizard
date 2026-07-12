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
  reader (spot, charts, technicals, news), xenon Query API (IB+Futu account
  state, live mid/L2 depth, live option greeks/IV; IB MCP fallback),
  ib_insync (order placement). Triggers on ticker mentions in trading context,
  FCN/ELN quote review, "should I sell put on X", "covered call on Y",
  "is this FCN deal good", "macro hedge", "check my positions", "place
  this order". Chinese response with English technical terms. Defined-risk
  only — never naked short calls, never margin-leveraged short puts.
---

# option-wizard

Domain knowledge lives in `references/`; numeric work in `scripts/`. See
§"When to read which file" below for the situation → files map (LLM uses
this to pick what to load); see §"How to invoke scripts" for the script
incantations. `references/` is an [Open Knowledge Format (OKF) v0.1] bundle
(`references/OKF.md` = conformance + type vocabulary, `references/index.md` =
navigable root, `references/log.md` = change history); the §"When to read
which file" router is the primary lazy-load mechanism, the per-file
frontmatter `description` is the self-describing fallback.

## Hard rules (apply to every response)

1. Defined-risk only. Refuse naked short calls and margin-leveraged short puts; explain why when refusing.
2. **Source discipline (3-source taxonomy).** Three sources, each canonical for non-overlapping core territory + overlapping zones where freshness picks the winner.

   **Canonical per source:**
   - **UW** — options-derivative metrics no one else serves: IV rank, skew, GEX by strike, max pain, RV, dark pool, flow, interpolated IV (analytical-mode greeks)
   - **xenon Query API** (read-only, `X-API-Key`) — account state for **IB and Futu** (`/portfolio`, `/futu/portfolio`, `/orders`, `/blotter`, `/journal`, `/performance`); live **mid / NBBO / L2 liquidity** (`/market-depth`); live **per-contract greeks / IV** (`/options/greeks`, IB `modelGreeks`). IB MCP read tools / Futu `portfolio-analyser` CLI / `ib_insync reqMktData` are the **documented fallbacks**. **No client-side BSM** for greeks/IV — always from a live broker quote.
   - **TradingView** — spot, OHLCV, technical indicators (SMA / EMA / RSI / MACD / BBANDS / ATR / volume bars), news, alerts, watchlists, charts
   - **ib_insync** — option **execution** (`placeOrder`) + fallback live greeks (`reqMktData` `modelGreeks`). Order routing stays here; xenon never routes orders (read-only key).

   **Overlapping zones priority:**

   | Data point | Primary | Fallback | Why |
   |---|---|---|---|
   | Spot | TV | xenon `/market-depth` underlying mid → IB `get_price_snapshot` | TV intra-minute fresh + chart-verifiable; xenon broker-feed authoritative for live-trade gating |
   | Live mid / NBBO / L2 liquidity | **xenon `/market-depth`** | IB `get_price_snapshot` | seconds-fresh book + sizes for the liquidity gate |
   | Option greeks / IV (live-trade <60s) | **xenon `/options/greeks`** (IB `modelGreeks`) | **ib_insync `reqMktData`** | live broker-computed greeks around the clock (frozen mode); **never** client-side BSM |
   | Option IV / greeks (analytical context) | **UW** `interpolated_iv` / `greeks_by_strike` | xenon `/options/greeks` | UW better for skew/term analytical context; cross-check vs the live quote |
   | OHLCV historical | TV (chart context) | IB `get_price_history` (backtest precision) | — |

   **Forbidden:**
   - UW `get_extended_technical_indicator` / `get_ticker_indicator_series` for analysis (series lagged by weeks)
   - IB for IV rank / skew / GEX / max pain (IB doesn't compute these derivative metrics)
   - TV for IV rank / skew / GEX / max pain / RV (UW is the only source for derivative metrics)

   **Rule of thumb:** if any of the three serves it directly, never recompute. Verdict / analysis output must carry `data_provenance` for every quoted metric so the trader can audit the source.

   **Skill-wide chain-mid path:** `scripts.fair_aq_dq`, `scripts.fair_coupon`, `scripts.macro_hedge`, `scripts.diagonal_calendar` ALL accept an optional `chain` field on their snapshot input. When provided, listed-strike option mids are read directly from the chain (per workflow §2 source-selection: UW analytical default / IB live-trade / TV when desktop session live) instead of recomputed via BSM. Output fields tag the source: `fair_coupon_source` ∈ {chain, model}, `pricing_source` ∈ {chain, mixed, bsm}, leg-level `mid_source` ∈ {UW, IB, TV, fallback} and `mid_provenance`. Orchestrator MUST pull a chain into the snapshot before calling these scripts when the trader is in live-trade or fair-value-comparison mode.

   **Chain orchestrator-transform contract:** UW / IB / TV native shapes differ — the orchestrator (skill prompt) MUST transform into the nested form:
   ```
   chain[expiry_iso][strike_pct][right] = {"mid": float, "iv": float, "greeks": {delta, gamma, theta, vega}}
   ```
   - **UW** `get_options_chain` returns `{states: [flat list of option_state]}` with greeks as top-level fields (`delta`, `gamma`, `theta`, `vega`), no `mid` (use `theo` or `(bid+ask)/2`); group by `expires` → `strike/spot` → `option_type`.
   - **xenon** `/options/greeks` (live-trade single-contract, PRIMARY): returns `{bid, ask, greeks:{impliedVol,delta,gamma,vega,theta,undPrice}}` per triplet (IB `modelGreeks`); `mid = (bid+ask)/2`, `greeks.impliedVol` → `iv`. Pair with `/market-depth` for liquidity. **ib_insync `reqMktData` is the fallback** for this path.
   - **IB** via `ib_insync.reqMktData` (FALLBACK) returns a `Ticker` with `bid`/`ask`/`modelGreeks`; compute `mid = (bid+ask)/2`, lift `modelGreeks` → nested `greeks`.
   - **TV** via `opencli tv options-chain` returns rows with `bid`/`ask`/`iv` and (depending on TV plan) greeks; same `mid = (bid+ask)/2` + nested greeks transform.
   - `chain_source` ∈ {"UW", "IB", "TV"}; legs inherit this as `mid_source`. BSM fallback flags `mid_source = "fallback"` per leg.
3. Every order shows the pre-flight (legs, mid price, net debit/credit, max loss, max gain, breakeven, margin, P/L matrix at expiry across spot −20 / −10 / −5 / 0 / +5 / +10 / +20 percent, account verification, UW regime check, liquidity check, catalyst clock) before submission. Exactly one YES/NO question. YES → submit via `ib_insync.placeOrder` (IB option orders) or `create_order_instruction` (IB stock drafts for tap-to-approve). Non-IB broker orders (any secondary broker configured in `private/trader-profile.md`) typically have no auto-submit path — flag "manual entry in the broker's trading app" in the preflight. Anything else → abort. Live-account preflight is the safety boundary — do **not** propose paper-account (IB TWS paper instance) tests, and do not treat paper-account criteria as a blocker.
4. Any short-premium position at 21 DTE surfaces as an entry in the consolidated **Action items** section at the end of the book review (see §"Book-review output structure"). It is **not** a mid-flow blocking YES/NO prompt — the trader picks close / roll / hold-and-accept-gamma from the action-items menu, and only then does the full hard-rule-#3 preflight expand.
5. **PB structured products (FCN / AQ / DQ): no IB ORDER ROUTING; IB MARKET DATA is allowed.** This is two separate concerns:
   - **Order routing (forbidden):** Never submit / structure / book a PB product via IB. PB products are OTC bilateral; IB execution doesn't apply.
   - **Market data (allowed):** IB Gateway broker-feed chain (mid / IV / greeks) is a valid `Snapshot.chain` source when in live-trade mode (per hard rule #2 overlap-zone priority).

   Output is product-specific:
   - **FCN**: 8-item PB checklist + 70/75/80/85% strike ladder + fair vs quoted verdict + bilingual counter-offer email (Chinese first, English second)
   - **AQ / DQ**: 7 refusal red-line check FIRST (may short-circuit to REFUSE before any chain pull) → 8-item PB checklist + fair-value breakdown with `data_provenance` per number + term-optimizer Pareto frontier (4-param sweep) + bilingual counter-offer email
6. Bracket order defaults: take-profit at 50% of max gain, stop-loss at 2× credit received (100% of max loss for spreads). Per-order override allowed.
7. **Freshness gate (live-first + exhaust-before-gap).** Every quoted number must be the **most accurate currently-obtainable** value, pulled **live at the moment of analysis** — never a prior-session close, a converted prior-day technical, or an extrapolation when a live source is reachable. The xenon Query API makes live data acquirable at any time (account/orders/blotter + `/market-depth` + `/options/greeks` — greeks via IB frozen mode return around the clock), alongside UW (analytics) and TV (spot/technicals). Walk the **per-data-point acquisition ladder** in `references/data-sources.md` before declaring any gap. Before writing any "STALE / 未重拉 / gap" caveat, self-check: *did I actually call the live endpoint? did I try alternative symbols / exchange codes / endpoint variants / other sources, including the xenon live surface?* A caveat is permitted only after a **documented** attempt and must state **what was tried** — never a bare "未重拉". **Avoidable** gaps (a reachable live source was simply not pulled) are not acceptable; **genuine** gaps (no source serves that slice) are flagged honestly and never extrapolated/fabricated. Surface freshness explicitly (xenon `last_sync` / Futu `is_stale` / UW `price_data.date`). **Every workflow step that says "pull live X" is a MANDATORY execution gate — you must actually call the live endpoint, not read a cached/aggregate feed and present it as live.** A feed returning a number is not the same as a live number: **verify its timestamp** (`updated_at` / latest-bar time / `date`) is the current session before quoting it — a stale value is a gap disguised as data. **Index pre-market/overnight is the load-bearing case: pull IB `get_price_snapshot` on the ES front-month future + VIX index FIRST; UW `get_futures_indices` / `get_market_tide` are RTH-cached and frozen outside regular hours** (see `references/data-sources.md` ladder + Pitfall 07).
8. **Ticker analysis structure is non-negotiable.** Every "分析 <TICKER>" / "evaluate <ticker>" response opens with a **Layer Coverage table** (template in `references/analysis-runbook.md`) declaring per-layer source + freshness + ✓/skipped status. Skipping is allowed only when the layer's data is unreachable; it must appear as `skipped` in the table AND under "What this analysis is missing" — never silently dropped. Following the full 8-layer runbook end-to-end is the structural baseline; the trader has explicitly flagged "miss or skip" as a recurring problem and the Layer Coverage table is the structural counter.
9. **复盘 source separation (archive ≠ broker).** Every weekly / monthly review (`复盘` / `weekly review` / `monthly review` / `review my recent calls`) outputs **three independent layers**, sourced strictly:

   - **Layer A — Analysis quality (archive only).** Source: `references/private/{ticker,market,review}/**/*.md` (recursively). Use: directional verdict (right / wrong / unknown) via markout, hit-rate aggregates, lessons for improving future analyses. Archive documents describe **proposed trades or analysis-only theses** — they are NOT trade records. Never infer "a trade happened" from archive presence.
   - **Layer B — Trade flow (broker only, BOTH brokers required).** Sources: **xenon `/blotter` (IB + Futu fills) + `/portfolio` + `/futu/portfolio`** (positions), via `scripts.retrospective.parse_xenon_blotter`. IB MCP `get_account_trades` + Futu `portfolio-analyser` CLI (per `private/trader-profile.md`) are the **documented fallbacks**. Use: actual fills, execution markout, realized P&L, roll patterns, position deltas. **Only legitimate source for "what was actually done"** — never substitute archive titles (e.g., `qqq-...-short-put-tp-close.md`) as evidence of execution.
   - **Layer C — Cross-cut (advisory, judgment-only).** Manual observations relating Layer A to Layer B (e.g., "6/04 bearish call → 6/05 才 hedge,lag 1 day"). Must be labeled **"judgment-only, not algorithmic"**. No automated `followed × correct` quadrant; no scorecard joining the two streams.

   **Forbidden:**
   - `reconcile_calls_with_trades` / `discipline_quadrant` style auto-join between archive and broker streams
   - Inferring trade execution from archive frontmatter status field
   - Using `qqq-...-tp-close.md`-style filenames as trade evidence
   - Running 复盘 with only one broker pulled — both IB and Futu must be hit each time

   See `references/review-framework.md` §"3-layer architecture" for the full pipeline and `scripts/retrospective.py` orchestrator.
10. **Decision doctrine (aggressive when confirmed, contrarian when crowded).** Every actionable recommendation (listed-options trade, macro hedge, book-review action item) follows `references/decision-doctrine.md`: competing hypotheses (bull / base / bear / vol-up / vol-down / no-trade) → disconfirmation + **crowding check** (consensus one-sided → the opposite case is written FIRST) → **≥2 economically distinct structures compared** → **aggression tier** (NO_TRADE / PROBE / SMALL / NORMAL / HIGH_CONVICTION / EXCEPTIONAL; max loss hard-capped at **5% NLV at every tier** — aggression buys earlier entry and more directional structure, never bigger max loss) → management plan with dynamic re-rating triggers → closes with the **决策块** decision block (当前判断 / 我的行动 / 进攻程度 / 为什么现在 / 最大风险 / 失效条件 / 下一步触发器 / 数据可信度). Conviction never exceeds evidence quality — data confidence LOW caps the tier at PROBE.

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
- "QQQ CSP" / "SPY 卖 put" / "RUT diagonal" / "卖 index premium"
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
- "qqq csp" / "spy put" / "rut diagonal" / "sell index premium"
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
| **Any trader request — match it to a workflow first** | `references/workflows-overview.md` (routing index for the 7 workflows: W1 ticker / W2a macro hedge / W2b index premium / W3 positions / W4 FCN / W5 AQ-DQ / W6 复盘). Read this **first** to pick the workflow, then drill into the deep-reference file the workflow points to |
| Full ticker analysis ("分析 <TICKER>", "evaluate <ticker> for <structure>") | `references/analysis-runbook.md` end-to-end — every layer in order, with the per-layer data source and decision output |
| Picking structure once vol regime + direction are known | `references/strategies.md` (regime × structure matrix); apply §"Strong bullish conviction veto" before recommending jade lizard / iron condor / calendar |
| **Turning evidence into a recommendation — sizing, aggression tier, competing hypotheses, crowding check, 决策块 decision block** | **MANDATORY for any actionable rec (hard rule #10)**: `references/decision-doctrine.md` — phases A–G, 9 alignment conditions, tier table (5% NLV max-loss hard cap), contrarian crowding check, dynamic re-rating triggers, missing-data taxonomy, adversarial QC checklist. Fires at runbook Layer 6–7, macro-hedge sizing, and book-review action items |
| **About to recommend jade lizard / iron condor / calendar / diagonal** | **MANDATORY**: `references/strategies.md` §"Strong bullish conviction veto" — run the 4-signal check FIRST. If ≥3 fire, refuse and recommend long call / bull put spread / risk reversal / CSP instead |
| Computing gamma flip / put wall / call wall from UW GEX | `references/gamma-framework.md`; invoke `scripts.gex_levels::compute_levels_per_expiry` with `call_wall_definition='oi_cluster'` for short-dated trades (aggregate `compute_levels` is misleading for short windows — see runbook Layer 1) |
| Labelling vol regime (RICH / NEUTRAL / CHEAP) | `scripts.vrp::compute_vrp` — IV − RV with ±5pp thresholds |
| Labelling IV term-curve regime (contango / flat / inverted) across held or analyzed expiries | `scripts.term_curve::label_regime` for per-pair labels + `summarize_regime` for the aggregate. ATM IV extraction: prefer `atm_iv_by_expiry_from_term_structure` (one `iv_term_structure` call covers every listed expiry) falling back to `atm_iv_from_chain_rows` (auto-pivots the actual `get_chains_for_expiry` per-contract row shape) for expiries not covered. Single source of truth for Workflow 1 L2, Workflow 3 stage-2 item (h), and Workflow 6 step 3b. Inline LLM-judge labels are forbidden — they drift across runs. |
| Reading TV chart, tape, news, catalyst-clock validation | `references/price-action-framework.md`; `references/data-sources.md` for TV setup gotchas (opencli ≥ 1.8.0, port 9222 collision with chrome-devtools-mcp, stale TV process recovery) |
| FCN / ELN quote evaluation ("PB 给我报了 X% coupon on Y") | `references/fcn-framework.md`; `scripts.fair_coupon::analyze_fcn`. Output is the 8-item PB checklist + 70/75/80/85% strike ladder + bilingual counter-offer email — do NOT route through IB (hard rule #5) |
| AQ/DQ quote evaluation ("PB 给我报了 AQ", "evaluate aq quote") | `references/aq-dq-framework.md`; `scripts.fair_aq_dq::analyze_quote` + `optimize_terms` + `build_counter_offer_email`. Output: 7-refusal-check → 8-item PB checklist → fair-value breakdown w/ provenance → Pareto frontier → bilingual email. Do NOT route through IB (hard rule #5). |
| SPX / cross-index macro hedge sizing | `references/macro-hedge-convexity.md` (empirical framework + regime decision tree); `scripts.macro_hedge::build_macro_hedge` (6 structures: butterfly / put_spread / long_put / vix_call_ladder / iwm_putspread / qqq_longput; `put_ratio_backspread` is FORBIDDEN per Pitfall 03). Respect the 1.5% NLV annualized cost cap (hard rule #5). For tactical structures (put_spread, iwm_putspread, vix_call_ladder), pass `tactical_window_days=14` to confirm intent — otherwise rejected when projected annualized carry > 5% NLV. For the standing hedge, prefer `long_put` with `target_delta=0.05` (5-delta) over fixed pct strike — carry stays calibrated across regimes. When `snapshot["regime_check"]` is supplied (vix / vix9d / vvix / skew / hy_oas / tech_specific_catalyst), structure-specific regime gates fire and reject wrong-regime suggestions. Trigger summary in `references/strategies.md` §"Macro hedge trigger heuristics". **A hedge placed manually (not via `build_macro_hedge`) bypasses this cap entirely** — `scripts.retrospective::flag_hedge_cost_outliers` (U6/F3) retroactively re-checks it during 复盘, surfacing as an R-item; see `review-framework.md` §"Hedge cost outliers" |
| Index premium selling (QQQ/SPY CSP or RUT put diagonal) | `references/index-premium-selling.md`; `scripts.diagonal_calendar::build_diagonal_calendar` for RUT 3-mode structures; `scripts.entry_timing::decide` for morning-vs-EOD; CSP uses `scripts.ib_order::build_preflight` directly. Threshold calibration via `scripts.entry_timing::calibrate` reading the audit log |
| Position book review ("我账户里这些仓位有没有问题") | Pull **both brokers via the xenon Query API** — `XenonClient.ib_portfolio()` + `futu_portfolio()` (IB MCP `get_account_summary`/`get_account_positions`/`get_account_orders` + Futu `portfolio-analyser` CLI are the documented fallbacks). `scripts.xenon_normalize.to_audit_positions` / `to_futu_audit_positions` translate both into the IB-shape dict (`contract_description` / `position`) before feeding into `scripts.defined_risk_audit::audit_book` and `scripts.manage_positions` (orchestrator CLI: `.venv/bin/python -m scripts.manage_positions --audit-only --no-email`). Report which broker(s) succeeded and any pull-time data gaps (xenon `last_sync` / Futu `is_stale`). Output follows §"Book-review output structure" — action items consolidated at the END of the report, not drilled into mid-flow. |
| 21 DTE review on short-premium positions | `scripts.evaluate_position`; hard rule #4 — surfaces in the Action items section at the end of the book review (close / roll / hold-and-accept-gamma). Trader picks from the menu; only then expand into hard-rule-#3 preflight. |
| Open decision-ledger items (start of any book review / 复盘 / daily scan) | `references/decision-doctrine.md` §"Dynamic risk management"; `scripts.ledger` — `load_ledger` + `open_items`/`render_open_items_block` (daily scan, prepended by `manage_positions`) or `render_ledger_section` (复盘, passed into `run_review(ledger_section=...)`). Unresolved book-review / 决策块 action items are logged via `append_entry` at the end of the session; picked-up items get `set_status(..., "done"/"superseded")`. |
| Pre-submission preflight + YES/NO gate | `references/execution.md`; `scripts.ib_order::build_preflight`. Hard rule #3 — must show legs + mid + max loss + max gain + breakeven + margin + P/L matrix (spot ±5/10/20%) + account verification + UW regime check + liquidity + catalyst clock before exactly one YES/NO question |
| Honest gap reporting when a data source is unreachable | `references/analysis-runbook.md` §"Honest reporting of gaps" — list every missing layer under "What this analysis is missing" rather than fabricating signals |
| Pattern match against a prior public case study (any ticker / structure) | `scripts.case_studies::find_case_studies(ticker=..., structures=[...])` reads the OKF `Trade Case Study` frontmatter in `references/ticker/*.md` and returns ranked matches (ticker hit > structure overlap); CLI: `python -m scripts.case_studies --ticker ORCL [--structure fcn] [--json]`. Load the matched file(s) — e.g. `references/ticker/orcl-2026-06-fcn.md` (public, anonymized). This is the public-bundle complement to the `private/` archive lookup below. |
| Pattern match against a prior personal trade / analysis | `references/private/{ticker,market,review}/**/*.md` — trader's local archive (gitignored). Pick subdir by analysis type (`ticker/` single-name, `market/` macro/multi-ticker, `review/` book/weekly/monthly) then by `{date}-{ticker}-{long|short|mixed}-{highlight}.md` filename |
| Capturing a new pitfall from a closed trade | `references/pitfalls/_template.md` → copy to `NN-slug.md` (template carries the `Trading Pitfall` OKF frontmatter to fill); add a row to `references/pitfalls/index.md` and a dated entry to `references/log.md`. Strip all account-specific numbers before promoting from `private/` |
| Weekly / monthly review ("复盘" / "weekly review" / "review my recent calls") | `references/review-framework.md`; `scripts.retrospective::run_review` (pure functions) + `python -m scripts.retrospective --window weekly|monthly` (orchestrator CLI). **Hard rule #9 — 3 independent layers:** Layer A = analysis quality from archive only (markout T+1/5/10/21/45d, directional verdict, hit rate). Layer B = trade flow from **xenon `/blotter` (both brokers) + `/portfolio` + `/futu/portfolio`** via `parse_xenon_blotter` (IB MCP + Futu CLI = documented fallback; both brokers required; execution markout, realized P&L, roll patterns). Layer C = cross-cut advisory (judgment-only, no algorithmic scorecard). Action items at END (S/P/T/D). Auto-writeback of verdict to source `## Outcome / Lesson` section. Auto pitfall draft generation to `references/pitfalls/_drafts/`. **FCN / AQ / DQ are out of scope** — those audit separately. |

## Book-review output structure

Every position book review follows the same four-stage layout. **Do not interrupt stages 1-3 to demand a per-position YES/NO** — that pattern produced a session-long detour during a multi-broker review and is no longer the workflow.

0. **Open decision-ledger items first** (`references/decision-doctrine.md` §"Dynamic risk management") — load `references/private/ledger.jsonl` via `scripts.ledger.load_ledger` / `open_items` and lead the report with "what did I say to do last time?" before any new analysis. This is what stops a prior 决策块 action item (e.g. "roll TSLA 400/390 down by 6/25") from only living in a one-off report the trader has to remember to reread.
1. **Data pull** — both brokers via the xenon Query API (`XenonClient.ib_portfolio()` + `futu_portfolio()`; IB MCP + Futu `portfolio-analyser` CLI are the documented fallbacks). Report which broker(s) succeeded and any pull-time data gaps (xenon `last_sync` / Futu `is_stale`; a fallback CLI report that doesn't include cash balance).
2. **Book-level analysis** — concentration (abs MV % and Δ-1 notional vs NLV), Greeks (net Δ / Γ / Θ / V, plus Δ-1 single-name bars), every leg laid out, defined-risk audit verdict, 22-45 DTE watchlist, catalyst clock, data quality flags.
3. **No mid-flow decision prompts.** 21 DTE short-premium positions, approaching-21-DTE positions, ER catalysts, large shorts, data anomalies — all of these are *observed* in stage 2 but **not** acted on yet.
4. **One consolidated "Action items" block at the END.** Grouped into Position-level decisions (P1, P2, …), Data quality (D1, D2, …), Book-level risks (R1, R2, …), Infrastructure (I1, I2, …). Each item is one line with the choice menu inline (close/roll/hold, verify, fix, etc.). Include trigger phrases ("P1 submit", "D2 verify", "R3 fix") so the trader can pick fast. **Wait** for the trader to pick — then expand the chosen item(s) into preflight / drill-down / fix in the next turn. **Any item not resolved in this session** gets logged via `scripts.ledger.append_entry` (ticker, action, tier if applicable, due date if there's a natural deadline like an event or expiry) so it resurfaces at stage 0 of the next review or in the daily `manage_positions` scan — never silently dropped once the session ends. When the trader later picks an item from a resurfaced ledger entry, mark it `done` (or `superseded` if circumstances changed the plan) via `scripts.ledger.set_status`.

Two reinforcing rules under stage 4:
- **AT THE END** — never interrupt the broader analysis with a single position's YES/NO.
- **ALL TOGETHER** — never drill into action items one at a time (P1 → wait → P2 → wait …). Present the full menu; trader picks one or many.

The full hard-rule-#3 preflight (legs, mids, P/L matrix, UW regime, liquidity, brackets, gaps, archive write) only runs when the trader explicitly picks an item from the menu and says "build it" / "submit" / "show me the roll" / "drill into P1". Hard rules are not weakened — they just don't auto-trigger from the book review alone.

Edge case — structurally dangerous position (naked short call discovered, undefined risk found, gamma blow-up imminent): surface as URGENT at the top of the Action items block. Still no auto-preflight; trader still picks.

## Reporting & archive

**Output the analysis to the screen first.** Do NOT auto-write to `private/` by default. The trader explicitly requests save with phrases like "保存这份" / "save this" / "archive" / "存档" — only then write to:

**Exception: 复盘 reports auto-archive by default** (U5/F2, `scripts.retrospective::save_review_report`). A 2026-06-14 weekly review drove real code fixes (commit `b6b5057`) but was never saved — its findings beyond the commit message are permanently unrecoverable. 复盘 is the skill's own audit trail, not a one-off analysis; losing the report defeats its purpose. This exception is scoped narrowly to 复盘's own rendered report — book reviews, ticker analyses, and everything else still follow the screen-first default above.

```
references/private/{ticker|market|review}/{date}-{ticker}-{long|short|mixed}-{highlight}.md
```

Subdir routing (active subtree):
- `ticker/` — single-name analyses, structure evals, roll/close decisions
- `market/` — macro calls, SPX/index hedge sizing, premarket snapshots, multi-ticker decisions
- `review/` — book reviews, weekly/monthly retrospectives, dual-broker book audits

Filename slots: `{date}` = YYYY-MM-DD, `{ticker}` = single symbol / broker tag (`futu`, `ib`) / scope (`macro`, `book`), `{long|short}` = directional thesis (做多 / 做空) or `mixed` when no single direction, `{highlight}` = short kebab-case event tag (`runbook-analysis`, `sell-put-eval`, `roll-preflight`, `tp-close`, `weekly-retrospective`).

### Active vs cold storage (30-day TTL)

Two-tier layout to prevent stale theses from contaminating future analysis:

```
references/private/
  ticker/  market/  review/                      ← ACTIVE  (last ~30 days, in scope for default review)
  archive/YYYY-MM/{ticker|market|review}/...     ← COLD    (frozen, skipped by default)
```

- **Default review** (`scripts.retrospective` weekly / monthly, `pattern-match` lookup): scans active subtree only. Cold `archive/` files are invisible.
- **Opt-in scan**: pass `--include-archive` to `python -m scripts.retrospective …` for monthly / quarterly reviews that span back past the TTL.
- **Migration**: `python -m scripts.archive_cold --apply` moves any file whose `archive_eligible_after` ≤ today into `archive/YYYY-MM/<subdir>/`. Run once at month-end (or whenever the active subtree feels too noisy).

Why: pattern-match against prior analyses (`references/private/{ticker,market,review}/**/*.md` routing row) would otherwise pick up a 2-month-old thesis as if it were current. 30 days is long enough to cover a single ER cycle and the average position lifetime; older files survive in cold storage for audit but stay out of the default working set.

**File format** (trade-skills frontmatter convention):
```yaml
---
ticker: <SYMBOL or comma-list for macro>
event: <one-line context>
date: YYYY-MM-DD
status: proposed | analysis-only | decision-pending | pending-<reason>
result: profit | loss | breakeven | pending
structures: [list]
tags: [list]
archive_eligible_after: YYYY-MM-DD   # optional — defaults to `date` + 30 days
calls: [list]                        # optional — structured falsifiable calls, see below
regime: <summary>                    # optional — see below
---
```

- `status` is **analysis intent only** per hard rule #9 (`proposed` / `analysis-only` / `decision-pending`) — never trade execution. Execution lives in the broker side (IB + Futu pull).
- `archive_eligible_after` is the date on which this file becomes eligible for cold-storage migration. **Default = `date` + 30 days** (no need to set it explicitly). Set it later if the file is still load-bearing — e.g., when the analysis covers a position that doesn't expire until next quarter, set `archive_eligible_after: 2026-09-19` (post-expiry) so it stays in the active subtree through the position's life.
- `calls` — **write one entry per falsifiable claim made in the 决策块** (hard rule #10), pipe-delimited: `"TICKER|call_type|direction|structure|tier|crowding_flags|opposite_case_first|horizon_days?"`. `call_type` ∈ `directional` / `vol_regime` / `structure`; `direction` ∈ `+1`/`-1`/`0`; `structure` and the trailing three fields may be left empty (`||`) for non-structure / pre-doctrine calls. `tier` is the aggression tier from 决策块's 进攻程度 (`NO_TRADE`/`PROBE`/`SMALL`/`NORMAL`/`HIGH_CONVICTION`/`EXCEPTIONAL`); `crowding_flags` is the count from the crowding check; `opposite_case_first` is `true` when it fired; `horizon_days` (optional 8th field, trading days) sets the verdict horizon — omit for the default (`directional` 21 / `vol_regime` 10 / `structure` 21). 7-field entries remain valid. Example: `calls: ["NVDA|structure|-1|bear_call_spread|PROBE|3|true", "TSLA|directional|+1||NORMAL|0|false|21"]`. When present (even `calls: []`), this field takes full precedence over 复盘's prose-keyword classification for the whole file — it's the accurate source, not a fallback. Older archives without it still work via prose extraction.
- Every archived analysis adds `regime: <summary>` frontmatter, copied from
  the latest `references/private/market/regime-log.jsonl` line
  (`scripts.regime_snapshot.latest_regime()` — e.g.
  `regime: SPX all_contango | QQQ-SPX ivr +37.7 | gamma_flip n/a | hy_oas n/a`).
  This is what lets 复盘 answer "in which regimes do my calls actually work"
  — unanswerable before 2026-07-13 because regime was never persisted at call time.

Reports that the trader typically wants saved (but still requires explicit ask):

- Full ticker analysis (`分析 <TICKER>`)
- Position book review / `持仓 review`
- FCN/ELN/AQ/DQ evaluation with concrete deal numbers
- Macro / SPX hedge decision
- Pre-flight + YES/NO order trace (regardless of YES, NO, or abort)
- Roll / close decision on existing positions

The `references/private/` directory is **gitignored**; it's the trader's personal trade journal containing NLV / positions / fills. The public `references/ticker/` tree only holds anonymized framework-teaching case studies (e.g., `orcl-2026-06-fcn.md`). (Separately, `/private/` at project root holds `trader-profile.md` — also gitignored, but unrelated.)

Body must capture: TL;DR, Data snapshot (point-in-time, with sources), Analysis, Decision + reasoning, Gaps in data, empty **Outcome / Lesson** section for audit fill-in.

**Audit cadence**: trader (or skill on re-invocation against same ticker) revisits each `references/private/{ticker,market,review}/**/*.md` file at its named checkpoint (next ER / expiry / 30d for macro) and fills in the outcome section. Lessons that generalize get promoted to `references/pitfalls/NN-slug.md` (account-stripped). After the outcome is filled and the position resolved, the file is eligible for cold-storage migration on its `archive_eligible_after` date.

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

# IV term-curve regime (Workflow 1 L2 / Workflow 3 stage-2 (h) / Workflow 6 step 3b).
# Caller supplies ATM IV per held (or analyzed) expiry. Use
# atm_iv_from_chain_rows() if you only have raw UW chain responses.
.venv/bin/python -c '
from scripts.term_curve import label_regime, summarize_regime
atm = {"2026-07-17": 0.42, "2026-08-21": 0.55, "2026-09-19": 0.46, "2027-01-15": 0.48}
pairs = label_regime(atm)
for p in pairs:
    print(p["from_expiry"], "→", p["to_expiry"], p["regime"], "basis", round(p["basis"], 3))
print("aggregate:", summarize_regime(pairs))
# 2026-07-17 → 2026-08-21 contango basis 0.13
# 2026-08-21 → 2026-09-19 inverted basis -0.09
# 2026-09-19 → 2027-01-15 contango basis 0.02
# aggregate: mixed_contango_inverted
'

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

# Diagonal calendar (RUT 3-mode pricer with chain-vs-BSM fallback)
.venv/bin/python -c '
from scripts.diagonal_calendar import build_diagonal_calendar
snap = {"iv_atm_short": 0.28, "iv_atm_long": 0.30,
        "iv_rank": 35, "vrp_label": "NEUTRAL"}
out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=snap)
print(out["mode"], out["net_debit_dollar"], out["regime_check"]["matches_chosen_mode"])
for leg in out["legs"]:
    print(leg["action"], leg["strike"], leg["limit_price"], leg["mid_source"])
print("roll matrix at -5%:", [r for r in out["roll_matrix"] if r["spot_scenario"] == -0.05])
'

# Entry timing decision (morning vs EOD vs abort)
.venv/bin/python -c '
from datetime import datetime, timezone
from scripts.entry_timing import decide
snap = {"spot": 2300.0, "time_et": "10:00",
        "snapshot_taken_at": datetime.now(timezone.utc).isoformat(),
        "vix": 14.2, "vix1d": 13.8, "vix9d": 14.0,
        "premarket_gap": 0.003, "gex_flip": 2250.0, "net_dealer_gex": 1.0e9,
        "odte_put_premium": 5.0e6, "odte_call_premium": 4.0e6,
        "is_fomc_day": False, "is_monday_open": False, "is_opex_friday": False}
print(decide(snap, mode="rut_calendar"))
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
