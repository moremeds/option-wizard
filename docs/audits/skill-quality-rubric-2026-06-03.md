# Skill Quality Audit — option-wizard

**Date**: 2026-06-03
**Subject**: `plugins/option-wizard/skills/option-wizard/` (SKILL.md + references/ + scripts/)
**Rubric source**: [`himself65/finance-skills` — `plugins/skill-creator/skills/skill-creator/references/quality-rubric.md`](https://github.com/himself65/finance-skills/blob/main/plugins/skill-creator/skills/skill-creator/references/quality-rubric.md)
**Scoring**: 1–10 per dimension, 100 total. Rubric defines production threshold at 70+; top finance-skills entries score 80–90.

---

## Verdict

**74 / 100** — production-quality, above threshold.

Two dimensions drag the total: **Dim 5 (Dynamic Calling) 3/10** and **Dim 2 (Defaults Coverage) 6/10**. Fixing both would lift to ~82, putting option-wizard in the top-tier band.

| # | Dimension | Score | Benchmark (rubric) |
|---|---|---:|---|
| 1 | Trigger Quality (description field) | **8** | sepa-strategy = 9 |
| 2 | Defaults Coverage | **6** | options-payoff = 9 |
| 3 | Step Architecture | **7** | sepa-strategy = 9 |
| 4 | Reference File Strategy | **9** | sepa-strategy = 9 |
| 5 | Dynamic Calling & Runtime Adaptation | **3** | github-auth = 10 |
| 6 | Output Template | **7** | sepa-strategy = 9 |
| 7 | Error Handling & Missing Data | **8** | sepa-strategy = 8 |
| 8 | Code / Formula Quality | **8** | stock-correlation = 8 |
| 9 | SKILL.md Conciseness | **9** | options-payoff = 8 |
| 10 | Domain Accuracy | **9** | options-payoff = 9 |
| | **Total** | **74** | |

---

## Per-dimension justifications

### Dim 1 — Trigger Quality: **8/10**

Frontmatter description enumerates FCN coupon, vol-regime structure picks (CC / CSP / defined-risk spreads / jade lizard / collar), SPX hedge sizing, position management, IB order placement. Lists data sources (UW, TV, IB). Triggers section has 6 Chinese + 4 English entry phrases including sideways entries ("place this order", "review positions"). Domain-specific (FCN/ELN) phrasing is captured.

**Gap to 9–10**: missing beginner phrasing (e.g., "I got this options quote, is it fair?", "should I sell this put?"). Description is 320 words — within the 1024-char rubric ceiling, but heavy on technical terms. Adding 2–3 "lay" trigger phrases would lift to 9.

### Dim 2 — Defaults Coverage: **6/10**

Defaults exist but are **scattered across files**:
- Bracket order: 50% TP / 2× SL in `SKILL.md:40` hard rule #6
- FCN strike ladder: 70/75/80/85% in `references/fcn-framework.md` + `scripts/fair_coupon.py`
- Iron condor target: 30–45 DTE, ~16Δ in `references/strategies.md`
- VRP thresholds: ±5pp in `scripts/vrp.py`
- Macro hedge cost cap: 1.5% NLV in hard rule #5

No centralized defaults table. A trader (or Claude) wanting to know "what does option-wizard assume if I don't specify X" has to grep across 5+ files.

**Fix to reach 9**: add a `## Defaults` section to SKILL.md (or `references/defaults.md`) with one table: parameter | default | rationale | override syntax. Mirror options-payoff's pattern (11 parameters, 9/10 score).

### Dim 3 — Step Architecture: **7/10**

The 8-layer `analysis-runbook.md` IS the step architecture and it's strong — each layer has explicit pull / compute / decision sections and a "what to do if data is missing" path. But the SKILL.md frontmatter doesn't surface a `## Step 1`, `## Step 2` structure that the rubric weights. The runbook is loaded only when "full ticker analysis" triggers; for sideways triggers (FCN, position review, hedge sizing), the SKILL.md doesn't lay out a step sequence — the routing table just points to references.

**Fix to reach 9**: the runbook layers ARE the steps; promote them to SKILL.md as a "Standard 8-step pipeline" reference, with the routing table listing which steps apply per request type.

### Dim 4 — Reference File Strategy: **9/10**

Clean split. SKILL.md is 145 lines (post-H2 edit); references total 7 files between 4.7KB and 12.6KB, each focused on one topic (gamma, price action, FCN, execution, etc.). Scripts directory cleanly separates numeric work. No bloat in SKILL.md, no orphan references.

**Gap to 10**: pitfalls/ exists but is empty (tracked as H1).

### Dim 5 — Dynamic Calling & Runtime Adaptation: **3/10**

This is the weakest dimension by a wide margin.

The rubric: *"Skills MUST detect what tools, libraries, and auth are available at runtime and adapt their behavior accordingly. Never hardcode a single method."*

Current state:
- **No `` !`command` `` blocks in SKILL.md** — finance-skills uses these for "is yfinance reachable?", "what's the current SPX?", "is IB authed?". option-wizard does none of this.
- Scripts assume IB Gateway is up on port 4001 and UW MCP is reachable. Failure mode: mid-analysis exception, not a graceful "data source unreachable, here's what I can do" path.
- No fallback decision tree. The runbook says "if TV is unreachable, report the gap" — good — but doesn't say "if IB is unreachable, drop Layer 0 and pre-flight against a manually-supplied account snapshot".
- No `metadata.hermes.requires_tools` frontmatter to hide the skill when dependencies aren't installed.

**Fix to reach 8+** (highest-leverage upgrade in this audit):
1. Add a `!` detection block at SKILL.md top: check IB Gateway port 4001, UW MCP reachable, TV opencli installed + port. Three quick checks, ~50ms each.
2. Build the decision tree: each layer of the runbook gets `"if Layer N data source detected → use it; else → degrade as follows"`.
3. Add `required_environment_variables` frontmatter for UW token, IB credentials, Anthropic key.

This single dimension upgrade is worth more than all other dimension improvements combined for skill robustness.

### Dim 6 — Output Template: **7/10**

The preflight template in `SKILL.md:36–37` hard rule #3 is **exhaustively specified**: legs / mid / max loss / max gain / breakeven / margin / P/L matrix at 7 spot points / account verification / regime check / liquidity / catalyst clock / exactly one YES/NO. FCN output is also specified (8-item checklist + 70/75/80/85% strike ladder + verdict + bilingual email).

But: outputs are described in prose ("must show...") rather than as a numbered template ("Step N: Respond to the user with sections 1, 2, ..., 8"). Two runs of the skill could produce structurally different reports.

**Fix to reach 9**: add `## Step 8 / Final: Respond to the User` sections to `references/execution.md` and `references/fcn-framework.md` with literal markdown templates.

### Dim 7 — Error Handling & Missing Data: **8/10**

Strong. `analysis-runbook.md` §"Honest reporting of gaps" lists common gaps and the explicit reporting requirement. Scripts handle null UW data (`gex_levels.py::_sorted_by_strike` drops null GEX). TV setup gotchas document workarounds (opencli version, port 9222, stale process). Hard rule #4 (21 DTE) is a missing-data backstop.

**Gap to 9–10**: no graceful degradation pattern at the SKILL.md level. Currently the skill says "report the gap" but doesn't say "produce best-effort output with partial data". sepa-strategy's "proceed with what you have, flag RS as significant gap" is the pattern to copy.

### Dim 8 — Code / Formula Quality: **8/10**

Scripts are clean Python 3.13: type hints, focused single-purpose modules, no IO inside computational functions (the orchestrator fetches; pure functions compute). Tests exist (`tests/`). Black-Scholes work in `fair_coupon.py` for FCN. GEX flip math in `gex_levels.py` is documented in `references/gamma-framework.md` with the linear-interpolation formula.

Not audited deeply: numerical accuracy vs. independent verification, edge cases on `compute_vrp` thresholds.

**Gap to 9–10**: no in-script docstring examples that double as doctests. Some module-level docs are sparse.

### Dim 9 — SKILL.md Conciseness: **9/10**

Post-H2 edit: ~145 lines. Under the 250 target. Routing table is the densest section but still tabular and scannable. Hard rules are 6 numbered items, terse.

**Gap to 10**: trim the script invocation examples in §"How to invoke scripts" — currently 60+ lines of inline Python — by moving to `references/scripts-runbook.md`. Would drop SKILL.md to ~100 lines.

### Dim 10 — Domain Accuracy: **9/10**

Defined-risk discipline, 21 DTE rule, gamma flip computation, IV-RV VRP, FCN strike ladder, per-expiry call wall (vs aggregate), opencli port collision recovery — all consistent with sophisticated active-trader practice. Caveats are correctly placed (e.g., "0DTE GEX skew makes flip drift several dollars intraday; use morning anchor"). FCN framework reflects how Asian private banks actually structure these products (auto-call observation, KI, coupon vs vol).

Per the rubric: *"Highly accurate, edge cases documented, disclaimers appropriate"* — yes. Could be used by a domain practitioner.

**Gap to 10**: no explicit disclaimer in SKILL.md (README has one). The rubric's 10 reserved for "could be used as a reference by domain practitioners" — that's met.

---

## Prioritized recommendations

Ranked by score-lift per effort:

1. **Dim 5: add runtime detection** (~3 hours) — `!` blocks for IB / UW / TV reachability, decision tree per layer, `required_environment_variables` frontmatter. Lifts Dim 5 from 3 → 8 (**+5**).
2. **Dim 2: centralize defaults** (~1 hour) — single `## Defaults` table or `references/defaults.md`. Lifts Dim 2 from 6 → 9 (**+3**).
3. **Dim 6: numbered output templates** (~1 hour) — literal markdown templates in `execution.md` and `fcn-framework.md`. Lifts Dim 6 from 7 → 9 (**+2**).
4. **Dim 3: promote runbook layers to SKILL.md steps** (~30 min) — already done in references; mirror as a SKILL.md outline. Lifts Dim 3 from 7 → 9 (**+2**).
5. **Dim 9: trim scripts examples** (~30 min) — move to references/scripts-runbook.md. Lifts Dim 9 from 9 → 10 (**+1**) and clears SKILL.md headroom for items 1 + 4 above.

**Total potential lift**: 74 → 87 with ~6 hours of work. Item 1 alone is worth half the lift and is also the most-impactful for skill robustness in live trading sessions (failure mode shifts from "mid-analysis exception" to "graceful adaptation to unreachable data source").

Out-of-scope for this audit (separate H1 finding): backfill `references/pitfalls/` from trade history. That's a content task, not a skill-architecture task — won't move the rubric score but is the highest user-facing improvement.

---

## Re-audit cadence

Re-run this audit after each priority recommendation lands. Target ≥ 85 by next acceptance gate.
