# Index Premium Selling — Workflow 2b Reference

Workflow 2b sub-flow for selling premium on US-equity index underlyings:
CSP on QQQ/SPY, put diagonal calendar on RUT (3 modes). Sibling of
Workflow 2a (macro hedge); shares 8-layer L0-L5 data spine from
`analysis-runbook.md`, diverges at L6 (structure pick) and L7 (preflight).

## 1. When to use

**Trigger phrases:**
- Chinese: `"QQQ CSP"` / `"SPY 卖 put"` / `"RUT diagonal"` / `"卖 index premium"`
- English: `"qqq csp"` / `"spy put"` / `"rut diagonal"` / `"sell index premium"`

**Workflow 2a vs 2b boundary:** 2a buys protection (macro hedge), 2b
sells premium. Both share L0-L5 data pull; never call both in one turn
without explicit user intent (buying hedges while selling premium reads
the same VRP/GEX state with opposite conclusions, and conflating them
loses signal).

**Out of scope (defer to other workflows):** PB structured products
(Workflow 4/5), single-name CSP (Workflow 1), VIX options
(separate v2 backlog).

## 2. Source discipline (index-specific)

- **UW**: IV rank, VRP label (via `scripts.vrp::compute_vrp`), GEX
  by strike (via `get_greek_exposure_by_strike` → `scripts.gex_levels`),
  0DTE flow per expiry, max pain
- **TV** (via `finance-data-providers:tradingview-reader`): spot,
  SMA(20/50/200), RSI(14), VIX & VIX1D & VIX9D term, news / catalyst
  headlines
- **IB** (live trade mode): chain mid via `get_options_chain` (when
  decision <60s), `get_account_summary` for buying power

Forbidden: UW `get_extended_technical_indicator` (lagged); IB for IV
rank / skew / GEX (IB doesn't compute these).

## 3. CSP on index ETF (QQQ / SPY / IWM)

**Legs:** short 1 OTM put + cash = strike × 100.

**Entry condition:** `IV rank ≥ 20 AND VRP ∈ {NEUTRAL, RICH}`. The
lower threshold than single-name (≥ 50) is justified because index
sell-premium edge comes from VRP (structural risk premium), not idio
compensation. Single-name CSP uses 50 because idio risk dominates.

**DTE:** 30-45. **Δ target:** 0.20-0.30 (more OTM than single-name
because index tail is fatter).

**Strike anchor:** put wall from `scripts.gex_levels::compute_levels`,
not 200DMA. Put wall is where dealer hedging is concentrated; spot
tends to mean-revert from below the put wall.

**Sizing:** Single contract notional ≤ 5% NLV; total index CSP notional
≤ 25% NLV.

**Refused:**
- SPX naked CSP (notional > $300k per contract, sizing violation even
  if cash-covered)
- IWM when bid-ask > $0.10 — use RUT options for better fills

**Preflight:** `scripts.ib_order::build_preflight` direct.

## 4. RUT put diagonal — three modes

All modes: long 45DTE put @ Kl + short 1-2DTE put @ Ks. Max loss at
short-leg expiry = `max((Ks − Kl) × 100, 0) − net credit`. Calendar
mode collapses to long put extrinsic decay (no width term).

| Mode | Strike layout | Default Δ | Regime fit |
|---|---|---|---|
| **calendar** | Ks = Kl | long 0.30, short Δ unused | NEUTRAL vol + expected IV term contango deepening |
| **protective** | Ks = Kl × (1 − 0.025) (anchor-based; Δ-only fails at 1-2 DTE) | long 0.30 | bearish bias + RICH vol |
| **aggressive** | Ks picked by short Δ = 0.30 (natural Ks > Kl with long Δ 0.15) | long 0.15, short 0.30 | bullish RICH vol; VIX < 25 hard limit |

**Greeks character at entry** (with default Δs):
- calendar: vega-POSITIVE (long-leg vega dominates); theta NEGATIVE
  at default 0.30Δ_long because short 1-DTE lands ~5% OTM with near-zero
  theta. To flip net theta positive, override `target_deltas={long:0.50, short:0.50}`
  → ATM calendar where short 1-DTE has meaningful theta.
- protective: θ+ (mild), ν+, Δ slightly negative (bearish lean)
- aggressive: θ++, ν+, Δ slightly positive (bullish lean)

**Abandon conditions per mode:**
- calendar: switch to protective if VRP becomes RICH or short leg
  drifts ITM by ≥ 1 listed strike (RUT $5)
- protective: continue rolling unless long-leg DTE < 21
- aggressive: hard abort if VIX ≥ 25 (entry_timing returns abort);
  switch to protective if VIX rises into 22-25 zone mid-position

**Pricer:** `scripts.diagonal_calendar::build_diagonal_calendar(spot,
mode, snapshot, ...)`. Returns legs + net debit + max loss +
breakevens (plural — diagonal P/L typically non-monotonic with TWO BEs) +
net greeks (entry) + roll matrix across 7 spot scenarios + regime_check
(warns on mode mismatch, does not abort).

## 5. Entry timing decision tree

5-step tree, command-order; first hit returns. Freshness gate (≤15min
stale) runs FIRST; day-specific overrides take priority over steps 1-5.

### Decision tree

```
0. Freshness gate (always first)
   - snapshot.snapshot_taken_at missing → ABORT (freshness_missing_timestamp)
   - snapshot > 15 min stale → ABORT (freshness_stale_snapshot)

Day-specific overrides (priority above steps 1-5)
   - FOMC presser day (pre-14:00 ET): WAIT until 14:30 ET
   - Monday open (09:00-09:59 ET): WAIT 30 min (weekend gamma unwind)
   - OPEX Friday afternoon (≥12:00 ET):
       CSP mode  → WAIT_EOD (defer for cleaner mid)
       diagonal  → enter_now (anchor short strike to UW max pain)

Aggressive-mode hard limit (priority above steps 1-5)
   - mode=rut_aggressive AND VIX ≥ 25 → ABORT (fall back to protective)

1. VIX gate
   - VIX1D > VIX > 18 AND VIX1D/VIX9D > 1.05 → ABORT (event-driven backwardation)
   - VIX < 12 AND VRP = CHEAP → ABORT (no risk premium)

2. Premarket gap (09:15 ET, ES/NQ futures)
   - |gap %| > 1.0% (QQQ/SPY) or > 1.5% (RUT) → WAIT 30 min

3. Dealer GEX state (UW)
   - Net dealer GEX < 0 AND |gamma_flip − spot| / spot < 1% → WAIT_EOD

4. 0DTE flow (UW flow_per_expiry, same-day expiry)
   - put_premium / call_premium > 3.0 → WAIT (whale put-buyer)

5. Mode-specific entry window
   - CSP (30-45 DTE)              → morning 09:45-10:30 ET
   - RUT calendar mode            → EOD 15:30-15:55 ET
   - RUT protective mode          → morning 09:45-10:30 ET
   - RUT aggressive mode          → EOD 15:30-15:55 ET only
```

### v0 threshold table

| Threshold | v0 default | Provenance / tuning direction |
|---|---|---|
| `vix_abort_high` | 18 | CBOE median for backwardation; sellers in 20+ regime can raise to 22 |
| `vix_event_ratio` | 1.05 | Buffer above 1.0 to skip noise |
| `vix_abort_low` | 12 | VIX 5th-pct historically |
| `gap_wait_pct` | 0.010 (QQQ/SPY) | ≈ 40% of 1 ATR |
| `gap_wait_pct_rut` | 0.015 | RUT intraday range higher |
| `gex_flip_proximity` | 0.010 | Spotgamma / Tier1Alpha published "danger zone" |
| `odte_put_buyer_ratio` | 3.0 | First-draft heuristic; calibrate via paired live trades |
| `aggressive_mode_vix_cap` | 25 | RUT 1d expected ≈ 1.6% at VIX 25, ATM 1DTE EV ≈ 0 |

All thresholds live in `THRESHOLDS` dict at top of
`scripts/entry_timing.py`. Audit log at
`references/private/market/entry-timing-log.jsonl`. Use
`scripts.entry_timing --calibrate` after N ≥ 10 decisions to see which
thresholds fire (over-tightening waste signal; never-fired catches nothing).

## 6. Roll & exit rules

### Short leg (1-2DTE)

- **Daily roll:** at expiry-day −1h, call
  `scripts.diagonal_calendar.build_short_leg_roll(existing_position,
  new_dte_short=1, snapshot, days_elapsed)` → returns close-old +
  open-new legs at new Δ matching mode default, plus
  `action_required` ∈ {roll_short, close_all_long_dte_too_short,
  switch_mode}.
- **Mode-drift switch:** if calendar mode short put now ITM by ≥ 1
  RUT listed strike width ($5), `action_required = 'switch_mode'`
  with `switch_mode_recommendation = 'protective'`. Trader confirms;
  next roll opens at protective Δ.

### Long leg (45DTE → 21DTE close)

- Hard rule #4: at 21 DTE remaining, force close to avoid long-leg
  gamma. `build_short_leg_roll` returns
  `action_required = 'close_all_long_dte_too_short'` when long DTE
  threshold hit. Trader closes long leg + most-recent short leg, then
  reopens full structure with fresh 45DTE long if continuing.

### Brackets

- TP: 50% of net debit captured (long leg mark + accumulated short
  credit cover ≥ 50% of initial debit).
- SL: long-leg mark drops > 30% of entry cost (long-leg only — short
  leg is replaced daily, no SL on short leg).

## 7. Book-level risk monitoring

- **Vega aggregation across diagonal positions:** each long-leg vega
  is positive (long vol); summing 5 RUT diagonals = 5× single-position
  vega exposure. Surface in Workflow 3 (positions review) book-level
  stats.
- **Net Δ contribution:** calendar mode ≈ 0; protective/aggressive
  contribute meaningful Δ. Beta-adjust to NLV when total options book
  Δ > 0.5 NLV (Workflow 2a hedge trigger).
- **Overlap with Workflow 2a macro hedge book:** RUT protective leg is
  long RUT put = small macro hedge equivalent. Don't double-count: if
  Workflow 2a sized SPX hedge assuming no incidental hedge, the
  protective leg over-hedges. Reconcile in book review.

## 8. Worked examples (live 2026-06-08 snapshot)

All numbers below are generated by
`scripts/regen_index_premium_worked_examples.py` — run that script after
any change to `scripts/diagonal_calendar.py` math to refresh this section.
Hand-edited numbers will drift from the pricer; the regen script keeps
doc and code in sync.

Live UW pulls from 2026-06-08 close. Re-run via:
```bash
.venv/bin/python -m scripts.regen_index_premium_worked_examples
```

### 8.1 QQQ CSP — NEUTRAL VRP, IV rank HIGH bucket

**Snapshot:** Spot $716.07; IV30d 23.9%; IV rank 61 (HIGH); RV 23.7% →
VRP = −0.2pp = NEUTRAL ✓ (passes entry gate); put wall $714; call wall
$722; max pain 2026-07-10 (~31 DTE) at $730.

**Structure:** 0.25Δ put, 35 DTE → `_strike_for_put_delta(716.07, 0.25,
35/365, 0.239)` → **$685.70 theo**, snap to $1-spaced strike = **$686**.

**Credit (BSM, after $0.05 slippage):** $8.24/share = **$824.08/contract**.

**Sizing:** notional cap $50k ÷ ($686 × 100) → 1 contract. Cash
reserve: $68,600.

**Preflight:**
- Max loss: $68,600 − $824.08 = **$67,775.92**
- Max gain: **$824.08**
- Breakeven: $686 − $8.24 = **$677.76**
- Bracket: TP exit at mid $4.12 (50% credit retained), SL exit at mid $24.72 (2× credit loss = 3× credit mark)

**Caution:** Strike $686 is **below put wall $714** by $28. Conservative
trader tightens to 0.30Δ (closer to put wall) or moves to 0.20Δ.

**Entry timing:** Normal weekday morning window 09:45-10:30 ET →
`enter_now`.

### 8.2 RUT diagonal calendar mode — NEUTRAL VRP

**Snapshot:** RUT ≈ 2841 (IWM × 10); IV30d 23.3%; IV rank 38 (MID);
iv_atm_short ≈ 0.235; iv_atm_long ≈ 0.233.

**Structure:** Mode = `calendar`. Kl = Ks at default long Δ=0.30.
- Kl theo at 0.30Δ 45 DTE: **2744.32**, snap to RUT $5-spaced = **2745**
- Ks = Kl = 2744.32 (BSM-priced; chain path would snap to listed $5 grid)

**Mids (BSM, $0.05 slippage applied):**
- Long 45 DTE @ 2744 ≈ **$46.22/share**
- Short 1 DTE @ 2744 ≈ **$0.02/share** (deep OTM 1-DTE = near-zero)

**Net debit:** ($46.22 − $0.02) × 100 = **$4,620**.

**Max loss:** **$5,940.10** (= net_debit + Kl·(1−DF)·100 discount-carry
term at S→0; Kl ≈ 2744, 44d at 4% rate → ~$1,320 extra theoretical loss).

**Net greeks at entry:**
- Δ = **−0.2977** (long put dominates; mildly bearish)
- γ = +0.0013
- θ_daily = **−$67.30/day** ⚠️ NEGATIVE (default Δ=0.30 puts K 5% OTM
  where short 1-DTE has near-zero theta; long-leg theta loss dominates)
- ν = **+$345.76** per 1pp IV (long-leg vega is the primary edge)

**Breakevens at short expiry:** lower=2670.54, upper=2841.00 (profit
zone is narrow, between the BEs).

**⚠️ Theta-positive variant:** To flip net theta positive, override
`target_deltas={"long": 0.45, "short": 0.45}` — pushes K toward ATM so
short 1-DTE has meaningful theta to farm. See §4 mode characteristics.

**Entry timing:** Calendar mode → **EOD window 15:30-15:55 ET**.
`wait_eod` if called outside.

### 8.3 RUT protective mode — bearish lean

**Snapshot:** Same base; trader bearish from L3 TV analysis. Mode = `protective`.

**Strikes:**
- Kl theo at 0.30Δ 45 DTE = **2744.32**
- Ks = Kl × (1 − 0.025) = **2675.71** (anchor-based; Δ-only would put Ks > Kl)

**Mids (BSM):** Long 45 DTE @ 2744 ≈ **$46.22**; short 1 DTE @ 2676 ≈ **$0.00**
(deep OTM 1-DTE essentially worthless).

**Net debit:** **$4,622**.

**Max loss:** **$4,622** (≈ net_debit; close-everything at short expiry;
worst case S > Kl, both worthless. Width (Kl − Ks) × 100 = $6,861 does
NOT add — when S < Ks both legs are ITM and offset dollar-for-dollar in
the [Ks, Kl] range. Spec §10 #1.)

**Roll matrix at short expiry:**
- Spot −10% (2557): net_pl = **+$3,421** (long put pays off heavily)
- Spot 0% (2841): net_pl = **−$80** (theta-eaten; near breakeven)
- Spot +5% (2983): net_pl = **−$3,009** (long decays, short kept)

**⚠️ Regime check warning:** At IV rank 38 (MID bucket) + NEUTRAL VRP,
recommended mode is `calendar` not `protective`. Trade proceeds but
trader sees: `"VRP=NEUTRAL + IV rank 38 (mid) suggests 'calendar' mode;
chose 'protective' — proceeds but accept lower expected edge"`.

**Entry timing:** Protective → **morning window 09:45-10:30 ET**
(needs early stop-level setting).

### 8.4 RUT aggressive mode — bullish RICH vol with VIX < 25

**Snapshot:** Same base; trader sees bullish setup. IV rank 38 (MID) does
NOT match aggressive's RICH-bucket preference — `regime_check.warning`
populates but trade proceeds.

**Strikes:**
- Kl theo at 0.15Δ 45 DTE = **2631.73**
- Ks theo at 0.30Δ 1 DTE = **2823.26** (natural Ks > Kl with default Δs)

**Mids (BSM):**
- Long 45 DTE @ 2632 ≈ **$18.74**
- Short 1 DTE @ 2823 ≈ **$6.70**

**Net debit:** ($18.74 − $6.70) × 100 = **$1,204**.

**Max loss:** **$21,622.50** = (Ks − Kl·DF) × 100 + net_debit
(worst case S → 0: long pays Kl·DF ≈ 2622 discounted, short pays Ks
intrinsic = 2823; difference + net_debit).

**Aggressive mode VIX check:** SPY IV30d 15.6% → VIX ~ 16, well under
25 cap → `aggressive_mode_vix_cap` does NOT abort.

**⚠️ Regime check warning:** Same `"chose 'aggressive' — proceeds but
accept lower expected edge"` warning fires (recommended = `calendar` at
IV rank 38).

**Entry timing:** Aggressive → **EOD-only** (15:30-15:55 ET). Decision
tree rejects morning entry for this mode.

---

**Data provenance:** UW 2026-06-08 close via `get_company_info` +
`get_stock_screener` + `get_greek_exposure_by_strike` + `get_max_pain`;
IV/strike via BSM. Chain mid path (UW/IB/TV) supersedes BSM when chain
provided via `build_diagonal_calendar(snapshot={chain: {...}})`.

**Regen contract:** `scripts/regen_index_premium_worked_examples.py` is
the source of truth for §8 numbers. CI assertion (v1.1 backlog): the
script's JSON output must round-trip into the §8 numeric tokens above.
