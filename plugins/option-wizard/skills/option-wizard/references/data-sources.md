# Data Sources

## Source split (SKILL.md hard rule #2)

**Strict, non-negotiable split:**

| Domain | Source | Forbidden alternative |
|---|---|---|
| Spot, OHLCV, daily/intraday candles, volume bars | **TV** via `finance-data-providers:tradingview-reader` | UW `get_company_info`, chain `price_data` (for "live spot"), `get_ticker_candles_by_range` (for analysis-grade technicals) |
| SMA(20/50/200), EMA, RSI(14), MACD, BBANDS, ATR | **TV** | UW `get_extended_technical_indicator`, `get_ticker_indicator_series` — **banned for L3 analysis**; chronic multi-week staleness was the root cause of the 2026-06 NVDA / QQQ / SPY analyses being degraded to extrapolation |
| IV rank, RV (UW computed), 25Δ skew, IV term structure | **UW** | TV (does not serve these) |
| Max pain, GEX-by-strike, greeks-by-strike, interpolated IV | **UW** | — (UW exclusive) |
| Flow alerts, flow per expiry, dark pool prints | **UW** | — (UW exclusive) |
| Account state (positions, balances, margin) | **IB MCP** | — |

## Freshness gate (SKILL.md hard rule #7)

Every data point quoted in an analysis must be **≤ 1 trading day stale**.
Older = **gap**, not signal. Check freshness explicitly:

- TV chart-state → returns live or T-0 close; freshness is usually fine
  but record the timestamp in the Layer Coverage table.
- UW chain endpoints → check `last_price.date` and `price_data.date`. If
  the field is more than 1 trading day before today, flag as STALE.
- UW indicator endpoints → routinely 2-6 weeks behind. **Do not extract
  daily-fresh technicals from these.** If used at all (only in an
  authorized exception), every value must carry an `as_of` timestamp and
  a `STALE` flag.
- IB MCP positions / balances → live during market hours; T-1 close after
  hours. Always fresh enough.

If a number cannot be brought current, list it under "What this analysis
is missing" and do not extrapolate it into the decision.

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

IB MCP is **read-only for state, equity-only for writes**. Verified via
`scripts/smoke/ib_mcp_findings.md` against the live `claude.ai` IBKR
connector on 2026-06-03:

- `get_account_summary`, `get_account_balances`, `get_account_positions`,
  `get_account_orders`, `get_account_trades` — read-only state.
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

1. **IB account context** — `get_account_summary` (net liq, buying power,
   maintenance margin), `get_account_positions` for any existing
   exposure in the same name. (Layer 0)
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
