---
type: Reference
title: Data Sources — source discipline & freshness ladder
description: Source discipline taxonomy — xenon (account state + live mid / L2 / greeks, no client-side BSM) / UW (options-analytics aggregates + analytical greeks) / TV (spot + technicals) / ib_insync (execution + fallback greeks); the live-first freshness ladder; TV setup gotchas.
tags: [data-sources, source-discipline, freshness, xenon, unusual-whales, tradingview, ib]
timestamp: 2026-06-18T13:09:06Z
---

# Data Sources

## Source split (SKILL.md hard rule #2)

**Strict, non-negotiable split:**

| Domain | Source | Forbidden alternative |
|---|---|---|
| Spot, OHLCV, daily/intraday candles, volume bars | **TV** via `finance-data-providers:tradingview-reader` | UW `get_company_info`, chain `price_data` (for "live spot"), `get_ticker_candles_by_range` (for analysis-grade technicals) |
| SMA(20/50/200), EMA, RSI(14), MACD, BBANDS, ATR | **TV** | UW `get_extended_technical_indicator`, `get_ticker_indicator_series` — **banned for L3 analysis**; chronic multi-week staleness was the root cause of the 2026-06 NVDA / QQQ / SPY analyses being degraded to extrapolation |
| IV rank, RV (UW computed), 25Δ skew, IV term structure | **UW** | TV (does not serve these) |
| Max pain, GEX-by-strike, greeks-by-strike, interpolated IV (analytical mode) | **UW** | — (UW exclusive) |
| Flow alerts, flow per expiry, dark pool prints | **UW** | — (UW exclusive) |
| Account state (positions, balances, margin, orders, fills) — IB **and** Futu | **xenon** Query API (`/portfolio`, `/futu/portfolio`, `/orders`, `/blotter`, `/journal`, `/performance`) | IB MCP read tools / Futu `portfolio-analyser` CLI = **documented fallback only** |
| Live mid / NBBO / L2 liquidity | **xenon** `/market-depth` | — |
| Live per-contract greeks / IV (live-trade mode) | **xenon** `/options/greeks` (IB `modelGreeks`) → **ib_insync `reqMktData`** fallback | **client-side BSM — forbidden**; UW analytical greeks are a cross-check, not the live source |
| Regime state history (IV-rank / gamma-flip / HY-OAS time series for 复盘) | `references/private/market/regime-log.jsonl` — written daily by `scripts.regime_snapshot` cron | UW serves point-in-time snapshots only; it is not a substitute for the persisted daily log — this file is the **only** IV-rank history that exists |

## Freshness gate + live-first acquisition (SKILL.md hard rule #7)

Every quoted number must be the **most accurate currently-obtainable** value,
pulled **live at the moment of analysis** — not a prior-session close, a
converted prior-day technical, or an extrapolation. The xenon Query API
(`XENON_BASE`, key `XENON_KEY`, header `X-API-Key`) makes live data
acquirable at any time: account/positions/orders/blotter/journal/performance,
`/market-depth` (live NBBO + L2), and `/options/greeks` (live greeks/IV — IB
frozen mode returns them around the clock).

**Per-data-point acquisition ladder** — try in order; declare a gap only after
every rung fails or returns empty:

| Data point | Ladder |
|---|---|
| Spot (equity, RTH) | TV live → xenon `/market-depth` underlying mid → UW chain `price_data` |
| **Index spot (pre-market / overnight)** | **IB `get_price_snapshot` on the front-month index future FIRST** — ES (underlying `11004968`, exchange CME) / NQ / RTY, via `search_futures` → earliest non-expired `contract_month` → snapshot `last`+`bid_ask`. Then TV `CBOE:SPX` live for the cash read. **UW `get_futures_indices` / `get_market_tide` are RTH-cached — outside regular hours they return the last settle snapshot, NOT a live tick. Check `updated_at` / the latest bar's timestamp; if it is not the current RTH session it is a GAP, never quote it as "pre-market".** (Pitfall 07.) |
| **Index VIX (pre-market / overnight)** | **IB `get_price_snapshot` on VIX index FIRST** (contract `13455763`, exchange CBOE) — live tick around the clock. UW `get_futures_indices` VIX field is RTH-cached (frozen overnight — same `updated_at` check). |
| Option IV / per-strike greeks | xenon `/options/greeks` → UW `interpolated_iv`/`greeks_by_strike` → ib_insync `reqMktData` |
| 25Δ skew / IV term | live `/options/greeks` strike+expiry sweep → UW `historical-risk-reversal-skew`/`iv_term_structure` |
| IV rank / RV | UW (exclusive — no rebuild) — for a **historical daily series** (not just today), `iv_rank(ticker)` alone only returns the trailing ~5 rows; walk `_get(f"/api/stock/{t}/iv-rank", params={"date": D})` with `D` stepped weekly across the target window and merge by `date` (see review-framework.md 复盘 Layer A vol-regime markout). This was misdiagnosed as "no historical endpoint exists" in the 2026-07-01 monthly skill audit — the endpoint takes a `date` param, it just wasn't tried. |
| GEX by strike/expiry/ticker | UW by-strike-expiry → by-strike → by-ticker (exclusive) |
| Max pain / dark pool / flow | UW (exclusive) |
| Technicals (RSI/SMA/EMA/MACD/ATR/BBANDS) | TV live **today** — never a converted prior-day value |
| VIX / VIX9D / VXN / VVIX | TV exchange codes (`CBOE:VIX`, `CBOE:VIX9D`, `CBOE:VXN`/`NASDAQ:VXN`, `CBOE:VVIX`) → **IB `get_price_history`** (`security_type="IND"`, `exchange="CBOE"`) with `contract_id`: VIX 13455763, **VIX9D 322592334**, **VVIX 105068053**, VXN 13455757 (all `search_contracts security_type=IND` verified live 2026-07-02) → UW → derive front-end IV from `/options/greeks` on SPX/QQQ near-term. This closes the macro-hedge regime-gate gap flagged in the 2026-07-02 macro archive (`snapshot["regime_check"]` in `scripts.macro_hedge::build_macro_hedge` needs vix9d/vvix and only VIX itself was filled — the TV exchange-prefix path fails for these symbols, but IB resolves them directly). |
| Account / positions / orders / fills | xenon `/portfolio` `/futu/portfolio` `/orders` `/blotter` → IB MCP / Futu CLI fallback |

**Exhaust-before-gap + self-check.** Before writing any "STALE / 未重拉 / gap"
caveat, self-check: *Did I actually call the live endpoint? Did I try
alternative symbols / exchange codes / endpoint variants / other sources,
including the xenon live surface?* A caveat is permitted only after a
**documented** attempt across the ladder, and must state **what was tried**
(e.g. "UW GEX-by-strike-expiry empty for SPX 6/19; tried by-strike and
by-ticker, both empty — genuine UW gap"), never a bare "未重拉".

- **Avoidable gap** (live source existed and was reachable but not pulled —
  stale chains, converted RSI, wrong VIX exchange code, **or a cached/RTH feed
  read outside its session**): **not acceptable.** A feed returning a *number*
  is not the same as a *live* number — a value with a stale `updated_at` (e.g.
  UW `futures_indices` / `market_tide` overnight) is a gap disguised as data.
  **Always verify the timestamp before quoting; never present a cached value as
  the live/pre-market state.** (Pitfall 07.)
- **Genuine gap** (no source serves that slice): flag honestly, characterize
  by what was tried; the remedy is to acquire live, never to extrapolate or
  convert a stale number into a "today" value (no fabrication).

Surface freshness explicitly: xenon IB `last_sync`; Futu `is_stale` /
`fetched_at` / `data_as_of`; UW `price_data.date` / chain `last_price.date`;
UW indicator endpoints run 2-6 weeks behind — **banned** for daily-fresh
technicals (use TV). If a number cannot be brought current, list it under
"What this analysis is missing" and do not extrapolate it into the decision.

## UW options-data policy

Any numeric **options** metric Unusual Whales serves directly is fetched
from UW, not recomputed client-side. UW's options/exposure data is
sourced from exchange feeds we don't have, and rebuilding it from
Yahoo/IB would silently introduce error. This UW-first policy applies
**only to the options-data domain** above — not to price or technicals.

Endpoints we consume (one method per endpoint in
`scripts/_clients/uw.py::UWClient`):

| UW path | UWClient method | Used for |
|---|---|---|
| `/api/stock/{t}/iv-rank` | `iv_rank(t)` | Vol regime + IV-rank checklist item |
| `/api/stock/{t}/volatility/realized` | `realized_volatility(t)` | VRP input |
| `/api/stock/{t}/historical-risk-reversal-skew` | `historical_risk_reversal_skew(t)` | Skew penalty in FCN checklist |
| `/api/stock/{t}/volatility/term-structure` | `iv_term_structure(t)` | Bullish-conviction veto signal (inversion) |
| `/api/stock/{t}/max-pain` | `max_pain(t)` | Strike anchor for monthly options |
| `/api/stock/{t}/spot-exposures/strike` | `spot_gex_by_strike(t)` | GEX-by-strike for level derivation |
| `/api/stock/{t}/interpolated-iv` | `interpolated_iv(t)` | Strike-specific IV for non-listed barriers |
| `/api/stock/{t}/greeks` | `greeks_by_strike(t)` | Position Greeks for candidate strikes |
| `/api/darkpool/{t}` | `dark_pool(t)` | Off-exchange print pressure |
| ~~`/api/stock/{t}/technical-indicator/{fn}`~~ | ~~`technical_indicator(t, fn)`~~ | **BANNED for L3 analysis** — chronic staleness (typically 2-6 weeks behind). Use TV instead. Method retained only for legacy callers; do not introduce new usage. |

All paths verified live against ORCL on 2026-06-03 (see
`scripts/smoke/uw_smoke.py` and `tests/integration/test_uw_smoke.py`).
Every endpoint returns `{"data": ...}` at the top level; `max_pain`
also returns `"date"`. Unwrap `resp["data"]` before parsing.

## Client-side derivations

UW does not pre-compute these named levels, so option-wizard derives them
from the raw UW payloads:

| Derived metric | Source | Code |
|---|---|---|
| Gamma flip | UW `spot-exposures/strike` (cumulative GEX zero crossing) | `scripts/gex_levels.py::compute_levels` |
| Put wall | UW `spot-exposures/strike` (largest +GEX strike below spot) | `scripts/gex_levels.py::_put_wall` |
| Call wall | UW `spot-exposures/strike` (largest −GEX strike above spot) | `scripts/gex_levels.py::_call_wall` |
| VRP | UW `iv-rank` (IV30 proxy) − UW `volatility/realized` | `scripts/vrp.py::compute_vrp` |
| FCN fair coupon (single) | UW `iv-rank` IV + closed-form barrier touch | `scripts/fair_coupon.py::single_name_ki_prob` / `fair_coupon_proxy` |
| Worst-of basket KI prob | UW IVs + correlation matrix + Monte Carlo | `scripts/fair_coupon.py::joint_ki_prob_mc` |

Example: with IV=0.804, 6-month tenor (~126 trading days), and a 75%
barrier, `single_name_ki_prob(0.804, 0.75, 126)` returns ≈0.613 — i.e.,
~61% probability of touching the barrier under continuous monitoring
(an upper bound; actual FCN discrete observation reduces this).

## TradingView role

TradingView covers what UW doesn't: realtime spot during the session,
candlestick visuals, chart-level technical analysis, and curated news.
Entry point is the `finance-data-providers:tradingview-reader` skill —
do not reimplement scraping in this project.

Typical calls:

- "TV snapshot ORCL daily, last 30 days, with SMA20/SMA50/SMA200" — for
  trend regime context before strike selection.
- "TV RSI 14 ORCL daily, last 90 days" — for overbought signal at
  current spot.
- "TV news ORCL last 7 days" — for catalyst clock and headline review.

The TV reader returns rendered text snapshots; consume them as
qualitative inputs, not numeric overlays. Numeric vol/skew/GEX still
comes from UW.

## IB role

**State reads now go through the xenon Query API first** (`/portfolio`,
`/futu/portfolio`, `/orders`, `/blotter`, `/journal`, `/performance` — both
brokers, one read-only surface; see Source split + Freshness gate above). The
IB MCP read tools below are the **documented fallback** when xenon is
unreachable. Option **execution** is unchanged — it stays on `ib_insync`.

IB MCP is **read-only for state, equity-only for writes**. Verified via
`scripts/smoke/ib_mcp_findings.md` against the live `claude.ai` IBKR
connector on 2026-06-03:

- `get_account_summary`, `get_account_balances`, `get_account_positions`,
  `get_account_orders`, `get_account_trades` — read-only state.
- **Known issue (observed 2026-06-14): `get_account_positions` can fail
  MCP output-schema validation** when IB returns `daily_pnl` as a string
  for any single position (error: `/positions/N/daily_pnl: string found,
  number expected`). This drops the **entire** positions payload, not just
  the offending row. Fallback: keep going with `get_account_summary` for
  account-level state (NLV / margin / buying power) + the Futu-side book
  (or the most recent good IB snapshot) for the position list, and surface
  the failure as an **Infrastructure (I-item) data gap**. Never report an
  empty IB book as "no positions" — distinguish "pull failed" from "flat".
- **IB option trades carry no strike / expiry / right.** `get_account_trades`
  returns only `{symbol, sec_type, side, size, price, trade_time,
  realized_pnl}` per leg, so a multi-leg option fill (e.g. an SPX 4-leg
  package) is direction-ambiguous on its own. To classify it, cross-
  reference `get_account_orders` / `get_account_positions` for the same
  symbol+timestamp, or `search_contracts` the option; if it can't be
  resolved, label the leg "direction inferred" rather than asserting it.
- `create_order_instruction` — supports **Equity and ETF orders only**;
  produces a **draft** that the user must approve in the IBKR app via
  deep-link. No OCA / no parent-child orders at the MCP layer.

All option execution (CC, CSP, spreads, condors, jade lizard) goes
through `ib_insync.IB.placeOrder` from Python directly. Brackets are
attached via `ib_insync.bracketOrder(...)` which returns three linked
`Order` objects with OCA semantics handled in `ib_insync`. See
`references/execution.md` for the full execution playbook.

## Call order for a fresh analysis

The standard sequence for evaluating a ticker for a new position
(parallel-where-possible; the per-layer freshness gate must pass for
each pull before its number is quoted):

1. **xenon account context** — `XenonClient.ib_portfolio()` (net liq, buying
   power, maintenance margin via `account_summary`; positions via `positions[]`)
   + `futu_portfolio()` for any existing exposure in the same name across both
   brokers. IB MCP `get_account_summary` / `get_account_positions` is the
   fallback. (Layer 0)
2. **UW vol regime** — `iv_rank`, `volatility/realized`,
   `volatility/term-structure`, `historical-risk-reversal-skew`. Computes
   VRP, term inversion flag, skew penalty. (Layer 1-2)
3. **UW GEX + max pain** — `spot-exposures/strike` per expiry +
   `max_pain`. Pipe through `gex_levels.compute_levels_per_expiry` with
   `call_wall_definition='oi_cluster'` for the trade window. (Layer 1)
4. **TV chart + technicals** — `opencli tradingview chart-state` for live
   spot, daily candles, volume bars; pull SMA(20/50/200), RSI(14), MACD,
   BBANDS, ATR overlays from TV. **Never use UW for these.** (Layer 3,
   SKILL.md hard rule #2)
5. **TV news** — `opencli tradingview news --symbol NASDAQ:<T> --limit 8`
   for catalyst-clock validation + bullish-veto signals 1-3. (Layer 3 + 5)
6. **UW flow + dark pool** — `get_flow_alerts`, `get_flow_per_expiry`,
   `get_dark_pool_trades`. (Layer 4)
7. **UW interpolated IV + greeks** at candidate strikes — `interpolated_iv`
   and `greeks_by_strike(ticker, expiry=...)` once the strategy module
   has picked the candidate strikes. (Layer 6 input)

When the answer is "no position" or "wait for a different setup", you
can short-circuit early but every layer that was supposed to fire must
be marked `skipped` in the Layer Coverage table and explained — never
silently drop one. Missing the GEX read or the IV rank check is how
we end up selling premium below the gamma flip on a ticker the market
is structurally short; missing TV is how we end up quoting April-vintage
RSI as "today's read."
