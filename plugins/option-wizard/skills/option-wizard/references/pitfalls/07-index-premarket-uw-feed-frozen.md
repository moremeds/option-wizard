---
type: Trading Pitfall
title: "Pitfall 07: UW futures_indices / market_tide are frozen pre-market — hit IB live FIRST for any index overnight/pre-market read"
description: For any index pre-market/overnight analysis, UW futures_indices and market_tide do not refresh outside RTH; pull IB ES front-month future + IB VIX index snapshot before forming any read, and treat a non-current updated_at as a gap.
severity: HIGH
appliesTo: index/大盘 pre-market analysis, macro hedge timing, any overnight or pre-open market diagnosis
tags: [freshness-gate, premarket, index, macro, data-sources, uw-staleness, live-first]
timestamp: 2026-07-08T00:00:00Z
---

# Pitfall 07: UW index feeds are frozen pre-market — go IB-live first

**Date:** 2026-07-08
**Ticker / structure:** SPX pre-market macro diagnosis / downside hedge
**Loss / forgone gain:** Near-miss — gave a "not late, market is calm, flat pre-market" read while SPX futures were already down ~1% and VIX was up ~15% on a Trump "Iran deal over" headline. The trader caught it, not the workflow.

## What I did

Opened the 分析大盘 (Workflow 2a) pull with UW `get_futures_indices` and
`get_market_tide` for the pre-market snapshot, read S&P 500 future ≈ 7546
(−0.07%) and VIX 17.58, and concluded "flat pre-market, vol not bid, this is
the calm window — not too late to hedge." Presented it as the live pre-market
state.

## What actually happened

Both UW feeds were **stale/frozen**: `futures_indices` was pinned to
`updated_at = 2026-07-07T23:22Z` (the prior evening) and never refreshed;
`market_tide` had **no 7/08 rows at all** (last bar 7/07 16:10 ET). Meanwhile a
real catalyst had hit overnight (Trump: Iran deal "over" → oil spike →
risk-off). A live IB pull showed **ES front −1.05% (7472, off an overnight high
of 7563)** and **VIX 18.51, +14.8% from 16.13** — i.e. the market had already
gapped **through** the 7500 gamma flip into the short-gamma shelf, and the
cheapest hedge window (VIX ~16, calm) was already gone. Only after the trader
pushed twice ("现在盘前已经低开了很多啊") did the freshness gate get walked and
the live IB ES + VIX snapshots get pulled.

## Why the assumption was wrong

UW's `futures_indices` and `market_tide` are RTH-oriented, cached endpoints —
outside regular hours they return the **last persisted RTH/settle snapshot**,
not a live overnight tick. Their `updated_at` timestamp said so plainly
(23:22Z), but the timestamp was not checked against "is this current?" before
the numbers were quoted. This is a direct violation of hard rule #7 (freshness
gate, live-first): a reachable live source (IB ES front-month future + IB VIX
index snapshot, both live in the overnight/pre-market session) existed and was
simply not pulled first. The self-check the rule mandates ("did I actually
call a live endpoint?") was skipped because the UW numbers *looked* like a
pre-market quote.

## Rule going forward

For ANY index overnight/pre-market read, pull the **live source FIRST** — IB
`get_price_snapshot` on the ES front-month future (`search_futures` under
underlying `ES` contract 11004968 → front `contract_month`, exchange CME) for
spot, and IB VIX index snapshot (contract 13455763, CBOE) for vol — *before*
touching UW `futures_indices` / `market_tide`, and treat any UW feed whose
`updated_at` is not the current RTH session as a **gap, not data** (do not
quote it as "pre-market"). UW stays canonical for the *structural* layer
(GEX-by-strike walls, flow, max pain, IV rank from the daily OHLC state) — but
never for the live overnight *spot/vol* print.
