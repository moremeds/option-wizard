---
type: Framework
title: FCN Framework — FCN / ELN coupon evaluation
description: FCN / ELN quote evaluation; the 8-item PB checklist + 70/75/80/85% strike ladder + bilingual counter-offer email; fair-coupon decomposition. Never route through IB.
tags: [fcn, eln, coupon, autocall, knock-in, pb-structured-product, counter-offer]
timestamp: 2026-06-03T05:49:38Z
---

# FCN Framework

## FCN structure

An FCN (Fixed Coupon Note) is a structured note that pays a guaranteed
coupon for a fixed tenor (typically 3-12 months) so long as none of the
underlying names ever touches a knock-in (KI) barrier. The headline
features:

- **Underlying:** 1 to 3 stocks, often correlated (single-name or
  worst-of basket).
- **Tenor:** 3, 6, or 12 months.
- **Observation:** monthly or quarterly autocall checks.
- **KI barrier:** typically 70-85% of initial spot for each name.
- **KO barrier:** typically 100-105% — if any single observation closes
  above KO, the note autocalls and pays accrued coupon + principal.
- **Coupon:** fixed annualized rate, accrues monthly.

**Payoff in words.** If at any observation date all names close above
KO, the note redeems early: you get principal back + accrued coupon.
If no autocall fires, the note runs to maturity. At maturity, if no
name ever touched its KI, you get principal back + final coupon. If
any name touched KI **and** that name finishes below initial spot,
you are delivered shares of the **worst-performing** name at the
initial spot price (taking a loss equal to how far below initial it
finished).

The dangerous asymmetry: coupon is a fixed small upside, while the
worst-of loss can be 30-50% of notional.

## Fair coupon math

The closed-form proxy used in `scripts/fair_coupon.py::single_name_ki_prob`:

```
p_ki ≈ 2 · Φ(ln(B) / (σ · √T))
```

where `B` is the barrier as a fraction of initial (e.g., 0.75), σ is
annualized vol (UW IV30 proxy), and T is the tenor in years. Φ is the
standard normal CDF.

**Why the factor of 2.** This is the reflection-principle approximation
for a continuously-monitored one-touch barrier on a driftless geometric
Brownian motion. The driftless assumption matches what we want for the
worst-of MC consistency check (`joint_ki_prob_mc` collapses to
`single_name_ki_prob` at ρ→1).

**Why continuous-touch overstates.** FCN observation is discrete
(weekly or monthly), not continuous. The closed-form bound assumes any
intraday touch counts; the actual note only checks at observation
dates. So the model probability is an upper bound.

**Empirical scaling rule of thumb.** The institutional fair coupon
(what UBS/CS would pay each other) is roughly **50-65% of the model
output**. The retail PB markup adds another layer; PB quotes typically
land at **25-40% of the model output** — i.e., the PB pockets the gap
between the institutional fair (~55%) and the retail offer (~30%).

Worked example. ORCL with IV 0.804, 6m tenor (~126 trading days), 75%
barrier:

- `single_name_ki_prob(0.804, 0.75, 126)` ≈ **0.613**
- `fair_coupon_proxy(p_ki=0.613, LGD=0.50, alive=3.5m, r=0.045, T=0.5)`
  ≈ **1.027** annualized (model)
- Institutional fair ≈ 0.55-0.65 × 1.027 ≈ **0.56-0.67** annualized
- Retail PB fair band ≈ 0.25-0.40 × 1.027 ≈ **0.26-0.41** annualized
- If PB quotes 18% coupon → `_verdict` returns `"rich"` (below the 25%
  floor). Predatory.
- Counter-offer recommendation: raise strike to 80% (lower KI prob) AND
  raise coupon to 30-40% of new model fair.

## The 8-item PB defense checklist

(Implemented in `scripts/fair_coupon.py::_checklist`; surfaced in each
ladder rung.)

1. **`strike_vs_gamma_flip`** — does the KI strike sit above the
   underlying's gamma flip? If below, dealer flow is in the
   amplifying regime → demand +5pp coupon or raise strike.
2. **`markup_vs_iv_rank`** — is the PB quoted coupon ≥25% of the model
   fair? <25% is predatory ("FAIL"); 25-30% needs a counter ("WARN").
3. **`ki_buffer_vs_5y_max_dd`** — is the KI buffer below current spot
   ≥10pp away from the 5y max drawdown? E.g., 75% strike on a name
   with 5y max DD of −58% has cushion (0.75 − 1.0) − (−0.58) = +0.33pp,
   passes. A 50% strike with the same DD has cushion only +0.08pp,
   FAIL.
4. **`iv_rank_threshold`** — is IV rank ≥50? Below 50, the trader is
   selling cheap vol; consider a monthly short put instead of a 6m
   lockup.
5. **`skew_penalty`** — is 25Δ risk-reversal skew flat or only mildly
   negative? Below −0.25 means the market is paying up for downside
   protection — demand +3-5pp coupon for left-tail compensation.
6. **`tenor_anchor`** (INFO) — translate the annualized coupon to an
   absolute dollar return given the expected alive duration (~3.5
   months for a 6m FCN under typical autocall probability).
7. **`liquidity_no_secondary`** (INFO) — FCN has no secondary market;
   only exit is hold-to-maturity. Sized accordingly (never >10% of
   liquid NLV).
8. **`issuer_credit_risk`** (INFO) — pull the PB parent's senior
   unsecured rating and 5y CDS spread. Flag any SPV-issued notes
   (often used to lower stated issuer rating below the parent).

A rung with any FAIL automatically gets the bilingual counter-offer
email attached by `analyze_fcn`. A rung with WARNs only does not (the
trader chooses whether to engage).

## Strike ladder workflow

`analyze_fcn(ticker, strike_pcts=[0.70, 0.75, 0.80, 0.85], ...)` emits
four rungs by default. Read top-down:

| Rung | KI buffer | Coupon expected | Typical reaction |
|---|---|---|---|
| 70% | Aggressive — only with cushion vs 5y max DD | Highest | Reject unless name is range-bound mega-cap |
| 75% | Standard | Mid-high | Default for first-look at "shall I take this" |
| 80% | Conservative | Mid-low | Default counter when 75% rung fails on items 1, 3, or 5 |
| 85% | Defensive | Lowest | Use when name has near-term catalyst within tenor |

The ladder is generated regardless of whether a PB quote was supplied.
With `pb_quoted_coupon=...`, each rung also gets a `verdict` field
(`fair`/`rich`/`cheap`) and the counter-offer email is auto-attached
to rich verdicts.

## Worst-of basket adjustments

`analyze_fcn_basket` handles 2-name baskets using `joint_ki_prob_mc`
(Monte Carlo simulation of correlated geometric Brownian paths). The
key output is `p_ki_either` — the probability that **at least one** of
the two names touches its barrier over the tenor.

**Diversification premium.** A 2-name worst-of FCN should pay strictly
more coupon than the worst single name in isolation, because the joint
either-touch probability is strictly higher than the single-touch. The
script's heuristic recommendation:

```
premium_min_pp = (1.0 − rho) · 0.30 · fair_worst_single
```

I.e., at ρ=0.5, the basket coupon should exceed the worst-single coupon
by at least 15% of the worst-single fair. PB quotes that come in at or
below the worst-single coupon are pocketing the diversification penalty.

## Counter-offer email usage

`build_counter_offer_email` produces a Chinese-first, English-second
formatted body. The trader pastes it into their email client and sends
to the banker. Typical PB rebuttals and responses:

- *"This is the best we can do for this size."* → Ask for the same
  structure on a smaller notional with the better coupon; pricing
  doesn't change linearly with size for small clients.
- *"The 80% strike isn't available on this name today."* → Counter to
  a different underlying with similar volatility profile (use UW
  IV-rank scan).
- *"We can move the coupon but only by 1pp."* → If still below the 25%
  floor, refuse. The model number is what matters; PB-side concessions
  below the floor are predatory.
- *"The basket gives you better coupon."* → Only true if the
  diversification premium is paid; demand the per-name and basket
  coupons side by side.

When the PB engages, redo `analyze_fcn` with the new strike/coupon and
re-evaluate. The objective is one of:

1. Coupon ≥ 30% of model fair, **and** all 5 first checklist items
   PASS or WARN (not FAIL). Take it.
2. Otherwise, **walk** — and revisit the same ticker as a 30-45 DTE
   short put / bull put spread, where pricing is exchange-listed and
   transparent.

## What FCN is bad at

FCN is materially worse than CC / CSP / bull put spread when:

- **Low IV rank** (<50) — short-dated listed options under-price the
  same vol exposure; FCN locks you into 6m of stale vol.
- **Near-term catalyst** — earnings, FDA, regulatory action within the
  tenor introduces binary risk the model doesn't price. Use a 30-45 DTE
  defined-risk spread that expires before the catalyst.
- **Want flexibility to roll** — FCN has no roll mechanic. Listed
  options can roll out to the next month at any time.
- **Want to harvest gamma scalping** — FCN is a passive structure;
  active delta-hedging requires listed options on the underlying.

Always check these conditions before recommending FCN. The
`_checklist` items 4 (IV rank) and 6/7 (tenor anchor, liquidity)
encode the first three of these; the catalyst-clock check lives in
the prose surrounding the script output (TV news pull).
