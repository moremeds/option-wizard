# Index Premium Selling — Design Spec

**Date:** 2026-06-09
**Author:** Brainstormed via /option-wizard session 2026-06-09
**Status:** Draft — awaiting trader review before transitioning to implementation plan
**Scope:** v0 (BSM-based backtest) + v1 (full framework); v2 captured in §13 backlog

---

## 1. Goal

Add to the `option-wizard` skill a Workflow 2 sub-flow ("2b: Index Premium
Selling") that recommends and prices three structures on US-equity index
underlyings:

1. **Cash-secured put (CSP)** on QQQ / SPY (SPX/NDX naked CSP refused —
   notional too large)
2. **Put diagonal calendar on RUT** (long 45DTE put + short 1-2DTE put)
   with three modes:
   - `calendar` (same strike) — vega-positive theta income, NEUTRAL vol
   - `protective` (short K < long K) — bearish bias, RICH vol
   - `aggressive` (short K > long K) — bullish bias, RICH vol, VIX < 25
3. **Entry-timing decision tree** (morning vs EOD) driven by VIX regime,
   premarket gap, dealer GEX state, 0DTE flow imbalance, and
   day-specific overrides (FOMC / Monday open / OPEX Friday)

Each recommendation lands as a preflight (hard rule #3) ready for IB
order submission.

The trader explicitly flagged that their entry-timing intuition is not
systematic; the framework's threshold defaults are v0 heuristics with
explicit provenance, calibrated via the backtest harness (§9) and an
audit log (§8).

## 2. Non-goals (v1)

- **No screener** — given a list of indices, "which is most attractive
  right now." Deferred to v2.
- **No multi-leg roll automation** — short leg daily roll is helper-only
  (`build_short_leg_roll`); trader confirms each roll preflight, not
  cron-scheduled.
- **No VIX options structures** (call calendar, put backspread) — VIX
  is its own beast; covered by Workflow 2a macro hedge.
- **No naked SPX/NDX CSP** — notional > $300k per contract refused on
  sizing grounds even when cash-covered.
- **No backtest v1/v2** (real historical chain mids + skew calibration)
  in this spec — v0 BSM-only backtest first; v1/v2 promoted only if
  v0 shows positive edge.

## 3. Architecture overview

Workflow 2 splits into 2a (existing macro hedge, unchanged) and 2b
(new index premium selling). Both share the 8-layer L0-L5 data spine
from `analysis-runbook.md`; only L6 (structure pick) and L7 (preflight)
diverge.

**New files:**

```
plugins/option-wizard/skills/option-wizard/
├── references/
│   └── index-premium-selling.md            (~320 lines)
├── scripts/
│   ├── diagonal_calendar.py                (~440 lines)
│   └── entry_timing.py                     (~310 lines)
└── tests/
    ├── test_diagonal_calendar.py           (~120 lines)
    └── test_entry_timing.py                (~100 lines)
```

**DEFERRED to v1.1:** `scripts/backtest_index_premium.py` + tests
(Pass-6 user decision: backtest is afterthought priority vs P0 pieces.
Build after N ≥ 10 real trades have outcomes to validate against.)

**Modified files:**

```
plugins/option-wizard/skills/option-wizard/
├── SKILL.md                                (routing table +1 row;
│                                            +1 script-invocation example;
│                                            +2 trigger phrases)
├── references/workflows-overview.md        (Workflow 2 split into 2a / 2b;
│                                            routing flowchart +1 branch)
└── references/strategies.md                (regime matrix +1 row;
                                              +1 CSP-on-index section;
                                              +1 put diagonal section)
```

## 4. Component 1 — Workflow 2 split (`workflows-overview.md`)

Existing Workflow 2 becomes **Workflow 2a: Index macro hedge** (verbatim,
no changes to its 8-layer substitutions).

**New Workflow 2b: Index premium selling.** Same 8-layer spine from
`analysis-runbook.md` with these substitutions:

| Layer | Difference from Workflow 1 |
|---|---|
| L0 | Compute net premium short notional vs NLV. > 25% → block new sells; surface as "cap reached" rather than recommend new structure |
| L1 | VRP label + IV rank for the underlying (QQQ / SPY / RUT); flag CHEAP vol → no sell |
| L2 | IV term curve across short-leg and long-leg DTEs (for diagonal). Contango deepening = vega-positive tailwind for calendar mode |
| L3 | TV: spot, 200DMA, RSI(14); used for directional bias only — never as primary trigger |
| L4 | UW flow_per_expiry on 0DTE chain → input to entry_timing.py |
| L5 | FOMC / CPI / NFP clock — abort if any major event within short-leg DTE |
| L6 | Pick structure from new regime matrix row (CSP / calendar / protective / aggressive); for RUT diagonal, regime_check warns on mismatch but does not abort |
| L7 | Preflight via `scripts.ib_order::build_preflight`; for diagonal, use `scripts.diagonal_calendar::build_diagonal_calendar` first to produce legs |
| L7+ | **Entry timing gate (new step)** — `scripts.entry_timing::decide(snapshot, mode)` → `enter_now` / `wait_eod` / `wait_minutes` / `abort`. Trader sees decision + reason before preflight YES/NO |

**Routing flowchart addition:**

```
├─ "QQQ CSP" / "SPY put" / "RUT diagonal" / "sell index premium"
│   └─ Workflow 2b (index premium selling)
├─ "SPX 大盘对冲" / "size spx hedge" → Workflow 2a (existing)
```

## 5. Component 2 — `strategies.md` additions

### 5.1 Regime × structure matrix — new row

|             | Bullish                        | Neutral                                | Bearish                              |
|-------------|--------------------------------|----------------------------------------|--------------------------------------|
| **Index premium sell** | QQQ/SPY CSP (IV rank ≥ 20 + VRP ≠ CHEAP); RUT diagonal aggressive mode (VIX < 25 hard limit) | RUT diagonal calendar mode; QQQ bull put spread | RUT diagonal protective mode |

### 5.2 New section: CSP on index ETF (QQQ / SPY / IWM)

- **Legs:** short 1 OTM put + cash = strike × 100
- **Entry condition:** `IV rank ≥ 20 AND VRP ∈ {NEUTRAL, RICH}` (lower IV
  rank threshold than single-name CSP justified by VRP being the core
  risk premium on indices, not idio)
- **DTE:** 30-45
- **Δ target:** 0.20-0.30 (more OTM than single-name due to fatter index
  tail)
- **Strike anchor:** put wall from `scripts.gex_levels::compute_levels`
  (not 200DMA)
- **Sizing:** single contract notional ≤ 5% NLV; total index CSP
  notional ≤ 25% NLV
- **Refused:** SPX naked CSP (notional too large), IWM when bid-ask >
  $0.10 (use RUT options instead)

### 5.3 New section: Put diagonal calendar on RUT — three modes

All modes: long 45DTE put @ Kl + short 1-2DTE put @ Ks. Max loss at
short-leg expiry =`max((Ks − Kl) × 100, 0) − net credit` (calendar
mode collapses to long put extrinsic decay).

| Mode | Strike layout (Ks selection) | Long Δ | Regime fit | Greeks character |
|---|---|---|---|---|
| **calendar** | Ks = Kl (same strike, NOT same Δ — different DTEs at same Δ give different K) | 0.30 | NEUTRAL vol + expected IV term contango deepening | θ+, ν+, γ ~ 0 |
| **protective** | Ks = Kl × (1 − 0.025) (2.5% below long strike — Δ-based picking fails at 1-2 DTE because 1DTE 0.15Δ K ≈ 1.5% OTM > 45DTE 0.30Δ K ≈ 5% OTM) | 0.30 | bearish bias + RICH vol | θ+, ν+, Δ slightly negative |
| **aggressive** | Ks picked by short Δ = 0.30 (1DTE 0.30Δ K ≈ 1.5% OTM > 45DTE 0.15Δ K ≈ 9% OTM, so Ks > Kl naturally) | 0.15 | bullish RICH vol; VIX < 25 hard limit | θ++, ν+, Δ slightly positive |

**Roll rule:** short leg rolled at expiry-day −1h to next 1-2DTE same
mode strike. Every 7 rolls (≈2 weeks) re-check long leg DTE; if < 21
DTE remaining, close long leg (hard rule #4) and reopen full structure
with fresh 45DTE long.

**Mode-drift recovery:** calendar mode short leg drifts ITM by ≥ 1
listed strike width (RUT typically $5 spacing for $2k+ underlying) →
switch to protective mode on next roll (defined-risk preserved, P/L
slightly capped but max loss tightened).

## 6. Component 3 — `references/index-premium-selling.md`

8-section deep reference parallel to `fcn-framework.md` / `aq-dq-framework.md`.
~320 lines.

| § | Title | Lines | Content |
|---|---|---:|---|
| 1 | When to use | 25 | Trigger phrases (CN + EN); Workflow 2a vs 2b boundary; non-goals reiterated |
| 2 | Source discipline (index-specific) | 30 | UW: IV rank / VRP / GEX / 0DTE flow / max pain. TV: spot / SMA / RSI / VIX & VIX1D & VIX9D term. IB: chain mid (live-trade mode) + buying power check |
| 3 | CSP on index ETF | 40 | Same content as §5.2 above + worked checklist (entry gate, Δ pick, sizing math) |
| 4 | RUT put diagonal — three modes | 60 | Same content as §5.3 + max loss derivation per mode + when to abandon each mode (e.g., aggressive aborts on VIX > 25, calendar warns on RICH vol) |
| 5 | **Entry timing decision tree** | 70 | 5-step tree (VIX gate → premarket gap → GEX state → 0DTE flow → mode-specific window) + day-specific overrides (FOMC / Monday open / OPEX Friday) + v0 threshold table with provenance per row |
| 6 | Roll & exit rules | 35 | Short-leg daily roll cadence; long-leg 21 DTE forced close; mode-drift recovery; TP 50% / SL 2× credit standard bracket; per-mode P/L exit conditions |
| 7 | Book-level risk monitoring | 30 | Vega aggregation across calendar positions (long-leg vega is implicit long-vol bet); net Δ contribution; overlap with Workflow 2a macro hedge book |
| 8 | Worked examples | 30 | 4 synthetic-data examples: QQQ CSP / RUT calendar / RUT protective / RUT aggressive, each with snapshot → preflight |

### 6.1 §5 Entry timing decision tree — full text

```
1. VIX gate
   - VIX1D > VIX > 18 AND VIX1D / VIX9D > 1.05 (frontend backwardation)
     → ABORT (event-driven volatility, do not sell short-dated premium)
   - VIX < 12 AND VRP = CHEAP
     → ABORT (no risk premium to capture)

2. Premarket gap (09:15 ET, ES/NQ futures)
   - |gap %| > 1.0% (QQQ/SPY) or > 1.5% (RUT)
     → WAIT 30 min, re-evaluate from step 3

3. Dealer GEX state (UW get_greek_exposure_by_strike)
   - Net dealer GEX < 0 AND |gamma_flip − spot| / spot < 1%
     → WAIT_EOD (short gamma + flip proximity, positioning unstable)
   - Net dealer GEX > 0 → continue (long gamma environment, vol self-suppressing)

4. 0DTE flow (UW get_flow_per_expiry on same-day expiry)
   - put_premium / call_premium > 3.0 (whale put-buyer ratio)
     → WAIT (large put protection bid, follow-on could hammer short put)

5. Mode-specific entry window
   - QQQ/SPY CSP (30-45 DTE)        → morning 09:45-10:30 ET
   - RUT calendar mode               → EOD 15:30-15:55 ET
   - RUT protective mode             → morning 09:45-10:30 ET
   - RUT aggressive mode             → EOD 15:30-15:55 ET only

Day-specific overrides (priority above all above)
   - FOMC presser day (pre-14:00 ET): WAIT until 14:30 ET
   - Monday open: WAIT 30 min (weekend gamma unwind)
   - OPEX Friday afternoon: favor EOD + anchor short strike to max pain
```

### 6.2 v0 threshold table

| Threshold | v0 default | Provenance / tuning direction |
|---|---|---|
| `vix_abort_high` | 18 | CBOE historical median for backwardation; trader who sells in VIX 20+ regularly can raise to 22 |
| `vix_event_ratio` | 1.05 | Buffer above 1.0 to skip noise-driven backwardation |
| `vix_abort_low` | 12 | VIX 5th percentile historically; below this, $0.30 credit < IB commission |
| `gap_wait_pct` | 0.010 (QQQ/SPY) | ≈ 40% of 1 ATR for index ETFs |
| `gap_wait_pct_rut` | 0.015 | RUT intraday range higher than SPX/QQQ |
| `gex_flip_proximity` | 0.010 | Spotgamma / Tier1Alpha published "danger zone" range |
| `odte_put_buyer_ratio` | 3.0 | First-draft heuristic; calibrate by running paired backtests (gate ON vs OFF) and stratifying trade lists in jupyter (v0 doesn't auto-attribute — see §9) |
| `aggressive_mode_vix_cap` | 25 | VIX 25 ≈ RUT 1d expected move 1.6%, where short ATM 1DTE EV turns negative |

All thresholds live in `THRESHOLDS` dict at top of
`scripts/entry_timing.py` for tuning.

## 7. Component 4 — `scripts/diagonal_calendar.py`

Pure-function module parallel to `macro_hedge.py`. Reuses
`scripts._market::read_chain_mid` / `nearest_expiry_to_tenor` /
`chain_leg_provenance` / `fallback_provenance` so chain-vs-BSM
fallback + provenance taxonomy is consistent across the skill.

### 7.1 Main entry

```python
from typing import Literal

def build_diagonal_calendar(
    spot: float,
    mode: Literal['calendar', 'protective', 'aggressive'],
    snapshot: dict,
    dte_long: int = 45,
    dte_short: int = 1,
    target_deltas: dict | None = None,
    qty: int = 1,
    underlying: str = "RUT",
) -> dict
```

**Default `target_deltas` per mode:**
- `calendar`: `{long: 0.30, short: 0.30}`
- `protective`: `{long: 0.30, short: 0.15}`
- `aggressive`: `{long: 0.15, short: 0.30}`

**Required `snapshot` fields:**
- `iv_atm_short` — ATM IV at short-leg expiry (chain-derived or UW
  interpolated)
- `iv_atm_long` — ATM IV at long-leg expiry
- `iv_rank` (0-100) — for regime_check
- `vrp_label` ∈ `{RICH, NEUTRAL, CHEAP}` — for regime_check

**Optional `snapshot` fields (chain path):**
- `chain` — keyed `{expiry_iso: {strike_pct: {right: {mid, iv}}}}`
- `chain_source` ∈ `{UW, IB}`
- `chain_timestamps` — `{expiry_iso: iso_timestamp}`
- `spot_timestamp` — iso_timestamp

### 7.2 Return shape

```python
{
    'underlying': 'RUT',
    'mode': 'calendar',
    'spot': 2300.0,
    'dte_long': 45, 'dte_short': 1,
    'legs': [
        {'right': 'put', 'action': 'buy',  'strike': 2280.0, 'qty': 1,
         'limit_price': 18.50, 'mid_source': 'UW',
         'mid_provenance': {...}, 'greeks': {'delta', 'gamma', 'theta', 'vega'}},
        {'right': 'put', 'action': 'sell', 'strike': 2280.0, 'qty': 1,
         'limit_price': 4.20,  ...},
    ],
    'net_debit_dollar': 1430.0,           # >0 = net debit, <0 = net credit
    'max_loss_dollar': 1430.0,            # holding through short expiry (formula §10 #1)
    'breakevens_at_short_expiry': {       # diagonal P/L is non-monotonic in S —
        'lower': 2180.0, 'upper': 2410.0, # two BEs bracket a profit zone.
    },                                    # Either may be None if no BE on that side.
    # NOTE (v1 backlog): max_gain_dollar_at_pin + net_greeks_at_short_expiry_pinned
    # deferred to v2; trader can read these from the roll_matrix middle row for now.
    'net_greeks_entry': {'delta': -0.05, 'gamma': 0.001,
                         'theta_daily': 12.50, 'vega': 8.20},
    'roll_matrix': [                       # P/L if close all at short expiry
        {'spot_scenario': -0.10, 'spot_at_expiry': 2070.0,
         'short_put_pl': 1200.0, 'long_put_mark': 850.0, 'net_pl': 1850.0},
        {'spot_scenario': -0.05, ...},
        {'spot_scenario': -0.02, ...},
        {'spot_scenario':  0.00, ...},
        {'spot_scenario': +0.02, ...},
        {'spot_scenario': +0.05, ...},
        {'spot_scenario': +0.10, ...},
    ],
    'pricing_source': 'chain',             # 'chain' | 'mixed' | 'bsm'
    'regime_check': {
        'recommended_mode_for_regime': 'protective',
        'matches_chosen_mode': False,
        'warning': 'VRP=RICH + bearish bias suggests protective; '
                   'chose calendar — proceeds but accept lower expected edge',
    },
}
```

### 7.3 Strike selection by Δ (closed-form BSM inversion)

For a put: `|Δ_put| = N(-d1)`. Solving for strike at target |Δ| = τ:

```python
def _strike_for_put_delta(spot, target_abs, t_years, iv, r=0.04):
    z = norm.ppf(target_abs)                          # negative for τ < 0.5
    return spot * math.exp((r + 0.5 * iv**2) * t_years + iv * math.sqrt(t_years) * z)
```

Where chain is present, snap target strike to nearest listed strike and
re-read mid (more accurate than BSM mid).

### 7.4 Short-leg roll helper

```python
def build_short_leg_roll(
    existing_position: dict,
    new_dte_short: int,
    snapshot: dict,
) -> dict:
    """Returns close-old + open-new legs, net credit, long-leg DTE
    remaining, action_required ∈
    {'roll_short', 'close_all_long_dte_too_short', 'switch_mode'}.
    Called daily at expiry-day −1h."""
```

## 8. Component 5 — `scripts/entry_timing.py`

### 8.1 Threshold dict (top of file)

```python
THRESHOLDS = {
    'vix_abort_high': 18, 'vix_event_ratio': 1.05,
    'vix_abort_low': 12,
    'gap_wait_pct': 0.010, 'gap_wait_pct_rut': 0.015,
    'gex_flip_proximity': 0.010,
    'odte_put_buyer_ratio': 3.0,
    'aggressive_mode_vix_cap': 25,
}
```

### 8.2 Main entry

```python
def decide(snapshot: dict, mode: str) -> dict:
    """
    snapshot fields:
      spot, time_et, vix, vix1d, vix9d, premarket_gap,
      gex_flip, net_dealer_gex, odte_put_premium, odte_call_premium,
      is_fomc_day, is_monday_open, is_opex_friday
    Returns:
      {action: 'enter_now' | 'wait_eod' | 'wait_minutes' | 'abort',
       reason: str, triggered_threshold: str, retry_at_iso: str | None}
    Side effect: appends a JSONL line to
    references/private/market/entry-timing-log.jsonl
    """

def calibrate(log_path: str | None = None) -> dict:
    """Walks entry-timing-log.jsonl, returns per-threshold fire rate
    and tuning direction. Use after N >= 10 decisions logged."""
```

### 8.3 CLI

```bash
.venv/bin/python -m scripts.entry_timing --decide --snapshot snap.json --mode csp
.venv/bin/python -m scripts.entry_timing --calibrate
```

### 8.4 Audit log line shape

```json
{
  "timestamp": "2026-06-09T13:42:00Z",
  "mode": "rut_calendar",
  "snapshot_hash": "abc123...",
  "decision": "wait_eod",
  "triggered_threshold": "gex_flip_proximity",
  "snapshot_summary": {
    "spot": 2300.0, "vix": 14.2, "vix1d": 13.8,
    "premarket_gap": 0.003, "net_dealer_gex": -1.2e9,
    "gex_flip": 2295.0, "is_fomc_day": false
  }
}
```

## 9. Component 6 — Backtest harness — DEFERRED to v1.1

**Status:** Originally specified `scripts/backtest_index_premium.py`. Cut
from v1 scope per Pass-6 user decision ("backtesting is not most important
part"). Rationale: with zero live trades yet, BSM-on-synthetic-data
backtest results carry near-zero weight in actual decisions; defer to
v1.1 when N ≥ 10 real trades have outcomes that can validate the harness.

**v1.1 design (deferred):**

- Paired-trade attribution: each entry day simulates both gate-on and
  gate-off arms in parallel with independent position tracking,
  eliminating the schedule-coupling bias that Pass-2 codex flagged
- Real historical chain mids via UW `get_historic_chains` (BSM
  fallback for missing strikes)
- Automated statistics with proper design: per-trade Sharpe annualization
  using actual `days_held` mean, equity-curve-normalized max_dd
  (not P/L-peak division), survivorship-bias-free regime stratification
- Out-of-sample chronological split with explicit overfit detection

**v1 calibration workflow (without backtest):** Trader runs live trades
with current threshold defaults; `entry_timing --calibrate` aggregates
the JSONL audit log to surface which thresholds fire (over-tightening
wastes signal) vs which never fire (over-loosening catches nothing).
This is sufficient for tuning the 8 threshold defaults given the audit
log accumulates ~3-5 entries per trading day.

## 10. Hard rules + invariants

This sub-flow does not introduce new hard rules; existing SKILL.md
hard rules apply with these specific instantiations:

- **#1 defined risk:** all three diagonal modes have bounded max loss
  at short expiry (close-everything; do NOT take assignment):
  - calendar (Ks = Kl) and protective (Ks < Kl): max loss = net_debit
    (worst case S >> Kl, both legs decay to zero; the width term
    Kl − Ks does NOT add to max loss in protective — when S < Ks both
    legs are ITM and offset dollar-for-dollar in the [Ks, Kl] range)
  - aggressive (Ks > Kl): max loss = (Ks − Kl) × 100 + net_debit
    (worst case S → 0, long ITM by Kl but short ITM by Ks, diff is Ks − Kl)
  - Sign convention: net_debit > 0 = paid, net_debit < 0 = received credit.
  - CSP cash-secured by §5.2 sizing rule.
- **#2 source discipline:** spot from TV / IB; IV rank, GEX, 0DTE flow
  from UW; chain mid from IB (live trade) or UW (analytical) with
  `pricing_source` provenance tag.
- **#3 preflight:** `build_diagonal_calendar` output feeds
  `scripts.ib_order::build_preflight` which assembles the full preflight
  (legs / mids / max loss / P/L matrix / brackets / regime check / catalyst).
- **#4 21 DTE:** long leg 21 DTE check enforced in `build_short_leg_roll`
  return field `action_required = 'close_all_long_dte_too_short'`.
- **#5 PB products:** N/A (listed options only, route through IB).
- **#6 brackets:** TP 50% of net credit (CSP) or net debit (diagonal,
  on long leg mark), SL 2× credit / 100% of max loss for spreads.
- **#7 freshness:** snapshot timestamps required;
  `entry_timing.decide` rejects snapshots with `time_et` more than 15 min
  stale.
- **#8 layer coverage table:** Workflow 2b inherits Workflow 1's
  requirement to open with the Layer Coverage table.
- **#9 source separation:** backtest output goes to `references/private/market/`
  with `structures: [csp, diagonal_calendar]` tags; reviewed via
  Workflow 6 weekly retrospective.

## 11. Testing plan

| Test file | Coverage |
|---|---|
| `test_diagonal_calendar.py` | (a) BSM path matches chain path within 10% when both available; (b) `regime_check` warns correctly on mismatched mode; (c) max_loss formula per mode INCLUDING discount-carry on long put at S→0; (d) `roll_matrix` shape — assert sign-change count ≤ 2 across 7 scenarios (diagonal P/L is non-monotonic); (e) short-leg roll triggers `close_all_long_dte_too_short` at correct DTE; (f) chain-path consumes provided greeks when chain leg includes them (no recompute) |
| `test_entry_timing.py` | (a) each of 5 decision-tree branches fires with synthetic snapshot; (b) day-specific overrides take priority including OPEX Friday; (c) freshness gate rejects snapshots > 15 min stale; (d) audit log line includes valid `snapshot_hash` (SHA-256 of canonical-ordered summary); (e) `calibrate` reports never-fired thresholds with tuning hint; (f) calibrate aggregates correctly across N>10 entries |

Existing `scripts/_market.py` chain/provenance helpers are reused —
their existing tests cover the chain key 4-decimal rounding edge case
already.

## 12. Rollout / phase plan

| Phase | Deliverables | Days |
|---|---|---|
| **P0 — Docs only** | `workflows-overview.md` split; `strategies.md` row + 2 sections; SKILL.md routing | 0.5 |
| **P1 — Diagonal calendar pricer** | `diagonal_calendar.py` + tests; can be called manually with hand-built snapshots | 1.5 |
| **P2 — Entry timing decision tree** | `entry_timing.py` + tests + audit log | 1.0 |
| **P3 — Deep reference doc** | `references/index-premium-selling.md` 8 sections | 0.5 |
| **P4 — DEFERRED to v1.1** | `backtest_index_premium.py` cut from v1 scope. v1 calibration loop relies on `entry_timing --calibrate` audit-log aggregation against real trades | 0d (deferred) |
| **P5 — Threshold calibration via audit log** | After N ≥ 10 live trades have been logged via `entry_timing.decide()`, run `--calibrate` to see fire rates per threshold; tune `THRESHOLDS` dict; document tuning in `references/private/market/` | 0.5 |

**Total:** ~4 working days (was ~6d with backtest in v1).

Phases run in this order in a single branch
(`feature/index-premium-selling`) with one commit per phase. Each
phase ends with `.venv/bin/pytest tests/test_<phase>.py` passing.

## 13. Open questions / v2 backlog

- **Backtest v1 — Stats + real chains**: re-introduce automated
  statistics (Sharpe, max_dd, win_rate, regime stratification) with
  PROPER design: paired-trade attribution (each entry day simulates
  both gate-on and gate-off arms in parallel with independent position
  tracking), equity-curve-normalized max_dd (not P/L-peak division),
  and per-trade Sharpe annualization using actual `days_held` mean.
  Also: replace BSM-priced legs with `get_historic_chains` real mids;
  pull `atm_iv_1d` for proper short-leg pricing. Decide after v0 raw
  data inspection — promote if directional inspection suggests positive
  edge, drop strategy if total dollar P/L < $0 OOS.
- **Backtest v2 — Skew calibration**: from UW historical 25Δ skew
  series; reduces BSM bias on short-dated ATM legs further.
- **Backtest v3 — Intraday simulation**: per-window (morning vs EOD)
  simulation requires intraday IV / spot snapshots. Without this,
  trader's "早盘 vs 尾盘" question cannot be answered by backtest.
- **Screener (v2)**: given a list of underlyings (QQQ / SPY / RUT /
  IWM / XLK), rank by current sell-premium attractiveness (IV rank +
  VRP + dealer GEX + catalyst clock combined).
- **VIX options income overlay**: VIX call calendar or put backspread
  as a separate premium-selling subflow. Deferred — VIX has its own
  vol-of-vol behavior that doesn't fit this framework cleanly.
- **0DTE-only sub-mode**: pure 0DTE CSP / put credit spread on SPY for
  intraday gamma scalping. Excluded from v1 because the entry-timing
  decision tree assumes the trade has overnight component.
- **Multi-broker support**: Futu RUT options if/when supported by
  `portfolio-analyser` CLI. Currently IB-only.
- **Auto-roll cron**: short-leg daily roll automation (currently
  trader-confirmed each day). Requires hard rule extension for
  unattended order submission — deferred indefinitely.

## 14. Acceptance criteria

This spec is implementation-ready when:

- [x] Workflow 2 split (2a / 2b) approved
- [x] Three RUT diagonal modes (calendar / protective / aggressive) approved
- [x] IV rank ≥ 20 + VRP ≠ CHEAP entry gate for index CSP approved
- [x] Entry-timing decision tree shape approved (5-step + day-specific)
- [x] v0 threshold defaults marked first-draft heuristic (not trader preference)
- [x] **Backtest harness DEFERRED to v1.1** (Pass-6 user decision —
      not most important; threshold calibration uses live audit log instead)
- [x] Entry-timing 4 gaps closed in v1: OPEX Friday override, freshness
      check (≤ 15 min stale), snapshot_hash in audit log, calibrate
      reports never-fired thresholds
- [x] Diagonal calendar 3 gaps closed in v1: max_loss discount-carry term,
      chain-path consumes provided greeks (no recompute), roll-matrix
      non-monotonic-shape test
- [x] All defined-risk modes verified bounded max loss
- [ ] Trader review of this written spec
- [ ] Implementation plan written via `superpowers:writing-plans`
