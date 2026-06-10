# Strategies

## Regime × structure matrix

Vol regime is read from `scripts/vrp.py::compute_vrp` (`RICH` / `NEUTRAL` /
`CHEAP` thresholds at ±5pp). Directional bias is read from the
combination of TV trend, gamma flip placement vs spot, and catalyst clock.

|             | Bullish                        | Neutral                                | Bearish                              |
|-------------|--------------------------------|----------------------------------------|--------------------------------------|
| **RICH vol** (sell-premium favored) | Bull put spread, jade lizard (with veto check) | Iron condor, short strangle (if defined-risk via wings) | Bear call spread |
| **NEUTRAL vol** | Bull put spread, CSP if IV rank ≥ 50 | Iron condor (wider), calendar | Bear call spread |
| **CHEAP vol** (buy-premium favored) | Long call, call debit spread | Long calendar, diagonal | Long put, put debit spread |
| **Index premium sell** (QQQ / SPY / RUT only) | QQQ/SPY CSP (IV rank ≥ 20 + VRP ≠ CHEAP); RUT diagonal aggressive mode (VIX < 25 hard limit) | RUT diagonal calendar mode; QQQ bull put spread | RUT diagonal protective mode |

Every cell assumes defined risk. The "naked CSP" appearing in the neutral
column is only allowed when cash on hand fully covers the assignment
notional (see `scripts/defined_risk_audit.py`).

## Structure mechanics

### Covered call (CC)

- **Legs:** Long 100 shares + short 1 OTM call.
- **Max loss:** spot purchase price − premium received (i.e., own the
  stock).
- **Max gain:** (strike − spot) × 100 + premium received.
- **Breakeven:** spot − premium / 100.
- **When:** Already long, IV rank ≥ 50, no near-term catalyst that could
  cause an unwanted assignment, target 30-45 DTE 0.30Δ short call.

### Cash-secured put (CSP)

- **Legs:** Short 1 OTM put + cash reserve = strike × 100.
- **Max loss:** (strike − 0) × 100 − premium = full strike notional minus
  premium (worst case stock goes to zero).
- **Max gain:** premium received.
- **Breakeven:** strike − premium / 100.
- **When:** Want to own the stock at a lower entry, IV rank ≥ 50, 30-45
  DTE, cash on hand covers full notional. Margin-secured shorts are
  **forbidden** under SKILL.md hard rule #1.

### Cash-secured put on index ETF (QQQ / SPY / IWM)

- **Legs:** Short 1 OTM put + cash reserve = strike × 100.
- **Entry condition:** `IV rank ≥ 20 AND VRP ∈ {NEUTRAL, RICH}`. The
  lower threshold than single-name CSP (≥ 50) is justified because the
  sell-premium edge on indices is the VRP risk premium, not idio compensation.
- **DTE:** 30-45.
- **Δ target:** 0.20-0.30 (more OTM than single-name due to fatter index
  tail).
- **Strike anchor:** put wall from `scripts.gex_levels::compute_levels`
  (not 200DMA).
- **Sizing:** Single contract notional ≤ 5% NLV; total index CSP
  notional ≤ 25% NLV.
- **Refused:** SPX naked CSP (notional > $300k per contract); IWM when
  bid-ask > $0.10 (use RUT options instead).

### Bull put spread (defined-risk CSP)

- **Legs:** Short put at strike A, long put at strike B (B < A).
- **Max loss:** (A − B) × 100 − net credit.
- **Max gain:** net credit.
- **Breakeven:** A − net credit / 100.
- **When:** Bullish but cash doesn't cover full CSP notional; want
  defined risk. Worked example: ORCL spot $244, sell 220P / buy 215P,
  net credit $1.20 → max loss $380, max gain $120, breakeven $218.80.

### Bear call spread

- **Legs:** Short call at A, long call at B (B > A).
- **Max loss:** (B − A) × 100 − net credit.
- **Max gain:** net credit.
- **Breakeven:** A + net credit / 100.
- **When:** Bearish or want to harvest premium on a name that has run
  above its 200DMA. Defined-risk by construction.

### Iron condor

- **Legs:** Bull put spread + bear call spread on the same expiry.
- **Max loss:** widest wing − total credit.
- **Max gain:** total credit (both spreads expire worthless).
- **When:** RICH or NEUTRAL vol, no directional view, ticker pinned
  between gamma flip and call wall. Target 30-45 DTE, ~16Δ on both
  short legs.

### Put diagonal calendar (RUT — three modes)

All modes: long 45DTE put @ Kl + short 1-2DTE put @ Ks. Max loss at
short-leg expiry = `max((Ks − Kl) × 100, 0) − net credit` (calendar
mode collapses to long put extrinsic decay).

| Mode | Strike layout | Default Δ | Regime fit | Greeks at default Δ |
|---|---|---|---|---|
| **calendar** | Ks = Kl | long 0.30 (short Δ unused) | NEUTRAL vol + expected IV term contango deepening | ν+ (long-leg vega), **θ NEGATIVE** at default Δ (short 1-DTE at 5% OTM has near-zero theta; long-leg theta dominates). Override `target_deltas={long:0.45, short:0.45}` for theta-positive ATM calendar. |
| **protective** | Ks < Kl | Kl 0.30 (Ks anchored 2.5% below Kl) | bearish bias + RICH vol | θ+ (mild), ν+, Δ slightly negative |
| **aggressive** | Ks > Kl | Kl 0.15, Ks 0.30 | bullish RICH vol; VIX < 25 hard limit (enforced via `entry_timing.decide`, NOT in pricer) | θ++, ν+, Δ slightly positive |

- **Roll rule:** Short leg rolled at expiry-day −1h to next 1-2DTE
  same-mode strike. Every 7 rolls (≈ 2 weeks) re-check long leg DTE; if
  < 21 DTE, close long leg (hard rule #4) and reopen full structure with
  fresh 45DTE long.
- **Mode-drift recovery:** Calendar mode short leg drifts ITM by ≥ 1
  listed strike width (RUT typically $5) → switch to protective mode on
  next roll.
- **Pricer:** `scripts.diagonal_calendar::build_diagonal_calendar(spot,
  mode, snapshot, ...)`.

### Collar

- **Legs:** Long 100 shares + short OTM call + long OTM put.
- **Max loss:** (spot − put strike) × 100 − net credit (or + net debit).
- **Max gain:** (call strike − spot) × 100 + net credit.
- **When:** Locked-in concentrated long with cap-and-floor mandate
  (e.g., RSU lockup pre-vest). Often a zero-cost or near-zero-cost
  structure if the put cost ≈ call credit.

### Jade lizard

- **Legs:** Short put + short call spread (short call + long call wing).
- **Max loss:** (put strike − 0) × 100 − net credit on the downside;
  upside is risk-free **only if the net credit ≥ call spread width**.
- **Max gain:** net credit (if pinned between strikes at expiry).
- **When:** RICH vol, bullish-to-neutral, IV rank ≥ 70.

## Jade lizard net-credit rule

**Mandatory.** If net credit < call spread width, the upside is no
longer risk-free and the structure degenerates into a short straddle
with a useless call wing — refuse to call it a jade lizard. Either
widen the call spread (lowers max upside loss) or pick a closer short
call strike (raises credit). Example: 30-day SPX $580/590 call spread
trading at $4.30 credit + $570 short put at $2.80 = $7.10 total. Call
spread width is $10. $7.10 < $10 → fail. Need either to drop the long
call to $600 (raising width but raising credit more), or sell a closer
short put.

## Strong bullish conviction veto

Per spec, when **three or more** of the following concurrent signals
fire, refuse jade lizard / iron condor / calendar and instead
recommend naked-CSP (when cash-covered) / bull put spread / long call
/ call debit spread. The signals:

1. Post-earnings beat with absorbed (not faded) gap-up — TV chart shows
   gap holds at close.
2. Three independent channel-check sources confirming demand strength
   (e.g., supplier guidance, sell-side checks, alt-data).
3. Validated thematic re-rate (AI / GLP-1 / cloud-migration tailwind
   with revenue acceleration, not just multiple expansion).
4. Normalized IV term structure inversion — front month richer than
   back month, indicating expected catalyst within the front.

These mean the market is mispricing upside risk; selling call premium
becomes asymmetric in the wrong direction.

## Macro hedge trigger heuristics

See `references/macro-hedge-convexity.md` for the full empirical
framework (5-event study 2018-2024 + 2017/2023 carry analysis). This
section is the routing index.

**Standing hedge — always on:**
- SPX 5-delta long put, 35 DTE, monthly roll. Empirical carry 0.01-0.54%
  NLV/yr. `build_macro_hedge(structure="long_put", target_delta=0.05)`.

**Regime decision tree (executed at every Monday open):**

| Regime signal at T-5 | Structure | Sizing | Window |
|---|---|---|---|
| VIX9D/VIX ≥ 1.04 AND VVIX > 130 AND HY OAS rising | IWM ATM/-10% put spread | 0.5% NLV | tactical 14d |
| VIX9D/VIX ≥ 1.04 AND 18 ≤ VIX < 25 | SPX ATM/-10% put spread | 0.5% NLV | tactical 14d |
| VIX9D/VIX ≥ 1.04 AND 18 ≤ VIX < 25 AND tech-specific catalyst | + QQQ -10% long put | + 0.2% NLV | tactical 14d |
| VIX9D/VIX ≥ 1.04 AND VIX < 18 | SPX 5-delta long put (overweight) + VIX 30-DTE ladder 25+35+45 | 0.15% + 0.5% NLV | std + tactical |
| SKEW > 140 AND VIX < 18 | Standing SPX 5-delta long put (normal sizing) | 0.05-0.10% NLV | std |
| VIX ≥ 25 AND VIX/VIX3M > 1.00 | **Don't chase.** Take profit on existing; convert naked puts → put spreads | — | exit-only |
| Calm (none of the above) | SPX 5-delta long put only | 0.05% NLV | std |

**Primary tell: VIX9D/VIX ≥ 1.04.** Fires **6 of 7** anchor events at T-5
(original 5-event set + 2011 debt downgrade + 2015 China Black Monday).
The miss is 2015 — that event was FX-driven (yuan devaluation cascade),
not equity-vol-driven, so VIX9D stayed compressed until the flash-crash
open. The short end of the VIX curve inverts before the proper term
structure for equity-vol events; FX-driven events bypass this tell entirely.

**Leading indicator: SKEW > 140.** Fires earlier (T-10) but less
reliably (1 of 4 events). Use for slow lean-in; use VIX9D/VIX for trigger.

**Cost cap:** 1.5% NLV/year annualized (per `private/trader-profile.md`).
The standing hedge consumes 0.01-0.54%; tactical deployments add ≤ 0.7%
per deployment × ~2 deployments/year typical = total ≤ 1.4% NLV/yr.

**Forbidden structures** (empirically eliminated, per Pitfall 03):
- `put_ratio_backspread` (any config) — max-loss valley aligns with
  typical M7 5-12% drawdown range; 20-40% win rate; lose $3-21K per $1M
  when they miss
- `put_butterfly` for tail purpose — body at -5% passed through in fast
  crashes; 40% win rate. Keep only for the literal `mild_correction_-5`
  scenario with explicit caller intent.
- Far-dated VIX call SPREAD as same-week hedge (Pitfall 01)

**Catalyst-based add-on triggers (independent of regime tree):**
- Portfolio short-premium notional > 50% of net liquidation → standing
  hedge sizing × 1.5
- Net delta of options book > +0.5 of NLV in dollar terms → standing
  hedge sizing × 1.5
- Earnings density: 3+ portfolio names reporting in a 2-week window →
  add QQQ -10% long put at 0.1% NLV for the window

## Rejected structures

- **Naked short calls** — refused unconditionally. Unbounded loss on
  upside spikes; sell the call leg of a vertical spread instead.
- **Margin-secured short puts on volatile single names** — refused.
  Cash-secure or convert to bull put spread.
- **Selling the long wing of an existing spread to "harvest theta"** —
  refused. Re-creates the naked exposure.
- **Stop-loss orders on illiquid contracts** — refused as primary
  exit. Use bracket OCO on weekly underlyings only; for illiquid
  contracts, close at predefined P&L target manually.
