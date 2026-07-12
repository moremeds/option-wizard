---
type: Runbook
title: Analysis Runbook — 分析 <TICKER>
description: The 8-layer ticker-analysis spine; every layer in order with its per-layer data source and decision output; opens with the Layer Coverage table; includes honest reporting of gaps when a data source is unreachable.
tags: [runbook, ticker-analysis, layer-coverage, 8-layer, gap-reporting]
timestamp: 2026-06-08T07:12:35Z
---

# Analysis Runbook — `分析 <TICKER>`

The end-to-end workflow the skill follows when the trader asks to analyze a
ticker for an income/hedge structure. Each layer below has a defined data
source, a defined compute step, and a defined decision output. Skip a layer
only when its inputs are unreachable, and report the skip explicitly to the
trader — incomplete coverage is allowed but must be flagged.

Source order (per CLAUDE.md + SKILL.md hard rule #2):
- **UW**: options data **only** — IV rank, RV, skew, IV term structure, max
  pain, GEX by strike, greeks by strike, dark pool, flow, interpolated IV.
- **TV via `finance-data-providers:tradingview-reader`**: price + technical
  indicators **only** — spot, OHLCV, volume bars, SMA(20/50/200), EMA, RSI,
  MACD, BBANDS, ATR, chart structure, news.
- **xenon**: account state — positions, balances, margin, via `/portfolio`
  + `/futu/portfolio` (IB MCP fallback).

Never recompute a number UW serves directly. Never use UW for price or
technical indicators (SKILL.md hard rule #2). Freshness: every quoted
number must be ≤ 1 trading day stale (SKILL.md hard rule #7).

---

## Required header on every ticker analysis: Layer Coverage table

Before any narrative, emit this table to declare what was pulled vs
skipped, source, and freshness. Anything marked `skipped` MUST also
appear under "What this analysis is missing" at the end.

```
| Layer | Status | Source | Data freshness |
|---|---|---|---|
| L0 Account state          | ✓ / skipped | xenon `/portfolio` + `/futu/portfolio` (IB MCP fallback) | live / T-1 / gap (>1 day = gap) |
| L1 Vol / dealer regime    | ✓ / skipped | UW                    | T-0 or T-1 / gap |
| L2 IV term + skew         | ✓ / skipped | UW                    | T-0 or T-1 / gap |
| L3 Price action           | ✓ / skipped | **TV ONLY** (no UW)   | live / T-1 / gap |
| L4 Tape (flow + dark pool)| ✓ / skipped | UW                    | T-0 or T-1 / gap |
| L5 Catalyst clock         | ✓ / skipped | UW + TV news          | T-1 / gap |
| L5.5 Fundamentals         | ✓ / skipped / n/a | UW + Massive (via `fundamental-analysis` skill) | annual FY (≤ 18 mo) / gap |
| L6 Structure pick         | ✓           | computed              | — |
| L7 Preflight              | ✓ / skipped | computed              | — |
```

Skipping a layer is OK when its source is unreachable. Silently dropping
one is not (SKILL.md hard rule #8).

---

## Layer 0 — Account state (xenon)

**Why first:** every downstream sizing and refusal depends on it.

**Pull:**
- `XenonClient.ib_portfolio()` — does the trader already hold the ticker?
  Fallback: `futu_portfolio()` for Futu-held positions; IB MCP if xenon is
  unreachable.
- xenon `/portfolio` account summary fields — `TotalCashValue`,
  `NetLiquidation`, `AvailableFunds`, `BuyingPower`, `InitMarginReq`,
  `MaintMarginReq`.

**Compute:**
- Margin utilization = `InitMarginReq / NetLiquidation`. Over ~50% means
  defined-risk only on any new add.
- Buffer after new trade = `AvailableFunds − new_position_margin`. Refuse
  if it would drop under ~$5,000.

**Decision:** is the trader's book healthy enough to add risk? If
`defined_risk_audit` already flags existing positions (e.g., CSPs failing
cash cover), every new short-premium position must be defined-risk.

---

## Layer 1 — Vol / dealer regime (UW)

**Why:** sets the structural backdrop. RICH vs CHEAP vol decides
sell-premium vs buy-premium. Gamma flip placement decides whether the
ticker is in a vol-dampening or vol-amplifying regime.

**Pull:**
- `get_market_state` — broad P/C ratio, market premium tilt
- `get_greek_exposure_by_ticker` (timeframe 1W) — net dealer gamma trend
- `get_greek_exposure_by_strike_expiry` — per-expiry GEX-by-strike (the
  one that matters for tactical walls — see "Per-expiry call wall" below)
- `get_max_pain` — pin levels across the expiry curve

**Compute (via `scripts.gex_levels`):**

```python
from scripts.gex_levels import compute_levels_per_expiry
# raw is the list returned by get_greek_exposure_by_strike_expiry
levels = compute_levels_per_expiry(raw, spot, call_wall_definition='oi_cluster')
# levels = {'2026-06-05': {gamma_flip, put_wall, call_wall}, ...}
```

**Per-expiry call wall is the trader convention.** Aggregating across all
expiries with `compute_levels(...)` is misleading for short-dated trade
windows because deep-OTM long-tail clusters dominate the aggregate.

`call_wall_definition='oi_cluster'` finds the strike above spot with the
largest positive `call_gex` — concentrated dealer-long-gamma resistance.
`call_wall_definition='net_neg_gex'` (default) looks for net-negative GEX,
which often returns `None` for high-momentum names whose net GEX stays
positive everywhere above spot.

**Compute VRP via `scripts.vrp`:**

```python
from scripts.vrp import compute_vrp
# IV: ATM IV from chain near trade expiry. RV: 21d realized close-to-close.
out = compute_vrp(iv, rv, with_label=True)
# {'vrp': float, 'label': 'RICH' | 'NEUTRAL' | 'CHEAP'}
```

**Decision:**
- Vol regime label drives the column in `references/strategies.md`'s
  regime × structure matrix
- Gamma flip vs spot drives directional bias: above flip = dealer long
  gamma (vol-dampening), below flip = short gamma (vol-amplifying)

---

## Layer 2 — IV term structure + 25Δ skew (UW)

**Why:** verifies that the trade-window expiry isn't sitting on a
front-loaded catalyst (would show as inverted term structure) and tells
you which side of the smile is structurally bid.

**Pull (Workflow 1 — new-position analysis):** `get_chains_for_expiry`
for 4-5 expiries spanning the trade window — typically front-week, trade
expiry, post-trade-expiry, post-ER. Limit ~30 strikes (sorted by volume
in UW output) to keep response small.

**Pull (Workflow 3 — position review mode):** the expiry list is **not**
the generic 4-5 span — it is the **actual set of held expiries** for the
ticker, plus the nearest weekly above the longest holding (anchor for
the term-curve extrapolation). Example: 6/4 TSLA book held 7/17 + 8/21
+ 1/15 → pull those three + one anchor like 6/12. ATM ± 3 strikes per
expiry is enough to read ATM IV; full chain is wasteful here. Build the
IV term curve over the held window and explicitly label
**contango / flat / inversion** per adjacent expiry pair.

Single-ticker IV rank or 52w IV percentile (as served by UW
`get_options/volatility` or IB `get_price_snapshot` field
`option-implied-volatility-historical-percentile-52-week`) is a
**point-in-time aggregate** — it does NOT reveal whether the trader is
short vol on the rich part of the curve or the cheap part. A position
review that quotes only IV percentile and skips the held-expiry term
curve is missing the most important Workflow-3 signal: whether one of
the held shorts sits on an inverted (catalyst-priced) chunk of the
curve. This was the gap in the 6/4 TSLA Futu review and is now codified
as required, not optional.

**Compute:**
- ATM IV per expiry = average of ATM call IV and ATM put IV. Use
  `scripts.term_curve.atm_iv_from_chain_rows(rows, spot)` to extract
  ATM IV from each `get_chains_for_expiry` response (auto-pivots the
  actual per-contract MCP row shape — one row per strike+option_type —
  and tolerates string-formatted IV fields). When 25Δ skew isn't needed
  (a term-curve-only check, e.g. Workflow 3/6), prefer
  `scripts.term_curve.atm_iv_by_expiry_from_term_structure` first — one
  `iv_term_structure(ticker)` call covers every listed expiry, falling
  back to the chain pull only for expiries it doesn't carry. See
  `review-framework.md` §"Open multi-expiry term-curve snapshot".
- Term-curve labels via **`scripts.term_curve.label_regime(atm_iv_by_expiry)`**
  — returns adjacent-pair labels (`contango` / `flat` / `inverted`) plus
  basis. Use `summarize_regime(pairs)` for a single aggregate label
  (`all_contango`, `all_inverted`, `mixed_contango_inverted`, etc.) to
  drop into stage-2 book-review or 复盘 tables. The script is the single
  source of truth — do NOT inline LLM-judge contango / inversion; that
  produced inconsistent labels across runs.
- 25Δ skew at the trade expiry = (25Δ call IV) − (25Δ put IV). Equity
  convention is **negative** (puts richer). Positive skew is unusual and
  signals heavy retail call demand (TSLA / NVDA / COIN behavior).

**Decision:**
- Inversion at the trade window = catalyst priced inside → defer the
  trade or shrink size.
- Contango + skew not strongly negative = clean entry for short premium.

---

## Layer 3 — Price action (TV ONLY — never UW)

**Why:** structural levels + tape posture. A range-bound chop reads
differently than a trending breakout; trade-window structure depends on
which one is current.

**Source rule (SKILL.md hard rule #2):** All price + technical indicators
come from **TradingView via `finance-data-providers:tradingview-reader`
only**. UW indicator endpoints (`get_extended_technical_indicator`,
`get_ticker_indicator_series`) are **forbidden** for this layer — their
series typically lag by weeks and were the root cause of three back-to-back
analyses (NVDA / QQQ / SPY 2026-06-03 to 06-04) using April-vintage RSI /
ATR / SMA values labelled as "today's estimates." That class of error is
banned.

**Pull (TV — mandatory):**
- `opencli tradingview chart-state` — current spot, daily candles, volume
  bars (always T-0 or T-1)
- `opencli tradingview chart` with `SMA(20)`, `SMA(50)`, `SMA(200)`, `EMA(21)`
  overlays — moving averages + crosses
- `opencli tradingview chart` with `RSI(14)`, `MACD(12,26,9)`, `BBANDS(20,2)`,
  `ATR(14)` — momentum + vol envelope
- `opencli tradingview news --symbol NASDAQ:<TICKER> --limit 8` — recent
  headlines for catalyst-clock validation AND for the 4-signal bullish veto
  check in Layer 6 (signals #1, #2, #3 all read from news)
- Always include **volume bars** (daily + intraday session VWAP). The trader
  has explicitly flagged that options analysis must always carry volume +
  MA technicals — not optional.

**Do not pull `tradingview watchlists`.** The trader organizes watchlists
for their own reasons (sector grouping, idea tracking) — membership and
color flags encode no directional signal. Earlier versions of this runbook
suggested using them as a "tiebreaker"; that guidance is rescinded.

**TV setup gotchas (encountered live, codified here):**

- **opencli ≥ 1.8.0 required.** Older opencli rejects the plugin's
  `access` declarations. Check with `opencli --version`; upgrade with
  `npm install -g @jackwener/opencli@latest`.
- **Port 9222 collision** is common when `chrome-devtools-mcp` is loaded
  as an MCP server (very typical in Claude Code sessions). Chrome holds
  9222; TV launch on the default port silently fails. Workaround: pick a
  different port (9224 used in practice) and:
  ```bash
  opencli tradingview launch --port 9224
  export OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9224  # data commands read this
  ```
  Persist the env var in **`~/.zshenv`** (not just `~/.zshrc`) so
  non-interactive subprocess shells also pick it up.
- **Stale TV processes survive polite quit.** A previously-detached
  `TradingView` binary (e.g., from a `--help` probe) is not caught by
  `osascript ... quit`, and macOS `open -a TradingView --args ...` will
  silently skip re-spawning. If `tradingview launch` returns
  `ready: false`, hard-kill first: `pkill -KILL -f "TradingView"`, wait
  2-3 seconds, then re-launch.

If TV is still unreachable after the above, **do NOT fall back to UW
indicators.** UW's `get_extended_technical_indicator` series is
chronically stale (weeks-old, not days-old) and using it for L3 was the
exact failure mode that triggered SKILL.md hard rule #2. Instead:

1. Mark Layer 3 as **`skipped`** in the Layer Coverage table.
2. Surface "TV unreachable; price action layer not run" under §"What this
   analysis is missing."
3. Ask the trader whether to proceed without L3 or pause until TV is fixed.
4. Veto-check signals #1-3 stay "Unknown" → conservative (non-firing) read.

If the trader explicitly authorizes a UW-indicator fallback (rare,
documented as exception in the report), every UW indicator value MUST be
labelled with its `as_of` date and a freshness flag (`current` if ≤ 1
trading day, `STALE` otherwise). Stale values do not get extrapolated.

**Compute:**
- Distance to 200DMA — uses the band table in `price-action-framework.md`
  to map onto bull/bear bias bucket.
- Recent swing high / swing low from the candle data. Note any failed
  retests (3× failure at the same level = strong tape resistance).
- RSI level + trajectory (overbought / oversold / mean-reverting).

**Decision:**
- 200DMA distance + RSI determine directional row in the regime ×
  structure matrix.
- Tape posture (trending vs range-bound) modifies structure choice:
  range-bound favors theta sellers, trending favors directional debits.

---

## Layer 4 — Tape (UW + optional Massive)

**Why:** confirms or contradicts the structural read. A bullish structural
setup with bearish dealer flow is a yellow flag.

**Pull (UW, primary):**
- `get_flow_alerts` (filter `ticker_symbol`, last ~15-20 alerts) — rule-
  triggered unusual activity. Look at expiry distribution and side
  dominance.
- `get_flow_per_expiry` — call vs put premium concentration per expiry.
  Look for inversions in the curve.
- `get_dark_pool_trades` (filter `ticker_symbol`, `min_premium` ≥ $500K) —
  institutional block flow. Note level + recency.

**Optional augment (Massive, requires `$MASSIVE_API_KEY`):**
- `GET /stocks/v1/short-volume?ticker=<TICKER>&limit=10` — DAILY short
  volume broken out by venue (NYSE / NASDAQ Carteret / NASDAQ Chicago /
  ADF). Carteret hosts Citadel + Virtu execution stacks; an unusual
  Carteret-side spike with no NYSE follow-through is HFT-driven
  positioning, not directional. UW gives bi-weekly short interest only —
  Massive's daily granularity catches positioning shifts UW misses by
  weeks. Mark this row `augment-skipped` if `$MASSIVE_API_KEY` unset; do
  not surface as a primary gap (it's optional).

**Decision:**
- Heavy call premium dominance at trade expiry → bullish flow tailwind.
- Long-dated put cluster → structural hedging, not directional signal.
- Dark pool blocks at levels close to current spot (within ~1%) =
  institutions actively positioning; further away with no follow-through
  = stale.

**Critical caveat (UW tool docs):** volume ≠ open-interest growth. The
5-25× VOL/OI ratios common in flow alerts can be intraday churn, not new
positioning. Confirm with next-morning OI before drawing positioning
conclusions.

---

## Layer 5 — Catalyst clock

**Why:** every short-premium position must have its expiry placed
**outside** binary catalysts. SKILL.md hard rule #4 (21 DTE blocking
review) is a backstop, not the primary gate.

**Pull / derive:**
- Next earnings date (from flow alert `next_earnings_date` field, UW
  company info, or TV news)
- Upcoming OPEX dates (monthlies: 3rd Friday; weeklies: every Friday)
- SPX quad witching (March / June / September / December 3rd Friday)
- Sector-specific binaries (FDA dates, central bank meetings, etc.)

**Decision:**
- Trade expiry must precede next earnings by ≥ 7 days (5 too close — IV
  pump already starting). Larger buffer (12+ days) preferred.
- 21 DTE review date matters — schedule the natural reassessment point
  to fall on a stable session (avoid scheduling review on quad witching
  if possible; if unavoidable, plan the close/roll choice in advance).

---

## Layer 5.5 — Fundamentals snapshot (optional sub-layer)

**Why this is a sub-layer, not a primary layer:** vol / dealer / tape / catalysts (L1-L5) are the load-bearing inputs for every option structure pick. Fundamentals are load-bearing only for a subset of trades — longer-dated theses, "is this name expensive vs peers" questions, structures where the trader is OK owning the stock at strike (CSP, FCN), names where the entire setup hangs on a quality / re-rating thesis.

**Skill that runs this layer:** `fundamental-analysis` (quick mode). Do **not** duplicate its data-pull logic here — invoke the skill with `--depth=quick` and paste its 3-section output (Snapshot / Fundamentals / Verdict) into this layer's block. See `plugins/option-wizard/skills/fundamental-analysis/SKILL.md` for the full mode taxonomy.

**When to run:**
- Trade thesis depends on company quality (turnaround, value re-rate, "why is PE so low")
- Structure has the trader on the hook for owning the stock (CSP near support, FCN with KI close to spot, deep ITM covered call where assignment is plausible)
- Trade duration ≥ 60 DTE or any LEAPS — fundamentals dominate over short-term vol mechanics at this horizon
- Trader explicitly asks ("基本面怎么样", "PE 偏不偏贵", "is this cheap")

**When to skip (default):**
- Short-DTE event play (≤ 30 DTE around earnings / FOMC / catalyst) — fundamentals don't move in this window
- Pure vol-regime structure (iron condor / jade lizard / put credit spread for VRP harvest) where the thesis is "skew is rich" not "company is cheap"
- M7 + QQQ buy-and-hold names per trader profile — fundamentals are known-good; no structural re-rate thesis is being made

Mark this row `skipped` in the Layer Coverage table when not run, or `n/a` for the M7/QQQ buy-and-hold carve-out (different reason: not "couldn't get data" but "thesis doesn't depend on it").

**Decision output (feeds L6):**
- Sizing modifier: high conviction + clean fundamentals → top of the 2-5% NLV band; "fundamentals say story is broken but vol setup attractive" → bottom of the band
- Structure modifier: weak fundamentals AND short-premium structure on the table → require defined-risk wings tighter than usual (no jade lizard, no naked-leg lizard variants)
- Veto: fundamentals returned `BLOCKED — insufficient data` AND trader was relying on a value re-rate thesis → refuse the structure pick and surface the gap

**Token cost note:** quick mode pulls 5 UW endpoints in parallel (`get_company_info`, `get_income_statements`, `get_cash_flows`, `get_ticker_performances`, `get_analyst_ratings`) plus TV spot — quick mode does NOT pull Massive (keep this layer cheap). ~10-30K tokens. If the trader asks for deep mode (peer matrix, scenario EV), that's a standalone report — exit the ticker-analysis flow and run `fundamental-analysis --depth=deep` directly; deep mode is where Massive augments (related-companies peer set, `source_filing_url` for SEC links, news sentiment) actually pull. Don't try to inline a 10-section report into L5.5.

---

## Layer 6 — Regime classification + structure pick

**Inputs from above:**
- Vol regime label (Layer 1, VRP)
- Directional bias (Layer 3, 200DMA distance + tape)
- Term structure shape (Layer 2)
- Catalyst clearance (Layer 5)
- Fundamentals conviction (Layer 5.5, if run) — sizing band + structure-tightening modifier

**Decision:** this layer is where `references/decision-doctrine.md`
(hard rule #10) fires. Before touching the matrix, run doctrine Phase C
(competing hypotheses: bull / base / bear / vol-up / vol-down / no-trade)
and Phase D (disconfirmation + crowding check — one-sided consensus means
the opposite case is written first) on the evidence from Layers 1–5.5.
Then map onto the regime × structure matrix in `references/strategies.md`
and:

1. Run the **4-signal bullish veto check** (`strategies.md` §"Strong
   bullish conviction veto"):
   - Post-ER absorbed gap-up?
   - 3+ independent channel-check sources?
   - Validated thematic re-rate?
   - Term structure inversion?
   - ≥3 fire → refuse iron condor / jade lizard / calendar; recommend
     CSP / bull put spread / long call instead.

2. Pick **strikes anchored to the structural levels** from Layer 1:
   - Short put at or just below the per-expiry put wall
   - Short call at or just above the per-expiry call wall
   - Long protective legs outside the secondary cluster (next put wall
     down / next call wall up)
   - Always defined-risk per SKILL.md hard rule #1

3. Pick **expiry** at 30-45 DTE, pre-catalyst, with the 21 DTE review
   date falling on a stable session.

4. Compare **≥2 economically distinct structures** (doctrine Phase E) —
   direction/Δ, convexity, θ, vega, capital, max loss, catalyst
   sensitivity, portfolio fit — and name the losing alternative in the
   output.

5. Pick **size** via the aggression tier (doctrine Phase F: PROBE ≤1% /
   SMALL 1–2% / NORMAL 2–3.5% / HIGH_CONVICTION 3.5–5% / EXCEPTIONAL 5%
   hard cap, of NLV at max loss), then take min of:
   - tier band % of NLV at max loss
   - 25% of `AvailableFunds`
   - integer position respecting margin reserve after entry

6. Close the analysis with the **决策块 decision block** (doctrine
   template — includes 进攻程度 tier, 失效条件, 数据可信度) before
   offering the Layer 7 preflight.

---

## Layer 7 — Pre-flight + YES/NO

**Required structure (SKILL.md hard rule #3):**
- Legs: exact symbol, action, qty, limit price
- Mid price, net debit/credit, max loss, max gain, breakeven, margin
- P/L matrix at expiry across spot −20 / −10 / −5 / 0 / +5 / +10 / +20%
- Account verification block (cash, NLV, margin used, available after)
- UW regime check block (vol, dealer, walls, term, skew)
- Liquidity check (bid-ask spread % per leg from IB or UW chain)
- Catalyst clock (next ER, OPEX, 21 DTE review date)
- Refusal / override conditions

**Exactly one YES/NO question.** YES = submit via `ib_insync.placeOrder`
(option combos) or `create_order_instruction` (stock drafts). Anything
other than YES = abort.

**After YES:**
- Build the combo bag order
- Submit limit at mid (or slightly worse — avoid touching ask on entry)
- Submit TP bracket at 50% of credit (close to 50% max gain)
- Submit SL bracket at 2× credit (= full max loss for spreads, per
  SKILL.md hard rule #6)
- Report fill price and order IDs

---

## Layer 8 — Archive (on explicit ask, after the screen output)

**Why:** every analysis is a future audit point. The trader needs a record of
what data we had, what we concluded, and what we missed — so future-us can
compare prediction vs outcome and harvest pitfalls. **But the trader reviews
the screen output first and decides whether the analysis is worth preserving.**

**Write to** `references/private/{ticker|market|review}/{date}-{ticker}-{long|short|mixed}-{highlight}.md`,
gitignored, trader's personal journal, **only when the trader explicitly asks**
("save", "保存", "archive", "存档"). SKILL.md §"Reporting & archive" has the
file format, subdir routing, and the master rule. This layer runs that rule on
demand, not automatically.

**Capture** (locked at point of analysis so a future replay is possible):

1. **Frontmatter** — `ticker / event / date / status / result / structures / tags`
2. **TL;DR** — one paragraph
3. **Data snapshot table** — every metric used in layers 1-6, with source
4. **Per-layer execution trace** — what each layer concluded
5. **Decision + reasoning** — including which Path (A/B/C/...) was presented
   and which (if any) the trader picked
6. **Gaps** — list every data source that returned empty / stale / unreachable,
   so a future audit knows what was extrapolated vs verified
7. **Empty Outcome / Lesson section** — to be filled at the named audit
   checkpoint (next ER / expiry / 30d / specific date depending on the trade)

**Always archive, regardless of outcome:**
- Trader said YES + order submitted → archive with preflight + fill data
- Trader said NO → archive with preflight + abort reason
- Mid-runbook abort (data gap, tool failure) → archive with reduced data + abort reason
- WAIT decision (no trade) → archive the analysis + the wait conditions

**Naming**: `<slug>-YYYY-MM-DD-<event>.md` where `<event>` is a 2-4 word
hyphenated descriptor (e.g., `premarket`, `short-put-tp-close`,
`sell-put-roll-decision`, `fcn-counter-offer`).

**Audit promotion**: when filling in §Outcome / Lesson reveals a
forward-applicable rule, promote it to `references/pitfalls/NN-slug.md` with
all account-specific numbers stripped.

---

## Honest reporting of gaps

When a layer's data source is unreachable (TV offline, IB market data
delayed, UW endpoint times out), the analysis MUST list the gap explicitly
under a "What this analysis is missing" heading at the end of the report.
Trader judgment requires knowing what's verified vs what's missing — never
paper over a missing layer with extrapolation alone.

Common gaps:
- TV news offline → can't validate post-ER absorption signal
- IB market data closed → bid/ask shown as UW last_price (mark-to-market
  end of prior session)
- UW chain too sparse → strike not in top-N-by-volume; OI/liquidity
  inferred from neighboring strikes
- 200DMA from UW only goes ~6 weeks back — note the extrapolation rate

---

## Worked end-to-end example

See `references/ticker/` for case studies. The TSLA 2026-06-03 analysis
during the v0.1.0 acceptance run is the canonical demonstration of this
runbook (data sources used: UW for layers 1-2-4-5, UW indicators for
layer 3, IB for layer 0; TV blocked then fixed during the same session).
