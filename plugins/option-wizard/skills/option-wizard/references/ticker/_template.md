---
type: Template
title: Case-study template
description: Copy-source for a new Trade Case Study concept. Copy everything below the marker into ticker/<slug>-YYYY-MM.md and fill it in.
tags: [template, case-study]
timestamp: 2026-06-03T05:51:05Z
---

Copy everything below the marker into `ticker/<slug>-YYYY-MM[-DD-event].md`, fill
it in, then add a row to [`index.md`](index.md) and a dated entry to
[`../log.md`](../log.md). Strip all account-specific numbers (NLV, cash, margin,
position-quantity, fills) — if the case relies on them, archive to `private/` instead.

--------8<-------- copy below --------8<--------

---
type: Trade Case Study
title: "<Ticker> — <Period> <one-line>"
description: <one-line relevance summary an agent reads to decide whether to load this file>
ticker: <TICKER>
event: <e.g., Q1 FY26 earnings / FCN quote evaluation>
date: YYYY-MM[-DD]
status: closed | open | in-progress | example
result: <outcome, anonymized>
structures: [<structure>, <structure>]
tags: [<tag>, <tag>]
timestamp: <ISO 8601 UTC — git last-commit time of this file>
---

# <Ticker> — <Period>

**Date:** YYYY-MM-DD
**Setup:** <one paragraph context>

## Data snapshot

| Metric | Value | Source |
|--------|-------|--------|
| Spot | $ | TV |
| IV rank | | UW |
| GEX flip | $ | derived |
| 5y max DD | | UW OHLC |

## Analysis

What the data said and the structure considered.

## Decision

What was done (or recommended) and why.

## Outcome / Lesson

Filled in after the position closes or 30 days later, whichever comes first.
