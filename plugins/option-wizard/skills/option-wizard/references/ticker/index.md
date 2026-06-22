---
type: Index
title: Ticker Case Studies — Index
description: Lookup index for public, anonymized trade / analysis case studies; load when the current setup pattern-matches a prior case.
tags: [index, case-studies, ticker]
timestamp: 2026-06-22T15:49:54Z
---

# Ticker Case Studies

Trade or analysis post-mortems. Each file documents one decision, the data behind it, and the outcome (`<slug>-YYYY-MM.md` or `<slug>-YYYY-MM-DD-<event>.md`). This is the OKF navigable index for this directory; see [`../OKF.md`](../OKF.md) for the format, [`../index.md`](../index.md) for the bundle root.

**Public case studies only** — anonymized, no account-specific NLV / position / fill numbers. The trader's personal journal (with full account data) lives in [`../private/`](../private/) (gitignored).

## Index

| File | Ticker | Period | Status | Structures | One-line |
|---|---|---|---|---|---|
| [`orcl-2026-06-fcn.md`](orcl-2026-06-fcn.md) | ORCL | 2026-06 | closed | fcn | FCN strike ladder + gamma-flip insight |
| [`aq-example-case.md`](aq-example-case.md) | MEGA-S (synthetic) | 2026-06 | example | aq | Labeled-synthetic AQ-framework worked example |

## Adding a public case study

1. Copy [`_template.md`](_template.md) to `<slug>-YYYY-MM[-DD-event].md`.
2. Fill the frontmatter (`type: Trade Case Study`, `title`, `description`, `ticker`, `event`, `date`, `status`, `result`, `structures`, `tags`, `timestamp`) and the prose body.
3. **Strip all account-specific numbers** (NLV, cash, margin, position-quantity, fills). If the case relies on those numbers, archive to `private/` instead.
4. Capture the framework insight that generalizes (the `orcl-2026-06-fcn` case is the model — it teaches the gamma-flip rule without exposing account data).
5. Add a row to the index table above and a dated entry to [`../log.md`](../log.md).

For personal trade journals (with full account data), see `../private/`.
