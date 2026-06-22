---
type: Index
title: Trading Pitfalls — Index
description: Lookup index for analytical-bias rules distilled from closed trades; load individual NN-*.md files by trade type.
tags: [index, pitfalls, biases]
timestamp: 2026-06-22T15:49:54Z
---

# Trading Pitfalls

Analytical mistakes and the rules they generated. One file per rule (`NN-slug.md`), designed for lazy loading — read individual files only when a matching situation arises. This is the OKF navigable index for this directory; see [`../OKF.md`](../OKF.md) for the format, [`../index.md`](../index.md) for the bundle root.

## Index

| # | Severity | Title | File |
|---|---|---|---|
| 01 | MED | Far-dated VIX call spreads track the VX future for that expiry, not spot VIX | [`01-vix-options-track-futures-not-spot.md`](01-vix-options-track-futures-not-spot.md) |
| 02 | MED | PB AQ quotes have no explicit yield — it is encoded in the strike discount | [`02-aq-pb-yield-is-implicit.md`](02-aq-pb-yield-is-implicit.md) |
| 03 | HIGH | Put ratio backspreads are short-skew premium capture, not tail hedges | [`03-ratio-backspreads-not-tail-hedges.md`](03-ratio-backspreads-not-tail-hedges.md) |
| 04 | HIGH | ER range structures — set strikes at entry, add a bearish-breakdown veto | [`04-er-range-structure-strike-staleness.md`](04-er-range-structure-strike-staleness.md) |
| 05 | HIGH | Macro prints are not single-name ER — buy the hedge BEFORE the print | [`05-macro-print-no-post-event-iv-crush.md`](05-macro-print-no-post-event-iv-crush.md) |

## Lookup by trade type

- **Macro / index hedge** → 03 (ratio backspreads), 05 (buy before the print), 01 (VIX futures mechanics).
- **Hedge timing / vol mechanics** → 05 (pre-event window), 01 (contango bleed).
- **Earnings vol-selling** → 04 (strike staleness + bearish-breakdown veto).
- **PB structured products (AQ/DQ)** → 02 (implicit yield).

## Adding a pitfall

1. Copy [`_template.md`](_template.md) to the next sequence number: `NN-slug.md`.
2. Fill the frontmatter (`type: Trading Pitfall`, `title`, `description`, `severity`, `appliesTo`, `tags`, `timestamp`) and the prose body.
3. Add a row to the index table above and the lookup-by-trade-type list.
4. Add a dated entry to [`../log.md`](../log.md).
5. **Strip all account-specific numbers** (NLV, position sizes, fills) before promoting from `private/`.

## Auto-generated drafts (复盘 workflow)

`scripts.retrospective` writes pitfall candidates to `_drafts/` (gitignored) for any analysis with a WRONG verdict. Each draft inherits the source analysis's ticker / date / call notes plus the markout data that scored it WRONG. The trader reviews each draft, strips account-specific numbers, fills in the **What went wrong** and **Rule going forward** sections, then promotes selected drafts to a numbered `NN-slug.md` here. Drafts not promoted stay in `_drafts/` as historical record.
