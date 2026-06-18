# Design: Unify option-wizard broker state + live quote/greeks on the xenon REST API

**Date:** 2026-06-18
**Status:** Draft — pending user review
**Author:** chenxi (with Claude Code)

## 1. Goal

option-wizard currently acquires IB + Futu account / positions / orders / trades
through **three fragmented paths**:

1. **ib_insync direct** (`scripts/_clients/ib.py`) — positions + account summary,
   live per-leg `reqMktData`, and order placement.
2. **IB MCP tools** — used by the agent during live analysis (Layer-0 account context).
3. **Futu portfolio-analyser CLI** (separate Node project, manual, with a `--rerun`
   caching gotcha).

xenon already exposes a single authenticated, **read-only** HTTP service unifying
**IB + Futu** account/positions/orders/trades/blotter/journal/performance, plus a live
**L2 market-depth** surface and a single-contract **quote** surface. This migration
routes option-wizard's broker **reads**, the live **mid / liquidity** read, and the
live **per-contract greeks/IV** read through that one service — demoting the old paths
to documented fallbacks.

Order execution stays on ib_insync (the xenon key is read-only). Greeks/IV are taken
from the **live quote's broker-computed `modelGreeks`** — **never** a client-side BSM
model (explicit user decision; see §8).

**The deeper purpose** of unifying on xenon is not merely tidiness — it is to make
**live market data acquirable at any time**, so every analysis quotes the most accurate
*currently obtainable* value instead of a prior-session close. This makes the recurring
stale-data caveats ("IV skew 今日未重拉 / used 6/17 close chains", "VIX9D 没取到", "RSI 为
6/16 口径换算") **unacceptable when a live source was reachable**. The behavioral contract
is codified in §3.1.

## 2. Verified API surface (live probes, 2026-06-18, base `http://100.66.147.98:8321`)

Verified by direct HTTP against the deployed server — not the deploy note, whose
earlier revision over-claimed market-data access (8 of 15 rows were wrong). The
read-only `XENON_QUERY_API_KEY` grants exactly these paths.

### Reachable with our key (200)

| Method | Path | Returns (verified) |
|---|---|---|
| GET | `/health` | `status`, `ib_gateway`, `ib_pool`, `database`, `futu` (no key needed) |
| GET | `/portfolio` | IB `account_summary` + `positions[]` (legs carry `conId`, `market_price`) + `last_sync` |
| GET | `/futu/portfolio` | Futu `account_summary` + `account_raw` + `positions[]` (+ `is_stale`, `fetched_at`, `data_as_of`) |
| GET | `/orders` | IB `open_orders`, `executed_orders` (today), `last_sync` |
| GET | `/blotter` | IB+Futu 30-day fills |
| GET | `/journal` | Journal both brokers (`days`, `limit`) |
| GET | `/trades/entry-dates` | Per-ticker earliest entry |
| GET | `/performance` | IB daily NAV `series[]` + TWR `summary` |
| GET | `/market-depth` | L2 book snapshot + qualified `conId` — see §2.1 |
| GET | `/options/greeks` | **Live option bid/ask + greeks/IV in one triplet call** (v0.6.5) — see §2.2. Supersedes `/orders/quote` for us. |
| GET | `/options/chain` | Strike enumerator only — `{symbol, expiry, exchange, strikes:[float], multiplier}` |
| GET | `/options/expirations` | `{symbol, expirations:[YYYYMMDD]}` |

Write/sync/execution paths (`/orders/place|cancel|modify`, `/portfolio/sync`,
`/futu/sync`, …) return **401** with this key — verified. `/contract/qualify`,
`/historical/bars`, `/attribution`, `/watchlist` are not consumed here.

### 2.1 `/market-depth` — live mid + liquidity + option conId resolver

```
GET /market-depth?symbol=QQQ[&expiry=YYYYMMDD&strike=600&right=C][&num_rows=10]
```
- `symbol` alone → stock/index depth; full option triplet → option depth; partial
  tuple → `422`.
- Response: `{symbol, conId, secType, isSmartDepth, entitled, numRows, asOf,
  bids:[{price,size,marketMaker}], asks:[...], note?}`.
- Returns the qualified `conId` (incl. options) as a bonus, but option-wizard no longer
  needs it for the greeks/mid path — `/options/greeks` (§2.2) takes the triplet directly.
- `entitled` is permission-only; an entitled symbol can return an empty book
  after-hours as a **200** with `note:"no depth returned"`.
- **502 `"IB Gateway connection recently failed. Retrying shortly."`** is transient
  (IB cooldown) → retryable.
- **Role:** liquidity gate (spread / size / depth). No longer needed as a conId
  resolver — the R1b quote takes the option triplet directly (§2.2). **Not** a source
  of IV/greeks.

### 2.2 `GET /options/greeks` — live option bid/ask + greeks/IV (v0.6.5, deployed & verified)

Keyed by the **option triplet** (no conId round-trip). Verified live 2026-06-18.

```
GET /options/greeks?symbol=QQQ&expiry=20260717&strike=600&right=C
```
- **Input:** `symbol` + full triplet (`expiry` YYYYMMDD / `strike` / `right` C|P).
  Option-only — no stock fallback. Invalid `right` → **422**.
- **Verified response shape:**
  ```json
  {"symbol","conId","secType":"OPT","expiry","strike","right","asOf",
   "bid","ask",
   "greeks":{"impliedVol","delta","gamma","vega","theta","undPrice"}}
  ```
  Greeks are IB broker-computed `modelGreeks` — real market data, **not a model**.
- **Greeks vs mid are independent signals:**
  - `greeks` populates even pre-market (model-computed). `greeks is null` →
    ib_insync `reqMktData` fallback.
  - `bid`/`ask`/`greeks.undPrice` are **null off-hours** (no live NBBO). `bid/ask null`
    → no live mid (use held-leg `market_price`, else mid gap). **Do not** conflate with
    greeks availability.
- **Field names:** IV = `greeks.impliedVol`; `undPrice` is nested in `greeks`.
- **Units:** IB `modelGreeks` (iv decimal e.g. `0.407`; delta per-share; theta per-day;
  vega per 1 vol-pt). Client normalizes/labels to the project's greek conventions.
- **Server timeout 12s** → client timeout ≈15s.
- **Supersedes `/orders/quote`** for option-wizard: one triplet call returns bid/ask +
  greeks, so the conId two-step and the `/orders/quote` token machinery are unused.

## 3. Architecture — the invariant

> - **xenon** = all account/positions/orders/trades/journal state (IB+Futu); live
>   **mid / NBBO / L2 liquidity** (`/market-depth`); live **per-contract greeks/IV**
>   (`/options/greeks` `modelGreeks`, v0.6.5).
> - **UW** = options-analytics aggregates only it serves — IV rank, RV, 25Δ skew, IV
>   term structure, max pain, GEX-by-strike, dark pool, flow — **and** analytical-mode
>   per-contract IV/greeks (`interpolated_iv`, `greeks_by_strike`) for non-time-critical
>   fair-value work.
> - **TV** = price / technicals / OHLCV / spot.
> - **ib_insync** = order execution (`placeOrder`) + **fallback** live greeks
>   (`reqMktData` `modelGreeks`) when xenon is unreachable.
> - **No client-side BSM** for greeks/IV. Greeks always come from a live broker quote.

### 3.1 Data-acquisition discipline (live-first, exhaust-before-gap)

The point of the unified live surface is that analyses **pull live at the moment of
analysis**. Never quote a previous-session close, a "converted" prior-day technical, or
an extrapolated value when a live source exists and is reachable.

**Per-data-point acquisition ladder** — try in order; a gap is declared only after every
rung fails or returns empty:

| Data point | Ladder (primary → … → fallback) |
|---|---|
| Spot | TV live → xenon `/market-depth` underlying mid → UW chain `price_data` |
| Option IV / per-strike greeks | xenon `/options/greeks` (live, populates pre-market) → UW `interpolated_iv` / `greeks_by_strike` → ib_insync `reqMktData` modelGreeks |
| Skew (25Δ) / IV term structure | live build from an `/options/greeks` strike+expiry sweep → UW `historical-risk-reversal-skew` / `iv_term_structure` |
| IV rank / RV | UW `iv_rank` / `volatility/realized` (UW-exclusive — no rebuild) |
| GEX by strike / expiry / ticker | UW by-strike-expiry → by-strike → by-ticker (UW-exclusive — cannot rebuild from xenon) |
| Max pain / dark pool / flow | UW (exclusive) |
| Technicals (RSI/SMA/EMA/MACD/ATR/BBANDS) | TV live **today** — never a converted prior-day value |
| VIX / VIX9D / VXN | TV with correct exchange codes (try `CBOE:VIX`, `CBOE:VIX9D`, `CBOE:VXN` / `NASDAQ:VXN`) → UW → derive front-end IV from `/options/greeks` on SPX/QQQ near-term |
| Account / positions / orders / fills | xenon `/portfolio` `/futu/portfolio` `/orders` `/blotter` → IB MCP / Futu CLI |

**Exhaust-before-gap + self-check.** Before writing any "STALE / 未重拉 / gap" caveat, the
agent must self-check: *Did I actually call the live endpoint? Did I try alternative
symbols / exchange codes / endpoint variants / other sources, including the xenon live
surface?* A caveat is permitted only after a **documented** attempt across the ladder,
and it must state **what was tried** (e.g. "UW GEX-by-strike-expiry empty for SPX 6/19;
tried by-strike and by-ticker, both empty — genuine UW gap"), never a bare "未重拉" that
implies the live pull was simply skipped.

**Two gap classes:**
- **Avoidable** — a live source existed and was reachable but wasn't pulled (stale
  chains, converted RSI, wrong VIX exchange code). **Not acceptable.**
- **Genuine** — no source serves that slice (e.g. a UW-exclusive aggregate with no data
  for that expiry). Still flagged **honestly** and characterized by what was tried —
  but the remedy is to **acquire live**, never to extrapolate or convert a stale number
  into a "today" value (no-fabrication, §8).

## 4. Decisions (all confirmed with user)

1. **Scope:** both docs *and* scripts repointed to xenon.
2. **Fallback:** xenon primary; IB MCP read tools + Futu CLI kept as documented fallback.
3. **Management greeks:** sourced from the live quote (see #7); ib_insync `reqMktData`
   `modelGreeks` becomes the **fallback** path (extended to extract full
   delta/gamma/theta/vega/IV, not just delta).
4. **Mid + liquidity:** live mid/NBBO + L2 liquidity via xenon `/market-depth` as
   PRIMARY for hard rule #2 live-trade mode.
5. **manage_positions position source:** book + account from xenon `/portfolio`;
   reconstruct `Option(conId=…)` from legs (verified `legs[].conId` present) for the
   fallback `reqMktData` path.
6. **Agent entry point:** thin CLI `python -m scripts.xenon <path>` primary;
   documented `curl` for ad-hoc.
7. **Greeks/IV source (live / live-trade mode):** the live quote's broker `modelGreeks`
   — **xenon `/options/greeks` (v0.6.5) PRIMARY**, **ib_insync `reqMktData`
   `modelGreeks` FALLBACK**. **No BSM.** UW `greeks_by_strike`/`interpolated_iv` remain
   the analytical-mode source + an independent cross-check.
8. **Data-acquisition discipline (§3.1):** live-first acquisition via a per-data-point
   escalation ladder; a data gap is legitimate only after **documented exhaustion** of
   the ladder and must state what was tried; **avoidable** stale-data caveats are not
   acceptable; no-fabrication is preserved for **genuine** gaps.

## 5. Components

### 5.0 R1a (done) + R1b (new) — xenon repo

- **R1a (done & verified):** read-only key scope widened to include `/market-depth`,
  `/options/chain`, `/options/expirations`.
- **R1b (done & verified — v0.6.5):** `GET /options/greeks` (triplet → bid/ask +
  `greeks:{impliedVol,delta,gamma,vega,theta,undPrice}`); §2.2. On the read-only key
  allowlist; 422 on bad `right`; greeks verified populating for QQQ 600C 20260717.
  **No further xenon work required** — all remaining work is option-wizard-side.

### 5.1 `scripts/_clients/xenon.py` — new `XenonClient`

Mirrors the `uw.py` / `tv.py` client pattern. Config from env `XENON_BASE` / `XENON_KEY`
(both already in `.env`, gitignored).

- State: `health()`, `ib_portfolio()`, `futu_portfolio()`, `orders()`, `blotter()`,
  `journal(days, limit)`, `trades_entry_dates()`, `performance()`.
- Market data: `market_depth(symbol, expiry=None, strike=None, right=None, num_rows=10)`,
  `option_greeks(symbol, expiry, strike, right)` → `/options/greeks`: bid/ask +
  `greeks:{impliedVol,delta,gamma,vega,theta,undPrice}` (greeks may populate while
  bid/ask are null off-hours), plus enumerators `options_chain` / `options_expirations`
  (low priority — UW/TV already serve these).
- Errors: raise on non-200 **except** `/market-depth` 502 → short-backoff retry;
  surface `entitled` + empty-book so callers never fabricate a mid; if `quote()` greeks
  are absent (pre-R1b or null) signal the caller to fall back.
- Freshness: surface `last_sync` (IB) / `is_stale` + `fetched_at` (Futu) for hard rule #7.

### 5.2 Normalization helpers

- `to_audit_positions(ib_portfolio) -> (list, cash)` — xenon positions +
  `account_summary.cash` (fallback `settled_cash`) → `defined_risk_audit.audit_book`
  input. Map `leg.type` `Put`/`Call`→`P`/`C`, `Stock`→stock; `direction` SHORT/LONG →
  signed position. *(Plan-time choice: synthesize the `contract_description` string the
  regex parses, or refactor `audit_book` to accept structured legs — prefer the refactor
  if low-risk.)*
- `to_manage_legs(ib_portfolio) -> list` — per option leg: `{symbol, conId, strike,
  right, expiry, qty(signed), avg_cost, market_price}`.
- `to_futu_audit_positions(futu_portfolio)` — from `positions[].normalized.{symbol,
  kind,right,strike,expiry}` + `position_side` + signed `quantity`.

### 5.3 Live quote/greeks helper

`live_quote(symbol, expiry, strike, right)`:
1. `XenonClient.option_greeks(...)` → bid/ask + greeks/IV in one call (no conId step).
2. **Greeks:** if `greeks is None` or xenon unreachable → ib_insync `reqMktData`
   `modelGreeks` fallback (reconstruct `Option` from the triplet, or `conId` from the
   `/portfolio` leg). If both fail → greeks gap (**never BSM**).
3. **Mid:** if `bid`/`ask` non-null → mid = (bid+ask)/2; else use the held leg's
   `market_price` (`/portfolio`), else mid gap (never fabricate).
4. Liquidity (spread/size/depth) from `market_depth(...)` when the preflight needs it.

### 5.4 Consumer rewires

- **`manage_positions.py`** — book + account from `ib_portfolio()`; greeks via
  `live_quote()` (xenon quote primary, `reqMktData` fallback — extend the existing
  `modelGreeks` extraction beyond `delta` to full greeks/IV). Retire
  `_ib_positions_to_audit_format`. Can also scan the Futu book via `futu_portfolio()`.
- **`defined_risk_audit.py`** — fed by `to_audit_positions()`; core logic untouched
  (modulo the optional structured-leg refactor).
- **`retrospective.py` (复盘)** — programmatic Futu via `futu_portfolio()` + `blotter()`;
  portfolio-analyser CLI demoted to fallback.
- **`ib_order.py`** — untouched; execution stays on ib_insync.

### 5.5 Agent entry point + 5.6 docs rewrite

- CLI `python -m scripts.xenon <path>` + documented `curl`.
- Rewrite data-source policy in: root `CLAUDE.md`, project `CLAUDE.md` (hard rules
  #2/#5), `SKILL.md`, `references/data-sources.md`, `references/review-framework.md`,
  `references/workflows-overview.md`, `private/trader-profile.md`. xenon primary for
  state + mid/liquidity + live greeks; old paths demoted to documented fallback; UW
  retained for analytics aggregates + analytical-mode greeks; **BSM never used.**
- **Encode the §3.1 discipline** into `SKILL.md` hard rule #7 (freshness gate →
  live-first + exhaust-before-gap) and `references/data-sources.md` (Call order → the
  per-data-point ladder + the "state what was tried" caveat requirement). This is the
  behavioral half of the migration — the wiring exists so the policy can demand live.

## 6. Data flow

- **State pull:** `ib_portfolio()` + `futu_portfolio()` → normalization → existing
  audit / scan / report logic. Freshness from `last_sync` / `is_stale`.
- **Live greeks/IV (live-trade mode, management):** `quote(symbol,expiry,strike,right)`
  (xenon, R1b) → on `greeks:null`/failure `reqMktData` `modelGreeks` (ib_insync).
- **Liquidity preflight:** `market_depth()` top-of-book spread/size + depth.
- **Analytical mode (AQ/DQ/FCN fair value):** UW `interpolated_iv` + `greeks_by_strike`
  (unchanged).
- **Fallback ladder:** `health()`/non-200 → ib_insync read methods (scripts) / IB MCP
  + Futu CLI (agent) / `reqMktData` (greeks).

## 7. Error handling

- **401:** only the §2 allowlist works; treat else as config error, not retry.
- **`/market-depth` 502 (IB cooldown):** retry with short backoff.
- **Empty book (`bids`/`asks` == [] + `note`):** after-hours / no levels — 200 pass;
  surface "no live depth"; never fabricate a mid.
- **Missing/null quote greeks:** pre-R1b or off-hours → fall back to `reqMktData`; if
  that also fails, mark a greeks gap (do not BSM).
- **Stale `last_sync` / `is_stale`:** freshness gap per hard rule #7; do not extrapolate.

## 8. Out of scope (YAGNI / explicit rejections)

- **Client-side BSM greeks/IV** — explicitly rejected by user; greeks always from a
  live broker quote (`modelGreeks`).
- **Order execution** — stays on ib_insync; xenon key is read-only.
- **`/historical/bars`** — TV serves OHLCV.
- **`/options/chain` strikes / `/options/expirations`** — wired but deprioritized;
  UW/TV cover them.
- **Direct Postgres >30d** — documented escape hatch, not built.

## 9. Testing (mirrors `tests/integration/` + `scripts/smoke/`)

- **Unit — normalization:** fixtures from live `/portfolio`, `/futu/portfolio`,
  `/market-depth`, `/options/greeks` → audit shape, signed quantities, `Put`/`Call`→`P`/`C`,
  cash mapping, conId carry-through, greeks extraction.
- **Unit — client:** mocked HTTP — 200, 401, 502-retry, empty-book, greeks-present vs
  greeks-absent (fallback trigger).
- **Integration smoke (network-gated):** live `/health` + `/portfolio` +
  `/market-depth?symbol=AAPL` + `/options/greeks` (live), mirroring
  `test_uw_smoke.py`.

## 10. Risks

- **R1b reliability:** option-computation ticks need streaming + a settle window; the
  xenon quote may return null greeks off-hours → ib_insync fallback covers it.
- **xenon position lag (~60s):** acceptable for audit/management.
- **`/market-depth` after-hours empty book:** mid unavailable outside RTH; degrade,
  don't substitute.
- **Transient 502 churn:** client backoff required.
- **Doc drift:** treat `docs/reference/readonly-query-api.md` + live probes as truth,
  not the gitignored deploy note.

## 11. Sequencing

1. **R1a + R1b** (xenon: key scope + `/options/greeks`) — **done & verified (v0.6.5)**.
   No further xenon work; everything below is option-wizard-side.
2. `XenonClient` + normalization + unit tests.
3. Rewire `defined_risk_audit` → `manage_positions` → `retrospective`.
4. Agent CLI entry + docs/policy rewrite.
5. Integration smoke + full `pytest`.

W1 (account/trades/orders state) can land before W2 (mid/liquidity/greeks). R1b has
shipped, so W2's live-greeks path can be verified immediately.
