---
type: Framework
title: Decision Doctrine — reasoning phases, aggression tiers, crowding check, adversarial QC
description: How evidence becomes a decision — define the decision, competing hypotheses, disconfirmation + crowding check (incl. mandatory escalation when crowding fires alongside a scheduled binary catalyst), ≥2-structure comparison, aggression tiers (PROBE→EXCEPTIONAL with a 5% NLV max-loss hard cap), dynamic risk re-rating, 12-class missing-data taxonomy, adversarial QC checklist, and the 决策块 final decision block.
tags: [decision-doctrine, sizing, aggression-tiers, crowding, contrarian, adversarial-qc, scenarios, invalidation]
timestamp: 2026-07-03T14:00:00Z
---

# Decision Doctrine

Reasoning discipline for every actionable recommendation. The runbook
layers (`analysis-runbook.md`) gather the evidence; this file governs how
evidence becomes a decision. Fires for: ticker analyses (Layer 6–7), any
listed-options trade recommendation, macro-hedge sizing, and book-review
action items. Does NOT apply to FCN / AQ / DQ (own frameworks, hard rule
#5) or pure data lookups.

The objective is the highest-quality decision, not the longest report.

## Phase discipline

Run these phases before writing the recommendation. They are internal —
the visible output leads with the conclusion, not the phase trail.

**A. Define the decision.** Name the actual choice: enter now vs wait ·
close / hold / roll · hedge vs de-risk · which structure. "No trade" is
always a candidate. Never analyze broadly without a named decision.

**B. Evidence.** Hard rules #2 (source discipline) and #7 (live-first
freshness) — the runbook layers are the evidence pass; nothing new here.

**C. Competing hypotheses.** Build at minimum: bull / base / bear /
vol-up / vol-down / no-trade. One line each: what current evidence
supports it, what would confirm it. The recommendation must name the base
case and say why the others lose — never a thesis plus a token risk
paragraph. Attach a rough probability to each hypothesis (e.g. "base 55% /
bear 30% / tail 15%") — a number the trader can disagree with beats a
qualitative label no one can falsify or argue against.

**D. Disconfirmation + crowding check.** Actively try to kill the
preferred thesis: contradictory tape, conflicting flow, surface signals
inconsistent with direction, catalyst risk, liquidity, stale data,
matching pitfalls (`pitfalls/index.md`), portfolio interactions. Then run
the crowding check (§below). Strengthen, shrink, postpone, or reject
based on what survives.

**E. Structure candidates.** Compare **≥2 economically distinct**
expressions (e.g. long call vs vertical vs risk reversal; CSP vs bull put
spread; collar vs put-spread overlay) on: direction/Δ · convexity/Γ · θ ·
vega · capital usage · max loss · catalyst sensitivity · portfolio fit.
Pick the best expression of the thesis — never the highest headline
yield. The `strategies.md` regime × structure matrix and the strong
bullish-conviction veto still gate the menu.

**F. Size via aggression tier** (§below).

**G. Management before entry.** Entry zone / preferred limit / max
acceptable price · TP rule · SL / thesis invalidation · time stop ·
catalyst rule · vol rule · roll criteria · explicit do-nothing conditions
· dynamic re-rating triggers (§below). A trade without a management plan
is incomplete.

## Aggression tiers

Stance: prudent by default, aggressive when evidence confirms. Aggression
buys **earlier entry, more directional structure, less confirmation,
top-of-band size** — never bigger max loss, never undefined risk (hard
rule #1).

Nine alignment conditions:

1. clear directional or volatility thesis
2. positive convexity or strongly favourable asymmetry
3. identifiable catalyst + timing
4. technicals, options structure, and portfolio context agree
5. liquidity sufficient (spread-% gates per `execution.md`)
6. objective, observable invalidation exists
7. max loss acceptable at the chosen size
8. correlation with the existing book controlled
9. expected return justifies the risk

| Tier | Max loss (% NLV) | Requires |
|---|---|---|
| NO_TRADE | — | default when EV is inadequate; name the trigger that would create the trade **and the shadow trade it activates** (§below) |
| PROBE | ≤ 1% | thesis interesting but ≤ 4 conditions, **or** evidence quality LOW |
| SMALL | 1–2% | ≥ 5 conditions, evidence ≥ MEDIUM |
| NORMAL | 2–3.5% | ≥ 6 conditions incl. #6 + #7, evidence ≥ MEDIUM |
| HIGH_CONVICTION | 3.5–5% | ≥ 8 conditions, evidence HIGH, explicit justification |
| EXCEPTIONAL | **5% hard cap** | all 9 conditions, evidence HIGH, justification + strongest-counter stated |

- The 5% NLV max-loss cap is absolute — EXCEPTIONAL never sizes past it
  (trader decision 2026-07-02). It buys timing and directionality, not
  more risk.
- Existing caps intersect: final size = min(tier band, 25% of
  `AvailableFunds`, margin reserve) per runbook Layer 6.
- **Conviction ≤ evidence quality.** Data confidence LOW caps the tier at
  PROBE regardless of how attractive the thesis looks.

## Crowding / consensus check (contrarian duty)

When consensus is one-sided, surfacing the other side is mandatory.
Crowded-optimism flags — **≥ 2 → the check fires**:

- spot at / near highs while IV rank < 30 (complacency carry)
- call skew rich or P/C flow heavily call-tilted (UW flow, call-heavy GEX)
- one-sided positioning: short interest washed out, OI concentrated in
  near-dated calls, dark-pool accumulation exhausted
- analyst ratings near-uniform buy on a crowded long narrative
- IV term structure unusually flat / compressed into a known catalyst
- breadth divergence (index highs on narrowing breadth) for index work

When it fires on a long-delta recommendation: write the **bear case
first**, state what the crowd is missing that justifies joining it, and
prefer convex defined-risk expressions over short-vol carry. Symmetric on
crowded pessimism: surface squeeze / upside risk before any bearish or
short-call recommendation.

### Crowding check × scheduled binary catalyst (mandatory escalation)

When the crowding check fires **and** a scheduled binary catalyst
(earnings, delivery/production print, FDA date, macro release) falls
inside the analysis window, a falling IV rank / compressed term structure
into that catalyst must **not** be read as a standalone bullish "market
isn't pricing risk" signal that overrides the crowding flag. IV rank
trend answers "is the options market charging a premium for this event" —
it does not answer "will the crowd's one-sided position get sold when the
event lands." Compressed IV plus one-sided positioning is the textbook
precondition for a "buy the rumor, sell the news" reversal — including on
a **beat**: crowded longs who already priced in a strong outcome have no
incremental buyer left once it prints, and no vol cushion to absorb any
narrative caveat (sustainability, margins, guidance) attached to the
headline number.

Required output when both conditions hold: a **two-sided reaction
scenario table** — beat-and-held / beat-and-sold / miss, each naming the
crowding-driven downside case explicitly — before letting the IV-rank
trend feed into the bull case. IV rank / term-structure evidence still
describes what the options market is pricing; it does not settle whether
the crowd itself will sell a good number. See pitfall
`06-crowded-into-catalyst-iv-rank-trap.md` (TSLA 2026-07-02 delivery
print — dealer gamma / price action / flow all one-sided bullish, IV rank
falling into the print, crowding check fired but the falling-IV-rank
reading was allowed to override it instead of triggering this escalation;
stock fell 7.5% on a delivery beat that topped every public estimate).

**Red line (general): once the crowding check fires, only positioning
evidence — flow / OI actually thinning — may downgrade it. An IV-level
argument (falling IV rank, compressed term structure) NEVER downgrades a
fired crowding flag, catalyst or not.** The catalyst case above is the
sharpest instance; the rule holds whenever crowding fires.

## Dynamic risk management

Risk posture is regime-conditioned, not set-and-forget:

- Every position carries escalation / de-escalation triggers defined at
  entry — e.g. dealer gamma flips sign through the strikes; VIX term
  structure inverts; IV rank leaves the band the structure was priced in;
  directional markout negative at T+5; catalyst date moves.
- Book reviews **re-rate each position's tier** against current evidence.
  A HIGH_CONVICTION entry whose alignment has decayed to ≤ 5 conditions is
  a de-risk action item even if P/L is fine.
- Never add size to defend a tier — no averaging down to preserve
  conviction.
- Hedge overlays are tiered decisions too, gated by
  `macro-hedge-convexity.md` regime gates and the 1.5% NLV carry cap.

## Missing-data classification

Extends hard rule #7. After the acquisition ladder (`data-sources.md`) is
exhausted, label every unresolved gap with one of:

`SOURCE_UNREACHABLE` · `AUTHENTICATION_FAILURE` · `SYMBOL_MAPPING_FAILURE`
· `NO_MARKET_COVERAGE` · `MARKET_CLOSED_NO_FROZEN_QUOTE` · `STALE_SOURCE`
· `PARSER_FAILURE` · `SCHEMA_MISMATCH` · `BROKER_RECONCILIATION_FAILURE` ·
`HISTORICAL_DATA_NOT_STORED` · `METRIC_NOT_OBSERVABLE` ·
`TEMPORARY_PROVIDER_ERROR`

Never collapse to a bare "no data" — the label goes in the Layer Coverage
table / gap report. **Recurring-gap rule:** the same label on the same
data point twice → engineering action item (I-item in book review, D-item
in 复盘) naming the failing source, frequency, decision impact, and
proposed fix. Persistent avoidable gaps are engineering defects, not
caveats.

## Adversarial QC (pre-delivery)

Before delivering any consequential analysis, verify:

- all relevant accounts pulled (IB + Futu per profile); quantities ×
  multipliers correct
- every quoted number carries source + timestamp (hard rules #2 / #7); no
  fabricated metric, no archive document mistaken for a broker trade
- max-loss arithmetic correct; margin verified
- **portfolio-incremental effect stated**: what the trade adds to book
  Δ / Γ / Θ / V, what it duplicates or hedges, and whether the same risk
  budget has a better use elsewhere
- the preferred structure beat ≥ 1 named alternative (Phase E)
- confidence matches evidence quality; invalidation is observable

Then answer: **"What is the strongest reason this recommendation is
wrong?"** — include the answer in the output when material.

## 决策块 — final decision block

Every substantive analysis closes with this block (before the Layer-7
preflight offer; for book reviews, atop the Action-items block as the
book-level verdict):

- **当前判断** — the market / portfolio view, falsifiable (level + horizon + condition), with the Phase C probability split (e.g. "base 55% / bear 30% / tail 15%")
- **我的行动** — the exact recommendation
- **进攻程度** — NO_TRADE / PROBE / SMALL / NORMAL / HIGH_CONVICTION / EXCEPTIONAL
- **赔率** — if 当前判断 plays out: gain vs max loss at the sized structure (or, for NO_TRADE, at the shadow trade below) — the number Phase F condition #9 (expected return justifies the risk) is actually checking
- **为什么现在** — the timing edge
- **最大风险** — the most important failure mode (the QC answer above)
- **失效条件** — observable invalidation
- **下一步触发器** — what data / price / vol / event forces reassessment
- **数据可信度** — HIGH / MEDIUM / LOW + the principal limitation

**Shadow trade (required whenever 我的行动 is weaker than 当前判断
supports)** — NO_TRADE, "wait", or any tier throttled by a constraint
unrelated to the thesis (e.g. hard rule #1's account-margin gate) must
still name the trade the evidence would otherwise justify: structure,
strikes, expiry, the tier it would have sized at, and the trigger that
lifts the constraint. Motivation: TSLA 2026-07-02 found dealer gamma,
term structure, and flow all aligned bullish, but the account-margin
constraint alone forced NO_TRADE — without a shadow trade recorded, the
underlying market judgment (which was independently verifiable and
correct) never enters the markout scoring pipeline, and 复盘 can only ever
ask "was NO_TRADE the right call" instead of "was the judgment underneath
it right." The shadow trade's direction is what goes in the archived
`calls:` entry (SKILL.md §"Reporting & archive") — `tier: NO_TRADE` on
that entry already records that it wasn't acted on; no schema change
needed, only the discipline of writing it down.

Falsifiability standard (feeds Layer A markout scoring in
`review-framework.md`): "NVDA looks constructive" is unscoreable; "over
the next 10 trading days NVDA holds > 165 and tests 175–180, unless 30-day
IV expands > 5 vol pts" is scoreable. Skip the block only for pure data
lookups / trivial answers.

**When the analysis gets archived** (trader says "save it"), encode every
falsifiable claim from the 决策块 as a `calls:` frontmatter entry (SKILL.md
§"Reporting & archive") carrying `tier` and the crowding-check result —
this is what lets 复盘 answer "did the PROBE-tier calls underperform
HIGH_CONVICTION?" and "does the crowding check improve hit rate?" instead
of only "was the direction right?".

## What stays fixed vs adaptive

The narrative adapts to the decision — verdict-first for time-critical
calls, deep structure for full analyses. Four skeletons never move:

1. Layer Coverage table opens every ticker analysis (hard rule #8)
2. Preflight + exactly one YES/NO before any order (hard rule #3)
3. Book-review action items at the END, all together (SKILL.md §Book-review output structure)
4. The 决策块 closes substantive analyses
