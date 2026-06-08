# Workflows Overview

Routing index for the 6 distinct workflows. Read this **first** when a
trader request comes in — match the request to a workflow, then drill
into the linked deep-reference file for the per-step detail.

**Cross-workflow constraints (apply to every workflow):**

- **Source split** (hard rule #2): UW = options data only; TV = price +
  technicals only; IB = account state. UW `get_extended_technical_indicator`
  / `get_ticker_indicator_series` are **forbidden** for L3 analysis.
- **Freshness** (hard rule #7): every quoted number ≤ 1 trading day stale,
  else it's a gap.
- **Defined-risk only** (hard rule #1): refuse naked short calls /
  margin-leveraged short puts.
- **Archive is opt-in** (SKILL.md §Reporting & archive): only write to
  `references/private/{ticker|market|review}/` when the trader says "save / 存档".

---

## Workflow 1 — 分析个股 (`分析 <TICKER>` for individual equity)

**Spine:** `analysis-runbook.md` end-to-end (8 layers).
**Opens with:** Layer Coverage table (hard rule #8).
**Ends with:** "What this analysis is missing."

| # | Layer | Pull | Source | Output |
|---|---|---|---|---|
| 1 | L0 Account | NLV, cash, available, margin, existing exposure in this ticker | IB MCP | Can we add risk? Is existing book healthy? |
| 2 | L1 Vol/Dealer | IV rank, RV, VRP, per-expiry GEX-by-strike, max pain term structure | UW | RICH/NEUTRAL/CHEAP label; gamma flip vs spot; per-expiry put/call wall |
| 3 | L2 IV term + skew | ATM IV at 4-5 expiries, 25Δ skew | UW | Term contango/inversion; skew vs ~-0.05 baseline |
| 4 | **L3 Price action (TV ONLY)** | Spot, OHLCV, volume bars, SMA(20/50/200), RSI(14), MACD, BBANDS, ATR(14), news | **TV via `finance-data-providers:tradingview-reader`** | Distance to 200DMA; trending vs range-bound; swing high/low; catalyst headlines |
| 5 | L4 Tape | Flow alerts, flow per expiry, dark pool blocks (≥$500K) | UW | Call/put premium tilt; dark-pool level + recency |
| 6 | L5 Catalyst | Next ER, OPEX, quad witching, sector binaries | UW company info + TV news | Trade expiry must precede ER by ≥7 days (12+ preferred) |
| 7 | L6 Structure pick | (inputs above → regime × structure matrix) | computed | Run **4-signal bullish veto** (`strategies.md`); strikes anchored to put/call wall; 30-45 DTE; size = min(2-5% NLV, 25% available) |
| 8 | L7 Preflight + YES/NO | Legs, mid, max loss/gain, BE, margin, P/L matrix ±5/10/20%, account check, UW regime check, liquidity, catalyst clock, bracket (TP 50% / SL 2×) | `scripts.ib_order::build_preflight` | Exactly one YES/NO; YES → submit + brackets |
| 9 | L8 Archive (opt-in only) | All of above + decision + gaps | gitignored `references/private/ticker/{date}-{ticker}-{long|short|mixed}-{highlight}.md` | Outcome/Lesson section left empty for audit |

---

## Workflow 2 — 分析指数/大盘 (SPY / QQQ / SPX / IWM macro view)

**Spine:** same `analysis-runbook.md`, with these substitutions:

| Layer | Difference from Workflow 1 |
|---|---|
| L0 | Also compute **net delta beta-weighted vs NLV**. > 0.5× NLV → macro hedge trigger fires (see `strategies.md` §"Macro hedge trigger heuristics") |
| L5 | Catalyst focus = FOMC / CPI / NFP / quad witching, not ER. Mark SPX quad (3rd Friday of Mar/Jun/Sep/Dec) |
| L6 | 4-signal bullish veto less relevant (no ER absorption signal on an index). Replace with **VIX regime + dealer gamma flip vs index spot**. Structure default = SPX/SPY put spread, VIX call calendar, collar — not CSP |
| L7 | **Macro cost cap (hard rule #5)**: total annualized hedge cost ≤ 1.5% NLV. Use `scripts.macro_hedge::build_macro_hedge(portfolio_notional, hedge_horizon_days, scenario, structure, snapshot)`. If output > 1.5% NLV → shrink size or pick cheaper structure |

**Not applicable:** FCN hard rule #5 (FCN never routes here).

**Output:** either hedge recommendation + preflight, or explicit "no hedge yet" conditions (e.g., "fire when SPX touches 200DMA").

---

## Workflow 3 — 分析仓位 ("持仓 review" / "我账户里这些仓位有没有问题")

**Does NOT use the 8-layer runbook.** Uses `SKILL.md §"Book-review output structure"` — 4 stages, no mid-flow YES/NO.

| Stage | Action | Tooling |
|---|---|---|
| **1. Data pull (ALL configured brokers)** | (a) IB MCP primary: `get_account_summary` + `get_account_positions` + `get_account_orders`. (b) Any secondary brokers documented in `private/trader-profile.md` — run the pull command specified there (user-provided CLI / MCP / Python wrapper), then translate the output to IB shape (`contract_description` / `position` / `market_price`) before feeding into the audit pipeline. Report broker pull success/failure + data gaps (e.g., if a CLI report omits cash balance, note it as a gap and fall back to a separate pull if needed) | IB MCP + user-provided secondary broker connector(s) |
| **2. Book-level analysis** | (a) Concentration: abs MV % + Δ-1 notional vs NLV. (b) Net Greeks: Δ / Γ / Θ / V + Δ-1 single-name bars. (c) Every leg listed. (d) **Defined-risk audit verdict** (`scripts.defined_risk_audit::audit_book`) with $20 strike-width false-positive callouts. (e) 22-45 DTE watchlist. (f) Catalyst clock per ticker (ER, FOMC). (g) Data quality flags (stale price, missing field). (h) **IV term verification across held expiries** — for any ticker with positions across ≥2 expiries, pull ATM IV at each held expiry (`get_chains_for_expiry`, ATM ± 3 strikes per expiry) and build the IV term curve over the actual exposure window. Flag contango (normal) vs inversion (catalyst priced into one of the held expiries). Single-ticker IV rank / 52w percentile is NOT a substitute — see `analysis-runbook.md` L2 §"Position-review mode" | `scripts.manage_positions --audit-only --no-email` (or call constituents directly) + `get_chains_for_expiry` per held expiry |
| **3. NO mid-flow decision** | 21 DTE positions, approaching-21 DTE, ER catalyst, large shorts, data anomalies — **observed in stage 2, NOT acted on yet** | — |
| **4. Consolidated Action items (at the END, all together)** | 4 groups: **P1, P2, …** position-level (close/roll/hold menu inline); **D1, D2, …** data quality; **R1, R2, …** book-level risks (concentration, macro delta, cover failure); **I1, I2, …** infra. Each line ends with trigger phrase ("P1 submit" / "D2 verify"). **Wait** for trader to pick → then hard-rule-#3 preflight expands | — |

**Edge case:** structurally dangerous position (naked short call, undefined risk, gamma blow-up imminent) → surface as **URGENT** at top of Action items. Still no auto-preflight; trader still picks.

**Two reinforcing rules:**
- **AT THE END** — never interrupt stage 2 with a single position's YES/NO.
- **ALL TOGETHER** — never drill P1 → wait → P2 → wait …; present the full menu, trader picks one or many.

---

## Workflow 4 — 分析 FCN ("PB 给我报了 X% coupon on Y")

**Hard rule #5: FCN never routes through IB.** Output = 8-item PB checklist + 70/75/80/85% strike ladder + fair-vs-quoted verdict + bilingual counter-offer email. **Spine:** `fcn-framework.md`.

| # | Step | Tooling / Source |
|---|---|---|
| 1 | Pull **UW snapshot**: `iv_rank`, `volatility/realized`, `historical-risk-reversal-skew`, `volatility/term-structure`, `max_pain`, `spot-exposures/strike` → derive gamma flip / put wall / call wall. Also pull **5y max drawdown** (KI buffer input). | UW |
| 2 | Pull **TV chart + news**: spot confirmation, 200DMA, last 30 days price action, in-tenor catalysts (ER, FDA, regulatory) | TV |
| 3 | Run `scripts.fair_coupon::analyze_fcn(ticker, strike_pcts=(0.70, 0.75, 0.80, 0.85), tenor_months, observation_months, pb_quoted_coupon, snapshot)` → 4-rung ladder with checklist + verdict (`fair` / `rich` / `cheap`) per rung | `scripts.fair_coupon` |
| 4 | **8-item PB checklist** (each rung): (1) strike vs gamma flip; (2) markup vs IV rank — PB coupon ≥ 25% model is floor, <25% = predatory FAIL; (3) KI buffer vs 5y max DD (≥10pp cushion); (4) IV rank ≥ 50 threshold (else switch to listed monthly CSP); (5) 25Δ skew penalty (<−0.25 → demand +3-5pp coupon); (6) tenor anchor (INFO: annualized → $ over expected alive duration); (7) liquidity / no secondary (INFO, size ≤ 10% liquid NLV); (8) issuer credit risk (INFO, PB parent senior unsecured + 5y CDS) | `_checklist` in `fair_coupon.py` |
| 5 | **Fair coupon math**: model `single_name_ki_prob ≈ 2·Φ(ln(B)/(σ·√T))` × LGD → annualized fair. **Institutional fair ≈ 50-65% × model**; **retail PB fair band ≈ 25-40% × model**. PB quote <25% × model = predatory | `scripts.fair_coupon` |
| 6 | **Worst-of basket** (if 2-name): `analyze_fcn_basket` runs MC for `p_ki_either`. Basket coupon must ≥ worst-single coupon × (1 + diversification premium); premium ≥ (1−ρ)·0.30·fair_worst_single. Below = PB pocketing diversification | `scripts.fair_coupon::joint_ki_prob_mc` |
| 7 | **Verdict + counter-offer email**: any rung with FAIL → `build_counter_offer_email` auto-attaches (Chinese first, English second). WARN-only rung does not (trader chooses) | — |
| 8 | **Decision tree**: (a) coupon ≥ 30% model fair **AND** first 5 checklist items all PASS/WARN (no FAIL) → take; (b) else **walk**, switch to 30-45 DTE listed short put / bull put spread where pricing is transparent | — |
| 9 | Archive (opt-in only): `references/private/ticker/{date}-{ticker}-long-fcn-counter-offer.md` with PB original quote + ladder + verdict + sent email | gitignored |

**FCN hard-ban conditions** (use listed options instead): IV rank <50, in-tenor ER / FDA / regulatory binary, need roll flexibility, want gamma scalp.

---

## Workflow 5: AQ / DQ quote evaluation

**Trigger phrases:**
- Chinese: `"PB 给我报了 <TICKER> 的 AQ, X% strike, Y% KO"`, `"PB 给我报了 DQ"`, `"评估这个 accumulator 报价"`, `"decumulator 怎么 counter"`
- English: `"evaluate aq quote"`, `"evaluate dq quote"`, `"negotiate accumulator"`

**Pipeline (6 steps):**

1. **Refusal red-line check** — `aq-dq-framework.md` §6. Six hard refusals (doubling ≥ 3×, IV rank < 30 + AQ, KO < 1 ATR, single notional > 10% NLV, tenor > 18M, ER in tenor midpoint). If ANY triggers, output `decision='REFUSE'` + reasons + stop. No chain pull.
2. **Chain pull mode selection** — live-trade mode (trader says "PB just quoted me", "30 min decision") → IB Gateway chain. Analytical mode (default) → UW chain. Both modes additionally pull UW IV rank, RV, skew, GEX, max pain.
3. **Fair-value breakdown** — `fair_aq_dq.analyze_quote`. Decomposes into chain-priced legs (put at strike, call at KO, deep-OTM tail put) + barrier-adjusted contributions. Returns `markup_pp` + `breakdown` + `data_provenance` (every numeric field tagged).
4. **Term Pareto optimizer** — `fair_aq_dq.optimize_terms`. Sweeps 4 parameters (tenor, KO%, doubling, obs_freq); returns variants sorted by `markup_reduction / pb_concession_difficulty`.
5. **Bilingual counter-offer email** — `fair_aq_dq.build_counter_offer_email`. Chinese first, English second, concrete concession asks (target markup 1.5pp).
6. **Present + verdict** — 8-item PB checklist → breakdown → Pareto → email → final `decision` in `{REFUSE, COUNTER, ACCEPT_IF_MUST}`. Do NOT route through IB (hard rule #5).

**Routes to:**
- `references/aq-dq-framework.md` — domain knowledge (8 sections)
- `scripts/fair_aq_dq.py` — pure-function math
- `references/ticker/aq-example-case.md` — synthetic public case study walking through all 6 steps with concrete numbers

---

## Workflow 6 — 复盘 (weekly / monthly review of past calls + trades)

**Trigger phrases:**
- Chinese: `"复盘"`, `"本周复盘"`, `"本月复盘"`
- English: `"weekly review"`, `"monthly review"`, `"review my recent calls"`

**Scope (intentional narrow):** directional calls + vol regime calls +
listed-options structure recommendations + actual stock/listed-option
trades. **FCN / AQ / DQ are explicitly out of scope** — PB structured
products audit separately through their own counter-offer / refusal
workflows. Archive files tagged `structures: [fcn|aq|dq|accumulator|
decumulator|eln]` are filtered at the extraction stage.

**Cadence:** two separate workflow invocations.

| Cadence | Window | Use case | Output emphasis |
|---|---|---|---|
| Weekly review | 7 calendar days back | Micro-feedback: did this week's calls hold up? What position changes happened? | Layer A per-call scorecard + Layer B trade log + Layer C advisory observations |
| Monthly review | 30 calendar days back | Pattern detection: systematic miss on a call type / ticker / regime? | Everything above + Layer A pattern analysis (hit rate by call type / ticker / regime) + skill rule suggestions |

**SKILL.md hard rule #9 — source separation (every 复盘 run):**

| Layer | Source | Output |
|---|---|---|
| A | `references/private/{ticker,market,review}/**/*.md` (archive only, recursive) | Directional verdict, hit rate. Never inferred to imply a trade. |
| B | **IB MCP + Futu CLI** (both brokers required) | Trade flow, execution markout, realized P&L. Only legit source. |
| C | Trader / LLM judgment | Advisory observations linking A ↔ B. No algorithmic scorecard. |

**Pipeline (5 steps):**

1. **Archive scan (Layer A)** — recursively walk `references/private/{ticker,market,review}/**/*.md` for files
   with `date` in window; skip PB-product files; classify each as
   directional / vol_regime / structure call.
2. **Call markout (Layer A)** — for each call, compute markout at fixed
   horizons **T+1d / T+5d / T+10d / T+21d / T+45d**. Directional uses
   `signed_dir × (spot_T / spot_0 − 1)`; vol regime uses `signed_dir ×
   (iv_rank_T − iv_rank_0)`; structure uses delta-1 spot proxy (Phase
   1) or BSM mark (Phase 2+). Aggregate via `aggregate_call_markout`.
3. **Trade flow (Layer B) — BOTH brokers required.** Pull IB
   (`get_account_trades`) + Futu (`portfolio-analyser` CLI), feed into
   `parse_ib_trades` + `parse_futu_trades`. Compute `compute_trade_markout`
   per fill (D1 excludes closes via `realized_pnl != 0`).
   Aggregate via `aggregate_trade_markout`.
4. **Cross-cut advisory (Layer C) — opt-in.** Trader (or LLM) supplies
   judgment-only observations linking specific Layer A calls to Layer B
   trades. **No automatic `followed × correct` quadrant.** Each
   observation carries `layer_a_refs` + `layer_b_refs` + optional
   `propose_action_item=True` flag.
5. **Auto-emit action items + writebacks** — verdict block appended to
   each source file's empty `## Outcome / Lesson` section
   (idempotent). WRONG calls generate pitfall drafts in
   `references/pitfalls/_drafts/` for trader review. Action items
   (S/P/T/D groups) at END only, never mid-flow.

**Verdict thresholds** (qualitative for now — quantify later when
N ≥ 50 calls):

- Directional: ±2% noise band at T+21d → CORRECT / NEUTRAL / WRONG
- Vol regime: ±5 IV rank pts at T+10d
- Structure: P/L sign at T+21d (no noise band — already normalized)

**Routes to:**
- `references/review-framework.md` — full design (3-layer architecture, v0.3)
- `scripts/retrospective.py` — pure functions + CLI orchestrator
  (`.venv/bin/python -m scripts.retrospective --window weekly|monthly`)
  + `parse_ib_trades` / `parse_futu_trades` broker adapters
- `tests/test_retrospective.py` — markout sign convention, scope filter,
  broker parsers, writeback idempotency, source-separation regression guard

**Out of scope (explicit):** FCN / AQ / DQ. These products' P/L
decomposition (path-truncation on KO, doubling tail, observation
cadence) doesn't fit the horizon-markout shape and their refusal
verdicts have their own checklist accountability via Workflows 4 and 5.

---

## Routing decision flowchart

```
Trader request
│
├─ "分析 <TICKER>" / "evaluate <ticker> for <structure>"
│   ├─ Is ticker an index (SPY/QQQ/SPX/IWM/VIX)? → Workflow 2
│   └─ Else → Workflow 1
│
├─ "持仓 review" / "我账户里这些仓位有没有问题" / "review positions" → Workflow 3
│
├─ "PB 给我报了 ... FCN" / "negotiate fcn quote" → Workflow 4
│
├─ "PB 给我报了 ... AQ / DQ" / "evaluate aq quote" / "evaluate dq quote" → Workflow 5
│
├─ "SPX 大盘对冲" / "size spx hedge" → Workflow 2 (L0 trigger + L7 macro hedge)
│
├─ "复盘" / "weekly review" / "monthly review" → Workflow 6
│
└─ "<TICKER> close 还是 roll" / 21 DTE blocking → Workflow 3 stage 4 (Action items menu)
```
