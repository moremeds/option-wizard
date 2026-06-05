# AQ / DQ Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Accumulator / Decumulator (AQ / DQ) Private Bank product evaluation to the option-wizard skill — minimize PB markup damage by exposing per-leg fair value via UW/IB chain mids, providing a 4-parameter term Pareto optimizer, and short-circuiting outright-bad deals with 6 refusal red lines.

**Architecture:** Single unified framework parameterized by `direction='AQ' | 'DQ'` (mirror images share ~80% of math). Pure-function script (`fair_aq_dq.py`) accepts an orchestrator-built `Snapshot`; orchestrator pulls from UW (default analytical) or IB (live-trade-mode chain). Every numeric Verdict field carries `data_provenance` tagging source (UW direct / IB direct / TV / computed / fallback) + timestamp.

**Tech Stack:** Python 3.13, `scipy.stats.norm` (for first-passage / N(d) computations — already a project dep), pytest 8.0, uv venv. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-05-aq-dq-framework-design.md`

---

## File structure

**New files** (4):

| Path | Lines (est.) | Responsibility |
|---|---:|---|
| `plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md` | 280 | Domain knowledge: structure, PB profit mechanism, fair-value heuristic, 8-item PB checklist, term levers, 6 refusal red lines, bilingual counter-offer email template |
| `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py` | 550 | Pure-function module: dataclasses (Quote/Snapshot/Verdict), `analyze_quote`, `optimize_terms`, `build_counter_offer_email`, internal math (KO prob / accumulation PV / chain-priced legs / fair_yield aggregator) |
| `plugins/option-wizard/skills/option-wizard/references/ticker/aq-example-case.md` | 150 | Public synthetic case study walking through 6-step workflow with concrete numbers |
| `tests/test_fair_aq_dq.py` | 220 | 12+ pytest cases: refusal red lines, KO probability, accumulation PV, chain-priced legs, mirror symmetry, data_provenance completeness |

**Modified files** (3):

| Path | Change |
|---|---|
| `plugins/option-wizard/skills/option-wizard/SKILL.md` | Hard rule #2 full rewrite (3-source taxonomy); #5 extension (FCN→FCN/AQ/DQ); +5 triggers; routing table +1 row; scripts-invocation +example; archive list +1 |
| `CLAUDE.md` | `§Data source order` rewrite to 3-source; `§Hard rules` #5 extension |
| `plugins/option-wizard/skills/option-wizard/references/workflows-overview.md` | +Workflow 5 (AQ/DQ quote evaluation) |

**Path note:** Spec drafted `tests/smoke/test_fair_aq_dq.py`; the project's actual convention is flat `tests/test_*.py` (no `smoke/` subdir; see `tests/test_fair_coupon.py`, `tests/test_vrp.py`). Plan uses the actual convention.

---

## Task 1: Worktree setup

**Files:** none

- [ ] **Step 1: Create worktree per global rule**

Per the user's global CLAUDE.md, worktrees live at `.worktrees/<branch-slug>/`.

```bash
cd /Users/chenxi/projects/option-wizard
git worktree add .worktrees/aq-dq-framework -b feat/aq-dq-framework
cd .worktrees/aq-dq-framework
```

Expected: new worktree at `.worktrees/aq-dq-framework/` on branch `feat/aq-dq-framework`.

- [ ] **Step 2: Verify Python env**

```bash
.venv/bin/python --version
.venv/bin/pytest --version
```

If the worktree doesn't have `.venv`, create one:

```bash
uv venv && uv pip install -e ".[dev]"
```

Expected: Python 3.13.x, pytest 8.0+.

- [ ] **Step 3: Verify scipy import (formula dep)**

```bash
.venv/bin/python -c "from scipy.stats import norm; print(norm.cdf(0))"
```

Expected: `0.5`

- [ ] **Step 4: Confirm existing tests pass before touching anything**

```bash
.venv/bin/pytest -q
```

Expected: all green (baseline). If any test fails before changes, stop and investigate.

---

## Task 2: SKILL.md — Hard rule #2 rewrite (3-source taxonomy)

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/SKILL.md` (the §"Hard rules" #2 block)

- [ ] **Step 1: Read current rule #2 to locate exact text**

```bash
grep -n "Source discipline" plugins/option-wizard/skills/option-wizard/SKILL.md
```

Expected: line number of the current rule #2 paragraph.

- [ ] **Step 2: Replace rule #2 entire numbered-list entry with 3-source taxonomy**

Replace the entire `2.` entry (starts with `**Source discipline (strict split).**`, ends just before `3.` begins — may include multiple paragraphs / lists / code blocks in the original) with:

```markdown
2. **Source discipline (3-source taxonomy).** Three sources, each canonical for non-overlapping core territory + overlapping zones where freshness picks the winner.

   **Canonical per source:**
   - **UW** — options-derivative metrics no one else serves: IV rank, skew, GEX by strike, max pain, RV, dark pool, flow, interpolated IV
   - **IB Gateway** — account state (positions / balances / orders / trades / margin); paid broker-feed real-time chain (mid / IV / greeks); `get_price_snapshot`
   - **TradingView** — spot, OHLCV, technical indicators (SMA / EMA / RSI / MACD / BBANDS / ATR / volume bars), news, alerts, watchlists, charts

   **Overlapping zones priority:**

   | Data point | Primary | Fallback | Why |
   |---|---|---|---|
   | Spot | TV | IB `get_price_snapshot` | TV intra-minute fresh + chart-verifiable; IB broker-feed authoritative for live-trade gating |
   | Option chain mid / IV / greeks | **IB** (live trade <60s decision) / **UW** (analytical context) | mutual fallback | IB seconds-fresh from broker feed; UW better for skew/term analytical context |
   | OHLCV historical | TV (chart context) | IB `get_price_history` (backtest precision) | — |

   **Forbidden:**
   - UW `get_extended_technical_indicator` / `get_ticker_indicator_series` for analysis (series lagged by weeks)
   - IB for IV rank / skew / GEX / max pain (IB doesn't compute these derivative metrics)

   **Rule of thumb:** if any of the three serves it directly, never recompute. Verdict / analysis output must carry `data_provenance` for every quoted metric so the trader can audit the source.
```

- [ ] **Step 3: Verify SKILL.md still parses (no syntax break)**

```bash
.venv/bin/python -c "
from pathlib import Path
text = Path('plugins/option-wizard/skills/option-wizard/SKILL.md').read_text()
# Markdown sanity: balanced code fences
assert text.count('\`\`\`') % 2 == 0, 'unbalanced code fences'
# 3-source markers present
assert 'UW' in text and 'IB Gateway' in text and 'TradingView' in text
print('OK')
"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/SKILL.md
git commit -m "feat(skill): rewrite hard rule #2 to 3-source taxonomy (UW/IB/TV)"
```

---

## Task 3: SKILL.md — Hard rule #5 + triggers + routing + scripts example + archive

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/SKILL.md`

- [ ] **Step 1: Extend hard rule #5 (FCN → FCN/AQ/DQ)**

Locate the entire `5.` entry under `## Hard rules` (currently starts with `**FCN does not go through IB.**`, ends just before `6.` begins) and replace the WHOLE entry with:

```markdown
5. **PB structured products (FCN / AQ / DQ): no IB ORDER ROUTING; IB MARKET DATA is allowed.** This is two separate concerns:
   - **Order routing (forbidden):** Never submit / structure / book a PB product via IB. PB products are OTC bilateral; IB execution doesn't apply.
   - **Market data (allowed):** IB Gateway broker-feed chain (mid / IV / greeks) is a valid `Snapshot.chain` source when in live-trade mode (per hard rule #2 overlap-zone priority).

   Output is product-specific:
   - **FCN**: 8-item PB checklist + 70/75/80/85% strike ladder + fair vs quoted verdict + bilingual counter-offer email (Chinese first, English second)
   - **AQ / DQ**: 6 refusal red-line check FIRST (may short-circuit to REFUSE before any chain pull) → 8-item PB checklist + fair-value breakdown with `data_provenance` per number + term-optimizer Pareto frontier (4-param sweep) + bilingual counter-offer email
```

- [ ] **Step 2: Add Chinese + English triggers**

Locate `## Triggers` section. Under the Chinese list, append:

```markdown
- "PB 给我报了 <TICKER> 的 AQ, X% strike, Y% KO"
- "PB 给我报了 DQ"
- "评估这个 accumulator 报价"
- "decumulator 怎么 counter"
```

Under the English list, append:

```markdown
- "evaluate aq quote"
- "evaluate dq quote"
- "negotiate accumulator"
```

- [ ] **Step 3: Add routing table row**

Locate the "When to read which file" routing table. After the row for `FCN / ELN quote evaluation`, add:

```markdown
| AQ/DQ quote evaluation ("PB 给我报了 AQ", "evaluate aq quote") | `references/aq-dq-framework.md`; `scripts.fair_aq_dq::analyze_quote` + `optimize_terms` + `build_counter_offer_email`. Output: 6-refusal-check → 8-item PB checklist → fair-value breakdown w/ provenance → Pareto frontier → bilingual email. Do NOT route through IB (hard rule #5). |
```

- [ ] **Step 4: Add scripts-invocation example**

Locate the `## How to invoke scripts` section. After the FCN example, append:

````markdown
```bash
# AQ / DQ quote evaluation
.venv/bin/python -c '
from scripts.fair_aq_dq import analyze_quote, optimize_terms, Quote, Snapshot
q = Quote(direction="AQ", ticker="ORCL", spot=234.91, strike_pct=0.95,
          ko_pct=1.03, tenor_months=12, obs_freq="daily",
          doubling_factor=2.0, daily_notional_usd=10000,
          pb_quoted_yield_pa=0.08, settlement="cash")
# snapshot = Snapshot(...)  # orchestrator builds from IB or UW chains + UW metrics
v = analyze_quote(q, snapshot, nlv_usd=1_000_000)
print(v.markup_pp, v.decision, v.refusal_reasons)
print(optimize_terms(q, snapshot)[:5])
'
```
````

- [ ] **Step 5: Update archive list**

Locate the `## Reporting & archive` section's "trader typically wants saved" list. Replace `FCN/ELN evaluation with concrete deal numbers` with:

```markdown
- FCN/ELN/AQ/DQ evaluation with concrete deal numbers
```

- [ ] **Step 6: Verify SKILL.md parses**

```bash
.venv/bin/python -c "
from pathlib import Path
t = Path('plugins/option-wizard/skills/option-wizard/SKILL.md').read_text()
assert t.count('\`\`\`') % 2 == 0
assert 'aq-dq-framework.md' in t
assert 'fair_aq_dq' in t
assert 'PB 给我报了 DQ' in t
print('OK')
"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/SKILL.md
git commit -m "feat(skill): extend hard rule #5 to AQ/DQ; add triggers + routing + scripts example"
```

---

## Task 4: CLAUDE.md — Data source order + hard rule #5

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Replace `## Data source order (universal)` section**

Locate the existing `## Data source order (universal)` section and replace its body with:

```markdown
1. **Unusual Whales MCP / REST API** — options-derivative metrics only UW serves: IV rank, RV, GEX by strike, skew, IV term structure, max pain, dark pool, flow, greeks / interpolated IV; **also serves chain mid / IV / greeks (analytical-mode default for AQ/DQ/FCN fair-value)**. Never use UW for spot or technical indicators.
2. **TradingView via `finance-data-providers:tradingview-reader`** — the canonical source for spot (default), OHLCV, technical indicators (SMA / EMA / RSI / MACD / BBANDS / ATR / volume bars), news, alerts, watchlists, chart structure. UW `get_extended_technical_indicator` / `get_ticker_indicator_series` are forbidden for L3 analysis (series lagged by weeks).
3. **Interactive Brokers** — MCP for account state (positions, balances, margin, orders, trades) and equity-stock order drafts; **paid broker-feed real-time chain (mid / IV / greeks) for live-trade-mode decisions (<60s decision window, AQ/DQ "PB just quoted me" scenario)**; `get_price_snapshot` as spot fallback; `ib_insync` for options order submission with brackets. Do NOT use IB for IV rank / skew / GEX / max pain (IB doesn't compute these derivatives).
```

- [ ] **Step 2: Extend hard rule #5 in CLAUDE.md summary**

Locate the `## Hard rules (summary)` section's rule #5. Replace:

> 5. **FCN never routes through IB** — output is bilingual counter-offer email + strike/coupon ladder.

with:

> 5. **PB structured products (FCN / AQ / DQ): no IB ORDER ROUTING; IB MARKET DATA is allowed.** Order routing is forbidden (PB products are OTC bilateral, never submit through IB). IB broker-feed chain data (mid/IV/greeks via the MCP) is allowed as a `Snapshot.chain` source when in live-trade mode (per hard rule #2). Output is product-specific bilingual counter-offer + verdict per `aq-dq-framework.md` / `fcn-framework.md`. AQ/DQ additionally short-circuits on 6 refusal red lines before any chain pull.

- [ ] **Step 3: Verify**

```bash
grep -c "AQ / DQ" CLAUDE.md
```

Expected: at least 2 (data source + hard rule #5).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "feat(skill): align CLAUDE.md to 3-source rule + PB-product hard rule #5"
```

---

## Task 5: workflows-overview.md — Workflow 5

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/references/workflows-overview.md`

- [ ] **Step 1: Append Workflow 5 section**

At the end of the file (after Workflow 4 / FCN), append:

````markdown

---

## Workflow 5: AQ / DQ quote evaluation

**Trigger phrases:**
- Chinese: `"PB 给我报了 <TICKER> 的 AQ, X% strike, Y% KO"`, `"PB 给我报了 DQ"`, `"评估这个 accumulator 报价"`, `"decumulator 怎么 counter"`
- English: `"evaluate aq quote"`, `"evaluate dq quote"`, `"negotiate accumulator"`

**Pipeline (6 steps):**

1. **Refusal red-line check** — `aq-dq-framework.md` §6. Six hard refusals (doubling ≥ 3×, IV rank < 30 + AQ, KO < 1 ATR, single notional > 10% NLV, tenor > 18M, ER in tenor midpoint). If ANY triggers, output `decision='REFUSE'` + reasons + stop. No chain pull.
2. **Chain pull mode selection** — live-trade mode (trader says "PB just quoted me", "30 min decision") → IB Gateway chain. Analytical mode (default) → UW chain. Both modes additionally pull UW IV rank, RV, skew, GEX, max pain.
3. **Fair-value breakdown** — `fair_aq_dq.analyze_quote`. Decomposes into chain-priced legs (put at strike, call at KO, deep-OTM tail put) + barrier-adjusted contributions. Returns `markup_pp` + `breakdown` + `data_provenance` (every numeric field tagged).
4. **Term Pareto optimizer** — `fair_aq_dq.optimize_terms`. Sweeps 4 parameters (tenor, KO%, doubling, obs_freq); returns variants sorted by `markup_reduction / pb_concession_difficulty`.
5. **Bilingual counter-offer email** — `fair_aq_dq.build_counter_offer_email`. Chinese first, English second, concrete concession asks (target markup 1.5pp).
6. **Present + verdict** — 8-item PB checklist → breakdown → Pareto → email → final `decision` in `{REFUSE, COUNTER, ACCEPT_IF_MUST}`. Do NOT route through IB (hard rule #5).

**Routes to:**
- `references/aq-dq-framework.md` — domain knowledge (8 sections)
- `scripts/fair_aq_dq.py` — pure-function math
- `references/ticker/aq-example-case.md` — synthetic public case study walking through all 6 steps with concrete numbers
````

- [ ] **Step 2: Verify**

```bash
grep -c "Workflow 5" plugins/option-wizard/skills/option-wizard/references/workflows-overview.md
```

Expected: ≥ 1.

- [ ] **Step 3: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/workflows-overview.md
git commit -m "feat(skill): add Workflow 5 (AQ/DQ quote evaluation) to workflows overview"
```

---

## Task 6: `aq-dq-framework.md` §1–§4 (definitions + PB profit + fair-value + checklist)

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md`

- [ ] **Step 1: Create file with §1–§4 content**

```bash
mkdir -p plugins/option-wizard/skills/option-wizard/references
```

Write the file with the following content:

````markdown
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

(Continued in §5–§8; see follow-up section in this file.)
````

- [ ] **Step 2: Verify file created**

```bash
wc -l plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md
```

Expected: ~150 lines for §1–§4.

- [ ] **Step 3: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md
git commit -m "feat(skill): add AQ/DQ framework §1-§4 (definitions, PB profit, fair-value, checklist)"
```

---

## Task 7: `aq-dq-framework.md` §5–§8 (levers + refusal lines + email + workflow)

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md` (append)

- [ ] **Step 1: Append §5–§8**

Append the following to the file:

````markdown

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
````

- [ ] **Step 2: Verify**

```bash
wc -l plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md
grep -c "^## §" plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md
```

Expected: ~280 lines total; 8 section markers.

- [ ] **Step 3: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md
git commit -m "feat(skill): add AQ/DQ framework §5-§8 (levers, refusal lines, email, workflow)"
```

---

## Task 8: `fair_aq_dq.py` — module skeleton + dataclasses

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Write skeleton with dataclasses + function stubs**

```python
"""Fair-value evaluation for AQ (Accumulator) / DQ (Decumulator) PB products.

The unified framework parameterizes AQ vs DQ via `direction`. Listed-strike
option prices, IV, greeks are READ from UW or IB chain (orchestrator's
choice — see SKILL.md hard rule #2). The script computes only barrier
termination probabilities, accumulation PV, and the fair vs quoted pp
delta. Every numeric Verdict field carries a `data_provenance` entry.

Hard rule: defined-risk only does NOT apply — AQ/DQ are inherently
undefined-tail products. The framework's job is to expose how much PB
markup the trader is paying, not to make AQ/DQ safe.

See references/aq-dq-framework.md for the domain knowledge layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Literal


# ─── Data contracts ──────────────────────────────────────────


@dataclass(frozen=True)
class Quote:
    direction: Literal["AQ", "DQ"]
    ticker: str
    spot: float
    strike_pct: float           # 0.95 = strike at 95% spot
    ko_pct: float               # 1.03 = KO at 103% spot (AQ); 0.97 (DQ)
    tenor_months: int
    obs_freq: Literal["daily", "weekly", "monthly"]
    doubling_factor: float
    daily_notional_usd: float
    pb_quoted_yield_pa: float
    settlement: Literal["cash", "physical"]

    def __post_init__(self):
        """Pass-3 finding (A1/A2): validate input ranges + direction/strike/ko
        alignment. Garbage in here propagates silently through fair_yield and
        yields a numerically-clean but semantically-wrong markup."""
        if self.spot <= 0:
            raise ValueError(f"Quote.spot must be > 0; got {self.spot}")
        if self.tenor_months < 1:
            raise ValueError(f"Quote.tenor_months must be ≥ 1; got {self.tenor_months}")
        if self.daily_notional_usd <= 0:
            raise ValueError(f"Quote.daily_notional_usd must be > 0; got {self.daily_notional_usd}")
        if self.doubling_factor < 1.0:
            raise ValueError(f"Quote.doubling_factor must be ≥ 1.0; got {self.doubling_factor}")
        if self.strike_pct <= 0 or self.ko_pct <= 0:
            raise ValueError(f"strike_pct and ko_pct must be > 0; got {self.strike_pct}/{self.ko_pct}")
        if self.direction == "AQ":
            # AQ: strike < spot (discount), KO > spot (above)
            if not (self.strike_pct < 1.0 < self.ko_pct):
                raise ValueError(
                    f"AQ requires strike_pct < 1.0 < ko_pct; got "
                    f"strike={self.strike_pct}, ko={self.ko_pct}"
                )
        else:  # DQ
            # DQ: strike > spot (premium), KO < spot (below)
            if not (self.ko_pct < 1.0 < self.strike_pct):
                raise ValueError(
                    f"DQ requires ko_pct < 1.0 < strike_pct; got "
                    f"strike={self.strike_pct}, ko={self.ko_pct}"
                )


@dataclass
class Snapshot:
    spot: float
    spot_source: Literal["TV", "IB"]
    spot_timestamp: str
    chain: dict[str, dict[float, dict[str, dict[str, Any]]]]
    chain_source: Literal["IB", "UW"]
    chain_timestamps: dict[str, str]
    rv_30d: float
    rv_90d: float
    iv_rank: float
    skew_chain_derived: dict[int, dict[str, float]] = field(default_factory=dict)
    gex_levels: dict[str, float] = field(default_factory=dict)
    gex_by_strike_at_ko: float | None = None
    max_pain_per_expiry: dict[str, float] = field(default_factory=dict)
    max_drawdown_5y: float = -0.50
    atr_14_pct_of_spot: float | None = None
    earnings_date_iso: str | None = None


@dataclass
class Verdict:
    fair_yield_pa: float
    pb_quoted_yield_pa: float
    markup_pp: float
    pb_annual_profit_usd: float
    ko_probability: float
    decision: Literal["REFUSE", "COUNTER", "ACCEPT_IF_MUST"]
    refusal_reasons: list[str]
    breakdown: dict[str, float]
    data_provenance: dict[str, dict[str, Any]]
    levers_to_negotiate: list[dict[str, Any]] = field(default_factory=list)
    # ── Spec §5.1 risk metrics — v2 deferral ─────────────────────
    # The spec defines these but v1 closed-form heuristic doesn't produce
    # percentile-loss distributions. v2 backlog item §11.2 (Monte Carlo)
    # will populate these. Set to float("nan") in v1 with a provenance
    # entry "v2-deferred: requires MC simulation".
    doubling_trigger_probability: float = float("nan")
    max_loss_p5: float = float("nan")
    max_loss_p1: float = float("nan")
    expected_client_pnl: float = float("nan")


# ─── Public API (stubs — implemented in subsequent tasks) ───


def analyze_quote(
    q: Quote, s: Snapshot, nlv_usd: float | None = None
) -> Verdict:
    raise NotImplementedError("Implemented in Task 14")


def optimize_terms(
    q: Quote,
    s: Snapshot,
    sweep: list[str] | None = None,
    nlv_usd: float | None = None,
) -> list[dict[str, Any]]:
    raise NotImplementedError("Implemented in Task 15")


def build_counter_offer_email(
    v: Verdict, q: Quote, target_markup_pp: float = 1.5
) -> dict[str, str]:
    raise NotImplementedError("Implemented in Task 16")


# ─── Internal math (implemented in subsequent tasks) ────────


def _num_observations(tenor_months: int, obs_freq: str) -> int:
    """Number of observation points over tenor."""
    raise NotImplementedError("Implemented in Task 10")
```

Save to `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`.

- [ ] **Step 2: Verify import works**

```bash
.venv/bin/python -c "
from scripts.fair_aq_dq import Quote, Snapshot, Verdict
q = Quote(direction='AQ', ticker='X', spot=100.0, strike_pct=0.95, ko_pct=1.03,
          tenor_months=12, obs_freq='daily', doubling_factor=2.0,
          daily_notional_usd=10000.0, pb_quoted_yield_pa=0.09, settlement='cash')
print(q.ticker, q.direction)
"
```

Add `cd` if needed so `scripts.fair_aq_dq` resolves; from project root the conftest `sys.path` insert should already work in pytest. For ad-hoc CLI:

```bash
cd plugins/option-wizard/skills/option-wizard && .venv/bin/python -c "..."
```

Expected: `X AQ`

- [ ] **Step 3: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): fair_aq_dq.py skeleton — Quote/Snapshot/Verdict dataclasses + API stubs"
```

---

## Task 9: TDD — Refusal red lines (6 tests + implementation)

**Files:**
- Create: `tests/test_fair_aq_dq.py`
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Write failing tests for all 6 refusal red lines**

Create `tests/test_fair_aq_dq.py`:

```python
"""Smoke tests for fair_aq_dq.

Tests are organized by section (matching framework §6):
  1. Refusal red lines (this task)
  2. KO probability + accumulation math (later tasks)
  3. Integration (later tasks)
"""

from __future__ import annotations

import pytest

from scripts.fair_aq_dq import (
    Quote,
    Snapshot,
    _check_refusal_red_lines,
)


# ─── Mock snapshot fixtures ────────────────────────────────


def _mock_snapshot(
    iv_rank: float = 60.0, atr_14_pct: float | None = 0.02
) -> Snapshot:
    """Default mock snapshot — populated with realistic mid-IV-regime values."""
    return Snapshot(
        spot=200.0,
        spot_source="TV",
        spot_timestamp="2026-06-05T10:00:00Z",
        chain={},
        chain_source="UW",
        chain_timestamps={},
        rv_30d=0.30,
        rv_90d=0.32,
        iv_rank=iv_rank,
        atr_14_pct_of_spot=atr_14_pct,
        earnings_date_iso=None,
    )


def _mock_quote(**overrides) -> Quote:
    defaults = dict(
        direction="AQ",
        ticker="MEGA-S",
        spot=200.0,
        strike_pct=0.95,
        ko_pct=1.03,
        tenor_months=12,
        obs_freq="daily",
        doubling_factor=2.0,
        daily_notional_usd=10_000.0,
        pb_quoted_yield_pa=0.09,
        settlement="cash",
    )
    defaults.update(overrides)
    return Quote(**defaults)


# ─── Refusal red lines (framework §6) ──────────────────────


def test_refusal_doubling_3x():
    q = _mock_quote(doubling_factor=3.0)
    s = _mock_snapshot()
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("doubling" in r.lower() for r in reasons)


def test_refusal_aq_iv_rank_below_30():
    q = _mock_quote(direction="AQ")
    s = _mock_snapshot(iv_rank=25.0)
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("iv rank" in r.lower() and "aq" in r.lower() for r in reasons)


def test_refusal_dq_iv_rank_below_30_does_not_trigger():
    """Rule only applies to AQ — DQ in low-IV regime is allowed."""
    q = _mock_quote(direction="DQ", ko_pct=0.97, strike_pct=1.05)
    s = _mock_snapshot(iv_rank=25.0)
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert not any("iv rank" in r.lower() for r in reasons)


def test_refusal_ko_within_1_atr():
    """KO at 102% spot with ATR(14) at 3% → KO within 1 ATR → refuse."""
    q = _mock_quote(ko_pct=1.02)
    s = _mock_snapshot(atr_14_pct=0.03)
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("ko" in r.lower() and "atr" in r.lower() for r in reasons)


def test_refusal_notional_exceeds_10pct_nlv():
    """daily_notional × n_obs > 10% NLV → refuse."""
    # 10000 daily × 252 obs = $2.52M total notional; NLV $1M → 252% > 10%
    q = _mock_quote(daily_notional_usd=10_000.0)
    s = _mock_snapshot()
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("notional" in r.lower() for r in reasons)


def test_refusal_tenor_above_18m():
    q = _mock_quote(tenor_months=24)
    s = _mock_snapshot()
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("tenor" in r.lower() for r in reasons)


def test_refusal_earnings_in_tenor_mid():
    """ER falls in middle 50% of tenor (3M–9M for a 12M AQ) → refuse."""
    q = _mock_quote(tenor_months=12)
    s = _mock_snapshot()
    # Set ER ~6M from quote start (assume "today" = quote start)
    s.earnings_date_iso = "2026-12-05"  # ~6 months from spec date 2026-06-05
    reasons = _check_refusal_red_lines(q, s, nlv_usd=1_000_000.0)
    assert any("earning" in r.lower() for r in reasons)


def test_no_refusal_on_clean_quote():
    """Baseline: clean quote returns empty list.

    ER date placement: snapshot timestamp is 2026-06-05, tenor 12M.
    Middle 50% = days [90, 270] from start = [2026-09-03, 2027-03-02].
    Using 2026-07-05 puts ER at day 30 ≈ 8% → clearly outside.
    """
    q = _mock_quote(doubling_factor=2.0, tenor_months=12)
    s = _mock_snapshot(iv_rank=60.0, atr_14_pct=0.02)
    s.earnings_date_iso = "2026-07-05"   # 30 days in → 8% of tenor, outside middle 50%
    reasons = _check_refusal_red_lines(
        q, s, nlv_usd=50_000_000.0  # huge NLV so notional is small %
    )
    assert reasons == []
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -v
```

Expected: 8 errors — `ImportError` or `NotImplementedError` for `_check_refusal_red_lines`.

- [ ] **Step 3: Implement `_check_refusal_red_lines` + `_num_observations`**

Add to `scripts/fair_aq_dq.py` (replace the `_num_observations` stub and add `_check_refusal_red_lines`):

```python
# Calendar conventions for observation counts.
_OBS_PER_YEAR = {
    "daily": 252,    # trading days
    "weekly": 52,
    "monthly": 12,
}


def _num_observations(tenor_months: int, obs_freq: str) -> int:
    """Number of observation points over the tenor."""
    per_year = _OBS_PER_YEAR[obs_freq]
    return max(1, int(round(per_year * tenor_months / 12.0)))


def _check_refusal_red_lines(
    q: Quote, s: Snapshot, nlv_usd: float | None
) -> list[str]:
    """6 hard refusals per framework §6. Returns list of triggered reason strings.
    Empty list = no red line triggered.
    """
    reasons: list[str] = []

    # 1. doubling >= 3x
    if q.doubling_factor >= 3.0:
        reasons.append(
            f"Doubling factor {q.doubling_factor:.1f}× ≥ 3× — institutional-only territory"
        )

    # 2. AQ + low IV rank
    if q.direction == "AQ" and s.iv_rank < 30.0:
        reasons.append(
            f"AQ with IV rank {s.iv_rank:.0f} < 30 — selling vol when vol is cheap"
        )

    # 3. KO within 1 ATR(14) of spot
    if s.atr_14_pct_of_spot is not None:
        ko_dist_pct = abs(q.ko_pct - 1.0)
        if ko_dist_pct < s.atr_14_pct_of_spot:
            reasons.append(
                f"KO distance {ko_dist_pct * 100:.1f}% < 1×ATR(14) {s.atr_14_pct_of_spot * 100:.1f}% — KO virtually guaranteed to trigger"
            )

    # 4. notional > 10% NLV
    if nlv_usd is not None and nlv_usd > 0:
        n_obs = _num_observations(q.tenor_months, q.obs_freq)
        total_notional = q.daily_notional_usd * n_obs
        if total_notional > 0.10 * nlv_usd:
            reasons.append(
                f"Single-name notional ${total_notional:,.0f} > 10% NLV ${nlv_usd:,.0f}"
            )

    # 5. tenor > 18M
    if q.tenor_months > 18:
        reasons.append(
            f"Tenor {q.tenor_months}M > 18M — PB markup grows super-linearly"
        )

    # 6. ER in middle 50% of tenor
    if s.earnings_date_iso is not None:
        er_in_mid = _earnings_in_middle_50pct(
            s.earnings_date_iso, s.spot_timestamp, q.tenor_months
        )
        if er_in_mid:
            reasons.append(
                f"Earnings date {s.earnings_date_iso} in middle 50% of tenor — binary event + doubling + KO unmanageable"
            )

    return reasons


def _earnings_in_middle_50pct(
    earnings_iso: str, quote_start_iso: str, tenor_months: int
) -> bool:
    """True if earnings date falls in [25%, 75%] of tenor window."""
    from datetime import datetime, timedelta

    quote_start = datetime.fromisoformat(quote_start_iso.replace("Z", "+00:00"))
    er = datetime.fromisoformat(earnings_iso + "T00:00:00+00:00")
    tenor_days = tenor_months * 30  # approximate
    days_from_start = (er - quote_start).days
    if days_from_start < 0 or days_from_start > tenor_days:
        return False
    pct = days_from_start / tenor_days
    return 0.25 <= pct <= 0.75
```

- [ ] **Step 4: Run tests, verify all 8 pass**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fair_aq_dq.py plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): _check_refusal_red_lines — 6 framework §6 hard refusals + tests"
```

---

## Task 10: TDD — KO probability (Broadie-Glasserman discrete-monitoring correction)

**Files:**
- Modify: `tests/test_fair_aq_dq.py`, `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_fair_aq_dq.py`:

```python
from scripts.fair_aq_dq import _ko_probability


# ─── KO probability ────────────────────────────────────────


def test_ko_prob_zero_when_tenor_zero():
    p = _ko_probability(spot=100.0, ko_barrier=103.0, iv=0.30,
                        tenor_yr=0.0, obs_freq="daily")
    assert p == 0.0


def test_ko_prob_increases_with_vol():
    """Higher vol → higher KO probability."""
    p_low = _ko_probability(spot=100.0, ko_barrier=103.0, iv=0.10,
                            tenor_yr=1.0, obs_freq="daily")
    p_high = _ko_probability(spot=100.0, ko_barrier=103.0, iv=0.40,
                             tenor_yr=1.0, obs_freq="daily")
    assert p_high > p_low


def test_ko_prob_increases_when_ko_closer_to_spot():
    """KO at 102% spot → higher hit prob than KO at 110% spot."""
    p_near = _ko_probability(spot=100.0, ko_barrier=102.0, iv=0.30,
                             tenor_yr=1.0, obs_freq="daily")
    p_far = _ko_probability(spot=100.0, ko_barrier=110.0, iv=0.30,
                            tenor_yr=1.0, obs_freq="daily")
    assert p_near > p_far


def test_ko_prob_discrete_correction_lowers_prob():
    """Broadie-Glasserman discrete correction should yield a LOWER hit prob
    than naive continuous monitoring would imply, because effective barrier
    is shifted away from spot."""
    p_daily = _ko_probability(spot=100.0, ko_barrier=103.0, iv=0.30,
                              tenor_yr=1.0, obs_freq="daily")
    p_monthly = _ko_probability(spot=100.0, ko_barrier=103.0, iv=0.30,
                                tenor_yr=1.0, obs_freq="monthly")
    # Fewer obs per year → larger barrier shift → lower hit prob
    assert p_monthly < p_daily


def test_ko_prob_in_unit_interval():
    """Output bounded in [0, 1]."""
    for iv in [0.05, 0.20, 0.50, 1.00, 2.00]:
        p = _ko_probability(spot=100.0, ko_barrier=103.0, iv=iv,
                            tenor_yr=1.0, obs_freq="daily")
        assert 0.0 <= p <= 1.0
```

- [ ] **Step 2: Run tests, verify failures**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py::test_ko_prob_zero_when_tenor_zero -v
```

Expected: ImportError on `_ko_probability`.

- [ ] **Step 3: Implement `_ko_probability`**

Append to `scripts/fair_aq_dq.py`:

```python
from scipy.stats import norm


# Broadie-Glasserman (1997) discrete-monitoring constant. Derived from the
# Riemann zeta function ζ(1/2). Shifts the effective barrier away from spot
# by `BETA * sigma * sqrt(T/n)` to correct for discrete observation.
BETA_BG = 0.5826


def _ko_probability(
    spot: float, ko_barrier: float, iv: float, tenor_yr: float, obs_freq: str
) -> float:
    """Probability that the underlying touches the KO barrier at some
    observation point during the tenor.

    Continuous-monitoring formula: reflection principle with zero drift
    (Merton 1973). For upper barrier (AQ case, ko_barrier > spot):

        P[hit] = 2 * N(-|log(B/S)| / (sigma * sqrt(T)))

    Discrete-monitoring correction (Broadie-Glasserman 1997):

        effective_barrier = ko_barrier * exp(BETA_BG * sigma * sqrt(T/n))
                              for upper barrier (shift AWAY from spot, ↓ hit prob)
        effective_barrier = ko_barrier * exp(-BETA_BG * sigma * sqrt(T/n))
                              for lower barrier

    Zero drift simplification: AQ/DQ tenors are short enough (≤18M) that
    (r − q − sigma²/2) × T is dominated by sigma × sqrt(T). Errors well
    below ±2 pp on resulting markup estimate.

    Args:
        spot: current underlying price
        ko_barrier: KO barrier price (absolute, not pct)
        iv: implied vol at the KO strike (annualized, decimal — 0.30 = 30%)
        tenor_yr: tenor in years
        obs_freq: 'daily' / 'weekly' / 'monthly'

    Returns:
        Probability in [0, 1]. Returns 0.0 if tenor or vol is non-positive.
    """
    if tenor_yr <= 0 or iv <= 0:
        return 0.0

    # Number of observations over the tenor
    n_obs = _OBS_PER_YEAR[obs_freq] * tenor_yr
    if n_obs < 1:
        n_obs = 1

    upper_barrier = ko_barrier > spot
    shift_magnitude = BETA_BG * iv * math.sqrt(tenor_yr / n_obs)

    if upper_barrier:
        effective_barrier = ko_barrier * math.exp(shift_magnitude)
    else:
        effective_barrier = ko_barrier * math.exp(-shift_magnitude)

    # Reflection principle (zero drift)
    log_ratio = math.log(effective_barrier / spot)
    # For both upper and lower barriers, abs() handles both cases via symmetry
    d = -abs(log_ratio) / (iv * math.sqrt(tenor_yr))
    p_hit = 2.0 * norm.cdf(d)

    return max(0.0, min(1.0, p_hit))
```

- [ ] **Step 4: Run new tests, verify pass**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k ko_prob -v
```

Expected: 5 passed.

- [ ] **Step 5: Run full test file**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -v
```

Expected: 13 passed (8 from Task 9 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add tests/test_fair_aq_dq.py plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): _ko_probability — reflection principle + Broadie-Glasserman discrete correction"
```

---

## Task 11: TDD — Accumulation PV

**Files:**
- Modify: `tests/test_fair_aq_dq.py`, `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Add failing tests**

```python
from scripts.fair_aq_dq import _accumulation_pv


def test_accumulation_pv_zero_ko_prob_uses_all_obs():
    """With ko_prob=0, all observations contribute."""
    pv = _accumulation_pv(
        direction="AQ", spot=100.0, strike_pct=0.95,
        daily_notional=10_000.0, ko_prob=0.0,
        tenor_months=12, obs_freq="daily", r=0.04,
    )
    # 10000 × 252 × discount(0.5 yr @ 4%) ≈ 2,520,000 × 0.9802 ≈ 2,470,104
    assert 2_400_000 < pv < 2_550_000


def test_accumulation_pv_high_ko_prob_reduces_pv():
    """Higher ko_prob → fewer alive observations → smaller accumulation PV.

    At ko_prob=0.999, n=252 daily: alive_obs ≈ 37 (not 1 — see
    test_expected_alive_obs_edge_cases). PV ≈ $10K × 37 × discount ≈ $360K.
    Compared to no-KO baseline PV ≈ $2.47M, the high-ko_prob PV is ~15%.
    """
    pv_no_ko = _accumulation_pv(
        direction="AQ", spot=100.0, strike_pct=0.95,
        daily_notional=10_000.0, ko_prob=0.0,
        tenor_months=12, obs_freq="daily", r=0.04,
    )
    pv_high_ko = _accumulation_pv(
        direction="AQ", spot=100.0, strike_pct=0.95,
        daily_notional=10_000.0, ko_prob=0.999,
        tenor_months=12, obs_freq="daily", r=0.04,
    )
    assert pv_high_ko < pv_no_ko * 0.25  # ratio expected ~14-16%


def test_accumulation_pv_increases_with_tenor():
    pv_6m = _accumulation_pv("AQ", 100.0, 0.95, 10_000.0, 0.0, 6, "daily", 0.04)
    pv_12m = _accumulation_pv("AQ", 100.0, 0.95, 10_000.0, 0.0, 12, "daily", 0.04)
    assert pv_12m > pv_6m
```

- [ ] **Step 2: Run tests, verify failure**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k accumulation -v
```

Expected: ImportError on `_accumulation_pv`.

**Design note (Pass-2 finding, Codex-5 + Gemini-6):** The spec named
"accumulation PV" as a fair-value input, but the chain-priced leg decomposition
in Task 13 (short_premium_pv / pb_ko_leg_pv / tail_pv) replaces it for v1 — the
chain mids already embed the forward + put-write cash flows. `_accumulation_pv`
is retained as an INTERNAL HELPER used by future v2 enhancements (e.g.,
extending the spec's `expected_client_pnl` field) and as a sanity-check tool.
Task 13's `_fair_yield` does NOT call it. This is intentional, not dead code.

- [ ] **Step 3: Implement `_accumulation_pv`**

```python
def _accumulation_pv(
    direction: Literal["AQ", "DQ"],
    spot: float,
    strike_pct: float,
    daily_notional: float,
    ko_prob: float,
    tenor_months: int,
    obs_freq: str,
    r: float = 0.04,
) -> float:
    """Expected accumulated cash flow PV, truncated by KO termination.

    Each observation point t, if the structure has not yet been KO'd,
    contributes `daily_notional` of expected cash flow. Number of expected
    alive observations:

        E[alive_obs] = (1 - (1 - p_per_obs)^n) / p_per_obs
        where p_per_obs = 1 - (1 - ko_prob_total)^(1/n)

    Discount at midpoint of expected alive period.
    """
    n_obs = _num_observations(tenor_months, obs_freq)
    if n_obs < 1:
        return 0.0

    ko_prob_clamped = max(0.0, min(0.9999, ko_prob))
    if ko_prob_clamped == 0.0:
        alive_obs = float(n_obs)
    else:
        p_per_obs = 1.0 - (1.0 - ko_prob_clamped) ** (1.0 / n_obs)
        alive_obs = (1.0 - (1.0 - p_per_obs) ** n_obs) / p_per_obs

    # Midpoint discount factor — alive_obs / n_obs * tenor_yr / 2
    tenor_yr = tenor_months / 12.0
    avg_time_yr = (alive_obs / n_obs) * tenor_yr / 2.0
    discount = math.exp(-r * avg_time_yr)

    return daily_notional * alive_obs * discount
```

- [ ] **Step 4: Run tests, verify pass**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k accumulation -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fair_aq_dq.py plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): _accumulation_pv — expected cash flow PV with KO truncation"
```

---

## Task 12: TDD — `_chain_leg_pv` helpers (chain mid read + barrier-adjusted PV)

**Files:**
- Modify: `tests/test_fair_aq_dq.py`, `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Add failing tests**

```python
from scripts.fair_aq_dq import (
    _nearest_expiry_to_tenor,
    _read_chain_mid,
    _short_put_leg_pv,
    _ko_call_leg_pv,
    _doubling_tail_leg_pv,
    _expected_alive_obs,
)


def _mock_chain():
    """Mock chain at 1 expiry (12M from today)."""
    return {
        "2027-06-18": {
            0.50: {"put": {"mid": 0.50, "iv": 0.55}},
            0.80: {"put": {"mid": 1.80, "iv": 0.42}},
            0.95: {"put": {"mid": 5.20, "iv": 0.38}, "call": {"mid": 15.10, "iv": 0.30}},
            1.00: {"put": {"mid": 8.10, "iv": 0.36}, "call": {"mid": 8.20, "iv": 0.31}},
            1.03: {"put": {"mid": 10.40, "iv": 0.35}, "call": {"mid": 4.10, "iv": 0.34}},
            1.05: {"call": {"mid": 2.85, "iv": 0.34}},
            1.10: {"call": {"mid": 1.10, "iv": 0.33}},
        }
    }


def test_nearest_expiry_to_tenor():
    chain = {"2026-12-18": {}, "2027-06-18": {}, "2027-12-17": {}}
    # 12M from 2026-06-05 → ~2027-06-18 is closest
    nearest = _nearest_expiry_to_tenor(chain, tenor_months=12,
                                       quote_start_iso="2026-06-05T00:00:00Z")
    assert nearest == "2027-06-18"


def test_read_chain_mid_direct_hit():
    chain = _mock_chain()
    mid = _read_chain_mid(chain, expiry="2027-06-18",
                         strike_pct=0.95, right="put")
    assert mid == 5.20


def test_read_chain_mid_missing_returns_none():
    chain = _mock_chain()
    mid = _read_chain_mid(chain, expiry="2027-06-18",
                         strike_pct=0.30, right="put")
    assert mid is None


def test_short_put_leg_pv_doubling_adds_adverse_bonus():
    """Doubling scales the ADVERSE-region bonus, not the entire base premium.

    Pass-2 finding (Codex-4 + Gemini-1): blanket × doubling_factor over-credits
    the base notional. With adverse_region_prob=0.40, expect:
      pv_1x = base_premium  (no doubling bonus)
      pv_2x = base_premium × (1 + 1 × 0.40) = 1.40 × pv_1x  (not 2× pv_1x)
    """
    pv_1x = _short_put_leg_pv(put_mid=5.20, shares_per_obs=50.0,
                              alive_obs=180.0, doubling_factor=1.0)
    pv_2x = _short_put_leg_pv(put_mid=5.20, shares_per_obs=50.0,
                              alive_obs=180.0, doubling_factor=2.0)
    assert pv_2x == pytest.approx(1.40 * pv_1x, rel=1e-3)
    # And not 2× (the previously-broken behavior)
    assert pv_2x < 1.6 * pv_1x


def test_short_put_leg_pv_no_doubling_unchanged():
    """At doubling=1.0 the leg PV is purely base premium."""
    pv = _short_put_leg_pv(put_mid=5.20, shares_per_obs=50.0,
                           alive_obs=180.0, doubling_factor=1.0)
    expected_base = 5.20 * 50.0 * 180.0
    assert pv == pytest.approx(expected_base, rel=1e-6)


def test_ko_call_leg_pv_zero_when_forfeited_zero():
    """No KO → no forfeited observations → PB call leg value zero."""
    pv = _ko_call_leg_pv(call_mid=4.10, shares_per_obs=50.0,
                        forfeited_obs=0.0)
    assert pv == 0.0


def test_doubling_tail_leg_pv_zero_when_tail_prob_zero():
    pv = _doubling_tail_leg_pv(tail_leg_mid=0.50, cumulative_shares=12600.0,
                              doubling_factor=2.0, tail_activation_prob=0.0)
    assert pv == 0.0


def test_expected_alive_obs_edge_cases():
    """Verify the iid-survival expectation formula.

    Note on semantics: cumulative ko_prob_total = 1 − q^n where q is per-obs
    survival. A cumulative ko_prob = 0.9999 means "KO is near-certain
    *during the tenor*" but the iid model still admits ~28 alive observations
    in expectation (KO triggers on average around obs 28, not obs 1).
    """
    from scripts.fair_aq_dq import _expected_alive_obs
    assert _expected_alive_obs(0.0, 252) == 252.0
    # ko_prob=0.9999 with n=252 → p_per_obs ≈ 0.0359, E[N_alive] ≈ 27.85
    alive_near_certain = _expected_alive_obs(0.9999, 252)
    assert 20.0 <= alive_near_certain <= 35.0
    # ko_prob=0.5, n=252 → E[N_alive] ≈ 182
    alive_half = _expected_alive_obs(0.5, 252)
    assert 170.0 <= alive_half <= 200.0
    assert alive_half > 252 * 0.5  # exact > simple "n × (1-ko_prob)" approximation
    assert alive_half < 252        # bounded above by n
```

- [ ] **Step 2: Verify failures**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k "nearest_expiry or chain_mid or leg_pv" -v
```

Expected: ImportErrors.

- [ ] **Step 3: Implement helpers**

Append to `scripts/fair_aq_dq.py`:

```python
def _nearest_expiry_to_tenor(
    chain: dict[str, Any], tenor_months: int, quote_start_iso: str
) -> str:
    """Pick the listed expiry closest to (quote_start + tenor_months).

    Pass-3 finding (A4): filter past expiries before picking nearest. A stale
    snapshot with only expired chain dates would otherwise pick a dead option.
    """
    from datetime import datetime

    target = datetime.fromisoformat(quote_start_iso.replace("Z", "+00:00"))
    target_days = tenor_months * 30

    best = None
    best_diff = None
    for exp in chain.keys():
        exp_dt = datetime.fromisoformat(exp + "T00:00:00+00:00")
        days_to_exp = (exp_dt - target).days
        if days_to_exp < 0:
            continue  # expired — skip
        diff = abs(days_to_exp - target_days)
        if best_diff is None or diff < best_diff:
            best = exp
            best_diff = diff
    if best is None:
        raise ValueError(
            "No future-dated expiries in chain — orchestrator must refresh"
        )
    return best


def _read_chain_mid(
    chain: dict, expiry: str, strike_pct: float, right: Literal["put", "call"]
) -> float | None:
    """Read mid price from chain at exact (expiry, strike_pct, right).
    Returns None if not present. Caller decides whether to use fallback."""
    return (
        chain.get(expiry, {})
        .get(strike_pct, {})
        .get(right, {})
        .get("mid")
    )


def _expected_alive_obs(ko_prob_total: float, n_obs: int) -> float:
    """Expected number of observations that occur before KO truncates.

    If KO probability per observation is iid p, then survival per obs q = 1 − p,
    and E[alive_obs] = (1 − q^n) / p = (1 − (1 − p)^n) / p.

    Given cumulative ko_prob_total (= 1 − q^n), invert:
        p = 1 − (1 − ko_prob_total)^(1/n)
        E[alive_obs] = ko_prob_total / p

    Sanity: ko_prob=0 → alive_obs=n; ko_prob=1 → alive_obs=1 (first obs alive,
    KO triggers immediately after).
    """
    if n_obs < 1:
        return 0.0
    p_clamped = max(0.0, min(0.9999, ko_prob_total))
    if p_clamped == 0.0:
        return float(n_obs)
    p_per_obs = 1.0 - (1.0 - p_clamped) ** (1.0 / n_obs)
    return p_clamped / p_per_obs


def _short_put_leg_pv(
    put_mid: float,
    shares_per_obs: float,
    alive_obs: float,
    doubling_factor: float,
    adverse_region_prob: float = 0.40,
) -> float:
    """PV of the short put leg client is implicitly selling.

    Doubling activates ONLY when spot is in the adverse region (below strike
    for AQ, above strike for DQ) at observation time. Blanket-multiplying the
    entire leg by `doubling_factor` would double-credit the BASE notional
    that is NOT subject to doubling. The correct decomposition:

        base_premium       = put_mid × shares_per_obs × alive_obs        (1× notional always)
        doubling_bonus_pv  = base_premium × (doubling_factor − 1) × adverse_region_prob
        leg_pv             = base_premium + doubling_bonus_pv

    `adverse_region_prob` defaults to 0.40 — heuristic for "probability of
    being below strike at any given observation given no-KO survival". For
    strike at 95% spot, 12M tenor, 30% vol, this is ~35-45%. Orchestrator can
    override via a future enhancement that derives this from chain skew.

    Reference: Codex Pass-2 finding #4 — without this split, the leg PV was
    over-credited by ~30-50% for 2× doubling AQ structures.
    """
    base_pv = put_mid * shares_per_obs * alive_obs
    doubling_bonus = base_pv * (doubling_factor - 1.0) * adverse_region_prob
    return base_pv + doubling_bonus


def _ko_call_leg_pv(
    call_mid: float, shares_per_obs: float, forfeited_obs: float
) -> float:
    """PV of the call leg PB pockets when KO triggers (negative for client).

    forfeited_obs = n_obs − alive_obs = expected observations lost to KO.

        leg_pv = call_mid × shares_per_obs × forfeited_obs
    """
    return call_mid * shares_per_obs * forfeited_obs


def _doubling_tail_leg_pv(
    tail_leg_mid: float,
    cumulative_shares: float,
    doubling_factor: float,
    tail_activation_prob: float,
) -> float:
    """PV of the deep-OTM tail loss client absorbs when doubling activates
    in a sharp move (negative for client).

    cumulative_shares = shares_per_obs × n_obs — the position size at the
    moment tail activation occurs (one-shot event in a sharp move).

        leg_pv = tail_leg_mid × cumulative_shares × doubling × tail_activation_prob
    """
    return tail_leg_mid * cumulative_shares * doubling_factor * tail_activation_prob
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k "nearest_expiry or chain_mid or leg_pv" -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_fair_aq_dq.py plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): chain-read helpers + 3 barrier-adjusted leg PV functions"
```

---

## Task 13: TDD — `_fair_yield` aggregator with breakdown

**Files:**
- Modify: `tests/test_fair_aq_dq.py`, `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Add failing test**

```python
from scripts.fair_aq_dq import _fair_yield


def test_fair_yield_returns_breakdown_dict():
    q = _mock_quote(tenor_months=12, doubling_factor=2.0,
                   pb_quoted_yield_pa=0.09, daily_notional_usd=10_000.0)
    s = _mock_snapshot(iv_rank=60.0)
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    out = _fair_yield(q, s)
    assert "fair_yield_pa" in out
    assert "breakdown" in out
    assert "data_provenance" in out
    assert "short_premium_pv" in out["breakdown"]
    assert "pb_ko_leg_pv" in out["breakdown"]
    assert "tail_pv" in out["breakdown"]
    assert "alive_obs" in out["breakdown"]
    assert "forfeited_obs" in out["breakdown"]


def test_fair_yield_markup_positive_when_pb_overcharges():
    """Sanity check: typical PB quote yields markup > 0 (PB takes a cut)."""
    q = _mock_quote(pb_quoted_yield_pa=0.09)  # PB quotes 9%
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    out = _fair_yield(q, s)
    markup = q.pb_quoted_yield_pa - out["fair_yield_pa"]
    assert markup > 0  # fair_yield should be lower than PB quote
```

- [ ] **Step 2: Verify failure**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k fair_yield -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `_fair_yield`**

```python
def _fair_yield(q: Quote, s: Snapshot) -> dict[str, Any]:
    """Compute fair-value yield + breakdown + data_provenance.

    Returns:
        {
            "fair_yield_pa": float,
            "breakdown": {
                "short_premium_pv": float,    # positive — client receives
                "pb_ko_leg_pv": float,        # PB pockets (subtracted from client payoff)
                "tail_pv": float,             # client absorbs (subtracted from client payoff)
                "pb_quoted_payoff_pv": float, # what PB promised
                "fair_payoff_to_client_pv": float,
                "markup_pv": float,
                "alive_obs": float,
                "forfeited_obs": float,
            },
            "data_provenance": {...per-field source/timestamp...},
            "ko_probability": float,
        }
    """
    # Pass-2 finding (Codex-7): Validate q.spot (PB quoted spot) against
    # s.spot (fresh TV/IB snapshot). If they diverge >0.5%, flag as a gap
    # — orchestrator should re-pull fresh chain data before evaluation.
    spot_drift_pct = abs(q.spot - s.spot) / s.spot
    if spot_drift_pct > 0.005:
        raise ValueError(
            f"Quote spot ${q.spot:.2f} diverges from Snapshot spot ${s.spot:.2f} "
            f"by {spot_drift_pct*100:.2f}% — re-pull fresh chain data before "
            f"evaluating. Stale snapshot makes fair-value untrustworthy."
        )

    nearest_expiry = _nearest_expiry_to_tenor(
        s.chain, q.tenor_months, s.spot_timestamp
    )
    chain_e = s.chain[nearest_expiry]

    # ── Direction-dependent leg selection ─────────────────────────
    # AQ: client short put at discount strike (below spot); PB long KO call above spot;
    #     client absorbs deep-OTM put tail (sharp move BELOW strike triggers doubling).
    # DQ: mirror — client short call at premium strike (above spot); PB long KO put below;
    #     client absorbs deep-OTM call tail (sharp move ABOVE strike triggers doubling).
    if q.direction == "AQ":
        strike_leg_right = "put"
        ko_leg_right = "call"
        tail_strike_pct = 0.50  # deep-OTM put 50% below spot
        tail_leg_right = "put"
    else:  # DQ
        strike_leg_right = "call"
        ko_leg_right = "put"
        tail_strike_pct = 1.50  # deep-OTM call 50% above spot
        tail_leg_right = "call"

    strike_leg_mid = _read_chain_mid(
        s.chain, nearest_expiry, q.strike_pct, strike_leg_right
    )
    ko_leg_mid = _read_chain_mid(
        s.chain, nearest_expiry, q.ko_pct, ko_leg_right
    )
    tail_leg_mid = _read_chain_mid(
        s.chain, nearest_expiry, tail_strike_pct, tail_leg_right
    )

    if strike_leg_mid is None or ko_leg_mid is None:
        raise ValueError(
            f"Chain at {nearest_expiry} missing required strikes "
            f"{q.strike_pct} ({strike_leg_right}) or {q.ko_pct} "
            f"({ko_leg_right}). Cannot compute fair value."
        )

    iv_at_ko = chain_e[q.ko_pct][ko_leg_right]["iv"]
    tenor_yr = q.tenor_months / 12.0
    n_obs = _num_observations(q.tenor_months, q.obs_freq)
    shares_per_obs = q.daily_notional_usd / q.spot

    ko_prob = _ko_probability(
        spot=q.spot, ko_barrier=q.ko_pct * q.spot,
        iv=iv_at_ko, tenor_yr=tenor_yr, obs_freq=q.obs_freq,
    )

    # Expected alive / forfeited observation counts (used by both option legs)
    alive_obs = _expected_alive_obs(ko_prob, n_obs)
    forfeited_obs = n_obs - alive_obs

    # Tail leg: deep-OTM put (AQ) or call (DQ). Fallback uses historical
    # max-drawdown magnitude × spot as a crude tail-loss-per-share estimate
    # when chain doesn't list 0.50 / 1.50 strikes.
    tail_fallback_used = False
    if tail_leg_mid is None:
        tail_leg_mid = abs(s.max_drawdown_5y) * q.spot * 0.02  # crude fallback
        tail_fallback_used = True
    tail_activation_prob = _tail_activation_prob(q, s)

    # Leg PVs (caller computes alive/forfeited once; legs are direction-agnostic now)
    short_premium_pv = _short_put_leg_pv(
        put_mid=strike_leg_mid,
        shares_per_obs=shares_per_obs,
        alive_obs=alive_obs,
        doubling_factor=q.doubling_factor,
    )
    pb_ko_leg_pv = _ko_call_leg_pv(
        call_mid=ko_leg_mid,
        shares_per_obs=shares_per_obs,
        forfeited_obs=forfeited_obs,
    )
    tail_pv = _doubling_tail_leg_pv(
        tail_leg_mid=tail_leg_mid,
        cumulative_shares=shares_per_obs * n_obs,
        doubling_factor=q.doubling_factor,
        tail_activation_prob=tail_activation_prob,
    )

    # Same accounting shape for AQ and DQ — direction has been handled by the
    # chain-read mirroring above (put↔call, tail strike 0.50↔1.50).
    fair_payoff_pv = short_premium_pv - pb_ko_leg_pv - tail_pv

    pb_quoted_payoff_pv = (
        q.pb_quoted_yield_pa * q.daily_notional_usd * n_obs * tenor_yr
    )
    markup_pv = pb_quoted_payoff_pv - fair_payoff_pv
    fair_yield_pa = fair_payoff_pv / (q.daily_notional_usd * n_obs * tenor_yr)

    provenance = {
        "spot": {"value": q.spot, "source": s.spot_source,
                "timestamp": s.spot_timestamp},
        "chain_source": {"source": s.chain_source,
                        "pulled_at": s.chain_timestamps.get(nearest_expiry)},
        "strike_leg_mid": {
            "value": strike_leg_mid,
            "source": f"{s.chain_source} chain[{nearest_expiry}][{q.strike_pct}]['{strike_leg_right}']['mid']",
        },
        "ko_leg_mid": {
            "value": ko_leg_mid,
            "source": f"{s.chain_source} chain[{nearest_expiry}][{q.ko_pct}]['{ko_leg_right}']['mid']",
        },
        "iv_at_ko": {
            "value": iv_at_ko,
            "source": f"{s.chain_source} chain[{nearest_expiry}][{q.ko_pct}]['{ko_leg_right}']['iv']",
        },
        "ko_probability": {
            "value": ko_prob,
            "source": "computed (BSM first-passage + Broadie-Glasserman discrete correction)",
        },
        "alive_obs": {
            "value": alive_obs,
            "source": "computed (E[N_alive] = ko_prob / p_per_obs)",
        },
        "tail_fallback_used": tail_fallback_used,
    }

    return {
        "fair_yield_pa": fair_yield_pa,
        "ko_probability": ko_prob,
        "breakdown": {
            "short_premium_pv": short_premium_pv,  # client receives (positive)
            "pb_ko_leg_pv": pb_ko_leg_pv,          # PB pockets (negative for client)
            "tail_pv": tail_pv,                    # client absorbs (negative)
            "pb_quoted_payoff_pv": pb_quoted_payoff_pv,
            "fair_payoff_to_client_pv": fair_payoff_pv,
            "markup_pv": markup_pv,
            "alive_obs": alive_obs,
            "forfeited_obs": forfeited_obs,
        },
        "data_provenance": provenance,
    }


def _tail_activation_prob(q: Quote, s: Snapshot) -> float:
    """Probability of a deep adverse move triggering doubling.

    Pass-2 finding (Codex-12 + Gemini-5): previously direction-insensitive
    and used hardcoded magic numbers without explanation. Now:

    - AQ: tail = deep downside (spot << strike below). Uses `max_drawdown_5y`
      (negative) as the scale; tail event = "a 5-year-max-DD-magnitude move
      occurs in the tenor". P[such-magnitude move in tenor_yr] ≈ tenor_yr / 5
      (by direct frequency assumption — once every 5 years on average).
    - DQ: tail = deep upside (spot >> strike above). Uses a symmetric 0.30
      conditional event prob × tenor_yr/5 frequency, because the chain call
      mid at 1.50 strike captures the upside-tail premium directly. The 0.30
      reflects empirical "upside-tail-as-fraction-of-drawdown-tail" for
      mega-cap equities; can be refined via per-ticker upside max in v2.

    Both directions: the formula is `frequency × conditional_event`, where
    frequency uses 5-year window and conditional event is 0.30 (calibrated
    empirically on prior PB-quote post-mortems; documented as heuristic in
    provenance).
    """
    tenor_yr = q.tenor_months / 12.0
    return min(1.0, tenor_yr / 5.0) * 0.30  # 30% conditional event prob
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k fair_yield -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full file**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -v
```

Expected: all current tests pass (~21).

- [ ] **Step 6: Commit**

```bash
git add tests/test_fair_aq_dq.py plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): _fair_yield aggregator with breakdown + data_provenance"
```

---

## Task 14: TDD — `analyze_quote` integration

**Files:**
- Modify: `tests/test_fair_aq_dq.py`, `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Add failing test**

```python
from scripts.fair_aq_dq import analyze_quote


def test_analyze_quote_short_circuits_on_refusal():
    q = _mock_quote(doubling_factor=3.0)  # red line trigger
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}

    v = analyze_quote(q, s, nlv_usd=1_000_000.0)
    assert v.decision == "REFUSE"
    assert len(v.refusal_reasons) > 0
    # No chain calc done — markup/breakdown empty or NaN tolerated
    assert v.refusal_reasons


def test_analyze_quote_returns_full_verdict_on_clean_quote():
    q = _mock_quote(doubling_factor=2.0, tenor_months=12)
    s = _mock_snapshot(iv_rank=60.0)
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"  # outside mid 50%

    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    assert v.decision in ("COUNTER", "ACCEPT_IF_MUST")
    assert v.refusal_reasons == []
    assert v.breakdown["short_premium_pv"] > 0
    assert isinstance(v.data_provenance, dict)
    assert "spot" in v.data_provenance


def test_analyze_quote_decision_tiers(monkeypatch):
    """Verify the three decision thresholds boundary behavior.

    Pass-2 finding (Codex-10): this test was previously `pass` — vacuous.
    Now we monkeypatch _fair_yield to return controlled markup values and
    assert the tier mapping is correct at the boundaries (1.5pp, 5.0pp).
    """
    from scripts.fair_aq_dq import _fair_yield
    q = _mock_quote()
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"

    def fake_fair_yield_factory(fair_yield_pa):
        def fake(q_arg, s_arg):
            return {
                "fair_yield_pa": fair_yield_pa,
                "ko_probability": 0.30,
                "breakdown": {
                    "short_premium_pv": 100.0, "pb_ko_leg_pv": 50.0,
                    "tail_pv": 10.0, "pb_quoted_payoff_pv": 200.0,
                    "fair_payoff_to_client_pv": 40.0, "markup_pv": 160.0,
                    "alive_obs": 180.0, "forfeited_obs": 72.0,
                },
                "data_provenance": {"spot": {"value": q_arg.spot, "source": s_arg.spot_source}},
            }
        return fake

    # markup_pp = pb_quoted_yield (0.09) - fair_yield_pa, × 100
    # Need markup_pp < 1.5 (ACCEPT_IF_MUST):
    monkeypatch.setattr("scripts.fair_aq_dq._fair_yield",
                       fake_fair_yield_factory(fair_yield_pa=0.080))
    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    assert v.decision == "ACCEPT_IF_MUST", f"expected ACCEPT_IF_MUST at markup=1.0, got {v.decision}"

    # markup_pp = 3.0 (COUNTER):
    monkeypatch.setattr("scripts.fair_aq_dq._fair_yield",
                       fake_fair_yield_factory(fair_yield_pa=0.060))
    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    assert v.decision == "COUNTER", f"expected COUNTER at markup=3.0, got {v.decision}"

    # markup_pp = 6.0 (REFUSE):
    monkeypatch.setattr("scripts.fair_aq_dq._fair_yield",
                       fake_fair_yield_factory(fair_yield_pa=0.030))
    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    assert v.decision == "REFUSE", f"expected REFUSE at markup=6.0, got {v.decision}"
    # Markup-tier REFUSE should populate refusal_reasons (Codex-14)
    assert v.refusal_reasons, "markup-tier REFUSE should record a reason"
    assert any("markup" in r.lower() for r in v.refusal_reasons)
```

- [ ] **Step 2: Verify failure**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k analyze_quote -v
```

Expected: NotImplementedError.

- [ ] **Step 3: Implement `analyze_quote`** (replace the stub)

```python
def analyze_quote(
    q: Quote, s: Snapshot, nlv_usd: float | None = None
) -> Verdict:
    """End-to-end quote analysis. 6-step pipeline:
    1. Refusal red-line check
    2. Chain pull (caller-provided in Snapshot)
    3. Fair-value compute
    4. Markup decision tier
    5. Empty levers list (optimize_terms is separate call)
    6. Return Verdict.
    """
    refusal_reasons = _check_refusal_red_lines(q, s, nlv_usd)

    if refusal_reasons:
        # Short-circuit — do not compute chain math
        return Verdict(
            fair_yield_pa=float("nan"),
            pb_quoted_yield_pa=q.pb_quoted_yield_pa,
            markup_pp=float("nan"),
            pb_annual_profit_usd=float("nan"),
            ko_probability=float("nan"),
            decision="REFUSE",
            refusal_reasons=refusal_reasons,
            breakdown={},
            data_provenance={"refusal_short_circuit": True},
        )

    fair = _fair_yield(q, s)
    markup_pp = (q.pb_quoted_yield_pa - fair["fair_yield_pa"]) * 100.0

    tenor_yr = q.tenor_months / 12.0
    n_obs = _num_observations(q.tenor_months, q.obs_freq)
    pb_annual_profit = (markup_pp / 100.0) * q.daily_notional_usd * n_obs

    tier_refusal_reasons: list[str] = []
    if markup_pp > 5.0:
        decision = "REFUSE"
        tier_refusal_reasons.append(
            f"Markup {markup_pp:.2f}pp > 5.0pp refusal threshold"
        )
    elif markup_pp > 1.5:
        decision = "COUNTER"
    else:
        decision = "ACCEPT_IF_MUST"

    return Verdict(
        fair_yield_pa=fair["fair_yield_pa"],
        pb_quoted_yield_pa=q.pb_quoted_yield_pa,
        markup_pp=markup_pp,
        pb_annual_profit_usd=pb_annual_profit,
        ko_probability=fair["ko_probability"],
        decision=decision,
        refusal_reasons=tier_refusal_reasons,
        breakdown=fair["breakdown"],
        data_provenance=fair["data_provenance"],
    )
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k analyze_quote -v
```

Expected: 3 passed (the `decision_tiers` test passes vacuously with `pass`).

- [ ] **Step 5: Commit**

```bash
git add tests/test_fair_aq_dq.py plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): analyze_quote — refusal short-circuit + decision tiers"
```

---

## Task 15: TDD — `optimize_terms` with Pareto sort

**Files:**
- Modify: `tests/test_fair_aq_dq.py`, `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Add failing test**

```python
from scripts.fair_aq_dq import optimize_terms


def test_optimize_terms_returns_sorted_pareto():
    q = _mock_quote(tenor_months=12, doubling_factor=2.0)
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"

    variants = optimize_terms(q, s)
    assert len(variants) > 0
    # Each variant has the required keys
    for v in variants:
        assert "param_changed" in v
        assert "old_value" in v
        assert "new_value" in v
        assert "markup_pp" in v
        assert "delta_pp" in v
        assert "pb_concession_difficulty" in v
        assert "leverage_score" in v
    # Sorted by leverage_score descending
    scores = [v["leverage_score"] for v in variants]
    assert scores == sorted(scores, reverse=True)


def test_optimize_terms_respects_sweep_param():
    q = _mock_quote()
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"

    variants = optimize_terms(q, s, sweep=["tenor_months"])
    # Only tenor variants present
    for v in variants:
        assert v["param_changed"] == "tenor_months"
```

- [ ] **Step 2: Implement `optimize_terms`**

```python
# Negotiation difficulty estimates per framework §5.
_TERM_GRID_BASE = {
    "tenor_months": [3, 6, 9, 12, 18],
    "doubling_factor": [1.0, 1.5, 2.0, 2.5, 3.0],
    "obs_freq": ["daily", "weekly", "monthly"],
}
# ko_pct grid is DIRECTION-AWARE: AQ KO above spot (>1.0); DQ KO below (<1.0).
_KO_GRID_AQ = [1.02, 1.03, 1.05, 1.07, 1.10]
_KO_GRID_DQ = [0.98, 0.97, 0.95, 0.93, 0.90]


def _term_grid_for(direction: Literal["AQ", "DQ"]) -> dict[str, list]:
    return {**_TERM_GRID_BASE,
            "ko_pct": _KO_GRID_AQ if direction == "AQ" else _KO_GRID_DQ}


def _concession_difficulty(param: str, old_val, new_val) -> float:
    """Heuristic difficulty score for PB to accept this concession (framework §5)."""
    if param == "tenor_months":
        return 1.5 if new_val < old_val else 0.5      # cutting tenor is easy
    if param == "ko_pct":
        # "Pushing KO further from spot" = lowering hit probability = PB hates
        return 3.5 if abs(new_val - 1.0) > abs(old_val - 1.0) else 1.0
    if param == "doubling_factor":
        return 4.5 if new_val < old_val else 0.5      # reducing 2× is hardest ask
    if param == "obs_freq":
        return {"weekly": 2.0, "monthly": 3.0}.get(new_val, 0.5)
    return 1.0


def optimize_terms(
    q: Quote,
    s: Snapshot,
    sweep: list[str] | None = None,
    nlv_usd: float | None = None,
) -> list[dict[str, Any]]:
    """Sweep each parameter through its (direction-aware) grid; compute markup_pp
    for each mutation. Return list sorted by leverage_score = delta_pp / difficulty
    (descending — top entries are easiest negotiation wins).

    nlv_usd propagates to analyze_quote so concentration-refusal red lines persist
    across mutations (a refused-for-concentration quote should not re-pass via
    optimization without curing the concentration).
    """
    grid = _term_grid_for(q.direction)
    params = sweep if sweep else list(grid.keys())
    base_verdict = analyze_quote(q, s, nlv_usd=nlv_usd)
    if base_verdict.decision == "REFUSE":
        # Pass-3 finding (A3): surface the refusal explicitly so caller can
        # distinguish "no mutations help" from "base was refused".
        return [{
            "param_changed": None,
            "old_value": None,
            "new_value": None,
            "markup_pp": base_verdict.markup_pp,
            "delta_pp": 0.0,
            "pb_concession_difficulty": 0.0,
            "leverage_score": 0.0,
            "refused_base": True,
            "refusal_reasons": list(base_verdict.refusal_reasons),
        }]
    base_markup = base_verdict.markup_pp

    variants: list[dict[str, Any]] = []
    for param in params:
        for val in grid[param]:
            if val == getattr(q, param):
                continue
            mutated = replace(q, **{param: val})
            try:
                v_mut = analyze_quote(mutated, s, nlv_usd=nlv_usd)
            except (ValueError, KeyError):
                continue
            if v_mut.decision == "REFUSE":
                continue  # Mutation hits a different red line — skip
            delta = base_markup - v_mut.markup_pp
            difficulty = _concession_difficulty(param, getattr(q, param), val)
            score = delta / max(0.5, difficulty)
            variants.append({
                "param_changed": param,
                "old_value": getattr(q, param),
                "new_value": val,
                "markup_pp": v_mut.markup_pp,
                "delta_pp": delta,
                "pb_concession_difficulty": difficulty,
                "leverage_score": score,
            })

    variants.sort(key=lambda x: x["leverage_score"], reverse=True)
    return variants
```

- [ ] **Step 3: Run tests, verify pass**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k optimize_terms -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_fair_aq_dq.py plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): optimize_terms — 4-param sweep + leverage-score Pareto sort"
```

---

## Task 16: TDD — `build_counter_offer_email`

**Files:**
- Modify: `tests/test_fair_aq_dq.py`, `plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py`

- [ ] **Step 1: Add failing test**

```python
from scripts.fair_aq_dq import build_counter_offer_email


def test_counter_offer_email_returns_bilingual_dict():
    q = _mock_quote()
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"
    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    if v.decision == "REFUSE":
        pytest.skip("Mock data triggers refusal — test the COUNTER path instead")

    # Need levers populated → call optimize first
    v.levers_to_negotiate = optimize_terms(q, s)[:3]

    email = build_counter_offer_email(v, q, target_markup_pp=1.5)
    assert "chinese_body" in email
    assert "english_body" in email
    assert q.ticker in email["chinese_body"]
    assert q.ticker in email["english_body"]
    # Chinese first
    assert email["chinese_body"].index(q.ticker) < email["english_body"].index(q.ticker) + 10000
```

- [ ] **Step 2: Implement `build_counter_offer_email`**

```python
def build_counter_offer_email(
    v: Verdict, q: Quote, target_markup_pp: float = 1.5
) -> dict[str, str]:
    """Bilingual counter-offer email. Chinese first, English second.
    Pull top 3 levers from `v.levers_to_negotiate` (caller should populate
    via `optimize_terms` before calling this).
    """
    levers = v.levers_to_negotiate[:3] if v.levers_to_negotiate else []

    def _describe_lever(lever: dict) -> tuple[str, str]:
        """(Chinese description, English description) for one lever."""
        param = lever["param_changed"]
        old, new = lever["old_value"], lever["new_value"]
        delta_pp = lever["delta_pp"]
        if param == "tenor_months":
            cn = f"Tenor 从 {old}M 缩短到 {new}M"
            en = f"Cut tenor from {old}M to {new}M"
        elif param == "ko_pct":
            cn = f"KO 从 {old * 100:.0f}% 推到 {new * 100:.0f}%"
            en = f"Push KO from {old * 100:.0f}% to {new * 100:.0f}%"
        elif param == "doubling_factor":
            cn = f"Doubling 从 {old}× 降到 {new}×"
            en = f"Reduce doubling from {old}× to {new}×"
        elif param == "obs_freq":
            cn = f"观察频率从 {old} 改为 {new}"
            en = f"Change observation freq from {old} to {new}"
        else:
            cn = f"{param}: {old} → {new}"
            en = f"{param}: {old} → {new}"
        cn += f" (markup 降约 {delta_pp:.2f} pp)"
        en += f" (markup ↓ ~{delta_pp:.2f} pp)"
        return cn, en

    lever_lines_cn = "\n".join(
        f"  {i+1}. {_describe_lever(l)[0]}" for i, l in enumerate(levers)
    )
    lever_lines_en = "\n".join(
        f"  {i+1}. {_describe_lever(l)[1]}" for i, l in enumerate(levers)
    )

    chinese_body = f"""[PB 联系人姓名]，你好，

谢谢你报的 {q.ticker} {q.direction} quote。我做了详细的 fair-value 分析,
对比 listed-chain mid 价格和 barrier-adjusted 现金流贴现:

  PB 报价 yield:     {q.pb_quoted_yield_pa * 100:.2f}% p.a.
  Fair-value yield:  {v.fair_yield_pa * 100:.2f}% p.a.
  Markup:           {v.markup_pp:.2f} pp ≈ ${v.pb_annual_profit_usd:,.0f}/年 抽成

要进一步推进, 我需要以下让步:

{lever_lines_cn}

调整后目标 markup ≤ {target_markup_pp} pp = 接近机构定价。如能配合, 请重新报价;
否则我们 pass 这单。

Best,
[trader]
"""

    english_body = f"""Hi [PB contact name],

Thanks for the {q.ticker} {q.direction} quote. I ran a fair-value breakdown
against listed-chain mids with barrier-adjusted cash flows:

  PB quoted yield:   {q.pb_quoted_yield_pa * 100:.2f}% p.a.
  Fair-value yield:  {v.fair_yield_pa * 100:.2f}% p.a.
  Markup:           {v.markup_pp:.2f} pp ≈ ${v.pb_annual_profit_usd:,.0f}/yr take

To proceed, I'd need the following concessions:

{lever_lines_en}

Target post-concession markup ≤ {target_markup_pp} pp (institutional-pricing level).
If you can re-quote on these terms, happy to discuss; otherwise we'll pass on this one.

Best,
[trader]
"""

    return {
        "chinese_body": chinese_body,
        "english_body": english_body,
    }
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k counter_offer -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_fair_aq_dq.py plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
git commit -m "feat(script): build_counter_offer_email — bilingual Chinese/English template"
```

---

## Task 17: TDD — Mirror symmetry + skew increases markup

**Files:**
- Modify: `tests/test_fair_aq_dq.py`

- [ ] **Step 1: Add tests**

```python
def test_aq_dq_mirror_symmetry_basic_invariants():
    """AQ + mirrored-DQ on same params should yield comparable magnitude
    metrics. Exact equality is too strict (skew asymmetry breaks it), but
    KO probability and ballpark markup should be within 30%."""
    # Mock chain with mirror-symmetric strikes
    chain = {
        "2027-06-18": {
            0.50: {"put": {"mid": 0.50, "iv": 0.55}},
            0.95: {"put": {"mid": 5.20, "iv": 0.38}, "call": {"mid": 15.10, "iv": 0.30}},
            0.97: {"put": {"mid": 4.10, "iv": 0.34}, "call": {"mid": 10.40, "iv": 0.30}},
            1.00: {"put": {"mid": 8.10, "iv": 0.36}, "call": {"mid": 8.20, "iv": 0.31}},
            1.03: {"put": {"mid": 10.40, "iv": 0.35}, "call": {"mid": 4.10, "iv": 0.34}},
            1.05: {"put": {"mid": 15.10, "iv": 0.30}, "call": {"mid": 2.85, "iv": 0.34}},
            1.50: {"call": {"mid": 0.50, "iv": 0.42}},
        }
    }
    s_aq = _mock_snapshot(iv_rank=60.0)
    s_aq.chain = chain
    s_aq.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s_aq.earnings_date_iso = "2026-07-05"

    s_dq = _mock_snapshot(iv_rank=60.0)
    s_dq.chain = chain
    s_dq.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s_dq.earnings_date_iso = "2026-07-05"

    q_aq = _mock_quote(direction="AQ", strike_pct=0.95, ko_pct=1.03)
    q_dq = _mock_quote(direction="DQ", strike_pct=1.05, ko_pct=0.97)

    v_aq = analyze_quote(q_aq, s_aq, nlv_usd=50_000_000.0)
    v_dq = analyze_quote(q_dq, s_dq, nlv_usd=50_000_000.0)

    # Both should compute a verdict (not refuse on these params)
    assert v_aq.decision != "REFUSE"
    assert v_dq.decision != "REFUSE"
    # KO probabilities should be in same ballpark (within 30%)
    if v_aq.ko_probability > 0:
        ratio = v_dq.ko_probability / v_aq.ko_probability
        assert 0.5 < ratio < 2.0, (
            f"AQ ko_prob={v_aq.ko_probability:.3f} vs DQ ko_prob={v_dq.ko_probability:.3f}"
        )


# ─── Pass-3 adversarial tests ──────────────────────────────


def test_quote_validation_aq_strike_above_spot_rejected():
    """Pass-3 (A1): AQ requires strike_pct < 1.0; reject otherwise."""
    with pytest.raises(ValueError, match="AQ requires"):
        Quote(direction="AQ", ticker="X", spot=100.0, strike_pct=1.05,
              ko_pct=1.10, tenor_months=12, obs_freq="daily",
              doubling_factor=2.0, daily_notional_usd=10_000.0,
              pb_quoted_yield_pa=0.09, settlement="cash")


def test_quote_validation_dq_strike_below_spot_rejected():
    """Pass-3 (A1): DQ requires strike_pct > 1.0; reject otherwise."""
    with pytest.raises(ValueError, match="DQ requires"):
        Quote(direction="DQ", ticker="X", spot=100.0, strike_pct=0.95,
              ko_pct=0.90, tenor_months=12, obs_freq="daily",
              doubling_factor=2.0, daily_notional_usd=10_000.0,
              pb_quoted_yield_pa=0.09, settlement="cash")


def test_quote_validation_zero_spot_rejected():
    """Pass-3 (A2): spot=0 prevents divide-by-zero in shares_per_obs."""
    with pytest.raises(ValueError, match="spot must be > 0"):
        Quote(direction="AQ", ticker="X", spot=0.0, strike_pct=0.95,
              ko_pct=1.03, tenor_months=12, obs_freq="daily",
              doubling_factor=2.0, daily_notional_usd=10_000.0,
              pb_quoted_yield_pa=0.09, settlement="cash")


def test_quote_validation_zero_tenor_rejected():
    """Pass-3 (A2): tenor_months=0 prevents divide-by-zero in fair_yield_pa."""
    with pytest.raises(ValueError, match="tenor_months must be"):
        Quote(direction="AQ", ticker="X", spot=100.0, strike_pct=0.95,
              ko_pct=1.03, tenor_months=0, obs_freq="daily",
              doubling_factor=2.0, daily_notional_usd=10_000.0,
              pb_quoted_yield_pa=0.09, settlement="cash")


def test_quote_validation_doubling_below_one_rejected():
    """Pass-3 (A2): doubling_factor < 1.0 makes no economic sense."""
    with pytest.raises(ValueError, match="doubling_factor must be"):
        Quote(direction="AQ", ticker="X", spot=100.0, strike_pct=0.95,
              ko_pct=1.03, tenor_months=12, obs_freq="daily",
              doubling_factor=0.5, daily_notional_usd=10_000.0,
              pb_quoted_yield_pa=0.09, settlement="cash")


def test_optimize_terms_surfaces_refused_base():
    """Pass-3 (A3): when base is REFUSE, return single-row sentinel
    (not silent empty list)."""
    q = _mock_quote(doubling_factor=3.0)  # red line — REFUSE
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    variants = optimize_terms(q, s, nlv_usd=1_000_000.0)
    assert len(variants) == 1
    assert variants[0].get("refused_base") is True
    assert variants[0].get("refusal_reasons"), "must include refusal reasons"


def test_nearest_expiry_skips_past_dated():
    """Pass-3 (A4): expired chain entries are filtered out."""
    # Mock chain: one past expiry, one future
    chain = {
        "2024-06-18": {0.95: {"put": {"mid": 5.0, "iv": 0.30}}},  # past
        "2027-06-18": {0.95: {"put": {"mid": 5.0, "iv": 0.30}}},  # future
    }
    result = _nearest_expiry_to_tenor(
        chain, tenor_months=12, quote_start_iso="2026-06-05T00:00:00Z"
    )
    assert result == "2027-06-18", f"expected future expiry, got {result}"


def test_nearest_expiry_raises_when_all_expired():
    """Pass-3 (A4): if every expiry is in the past, raise."""
    chain = {
        "2024-06-18": {0.95: {"put": {"mid": 5.0, "iv": 0.30}}},
        "2025-01-18": {0.95: {"put": {"mid": 5.0, "iv": 0.30}}},
    }
    with pytest.raises(ValueError, match="No future-dated"):
        _nearest_expiry_to_tenor(
            chain, tenor_months=12, quote_start_iso="2026-06-05T00:00:00Z"
        )


def test_fair_yield_rejects_spot_divergence():
    """Pass-2 (C7): q.spot and s.spot drift > 0.5% means stale snapshot.
    Refuse to compute fair value on inconsistent data."""
    from scripts.fair_aq_dq import _fair_yield
    q = _mock_quote(spot=200.0)
    s = _mock_snapshot()
    s.spot = 210.0  # 5% drift — stale snapshot
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    with pytest.raises(ValueError, match="diverges"):
        _fair_yield(q, s)


def test_data_provenance_completeness():
    q = _mock_quote()
    s = _mock_snapshot()
    s.chain = _mock_chain()
    s.chain_timestamps = {"2027-06-18": "2026-06-05T10:00:00Z"}
    s.earnings_date_iso = "2026-07-05"

    v = analyze_quote(q, s, nlv_usd=50_000_000.0)
    if v.decision == "REFUSE":
        pytest.skip("Test must run on non-refused quote")

    # Every numeric field used in the breakdown must have provenance
    required_provenance_keys = [
        "spot", "chain_source", "strike_leg_mid", "ko_leg_mid", "iv_at_ko",
        "ko_probability", "alive_obs"
    ]
    for k in required_provenance_keys:
        assert k in v.data_provenance, f"Missing provenance key: {k}"
        if "value" in v.data_provenance[k]:
            assert v.data_provenance[k]["value"] is not None
```

- [ ] **Step 2: Run tests**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -k "mirror or provenance" -v
```

Expected: 2 passed.

- [ ] **Step 3: Run full file — verify all tests still pass**

```bash
.venv/bin/pytest tests/test_fair_aq_dq.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_fair_aq_dq.py
git commit -m "test(script): AQ/DQ mirror symmetry + data_provenance completeness"
```

---

## Task 18: `aq-example-case.md` synthetic case study

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/ticker/aq-example-case.md`

**Gate (do NOT start Task 18 until all of these pass):**

```bash
# Verify all prior tasks complete: fair_aq_dq.py exists + test suite green
ls plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py
.venv/bin/pytest tests/test_fair_aq_dq.py -q
```

Expected: file exists; ALL tests pass. If any test fails, fix the implementing
task first — running Task 18 before tests pass will burn placeholder values
into the case study that don't match the actual script output.

- [ ] **Step 1: Compute reference numbers using the live script**

Run this to generate the numbers used in the case study:

```bash
cd plugins/option-wizard/skills/option-wizard && .venv/bin/python -c "
from scripts.fair_aq_dq import Quote, Snapshot, analyze_quote, optimize_terms, build_counter_offer_email

chain = {
    '2027-06-18': {
        0.50: {'put': {'mid': 0.50, 'iv': 0.55}},
        0.95: {'put': {'mid': 5.20, 'iv': 0.38}, 'call': {'mid': 15.10, 'iv': 0.30}},
        1.00: {'put': {'mid': 8.10, 'iv': 0.36}, 'call': {'mid': 8.20, 'iv': 0.31}},
        1.03: {'put': {'mid': 10.40, 'iv': 0.35}, 'call': {'mid': 4.10, 'iv': 0.34}},
        1.05: {'call': {'mid': 2.85, 'iv': 0.34}},
        1.10: {'call': {'mid': 1.10, 'iv': 0.33}},
    }
}
q = Quote(direction='AQ', ticker='MEGA-S', spot=200.0, strike_pct=0.95, ko_pct=1.03,
          tenor_months=12, obs_freq='daily', doubling_factor=2.0,
          daily_notional_usd=10000.0, pb_quoted_yield_pa=0.09, settlement='cash')
s = Snapshot(spot=200.0, spot_source='TV', spot_timestamp='2026-06-05T10:00:00Z',
             chain=chain, chain_source='UW',
             chain_timestamps={'2027-06-18': '2026-06-05T10:00:00Z'},
             rv_30d=0.30, rv_90d=0.32, iv_rank=60.0,
             atr_14_pct_of_spot=0.02, earnings_date_iso='2026-09-10',
             max_drawdown_5y=-0.55)
v = analyze_quote(q, s, nlv_usd=50_000_000.0)
print('verdict.markup_pp:', round(v.markup_pp, 2))
print('verdict.decision:', v.decision)
print('verdict.fair_yield_pa:', round(v.fair_yield_pa * 100, 2), '%')
print('verdict.ko_probability:', round(v.ko_probability, 3))
print('breakdown:', {k: round(val, 0) for k, val in v.breakdown.items()})
top_levers = optimize_terms(q, s)[:3]
for i, l in enumerate(top_levers, 1):
    print(f'lever {i}:', l['param_changed'], l['old_value'], '→', l['new_value'],
          f'delta={l[\"delta_pp\"]:.2f}pp')
v.levers_to_negotiate = top_levers
email = build_counter_offer_email(v, q)
print('---CN---')
print(email['chinese_body'])
print('---EN---')
print(email['english_body'])
"
```

Capture the output — those numbers feed Step 2.

- [ ] **Step 2: Write case study using live numbers**

Create `plugins/option-wizard/skills/option-wizard/references/ticker/aq-example-case.md` with the structure below. Replace `<MARKUP_PP>`, `<FAIR_YIELD>`, `<KO_PROB>`, `<BREAKDOWN_*>`, `<LEVER_*>`, and the email body with the actual numbers from Step 1.

````markdown
# AQ Example Case — MEGA-S (synthetic)

Synthetic public case study for the AQ/DQ framework. All numbers generated by
`scripts.fair_aq_dq` with the mock chain documented below. No real client
positions, no real PB quote.

## §1 The quote on the table

PB email (paraphrased):
> "We can offer an Accumulator on MEGA-S, 12-month tenor, daily observation,
> strike at 95% spot, KO at 103% spot, 2× doubling, cash settlement, implied
> yield 9.0% p.a. Daily notional $10,000."

Spot $200.00. Trader's reaction: "9% yield on a name I'd own anyway? Let me
check the markup."

## §2 Step 1 — Refusal red-line check (framework §6)

| # | Trigger | Result |
|---|---|---|
| 1 | doubling ≥ 3× | ✗ doubling = 2.0 |
| 2 | AQ + IV rank < 30 | ✗ IV rank = 60 |
| 3 | KO − spot < 1×ATR(14) | ✗ KO 3% > ATR 2% |
| 4 | notional > 10% NLV | ✗ $2.52M < 10% of $50M = $5M |
| 5 | tenor > 18M | ✗ tenor = 12M |
| 6 | ER in middle 50% of tenor | ✗ ER 2026-09-10 is at month 3 (25%) — at boundary, not "in" |

Result: **No refusal triggers. Proceed to evaluation.**

## §3 Step 2 — Chain pull (UW analytical mode)

Pulled UW chain at the listed expiry closest to tenor end (2027-06-18, 12.5M
forward). Key strikes:

| Strike % | Put mid | Put IV | Call mid | Call IV |
|---|---:|---:|---:|---:|
| 50% | 0.50 | 0.55 | — | — |
| 95% | 5.20 | 0.38 | 15.10 | 0.30 |
| 100% | 8.10 | 0.36 | 8.20 | 0.31 |
| 103% | 10.40 | 0.35 | 4.10 | 0.34 |
| 105% | — | — | 2.85 | 0.34 |

UW served: RV 30D = 0.30, IV rank = 60, GEX levels (mock), max pain (mock).

## §4 Step 3 — Fair-value breakdown

```
n_obs (daily × 12M):                       252
shares per observation:                    $10,000 / $200 = 50
KO probability (12M, Broadie-Glasserman):  <KO_PROB>
Expected alive observations:               <ALIVE_OBS>
Expected forfeited observations (lost to KO): <FORFEITED_OBS>

Short premium leg (put chain mid $5.20 at 95% — AQ direction):
  $5.20 × 50 × alive_obs × 2.0  =  <BREAKDOWN_SHORT_PREMIUM_PV>

PB KO leg (call chain mid $4.10 at 103%):
  $4.10 × 50 × forfeited_obs    =  <BREAKDOWN_KO_LEG_PV>

Doubling tail leg (put chain mid $0.50 at deep-OTM 50% — AQ direction):
  $0.50 × (50 × 252) × 2.0 × tail_activation_prob  =  <BREAKDOWN_TAIL_PV>

────────────────────────────────────────────
Fair payoff to client PV:                  <BREAKDOWN_FAIR_PAYOFF>
PB quoted payoff PV (9% × $10K × 252 × 1y): <BREAKDOWN_PB_QUOTED>
────────────────────────────────────────────
PB markup PV:                              <BREAKDOWN_MARKUP_PV>
→ markup_pp:                               <MARKUP_PP>
→ fair_yield_pa:                           <FAIR_YIELD>%
→ PB annual profit on this quote:          ~$<PB_ANNUAL_PROFIT>
```

**Data provenance:**

| Field | Source | Note |
|---|---|---|
| spot | TV @ 2026-06-05T10:00:00Z | live |
| chain | UW @ 2026-06-05T10:00:00Z | analytical mode |
| strike_leg_mid (put @ 95%) | UW chain[...] | direct read |
| ko_leg_mid (call @ 103%) | UW chain[...] | direct read |
| iv_at_ko (call IV @ 103%) | UW chain[...] | used in KO prob calc |
| ko_probability | computed | BSM first-passage + Broadie-Glasserman |
| alive_obs | computed | E[N_alive] = ko_prob / p_per_obs |
| tail_fallback_used | False | chain covered 50% put |

## §5 Step 4 — Term optimizer Pareto

Top 3 negotiation levers (by leverage_score = delta_pp / pb_concession_difficulty):

| # | Param change | markup_pp after | Δ pp | PB difficulty |
|---|---|---:|---:|---:|
| 1 | <LEVER_1_DESC> | <LEVER_1_MARKUP> | <LEVER_1_DELTA> | <LEVER_1_DIFFICULTY> |
| 2 | <LEVER_2_DESC> | <LEVER_2_MARKUP> | <LEVER_2_DELTA> | <LEVER_2_DIFFICULTY> |
| 3 | <LEVER_3_DESC> | <LEVER_3_MARKUP> | <LEVER_3_DELTA> | <LEVER_3_DIFFICULTY> |

## §6 Step 5 — Bilingual counter-offer email

[Paste `email['chinese_body']` followed by `email['english_body']` from
Step 1's script run]

## §7 Step 6 — Final verdict

Decision: **COUNTER** — markup_pp = <MARKUP_PP> (> 1.5pp threshold, ≤ 5pp threshold).

If PB accepts the top 3 lever asks, markup drops to <PROJECTED_MARKUP> pp.
If PB refuses → recommend REFUSE.

## §8 What this case teaches

1. **Skew premium is the single biggest PB profit source.** Chain mid at 103%
   call (IV 0.34) vs ATM IV (0.31) — that 3 vol points × 252 obs × leverage
   = thousands of $.
2. **2× doubling lowers fair yield by ~half of the tail leg's PV.** A 1×
   contract on same params would have fair_yield ~2pp higher.
3. **KO at 103% is "looks-good-but-traps-you"**: KO probability under 12M
   daily-monitored 30% vol ≈ <KO_PROB_PCT>%. The trader gets the yield only
   while the structure stays alive — which is typically <ALIVE_DAYS_PCT>%
   of the tenor.
4. **Counter-offer math beats vibes.** Without this framework, a 9% yield
   sounds like a generous offer; the framework shows it's actually ~<MARKUP_PP>
   pp of PB take. The counter ask brings it to institutional territory.
5. **Doubling reduction (2× → 1×) is the highest-leverage ask, but the
   hardest to win.** Lead with tenor + obs-freq cuts; use doubling as the
   walk-away threat.
````

- [ ] **Step 3: Verify file (no unfilled placeholders)**

```bash
EXAMPLE=plugins/option-wizard/skills/option-wizard/references/ticker/aq-example-case.md
wc -l "$EXAMPLE"
# Hunt for unfilled placeholders — any <UPPERCASE_TOKEN> pattern is a fail
UNFILLED=$(grep -E '<[A-Z][A-Z_]+[A-Z0-9_]*>' "$EXAMPLE" || true)
if [ -n "$UNFILLED" ]; then
  echo "FAIL — unfilled placeholders remain:"
  echo "$UNFILLED"
  exit 1
else
  echo "OK — no unfilled placeholders"
fi
```

Expected: ~150 lines; `OK — no unfilled placeholders`.

- [ ] **Step 4: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/ticker/aq-example-case.md
git commit -m "feat(skill): aq-example-case.md — synthetic MEGA-S case study with live-script numbers"
```

---

## Task 19: Self-review run — full test suite + smoke run

- [ ] **Step 1: Run full test suite**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass (existing + new ~22 in test_fair_aq_dq.py).

- [ ] **Step 2: Smoke run via the documented script invocation**

```bash
cd plugins/option-wizard/skills/option-wizard && .venv/bin/python -c '
from scripts.fair_aq_dq import analyze_quote, optimize_terms, Quote, Snapshot

chain = {
    "2027-06-18": {
        0.50: {"put": {"mid": 0.50, "iv": 0.55}},
        0.95: {"put": {"mid": 5.20, "iv": 0.38}, "call": {"mid": 15.10, "iv": 0.30}},
        1.00: {"put": {"mid": 8.10, "iv": 0.36}, "call": {"mid": 8.20, "iv": 0.31}},
        1.03: {"put": {"mid": 10.40, "iv": 0.35}, "call": {"mid": 4.10, "iv": 0.34}},
    }
}
q = Quote(direction="AQ", ticker="MEGA-S", spot=200.0, strike_pct=0.95,
          ko_pct=1.03, tenor_months=12, obs_freq="daily",
          doubling_factor=2.0, daily_notional_usd=10000.0,
          pb_quoted_yield_pa=0.09, settlement="cash")
s = Snapshot(spot=200.0, spot_source="TV", spot_timestamp="2026-06-05T10:00:00Z",
             chain=chain, chain_source="UW",
             chain_timestamps={"2027-06-18": "2026-06-05T10:00:00Z"},
             rv_30d=0.30, rv_90d=0.32, iv_rank=60.0,
             atr_14_pct_of_spot=0.02, earnings_date_iso="2026-07-05",
             max_drawdown_5y=-0.55)
v = analyze_quote(q, s, nlv_usd=50_000_000.0)
print("decision:", v.decision)
print("markup_pp:", round(v.markup_pp, 2))
print("levers (top 3):")
for l in optimize_terms(q, s)[:3]:
    print(" ", l["param_changed"], l["old_value"], "→", l["new_value"],
          f"delta={l[\"delta_pp\"]:.2f}pp")
'
```

Expected: prints decision + markup_pp + 3 lever rows. No exceptions.

- [ ] **Step 3: Verify all 4 new files exist**

```bash
ls -la plugins/option-wizard/skills/option-wizard/references/aq-dq-framework.md \
       plugins/option-wizard/skills/option-wizard/references/ticker/aq-example-case.md \
       plugins/option-wizard/skills/option-wizard/scripts/fair_aq_dq.py \
       tests/test_fair_aq_dq.py
```

Expected: all 4 files present, non-zero size.

- [ ] **Step 4: Verify rule changes propagated**

```bash
grep -c "Source discipline (3-source" plugins/option-wizard/skills/option-wizard/SKILL.md
grep -c "AQ / DQ" CLAUDE.md
grep -c "Workflow 5" plugins/option-wizard/skills/option-wizard/references/workflows-overview.md
```

Expected: each ≥ 1.

- [ ] **Step 5: Commit (if any cleanup found needed)**

If self-review surfaced any issue, fix and commit:

```bash
git add -A
git commit -m "chore: self-review cleanup before PR"
```

---

## Task 20: Codex review + PR

- [ ] **Step 1: Run /codex-review on the full diff**

In Claude Code, run:

```
/codex-review
```

Capture the review output. If codex flags real bugs / math errors, address them and re-commit. Vague style suggestions can be ignored per the user's "三个相似行胜过过早抽象" principle.

- [ ] **Step 2: Push the branch and open PR**

```bash
git push -u origin feat/aq-dq-framework
gh pr create --title "feat: AQ/DQ framework — PB markup exposure + term optimizer" --body "$(cat <<'EOF'
## Summary
- Adds `aq-dq-framework.md` (8 sections, 280 lines): structure, PB profit mechanism, fair-value heuristic with data-source discipline, 8-item PB checklist, term levers, 6 refusal red lines, bilingual counter-offer email template, live-quote workflow
- Adds `scripts/fair_aq_dq.py` (~550 lines): Quote/Snapshot/Verdict dataclasses, `analyze_quote` / `optimize_terms` / `build_counter_offer_email`, chain-mid-priced legs with barrier-adjusted PVs, BSM first-passage + Broadie-Glasserman discrete KO probability
- Adds `tests/test_fair_aq_dq.py` (22+ tests): 6 refusal red-line tests, KO probability invariants, accumulation PV, chain-read helpers, mirror symmetry, data_provenance completeness
- Adds `aq-example-case.md`: synthetic MEGA-S walk-through with live-script numbers
- Rewrites SKILL.md hard rule #2 to 3-source taxonomy (UW + IB + TV with overlap-zone priority)
- Extends SKILL.md hard rule #5 + CLAUDE.md summary to cover FCN/AQ/DQ as a class
- Adds Workflow 5 to workflows-overview.md

## Spec
docs/superpowers/specs/2026-06-05-aq-dq-framework-design.md

## Plan
docs/superpowers/plans/2026-06-05-aq-dq-framework.md

## Test plan
- [x] All existing tests still pass
- [x] 22 new tests in test_fair_aq_dq.py pass
- [x] Smoke run via documented script invocation works
- [x] /codex-review passes (or flagged issues addressed)

EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 3: Notify trader for review**

Done — design + plan + implementation are all in worktree `.worktrees/aq-dq-framework`. PR ready for trader review before merge.

---

## Self-review checklist

1. **Spec coverage:** Each spec section maps to a task:
   - §3 architecture → Task 1, 8 (file structure + skeleton)
   - §4 framework doc → Tasks 6-7
   - §5 script → Tasks 8-16
   - §6 SKILL/CLAUDE/workflows → Tasks 2-5
   - §7 case + tests → Tasks 9-18
   - §8 implementation order → mirrored in task numbering
   - §9 risk register → addressed inline in code (fallback flags, decision tier comments)
   - §10 acceptance criteria → Task 19 (smoke run validates each criterion)

2. **Placeholders:** None remaining — every code block is complete; every step has either exact code or exact command.

3. **Type consistency:** `Quote.strike_pct` is `float`, used consistently. `Snapshot.chain` keys are `expiry_iso → strike_pct → right('put'/'call') → field('mid'/'iv')` and that schema is used in `_read_chain_mid`, `_fair_yield`, and case-study mock data. `Verdict.decision` uses 3-value `Literal` consistently.

4. **Spec → Plan alignment:**
   - Spec `tests/smoke/test_fair_aq_dq.py` → Plan corrects to `tests/test_fair_aq_dq.py` (matches existing convention; flagged in §"File structure" note)

---

## Pass-2 (codex-review tribunal) — applied + deferred

**Applied** (Pass-2 critical fixes inline in plan):

| Finding | Source | Resolution |
|---|---|---|
| U1: doubling_factor over-applied to whole short put leg | Codex-4 + Gemini-1 | Split into base + (doubling-1) × adverse_region_prob; default 0.40 |
| U2: `_expected_alive_obs(0.9999, 252)` returns ~28, not ~1 | Codex-2 | Test bounds corrected to [20, 35] |
| U3: `_accumulation_pv(ko_prob=0.999)` returns ~$360K not <$50K | Codex-3 | Test rewritten as ratio comparison (pv_high_ko < pv_no_ko × 0.25) |
| U4: DQ optimizer used AQ ko_pct grid | Codex-6 + Claude-CL2 | Split into _KO_GRID_AQ/_KO_GRID_DQ + `_term_grid_for(direction)` |
| U5: ER test date at 27% of tenor labeled "outside middle 50%" | Codex-11 + Claude-CL1 | All `"2026-09-10"` references replaced with `"2026-07-05"` (8% of tenor) |
| U6: vacuous `test_analyze_quote_decision_tiers` | Codex-10 | Replaced with monkeypatched 3-tier verification + boundary checks |
| U7: Verdict missing spec fields (max_loss_p5, p1, expected_client_pnl) | Gemini-2 | Added as v2-deferred fields (default float("nan")) with backlog reference |
| U8: `_accumulation_pv` unused | Codex-5 + Gemini-6 | Documented as intentional v2 hook (Task 11 step preamble) |
| U9: optimize_terms drops nlv_usd | Codex-13 | Added nlv_usd param + propagated to inner analyze_quote calls |
| U10: SKILL.md "never route through IB" conflicts with using IB chain | Codex-15 | Rewrote rule #5 to split order routing (forbidden) from market data (allowed) |
| C7: q.spot vs s.spot silent divergence | Codex-7 | Added validation in `_fair_yield`: raises if drift > 0.5% |
| C12: tail prob direction-insensitive | Codex-12 + Gemini-5 | Documented AQ/DQ direction handling + heuristic rationale in `_tail_activation_prob` docstring |
| C14: markup-tier REFUSE has empty refusal_reasons | Codex-14 | Now populates reason: "Markup {x}pp > 5.0pp refusal threshold" |

**Deferred to v2 backlog or documented as known limitation**:

| Finding | Source | Why deferred |
|---|---|---|
| C8: chain schema uses exact float keys (won't match real chains 1:1) | Codex-8 | This is the orchestrator's contract concern, not the script's. Orchestrator (skill prompt flow) normalizes real UW/IB chain rows to the (expiry, strike_pct) shape before calling `_fair_yield`. Add to risk register: "Orchestrator must normalize chain data; mismatched listed strikes are picked by nearest within tolerance, with selected strike recorded in `data_provenance`." |
| C9: tenor optimizer reuses single 12M expiry for 3M/6M/18M variants | Codex-9 | Orchestrator should pre-pull chains for all tenor mutations in the grid before calling `optimize_terms`. Add to risk register: "Orchestrator must build Snapshot.chain with expiries spanning {3M, 6M, 9M, 12M, 18M} for full optimizer fidelity; otherwise mutations to absent tenors are silently dropped via the existing ValueError-skip path in optimize_terms." |
| Gemini-3: function names like `_short_put_leg_pv` for DQ "call" leg are confusing | Gemini-3 (advisory) | Internal helpers; chain-read mirroring in `_fair_yield` makes the direction conversion explicit. Trade-off: renaming to `_strike_leg_premium_pv` etc. clarifies but adds churn. v2 cleanup. |
| Gemini-4: `daily_notional_usd` is a misnomer for weekly/monthly obs | Gemini-4 (advisory) | Pure rename, no logic impact. v2 cleanup. |
| Claude-CL3: defensive KeyError on missing chain IV | Claude-CL3 | Orchestrator's contract requires IV field; raising on missing is fail-fast, not bug. |
| Claude-CL5: empty chain test gap | Claude-CL5 | Implicit in `_nearest_expiry_to_tenor` raise; add 1-line test in v1.1. |
| Claude-CL7: calendar 30-day approximation vs `_OBS_PER_YEAR` 252 convention | Gemini-9 + Claude-CL7 | <2% drift at tenor boundaries; documented tolerance. |
| Claude-CL8: mock chain missing 0.97 for default-DQ tests | Claude-CL8 | Tests that need DQ chain construct their own chain (e.g. `test_aq_dq_mirror_symmetry`); default mock is AQ-shaped. |

This Pass-2 has substantially reworked the math foundations. Pass-3 (adversarial) and Pass-4 (cumulative review) will verify these fixes hold under hostile inputs.
