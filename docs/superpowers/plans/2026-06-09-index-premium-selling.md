# Index Premium Selling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Workflow 2b "Index Premium Selling" to option-wizard skill: CSP on QQQ/SPY, RUT put diagonal calendar (3 modes), entry-timing decision tree. Backtest harness DEFERRED to v1.1 (Pass-6 user decision: not most important; build after N ≥ 10 real trades have outcomes to validate against).

**Architecture:** Workflow 2 splits into 2a (existing macro hedge, unchanged) + 2b (new). Two new scripts (`diagonal_calendar.py`, `entry_timing.py`) reuse `scripts/_market.py` chain/provenance helpers and follow `scripts/macro_hedge.py` BSM-vs-chain fallback pattern. One new deep-reference doc (`references/index-premium-selling.md`). Three existing docs updated (`SKILL.md`, `workflows-overview.md`, `strategies.md`).

**Tech Stack:** Python 3.13, `uv` for venv, `pytest` for tests, `scipy.stats.norm` for BSM, existing `scripts/_market.py` for chain provenance.

**Spec:** `docs/superpowers/specs/2026-06-09-index-premium-selling-design.md`

**Branch:** `feature/index-premium-selling`

**Canonical file paths:** Skill source lives at `/Users/chenxi/projects/option-wizard/plugins/option-wizard/skills/option-wizard/`. `~/.claude/skills/option-wizard` is a symlink — edit the canonical path. Tests live at `/Users/chenxi/projects/option-wizard/tests/` (project root, flat).

---

## File Structure

**New files:**

| Path | Responsibility |
|---|---|
| `plugins/option-wizard/skills/option-wizard/references/index-premium-selling.md` | 8-section deep reference; entry-timing decision tree + threshold table |
| `plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py` | Pure-function module — three-mode strike selection, leg construction, Greeks, roll matrix, regime check, chain-vs-BSM fallback |
| `plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py` | Decision tree `decide(snapshot, mode)` + JSONL audit log + `calibrate()` CLI |
| `tests/test_diagonal_calendar.py` | Pricer correctness, regime check, roll matrix non-monotonic shape, short-leg roll |
| `tests/test_entry_timing.py` | Each decision-tree branch fires; day-override priority; freshness gate; audit log JSONL valid (with snapshot_hash); calibrate reports never-fired thresholds |

**Modified files:**

| Path | Change |
|---|---|
| `plugins/option-wizard/skills/option-wizard/SKILL.md` | +1 routing table row, +2 trigger phrases, +1 script-invocation example |
| `plugins/option-wizard/skills/option-wizard/references/workflows-overview.md` | Split Workflow 2 into 2a (existing) + 2b (new); routing flowchart +1 branch |
| `plugins/option-wizard/skills/option-wizard/references/strategies.md` | Regime matrix +1 row (Index premium sell); +1 CSP-on-index section; +1 put diagonal section |

---

## Pre-flight (one-time setup)

- [ ] **Step 0.1: Create branch from main**

```bash
cd /Users/chenxi/projects/option-wizard
git checkout main && git pull
git checkout -b feature/index-premium-selling
```

Expected: switched to new branch.

- [ ] **Step 0.2: Verify test infrastructure works on a known-passing test**

```bash
cd /Users/chenxi/projects/option-wizard
.venv/bin/pytest tests/test_macro_hedge.py -v
```

Expected: all tests pass. If they don't, stop and resolve before proceeding.

---

## Phase A — Docs spine (3 tasks, no code)

### Task 1: Split Workflow 2 into 2a / 2b in workflows-overview.md

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/references/workflows-overview.md`

- [ ] **Step 1.1: Read current Workflow 2 section**

```bash
sed -n '41,55p' plugins/option-wizard/skills/option-wizard/references/workflows-overview.md
```

Expected: see existing Workflow 2 macro hedge table. This is the verbatim content for "2a".

- [ ] **Step 1.2: Rename Workflow 2 heading to 2a and add 2b section**

Edit `plugins/option-wizard/skills/option-wizard/references/workflows-overview.md` line 41:

Change `## Workflow 2 — 分析指数/大盘 (SPY / QQQ / SPX / IWM macro view)` to `## Workflow 2a — 分析指数/大盘 macro hedge (SPY / QQQ / SPX / IWM)`.

Then append after the existing Workflow 2 block (before `## Workflow 3 — ...`):

```markdown
---

## Workflow 2b — Index premium selling (QQQ/SPY CSP + RUT put diagonal)

**Spine:** same 8-layer `analysis-runbook.md` data pull (L0-L5 shared with Workflow 2a) with these L6-L7 substitutions:

| Layer | Difference from Workflow 1 |
|---|---|
| L0 | Compute net premium short notional vs NLV. > 25% → block new sells; surface as "cap reached" rather than recommend new structure |
| L1 | VRP label + IV rank for underlying (QQQ / SPY / RUT); CHEAP vol → no sell |
| L2 | IV term curve across short-leg and long-leg DTEs (diagonal). Contango deepening = vega-positive tailwind for calendar mode |
| L3 | TV: spot, 200DMA, RSI(14); directional bias only — never primary trigger |
| L4 | UW `flow_per_expiry` on 0DTE chain → input to `entry_timing.py` |
| L5 | FOMC / CPI / NFP clock — abort if major event within short-leg DTE |
| L6 | Pick structure from `strategies.md` regime matrix "Index premium sell" row; for RUT diagonal, regime_check warns on mode mismatch but does not abort |
| L7 | Preflight via `scripts.ib_order::build_preflight`; for diagonal, call `scripts.diagonal_calendar::build_diagonal_calendar` first to produce legs |
| L7+ | **Entry timing gate (new step)** — `scripts.entry_timing::decide(snapshot, mode)` returns `enter_now` / `wait_eod` / `wait_minutes` / `abort`. Show decision + reason BEFORE preflight YES/NO |

**Output:** preflight ready for IB submission, OR explicit "wait until X" / "abort because Y" with reason.
```

- [ ] **Step 1.3: Update routing flowchart at end of workflows-overview.md**

In the `## Routing decision flowchart` code block (around line 207), find the existing `├─ "SPX 大盘对冲"` line and replace with:

```
├─ "SPX 大盘对冲" / "size spx hedge" → Workflow 2a (L0 trigger + L7 macro hedge)
├─ "QQQ CSP" / "SPY put" / "RUT diagonal" / "sell index premium" → Workflow 2b
```

- [ ] **Step 1.4: Verify markdown renders**

```bash
grep -n "Workflow 2" plugins/option-wizard/skills/option-wizard/references/workflows-overview.md
```

Expected: see `## Workflow 2a` and `## Workflow 2b` headings, plus routing flowchart references to 2a and 2b.

- [ ] **Step 1.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/workflows-overview.md
git commit -m "docs(workflows): split Workflow 2 into 2a (macro hedge) and 2b (premium selling)"
```

---

### Task 2: Add regime row + CSP and diagonal sections to strategies.md

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/references/strategies.md`

- [ ] **Step 2.1: Add new row to regime × structure matrix**

Edit lines 9-13 (the matrix table). Add row after CHEAP vol:

```markdown
| **Index premium sell** (QQQ / SPY / RUT only) | QQQ/SPY CSP (IV rank ≥ 20 + VRP ≠ CHEAP); RUT diagonal aggressive mode (VIX < 25 hard limit) | RUT diagonal calendar mode; QQQ bull put spread | RUT diagonal protective mode |
```

- [ ] **Step 2.2: Add CSP-on-index ETF section after existing CSP section (around line 41)**

Insert after the existing `### Cash-secured put (CSP)` block:

```markdown
### Cash-secured put on index ETF (QQQ / SPY / IWM)

- **Legs:** Short 1 OTM put + cash reserve = strike × 100.
- **Entry condition:** `IV rank ≥ 20 AND VRP ∈ {NEUTRAL, RICH}`. The
  lower threshold than single-name CSP (≥ 50) is justified because the
  sell-premium edge on indices is the VRP risk premium, not idio compensation.
- **DTE:** 30-45.
- **Δ target:** 0.20-0.30 (more OTM than single-name due to fatter index
  tail).
- **Strike anchor:** put wall from `scripts.gex_levels::compute_levels`
  (not 200DMA).
- **Sizing:** Single contract notional ≤ 5% NLV; total index CSP
  notional ≤ 25% NLV.
- **Refused:** SPX naked CSP (notional > $300k per contract); IWM when
  bid-ask > $0.10 (use RUT options instead).
```

- [ ] **Step 2.3: Add put diagonal calendar section after iron condor section (around line 70)**

Insert after `### Iron condor` block:

```markdown
### Put diagonal calendar (RUT — three modes)

All modes: long 45DTE put @ Kl + short 1-2DTE put @ Ks. Max loss at
short-leg expiry = `max((Ks − Kl) × 100, 0) − net credit` (calendar
mode collapses to long put extrinsic decay).

| Mode | Strike layout | Default Δ | Regime fit | Greeks |
|---|---|---|---|---|
| **calendar** | Ks = Kl | both 0.30 | NEUTRAL vol + expected IV term contango deepening | θ+, ν+, γ ~ 0 |
| **protective** | Ks < Kl | Kl 0.30, Ks 0.15 | bearish bias + RICH vol | θ+, ν+, Δ slightly negative |
| **aggressive** | Ks > Kl | Ks 0.30, Kl 0.15 | bullish RICH vol; VIX < 25 hard limit | θ++, ν+, Δ slightly positive |

- **Roll rule:** Short leg rolled at expiry-day −1h to next 1-2DTE
  same-mode strike. Every 7 rolls (≈ 2 weeks) re-check long leg DTE; if
  < 21 DTE, close long leg (hard rule #4) and reopen full structure with
  fresh 45DTE long.
- **Mode-drift recovery:** Calendar mode short leg drifts ITM by ≥ 1
  listed strike width (RUT typically $5) → switch to protective mode on
  next roll.
- **Pricer:** `scripts.diagonal_calendar::build_diagonal_calendar(spot,
  mode, snapshot, ...)`.
```

- [ ] **Step 2.4: Verify additions**

```bash
grep -n "Index premium sell\|Cash-secured put on index ETF\|Put diagonal calendar" plugins/option-wizard/skills/option-wizard/references/strategies.md
```

Expected: 3 matches, each on a distinct line.

- [ ] **Step 2.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/strategies.md
git commit -m "docs(strategies): add index premium sell regime row + CSP-on-index + put diagonal sections"
```

---

### Task 3: Update SKILL.md routing + triggers

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/SKILL.md`

- [ ] **Step 3.1: Add trigger phrases**

Find the `## Triggers` section. In the Chinese trigger list, add after the existing `"<TICKER> 怎么做 sell put / covered call / jade lizard"` line:

```
- "QQQ CSP" / "SPY 卖 put" / "RUT diagonal" / "卖 index premium"
```

In the English trigger list, add after `"size spx hedge"`:

```
- "qqq csp" / "spy put" / "rut diagonal" / "sell index premium"
```

- [ ] **Step 3.2: Add routing table row**

In the `## When to read which file` routing table, add row before the "Honest gap reporting" row:

```markdown
| Index premium selling (QQQ/SPY CSP or RUT put diagonal) | `references/index-premium-selling.md`; `scripts.diagonal_calendar::build_diagonal_calendar` for RUT 3-mode structures; `scripts.entry_timing::decide` for morning-vs-EOD; CSP uses `scripts.ib_order::build_preflight` directly. Threshold calibration via `scripts.entry_timing::calibrate` reading the audit log |
```

- [ ] **Step 3.3: Add script-invocation example**

In the `## How to invoke scripts` section, add a new code block after the macro hedge chain-path example:

```python
# Diagonal calendar (RUT 3-mode pricer with chain-vs-BSM fallback)
.venv/bin/python -c '
from scripts.diagonal_calendar import build_diagonal_calendar
snap = {"iv_atm_short": 0.28, "iv_atm_long": 0.30,
        "iv_rank": 35, "vrp_label": "NEUTRAL"}
out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=snap)
print(out["mode"], out["net_debit_dollar"], out["regime_check"]["matches_chosen_mode"])
for leg in out["legs"]:
    print(leg["action"], leg["strike"], leg["limit_price"], leg["mid_source"])
print("roll matrix at -5%:", [r for r in out["roll_matrix"] if r["spot_scenario"] == -0.05])
'

# Entry timing decision (morning vs EOD vs abort)
.venv/bin/python -c '
from scripts.entry_timing import decide
snap = {"spot": 2300.0, "time_et": "10:00", "vix": 14.2, "vix1d": 13.8, "vix9d": 14.0,
        "premarket_gap": 0.003, "gex_flip": 2295.0, "net_dealer_gex": -1.2e9,
        "odte_put_premium": 5.0e6, "odte_call_premium": 4.0e6,
        "is_fomc_day": False, "is_monday_open": False, "is_opex_friday": False}
print(decide(snap, mode="rut_calendar"))
'
```

- [ ] **Step 3.4: Verify SKILL.md still parses**

```bash
.venv/bin/python -c "import yaml; print(open('plugins/option-wizard/skills/option-wizard/SKILL.md').read().count('|'))"
```

Expected: count > 200 (just a non-zero sanity that file is readable; no parse errors).

- [ ] **Step 3.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/SKILL.md
git commit -m "docs(skill): wire Workflow 2b triggers + routing + script examples"
```

---

## Phase B — `scripts/diagonal_calendar.py` (6 tasks, TDD)

### Task 4: Scaffold module + BSM Greeks + strike selection

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py`
- Create: `tests/test_diagonal_calendar.py`

- [ ] **Step 4.1: Write failing test for BSM Greeks**

Create `tests/test_diagonal_calendar.py`:

```python
"""Tests for scripts.diagonal_calendar."""

import math

import pytest

from scripts.diagonal_calendar import (
    _bs_put_greeks,
    _strike_for_put_delta,
)


def test_bs_put_greeks_atm():
    """ATM put: delta near -0.5, positive gamma + vega, negative theta."""
    g = _bs_put_greeks(spot=2300.0, strike=2300.0, t_years=45 / 365, r=0.04, sigma=0.28)
    assert -0.55 < g["delta"] < -0.40, f"ATM put delta ≈ -0.5, got {g['delta']}"
    assert g["gamma"] > 0
    assert g["vega"] > 0
    assert g["theta"] < 0  # long put loses theta


def test_bs_put_greeks_deep_otm():
    """Deep OTM put: small delta magnitude."""
    g = _bs_put_greeks(spot=2300.0, strike=2070.0, t_years=45 / 365, r=0.04, sigma=0.28)
    assert -0.20 < g["delta"] < 0


def test_strike_for_put_delta_round_trip():
    """Pick strike for target |Δ| = 0.30 then check Greeks deliver that delta."""
    spot, t, iv = 2300.0, 45 / 365, 0.28
    strike = _strike_for_put_delta(spot=spot, target_abs=0.30, t_years=t, iv=iv)
    assert strike < spot, "30Δ put strike must be OTM (below spot)"
    g = _bs_put_greeks(spot=spot, strike=strike, t_years=t, r=0.04, sigma=iv)
    assert abs(abs(g["delta"]) - 0.30) < 0.01
```

- [ ] **Step 4.2: Run test to verify it fails**

```bash
cd /Users/chenxi/projects/option-wizard
.venv/bin/pytest tests/test_diagonal_calendar.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.diagonal_calendar'` (or `ImportError`).

- [ ] **Step 4.3: Implement scaffold + Greeks + strike selection**

Create `plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py`:

```python
"""Build long-45DTE put + short-1to2DTE put diagonal calendar on RUT.

Three modes:
  - calendar   (Ks = Kl)  — vega-positive theta income, NEUTRAL vol
  - protective (Ks < Kl)  — bearish bias, RICH vol
  - aggressive (Ks > Kl)  — bullish RICH vol, VIX < 25 hard limit

Defined-risk in all three: max loss at short-leg expiry =
max((Ks - Kl) * 100, 0) - net_credit (calendar collapses to long put
extrinsic decay).

Chain-vs-BSM fallback follows scripts.macro_hedge pattern using
shared scripts._market helpers; pricing_source ∈ {chain, mixed, bsm}.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from scipy.stats import norm

Mode = Literal["calendar", "protective", "aggressive"]

# Strike-selection policy per mode. Δ-only selection across 1-2DTE short +
# 45DTE long is mathematically broken for `calendar` (same Δ → different K
# across DTEs) and `protective` (1DTE 0.15Δ K ≈ 1.5% OTM, 45DTE 0.30Δ K ≈
# 5% OTM, so Ks > Kl with default Δs — violates the spec's "Ks < Kl"
# protective layout). Fix: Kl picked by Δ in all modes; Ks derived
# relative to Kl per mode-specific anchor below.
DEFAULT_DELTAS: dict[Mode, dict[str, float]] = {
    "calendar":   {"long": 0.30, "short": 0.30},  # short Δ unused; Ks = Kl
    "protective": {"long": 0.30, "short": 0.15},  # short Δ used as fallback
    "aggressive": {"long": 0.15, "short": 0.30},  # natural Ks > Kl with these Δs
}

# Mode-specific Ks selection AFTER Kl is fixed.
#   calendar:   Ks = Kl  (same strike)
#   protective: Ks = Kl * (1 - SHORT_STRIKE_OFFSET_PCT)  → Ks < Kl by ~2.5%
#   aggressive: Ks picked by short_delta (gives Ks > Kl naturally with
#               default 0.30 short Δ + 0.15 long Δ, since 1DTE 0.30Δ K is
#               ~1.5% OTM while 45DTE 0.15Δ K is ~9% OTM)
SHORT_STRIKE_OFFSET_PCT = {
    "protective": 0.025,
}

_R = 0.04  # risk-free rate assumption shared with macro_hedge


def _bs_put_greeks(
    spot: float, strike: float, t_years: float, r: float, sigma: float
) -> dict[str, float]:
    """Black-Scholes put greeks. Theta returned per calendar day, vega per 1pp IV."""
    if t_years <= 0 or sigma <= 0:
        intrinsic_delta = -1.0 if spot < strike else 0.0
        return {"delta": intrinsic_delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    delta = norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (spot * sigma * math.sqrt(t_years))
    theta_annual = (
        -spot * norm.pdf(d1) * sigma / (2 * math.sqrt(t_years))
        + r * strike * math.exp(-r * t_years) * norm.cdf(-d2)
    )
    vega_per_1 = spot * norm.pdf(d1) * math.sqrt(t_years)
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta_annual / 365,
        "vega": vega_per_1 / 100,
    }


def _strike_for_put_delta(
    spot: float, target_abs: float, t_years: float, iv: float, r: float = _R
) -> float:
    """Invert BSM to find strike with put |Δ| ≈ target_abs."""
    if not 0 < target_abs < 1:
        raise ValueError(f"target_abs must be in (0,1), got {target_abs}")
    z = norm.ppf(target_abs)
    return spot * math.exp((r + 0.5 * iv ** 2) * t_years + iv * math.sqrt(t_years) * z)
```

- [ ] **Step 4.4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v
```

Expected: 3 tests pass.

- [ ] **Step 4.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py tests/test_diagonal_calendar.py
git commit -m "feat(diagonal_calendar): scaffold module with BSM greeks + strike selection"
```

---

### Task 5: Mode dispatch + leg building (BSM-only path)

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py`
- Modify: `tests/test_diagonal_calendar.py`

- [ ] **Step 5.1: Write failing tests for build_diagonal_calendar (BSM path)**

Append to `tests/test_diagonal_calendar.py`:

```python
from scripts.diagonal_calendar import build_diagonal_calendar


RUT_SNAPSHOT_BSM = {
    "iv_atm_short": 0.28,
    "iv_atm_long": 0.30,
    "iv_rank": 35,
    "vrp_label": "NEUTRAL",
}


def test_calendar_mode_same_strike():
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    assert out["mode"] == "calendar"
    assert len(out["legs"]) == 2
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    assert long_leg["strike"] == pytest.approx(short_leg["strike"], rel=1e-6), (
        "calendar mode requires Ks == Kl"
    )


def test_protective_mode_short_below_long():
    out = build_diagonal_calendar(spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM)
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    assert short_leg["strike"] < long_leg["strike"], "protective: Ks < Kl"


def test_aggressive_mode_short_above_long():
    out = build_diagonal_calendar(spot=2300.0, mode="aggressive", snapshot=RUT_SNAPSHOT_BSM)
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    assert short_leg["strike"] > long_leg["strike"], "aggressive: Ks > Kl"


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="mode"):
        build_diagonal_calendar(spot=2300.0, mode="butterfly", snapshot=RUT_SNAPSHOT_BSM)


def test_pricing_source_bsm_when_no_chain():
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    assert out["pricing_source"] == "bsm"
    for leg in out["legs"]:
        assert leg["mid_source"] == "fallback"
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v -k "mode or pricing_source"
```

Expected: 5 fails with `AttributeError: module has no attribute 'build_diagonal_calendar'`.

- [ ] **Step 5.3: Add build_diagonal_calendar with BSM-only path**

Append to `scripts/diagonal_calendar.py`:

```python
def _bs_put(spot: float, strike: float, t_years: float, r: float, sigma: float) -> float:
    """BSM put price (same closed form as scripts.macro_hedge._bs_put)."""
    if t_years <= 0 or sigma <= 0:
        return max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma ** 2) * t_years) / (
        sigma * math.sqrt(t_years)
    )
    d2 = d1 - sigma * math.sqrt(t_years)
    return strike * math.exp(-r * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def _build_leg_bsm(
    *, spot: float, strike: float, action: str, qty: int, t_years: float, iv: float
) -> dict[str, Any]:
    """Build one leg dict using BSM mid (no chain available)."""
    price = _bs_put(spot, strike, t_years, _R, iv)
    greeks = _bs_put_greeks(spot, strike, t_years, _R, iv)
    return {
        "right": "put",
        "action": action,
        "strike": strike,
        "qty": qty,
        "limit_price": round(price, 2),
        "mid_source": "fallback",
        "mid_provenance": {
            "source": "fallback",
            "reason": f"BSM mid (no chain); IV={iv * 100:.0f}%, DTE={t_years * 365:.0f}",
        },
        "greeks": greeks,
    }


def build_diagonal_calendar(
    spot: float,
    mode: Mode,
    snapshot: dict[str, Any],
    dte_long: int = 45,
    dte_short: int = 1,
    target_deltas: dict[str, float] | None = None,
    qty: int = 1,
    underlying: str = "RUT",
) -> dict[str, Any]:
    """Build a put diagonal calendar (long Kl 45DTE + short Ks 1-2DTE).

    BSM-only path (chain support added in Task 8). See spec §7.
    """
    if mode not in DEFAULT_DELTAS:
        raise ValueError(f"unknown mode {mode!r}; expected one of {list(DEFAULT_DELTAS)}")
    deltas = target_deltas or DEFAULT_DELTAS[mode]

    iv_short = float(snapshot["iv_atm_short"])
    iv_long = float(snapshot["iv_atm_long"])
    t_short = dte_short / 365.0
    t_long = dte_long / 365.0

    # Kl always picked by long-leg Δ.
    k_long = _strike_for_put_delta(spot, deltas["long"], t_long, iv_long)

    # Ks selection per mode (NOT all by Δ — see DEFAULT_DELTAS docstring).
    if mode == "calendar":
        k_short = k_long
    elif mode == "protective":
        k_short = k_long * (1 - SHORT_STRIKE_OFFSET_PCT["protective"])
    else:  # aggressive
        k_short = _strike_for_put_delta(spot, deltas["short"], t_short, iv_short)

    if mode == "protective" and not k_short < k_long:
        raise ValueError(
            f"protective mode invariant violated: Ks={k_short:.2f} not < Kl={k_long:.2f}"
        )
    if mode == "aggressive" and not k_short > k_long:
        raise ValueError(
            f"aggressive mode invariant violated: Ks={k_short:.2f} not > Kl={k_long:.2f}"
        )

    long_leg = _build_leg_bsm(
        spot=spot, strike=k_long, action="buy", qty=qty, t_years=t_long, iv=iv_long
    )
    short_leg = _build_leg_bsm(
        spot=spot, strike=k_short, action="sell", qty=qty, t_years=t_short, iv=iv_short
    )

    return {
        "underlying": underlying,
        "mode": mode,
        "spot": spot,
        "dte_long": dte_long,
        "dte_short": dte_short,
        "legs": [long_leg, short_leg],
        "pricing_source": "bsm",
    }
```

- [ ] **Step 5.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v
```

Expected: all tests so far pass.

- [ ] **Step 5.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py tests/test_diagonal_calendar.py
git commit -m "feat(diagonal_calendar): mode dispatch + BSM leg building for 3 modes"
```

---

### Task 6: Net greeks, max_loss, breakeven, net_debit

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py`
- Modify: `tests/test_diagonal_calendar.py`

- [ ] **Step 6.1: Write failing tests**

Append to `tests/test_diagonal_calendar.py`:

```python
def test_calendar_net_debit_positive():
    """Calendar mode (Ks=Kl): long 45DTE >> short 1DTE premium at same K → net debit."""
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    assert out["net_debit_dollar"] > 0, "calendar should be net debit (long > short)"


def test_calendar_max_loss_equals_net_debit():
    """Calendar max loss = net_debit (worst case both legs decay to zero)."""
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    assert out["max_loss_dollar"] == pytest.approx(out["net_debit_dollar"], rel=1e-6)


def test_protective_max_loss_equals_net_debit():
    """Protective max loss = net_debit (S > Kl worst case, both worthless).
    Width (Kl - Ks) does NOT add to max loss — when S < Ks both legs are ITM
    and offset dollar-for-dollar in the width range."""
    out = build_diagonal_calendar(spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM)
    assert out["max_loss_dollar"] == pytest.approx(out["net_debit_dollar"], rel=1e-6)


def test_protective_strike_invariant_ks_below_kl():
    """Protective mode MUST produce Ks < Kl, regardless of input deltas."""
    out = build_diagonal_calendar(spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM)
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    assert short_leg["strike"] < long_leg["strike"]


def test_aggressive_max_loss_width_plus_debit():
    """Aggressive max loss = (Ks - Kl) * 100 + net_debit. Net credit (negative
    net_debit) correctly REDUCES max loss — formula must NOT use max(net_debit, 0)."""
    out = build_diagonal_calendar(spot=2300.0, mode="aggressive", snapshot=RUT_SNAPSHOT_BSM)
    long_leg = next(l for l in out["legs"] if l["action"] == "buy")
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    width = short_leg["strike"] - long_leg["strike"]
    expected = width * 100 + out["net_debit_dollar"]
    assert out["max_loss_dollar"] == pytest.approx(expected, rel=1e-6)


def test_aggressive_credit_reduces_max_loss():
    """If aggressive run produces net credit, the credit must REDUCE max loss
    by that amount (vs zero-credit comparison). Regression guard for the
    `max(net_debit, 0)` bug that swallowed credit silently."""
    out = build_diagonal_calendar(spot=2300.0, mode="aggressive", snapshot=RUT_SNAPSHOT_BSM)
    if out["net_debit_dollar"] < 0:  # got net credit
        long_leg = next(l for l in out["legs"] if l["action"] == "buy")
        short_leg = next(l for l in out["legs"] if l["action"] == "sell")
        width = short_leg["strike"] - long_leg["strike"]
        # max_loss must be strictly less than width × 100 (since credit covers some)
        assert out["max_loss_dollar"] < width * 100


def test_net_greeks_keys_present():
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    for k in ("delta", "gamma", "theta_daily", "vega"):
        assert k in out["net_greeks_entry"]
    assert out["net_greeks_entry"]["theta_daily"] > 0, (
        "calendar diagonal net theta should be positive (short theta dominates)"
    )
```

- [ ] **Step 6.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v -k "net_debit or max_loss or net_greeks"
```

Expected: 4 fails with `KeyError`.

- [ ] **Step 6.3: Implement net_debit, max_loss, breakeven, net_greeks**

Add helper functions and modify `build_diagonal_calendar` return dict. Append to `scripts/diagonal_calendar.py`:

```python
def _net_debit_dollar(legs: list[dict]) -> float:
    """Positive = net debit paid; negative = net credit received. Multiplier 100."""
    total = 0.0
    for leg in legs:
        sign = 1 if leg["action"] == "buy" else -1
        total += sign * leg["limit_price"] * leg["qty"] * 100
    return round(total, 2)


def _max_loss_at_short_expiry(
    legs: list[dict], net_debit: float, dte_long: int, dte_short: int
) -> float:
    """At short-leg expiry, close everything. Max loss per mode (derived
    from first principles — close both legs; do NOT take assignment):

      calendar (Ks=Kl):   worst case S >> K → both worthless → loss = net_debit
      protective (Ks<Kl): worst case S > Kl → both worthless → loss = net_debit.
                          When S < Ks, long put offsets short put dollar-for-
                          dollar (both ITM by same Δ), so width term cancels.
      aggressive (Ks>Kl): worst case S → 0 → long ITM by ~Kl·e^(-r·T_remain),
                          short ITM by Ks. Loss = (Ks - Kl·e^(-r·T_remain))*100 + net_debit.

    Discount-carry correction (codex P1.2 / v0 limit #8): at S=0 the
    long put market value is NOT Kl but Kl·e^(-r·T_remain). For aggressive
    this slightly REDUCES max loss (long pays out a bit less than Kl);
    for protective the long-vs-short offset is also imperfect by the same
    discount factor. Material on 43-day at 4% rate (~0.47% of Kl).

    Sign convention: net_debit > 0 = paid debit; net_debit < 0 = received credit.
    """
    long_leg = next(l for l in legs if l["action"] == "buy")
    short_leg = next(l for l in legs if l["action"] == "sell")
    kl, ks = long_leg["strike"], short_leg["strike"]
    qty = long_leg["qty"]
    t_remain = (dte_long - dte_short) / 365.0
    discount_factor = math.exp(-_R * t_remain)
    long_at_zero = kl * discount_factor  # PV of long put intrinsic if S→0

    if ks <= kl:  # calendar OR protective
        # When S >> Kl, both worthless → loss = net_debit (unchanged).
        # When S << Ks ≤ Kl, long pays Kl·DF, short pays Ks. Long − short = (Kl·DF − Ks)*100.
        # If Kl·DF > Ks (typical at small t_remain or far OTM short): profit on crash.
        # If Kl·DF < Ks (rare — Ks very close to Kl + meaningful discount): small crash loss.
        # Worst case is max of (S >> Kl loss) and (S << Ks loss):
        crash_loss = (ks - long_at_zero) * 100 * qty if long_at_zero < ks else 0.0
        return max(net_debit, crash_loss + net_debit)
    # aggressive (ks > kl)
    return (ks - long_at_zero) * 100 * qty + net_debit


def _breakevens_at_short_expiry(
    legs: list[dict], iv_long: float, dte_long: int, dte_short: int, spot: float
) -> dict[str, float | None]:
    """Find ALL breakevens (sign changes) of P/L(S) at short expiry on a fine grid
    spanning [spot * 0.6, spot * 1.10]. Diagonal calendars typically have two BE
    points (one above, one below the strike cluster) bracketing a profit zone.

    Returns {'lower': float | None, 'upper': float | None}. None when no BE
    on that side (e.g., pure debit with no profit zone)."""
    long_leg = next(l for l in legs if l["action"] == "buy")
    short_leg = next(l for l in legs if l["action"] == "sell")
    kl, ks = long_leg["strike"], short_leg["strike"]
    long_cost = long_leg["limit_price"] * long_leg["qty"] * 100
    short_credit = short_leg["limit_price"] * short_leg["qty"] * 100
    t_remain = max((dte_long - dte_short) / 365.0, 1 / 365.0)

    def net_at(s: float) -> float:
        short_loss = max(ks - s, 0) * 100 * short_leg["qty"]
        long_mark = _bs_put(s, kl, t_remain, _R, iv_long) * 100 * long_leg["qty"]
        return short_credit - short_loss + (long_mark - long_cost)

    n_steps = 200
    lo_bound, hi_bound = spot * 0.60, spot * 1.10
    grid = [lo_bound + i * (hi_bound - lo_bound) / n_steps for i in range(n_steps + 1)]
    sign_changes = []
    prev = net_at(grid[0])
    for s in grid[1:]:
        cur = net_at(s)
        if (prev <= 0 and cur > 0) or (prev >= 0 and cur < 0):
            sign_changes.append(s)
        prev = cur
    lower = round(sign_changes[0], 2) if len(sign_changes) >= 1 else None
    upper = round(sign_changes[-1], 2) if len(sign_changes) >= 2 else None
    return {"lower": lower, "upper": upper}


def _net_greeks(legs: list[dict]) -> dict[str, float]:
    """Sum greeks across legs (sign by action: sell flips). Returns delta, gamma,
    theta_daily, vega (per 1pp IV move)."""
    net = {"delta": 0.0, "gamma": 0.0, "theta_daily": 0.0, "vega": 0.0}
    for leg in legs:
        sign = 1 if leg["action"] == "buy" else -1
        g = leg["greeks"]
        qty = leg["qty"]
        net["delta"] += sign * g["delta"] * qty
        net["gamma"] += sign * g["gamma"] * qty
        net["theta_daily"] += sign * g["theta"] * qty * 100  # $ per day
        net["vega"] += sign * g["vega"] * qty * 100         # $ per 1pp IV
    return {k: round(v, 4) for k, v in net.items()}
```

Now modify `build_diagonal_calendar` to compute these and include them in the return dict. Find the existing `return { ... }` block at the end of `build_diagonal_calendar` and replace with:

```python
    net_debit = _net_debit_dollar([long_leg, short_leg])
    max_loss = _max_loss_at_short_expiry([long_leg, short_leg], net_debit, dte_long, dte_short)
    breakevens = _breakevens_at_short_expiry(
        [long_leg, short_leg], iv_long, dte_long, dte_short, spot
    )
    net_greeks = _net_greeks([long_leg, short_leg])

    return {
        "underlying": underlying,
        "mode": mode,
        "spot": spot,
        "dte_long": dte_long,
        "dte_short": dte_short,
        "legs": [long_leg, short_leg],
        "net_debit_dollar": net_debit,
        "max_loss_dollar": round(max_loss, 2),
        "breakevens_at_short_expiry": breakevens,  # {'lower': float|None, 'upper': float|None}
        "net_greeks_entry": net_greeks,
        "pricing_source": "bsm",
    }
```

- [ ] **Step 6.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v
```

Expected: all tests pass (including the 4 new ones).

- [ ] **Step 6.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py tests/test_diagonal_calendar.py
git commit -m "feat(diagonal_calendar): net debit, max loss per mode, breakeven, net greeks"
```

---

### Task 7: Roll matrix computation

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py`
- Modify: `tests/test_diagonal_calendar.py`

- [ ] **Step 7.1: Write failing tests**

Append to `tests/test_diagonal_calendar.py`:

```python
def test_roll_matrix_has_seven_scenarios():
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    assert len(out["roll_matrix"]) == 7
    scenarios = [r["spot_scenario"] for r in out["roll_matrix"]]
    assert scenarios == [-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10]


def test_roll_matrix_protective_monotone_down():
    """For protective mode, net_pl should rise as RUT falls (until Ks hit), then bound."""
    out = build_diagonal_calendar(spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM)
    rows = out["roll_matrix"]
    # Net PL at -10% should be HIGHER than at 0% (long put pays off)
    pl_down10 = next(r["net_pl"] for r in rows if r["spot_scenario"] == -0.10)
    pl_flat = next(r["net_pl"] for r in rows if r["spot_scenario"] == 0.0)
    assert pl_down10 > pl_flat


def test_roll_matrix_short_put_pl_zero_above_strike():
    """If spot at short expiry > short strike Ks, short_put_pl ≈ credit received."""
    out = build_diagonal_calendar(spot=2300.0, mode="protective", snapshot=RUT_SNAPSHOT_BSM)
    short_leg = next(l for l in out["legs"] if l["action"] == "sell")
    ks = short_leg["strike"]
    short_credit = short_leg["limit_price"] * 100
    up_row = next(r for r in out["roll_matrix"] if r["spot_scenario"] == 0.10)
    assert up_row["spot_at_expiry"] > ks
    # short put expires worthless; PL = credit received
    assert up_row["short_put_pl"] == pytest.approx(short_credit, abs=1.0)


@pytest.mark.parametrize("mode", ["calendar", "protective", "aggressive"])
def test_roll_matrix_non_monotonic_shape(mode):
    """Diagonal calendar P/L is GENERALLY non-monotonic in spot — typically
    has a profit zone near the strike cluster with two breakevens flanking it.
    Replaces the lax 'P/L(-10%) > P/L(0%)' check; v0 limit #10.

    Expect: ≤ 2 sign changes in net_pl across the 7 spot scenarios
    (two breakevens = two sign changes; one or zero = degenerate cases
    like deep-credit aggressive where always profitable on upside).
    """
    out = build_diagonal_calendar(spot=2300.0, mode=mode, snapshot=RUT_SNAPSHOT_BSM)
    pls = [r["net_pl"] for r in out["roll_matrix"]]
    sign_changes = sum(
        1 for i in range(1, len(pls))
        if (pls[i - 1] > 0 and pls[i] < 0) or (pls[i - 1] < 0 and pls[i] > 0)
    )
    assert sign_changes <= 2, (
        f"{mode} roll matrix has {sign_changes} sign changes across 7 spot "
        f"scenarios — diagonal P/L should have ≤ 2 breakevens. P/L: {pls}"
    )
```

- [ ] **Step 7.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v -k "roll_matrix"
```

Expected: 3 fails with `KeyError: 'roll_matrix'`.

- [ ] **Step 7.3: Implement roll matrix**

Append to `scripts/diagonal_calendar.py`:

```python
def _roll_matrix(
    legs: list[dict],
    spot: float,
    iv_long: float,
    dte_long: int,
    dte_short: int,
) -> list[dict[str, float]]:
    """Compute P/L if we close everything at short-leg expiry, across 7 spot scenarios."""
    long_leg = next(l for l in legs if l["action"] == "buy")
    short_leg = next(l for l in legs if l["action"] == "sell")
    kl, ks = long_leg["strike"], short_leg["strike"]
    long_cost = long_leg["limit_price"] * long_leg["qty"] * 100
    short_credit = short_leg["limit_price"] * short_leg["qty"] * 100
    t_remain = (dte_long - dte_short) / 365.0

    out = []
    for s_scenario in (-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10):
        s_T = spot * (1 + s_scenario)
        short_intrinsic = max(ks - s_T, 0) * short_leg["qty"] * 100
        short_pl = short_credit - short_intrinsic
        long_mark = _bs_put(s_T, kl, t_remain, _R, iv_long) * long_leg["qty"] * 100
        net_pl = short_pl + (long_mark - long_cost)
        out.append({
            "spot_scenario": s_scenario,
            "spot_at_expiry": round(s_T, 2),
            "short_put_pl": round(short_pl, 2),
            "long_put_mark": round(long_mark, 2),
            "net_pl": round(net_pl, 2),
        })
    return out
```

Then in `build_diagonal_calendar`, after computing `net_greeks`, add:

```python
    roll_matrix = _roll_matrix([long_leg, short_leg], spot, iv_long, dte_long, dte_short)
```

And add to the return dict:

```python
        "roll_matrix": roll_matrix,
```

- [ ] **Step 7.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v
```

Expected: all tests pass.

- [ ] **Step 7.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py tests/test_diagonal_calendar.py
git commit -m "feat(diagonal_calendar): roll matrix across 7 spot scenarios at short expiry"
```

---

### Task 8: Chain-vs-BSM fallback + provenance + regime_check

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py`
- Modify: `tests/test_diagonal_calendar.py`

- [ ] **Step 8.1: Write failing tests**

Append to `tests/test_diagonal_calendar.py`:

```python
RUT_SNAPSHOT_CHAIN = {
    "iv_atm_short": 0.28,
    "iv_atm_long": 0.30,
    "iv_rank": 35,
    "vrp_label": "NEUTRAL",
    "chain_source": "UW",
    "spot_timestamp": "2026-06-09T10:00:00Z",
    "chain_timestamps": {
        "2026-06-10": "2026-06-09T10:00:00Z",
        "2026-07-24": "2026-06-09T10:00:00Z",
    },
    "chain": {
        "2026-06-10": {  # 1 DTE
            1.00: {"put": {"mid": 9.50, "iv": 0.28}},
            0.99: {"put": {"mid": 4.20, "iv": 0.30}},
            0.97: {"put": {"mid": 1.80, "iv": 0.33}},
        },
        "2026-07-24": {  # 45 DTE
            1.00: {"put": {"mid": 38.00, "iv": 0.30}},
            0.95: {"put": {"mid": 18.50, "iv": 0.32}},
            0.93: {"put": {"mid": 12.20, "iv": 0.33}},
        },
    },
}


def test_chain_path_used_when_available():
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_CHAIN)
    assert out["pricing_source"] in ("chain", "mixed")
    sources = {leg["mid_source"] for leg in out["legs"]}
    assert "UW" in sources or "IB" in sources


def test_regime_check_warns_on_mismatch():
    """Aggressive mode + bearish/cheap VRP → regime_check.warning populated."""
    cheap_snap = {**RUT_SNAPSHOT_BSM, "iv_rank": 12, "vrp_label": "CHEAP"}
    out = build_diagonal_calendar(spot=2300.0, mode="aggressive", snapshot=cheap_snap)
    assert out["regime_check"]["matches_chosen_mode"] is False
    assert out["regime_check"]["warning"] is not None


def test_regime_check_no_warning_when_match():
    """Calendar mode + NEUTRAL VRP → recommended_mode_for_regime should be 'calendar'."""
    out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    assert out["regime_check"]["matches_chosen_mode"] is True
    assert out["regime_check"]["warning"] is None
```

- [ ] **Step 8.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v -k "chain_path or regime_check"
```

Expected: 3 fails with `KeyError: 'regime_check'` or wrong pricing_source.

- [ ] **Step 8.3: Implement chain helpers + regime check**

Add imports at top of `scripts/diagonal_calendar.py`:

```python
from scripts._market import (
    chain_leg_provenance,
    fallback_provenance,
    read_chain_mid,
)
```

Append helper functions:

```python
def _read_chain_greeks(chain: dict, expiry: str, strike_pct: float) -> dict | None:
    """Read greeks dict from chain[expiry][matching_strike_pct]['put'] if
    present. Uses same 0.005 tolerance as read_chain_mid. Returns None
    if not provided — caller falls back to BSM recompute."""
    expiry_chain = chain.get(expiry, {})
    for k_pct, payload in expiry_chain.items():
        if abs(k_pct - strike_pct) <= 0.005:
            put_leg = payload.get("put", {})
            g = put_leg.get("greeks")
            if g and all(k in g for k in ("delta", "gamma", "theta", "vega")):
                return g
    return None


def _build_leg_chain_first(
    *,
    spot: float,
    strike: float,
    action: str,
    qty: int,
    t_years: float,
    iv: float,
    chain: dict | None,
    chain_source: str,
    chain_expiry: str | None,
    chain_timestamp: str | None,
) -> dict[str, Any]:
    """Build leg with chain mid + chain greeks if available, BSM fallback otherwise.

    Per hard rule #2 'if a source serves it directly, never recompute':
    when chain provides greeks, USE them. BSM recompute only when chain
    leg lacks greeks (mid + iv but no delta/gamma/theta/vega). Recomputing
    would silently disagree with the broker's IV surface."""
    if chain and chain_expiry:
        strike_pct = round(strike / spot, 4)
        mid = read_chain_mid(chain, chain_expiry, strike_pct, "put")
        if mid is not None:
            provenance = chain_leg_provenance(
                value=mid,
                chain_source=chain_source,
                expiry=chain_expiry,
                strike_pct=strike_pct,
                right="put",
                field="mid",
                timestamp=chain_timestamp,
            )
            chain_greeks = _read_chain_greeks(chain, chain_expiry, strike_pct)
            if chain_greeks is not None:
                greeks = chain_greeks
                greeks_source = chain_source
            else:
                greeks = _bs_put_greeks(spot, strike, t_years, _R, iv)
                greeks_source = "bsm_fallback"
            return {
                "right": "put",
                "action": action,
                "strike": strike,
                "qty": qty,
                "limit_price": round(mid, 2),
                "mid_source": chain_source,
                "mid_provenance": provenance,
                "greeks": greeks,
                "greeks_source": greeks_source,
            }
    # Fallback path (no chain at all)
    return _build_leg_bsm(
        spot=spot, strike=strike, action=action, qty=qty, t_years=t_years, iv=iv
    )


def _resolve_chain_expiries(
    snapshot: dict, dte_short: int, dte_long: int
) -> tuple[dict | None, str, str | None, str | None, str | None, str | None]:
    """Return (chain, chain_source, short_expiry, short_ts, long_expiry, long_ts)
    or (None, ..., None, None, None, None) if no chain in snapshot.
    Picks nearest listed expiry by sorted iso key (chain keys are 'YYYY-MM-DD')."""
    chain = snapshot.get("chain")
    chain_source = snapshot.get("chain_source", "UW")
    if not chain:
        return None, chain_source, None, None, None, None
    timestamps = snapshot.get("chain_timestamps", {})
    sorted_expiries = sorted(chain.keys())
    if len(sorted_expiries) < 2:
        return None, chain_source, None, None, None, None
    # Heuristic: first expiry → short, last → long. Caller is expected to
    # build the chain with exactly the expiries we want priced.
    short_expiry = sorted_expiries[0]
    long_expiry = sorted_expiries[-1]
    return (
        chain,
        chain_source,
        short_expiry,
        timestamps.get(short_expiry),
        long_expiry,
        timestamps.get(long_expiry),
    )


_REGIME_MODE_TABLE = {
    # (vrp_label, iv_rank_bucket) → recommended mode
    ("RICH", "high"):    "aggressive",   # high IV + RICH = sell premium aggressively
    ("RICH", "mid"):     "protective",   # bearish lean
    ("NEUTRAL", "high"): "calendar",
    ("NEUTRAL", "mid"):  "calendar",
    ("NEUTRAL", "low"):  "calendar",
    ("CHEAP", "high"):   None,           # don't sell when CHEAP
    ("CHEAP", "mid"):    None,
    ("CHEAP", "low"):    None,
}


def _regime_check(mode: str, snapshot: dict) -> dict[str, Any]:
    """Compare chosen mode against regime recommendation."""
    vrp = snapshot.get("vrp_label", "NEUTRAL")
    iv_rank = snapshot.get("iv_rank", 50)
    bucket = "high" if iv_rank >= 60 else "mid" if iv_rank >= 30 else "low"
    recommended = _REGIME_MODE_TABLE.get((vrp, bucket))
    matches = recommended == mode
    warning = None
    if not matches and recommended is not None:
        warning = (
            f"VRP={vrp} + IV rank {iv_rank} ({bucket}) suggests {recommended!r} mode; "
            f"chose {mode!r} — proceeds but accept lower expected edge"
        )
    elif recommended is None:
        warning = (
            f"VRP={vrp} indicates no sell-premium regime; chose {mode!r} — "
            f"consider deferring entry until VRP turns NEUTRAL or RICH"
        )
    return {
        "recommended_mode_for_regime": recommended,
        "matches_chosen_mode": matches,
        "warning": warning,
    }


def _pricing_source(legs: list[dict]) -> str:
    """Roll up per-leg mid_source to top-level pricing_source."""
    sources = {leg["mid_source"] for leg in legs}
    if sources in ({"UW"}, {"IB"}):
        return "chain"
    if "fallback" in sources and len(sources) > 1:
        return "mixed"
    return "bsm"


def _snap_to_listed_strike(target_k: float, spot: float, expiry_chain: dict) -> float:
    """Given a theoretical strike K_theo, find the listed strike (in $)
    closest to it from the chain's strike grid. Chain keys are strike_pct
    floats; convert each to $ and pick min distance."""
    if not expiry_chain:
        return target_k
    listed_dollars = [k_pct * spot for k_pct in expiry_chain.keys()]
    return min(listed_dollars, key=lambda k: abs(k - target_k))
```

Now rewrite `build_diagonal_calendar` to use the chain path. Replace the function body (everything after the docstring) with:

```python
    if mode not in DEFAULT_DELTAS:
        raise ValueError(f"unknown mode {mode!r}; expected one of {list(DEFAULT_DELTAS)}")
    deltas = target_deltas or DEFAULT_DELTAS[mode]

    iv_short = float(snapshot["iv_atm_short"])
    iv_long = float(snapshot["iv_atm_long"])
    t_short = dte_short / 365.0
    t_long = dte_long / 365.0

    # CRITICAL: mode-specific Ks selection (do NOT revert to Δ-only —
    # see Task 5 DEFAULT_DELTAS docstring; codex Pass-2 found this exact
    # regression when this function was rewritten for chain support).
    k_long = _strike_for_put_delta(spot, deltas["long"], t_long, iv_long)
    if mode == "calendar":
        k_short = k_long
    elif mode == "protective":
        k_short = k_long * (1 - SHORT_STRIKE_OFFSET_PCT["protective"])
    else:  # aggressive
        k_short = _strike_for_put_delta(spot, deltas["short"], t_short, iv_short)

    if mode == "protective" and not k_short < k_long:
        raise ValueError(
            f"protective mode invariant violated: Ks={k_short:.2f} not < Kl={k_long:.2f}"
        )
    if mode == "aggressive" and not k_short > k_long:
        raise ValueError(
            f"aggressive mode invariant violated: Ks={k_short:.2f} not > Kl={k_long:.2f}"
        )

    (
        chain,
        chain_source,
        short_expiry,
        short_ts,
        long_expiry,
        long_ts,
    ) = _resolve_chain_expiries(snapshot, dte_short, dte_long)

    # Snap strikes to nearest listed strike when chain available (codex P2:
    # exact rounded strike-pct lookup misses real-listed strikes — read the
    # chain's actual grid and pick closest).
    if chain:
        if long_expiry and long_expiry in chain:
            k_long = _snap_to_listed_strike(k_long, spot, chain[long_expiry])
        if short_expiry and short_expiry in chain:
            k_short = _snap_to_listed_strike(k_short, spot, chain[short_expiry])
        # Re-validate invariants after snapping
        if mode == "calendar" and abs(k_short - k_long) > 1e-6:
            # Calendar requires same K — if expiries have different listed grids,
            # snap short to the long's K rounded to short-expiry's nearest strike
            if short_expiry and short_expiry in chain:
                k_short = _snap_to_listed_strike(k_long, spot, chain[short_expiry])
        if mode == "protective" and not k_short < k_long:
            k_short = k_long * (1 - SHORT_STRIKE_OFFSET_PCT["protective"])
            if short_expiry and short_expiry in chain:
                k_short = _snap_to_listed_strike(k_short, spot, chain[short_expiry])

    long_leg = _build_leg_chain_first(
        spot=spot, strike=k_long, action="buy", qty=qty, t_years=t_long, iv=iv_long,
        chain=chain, chain_source=chain_source,
        chain_expiry=long_expiry, chain_timestamp=long_ts,
    )
    short_leg = _build_leg_chain_first(
        spot=spot, strike=k_short, action="sell", qty=qty, t_years=t_short, iv=iv_short,
        chain=chain, chain_source=chain_source,
        chain_expiry=short_expiry, chain_timestamp=short_ts,
    )

    net_debit = _net_debit_dollar([long_leg, short_leg])
    max_loss = _max_loss_at_short_expiry([long_leg, short_leg], net_debit, dte_long, dte_short)
    breakevens = _breakevens_at_short_expiry(
        [long_leg, short_leg], iv_long, dte_long, dte_short, spot
    )
    net_greeks = _net_greeks([long_leg, short_leg])
    roll_matrix = _roll_matrix([long_leg, short_leg], spot, iv_long, dte_long, dte_short)
    regime_check = _regime_check(mode, snapshot)

    return {
        "underlying": underlying,
        "mode": mode,
        "spot": spot,
        "dte_long": dte_long,
        "dte_short": dte_short,
        "legs": [long_leg, short_leg],
        "net_debit_dollar": net_debit,
        "max_loss_dollar": round(max_loss, 2),
        "breakevens_at_short_expiry": breakevens,
        "net_greeks_entry": net_greeks,
        "roll_matrix": roll_matrix,
        "pricing_source": _pricing_source([long_leg, short_leg]),
        "regime_check": regime_check,
    }
```

- [ ] **Step 8.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v
```

Expected: all tests pass (including chain + regime_check tests). Note: `test_pricing_source_bsm_when_no_chain` still passes because BSM snapshot has no `chain` key.

- [ ] **Step 8.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py tests/test_diagonal_calendar.py
git commit -m "feat(diagonal_calendar): chain-vs-BSM fallback with provenance + regime check"
```

---

### Task 9: `build_short_leg_roll` helper

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py`
- Modify: `tests/test_diagonal_calendar.py`

- [ ] **Step 9.1: Write failing tests**

Append to `tests/test_diagonal_calendar.py`:

```python
from scripts.diagonal_calendar import build_short_leg_roll


def test_roll_triggers_close_when_long_dte_too_short():
    """Long leg DTE remaining < 21 → action_required = 'close_all_long_dte_too_short'."""
    pos = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM,
                                   dte_long=24, dte_short=1)
    # Simulate 4 days passing: long_dte_remaining_when_roll_done = 24 - 4 - 1 = 19
    snap_after = {**RUT_SNAPSHOT_BSM}
    roll = build_short_leg_roll(
        existing_position=pos, new_dte_short=1, snapshot=snap_after, days_elapsed=4
    )
    assert roll["action_required"] == "close_all_long_dte_too_short"


def test_roll_returns_close_old_and_open_new():
    pos = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    snap_after = {**RUT_SNAPSHOT_BSM, "iv_atm_short": 0.30}  # slight IV change
    roll = build_short_leg_roll(
        existing_position=pos, new_dte_short=1, snapshot=snap_after, days_elapsed=1
    )
    assert "close_old_short_leg" in roll
    assert "open_new_short_leg" in roll
    assert roll["action_required"] == "roll_short"


def test_roll_recommends_mode_switch_on_drift():
    """Calendar mode but short put ITM by 1+ strike → switch_mode_recommendation = 'protective'."""
    pos = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=RUT_SNAPSHOT_BSM)
    # Spot dropped 3% — short put now ITM by more than 1 strike
    snap_after = {**RUT_SNAPSHOT_BSM, "spot": 2230.0}
    roll = build_short_leg_roll(
        existing_position=pos, new_dte_short=1, snapshot=snap_after, days_elapsed=1
    )
    assert roll["switch_mode_recommendation"] == "protective"
```

- [ ] **Step 9.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v -k "roll_triggers or roll_returns or roll_recommends"
```

Expected: 3 fails with ImportError.

- [ ] **Step 9.3: Implement build_short_leg_roll**

Append to `scripts/diagonal_calendar.py`:

```python
def build_short_leg_roll(
    existing_position: dict[str, Any],
    new_dte_short: int,
    snapshot: dict[str, Any],
    days_elapsed: int = 1,
) -> dict[str, Any]:
    """Roll short leg on expiry-day −1h.

    Returns action_required ∈ {'roll_short', 'close_all_long_dte_too_short', 'switch_mode'}.
    """
    mode = existing_position["mode"]
    spot_now = snapshot.get("spot", existing_position["spot"])
    long_dte_remaining = existing_position["dte_long"] - days_elapsed - new_dte_short

    old_short_leg = next(l for l in existing_position["legs"] if l["action"] == "sell")
    old_long_leg = next(l for l in existing_position["legs"] if l["action"] == "buy")
    ks_old, kl = old_short_leg["strike"], old_long_leg["strike"]

    iv_short_new = float(snapshot["iv_atm_short"])
    t_new_short = new_dte_short / 365.0

    # Mark current short leg (cost to close)
    old_short_mark = _bs_put(spot_now, ks_old, max(t_new_short / 2, 1 / 365), _R, iv_short_new)
    short_credit_orig = old_short_leg["limit_price"]
    close_pl = (short_credit_orig - old_short_mark) * old_short_leg["qty"] * 100

    # Pick new short strike at default Δ for this mode
    deltas = DEFAULT_DELTAS[mode]
    k_short_new = _strike_for_put_delta(spot_now, deltas["short"], t_new_short, iv_short_new)
    new_short_mark = _bs_put(spot_now, k_short_new, t_new_short, _R, iv_short_new)
    new_credit = new_short_mark * old_short_leg["qty"] * 100

    net_credit_for_roll = round(close_pl + new_credit, 2)

    # Action decisions (priority order)
    if long_dte_remaining < 21:
        action = "close_all_long_dte_too_short"
    elif mode == "calendar" and (kl - spot_now) >= 5:
        # Calendar drifted ITM by ≥ 1 RUT strike width
        action = "switch_mode"
    else:
        action = "roll_short"

    switch_recommendation = None
    if mode == "calendar" and (kl - spot_now) >= 5:
        switch_recommendation = "protective"

    return {
        "close_old_short_leg": {
            "strike": ks_old,
            "mark_close": round(old_short_mark, 2),
            "pl_dollar": round(close_pl, 2),
        },
        "open_new_short_leg": {
            "strike": round(k_short_new, 2),
            "mark_open": round(new_short_mark, 2),
            "target_delta": deltas["short"],
        },
        "net_credit_for_roll": net_credit_for_roll,
        "long_leg_dte_remaining": long_dte_remaining,
        "action_required": action,
        "switch_mode_recommendation": switch_recommendation,
    }
```

- [ ] **Step 9.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_diagonal_calendar.py -v
```

Expected: all tests pass.

- [ ] **Step 9.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/diagonal_calendar.py tests/test_diagonal_calendar.py
git commit -m "feat(diagonal_calendar): short-leg roll helper with mode-switch and 21-DTE close trigger"
```

---

## Phase C — `scripts/entry_timing.py` (4 tasks, TDD)

### Task 10: Scaffold + THRESHOLDS + VIX + premarket gap + GEX steps

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py`
- Create: `tests/test_entry_timing.py`

- [ ] **Step 10.1: Write failing tests for steps 1-3**

Create `tests/test_entry_timing.py`:

```python
"""Tests for scripts.entry_timing."""

import pytest

from scripts.entry_timing import THRESHOLDS, decide


BASE_SNAPSHOT = {
    "spot": 2300.0,
    "time_et": "10:00",
    "vix": 14.0, "vix1d": 13.5, "vix9d": 14.0,
    "premarket_gap": 0.003,
    "gex_flip": 2250.0, "net_dealer_gex": 1.0e9,
    "odte_put_premium": 4.0e6, "odte_call_premium": 4.0e6,
    "is_fomc_day": False, "is_monday_open": False, "is_opex_friday": False,
}


def test_vix_event_backwardation_aborts():
    snap = {**BASE_SNAPSHOT, "vix": 22.0, "vix1d": 24.0, "vix9d": 22.5}
    out = decide(snap, mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "vix_event_backwardation"


def test_vix_too_low_aborts():
    snap = {**BASE_SNAPSHOT, "vix": 10.5}
    snap["vrp_label"] = "CHEAP"
    out = decide(snap, mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "vix_too_low_cheap_vrp"


def test_premarket_gap_qqq_waits():
    snap = {**BASE_SNAPSHOT, "premarket_gap": -0.015}  # 1.5% gap down on QQQ underlying
    out = decide(snap, mode="csp")
    assert out["action"] == "wait_minutes"
    assert out["triggered_threshold"] == "premarket_gap"


def test_premarket_gap_rut_uses_higher_threshold():
    snap = {**BASE_SNAPSHOT, "premarket_gap": -0.012}  # 1.2% — below RUT's 1.5% threshold
    out = decide(snap, mode="rut_calendar")
    # 1.2% < 1.5% → does NOT trigger premarket gap
    assert out["triggered_threshold"] != "premarket_gap"


def test_gex_short_gamma_with_flip_proximity_waits_eod():
    snap = {**BASE_SNAPSHOT,
            "net_dealer_gex": -2.0e9, "gex_flip": 2295.0, "spot": 2300.0}
    out = decide(snap, mode="csp")
    assert out["action"] == "wait_eod"
    assert out["triggered_threshold"] == "gex_short_flip_proximity"


def test_thresholds_is_dict():
    assert isinstance(THRESHOLDS, dict)
    assert "vix_abort_high" in THRESHOLDS
```

- [ ] **Step 10.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_entry_timing.py -v
```

Expected: all fail with ImportError.

- [ ] **Step 10.3: Implement scaffold + steps 1-3 of decision tree**

Create `plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py`:

```python
"""Entry timing decision tree for short-dated short-premium structures.

5-step tree: VIX gate → premarket gap → dealer GEX → 0DTE flow → mode window.
Day-specific overrides (FOMC / Monday open / OPEX Friday) take priority.

All thresholds in the THRESHOLDS dict at module top — first-draft heuristics,
calibrate via `scripts.entry_timing --calibrate` audit log (backtest deferred to v1.1).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

THRESHOLDS = {
    "vix_abort_high":           18.0,
    "vix_event_ratio":          1.05,
    "vix_abort_low":            12.0,
    "gap_wait_pct":             0.010,
    "gap_wait_pct_rut":         0.015,
    "gex_flip_proximity":       0.010,
    "odte_put_buyer_ratio":     3.0,
    "aggressive_mode_vix_cap":  25.0,
}

AUDIT_LOG_PATH = os.path.expanduser(
    "~/projects/option-wizard/plugins/option-wizard/skills/option-wizard/"
    "references/private/market/entry-timing-log.jsonl"
)


def _is_rut_mode(mode: str) -> bool:
    return mode.startswith("rut_")


def _step1_vix_gate(snap: dict) -> dict | None:
    """ABORT on VIX event backwardation or too-low + CHEAP VRP. Returns abort dict or None."""
    vix = snap.get("vix", 15.0)
    vix1d = snap.get("vix1d", vix)
    vix9d = snap.get("vix9d", vix)
    if (
        vix1d > vix > THRESHOLDS["vix_abort_high"]
        and vix9d > 0
        and (vix1d / vix9d) > THRESHOLDS["vix_event_ratio"]
    ):
        return {
            "action": "abort",
            "reason": (
                f"VIX1D {vix1d:.1f} > VIX {vix:.1f} > {THRESHOLDS['vix_abort_high']} + "
                f"backwardation ratio {vix1d / vix9d:.2f} > {THRESHOLDS['vix_event_ratio']}"
            ),
            "triggered_threshold": "vix_event_backwardation",
            "retry_at_iso": None,
        }
    if vix < THRESHOLDS["vix_abort_low"] and snap.get("vrp_label") == "CHEAP":
        return {
            "action": "abort",
            "reason": (
                f"VIX {vix:.1f} < {THRESHOLDS['vix_abort_low']} + VRP=CHEAP — "
                f"no risk premium to capture"
            ),
            "triggered_threshold": "vix_too_low_cheap_vrp",
            "retry_at_iso": None,
        }
    return None


def _step2_premarket_gap(snap: dict, mode: str) -> dict | None:
    """WAIT 30 min if absolute premarket gap exceeds mode-specific threshold."""
    gap = abs(snap.get("premarket_gap", 0.0))
    threshold = (
        THRESHOLDS["gap_wait_pct_rut"] if _is_rut_mode(mode) else THRESHOLDS["gap_wait_pct"]
    )
    if gap > threshold:
        return {
            "action": "wait_minutes",
            "reason": f"premarket gap {gap * 100:.2f}% > {threshold * 100:.1f}% — wait 30 min",
            "triggered_threshold": "premarket_gap",
            "retry_at_iso": None,
            "wait_minutes": 30,
        }
    return None


def _step3_gex_state(snap: dict) -> dict | None:
    """WAIT_EOD if dealers short gamma AND spot within 1% of gamma flip."""
    spot = snap["spot"]
    flip = snap.get("gex_flip")
    gex = snap.get("net_dealer_gex", 0.0)
    if flip is None or spot == 0:
        return None
    proximity = abs(flip - spot) / spot
    if gex < 0 and proximity < THRESHOLDS["gex_flip_proximity"]:
        return {
            "action": "wait_eod",
            "reason": (
                f"short dealer gamma ({gex:.1e}) + flip @ {flip:.0f} within "
                f"{proximity * 100:.2f}% of spot {spot:.0f} — positioning unstable"
            ),
            "triggered_threshold": "gex_short_flip_proximity",
            "retry_at_iso": None,
        }
    return None


def decide(snapshot: dict[str, Any], mode: str) -> dict[str, Any]:
    """Return one of: enter_now, wait_eod, wait_minutes, abort.

    Side effect: appends JSONL line to AUDIT_LOG_PATH (best-effort).
    """
    for step in (_step1_vix_gate, lambda s: _step2_premarket_gap(s, mode), _step3_gex_state):
        result = step(snapshot)
        if result is not None:
            return result
    # Steps 4-5 added in Task 11.
    return {
        "action": "enter_now",
        "reason": "all gates passed (steps 4-5 pending)",
        "triggered_threshold": "none",
        "retry_at_iso": None,
    }
```

- [ ] **Step 10.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_entry_timing.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 10.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py tests/test_entry_timing.py
git commit -m "feat(entry_timing): scaffold + steps 1-3 (VIX gate, premarket gap, GEX state)"
```

---

### Task 11: Steps 4-5 (0DTE flow, mode window) + day-specific overrides

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py`
- Modify: `tests/test_entry_timing.py`

- [ ] **Step 11.1: Write failing tests**

Append to `tests/test_entry_timing.py`:

```python
def test_odte_whale_put_buyer_waits():
    snap = {**BASE_SNAPSHOT, "odte_put_premium": 15.0e6, "odte_call_premium": 3.0e6}
    out = decide(snap, mode="csp")
    assert out["action"] == "wait_minutes"
    assert out["triggered_threshold"] == "odte_put_buyer_imbalance"


def test_csp_mode_morning_window_recommends_enter():
    snap = {**BASE_SNAPSHOT, "time_et": "10:00"}
    out = decide(snap, mode="csp")
    assert out["action"] == "enter_now"


def test_rut_calendar_mode_morning_says_wait_eod():
    """RUT calendar mode targets EOD window. Calling at 10am → wait until EOD."""
    snap = {**BASE_SNAPSHOT, "time_et": "10:00"}
    out = decide(snap, mode="rut_calendar")
    assert out["action"] == "wait_eod"
    assert out["triggered_threshold"] == "mode_window_eod"


def test_rut_aggressive_vix_cap_blocks_above_25():
    snap = {**BASE_SNAPSHOT, "vix": 27.0}
    out = decide(snap, mode="rut_aggressive")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "aggressive_mode_vix_cap"


def test_fomc_day_override_waits_until_1430():
    snap = {**BASE_SNAPSHOT, "is_fomc_day": True, "time_et": "10:00"}
    out = decide(snap, mode="csp")
    assert out["action"] == "wait_minutes"
    assert out["triggered_threshold"] == "fomc_presser"


def test_monday_open_override():
    snap = {**BASE_SNAPSHOT, "is_monday_open": True, "time_et": "09:35"}
    out = decide(snap, mode="csp")
    assert out["action"] == "wait_minutes"
    assert out["triggered_threshold"] == "monday_open_unwind"


def test_opex_friday_csp_defers_to_eod():
    snap = {**BASE_SNAPSHOT, "is_opex_friday": True, "time_et": "13:30"}
    out = decide(snap, mode="csp")
    assert out["action"] == "wait_eod"
    assert out["triggered_threshold"] == "opex_friday_pin_csp"


def test_opex_friday_diagonal_anchors_max_pain():
    snap = {**BASE_SNAPSHOT, "is_opex_friday": True, "time_et": "13:30"}
    out = decide(snap, mode="rut_calendar")
    assert out["action"] == "enter_now"
    assert out["triggered_threshold"] == "opex_friday_anchor_max_pain"


def test_freshness_gate_rejects_stale_snapshot():
    from datetime import datetime, timezone, timedelta
    stale = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    snap = {**BASE_SNAPSHOT, "snapshot_taken_at": stale}
    out = decide(snap, mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "freshness_stale_snapshot"


def test_freshness_gate_rejects_missing_timestamp():
    # BASE_SNAPSHOT has no snapshot_taken_at
    out = decide(BASE_SNAPSHOT, mode="csp")
    assert out["action"] == "abort"
    assert out["triggered_threshold"] == "freshness_missing_timestamp"


def test_freshness_gate_accepts_fresh_snapshot():
    from datetime import datetime, timezone
    fresh = datetime.now(timezone.utc).isoformat()
    snap = {**BASE_SNAPSHOT, "snapshot_taken_at": fresh}
    out = decide(snap, mode="csp")
    # Should pass freshness; downstream result depends on other gates
    assert out["triggered_threshold"] != "freshness_stale_snapshot"
    assert out["triggered_threshold"] != "freshness_missing_timestamp"
```

**Note on test data**: `BASE_SNAPSHOT` deliberately lacks
`snapshot_taken_at` to test the missing-timestamp branch.
Other tests that need to pass freshness must inject a fresh ISO
timestamp; update existing test cases above to add
`"snapshot_taken_at": (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()`
to their snap dicts.

- [ ] **Step 11.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_entry_timing.py -v -k "odte or window or aggressive or fomc or monday"
```

Expected: 6 fails (current code returns "enter_now" without checking these).

- [ ] **Step 11.3: Implement steps 4-5 + day overrides**

Append helper functions to `scripts/entry_timing.py`:

```python
def _step4_odte_flow(snap: dict) -> dict | None:
    """WAIT if 0DTE put-buyer ratio exceeds threshold."""
    pp = snap.get("odte_put_premium", 0.0)
    cp = snap.get("odte_call_premium", 0.0)
    if cp <= 0:
        return None
    ratio = pp / cp
    if ratio > THRESHOLDS["odte_put_buyer_ratio"]:
        return {
            "action": "wait_minutes",
            "reason": (
                f"0DTE put/call premium ratio {ratio:.1f} > "
                f"{THRESHOLDS['odte_put_buyer_ratio']} — wait for whale flow to clear"
            ),
            "triggered_threshold": "odte_put_buyer_imbalance",
            "retry_at_iso": None,
            "wait_minutes": 30,
        }
    return None


def _step5_mode_window(snap: dict, mode: str) -> dict:
    """Final gate: pick window by mode. Compare current time to target window."""
    time_et = snap.get("time_et", "10:00")
    hour = int(time_et.split(":")[0])
    minute = int(time_et.split(":")[1])
    minutes_into_day = hour * 60 + minute

    # Window in minutes (ET): morning = 9:45-10:30; eod = 15:30-15:55
    morning_start, morning_end = 9 * 60 + 45, 10 * 60 + 30
    eod_start, eod_end = 15 * 60 + 30, 15 * 60 + 55

    mode_window = {
        "csp":             "morning",
        "rut_calendar":    "eod",
        "rut_protective":  "morning",
        "rut_aggressive":  "eod",
    }.get(mode, "morning")

    if mode_window == "morning":
        if morning_start <= minutes_into_day <= morning_end:
            return {
                "action": "enter_now",
                "reason": f"in morning window for {mode}",
                "triggered_threshold": "mode_window_morning",
                "retry_at_iso": None,
            }
        if minutes_into_day < morning_start:
            return {
                "action": "wait_minutes",
                "reason": f"morning window opens at 09:45 ET",
                "triggered_threshold": "mode_window_morning_pending",
                "retry_at_iso": None,
                "wait_minutes": morning_start - minutes_into_day,
            }
        return {
            "action": "wait_eod",
            "reason": f"morning window passed; defer to next session or EOD review",
            "triggered_threshold": "mode_window_morning_missed",
            "retry_at_iso": None,
        }
    # eod
    if eod_start <= minutes_into_day <= eod_end:
        return {
            "action": "enter_now",
            "reason": f"in EOD window for {mode}",
            "triggered_threshold": "mode_window_eod",
            "retry_at_iso": None,
        }
    return {
        "action": "wait_eod",
        "reason": f"EOD window {mode}: 15:30-15:55 ET",
        "triggered_threshold": "mode_window_eod",
        "retry_at_iso": None,
    }


def _day_specific_override(snap: dict, mode: str) -> dict | None:
    """FOMC presser / Monday open / OPEX Friday overrides (priority above all)."""
    time_et = snap.get("time_et", "10:00")
    hour = int(time_et.split(":")[0])
    minute = int(time_et.split(":")[1])
    if snap.get("is_fomc_day") and hour < 14:
        return {
            "action": "wait_minutes",
            "reason": "FOMC presser day; wait until 14:30 ET",
            "triggered_threshold": "fomc_presser",
            "retry_at_iso": None,
            "wait_minutes": (14 * 60 + 30) - (hour * 60 + minute),
        }
    if snap.get("is_monday_open") and hour == 9 and minute < 60:
        return {
            "action": "wait_minutes",
            "reason": "Monday open: wait 30 min for weekend gamma unwind",
            "triggered_threshold": "monday_open_unwind",
            "retry_at_iso": None,
            "wait_minutes": 30,
        }
    # OPEX Friday afternoon (3rd Friday of month, after 12:00 ET): pin
    # trading active. CSP defers to EOD (cleaner mid); diagonals stay
    # but flag for orchestrator to anchor short strike to UW max pain.
    if snap.get("is_opex_friday") and hour >= 12:
        if mode == "csp":
            return {
                "action": "wait_eod",
                "reason": "OPEX Friday afternoon: pin trading active; defer CSP entry to EOD window",
                "triggered_threshold": "opex_friday_pin_csp",
                "retry_at_iso": None,
            }
        return {
            "action": "enter_now",
            "reason": "OPEX Friday afternoon: anchor short strike to UW max pain (orchestrator verifies)",
            "triggered_threshold": "opex_friday_anchor_max_pain",
            "retry_at_iso": None,
        }
    return None


def _check_snapshot_freshness(snap: dict) -> dict | None:
    """Per spec §10 hard rule #7: snapshot must be ≤ 15 min stale for
    entry decisions (tighter than the 1-trading-day default because
    dealer GEX + 0DTE flow + premarket gap move minute-by-minute)."""
    from datetime import datetime, timezone, timedelta
    ts_iso = snap.get("snapshot_taken_at")
    if not ts_iso:
        return {
            "action": "abort",
            "reason": "snapshot.snapshot_taken_at missing; cannot verify freshness",
            "triggered_threshold": "freshness_missing_timestamp",
            "retry_at_iso": None,
        }
    try:
        snap_ts = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    except ValueError:
        return {
            "action": "abort",
            "reason": f"snapshot.snapshot_taken_at {ts_iso!r} not valid ISO8601",
            "triggered_threshold": "freshness_invalid_timestamp",
            "retry_at_iso": None,
        }
    age = datetime.now(timezone.utc) - snap_ts
    if age > timedelta(minutes=15):
        return {
            "action": "abort",
            "reason": f"snapshot {age.total_seconds() / 60:.0f} min stale (> 15 min limit); re-pull UW + TV",
            "triggered_threshold": "freshness_stale_snapshot",
            "retry_at_iso": None,
        }
    return None


def _aggressive_mode_vix_check(snap: dict, mode: str) -> dict | None:
    """RUT aggressive mode hard limit: VIX < 25."""
    if mode == "rut_aggressive" and snap.get("vix", 0) >= THRESHOLDS["aggressive_mode_vix_cap"]:
        return {
            "action": "abort",
            "reason": (
                f"RUT aggressive mode requires VIX < {THRESHOLDS['aggressive_mode_vix_cap']}; "
                f"current {snap.get('vix'):.1f} — fall back to protective mode"
            ),
            "triggered_threshold": "aggressive_mode_vix_cap",
            "retry_at_iso": None,
        }
    return None
```

Modify the `decide()` function to call these new steps in the right order. Replace the body of `decide`:

```python
    # Priority order: freshness → day-specific override → mode hard limits →
    # vix gate → gap → gex → 0dte → mode window
    for step in (
        _check_snapshot_freshness,
        lambda s: _day_specific_override(s, mode),
        lambda s: _aggressive_mode_vix_check(s, mode),
        _step1_vix_gate,
        lambda s: _step2_premarket_gap(s, mode),
        _step3_gex_state,
        _step4_odte_flow,
    ):
        result = step(snapshot)
        if result is not None:
            return result
    return _step5_mode_window(snapshot, mode)
```

- [ ] **Step 11.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_entry_timing.py -v
```

Expected: all 12 tests pass.

- [ ] **Step 11.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py tests/test_entry_timing.py
git commit -m "feat(entry_timing): steps 4-5 (0DTE flow, mode window) + day-specific overrides"
```

---

### Task 12: Audit log write + calibrate()

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py`
- Modify: `tests/test_entry_timing.py`

- [ ] **Step 12.1: Write failing tests**

Append to `tests/test_entry_timing.py`:

```python
import tempfile

from scripts.entry_timing import calibrate


def test_audit_log_writes_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "entry-timing-log.jsonl"
    monkeypatch.setattr("scripts.entry_timing.AUDIT_LOG_PATH", str(log_path))
    decide(BASE_SNAPSHOT, mode="csp")
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["decision"] in ("enter_now", "wait_eod", "wait_minutes", "abort")
    assert "mode" in parsed
    assert "triggered_threshold" in parsed


def test_calibrate_aggregates(tmp_path, monkeypatch):
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setattr("scripts.entry_timing.AUDIT_LOG_PATH", str(log_path))
    # Write 5 fake entries
    for trigger in ["vix_event_backwardation", "premarket_gap", "premarket_gap",
                    "mode_window_morning", "mode_window_morning"]:
        log_path.open("a").write(json.dumps({
            "timestamp": "2026-06-09T10:00:00Z",
            "mode": "csp",
            "decision": "abort" if "vix" in trigger else "enter_now",
            "triggered_threshold": trigger,
            "snapshot_hash": f"hash_{trigger}",
        }) + "\n")
    stats = calibrate(log_path=str(log_path))
    assert stats["total_decisions"] == 5
    assert stats["per_threshold_fire_count"]["premarket_gap"] == 2
    assert "tuning_hints" in stats


def test_calibrate_reports_never_fired_thresholds(tmp_path, monkeypatch):
    """Spec gap #8: calibrate must report thresholds that never fired
    (count=0) with 'never fired' hint, NOT just iterate triggers seen
    in log. Otherwise over-loose thresholds catching nothing are invisible."""
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setattr("scripts.entry_timing.AUDIT_LOG_PATH", str(log_path))
    # Write 15 entries that all trigger ONE threshold (vix_too_low_cheap_vrp);
    # the other 17 should appear as count=0 with never-fired hint
    for i in range(15):
        log_path.open("a").write(json.dumps({
            "timestamp": f"2026-06-09T{10+i % 8:02d}:00:00Z",
            "mode": "csp",
            "decision": "abort",
            "triggered_threshold": "vix_too_low_cheap_vrp",
            "snapshot_hash": f"hash_{i}",
        }) + "\n")
    stats = calibrate(log_path=str(log_path))
    assert stats["total_decisions"] == 15
    # Every threshold in ALL_TRIGGER_NAMES must appear in fire_count
    assert "freshness_stale_snapshot" in stats["per_threshold_fire_count"]
    assert stats["per_threshold_fire_count"]["freshness_stale_snapshot"] == 0
    # Tuning hints should call out the un-fired ones
    never_fired_hints = [h for h in stats["tuning_hints"] if "NEVER FIRED" in h]
    assert len(never_fired_hints) > 5, (
        f"calibrate should flag never-fired thresholds; got {len(never_fired_hints)} "
        f"hints from {len(stats['per_threshold_fire_count'])} thresholds"
    )


def test_audit_log_includes_snapshot_hash(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setattr("scripts.entry_timing.AUDIT_LOG_PATH", str(log_path))
    snap = {**BASE_SNAPSHOT,
            "snapshot_taken_at": datetime.now(timezone.utc).isoformat()}
    decide(snap, mode="csp")
    parsed = json.loads(log_path.read_text().strip().splitlines()[0])
    assert "snapshot_hash" in parsed
    assert len(parsed["snapshot_hash"]) == 16  # 16 hex chars


# Need json import at top of test file:
import json
```

- [ ] **Step 12.2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_entry_timing.py -v -k "audit_log or calibrate"
```

Expected: 2 fails (audit log not written / `calibrate` not defined).

- [ ] **Step 12.3: Implement audit log + calibrate**

In `scripts/entry_timing.py`, modify `decide()` to write audit log before returning. Wrap the current logic:

```python
def decide(snapshot: dict[str, Any], mode: str) -> dict[str, Any]:
    """Return one of: enter_now, wait_eod, wait_minutes, abort.

    Side effect: appends JSONL line to AUDIT_LOG_PATH (best-effort).
    """
    for step in (
        _day_specific_override,
        lambda s: _aggressive_mode_vix_check(s, mode),
        _step1_vix_gate,
        lambda s: _step2_premarket_gap(s, mode),
        _step3_gex_state,
        _step4_odte_flow,
    ):
        result = step(snapshot)
        if result is not None:
            _write_audit_log(snapshot, mode, result)
            return result
    final = _step5_mode_window(snapshot, mode)
    _write_audit_log(snapshot, mode, final)
    return final


import hashlib


# Full set of threshold trigger names (kept in sync with branch labels
# in _step1_vix_gate / _step2_premarket_gap / _step3_gex_state /
# _step4_odte_flow / _step5_mode_window / _day_specific_override /
# _aggressive_mode_vix_check / _check_snapshot_freshness).
ALL_TRIGGER_NAMES = (
    "vix_event_backwardation", "vix_too_low_cheap_vrp",
    "premarket_gap",
    "gex_short_flip_proximity",
    "odte_put_buyer_imbalance",
    "mode_window_morning", "mode_window_morning_pending",
    "mode_window_morning_missed", "mode_window_eod",
    "fomc_presser", "monday_open_unwind",
    "opex_friday_pin_csp", "opex_friday_anchor_max_pain",
    "aggressive_mode_vix_cap",
    "freshness_stale_snapshot", "freshness_missing_timestamp",
    "freshness_invalid_timestamp",
    "none",
)


def _write_audit_log(snapshot: dict, mode: str, decision: dict) -> None:
    """Append one JSONL line to AUDIT_LOG_PATH. Silently no-op if path unwritable.

    `snapshot_hash` = SHA-256 of canonical-ordered snapshot_summary (spec §8.4).
    Lets calibrate() detect duplicate decisions on the same input (orchestrator
    bug or re-run) without false-positive 'threshold fired N times'.
    """
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
        snapshot_summary = {
            k: snapshot.get(k) for k in
            ("spot", "vix", "vix1d", "vix9d", "premarket_gap",
             "net_dealer_gex", "gex_flip", "odte_put_premium",
             "odte_call_premium", "is_fomc_day", "is_monday_open",
             "is_opex_friday", "snapshot_taken_at")
        }
        snap_hash = hashlib.sha256(
            json.dumps(snapshot_summary, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]  # 16 hex chars = 64 bits; collision-safe for audit log
        line = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "decision": decision["action"],
            "triggered_threshold": decision.get("triggered_threshold", "unknown"),
            "snapshot_hash": snap_hash,
            "snapshot_summary": snapshot_summary,
        }
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(line) + "\n")
    except (OSError, PermissionError):
        pass  # audit log is best-effort


def calibrate(log_path: str | None = None) -> dict[str, Any]:
    """Walk audit log, return per-threshold fire counts + tuning hints.

    Seeds with ALL_TRIGGER_NAMES so never-fired thresholds appear with
    count=0 + 'never fired' hint (spec gap #8 — calibrate() must report
    these to flag over-loose thresholds that catch nothing)."""
    path = log_path or AUDIT_LOG_PATH
    fire_count: dict[str, int] = {t: 0 for t in ALL_TRIGGER_NAMES}
    total = 0
    unique_snapshots: set[str] = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total += 1
                snap_h = entry.get("snapshot_hash", "")
                if snap_h:
                    unique_snapshots.add(snap_h)
                t = entry.get("triggered_threshold", "unknown")
                fire_count[t] = fire_count.get(t, 0) + 1
    tuning_hints = []
    duplicate_count = total - len(unique_snapshots) if unique_snapshots else 0
    if duplicate_count > 0:
        tuning_hints.append(
            f"{duplicate_count} duplicate-snapshot decisions detected — "
            "orchestrator may be calling decide() multiple times on the same input"
        )
    for t, c in fire_count.items():
        pct = c / total if total else 0
        if c == 0 and total > 10:
            tuning_hints.append(
                f"threshold {t!r} NEVER FIRED in {total} decisions — "
                "consider tightening (raise the bar) or removing entirely"
            )
        elif pct > 0.5 and t not in ("mode_window_morning", "mode_window_eod"):
            tuning_hints.append(
                f"threshold {t!r} fires {pct * 100:.0f}% — consider loosening"
            )
    return {
        "total_decisions": total,
        "unique_snapshot_count": len(unique_snapshots) if unique_snapshots else None,
        "per_threshold_fire_count": fire_count,
        "tuning_hints": tuning_hints,
    }
```

- [ ] **Step 12.4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_entry_timing.py -v
```

Expected: all tests pass.

- [ ] **Step 12.5: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py tests/test_entry_timing.py
git commit -m "feat(entry_timing): JSONL audit log + calibrate() with tuning hints"
```

---

### Task 13: CLI entrypoint

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py`

- [ ] **Step 13.1: Add CLI to entry_timing.py**

Append to `scripts/entry_timing.py`:

```python
def _cli() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Entry timing decision tree")
    sub = parser.add_subparsers(dest="cmd", required=True)

    decide_p = sub.add_parser("decide", help="Run decision tree on a snapshot JSON file")
    decide_p.add_argument("--snapshot", required=True, help="Path to snapshot JSON")
    decide_p.add_argument("--mode", required=True,
                          choices=["csp", "rut_calendar", "rut_protective", "rut_aggressive"])

    cal_p = sub.add_parser("calibrate", help="Aggregate audit log thresholds")
    cal_p.add_argument("--log", default=None)

    args = parser.parse_args()
    if args.cmd == "decide":
        with open(args.snapshot) as f:
            snap = json.load(f)
        out = decide(snap, mode=args.mode)
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.cmd == "calibrate":
        stats = calibrate(log_path=args.log)
        json.dump(stats, sys.stdout, indent=2)
        sys.stdout.write("\n")


if __name__ == "__main__":
    _cli()
```

- [ ] **Step 13.2: Smoke test the CLI**

```bash
cat > /tmp/snap.json <<'EOF'
{
  "spot": 2300.0, "time_et": "10:00",
  "vix": 14.0, "vix1d": 13.5, "vix9d": 14.0,
  "premarket_gap": 0.003,
  "gex_flip": 2250.0, "net_dealer_gex": 1.0e9,
  "odte_put_premium": 4.0e6, "odte_call_premium": 4.0e6,
  "is_fomc_day": false, "is_monday_open": false, "is_opex_friday": false
}
EOF
cd /Users/chenxi/projects/option-wizard
.venv/bin/python -m scripts.entry_timing decide --snapshot /tmp/snap.json --mode csp
```

Expected: JSON output with `"action": "enter_now"` (in morning window, all gates passed).

- [ ] **Step 13.3: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/entry_timing.py
git commit -m "feat(entry_timing): argparse CLI with decide + calibrate subcommands"
```

---

## Phase D — Backtest harness — DEFERRED to v1.1

Originally Tasks 14-19 (scripts/backtest_index_premium.py + tests).
**Cut from v1 scope** per Pass-6 user decision: backtest is afterthought
priority vs the P0 pieces (CSP/diagonal pricer, entry timing, docs).
With zero live trades yet, BSM-on-synthetic-data backtest results carry
near-zero weight in actual decisions; build it when N ≥ 10 real trades
have accumulated so v1.1 design has real outcome data to validate against.

v1.1 design (deferred): per spec §13 backlog — paired-trade attribution +
real historical chain mids + automated stats (Sharpe, max_dd, regime
stratification) with proper survivorship-bias-free design.

---

## Phase E — Deep reference doc + final wiring (2 tasks)

### Task 14: Write `references/index-premium-selling.md`

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/references/index-premium-selling.md`

- [ ] **Step 14.1: Create the file with all 8 sections**

Create `plugins/option-wizard/skills/option-wizard/references/index-premium-selling.md` with the following structure. Use the section content directly from spec §6.

```markdown
# Index Premium Selling — Workflow 2b Reference

Workflow 2b sub-flow for selling premium on US-equity index underlyings:
CSP on QQQ/SPY, put diagonal calendar on RUT (3 modes). Sibling of
Workflow 2a (macro hedge); shares 8-layer L0-L5 data spine from
`analysis-runbook.md`, diverges at L6 (structure pick) and L7 (preflight).

## 1. When to use

**Trigger phrases:**
- Chinese: `"QQQ CSP"` / `"SPY 卖 put"` / `"RUT diagonal"` / `"卖 index premium"`
- English: `"qqq csp"` / `"spy put"` / `"rut diagonal"` / `"sell index premium"`

**Workflow 2a vs 2b boundary:** 2a buys protection (macro hedge), 2b
sells premium. Both share L0-L5 data pull; never call both in one turn
without explicit user intent (buying hedges while selling premium reads
the same VRP/GEX state with opposite conclusions, and conflating them
loses signal).

**Out of scope (defer to other workflows):** PB structured products
(Workflow 4/5), single-name CSP (Workflow 1), VIX options
(separate v2 backlog).

## 2. Source discipline (index-specific)

- **UW**: IV rank, VRP label (via `scripts.vrp::compute_vrp`), GEX
  by strike (via `get_greek_exposure_by_strike` → `scripts.gex_levels`),
  0DTE flow per expiry, max pain
- **TV** (via `finance-data-providers:tradingview-reader`): spot,
  SMA(20/50/200), RSI(14), VIX & VIX1D & VIX9D term, news / catalyst
  headlines
- **IB** (live trade mode): chain mid via `get_options_chain` (when
  decision <60s), `get_account_summary` for buying power

Forbidden: UW `get_extended_technical_indicator` (lagged); IB for IV
rank / skew / GEX (IB doesn't compute these).

## 3. CSP on index ETF (QQQ / SPY / IWM)

**Legs:** short 1 OTM put + cash = strike × 100.

**Entry condition:** `IV rank ≥ 20 AND VRP ∈ {NEUTRAL, RICH}`. The
lower threshold than single-name (≥ 50) is justified because index
sell-premium edge comes from VRP (structural risk premium), not idio
compensation. Single-name CSP uses 50 because idio risk dominates.

**DTE:** 30-45. **Δ target:** 0.20-0.30 (more OTM than single-name
because index tail is fatter).

**Strike anchor:** put wall from `scripts.gex_levels::compute_levels`,
not 200DMA. Put wall is where dealer hedging is concentrated; spot
tends to mean-revert from below the put wall.

**Sizing:** Single contract notional ≤ 5% NLV; total index CSP notional
≤ 25% NLV.

**Refused:**
- SPX naked CSP (notional > $300k per contract, sizing violation even
  if cash-covered)
- IWM when bid-ask > $0.10 — use RUT options for better fills

**Preflight:** `scripts.ib_order::build_preflight` direct.

## 4. RUT put diagonal — three modes

All modes: long 45DTE put @ Kl + short 1-2DTE put @ Ks. Max loss at
short-leg expiry = `max((Ks − Kl) × 100, 0) − net credit`. Calendar
mode collapses to long put extrinsic decay (no width term).

| Mode | Strike layout | Default Δ | Regime fit |
|---|---|---|---|
| **calendar** | Ks = Kl | both 0.30 | NEUTRAL vol + expected IV term contango deepening |
| **protective** | Ks < Kl | Kl 0.30, Ks 0.15 | bearish bias + RICH vol |
| **aggressive** | Ks > Kl | Ks 0.30, Kl 0.15 | bullish RICH vol; VIX < 25 hard limit |

**Greeks character at entry:**
- calendar: θ+, ν+, γ ≈ 0
- protective: θ+, ν+, Δ slightly negative
- aggressive: θ++, ν+, Δ slightly positive

**Abandon conditions per mode:**
- calendar: switch to protective if VRP becomes RICH or short leg
  drifts ITM by ≥ 1 listed strike (RUT $5)
- protective: continue rolling unless long-leg DTE < 21
- aggressive: hard abort if VIX ≥ 25 (entry_timing returns abort);
  switch to protective if VIX rises into 22-25 zone mid-position

**Pricer:** `scripts.diagonal_calendar::build_diagonal_calendar(spot,
mode, snapshot, ...)`. Returns legs + net debit + max loss +
breakeven + net greeks (entry + at short expiry pinned) + roll matrix
across 7 spot scenarios + regime_check.

## 5. Entry timing decision tree

5-step tree, command-order; first hit returns. Day-specific overrides
(below) take priority above all 5 steps.

### Decision tree

```
1. VIX gate
   - VIX1D > VIX > 18 AND VIX1D/VIX9D > 1.05 → ABORT (event-driven backwardation)
   - VIX < 12 AND VRP = CHEAP → ABORT (no risk premium)

2. Premarket gap (09:15 ET, ES/NQ futures)
   - |gap %| > 1.0% (QQQ/SPY) or > 1.5% (RUT) → WAIT 30 min, re-evaluate

3. Dealer GEX state (UW)
   - Net dealer GEX < 0 AND |gamma_flip − spot| / spot < 1% → WAIT_EOD

4. 0DTE flow (UW flow_per_expiry, same-day expiry)
   - put_premium / call_premium > 3.0 → WAIT (whale put-buyer)

5. Mode-specific entry window
   - QQQ/SPY CSP (30-45 DTE)        → morning 09:45-10:30 ET
   - RUT calendar mode               → EOD 15:30-15:55 ET
   - RUT protective mode             → morning 09:45-10:30 ET
   - RUT aggressive mode             → EOD 15:30-15:55 ET only

Day-specific overrides (priority above steps 1-5)
   - FOMC presser day (pre-14:00 ET): WAIT until 14:30 ET
   - Monday open: WAIT 30 min (weekend gamma unwind)
   - OPEX Friday afternoon: favor EOD, anchor short strike to max pain
```

### v0 threshold table

| Threshold | v0 default | Provenance / tuning direction |
|---|---|---|
| `vix_abort_high` | 18 | CBOE median for backwardation; sellers in 20+ regime regularly may raise to 22 |
| `vix_event_ratio` | 1.05 | Buffer above 1.0 to skip noise |
| `vix_abort_low` | 12 | VIX 5th-pct historically |
| `gap_wait_pct` | 0.010 (QQQ/SPY) | ≈ 40% of 1 ATR |
| `gap_wait_pct_rut` | 0.015 | RUT intraday range higher |
| `gex_flip_proximity` | 0.010 | Spotgamma / Tier1Alpha published "danger zone" |
| `odte_put_buyer_ratio` | 3.0 | First-draft heuristic; calibrate via backtest |
| `aggressive_mode_vix_cap` | 25 | RUT 1d expected ≈ 1.6% at VIX 25, ATM 1DTE EV ≈ 0 |

All thresholds live in `THRESHOLDS` dict at top of
`scripts/entry_timing.py`. Audit log at
`references/private/market/entry-timing-log.jsonl`. Use
`scripts.entry_timing --calibrate` after N ≥ 10 decisions to see
which thresholds fire (over-tightening waste signal; under-tightening
catches nothing).

## 6. Roll & exit rules

### Short leg (1-2DTE)

- **Daily roll:** at expiry-day −1h, call
  `scripts.diagonal_calendar.build_short_leg_roll(existing_position,
  new_dte_short=1, snapshot, days_elapsed)` → returns close-old +
  open-new legs at new Δ matching mode default, plus
  `action_required` ∈ {roll_short, close_all_long_dte_too_short,
  switch_mode}.
- **Mode-drift switch:** if calendar mode short put now ITM by ≥ 1
  RUT listed strike width ($5), `action_required = 'switch_mode'`
  with `switch_mode_recommendation = 'protective'`. Trader confirms;
  next roll opens at protective Δ.

### Long leg (45DTE → 21DTE close)

- Hard rule #4: at 21 DTE remaining, force close to avoid long-leg
  gamma. `build_short_leg_roll` returns
  `action_required = 'close_all_long_dte_too_short'` when long DTE
  threshold hit. Trader closes long leg + most-recent short leg, then
  reopens full structure with fresh 45DTE long if continuing.

### Brackets

- TP: 50% of net debit captured (long leg mark + accumulated short
  credit cover ≥ 50% of initial debit).
- SL: long-leg mark drops > 30% of entry cost (long-leg only — short
  leg is replaced daily, no SL on short leg).

## 7. Book-level risk monitoring

- **Vega aggregation across diagonal positions:** each long-leg vega
  is positive (long vol); summing 5 RUT diagonals = 5× single-position
  vega exposure. Surface in Workflow 3 (positions review) book-level
  stats.
- **Net Δ contribution:** calendar mode ≈ 0; protective/aggressive
  contribute meaningful Δ. Beta-adjust to NLV when total options book
  Δ > 0.5 NLV (Workflow 2a hedge trigger).
- **Overlap with Workflow 2a macro hedge book:** RUT protective leg is
  long RUT put = small macro hedge equivalent. Don't double-count: if
  Workflow 2a sized SPX hedge assuming no incidental hedge, the
  protective leg over-hedges. Reconcile in book review.

## 8. Worked examples (live 2026-06-08 snapshot)

All four examples use real UW pulls from 2026-06-08 close. Trader can
re-run by pulling fresh snapshots and feeding through `build_diagonal_calendar`
/ `build_preflight`. Numbers are tagged with `data_provenance: UW screener +
GEX endpoint, 2026-06-08`.

### 8.1 QQQ CSP — NEUTRAL VRP, IV rank HIGH bucket

**Snapshot (UW 2026-06-08):** Spot $716.07; IV30d 23.9%; IV rank 61
(HIGH); RV 23.7% → VRP = −0.2pp = NEUTRAL ✓ (passes entry gate);
put wall $714; call wall $722; max pain 2026-07-10 (~31 DTE) at $730;
SPY VIX-proxy ~ 16 → vix_abort gates clear.

**Structure:** 0.25Δ put, 35 DTE → `_strike_for_put_delta(716.07, 0.25, 35/365, 0.239)` ≈ **$686**.
Snap to listed $1-spaced strike = $686.

**Credit (BSM):** ≈ $8.40/share = **$840/contract**.

**Sizing:** notional cap $50k ÷ ($686 × 100) = 0.73 contracts → 1 contract.
Cash reserve required: $68,600.

**Preflight:**
- Max loss: $68,600 − $840 = **$67,760**
- Max gain: $840
- Breakeven: $686 − $8.40 = **$677.60**
- Bracket: TP exit at mid $4.20 (50% of credit retained), SL exit at mid $25.20 (3× credit = 2× credit loss)

**Caution:** Strike $686 is **below put wall $714** by $28 — deeper OTM
than ideal. Per §3 anchor rule, conservative trader would tighten to
0.30Δ (closer to put wall) or move to 0.20Δ (further out for safer
delta exposure). $686 is the "math says here" answer, not the operational
final.

**Entry timing:** Normal weekday morning window 09:45-10:30 ET → `enter_now`
(assuming dealer GEX positive, no premarket gap > 1%, no FOMC day).

### 8.2 RUT diagonal calendar mode — NEUTRAL VRP

**Snapshot (UW 2026-06-08, RUT proxy via IWM × 10):** Spot ≈ 2841;
IV30d 23.3%; IV rank 38 (MID); RV 22.6% → VRP = −1.4pp = NEUTRAL ✓ for
calendar; iv_atm_short ≈ 0.235 (1-2 DTE rich vs ATM; v0 limit #10 notes
the systematic underestimate); iv_atm_long ≈ 0.233; max pain 2026-07-17
(~38 DTE) at $2900 → above spot, mild upward bias signal.

**Structure:** Mode = `calendar`. Kl = Ks (per Task 5 fix).
- Kl at 0.30Δ 45 DTE: `_strike_for_put_delta(2841, 0.30, 45/365, 0.233)` ≈ **$2745**
- Snap to nearest RUT $5-spaced strike = **$2745**
- Ks = Kl = $2745

**Mids (BSM):** Long 45 DTE @ 2745 ≈ $59.00; short 1 DTE @ 2745 ≈ $1.20.

**Net debit:** ($59.00 − $1.20) × 100 = **$5,780**.

**Max loss:** = net_debit = **$5,780** (calendar both worthless at S >> $2745).

**Net greeks at entry:** Δ ≈ −0.02 (calendar is delta-neutral by design);
θ ≈ +$40/day (short 1-DTE theta dominates); ν ≈ +$110/1pp IV (long
45-DTE vega).

**Entry timing:** Calendar mode targets **EOD window 15:30-15:55 ET**.
Decision tree returns `wait_eod` if called outside that window. Short
leg rolls each EOD to next 1-2 DTE same strike.

### 8.3 RUT protective mode — bearish lean

**Snapshot:** Same 2026-06-08 base. Trader has bearish lean from L3 TV
analysis (RSI extended). Mode = `protective`.

**Strikes:**
- Kl at 0.30Δ 45 DTE ≈ **$2745**
- Ks = Kl × (1 − 0.025) = 2745 × 0.975 = **$2676** (anchor-based per
  Task 5 fix; 1-2DTE Δ-based would produce Ks > Kl which violates
  protective layout)
- Snap Ks to nearest RUT $5-spaced strike = **$2675**

**Mids (BSM):** Long 45 DTE @ 2745 ≈ $59.00; short 1 DTE @ 2675 ≈ $0.30
(deep OTM 1-day put has minimal premium).

**Net debit:** ($59.00 − $0.30) × 100 = **$5,870**.

**Max loss:** = net_debit = **$5,870** (close-everything at short expiry;
worst case S > Kl, both worthless. The width (Kl − Ks) × 100 = $7,000
does NOT add — when S < Ks both legs are ITM and offset dollar-for-dollar
in the [Ks, Kl] range. Spec §10 #1.)

**Roll matrix scenarios** (close at short expiry):
- Spot −10% (2557): long mark ≈ $190 → net_pl ≈ +$5,500 (long pays)
- Spot 0% (2841): long mark ≈ $58 → net_pl ≈ −$50 (theta-eaten)
- Spot +5% (2983): long mark ≈ $25 → net_pl ≈ −$3,370 (long decays)

**Entry timing:** Protective targets **morning window 09:45-10:30 ET**
(needs early stop-level setting). Decision tree may abort if dealer
GEX short + flip vicinity to spot.

### 8.4 RUT aggressive mode — bullish RICH vol with VIX < 25

**Snapshot:** Same base, but trader sees bullish setup (gap-up
absorbed, RSI building). Note: IV rank 38 is MID not HIGH bucket;
aggressive ideally wants RICH VRP. v0 framework warns but doesn't
abort. Mode = `aggressive`.

**Strikes:**
- Kl at 0.15Δ 45 DTE: `_strike_for_put_delta(2841, 0.15, 45/365, 0.233)` ≈ **$2550**
- Snap to nearest $5 = **$2550**
- Ks at 0.30Δ 1 DTE: `_strike_for_put_delta(2841, 0.30, 1/365, 0.235)` ≈ **$2811**
- Snap to nearest $5 = **$2810**

**Mids (BSM):** Long 45 DTE @ 2550 ≈ $19.00; short 1 DTE @ 2810 ≈ $5.50.

**Net cash:** ($19.00 − $5.50) × 100 = **$1,350 net debit**.

**Max loss:** (Ks − Kl) × 100 + net_debit = (2810 − 2550) × 100 + $1,350
= **$27,350**. (At S → 0, long pays $2550 intrinsic [discounted to
$2540 with 4% rate × 43d], short pays $2810 intrinsic, net loss = $270
× 100 + $1,350.)

**Aggressive mode VIX check:** SPY IV30d 15.6% → VIX ~ 16, well under
the 25 cap → `aggressive_mode_vix_cap` does NOT abort.

**Entry timing:** Aggressive **EOD-only** (15:30-15:55 ET). Decision
tree rejects morning entry for this mode (short ATM 1DTE put intraday
gap risk not worth marginal theta).

**Warning to surface:** IV rank 38 (MID bucket) doesn't match the
aggressive mode's RICH-bucket recommendation → `regime_check.warning`
populated, trade proceeds at trader's discretion.

---

**Data provenance (all 4 examples):** UW 2026-06-08 close via
`get_company_info` + `get_stock_screener` + `get_greek_exposure_by_strike`
+ `get_max_pain`; IV/strike computations via BSM (v0 — chain mid path
would supersede when available via `build_diagonal_calendar(chain=…)`).
```

- [ ] **Step 14.2: Verify file size and section count**

```bash
wc -l plugins/option-wizard/skills/option-wizard/references/index-premium-selling.md
grep -c "^## " plugins/option-wizard/skills/option-wizard/references/index-premium-selling.md
```

Expected: ~250 lines, 8 section headings.

- [ ] **Step 14.3: Commit**

```bash
git add plugins/option-wizard/skills/option-wizard/references/index-premium-selling.md
git commit -m "docs(index-premium-selling): 8-section deep reference with entry timing decision tree"
```

---

### Task 15: Final sanity + branch wrap-up

**Files:**
- All

- [ ] **Step 15.1: Run full test suite**

```bash
cd /Users/chenxi/projects/option-wizard
.venv/bin/pytest tests/ -v
```

Expected: all tests pass, including pre-existing ones (no regressions).

- [ ] **Step 15.2: Run end-to-end smoke for each new CLI**

```bash
# Diagonal calendar pricer
.venv/bin/python -c '
from scripts.diagonal_calendar import build_diagonal_calendar
snap = {"iv_atm_short": 0.28, "iv_atm_long": 0.30, "iv_rank": 35, "vrp_label": "NEUTRAL"}
out = build_diagonal_calendar(spot=2300.0, mode="calendar", snapshot=snap)
print("mode:", out["mode"], "net debit:", out["net_debit_dollar"],
      "regime ok:", out["regime_check"]["matches_chosen_mode"])
'

# Entry timing
.venv/bin/python -m scripts.entry_timing decide --snapshot /tmp/snap.json --mode csp

# Threshold calibration (after N >= 10 audit log entries)
.venv/bin/python -m scripts.entry_timing calibrate
```

Expected: both produce valid JSON output. (Backtest deferred to v1.1 — no smoke test here.)

- [ ] **Step 15.3: Verify SKILL.md changes don't break skill loading**

```bash
.venv/bin/python -c "
content = open('plugins/option-wizard/skills/option-wizard/SKILL.md').read()
assert 'Index premium selling' in content
assert 'scripts.diagonal_calendar' in content
assert 'scripts.entry_timing' in content
print('SKILL.md wiring OK')
"
```

Expected: prints "SKILL.md wiring OK".

- [ ] **Step 15.4: Push branch and open PR**

```bash
git push -u origin feature/index-premium-selling
gh pr create --title "feat: Workflow 2b index premium selling (CSP + RUT diagonal + backtest)" \
    --body "$(cat <<'EOF'
## Summary

- Adds Workflow 2b: index premium selling sub-flow
- CSP on QQQ/SPY (IV rank ≥ 20 + VRP ≠ CHEAP entry gate)
- RUT put diagonal calendar with 3 modes (calendar / protective / aggressive)
- Entry timing decision tree (morning vs EOD, dealer GEX + 0DTE flow + day overrides)
- v0 BSM backtest harness with IS/OOS split + slippage + regime stratification + gating attribution

## Design

`docs/superpowers/specs/2026-06-09-index-premium-selling-design.md`

## Plan

`docs/superpowers/plans/2026-06-09-index-premium-selling.md`

## Test plan

- [ ] `pytest tests/` all green
- [ ] Manually verify diagonal_calendar pricer against IB chain mid for one RUT structure
- [ ] Run entry_timing decide on a real snapshot from a live UW pull
- [ ] Run backtest grid on real historical data (post-merge, with fetch_historical_data implemented per v1 backlog)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 15.5: No commit needed at this stage (Phase E is doc-only after Task 14)**

Branch is ready for review. CI runs on PR.

---

## Mode string mapping (entry_timing ↔ diagonal_calendar)

The two scripts use DIFFERENT mode strings — orchestrator (skill prompt)
MUST translate or implementer will get silent bugs.

| Workflow 2b context | `entry_timing.decide(mode=…)` | `build_diagonal_calendar(mode=…)` |
|---|---|---|
| QQQ/SPY CSP | `"csp"` | N/A (uses `build_preflight` direct) |
| RUT calendar mode | `"rut_calendar"` | `"calendar"` |
| RUT protective mode | `"rut_protective"` | `"protective"` |
| RUT aggressive mode | `"rut_aggressive"` | `"aggressive"` |

**Implementation requirement:** add a shared `MODE_TRANSLATION` dict in
`scripts/entry_timing.py` (or new `scripts/_index_premium_modes.py`) that
maps entry_timing strings → diagonal_calendar strings. SKILL.md
script-invocation example must use entry_timing mode strings in the
`decide()` call and diagonal_calendar mode strings in the `build()` call,
with the orchestrator translating between them.

Reasoning for the split: entry_timing's mode tells it which window to
target (CSP morning vs RUT-diagonal EOD), so CSP needs to be in its
namespace even though it doesn't have a diagonal counterpart.
diagonal_calendar's mode names what structure to build, ticker-agnostic.

---

## Known v0 limitations (post Pass-6 scope reduction)

Items resolved by Pass-6 v0 scope reduction (deleted from backtest):
~~DTE calendar/trading-days~~ (fixed via `_calendar_offset_days`);
~~short-leg every-row settle~~ (fixed via `cal_offset_since_short_open`);
~~Sharpe denom~~ / ~~max_dd_pct peak div~~ / ~~gating_attribution control
arm bias~~ / ~~entry_window attribution~~ (all DELETED — v0 ships
trades + equity_curve only).

Remaining issues to fix during implementation:

**Diagonal calendar pricer (Task 4-9):**

1. **Max-loss formulas ignore long-put discount carry at S→0.** True
   long-put mark at S=0 = `Kl·e^(-r·T_remain)`, not `Kl`. For 43-day
   remaining at r=4%: discount ≈ 0.47% of Kl. On RUT Kl=2240 that's
   ~$1,053 per contract. Calendar/protective max loss is understated.
   **Fix:** add `+ kl * (1 - math.exp(-_R * t_remain)) * 100 * qty`
   to max_loss for calendar and protective. v0 acceptable approximation;
   document in docstring.

2. **Chain-path BSM greeks recompute instead of consuming chain greeks.**
   Per hard rule #2 "if a source serves it directly, never recompute".
   When `chain[expiry][strike_pct][right]` contains `greeks`, use them.
   **Fix:** check chain leg for greeks dict; only call `_bs_put_greeks`
   if missing.

3. **Roll-matrix monotonicity test too lax.** Only checks 2 points
   (P/L(-10%) > P/L(0%)) for protective; diagonal P/L is non-monotonic
   around the strike cluster. **Fix:** assert sign-change-count ≤ 2
   across the 7 scenarios for each mode.

4. **Tests round-trip the implementation.** `test_calendar_max_loss_equals_net_debit`
   asserts `max_loss == net_debit_dollar` — true tautologically given
   `_max_loss_at_short_expiry` returns exactly that for calendar mode.
   **Fix:** add independent BSM payoff verification (price both legs at
   S = spot * 1.5 and confirm net P/L ≥ -max_loss within tolerance).

**Entry timing (Task 10-13):**

5. **OPEX Friday override documented in spec §6.1 but not implemented.**
   **Fix:** add `is_opex_friday` branch in `_day_specific_override`.

6. **No freshness check on `snapshot.time_et`.** Spec §10 #7 requires
   decide() to reject snapshots > 15 min stale. **Fix:** add staleness
   validation at decide() entry.

7. **Audit log line missing `snapshot_hash` (spec §8.4 requires it).**
   **Fix:** add `hashlib.sha256(json.dumps(snap_summary, sort_keys=True))`.

8. **`calibrate()` cannot report never-fired thresholds.** It only
   aggregates triggers found in the log. **Fix:** seed iteration with
   full `THRESHOLDS` keys; report 0-count thresholds with hint
   "never fired — consider tightening or removing".

**Backtest scope acknowledgments (intentional v0 simplifications):**

9. **No automated stats.** Sharpe / max_dd / win_rate / regime
   stratification / gating attribution all NOT computed. User runs
   `quantstats` on `equity_curve` and pandas groupby on `trades` in
   jupyter. v1 backlog: paired-trade design enables clean automated
   attribution.

10. **Short leg IV uses `atm_iv_30d` (fixture limitation).** Real 1-2DTE
    ATM IV is usually higher (weekend/event premium). Systematic
    understatement of short credit. v1 backlog: pull `atm_iv_1d` series.

11. **No intraday entry-window differentiation.** "Morning vs EOD"
    comparison is the trader's explicit question, but fixture provides
    one IV/spot per day. v1 backlog: intraday data + per-window simulation.

**SL formula clarity (Task 15):**

12. **`sl_target = credit * (1 + sl_pct)` parameter name ambiguous.**
    `sl_pct=2.0` correctly implements "exit when loss = 2× credit",
    which means exit-mark = 3× credit (you owe 3× to close after
    collecting 1×). **Fix:** rename `sl_pct` →
    `sl_loss_multiple_of_credit` and add docstring example.

**Input validation (Task 4):**

13. **No validation for `spot<=0`, `strike<=0`, non-finite, `iv<=0`,
    `t<=0`.** `_bs_put_greeks` handles `t<=0` and `sigma<=0`; add
    explicit `ValueError` for negative spot/strike at entry of
    `build_diagonal_calendar`.

14. **No sanity check on iv_atm_short vs iv_atm_long.** If swapped at
    snapshot construction time, pricing silently wrong. **Fix:** add
    `if abs(iv_short - iv_long) > 0.30: warn(...)` at entry of
    `build_diagonal_calendar` (real catalyst inversions ≤ ~20pp;
    ±30pp is almost always operator error).

**Pass-3 adversarial findings (orchestration + path-dependence):**

15. **Max loss ignores long-leg vol crush.** Closed-form max_loss assumes
    IV unchanged from entry to short expiry. Real vol crush can cut long
    mark by 30-50% on its own. v0 acceptable; document in
    `build_diagonal_calendar` docstring: "max_loss assumes IV stable;
    realized worst case under vol crush can exceed this by ~30% of
    long-leg cost".

16. **Aggressive mode VIX cap is entry-only, no exit rule.** Position
    opened at VIX 22 stays open even if VIX spikes to 28 mid-life.
    **Fix in Workflow 2b L7+:** add a daily monitoring step that flags
    open aggressive positions when VIX ≥ `aggressive_mode_vix_cap`.

17. **SHORT_STRIKE_OFFSET_PCT fixed at 0.025 regardless of IV regime.**
    In IV 50% regime, 2.5% offset is < 0.5σ — protective mode degenerates
    to near-calendar. **Fix:** make offset IV-scaled, e.g.,
    `offset_pct = max(0.015, min(0.05, 0.5 * iv_atm_long * sqrt(dte_long/365)))`.

---

## Self-Review Checklist (run before declaring plan complete)

- [x] **Spec coverage:** Every spec section §1-§14 maps to one or more tasks above.
  - §1 Goal → Tasks 1-21 (whole plan)
  - §2 Non-goals → enforced by absence of tasks for screener / Monte Carlo / SPX naked CSP
  - §3 File structure → Task table at top of plan
  - §4 Workflow 2 split → Task 1
  - §5 strategies.md → Task 2
  - §6 reference doc → Task 14
  - §7 diagonal_calendar.py → Tasks 4-9
  - §8 entry_timing.py → Tasks 10-13
  - §9 backtest → DEFERRED to v1.1 (Pass-6 user decision)
  - §10 hard rules → enforced by tests (max_loss bounded, regime_check, audit log) + manual review on PR
  - §11 testing plan → tests written in each task (sans backtest)
  - §12 phase plan → Phases A-C + E (Phase D deferred)
  - §13 backlog → enumerated in spec
  - §14 acceptance → Task 15 final checks (renumbered from 21)

- [x] **Placeholder scan:** No TBD / TODO / "add error handling" / "similar to Task N" patterns. Every step has actual code or actual command.

- [x] **Type consistency:** `Mode = Literal['calendar', 'protective', 'aggressive']` used consistently in diagonal_calendar.py. Output dict keys (`net_debit_dollar`, `pricing_source`, `regime_check`, `roll_matrix`, `breakevens_at_short_expiry`) consistent between diagonal_calendar.py output and tests.

- [x] **Function signatures match:** `build_short_leg_roll(existing_position, new_dte_short, snapshot, days_elapsed)` signature consistent between Task 9 implementation and Task 9 tests.
