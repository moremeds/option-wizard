# AQ / DQ Framework — Design Spec

**Date:** 2026-06-05
**Author:** Brainstormed via /option-wizard session 2026-06-04 → 2026-06-05
**Status:** Draft — awaiting trader review before transitioning to implementation plan
**Scope:** v1 only; v2/v3 captured in §11 backlog

---

## 1. Goal

Add to the `option-wizard` skill the ability to evaluate Private Bank–quoted
**Accumulator (AQ)** and **Decumulator (DQ)** structured products, with the
explicit framing: **"not unscrewed, but less screwed."**

The trader receives AQ/DQ pitches from PB regularly. These products are
structurally hostile to retail clients (asymmetric payoff, knock-out cuts
upside, doubling magnifies tail loss, opaque fair value). The framework's
job is to:

1. Expose how much the PB makes from a given quote (markup in pp of yield + USD
   annualized profit estimate)
2. Identify which terms (tenor / KO / doubling / observation frequency) yield
   the most negotiation leverage
3. Produce a bilingual counter-offer email with concrete concession asks
4. Block outright bad deals via 6 hard refusal red lines

## 2. Non-goals (v1)

- **No ticker screener** — given a watchlist, "which name is least bad for
  AQ/DQ." Deferred to v2.
- **No Monte Carlo path simulation** — heuristic closed-form (BSM first-passage
  for KO probability + chain-priced legs) is sufficient for ±0.5% markup
  accuracy and avoids opaque assumptions.
- **No automatic order routing** — PB structured products never go through IB
  (extension of existing hard rule #5).
- **No "make AQ/DQ safe" framing** — refusal red lines are real; the framework
  helps minimize damage when the trader chooses to engage, not pretend the
  product is safe.

## 3. Architecture overview

Single unified framework parameterized by `direction='AQ' | 'DQ'` (mirror
images sharing ~80% of math). Files:

**New:**

```
plugins/option-wizard/skills/option-wizard/
├── references/
│   ├── aq-dq-framework.md           (~280 lines)
│   └── ticker/
│       └── aq-example-case.md       (~150 lines, synthetic public case)
├── scripts/
│   └── fair_aq_dq.py                (~550 lines)
└── tests/smoke/
    └── test_fair_aq_dq.py           (~80 lines, 12 smoke tests)
```

**Modified:**

```
plugins/option-wizard/skills/option-wizard/
├── SKILL.md                         (hard rule #2 full rewrite; #5 extension;
│                                     +5 triggers; routing table +1 row;
│                                     +script-invocation example; archive list +1)
└── references/workflows-overview.md (+Workflow 5)

option-wizard/CLAUDE.md              (data-source order section aligned to
                                       3-source taxonomy; hard rule #5 extension)
```

## 4. Component 1 — `references/aq-dq-framework.md`

Domain-knowledge reference doc parallel to `fcn-framework.md`. ~280 lines.

| § | Title | Lines | Content |
|---|---|---:|---|
| 1 | What is AQ / DQ | 30 | Structure definition; client = short knock-out put (AQ) / short knock-out call (DQ) + doubling trigger; Buffett "I-kill-you-later" historical context; typical PB pitch decoded |
| 2 | The 4 things PB profits from | 30 | (a) IV markup; (b) skew markup; (c) KO-side optionality not refunded to client; (d) doubling tail underpriced |
| 3 | Fair-value heuristic + data-source discipline | 50 | Formula breakdown into 4 independently auditable terms (accumulation PV / KO call PV to PB / tail premium / fair vs quoted spread); §3 prefaced with the data-source discipline rule (next paragraph) |
| 4 | The 8-item PB checklist | 40 | Direction; KO type (American/European); doubling factor; observation freq; strike+KO distance; tenor; settlement (cash/physical); PB yield decomposition transparency |
| 5 | "Less screwed" levers | 40 | 4 term parameters × concrete markup-reduction tables; e.g., "shorter tenor 12M→6M: markup ↓1.5-2.5pp" |
| 6 | Refusal red lines | 25 | 6 hard refusals: doubling ≥ 3×; IV rank < 30 + AQ; spot−KO < 1 ATR(14); single notional > 10% NLV; tenor > 18M; ER in tenor midpoint |
| 7 | Counter-offer email template | 40 | Bilingual (Chinese first, English second); concession asks line-by-line |
| 8 | Live-quote workflow | 25 | 6-step pipeline from PB quote → verdict → email |

### Data-source discipline (written into §3 of the framework as a permanent
methodology principle):

> Listed-strike option price / IV / greeks **always read directly** from UW
> chain or IB chain (per source-selection mode below); **never recompute via
> BSM** inside the script. The script computes only quantities the data
> providers do not serve: barrier termination probabilities, accumulation
> cash-flow present value, barrier-adjustment factors, and the final fair
> vs quoted pp delta. Every numeric field in the Verdict carries a
> `data_provenance` entry marking source (UW direct / IB direct / TV /
> computed / fallback) + timestamp + staleness.

## 5. Component 2 — `scripts/fair_aq_dq.py`

Pure-function module. Orchestrator (skill prompt flow) fetches data and
builds the Snapshot; the script does only the math. ~550 lines.

### 5.1 Data contracts

```python
@dataclass
class Quote:
    direction: Literal['AQ', 'DQ']
    ticker: str
    spot: float
    strike_pct: float          # 0.95 = strike at 95% spot
    ko_pct: float              # 1.03 = KO at 103% spot (AQ); 0.97 (DQ)
    tenor_months: int
    obs_freq: Literal['daily', 'weekly', 'monthly']
    doubling_factor: float     # 1.0 / 2.0 / 3.0
    daily_notional_usd: float
    pb_quoted_yield_pa: float
    settlement: Literal['cash', 'physical']

@dataclass
class Snapshot:
    spot: float
    spot_source: Literal['TV', 'IB']
    spot_timestamp: str

    chain: dict[str, dict[float, dict[Literal['call', 'put'], dict]]]
    chain_source: Literal['IB', 'UW']
    chain_timestamps: dict[str, str]

    # UW-only metrics
    rv_30d: float
    rv_90d: float
    iv_rank: float
    skew_chain_derived: dict[int, dict[str, float]]
    gex_levels: dict
    gex_by_strike_at_ko: float | None
    max_pain_per_expiry: dict[str, float]

    # Fallback
    max_drawdown_5y: float

@dataclass
class Verdict:
    fair_yield_pa: float
    pb_quoted_yield_pa: float
    markup_pp: float
    pb_annual_profit_usd: float
    ko_probability_at_obs: float
    doubling_trigger_probability: float
    max_loss_p5: float
    max_loss_p1: float
    expected_client_pnl: float
    decision: Literal['REFUSE', 'COUNTER', 'ACCEPT_IF_MUST']
    refusal_reasons: list[str]
    breakdown: dict
    levers_to_negotiate: list[dict]
    data_provenance: dict
```

### 5.2 Public API

```python
def analyze_quote(q: Quote, s: Snapshot, nlv_usd: float | None = None) -> Verdict
def optimize_terms(q: Quote, s: Snapshot,
                   sweep: list[str] | None = None) -> list[dict]
def build_counter_offer_email(v: Verdict, q: Quote,
                              target_markup_pp: float = 1.5) -> dict
```

### 5.3 Internal math (pure functions, independently testable)

```python
def _check_refusal_red_lines(q: Quote, s: Snapshot,
                             nlv_usd: float | None) -> list[str]
def _ko_probability_per_observation(spot, ko_barrier, iv_at_ko,
                                    tenor_months, obs_freq) -> float
def _accumulation_pv(direction, spot, strike_pct, daily_notional,
                     ko_prob, tenor_months, obs_freq, r=0.04) -> float
def _doubling_tail_pv(direction, spot, strike_pct, doubling_factor,
                      tail_put_mid, tail_activation_prob) -> float
def _ko_call_pv(spot, ko_pct, ko_call_mid, ko_prob, shares_per_obs,
                n_obs) -> float
def _historical_tail_proxy(q, s) -> float
def _fair_yield(q, s) -> dict  # returns breakdown
def _estimate_pb_pushback(param: str, value) -> float  # for Pareto sort
```

### 5.4 Fair-value formula (chain-priced legs + barrier adjustment)

```
fair_payoff_to_client_PV =
    + short_put_PV                                       (chain mid at strike%, × shares × n_obs × doubling × (1 − ko_prob))
    − pb_ko_call_PV                                      (chain mid at ko%, × shares × n_obs × ko_prob)
    − doubling_tail_PV                                   (chain mid at ~50%, × shares × doubling × tail_activation_prob)

pb_quoted_payoff_PV =
    pb_quoted_yield_pa × daily_notional × n_obs × tenor_yr

markup_PV = pb_quoted_payoff_PV − fair_payoff_to_client_PV
fair_yield_pa = fair_payoff_to_client_PV / (daily_notional × n_obs × tenor_yr)
markup_pp = (pb_quoted_yield_pa − fair_yield_pa) × 100
```

Only barrier termination probabilities and accumulation PV are computed
inside the script; the three leg base values come from chain mid.

### 5.5 Term optimizer

Sweep grid (defaults; configurable via `sweep` param):

```python
GRID = {
    'tenor_months':    [3, 6, 9, 12, 18],
    'ko_pct':          [1.02, 1.03, 1.05, 1.07, 1.10],  # mirrored for DQ
    'doubling_factor': [1.0, 1.5, 2.0, 2.5, 3.0],
    'obs_freq':        ['daily', 'weekly', 'monthly'],
}
```

For each `(param, value)` mutation, recompute `markup_pp` and return a sorted
list by `markup_reduction / pb_concession_difficulty`. Top entries are the
sharpest negotiation leverage points.

### 5.6 Data provenance

Every Verdict carries a complete `data_provenance` dict mapping each
numeric field to its source (UW direct / IB direct / TV / computed /
fallback), the pull timestamp, and a staleness window. Format example
in §11.6.

## 6. Component 3 — Cross-file changes

### 6.1 SKILL.md hard rule #2 (full rewrite)

Replace the existing 2-source rule with 3-source taxonomy:

> **Source discipline (3-source taxonomy).** Three sources, each canonical for
> non-overlapping core territory + overlapping zones where freshness picks
> the winner.
>
> **Canonical per source:**
> - **UW** — options-derivative metrics no one else serves: IV rank, skew,
>   GEX by strike, max pain, RV, dark pool, flow, interpolated IV
> - **IB Gateway** — account state (positions / balances / orders / trades
>   / margin); paid broker-feed real-time chain (mid / IV / greeks);
>   `get_price_snapshot`
> - **TradingView** — spot, OHLCV, technical indicators (SMA / EMA / RSI /
>   MACD / BBANDS / ATR / volume bars), news, alerts, watchlists, charts
>
> **Overlapping zones priority:**
>
> | Data point | Primary | Fallback | Why |
> |---|---|---|---|
> | Spot | TV | IB `get_price_snapshot` | TV intra-minute fresh + chart-verifiable; IB broker-feed authoritative for live-trade gating |
> | Option chain mid / IV / greeks | **IB** (live trade <60s) / **UW** (analytical) | mutual fallback | IB seconds-fresh; UW better for skew/term analytical context |
> | OHLCV historical | TV (chart context) | IB `get_price_history` (backtest precision) | — |
>
> **Forbidden:**
> - UW `get_extended_technical_indicator` / `get_ticker_indicator_series` for
>   analysis (lagged by weeks)
> - IB for IV rank / skew / GEX / max pain (IB doesn't compute derivatives)
>
> **Rule of thumb:** if any of the three serves it directly, never recompute.
> Verdict / analysis output must carry `data_provenance` for every quoted
> metric.

### 6.2 SKILL.md hard rule #5 extension

> **PB structured products (FCN / AQ / DQ) never route through IB.** Output is
> product-specific:
> - **FCN**: 8-item PB checklist + 70/75/80/85% strike ladder + fair vs quoted
>   verdict + bilingual counter-offer email
> - **AQ / DQ**: 8-item PB checklist + fair-value breakdown (`data_provenance`
>   per number) + term-optimizer Pareto frontier + bilingual counter-offer
>   email; preceded by 6 refusal red-line check that may short-circuit to
>   REFUSE before any computation

### 6.3 SKILL.md triggers (new)

Chinese:
- "PB 给我报了 <TICKER> 的 AQ, X% strike, Y% KO"
- "PB 给我报了 DQ"
- "评估这个 accumulator 报价"
- "decumulator 怎么 counter"

English:
- "evaluate aq quote"
- "evaluate dq quote"
- "negotiate accumulator"

### 6.4 SKILL.md routing table (new row)

| AQ/DQ quote evaluation ("PB 给我报了 AQ", "evaluate aq quote") | `references/aq-dq-framework.md` + `scripts.fair_aq_dq::analyze_quote`/`optimize_terms`/`build_counter_offer_email`. Output: 6-refusal-check → breakdown w/ provenance → Pareto frontier → bilingual email. Do NOT route through IB (hard rule #5). |

### 6.5 SKILL.md scripts-invocation example (added)

```bash
.venv/bin/python -c '
from scripts.fair_aq_dq import analyze_quote, optimize_terms, Quote, Snapshot
q = Quote(direction="AQ", ticker="ORCL", spot=234.91, strike_pct=0.95, ko_pct=1.03,
          tenor_months=12, obs_freq="daily", doubling_factor=2.0,
          daily_notional_usd=10000, pb_quoted_yield_pa=0.08, settlement="cash")
# snapshot = Snapshot(...)  # orchestrator builds from IB/UW chains + UW metrics
v = analyze_quote(q, snapshot)
print(v.markup_pp, v.decision, v.refusal_reasons)
print(optimize_terms(q, snapshot)[:5])
'
```

### 6.6 SKILL.md archive list

Add `FCN/ELN/AQ/DQ evaluation with concrete deal numbers` to the
"trader typically wants saved" report list.

### 6.7 CLAUDE.md changes

- `§Data source order (universal)`: rewrite UW / IB / TV bullets to align
  with §6.1 3-source taxonomy. UW: "options-derivative metrics + chain mid/IV/
  greeks (analytical default)". IB: "account state + broker-feed real-time
  chain for live-trade-mode (<60s decision window); `get_price_snapshot`".
  TV: unchanged (spot + technicals + charts).
- `§Hard rules (summary)` #5: "FCN never routes through IB" → "PB structured
  products (FCN / AQ / DQ) never route through IB".

### 6.8 `workflows-overview.md` (+Workflow 5)

New section documenting the AQ/DQ workflow: trigger phrases, 6-step
decision tree (refusal → chain pull → fair value → term optimizer →
email → present), routes to `aq-dq-framework.md` + `fair_aq_dq.py` +
example case.

## 7. Component 4 — Example case + tests

### 7.1 `references/ticker/aq-example-case.md`

Synthetic, fully public, anonymized case study. Walks through the 6-step
workflow with concrete numbers:

```
Ticker:           "MEGA-S" (synthetic name)
Spot:             $200.00
Direction:        AQ
Strike:           95% = $190
KO:               103% = $206
Tenor:            12M
Obs freq:         daily
Doubling:         2×
Daily notional:   $10,000
PB quoted yield:  9.0% p.a.
```

Output sections: refusal red-line check passes → chain pull (UW analytical
mode) shows mid prices read → fair-value breakdown with `data_provenance`
→ term optimizer Pareto → counter-offer email (Chinese first, English
second) → verdict COUNTER with target markup 1.5pp → 5 case takeaways.

### 7.2 `tests/smoke/test_fair_aq_dq.py`

12 smoke tests, ~80 lines, hardcoded mock Snapshot, CI < 5 seconds:

- 6 refusal red-line tests (doubling 3×; AQ + low IV rank; KO < 1 ATR;
  notional > 10% NLV; tenor 18M; ER in tenor)
- 3 fair-value math tests (chain mid not BSM-recomputed; breakdown sum =
  total markup; skew increases markup)
- 1 AQ/DQ mirror symmetry test
- 1 term optimizer Pareto-sort test
- 1 data_provenance completeness test

## 8. Implementation order

1. Create worktree (per global rule)
2. Atomic commit: SKILL.md / CLAUDE.md / workflows-overview.md changes
   (rule + trigger + routing additions, no functional impact yet)
3. Write `references/aq-dq-framework.md`
4. TDD: `scripts/fair_aq_dq.py` + `tests/smoke/test_fair_aq_dq.py` together
5. Write `references/ticker/aq-example-case.md` using the live script for
   real numbers
6. `/codex-review` full diff
7. PR + merge per global rule

Estimated: 4-5 hours of focused work.

## 9. Risk register

| Risk | Mitigation |
|---|---|
| Heuristic fair-value accuracy depends on chain skew data quality | Explicit fallback when chain doesn't cover deep OTM tail; verdict.data_provenance flags fallback path |
| IB Gateway lacks real-time options subscription for some tickers | Orchestrator decision tree falls back to UW; `chain_source` field transparently logged |
| Barrier first-passage formula diverges from actual KO path | Discrete observation correction (per `obs_freq`); verdict surfaces `ko_probability` numerically so trader can sanity-check |
| Term optimizer Pareto gives "theoretically optimal but PB will refuse" | Each variant carries `pb_concession_difficulty`; sort key is `markup_reduction / concession_difficulty` |
| Trader misreads framework as "AQ/DQ is now safe" | aq-dq-framework.md §6 explicitly states framing; every Verdict carries footer disclaimer "this is less-screwed, not unscrewed" |

## 10. Acceptance criteria

v1 ships when:

1. All 12 smoke tests pass; CI < 5 seconds total
2. Example case study renders coherently and uses the live script for every
   number
3. `data_provenance` populated for every numeric Verdict field; no
   placeholder strings
4. 3-source rule passes a 1-trader review on SKILL.md + CLAUDE.md
5. Mock end-to-end run: synthetic Quote + mock Snapshot → `analyze_quote` →
   `optimize_terms` → `build_counter_offer_email` completes without raising
6. Refusal red-line short-circuit verified: Quote with `doubling_factor=3.0`
   returns `decision='REFUSE'` immediately without calling chain-dependent
   math

## 11. v2 / v3 backlog (out of scope for v1)

### 11.1 Ticker screener (deferred from v1)

Given trader watchlist + AQ/DQ direction, rank by "least bad" using
realized vs implied skew, max-drawdown history, gamma flip distance to spot,
path centrality (mean reversion vs trend). Outputs a sorted table.

### 11.2 Monte Carlo path simulation (deferred)

Replace closed-form barrier formula with MC over N paths for explicit P&L
distribution. Adds dependency on vol-surface evolution model. Defer until
heuristic shows real-world divergence on a closed AQ/DQ deal.

### 11.3 Multi-quote comparison (deferred)

PB often sends 2-3 variants of the same product. Side-by-side comparison
mode that highlights which terms changed and how markup differs.

### 11.4 Real IB chain integration (post v1)

v1 documents the IB chain-pull path but the orchestrator's IB chain code
path may not exist yet in the codebase. v1 ships with UW chain primary +
IB chain as documented orchestrator behavior; first IB-chain run waits
until a live-mode quote actually arrives.

### 11.5 Outcome tracking (post-trade analysis)

Once trader actually does (or refuses) an AQ/DQ, fill in the
Outcome/Lesson section of the archived analysis. Compare actual KO date,
actual accumulation, actual PB profit vs framework prediction.

### 11.6 Verdict.data_provenance reference format

```python
verdict.data_provenance = {
    'spot': {'value': 234.91, 'source': 'TV', 'timestamp': '...', 'staleness_s': 3},
    'chain': {'source': 'IB', 'pulled_at': '...', 'expiries_pulled': [...],
              'subscription_realtime': True, 'consolidated_delay_min': 0},
    'put_at_strike': {'value': 5.20, 'source': 'IB chain[...][0.95]["put"]["mid"]',
                      'bid_ask_spread': 0.10},
    'iv_rank': {'value': 62, 'source': 'UW', 'pulled_at': '...'},
    'ko_probability_at_obs': {'value': 0.42, 'source': 'computed (BSM first-passage)',
                              'inputs': {...}},
    'max_drawdown_5y_fallback_used': False,
}
```

## 12. Open questions for trader review

(None as of brainstorming close — all 5 sections OK'd. Listed here for the
record so the spec self-review remembers to re-check before implementation.)

---

## Spec self-review notes

Reviewed for: placeholders, internal consistency, scope, ambiguity.

- **Placeholders:** None remaining. v2/v3 items are explicitly labeled as
  out-of-scope, not "TBD".
- **Consistency:** §3 architecture matches §4-7 components. §6.1's
  3-source rule applied consistently in §5.1 Snapshot fields.
- **Scope:** Single implementation plan, ~4-5 hours. No decomposition
  needed.
- **Ambiguity:** Two clarifications added during review:
  - §5.4 explicitly notes "only barrier termination probabilities and
    accumulation PV are computed inside the script; the three leg base
    values come from chain mid" — was ambiguous earlier.
  - §11.4 separately tracks the IB chain integration sequencing (v1 ships
    with documented orchestrator behavior; first live run later).
