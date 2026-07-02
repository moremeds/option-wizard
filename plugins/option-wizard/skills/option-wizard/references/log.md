---
type: Changelog
title: option-wizard Knowledge Base — Change Log
description: Chronological history of the option-wizard reference bundle — frameworks, runbooks, pitfalls, and case studies added over time.
tags: [log, changelog, history]
timestamp: 2026-07-02T02:20:29Z
---

# Change Log

OKF reserved `log.md` — chronological history of this knowledge bundle, most recent first. Seeded from git history; append a dated entry whenever you add or materially revise a concept (see [`OKF.md`](OKF.md) conformance checklist). For the full commit-level history, `git log -- plugins/option-wizard/skills/option-wizard/references/`.

## 2026-07-02 — Decision doctrine

- Added [`decision-doctrine.md`](decision-doctrine.md): reasoning phases (competing hypotheses → disconfirmation → ≥2-structure comparison), aggression tiers with 9 alignment conditions (max loss hard-capped at **5% NLV at every tier**, per trader decision), mandatory contrarian crowding check, dynamic risk re-rating, 12-class missing-data taxonomy, adversarial QC checklist, and the 决策块 final decision block. Distilled from the trader's "ultimate market-structure agent" prompt; conflicts resolved in favor of hard rules #3 / #8 / #9 (fixed skeletons and 复盘 source separation stay).
- `SKILL.md`: new hard rule #10 (decision doctrine) + router row; `analysis-runbook.md` Layer 6 now runs doctrine phases C–F (hypotheses, crowding check, structure comparison, tier-based sizing) and closes with the 决策块.
- `review-framework.md`: four layer-mapped scoring dimensions (thesis / structure / process = Layer A, execution = Layer B, joins = Layer C judgment-only); pitfall promotion lifecycle (`OBSERVATION` → `CANDIDATE` → `ACTIVE` → `RETIRED`) with overfitting gate; removed the v0.2 "Discipline 4-quadrant" leftover from the output structure (contradicted hard rule #9).

## 2026-06-22 — OKF v0.1 alignment

- Adopted [Open Knowledge Format v0.1](OKF.md): added OKF-standard frontmatter (`type`, `title`, `description`, `tags`, `timestamp`) to every framework, runbook, pitfall, and case study, preserving each file's existing prose body.
- Added the reserved [`index.md`](index.md) bundle root, per-directory `index.md` indexes (with one-line `README.md` stubs), [`log.md`](log.md), and the [`OKF.md`](OKF.md) conformance & mapping document.
- Defined the option-wizard type vocabulary: `Framework` / `Runbook` / `Reference` extensions alongside upstream-identical `Trading Pitfall` / `Trade Case Study`.
- Pattern and `Trading Pitfall` / `Trade Case Study` types kept byte-identical to the upstream [trade-skills](https://github.com/himself65/trade-skills) bundle for paste-compatibility.

## Pre-OKF history (from git)

The bundle predates the OKF naming; these are the concept-level milestones reconstructed from git history.

- **2026-06-18** — `review-framework.md` / `workflows-overview.md` / `data-sources.md` updated (xenon Query API migration, freshness ladder).
- **2026-06-15** — `macro-hedge-convexity.md` empirical convexity framework + regime gates; pitfall 04 (ER range-structure strike staleness) + pitfall 05 (macro-print no post-event IV crush); `strategies.md` macro-hedge trigger heuristics.
- **2026-06-10** — `index-premium-selling.md` (Workflow 2b: CSP + RUT diagonal + entry timing); `aq-dq-framework.md`; pitfall 01 (VIX options track futures) + pitfall 03 (ratio backspreads not tail hedges).
- **2026-06-08** — `analysis-runbook.md` (8-layer ticker-analysis spine).
- **2026-06-06** — pitfall 02 (PB AQ implicit yield).
- **2026-06-05** — `ticker/aq-example-case.md` (AQ framework worked example).
- **2026-06-04** — `price-action-framework.md`.
- **2026-06-03** — Foundation: `strategies.md`, `gamma-framework.md`, `fcn-framework.md`, `execution.md`, `data-sources.md`, `ticker/orcl-2026-06-fcn.md`, pitfall/case-study templates.
