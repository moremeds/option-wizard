---
type: Index
title: option-wizard Knowledge Base — Bundle Root
description: OKF v0.1 entry point for the option-wizard reference bundle — frameworks, runbooks, pitfalls, case studies, and source-discipline reference.
tags: [index, okf, bundle-root, options-trading]
timestamp: 2026-07-02T02:20:29Z
---

# option-wizard Knowledge Base

The curated knowledge bundle behind the `option-wizard` skill. It is an **[Open Knowledge Format (OKF) v0.1](OKF.md)** bundle: a graph of markdown concept files with YAML frontmatter, loaded lazily via the *situation → file* router in [`../SKILL.md`](../SKILL.md) §"When to read which file". That router is the primary lazy-load mechanism; this index and the per-file `description` frontmatter are the navigable / self-describing fallback.

## Conformance

- **[`OKF.md`](OKF.md)** — Open Knowledge Format conformance & mapping (type vocabulary, frontmatter schema, bundle conventions).
- **[`log.md`](log.md)** — chronological change history of this knowledge base.

## Frameworks — decision logic ("given regime X, pick Y")

| File | What it covers |
|---|---|
| [`decision-doctrine.md`](decision-doctrine.md) | How evidence becomes a decision: phases A–G, aggression tiers (PROBE→EXCEPTIONAL, 5% NLV max-loss hard cap), contrarian crowding check, dynamic risk re-rating, missing-data taxonomy, adversarial QC, 决策块 decision block. |
| [`strategies.md`](strategies.md) | Regime × structure matrix, strong-bullish-conviction veto, LEAPS stock replacement, position management, macro-hedge trigger heuristics. |
| [`gamma-framework.md`](gamma-framework.md) | Dealer GEX → gamma flip / put wall / call wall; oi_cluster vs aggregate for short-dated. |
| [`price-action-framework.md`](price-action-framework.md) | Orderbook microstructure mental model; tape / news / catalyst-clock validation. |
| [`macro-hedge-convexity.md`](macro-hedge-convexity.md) | Empirical convexity + regime gates for SPX / cross-index macro hedge sizing; 1.5% NLV cost cap. |
| [`index-premium-selling.md`](index-premium-selling.md) | QQQ/SPY CSP + RUT put-diagonal (Workflow 2b); entry timing. |
| [`aq-dq-framework.md`](aq-dq-framework.md) | PB Accumulator / Decumulator evaluation; 7 refusal red lines → checklist → fair value → counter-offer. |
| [`fcn-framework.md`](fcn-framework.md) | FCN / ELN coupon evaluation; strike ladder + bilingual counter-offer. |

## Runbooks — operational step-sequences ("do these steps in order")

| File | What it covers |
|---|---|
| [`workflows-overview.md`](workflows-overview.md) | Routing index for the 7 workflows (W1 ticker / W2a macro hedge / W2b index premium / W3 positions / W4 FCN / W5 AQ-DQ / W6 复盘) — **read first** to pick the workflow. |
| [`analysis-runbook.md`](analysis-runbook.md) | The 8-layer ticker-analysis spine; opens with the Layer Coverage table; honest gap reporting. |
| [`execution.md`](execution.md) | Pre-submission preflight + the single YES/NO gate; bracket defaults. |
| [`review-framework.md`](review-framework.md) | 复盘 weekly / monthly review; 3 independent layers; markout scoring; auto pitfall drafts. |

## Reference

| File | What it covers |
|---|---|
| [`data-sources.md`](data-sources.md) | Source discipline (xenon / UW / TV / ib_insync) + live-first freshness ladder + TV gotchas. |

## Pitfalls

**[`pitfalls/index.md`](pitfalls/index.md)** — analytical-bias rules (`Trading Pitfall`), one file per rule, with lookup-by-trade-type. Load individual `pitfalls/NN-*.md` files when a matching situation arises.

## Case studies

**[`ticker/index.md`](ticker/index.md)** — closed / example trade post-mortems (`Trade Case Study`): ORCL FCN, AQ worked example. Public, anonymized. Load when the current setup pattern-matches a prior case.

## Trader's private bundle

[`private/`](private/) is a second, parallel bundle (gitignored) for the trader's personal journal — single-name analyses (`ticker/`), macro calls (`market/`), and book reviews (`review/`), with a 30-day active-vs-cold-storage TTL. It holds raw account data, follows the same concept-=-file convention, and is never committed or conformance-checked. See [`../SKILL.md`](../SKILL.md) §"Reporting & archive".
