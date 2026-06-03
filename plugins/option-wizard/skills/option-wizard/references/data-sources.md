# Data Sources

## UW first policy

Restating SKILL.md: any numeric metric Unusual Whales serves directly is
fetched from UW, not recomputed client-side. UW's pricing/exposure data
is sourced from exchange feeds we don't have, and rebuilding it from
Yahoo/IB would silently introduce error.

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
| `/api/stock/{t}/technical-indicator/{fn}` | `technical_indicator(t, fn)` | SMA/RSI/MACD pull |

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

The standard sequence for evaluating a ticker for a new position:

1. **UW vol regime** — `iv_rank`, `volatility/realized`, `volatility/term-structure`,
   `historical-risk-reversal-skew`. Computes VRP, term inversion flag,
   skew penalty.
2. **UW GEX** — `spot-exposures/strike`. Pipe through `gex_levels.compute_levels`
   for flip / put wall / call wall.
3. **UW interpolated IV + greeks** at candidate strikes — `interpolated_iv`
   and `greeks_by_strike(ticker, expiry=...)` for the strikes the
   strategy module identifies (e.g., for a CSP, the 70-90Δ short put
   strike; for a bull put spread, both legs).
4. **TV spot confirmation** — TV reader, last 1-day with current bid/ask;
   sanity check vs UW quote and IB position price.
5. **IB account context** — `get_account_summary` (net liq, buying power,
   maintenance margin), `get_account_positions` for any existing
   exposure in the same name (don't pile a short put under a covered
   call you already have).

When the answer is "no position" or "wait for a different setup", you
can short-circuit at step 1 or 2. Never skip steps to reach a
recommendation faster — missing the GEX read or the IV rank check is
how we end up selling premium below the gamma flip on a ticker the
market is structurally short.
