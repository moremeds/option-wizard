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

**AQ implicit-yield mode.** Real PB AQ quotes (e.g., the GOOGL 2026-06-03 deal) do NOT include a `pb_quoted_yield_pa` field. The "yield" of an AQ is structurally the strike discount × accumulated shares — encoded in `远期买入水平` (strike%) and the accumulation schedule, not as a coupon. When the orchestrator decodes a PB quote that lacks an explicit yield, set `Quote.pb_quoted_yield_pa = None` and `analyze_quote` enters **implicit-yield mode**:

```
discount_per_share        = entry_spot − strike_abs
expected_shares           = shares_per_obs × alive_obs × (1 + (doubling − 1) × adverse_region_prob)
expected_discount_value   = discount_per_share × expected_shares
discount_implied_yield_pa = expected_discount_value / (notional_per_obs × n_obs × tenor_yr)

# Decision tier inverted vs FCN markup_pp:
markup_pp = (discount_implied_yield_pa − fair_yield_pa) × 100
# More-NEGATIVE markup_pp = PB extracting more from trader.
#   markup_pp < -5.0pp  → REFUSE
#   markup_pp < -1.5pp  → COUNTER
#   else                → ACCEPT_IF_MUST
```

Verdict carries `mode='implicit_yield_aq'` and `discount_implied_yield_pa` (rather than the FCN-style `markup_comparison` mode). The counter-offer email emits "PB take" instead of "PB markup" in this mode.

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
| 4 | `shares_per_obs × strike_abs × n_obs × doubling_factor > 0.10 × NLV` (max-exposure notional) | True worst-case cash commitment > 10% portfolio NLV. **NOTE**: this formula intentionally includes `strike_abs` (the price PB will buy you in at — NOT spot) and `doubling_factor` (worst-case forced accumulation rate). The legacy `daily_notional × n_obs` formula systematically understated exposure on shares-denominated PB AQ contracts by 10-20%. |
| 5 | `tenor_months > 18` | PB markup grows super-linearly past 18M; longer tenors compound their edge |
| 6 | **ANY** earnings date in middle 50% of tenor (iterates `s.earnings_dates_iso` if provided, else quarterly-extrapolates from `s.earnings_date_iso`) | Binary event + doubling + KO is unmanageable. **NOTE**: legacy behavior only checked the single next-ER, which silently passed 12M+ tenors that had Q3 / Q4 ERs in middle 50%. Iteration is mandatory for tenors ≥ 9M. |

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

## §7.5 Real PB quote field decoding

PB AQ quotes arrive as PDF screenshots, broker portals, or pasted Chinese text. The mapping below shows how each field in the report decodes into the `Quote` / `Snapshot` data contract. Use this table when the trader sends a screenshot — start by filling these fields, then run §8 workflow.

| PB quote label (Chinese) | English | Quote / Snapshot field | Notes |
|---|---|---|---|
| 标的 | Underlying | `Quote.ticker` | |
| 远期买入水平 (%) | Forward buy level (%) | `Quote.strike_pct` | PB shows e.g. "85.79%" → 0.8579. The price PB will buy the trader in at. |
| 入场价 | Entry spot | `Quote.entry_spot` | Reference spot PB locked strike + KO against at quote time. Distinct from current spot (`Quote.spot`) for post-trade analysis. |
| 闭市价 | Close at report time | `Snapshot.spot` (if PDF was generated after market close) | If PDF was generated intraday during placement, use that spot. |
| 买入价 | Buy price (= entry × strike%) | derived = `strike_pct × entry_spot` | PB displays for reader convenience; framework computes it. |
| KO敲出水平 (%) | KO knock-out level (%) | `Quote.ko_pct` | PB shows "105.00%" → 1.05. |
| 敲出价 | KO absolute price | derived = `ko_pct × entry_spot` | PB displays; framework computes. |
| 保证期 (weeks) | Guarantee / non-call period | `Quote.guarantee_period_weeks` | KO cannot trigger during this window. Accumulation still runs. Standard 4 weeks. |
| 期限 / 投资期限 | Tenor | `Quote.tenor_months` | PB shows "12个月" → 12. |
| 杠杆倍数 | Doubling factor | `Quote.doubling_factor` | PB shows "2x" → 2.0. |
| 每日买入 (shares) | Daily buy (base) | `Quote.daily_shares` | PB writes literal share count e.g. "4 shares". Do NOT convert to USD notional. |
| 杠杆股数 (shares) | Leveraged daily buy | derived = `daily_shares × doubling_factor` | PB displays the doubled count for convenience. |
| 货币 | Currency | (info only — settlement always USD-denominated for US-equity AQ) | |
| 报价方式 | Order type | (info only — typically "Market") | |
| 成本价 | Cost basis | derived = `strike_abs` | Per-share cost trader will pay (= strike). |
| 浮盈 / 浮亏 (%) | Unrealized P/L (%) | derived by `evaluate_placed_aq` post-trade | (current_spot − strike_abs) / strike_abs |
| Scenario 1 (KO during guarantee) | shares × strike | `Verdict.scenarios['ko_during_guarantee']` | Best case: KO triggers at first opportunity after guarantee window. |
| Scenario 2 (no KO, no doubling) | shares × strike × n_obs | `Verdict.scenarios['full_term_no_doubling']` | Base case: spot stays above strike, no KO. |
| Scenario 3 (max exposure) | shares × strike × n_obs × doubling | `Verdict.scenarios['max_exposure_all_doubled']` | Worst case: spot crashes below strike, doubling fires for the full tenor. |
| (not in quote) | Next earnings date(s) | `Snapshot.earnings_date_iso` + `earnings_dates_iso` | Pull from UW `get_company_info` / `get_earnings_history`. For tenors ≥ 9M, populate `earnings_dates_iso` with the full list (refusal #6 iterates). |
| (not in quote) | IV rank | `Snapshot.iv_rank` | UW only. Required for refusal #2. |
| (not in quote) | ATR(14) | `Snapshot.atr_14_pct_of_spot` | TV only. Required for refusal #3. |

**Critical**: `pb_quoted_yield_pa` is **NOT** in a PB AQ quote. The PB report shows the strike discount (e.g., 85.79% = 14.21% off entry) and the accumulation schedule — the "yield" is implicit in those two numbers. Always set `Quote.pb_quoted_yield_pa = None` for PB AQ decoding; analyze_quote then enters implicit-yield mode (see §3).

## §8 Live-quote workflow (7 steps)

1. Trader provides Quote params (or pastes PB quote text / sends screenshot). If screenshot, decode per §7.5 into the `Quote` / `Snapshot` contract.
2. Run `_check_refusal_red_lines(quote, snapshot, nlv_usd)`. If non-empty, return `REFUSE` verdict with reasons + the 3-scenario projection. Stop. (Trader still sees the scenarios so they can verify whether the deal would have been REFUSEd on a larger NLV.)
3. Orchestrator pulls chain data per workflow 5 §2 (live → IB, analytical → UW). Builds Snapshot. For tenors ≥ 9M, populate `Snapshot.earnings_dates_iso` with the full quarterly schedule from UW.
4. Run `analyze_quote(q, s)` to get full Verdict with breakdown + data_provenance + 3 scenarios + mode flag.
5. Run `optimize_terms(q, s)` to get sorted Pareto frontier of negotiation levers. Note: in implicit-yield mode, leverage_score uses inverted sign (mutations that increase `discount_implied_yield_pa` toward `fair_yield_pa` are the wins).
6. Run `build_counter_offer_email(v, q)` to assemble bilingual draft. Email automatically switches preamble between markup-comparison and implicit-yield-aq modes.
7. Present all five artifacts (checklist + breakdown + scenarios + Pareto + email) to trader.

Final decision rules:
- **markup_comparison mode** (PB quoted a yield — typical FCN/ELN):
  - `markup_pp > 5.0` OR refusal lines triggered → `REFUSE`
  - `1.5 < markup_pp ≤ 5.0` → `COUNTER` (run lever negotiation)
  - `markup_pp ≤ 1.5` AND no red lines → `ACCEPT_IF_MUST` (institutional-grade pricing)
- **implicit_yield_aq mode** (PB AQ — no quoted yield):
  - `markup_pp < -5.0` (PB extracting > 5pp from implicit yield) → `REFUSE`
  - `-5.0 ≤ markup_pp < -1.5` → `COUNTER`
  - `markup_pp ≥ -1.5` AND no red lines → `ACCEPT_IF_MUST`

## §9 Post-trade audit workflow

The pre-trade workflow above answers "should we accept this PB quote?". For trades already placed (PB structured products can rarely be unwound), the question becomes "where are we now, and how bad can it get?". Use `evaluate_placed_aq(quote, snapshot, current_spot, observations_elapsed, shares_accumulated, nlv_usd)`.

**When to invoke:**
- Weekly position book review touches an active PB AQ
- Approaching guarantee period end (4 weeks after placement for typical AQ)
- Earnings release inside tenor — pre-ER and post-ER audit
- Spot approaches KO barrier (< 2% distance) or strike (< 5% above)

**Input requirements:**
- `Quote.entry_spot` set to PB's reference spot at placement (not current). This freezes `strike_abs` and `ko_abs` against the historical anchor — current spot drift no longer pollutes the comparison.
- `current_spot` from fresh TV pull (T-1 close or live).
- `observations_elapsed` derived from placement_date → current_date by trading-day count.
- `shares_accumulated` from PB statement (don't rely on base-case formula — actual count may differ if doubling fired on past days).

**Output dict:**
- `current_state`: shares accumulated, cost basis total, market value, unrealized P/L USD + %.
- `barriers`: `strike_abs` / `ko_abs` / `pct_above_strike` / `pct_below_ko` / `in_guarantee_period` (bool).
- `forward`: `observations_remaining`, `days_to_guarantee_end`, `forward_ko_prob` (over remaining callable window), `max_additional_exposure_usd` (= remaining_obs × shares × strike × doubling), `max_additional_exposure_pct_of_nlv`.
- `crash_scenario`: a -20% from-here crash (configurable) — `spot_at_crash`, `additional_shares_doubled`, `total_shares_at_year_end`, `total_cost_basis`, `market_value_at_crash`, `pnl_usd`.
- `monitor_level`: `"near_ko"` (< 2% to KO — call your PB to confirm KO trigger logic), `"hedge_recommended"` (< 5% above strike — doubling tail is live, consider OTM put hedge), `"monitor"` (default).

**Hedging the doubling tail** (when `monitor_level == "hedge_recommended"`): the PB AQ commits the trader to forced accumulation at strike if spot crashes. The natural hedge is a listed-options OTM put spread expiring near the tenor mid-point. Size: 1× the `max_additional_exposure_usd / strike_abs` share equivalent (covers the doubling-activated incremental shares). See `references/strategies.md` "OTM put spread overlay" for cost-budget framing.
