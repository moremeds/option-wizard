# AQ / DQ Framework

Private Bank structured products evaluation — Accumulator (AQ) and Decumulator (DQ).

**Framing:** the trader receives these pitches regularly. The product is structurally hostile (asymmetric payoff, KO cuts client upside, doubling magnifies client tail loss). This framework's job is **"less screwed, not unscrewed"** — expose PB markup, identify negotiation leverage, and short-circuit clearly bad deals.

## §1 What is AQ / DQ

**Accumulator (AQ)** — client agrees to BUY stock at a discount strike (typically 95% spot) at every observation point over a fixed tenor (e.g., 12 months).

- **Knock-out (KO)** above current spot (typically 103%): contract terminates if spot ever touches the barrier. Client loses upside; PB keeps the path-dependent call value.
- **Doubling factor** (typically 2×): if spot is BELOW strike at observation, client must buy 2× the agreed shares — magnifies losses in declines.
- **Client position equivalent:** short OTM put at strike (with doubling) + short knock-out call at KO + accumulation leg.

**Decumulator (DQ)** — mirror image. Client agrees to SELL stock at premium strike (e.g., 105% spot) at every observation; KO is below current spot (e.g., 97%); doubling activates when spot is ABOVE strike.

**Buffett's nickname for AQ: "I-kill-you-later."** Marketed during the 2007–2008 HK retail boom, devastated holders in the subsequent crash.

**Typical PB pitch decoded:**
- "Boost your yield to 9% on names you'd buy anyway" → you'd buy IF stock holds; you're forced to buy MORE if it crashes.
- "KO protects you from runaway upside cost" → KO protects PB from owing you the call value.
- "2× is standard market practice" → 2× is PB-standard; institutional clients negotiate to 1×.

## §2 The 4 things PB profits from

1. **IV markup.** PB's quoted yield embeds an implied vol higher than the listed-chain mid; the difference is gross profit.
2. **Skew markup.** AQ/DQ tail legs sit on the steep part of the smile. PB collects high OTM put IV from you but funds the structure at ATM IV → keeps the skew premium.
3. **KO-side optionality.** When KO triggers, PB keeps the unrealized value of the embedded long call (for AQ) — not refunded to client. This is the biggest single source of PB profit on path-friendly tickers.
4. **Doubling tail underpricing.** The 2×-on-decline leg is a short put on 2× notional at strike. PB doesn't credit you the full vol-adjusted premium of this leg — typically credits ~50% of fair value.

## §3 Fair-value heuristic + data-source discipline

**Data-source discipline (permanent methodology principle).** Listed-strike option price / IV / greeks **always read directly** from UW chain or IB chain (per source-selection mode in workflows-overview.md §Workflow 5). **Never recompute via BSM inside the script.** The script computes only quantities the data providers do not serve: barrier termination probabilities, accumulation cash-flow present value, barrier-adjustment factors, and the final fair vs quoted pp delta. Every numeric field in the Verdict carries a `data_provenance` entry marking source (UW direct / IB direct / TV / computed / fallback) + timestamp + staleness.

**Fair-value decomposition** — AQ/DQ payoff to client can be expressed as a sum of listed-option legs adjusted for the KO barrier. AQ vs DQ flips which right (put/call) is read at strike% / ko% / tail strike (see §"Direction mirroring" below):

```
                                       strike_leg_right    ko_leg_right    tail_strike    tail_right
AQ (accumulator):                      put                 call            0.50           put
DQ (decumulator, mirror image):        call                put             1.50           call

fair_payoff_to_client_PV =
    + short_premium_PV at strike%      (chain mid × shares_per_obs × alive_obs × doubling)
    − pb_ko_leg_PV at ko%              (chain mid × shares_per_obs × forfeited_obs)
    − doubling_tail_PV at tail strike  (chain mid × cumulative_shares × doubling × tail_activation_prob)

where:
    alive_obs        = E[N_alive] = ko_prob_total / p_per_obs
                       (with p_per_obs = 1 − (1 − ko_prob_total)^(1/n))
    forfeited_obs    = n_obs − alive_obs
    cumulative_shares = shares_per_obs × n_obs
    shares_per_obs   = daily_notional_usd / spot

pb_quoted_payoff_PV =
    pb_quoted_yield_pa × daily_notional × n_obs × tenor_yr

markup_PV = pb_quoted_payoff_PV − fair_payoff_to_client_PV
fair_yield_pa = fair_payoff_to_client_PV / (daily_notional × n_obs × tenor_yr)
markup_pp = (pb_quoted_yield_pa − fair_yield_pa) × 100   # in percentage points
```

**Why `alive_obs` is not just `n_obs × (1 − ko_prob)`:** the simple approximation assumes each observation is independently subject to the cumulative KO probability, which double-counts. The exact expectation when KO survival is iid per observation is `E[N_alive] = (1 − q^n) / (1 − q) = ko_prob_total / p_per_obs`. At ko_prob_total = 0.5, n = 252, the exact formula gives ~182, the simple approximation gives 126 — a 30% gap on a quantity that drives all three leg values.

**Where each input comes from:**

| Input | Source | Notes |
|---|---|---|
| `spot` | TV (default) / IB snapshot (live-trade mode) | hard rule #2 |
| `chain[expiry][strike%][put or call]["mid"]` | IB (live) / UW (analytical) | per workflow 5 §2 |
| `chain[expiry][strike%][put or call]["iv"]` | same | used in `ko_probability` calc |
| `ko_probability` | **computed** (BSM first-passage with Broadie-Glasserman discrete-monitoring correction) | UW lacks barrier products |
| `n_obs` | computed from `tenor_months × obs_freq` | derived |
| `iv_rank`, `rv_30d`, `rv_90d` | UW | derivative metrics |
| `gex_levels`, `max_pain` | UW | path-context |
| `max_drawdown_5y` | fallback only | when chain doesn't cover deep-OTM tail (50% spot put) |

**Verdict carries `data_provenance` field** mapping every numeric output to its source. Example:

```python
verdict.data_provenance = {
    'spot': {'value': 234.91, 'source': 'TV', 'timestamp': '...', 'staleness_s': 3},
    'chain_source': {'source': 'IB', 'pulled_at': '...', 'subscription_realtime': True},
    'strike_leg_mid': {'value': 5.20, 'source': 'IB chain[2026-12-18][0.95]["put"]["mid"]'},
    'ko_leg_mid': {'value': 4.10, 'source': 'IB chain[2026-12-18][1.03]["call"]["mid"]'},
    'iv_at_ko': {'value': 0.34, 'source': 'IB chain[2026-12-18][1.03]["call"]["iv"]'},
    'ko_probability': {'value': 0.42, 'source': 'computed (BSM first-passage)', 'inputs': {...}},
    'tail_fallback_used': False,
}
```

## §4 The 8-item PB checklist

Every quote evaluation must address all 8 items. Missing items = PB hasn't disclosed; insist on disclosure before evaluation.

1. **Direction** — AQ (you buy on accumulation) or DQ (you sell on decumulation)?
2. **KO type** — American (continuous monitoring during market hours, easier to KO) or European (only at expiry, harder to KO)? American is more client-friendly.
3. **Doubling factor** — 1× / 1.5× / 2× / 2.5× / 3×? ≥ 3× triggers refusal (see §6).
4. **Observation frequency** — daily / weekly / monthly? Daily increases PB's edge (more KO chances + more accumulation events).
5. **Strike + KO distance from spot** — `strike_pct` and `ko_pct` as % of spot. KO within 1 ATR(14) of spot triggers refusal (see §6).
6. **Tenor** — months; tenor > 18M triggers refusal (PB markup grows non-linearly past 18M).
7. **Settlement** — cash (USD difference settled) or physical (shares delivered)? Physical delivery on AQ ties up your capital; cash gives flexibility.
8. **PB yield decomposition transparency** — can PB break the quoted yield into (a) accumulation discount, (b) KO call value retained, (c) doubling premium, (d) PB margin? PB unwillingness to disclose is itself a markup signal.

## §5 "Less screwed" levers — term parameters that reduce PB edge

Each lever shows: parameter change → typical markup reduction (in pp) → PB pushback difficulty (1=easy, 5=PB will refuse outright). The numbers are heuristic ranges from market practice; `optimize_terms` will compute exact deltas per quote.

| Lever | From → To | Markup ↓ (pp) | PB pushback | Notes |
|---|---|---|---:|---|
| **Tenor cut** | 12M → 6M | 1.5 – 2.5 | 2 | PB usually negotiable; shorter tenor = less of their edge accrues |
| **Tenor cut** | 12M → 3M | 3.0 – 5.0 | 3 | More aggressive; PB may push back on minimum tenor |
| **KO push out** | 103% → 105% | 0.8 – 1.5 | 3 | PB hates this — KO probability drops, they keep less call value |
| **KO push out** | 103% → 107% | 1.5 – 2.5 | 4 | Aggressive |
| **Doubling reduction** | 2× → 1.5× | 1.0 – 2.0 | 4 | Big concession from PB; biggest single markup source |
| **Doubling reduction** | 2× → 1× | 2.0 – 3.5 | 5 | PB rarely agrees on 1×; "institutional terms" — try anyway |
| **Observation freq** | daily → weekly | 0.5 – 1.0 | 2 | Easy concession; PB often agrees |
| **Observation freq** | daily → monthly | 1.0 – 1.8 | 3 | Bigger but harder |

**Negotiation tactics:**
1. Always ask for tenor cut + obs-freq change first (low pushback, decent markup reduction).
2. If PB resists, threaten to walk and push for doubling reduction (high pushback but highest leverage).
3. KO push-out is a fallback if doubling won't move.
4. Combining 2-3 levers compounds the reduction; `optimize_terms` ranks by combined effect.

## §6 Refusal red lines — 6 hard refusals

If ANY of the following triggers, output `decision='REFUSE'` immediately (before any chain pull / fair-value math). Document the triggered reason; do NOT continue to evaluate.

| # | Trigger | Why |
|---|---|---|
| 1 | `doubling_factor >= 3.0` | Tail loss scales linearly with doubling; 3× is institutional-only territory, retail PB pricing fails |
| 2 | `direction='AQ' AND iv_rank < 30` | Selling vol when vol is cheap means PB's vol-markup % is highest; you're double-screwed |
| 3 | `abs(spot − ko_barrier) < 1 × ATR(14)` | KO virtually guaranteed to trigger early; you get fees but ~zero of the yield |
| 4 | `daily_notional × n_obs > 0.10 × NLV` (total accumulated notional over the tenor) | Single-name notional > 10% portfolio NLV concentrates tail risk |
| 5 | `tenor_months > 18` | PB markup grows super-linearly past 18M; longer tenors compound their edge |
| 6 | Earnings date falls in middle 50% of tenor | Binary event + doubling + KO is unmanageable |

If trader insists on proceeding despite a red line, framework still runs evaluation but `decision` stays `REFUSE` and counter-offer email's preamble explicitly notes the red line.

## §7 Counter-offer email template

Bilingual (Chinese first, English second). Generated by `build_counter_offer_email`. Personalize the placeholder fields from the Verdict.

**Chinese version structure:**

```
[PB 联系人姓名]，你好，

谢谢你 [date] 报的 [TICKER] [AQ/DQ] quote。我做了详细的 fair-value 分析，
对比 listed-chain mid 价格和 barrier-adjusted 现金流贴现:

  PB 报价 yield:     [PB_QUOTED]% p.a.
  Fair-value yield:  [FAIR_YIELD]% p.a.
  Markup:           [MARKUP_PP] pp = ~$[PB_ANNUAL_PROFIT] / 年 抽成

要进一步推进, 我需要以下让步:

  1. [LEVER_1_DESCRIPTION] (markup 降约 [LEVER_1_DELTA] pp)
  2. [LEVER_2_DESCRIPTION] (markup 降约 [LEVER_2_DELTA] pp)
  3. [LEVER_3_DESCRIPTION] (markup 降约 [LEVER_3_DELTA] pp)

调整后目标 markup ≤ 1.5pp = 接近机构定价。如能配合, 请重新报价;
否则我们 pass 这单。

Best,
[trader]
```

**English version structure:**

```
Hi [PB contact name],

Thanks for the [TICKER] [AQ/DQ] quote on [date]. I ran a fair-value
breakdown against listed-chain mids with barrier-adjusted cash flows:

  PB quoted yield:   [PB_QUOTED]% p.a.
  Fair-value yield:  [FAIR_YIELD]% p.a.
  Markup:           [MARKUP_PP] pp ≈ $[PB_ANNUAL_PROFIT]/yr take

To proceed, I'd need the following concessions:

  1. [LEVER_1_DESCRIPTION] (markup ↓ ~[LEVER_1_DELTA] pp)
  2. [LEVER_2_DESCRIPTION] (markup ↓ ~[LEVER_2_DELTA] pp)
  3. [LEVER_3_DESCRIPTION] (markup ↓ ~[LEVER_3_DELTA] pp)

Target post-concession markup ≤ 1.5 pp (institutional-pricing level).
If you can re-quote on these terms, happy to discuss; otherwise we'll
pass on this one.

Best,
[trader]
```

## §8 Live-quote workflow (6 steps)

1. Trader provides Quote params (or pastes PB quote text).
2. Run `_check_refusal_red_lines(quote, snapshot, nlv_usd)`. If non-empty, return `REFUSE` verdict with reasons. Stop.
3. Orchestrator pulls chain data per workflow 5 §2 (live → IB, analytical → UW). Builds Snapshot.
4. Run `analyze_quote(q, s)` to get full Verdict with breakdown + data_provenance.
5. Run `optimize_terms(q, s)` to get sorted Pareto frontier of negotiation levers.
6. Run `build_counter_offer_email(v, q)` to assemble bilingual draft. Present all four artifacts (checklist + breakdown + Pareto + email) to trader.

Final decision rules:
- `markup_pp > 5.0` OR refusal lines triggered → `REFUSE`
- `1.5 < markup_pp ≤ 5.0` → `COUNTER` (run lever negotiation)
- `markup_pp ≤ 1.5` AND no red lines → `ACCEPT_IF_MUST` (institutional-grade pricing; if trader must engage, this is the best they'll get)
