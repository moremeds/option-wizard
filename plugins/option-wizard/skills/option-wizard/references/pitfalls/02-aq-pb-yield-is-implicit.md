# Pitfall 02: PB AQ quotes do not include an explicit yield — "yield" is encoded in the strike discount

**Date:** 2026-06-06
**Ticker / structure:** GOOGL 12M Accumulator (AQ), 85.79% strike, 105% KO, 4-week guarantee, 2× doubling
**Loss / forgone gain:** N/A (skill-framework gap, not a trade loss) — caused the skill to incorrectly reject `analyze_quote` runs against real PB AQ screenshots

## What I did

Built the AQ/DQ framework around a `Quote.pb_quoted_yield_pa: float` field, mirroring the FCN/ELN data contract where PB always quotes an explicit annualized coupon. The fair-value comparison was `markup_pp = (pb_quoted_yield_pa − fair_yield_pa) × 100`, with REFUSE/COUNTER/ACCEPT_IF_MUST decision tiers anchored on `markup_pp`.

Tested the framework against a real PB AQ quote (GOOGL, 2026-06-03) and discovered the dataclass couldn't accept the screenshot data — there was no field on the PB report that mapped to `pb_quoted_yield_pa`.

## What actually happened

PB AQ quotes structurally do not have a quoted yield. The "yield" of an AQ is delivered as **forward stock purchases at a discount strike** — encoded in two fields:

1. `远期买入水平` (strike%) — e.g., 85.79% means the trader buys GOOGL at 85.79% of entry spot
2. The accumulation schedule (daily shares × tenor × KO/doubling adjustments)

PB profit comes from:
- The path-truncation value when KO triggers (PB keeps the forfeited forward-call value on the un-accumulated shares)
- The under-pricing of the doubling tail (forced 2× accumulation on adverse moves)

Neither of these is captured by a single "yield" number, so PB doesn't report one. The screenshot lists 强度 / 杠杆 / Scenario 1/2/3 numbers but never a coupon.

The framework's pre-existing assumption — that every PB structured product quotes a yield — was a category error: it applied FCN economics to a product that doesn't have an explicit coupon stream.

## Why the assumption was wrong

**FCN ≠ AQ structurally.** FCN is `coupon-stream + tail put`: PB pays a fixed cash coupon at every observation; trader takes shares on the tail put if spot falls below strike at expiry. AQ is `forward-buy + KO call sale`: trader buys shares at strike at every observation; PB takes the embedded knock-out call value on the unrealized forward-buys when KO triggers.

These two structures have completely different P/L decompositions:
- FCN trader receives `coupon × notional × tenor` and pays `tail_put_value`. Yield is naturally expressed as the coupon rate.
- AQ trader receives `strike_discount × E[accumulated_shares]` (= the discount × however many shares end up bought) and pays the forfeited knock-out call value + tail-doubling exposure. Yield only emerges after weighting by `alive_obs` (which depends on KO probability) and `adverse_region_prob` (which depends on the doubling tail).

By forcing AQ through the FCN data contract (`pb_quoted_yield_pa: float` required), the framework either rejected real quotes or required the orchestrator to fabricate a yield number — neither acceptable.

A second-order consequence: even if the orchestrator computed an "implied yield" upfront and stuffed it into the Quote, downstream decision-tier logic (`markup_pp > 5pp → REFUSE`) would compare a self-computed number against another self-computed number, defeating the point of having `pb_quoted_yield_pa` separated from `fair_yield_pa` at all.

## Rule going forward

**For PB AQ / DQ quotes, set `Quote.pb_quoted_yield_pa = None` and run `analyze_quote` in implicit-yield mode.** The framework derives `discount_implied_yield_pa` from `(reference_spot − strike_abs) × E[shares_accumulated]` and reports `Verdict.mode = 'implicit_yield_aq'`. Decision tiers in implicit-yield mode use INVERTED markup_pp sign convention: more-negative markup_pp = PB extracting more from trader (`markup_pp < -5.0pp → REFUSE`). For FCN/ELN quotes that DO include an explicit coupon, keep `pb_quoted_yield_pa = float` and `mode = 'markup_comparison'` (legacy behavior).

When decoding a PB quote screenshot, follow `references/aq-dq-framework.md` §7.5 mapping table — that section is the canonical field-by-field decoder so future Quote construction stays mechanical.
