# Analysis Runbook — `分析 <TICKER>`

The end-to-end workflow the skill follows when the trader asks to analyze a
ticker for an income/hedge structure. Each layer below has a defined data
source, a defined compute step, and a defined decision output. Skip a layer
only when its inputs are unreachable, and report the skip explicitly to the
trader — incomplete coverage is allowed but must be flagged.

Source order (per CLAUDE.md): UW first for vol/dealer/microstructure
numbers, TV via `finance-data-providers:tradingview-reader` for chart/news,
IB for account state. Never recompute a number UW serves directly.

---

## Layer 0 — Account state (IB)

**Why first:** every downstream sizing and refusal depends on it.

**Pull:**
- `IBClient.get_positions()` — does the trader already hold the ticker?
- `IBClient.get_account_summary()` — `TotalCashValue`, `NetLiquidation`,
  `AvailableFunds`, `BuyingPower`, `InitMarginReq`, `MaintMarginReq`.

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

**Pull:** `get_chains_for_expiry` for 4-5 expiries spanning the trade
window — typically front-week, trade expiry, post-trade-expiry, post-ER.
Limit ~30 strikes (sorted by volume in UW output) to keep response small.

**Compute:**
- ATM IV per expiry = average of ATM call IV and ATM put IV. Look for
  monotonic increase (contango = normal) or any inversion.
- 25Δ skew at the trade expiry = (25Δ call IV) − (25Δ put IV). Equity
  convention is **negative** (puts richer). Positive skew is unusual and
  signals heavy retail call demand (TSLA / NVDA / COIN behavior).

**Decision:**
- Inversion at the trade window = catalyst priced inside → defer the
  trade or shrink size.
- Contango + skew not strongly negative = clean entry for short premium.

---

## Layer 3 — Price action (UW + TV)

**Why:** structural levels + tape posture. A range-bound chop reads
differently than a trending breakout; trade-window structure depends on
which one is current.

**Pull (UW):**
- `get_extended_technical_indicator` — SMA(200), SMA(50), RSI(14), MACD,
  BBANDS (daily). UW only returns recent history; extrapolate forward
  with the rate-of-change.
- `get_ticker_candles_by_range` (range=4h or 1h, interval=1m) — last
  ~21 sessions for tape context.

**Pull (TV via `finance-data-providers:tradingview-reader`):**
- `opencli tradingview chart-state` — current chart layout, interval,
  drawings (qualitative)
- `opencli tradingview news --symbol NASDAQ:<TICKER> --limit 8` — recent
  headlines for catalyst-clock validation
- `opencli tradingview watchlists --color <flag>` — does the trader have a
  manual prior on this ticker? Treat as tiebreaker, not a decision driver
  (see `price-action-framework.md`).

If TV is unreachable, fall back to UW indicators alone and report the gap
to the trader.

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

## Layer 4 — Tape (UW)

**Why:** confirms or contradicts the structural read. A bullish structural
setup with bearish dealer flow is a yellow flag.

**Pull:**
- `get_flow_alerts` (filter `ticker_symbol`, last ~15-20 alerts) — rule-
  triggered unusual activity. Look at expiry distribution and side
  dominance.
- `get_flow_per_expiry` — call vs put premium concentration per expiry.
  Look for inversions in the curve.
- `get_dark_pool_trades` (filter `ticker_symbol`, `min_premium` ≥ $500K) —
  institutional block flow. Note level + recency.

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

## Layer 6 — Regime classification + structure pick

**Inputs from above:**
- Vol regime label (Layer 1, VRP)
- Directional bias (Layer 3, 200DMA distance + tape)
- Term structure shape (Layer 2)
- Catalyst clearance (Layer 5)

**Decision:** map onto the regime × structure matrix in
`references/strategies.md`. Then:

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

4. Pick **size** = min of:
   - 2-5% of NLV at max loss
   - 25% of `AvailableFunds`
   - integer position respecting margin reserve after entry

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
