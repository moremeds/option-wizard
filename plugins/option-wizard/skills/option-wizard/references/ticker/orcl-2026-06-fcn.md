---
type: Trade Case Study
title: "ORCL — 2026-06 FCN strike ladder + gamma-flip insight"
description: ORCL FCN evaluation — the 70/75/80/85% strike ladder and the gamma-flip insight that generalizes; teaches the rule without exposing account data.
ticker: ORCL
event: FCN quote evaluation
date: 2026-06
status: closed
result: framework insight (public, anonymized)
structures: [fcn]
tags: [fcn, strike-ladder, gamma-flip, coupon, case-study]
timestamp: 2026-06-03T06:03:28Z
---

# ORCL — 2026-06

**Date:** 2026-06-03
**Setup:** Private bank quoted a 6-month FCN on ORCL with 3-month
observation cadence and KO at 100% of initial. PB offering ranged from
17-19% annualized coupon depending on strike. The question was whether
to take any rung, and if so which one — and what counter-offer to
push back at if the quote was rich.

## Data snapshot

| Metric | Value | Source |
|--------|-------|--------|
| Spot | $244.58 | TV |
| IV ATM | 80.4% | UW interpolated_iv |
| IV rank | 91 | UW iv-rank |
| IV %ile 30d | 100 | UW iv-rank (rank vs trailing 30) |
| RV (HV30) | 61.0% | UW volatility/realized |
| VRP | +0.194 (RICH) | derived (`scripts/vrp.py`) |
| 25Δ skew | -0.20 | UW historical-risk-reversal-skew |
| Gamma flip | $192.50 | derived (`scripts/gex_levels.py`) |
| Put wall | $240 | derived |
| Call wall | $250 | derived |
| Max pain | $245 | UW max-pain |
| 5y max DD | -58.2% | UW OHLC |

## Strike ladder (model)

Computed via `scripts/fair_coupon.py::analyze_fcn` with default LGD 50%,
expected alive months 3.5, discount rate 4.5%, tenor 0.5 years.

| Rung | $ Strike | 6m p_KI | Model fair coupon | Dealer zone | Checklist |
|---|---|---|---|---|---|
| 70% | $171.21 | 79% | 113% (model) | **RISK** (below flip $192.50) | item 1 **FAIL** + item 3 **FAIL** (cushion only -12pp vs 5y DD -58%) |
| 75% | $183.44 | 61% | 103% | **RISK** (below flip) | item 1 **FAIL** + item 3 **PASS** |
| 80% | $195.66 | 47% | 79% | OK (above flip) | all items PASS or INFO |
| 85% | $207.89 | 36% | 60% | OK (above flip, below put wall) | all items PASS or INFO |

## Analysis

- **VRP is RICH at +0.194.** Sell-premium regime favored.
- **IV rank 91** — supports selling vol. Checklist item 4 PASSES.
- **The 70% and 75% rungs are both below gamma flip.** Dealer flow
  amplifies moves there; the model's continuous-touch barrier ignores
  this. Result: real KI probability is higher than model output, so
  the model fair coupon is an upper bound. Item 1 raises FAIL — demand
  higher strike or +5pp coupon.
- **The 80% rung at $195.66 sits just above the gamma flip ($192.50).**
  Model fair coupon ≈ 79%. Retail PB band (25-40% of model) ≈ 19.8-31.6%.
- **The 85% rung at $207.89** sits comfortably between the put wall
  ($240) and the gamma flip, with the lowest model KI probability of
  the ladder.

## Decision

**Recommended: 80% strike, target coupon 24-28% annualized.**

Why:
- 80% strike is the lowest rung where the gamma-flip check passes;
  going lower (75%, 70%) demands a strike-specific premium that PB
  won't pay.
- 24-28% coupon target lands at 30-35% of model fair (79%), which is
  inside the honest retail band and meaningfully above what the
  trader's PB initially quoted.
- The bilingual counter-offer email auto-emitted by
  `build_counter_offer_email` recommended exactly this — raise strike
  by one rung (75% → 80%) and target 30-40% of model fair as the
  coupon band.

**Rejected: 75% strike.** Item 1 FAIL on gamma flip. Even at 28% coupon
(15% above the original PB offer), the dealer-flow risk inside the
flip is uncompensated.

**Rejected: 70% strike.** Same gamma-flip failure plus item 3 failure
(only -12pp cushion above 5y max DD of -58%).

## Outcome / Lesson

**Lesson:** The gamma flip changes the FCN strike calculus
materially. The vanilla closed-form fair-coupon model assumes
driftless geometric Brownian motion and does not capture the
dealer-flow path dependency around the gamma flip. When the prospective
KI strike sits below the flip, the model's KI probability is biased
low (i.e., the true touch probability is higher), so the model's fair
coupon is an upper bound that retail PB pricing relies on without
flagging the underlying assumption.

**Rule going forward:** FCN strike must sit above the underlying's
gamma flip for the model output to be trustworthy. The
`strike_vs_gamma_flip` checklist item is the gate; without it
passing, demand strike repricing or refuse. Encoded as item #1 of the
8-item PB defense checklist in `scripts/fair_coupon.py::_checklist`.
