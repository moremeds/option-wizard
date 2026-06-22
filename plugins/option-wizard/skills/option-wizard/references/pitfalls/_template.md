---
type: Template
title: Pitfall template
description: Copy-source for a new Trading Pitfall concept. Copy everything below the marker into pitfalls/NN-slug.md and fill it in.
tags: [template, pitfall]
timestamp: 2026-06-03T05:51:05Z
---

Copy everything below the marker into `pitfalls/NN-slug.md`, fill it in, then
add a row to [`index.md`](index.md) and a dated entry to [`../log.md`](../log.md).
Strip all account-specific numbers (NLV, position sizes, fills) first.

--------8<-------- copy below --------8<--------

---
type: Trading Pitfall
title: "Pitfall NN: <one-line takeaway>"
description: <one-line relevance summary an agent reads to decide whether to load this file>
severity: HIGH | MED | LOW
appliesTo: <comma-separated trade types this rule guards>
tags: [<tag>, <tag>]
timestamp: <ISO 8601 UTC — git last-commit time of this file>
---

# Pitfall NN: <One-line takeaway>

**Date:** YYYY-MM-DD
**Ticker / structure:** <e.g., ORCL bull put spread>
**Loss / forgone gain:** <dollar or percent>

## What I did

Brief recap of the trade and the assumption that drove it.

## What actually happened

The market reaction or development that invalidated the assumption.

## Why the assumption was wrong

Root cause analysis. Be honest, not defensive.

## Rule going forward

One sentence. Specific enough that next time I would catch myself.
