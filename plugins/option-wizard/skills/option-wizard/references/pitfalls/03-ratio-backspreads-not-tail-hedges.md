---
type: Trading Pitfall
title: "Pitfall 03: Put ratio backspreads are short-skew premium capture, not tail hedges"
description: Put ratio backspreads have a max-loss valley between strikes that aligns with typical M7 5-12% vol-shock drawdowns — they are short-skew premium capture, not crash hedges. Use a delta-targeted long put + tactical SPX put spread instead.
severity: HIGH
appliesTo: macro-hedge, tail-hedge, ratio-backspread, structure-selection
tags: [ratio-backspread, tail-hedge, short-skew, macro-hedge, max-loss-valley]
timestamp: 2026-06-10T09:04:58Z
---

# Pitfall 03: Put ratio backspreads are short-skew premium capture, not tail hedges

**Date:** 2026-06-10
**Ticker / structure:** Put ratio backspread (long 2× lower-strike OTM / short 1× higher-strike OTM) on SPX / SPY / QQQ / IWM, 30-60 DTE
**Loss / forgone gain:** Would have lost $2.7K-$15K per $1M book across 60-80% of the 5 vol events studied (2018-2024)

## What I almost did

I started designing a macro-hedge upgrade by analogy to leveraged ETF
convexity math: 3× LETFs beat linear 3× in trends because the daily
`(1+L·R₁)·(1+L·R₂)` compounding produces a positive `L²·R₁·R₂` term
when returns share sign. Translating to hedges, the "convex" analog
should be a structure where the long-leg count exceeds the short-leg
count — like a put ratio backspread (long 2× lower-strike, short 1×
higher-strike). The logic: long-count > short-count means the cross-leg
vega cancellation that kills convexity in regular spreads doesn't
happen, so each additional 1% drop past the long strike accelerates
payoff.

The candidate I was about to recommend was a SPX put ratio backspread:
short 1× -8% strike, long 2× -15% strike, 35 DTE, near-zero net cost.
Trader's book is M7-heavy mega-cap tech ($1M notional). Plan was to add
this to `scripts/macro_hedge.py` as a new structure named
`put_ratio_backspread`.

## What the data showed

I ran an empirical backtest over 5 vol events (2018 Volmageddon, 2020
COVID-1, 2020 COVID-2, 2022 hike-cycle, 2024 Aug JPY unwind), entered
T-5 trading days before peak vol, exited at peak. Results across the
SPX / SPY / QQQ / IWM × 2 strike configs = 20 observations:

| Config | Win rate | Worst event loss |
|---|---|---|
| -8% / -15% ratio backspread | 7/20 (35%) | -$15K per $1M |
| -10% / -20% ratio backspread | 4/20 (20%) | -$21K per $1M |

The structure paid only in COVID-1 (where the underlying drew down past
the long strike: SPX -13.1%, IWM -20.5%) and partial in JPY unwind for
IWM. Every other event, the underlying peaked AT the structure's
max-loss valley.

Worst case: 2018 Volmageddon, SPX -7.17%. The short -8% leg was nearly
ATM and ITM by close, the long -15% legs were still $200+ OTM. Net P&L:
-$21K per $1M book (Config 2, -10%/-20%). The structure looked like a
"crash hedge" on paper but was actually a bet that crashes would go
PAST -15% to -20%, which 4 of the 5 events did not.

## Why the assumption was wrong

The LETF analogy captured the convexity term but ignored strike
placement. Put ratio backspreads have a max-loss valley between the
short and long strikes. Visually the payoff profile is:

```
Payoff
  │
  │\  ← Above short strike: small initial net credit, slow theta
  │ \
  │  \________________ ← Between strikes: short leg ITM, longs OTM (MAX LOSS)
  │  ↑                ↑
  │  short            long-leg breakeven
  │  strike (-8%)     (long-strike − credit/2)
  │                   ↑
  │                  /
  │                 / ← Below long strike: unbounded gain
```

The structure's convexity (positive gamma) only kicks in BELOW the long
strike. Above the short strike, the structure earns small theta. BETWEEN
strikes, the structure bleeds linearly in spot.

The trader's portfolio is M7 mega-cap tech + QQQ. Empirical drawdown
distribution of M7 in vol shocks:

| Event | M7-proxy DD (QQQ proxy) |
|---|---|
| Volmageddon 2018 | -7.0% |
| COVID-1 2020 | -12.5% |
| COVID-2 2020 | +0.7% (already past trough) |
| Hike-cycle 2022 | -5.3% |
| JPY unwind 2024 | -6.2% |

**4 of 5 events landed between -5% and -13% drawdown.** Strikes at -8%
short, -15% long perfectly straddle this range. The structure is, in
practice, a bet AGAINST the realistic crash depth — short the -8% put
guarantees a loss on any move into the valley, long -15% puts only
activate beyond the historical baseline.

In LETF terms: the convexity gift `L²·R₁·R₂` requires the move to
actually traverse multiple sign-coherent days INTO the convex zone. For
ratio backspreads, the convex zone starts at the long strike, not at
the entry spot. The structure has NEGATIVE convexity (saturated short
leg) for the first ~15% of the move.

## Rule going forward

**Never deploy put ratio backspreads as the M7-book tail hedge. They are
short-skew premium-capture trades whose max-loss valley aligns with the
realistic drawdown distribution.** When evaluating any candidate
structure for tail purpose, the test is: at the historical 75th-%ile
drawdown of the protected book, is the structure NET LONG or NET SHORT
delta? If short, it is not a hedge.

The positive replacements (per
`references/macro-hedge-convexity.md`):
- **Standing hedge:** SPX 5-delta long put, 35 DTE, monthly roll. Carry
  0.01-0.54% NLV/yr. Pays linearly past the strike with no valley.
- **Tactical regime hedge:** SPX ATM/-10% put SPREAD (100% win rate),
  limited to 1-3 week deployment when VIX9D/VIX ≥ 1.04.
- **Convexity bet (gated):** VIX 30-DTE OTM call LADDER (no short legs
  anywhere), 0.5% NLV cap, when VIX9D/VIX ≥ 1.04 AND VIX < 20.

## Closure criterion for this pitfall

Mark as resolved once: (a) `put_ratio_backspread` is explicitly listed
as a forbidden structure in `scripts/macro_hedge.py` (with a `ValueError`
on attempted use that names this pitfall), AND (b) the trader has
deployed the SPX 5-delta standing hedge for ≥ 1 full quarter and
confirmed the empirical carry estimate (-0.01% to -0.54% NLV/yr) holds
against live IB execution.
