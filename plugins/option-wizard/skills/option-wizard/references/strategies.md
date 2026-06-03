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

When to suggest SPX put-spread hedge sizing (see
`scripts/macro_hedge.py`):

- Portfolio short-premium notional > 50% of net liquidation.
- Net delta of options book > +0.5 of NLV in dollar terms.
- VIX < 18 with VIX term structure backwardation — cheap hedge insurance.
- Calendar earnings density: 3+ portfolio names reporting in a 2-week
  window.

Maximum annualized hedge cost capped at 1.5% of NLV (spec hard rule).

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
