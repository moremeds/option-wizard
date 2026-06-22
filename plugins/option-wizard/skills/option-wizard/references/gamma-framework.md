---
type: Framework
title: Gamma Framework — dealer GEX to flip / put wall / call wall
description: Dealer GEX → gamma flip, put wall, call wall; oi_cluster vs aggregate definitions for short-dated trades; multi-factor probability map from chain + IV term + flow.
tags: [gamma, gex, dealer-positioning, gamma-flip, put-wall, call-wall]
timestamp: 2026-06-03T05:47:19Z
---

# Gamma Framework

## What GEX is

GEX — gamma exposure — is a market-wide proxy for dealer positioning.
When dealers are net long gamma, their hedging dampens price moves: as
spot rises they sell, as spot falls they buy. When dealers are net short
gamma, the same delta-hedging amplifies moves: rallies beget more buying,
selloffs beget more selling.

UW reports per-strike GEX in `/api/stock/{ticker}/spot-exposures/strike`.
Each row is a `(strike, gex)` pair. Positive GEX = dealers long gamma at
that strike; negative = dealers short. The aggregate behavior across all
strikes determines the regime.

## Reading UW `spot-exposures/strike`

Top-level JSON shape: `{"data": [...]}`. Each row in `data` minimally
contains `strike` (float, dollar) and `gex` (float, signed gamma
notional in some scaled unit — only signs and relative magnitudes matter
for level identification). UW occasionally returns null GEX on illiquid
strikes; `scripts/gex_levels.py::_sorted_by_strike` drops those rows
rather than crashing the analysis.

A typical ORCL response on a normal day spans ~40-80 strike rows from
roughly 50% below spot to 30% above. The interesting structure is
usually in the band from `0.85 * spot` to `1.15 * spot`.

## Gamma flip

**Definition.** The strike at which cumulative GEX (summed from low
strike to high) crosses zero. Below the flip, dealers are net short
gamma (amplifying regime). Above, net long (dampening regime).

**How `scripts/gex_levels.py::_gamma_flip` computes it.** Iterate
strikes in ascending order, accumulating GEX. When `prev_cum * cur_cum
< 0`, linearly interpolate between the two strikes:

```
flip = prev_strike + (-prev_cum / (cur_cum - prev_cum)) * (cur_strike - prev_strike)
```

Returns `None` if no zero crossing exists in the strike range.

**What it means.** When spot is above the flip and headed toward it,
expect dampening — rallies stall, drawdowns get bought. When spot is
below the flip and headed lower, expect amplification — selling
accelerates. Concrete example: with the FCN strike ladder, the 70%
strike ($171 against spot $245 on ORCL) sits well below a flip near
$192 → `_tag_zone` returns `"RISK: below gamma flip (dealer short
gamma)"` and `_checklist` raises a FAIL on `strike_vs_gamma_flip`.

## Put wall / Call wall

**Put wall.** Strike below spot with the largest positive GEX. Dealers
who sold puts at that strike must buy as spot approaches it (to stay
delta-hedged), which is mechanically supportive. Acts as soft floor.

**Call wall.** Strike above spot with the largest negative GEX in
absolute terms. Dealers short calls there sell into rallies that
approach it, acting as soft resistance.

Computed by `scripts/gex_levels.py::_put_wall` and `_call_wall`.

**Strike-selection interaction.**

- FCN strikes should sit **above the gamma flip** to avoid pricing the
  barrier into a dealer-short regime.
- Bull put spread short leg should sit **above the put wall** to lean
  on dealer-supportive flow.
- Iron condor short call leg should sit **below the call wall** for
  the same reason on the upside.
- Bear call spread short leg should sit **above the call wall** —
  dealer flow does the heavy lifting against an upside breach.

Example: ORCL on a recent reading, flip $192.50, put wall $240, call
wall $250. A 30 DTE iron condor with short put 235 / long put 230 and
short call 250 / long call 255 places one short leg right at the call
wall (acceptable, supportive) and one short leg below the put wall
(suboptimal — should target 240 or 242). The script's checklist would
not raise a FAIL for the put-wall mismatch (item not in the v1 8-item
checklist) but the prose recommendation should flag it.

## Vol regime label

UW's dashboard sometimes surfaces a "dampening / amplifying" label per
ticker. The mechanical interpretation:

- **Dampening:** aggregate GEX is positive AND spot is above the flip.
  Implied vol tends to fade faster than realized. VRP often positive.
- **Amplifying:** aggregate GEX is negative OR spot is below the flip.
  Implied vol can persistently exceed realized as gap-risk priced in.

Option-wizard does not consume the label directly (it derives the
underlying signals itself), but when both UW's label and our
`_tag_zone` disagree, prefer ours — UW's label aggregates across all
strikes, while we evaluate the specific strike under consideration.

## 0DTE GEX caveat

Same-day expirations (0DTE) skew GEX readings, especially near close.
Dealer short-gamma positioning that will be flat by end-of-day still
shows in the spot-exposures snapshot. Two practical adjustments:

1. When evaluating a 30-45 DTE structure (the normal option-wizard
   working horizon), ignore the 0DTE strike from `spot_gex_by_strike`
   before calling `compute_levels`. UW doesn't filter for us; you can
   filter caller-side by inspecting `expiry` if present in the row,
   or by simply re-running near open (pre-0DTE pinning) rather than
   3:55pm ET.
2. The gamma flip can drift several dollars intraday as 0DTE positioning
   rolls. For position-sizing decisions, use the morning reading
   (~10am ET) as the daily anchor, not the live 3:30pm number.

If 0DTE skew makes a particular reading nonsensical (flip moved >5% of
spot in 4 hours with no underlying news), discard the reading rather
than trade against it.
