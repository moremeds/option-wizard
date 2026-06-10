# Macro hedge convexity framework

How to design index hedges that pay more in crashes per dollar of carry.
Built from the empirical study in
`references/research/2026-06-10-convex-macro-hedges.md` (5 anchor events
2018-2024 + 2017/2023 false-positive carry).

## The convexity equation

For a 2-day path with returns R₁ and R₂, a position with daily-reset
leverage L returns `(1+L·R₁)·(1+L·R₂) − 1`. Expanding:

```
total ≈ L·(R₁+R₂) + L²·R₁·R₂
```

The `L²·R₁·R₂` term is the convexity gift: positive when returns share
sign (trend), negative when they oppose (chop). 3× LETFs eat chop and
print money in trends because of this term.

**Hedges harvest the same term on the downside.** A long put that gets
deeper ITM as the market drops has positive gamma — each additional 1%
drop accelerates payoff. The hedge designer's job is to maximize
crash-side gamma per dollar of premium spent. Two levers:

1. **Long-leg count ≥ short-leg count.** Otherwise the short leg refunds
   the convexity you paid for on the long leg. Spreads cap payoff at the
   short strike → saturated convexity. Put butterflies, put spreads,
   call spreads all suffer this.
2. **Strike placement aligned with the realistic drawdown depth.** This
   is where naive convexity reasoning fails (see §"Failure modes" below).

## What works empirically (5-event study)

Mean P&L per $1M book across 2018 Volmageddon, 2020 COVID-1, 2020
COVID-2, 2022 hike-cycle, 2024 JPY unwind:

| Structure | Win rate | Mean P&L | Mean cost | Standing/Tactical |
|---|---|---|---|---|
| **SPX ATM/-10% put spread** | **5/5 (100%)** | +$26,826 | $30,652 | **Tactical only** — carries 10-12% NLV/yr if held |
| **SPX -10% long put** | 4/5 (80%) | +$25,578 | $17,004 | **Standing** — carries -0.01% to -0.54% NLV/yr |
| IWM -10% long put | 4/5 (80%) | +$37,155 | $21,210 | Cross-index variant |
| QQQ -10% long put | 4/5 (80%) | +$24,199 | $21,053 | Tech-catalyst variant |
| **VIX 30-DTE ladder 25+35+45** | 4/5 (80%) | +$295,026* | $6,429* | **Tactical only** — BSM-inflated; carries 4.5%+ NLV/yr |

*P&L and cost are BSM-estimated with VVIX-as-IV. Real listed mids 50-200%
higher in calm regimes → real convexity 3-5× compressed. Treat as upper bound.

### What does NOT work (and why the LETF analogy mis-fired)

| Structure | Win rate | Mean P&L | Why it fails |
|---|---|---|---|
| Put ratio backspread -8/-15 (any underlying) | 2/5 (40%) | -$254 to -$805 | Max-loss valley between strikes aligns with typical 5-10% vol-shock DD on M7 book — peak lands IN the valley |
| Put ratio backspread -10/-20 (any underlying) | 1/5 (20%) | -$2,724 to -$7,855 | Even wider valley; only pays when crash exceeds -20% (COVID-1 only) |
| Put butterfly -2/-5/-8 (any underlying) | 2/5 (40%) | -$221 to -$542 | Body strike (-5%) gets passed through; outside the upper wing in fast crashes |
| VIX weekly single call K=30 | 2/5 (40%) | +$992 | BSM-zero at low VIX; would carry 30-50%/yr at listed mids |

**The ratio-backspread failure is the headline pedagogy.** The
LETF-style "long-count > short-count = preserved convexity" reasoning is
directionally correct but ignores STRIKE PLACEMENT. A 2× -15% long / 1×
-8% short structure has its maximum loss exactly at -15% spot. Of the 5
events studied, only COVID-1 (SPX -13.1%, IWM -20.5%) pushed past the
long strike. Volmageddon (-7.2%), COVID-2 (-6.2%), hike-cycle (-3.2%),
JPY unwind (-5.1%) all landed IN the valley between the short and long
strikes — where the short leg is deep ITM and the long legs are still
worthless. **Ratio backspreads are short-skew premium-capture trades
that masquerade as crash hedges.** They earn small carry in calm years
(+$822 in 2017, +$12,456 in 2023) but pay it back catastrophically on
the next 5-10% drawdown.

## The structure menu (post-research)

### Standing hedge — keep on always

**SPX 5-delta long put, 35 DTE, monthly roll.** Default scenario for
`build_macro_hedge(structure="long_put")` after the upgrade. The strike
is delta-targeted (5-delta), not pct-targeted (-10%), so carry scales
with the regime: in calm VIX 12-14 the 5-delta strike is ~-7% to -8% and
the put costs $0.20-0.50/contract; in VIX 25+ the 5-delta strike walks
further OTM and stays cheap. Empirically: -0.01% to -0.54% NLV/yr carry,
67×-361× convexity in low-IV entries.

### Tactical hedge — deploy on regime signal

**SPX ATM/-10% put spread, 35 DTE, hold ≤ 14 days.** The only
100%-win-rate structure. Deploy when `VIX9D/VIX ≥ 1.04 AND 18 ≤ VIX <
25`. Carries 10-12% NLV/yr if held continuously → annual cost cap blown.
Treat as a 1-3 week deployment with explicit `tactical_window_days=14`
flag, then close.

### Tactical hedge — vol-of-vol regime

**VIX 30-DTE OTM call ladder (25+35+45), 0.5% NLV cap per deployment.**
Highest absolute payoff in the study, but BSM-estimated cost dramatically
understates real listed mids. Deploy ONLY when:
- VIX9D/VIX ≥ 1.04 (term inversion)
- VIX < 20 (still pre-spike; if VIX > 20 the convexity premium is
  already priced)
- TP at 200% of cost (sell half), runner to expiry or peak vol day

Bracket the deployment with an explicit calibration step: pull the live
UW or IB VIX chain on entry, compute the BSM-vs-mid ratio for this
deployment, and write it back to `references/research/data/` so the next
deployment uses a calibrated cost.

### Cross-index variants

| Variant | When | Empirical evidence |
|---|---|---|
| **IWM ATM/-10% put spread** | VVIX > 130 AND credit widening (HY OAS > prior-30d 80th %ile) | COVID-1: IWM DD 20.5% vs SPX 13.1%, IWM put paid +$117K vs SPX +$80K. JPY unwind: IWM DD 8.8% vs SPX 5.1%, IWM paid +$54K vs SPX +$21K |
| **QQQ -10% long put** | Tech-specific catalyst (FOMC hawkish, semi cycle, AI rotation) AND VXN-vs-VIX ratio < 1.5 | Hike-cycle 2022: QQQ DD 5.3% vs SPX 3.1%, IV priced only 1.46× → free convexity. QQQ paid +$12K vs SPX +$4K |

### Forbidden in the auto-menu

- **Put ratio backspread** (any config) — fails on typical M7 drawdown depth
- **Put butterfly** for tail purpose — keeps as `mild_correction_-5`
  option but emits a deprecation warning if `scenario` is anything else
- **Far-dated (≥30 DTE) VIX call SPREAD** — see pitfall #01

## Regime decision tree

Executed at every Monday open by scanning UW + FRED.

```
Inputs:
  VIX, VIX9D, VIX3M, VVIX, SKEW       (UW or yfinance)
  HY_OAS                              (FRED BAMLH0A0HYM2)
  VXN                                 (yfinance ^VXN, optional)
  catalyst_clock                      (FOMC, ER density, geopolitical)

DECISION:

  IF VIX ≥ 25 AND VIX/VIX3M > 1.00:
    # Vol is already rich. Don't chase.
    → Take profit on existing hedges (50% TP rule)
    → Convert any naked long puts into put spreads (sell -10% strike for credit)
    → No new hedge initiation

  ELIF VIX9D/VIX ≥ 1.04 AND VVIX > 130 AND HY_OAS rising:
    # Fast-deleveraging regime
    → IWM ATM/-10% put spread, 0.5% NLV, tactical_window_days=14

  ELIF VIX9D/VIX ≥ 1.04 AND 18 ≤ VIX < 25:
    # Term inversion + elevated vol = tactical spread regime
    → SPX ATM/-10% put spread, 0.5% NLV, tactical_window_days=14
    → IF catalyst_clock includes tech-specific (FOMC hawkish, semi cycle):
        Add QQQ -10% long put, 0.2% NLV

  ELIF VIX9D/VIX ≥ 1.04 AND VIX < 18:
    # Earliest tell — cheap pre-positioning
    → SPX 5-delta long put, 0.15% NLV (overweight the standing hedge)
    → VIX 30-DTE ladder 25+35+45, 0.5% NLV cap (tactical convexity bet)

  ELIF SKEW > 140 AND VIX < 18:
    # Leading indicator — slow lean-in
    → Standing SPX 5-delta long put at normal sizing (0.05-0.10% NLV)
    → Add QQQ -10% put if catalyst is tech-specific

  ELSE:
    # Calm regime — minimum carry
    → SPX 5-delta long put only, 0.05% NLV (cheap tail insurance)
    → No tactical adds
```

The strongest tell is `VIX9D/VIX ≥ 1.04`: fires **6 of 7** anchor events
at T-5 trading days when the 2011 US debt downgrade + 2015 China Black
Monday are added to the original 5-event set (extended backtest run
2026-06-10). Per-event T-5 reading:

| Event | T-5 VIX9D/VIX | Fired? |
|---|---|---|
| 2011-08-08 US debt downgrade | 1.135 | yes (also 1.054 at T-10 — earliest warning in dataset) |
| 2015-08-24 China Black Monday | 0.867 | **NO** (fired only at T-2 = 1.091, too late) |
| 2018-02-05 Volmageddon | 1.077 | yes |
| 2020-03-16 COVID-1 | 1.291 | yes |
| 2020-03-23 COVID-2 | 1.290 | yes |
| 2022-03-08 hike-cycle | 1.044 | yes (just) |
| 2024-08-05 JPY unwind | 1.048 | yes (just) |

**The 2015 miss is the structural exception.** China Black Monday built
via FX (yuan devaluation Aug 11) and EM currency stress — equity vol
stayed compressed until the flash-crash open itself. VIX9D/VIX is a
coincident indicator for **equity-vol-driven** events; for currency- or
EM-driven crises, the leading indicator lives in DXY, USDCNY, or EM CDS,
NOT in VIX-family signals. Adding FX-vol to the regime tree is open
research (see §"Open questions").

Mechanic: VIX9D measures 9-day-implied vol from SPX weeklies; when it
rises above 30-day VIX (the regular VIX), the market prices a near-term
event sharper than the rolling average. The short end inverts BEFORE the
term structure (VIX/VIX3M) proper inverts.

SKEW > 140 is the leading indicator. Only fired at T-10 in the JPY
unwind event in our extended 7-event study, but fires earlier than
VIX9D when it does fire — far-OTM put skew loads ahead of left-tail risk
perception. Use both: SKEW for slow lean-in, VIX9D/VIX for the trigger.

## Why SPX over SPY for the same notional

Two empirical reasons reinforce the existing `feedback_index_analysis_use_spx.md`:

1. **Strike-rounding finer.** On a $1M book, SPX buys ~4 contracts vs
   ~35 SPY contracts. Each SPX contract has $5 strike spacing → finer
   strike placement than SPY's $1 spacing for the same dollar exposure.
   Mean win: SPX put spread paid +$1,958 more than SPY put spread per
   event in our study.

2. **24-hour tradability.** SPX index options trade in CME globex
   8:15pm-9:25am ET. SPY only trades NYSE RTH. Overnight crash $ value
   per anchor event:

   | Event | % of drawdown overnight | Practical implication |
   |---|---|---|
   | COVID-2 (Mar 23) | 38.9% | ES gapped -8.93% Sunday→Monday; SPY puts couldn't be rolled |
   | JPY unwind (Aug 5) | 18.7% | Half of -4.5% intraday move happened Asia session |
   | Hike-cycle | 13.9% | Several -1% to -1.5% overnight prints |
   | COVID-1 | 9.7% | Black Monday I limit-down sequence |
   | Volmageddon | 3.1% | Mostly intraday US session |

   On $1M book, a 5% overnight gap = $50K of underlying move where SPY
   put holders cannot rebalance, roll, or take profit. SPX option
   holders can.

## Failure modes to remember

### Failure mode 1: Convexity reasoning without strike-placement reasoning

The put ratio backspread looks like positive convexity (long-leg count >
short-leg count = preserved convexity term) but fails empirically
because the typical drawdown depth on an M7 book (5-12%) lands IN the
max-loss valley between the short and long strikes. The convexity is
real ABOVE the long strike; the valley below the short strike is where
the structure lives in practice. **Match strike placement to the
realistic drawdown distribution, not the theoretical tail.**

### Failure mode 2: Entering long-vol hedges at peak vol

COVID-2 (Mar 16-23): VIX was already 82, VVIX 207. Entering a -10% SPX
long put cost $51K per $1M book. SPX fell another 6%, but VIX crushed
back from 82 → 61 and the put lost $6.9K. The only winner was the put
SPREAD (which has SHORT vol via the short -10% leg). **Rule: at VIX >
50, switch from naked long puts to put SPREADS.** The
`build_macro_hedge` function rejects naked `long_put` when VIX > 50 and
recommends `put_spread` instead.

### Failure mode 3: Far-dated VIX call SPREAD as same-week hedge

This is pitfall #01. Two compounding problems: (1) VIX call SPREAD legs
have cross-leg vega cancellation in a spike, (2) ≥30 DTE expiries anchor
to the back-month VX future, which lags spot VIX by 50%+ in a fast
spike. The positive answer is the VIX OTM call LADDER above (no short
legs anywhere, vega is purely stacked) and/or the SPX/IWM put spread on
the equity side (delta-1 mapping to actual equity exposure, no futures
basis).

## False-positive carry budget

Annual hedge cost cap is 1.5% NLV (per `private/trader-profile.md`). The
study's 2017 + 2023 calm-year carry results:

| Structure | 2017 carry % NLV | 2023 carry % NLV | Under 1.5% cap? |
|---|---|---|---|
| **SPX 5-delta long put (standing)** | **-0.01%** | **-0.54%** | **Yes — primary** |
| Put butterfly -2/-5/-8 (deprecated for tail) | -3.84% | -1.26% | No |
| SPX ATM/-10% put spread | -10.41% | -11.94% | **NO — tactical only** |
| Put ratio backspread -8/-15 | +0.08% | +1.25% | Yes but **not a hedge** (loses on next vol shock) |
| VIX 30-DTE ladder | ~1-3% (real) | ~4.5% | **NO — tactical only** |
| VIX weekly single call | ~3-5% (real) | ~4.5% | **NO — tactical only** |

The trader's standing hedge is a single line item: SPX 5-delta long put
@ 35 DTE, monthly roll, ~$0.15-0.50 per share. Everything else is
regime-gated tactical deployment that sums to ≤ 1% NLV/yr if deployed
sparingly per the decision tree (i.e., 2-4 deployment windows per year ×
~0.2% NLV per).

## Open questions and how to harvest answers

| Gap | Resolution path |
|---|---|
| VIX option chains historical mid | **Calm-regime calibration done 2026-06-10** (`references/research/data/vix_calibration_2026-06-10.py` + `vix_calibration_history.json`). Result: real ladder cost = **2.0× BSM-with-VVIX** at K=25/35/45 30-DTE; per-leg gap 22% / 78% / 96%. Next: pull on first VIX9D/VIX inversion to measure how much the gap WIDENS in inversion regime. |
| 2015 China devaluation + 2011 US debt downgrade in event set | Re-run `references/research/data/run_analysis.py` with extended dates |
| HY OAS automatic ingestion | Wire FRED series `BAMLH0A0HYM2` into snapshot via `pandas_datareader.fred` or HTTP CSV fetch |
| Bid-ask drag on monthly rolls | Sample live UW/IB chain spreads on SPX 5-delta puts; assume current is representative; add as line in cost output |

## References

- Empirical study: `references/research/2026-06-10-convex-macro-hedges.md`
- Pitfall 01: `references/pitfalls/01-vix-options-track-futures-not-spot.md`
- Pitfall 03 (this work): `references/pitfalls/03-ratio-backspreads-not-tail-hedges.md`
- Code: `scripts/macro_hedge.py`
- Trigger heuristics: `references/strategies.md` §"Macro hedge trigger heuristics"
- Trader profile (1.5% NLV cap): `private/trader-profile.md`
- Existing memory: `feedback_index_analysis_use_spx.md` (reinforced by §"Why SPX over SPY")
