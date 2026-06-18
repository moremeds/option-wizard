# option-wizard working agreements

This file is loaded automatically when Claude Code runs in this repo.
Generic skill philosophy below; personal trader preferences (broker
setup, language, response style, macro budget) come from
`private/trader-profile.md` when present.

## Customize for your trading style

```bash
mkdir -p private/
cp docs/setup/trader-profile.md.example private/trader-profile.md
$EDITOR private/trader-profile.md
```

The skill runs without this file using the generic defaults documented
below. `private/` is gitignored — your profile, NLV, positions, and
trade journal never leave your machine.

## Data source order (universal)

1. **Unusual Whales MCP / REST API** — options-derivative metrics only UW serves: IV rank, RV, GEX by strike, skew, IV term structure, max pain, dark pool, flow, greeks / interpolated IV; **also serves chain mid / IV / greeks (analytical-mode default for AQ/DQ/FCN fair-value)**. Never use UW for spot or technical indicators.
2. **TradingView via `finance-data-providers:tradingview-reader`** — the canonical source for spot (default), OHLCV, technical indicators (SMA / EMA / RSI / MACD / BBANDS / ATR / volume bars), news, alerts, watchlists, chart structure. UW `get_extended_technical_indicator` / `get_ticker_indicator_series` are forbidden for L3 analysis (series lagged by weeks).
3. **xenon Query API** (read-only, base `XENON_BASE`, header `X-API-Key` from `XENON_KEY`) — **PRIMARY for account state (IB *and* Futu): `/portfolio`, `/futu/portfolio`, `/orders`, `/blotter`, `/journal`, `/performance`**; live **mid / NBBO / L2 liquidity** (`/market-depth`); live **per-contract greeks / IV** (`/options/greeks`, IB `modelGreeks`) for live-trade-mode decisions (<60s window, AQ/DQ "PB just quoted me"). **No client-side BSM** — greeks always from a live broker quote. Ad-hoc: `python -m scripts.xenon <path>` or `curl -H "X-API-Key: $XENON_KEY" "$XENON_BASE<path>"`.
4. **Interactive Brokers / ib_insync** — `ib_insync` for option **order submission** with brackets (execution stays here; xenon never routes orders). **Fallbacks** (when xenon is unreachable): IB MCP read tools for account state, `reqMktData` `modelGreeks` for live greeks, `get_price_snapshot` for spot. Do NOT use IB for IV rank / skew / GEX / max pain (IB doesn't compute these derivatives).

The invariant: **xenon** = state + live mid/liquidity + live greeks; **UW** = options-analytics aggregates + analytical-mode greeks; **TV** = spot/technicals; **ib_insync** = execution + fallback greeks.

Secondary brokers (Futu, Tastytrade, Schwab, etc.) — Futu is served through
xenon `/futu/portfolio`; others are configured in `private/trader-profile.md`
if used.

## Hard rules (summary; authoritative list in SKILL.md)

See `plugins/option-wizard/skills/option-wizard/SKILL.md` for the full
text. Summary:

1. **Defined-risk only** — no naked short calls, no margin-leveraged
   short puts.
2. **Source discipline** — xenon = account state (IB+Futu) + live
   mid/liquidity + live greeks/IV (no client-side BSM); UW = options
   analytics aggregates + analytical greeks; TV = price + technicals;
   ib_insync = execution + fallback greeks.
3. **Preflight + one YES/NO** — every order shows legs, mid, max
   loss/gain, BE, margin, P/L matrix (±5/10/20%), account check, UW
   regime check, liquidity, catalyst clock.
4. **21 DTE in book-review Action items** — not a mid-flow blocking
   YES/NO. Trader picks close / roll / hold from the consolidated menu.
5. **PB structured products (FCN / AQ / DQ): no IB ORDER ROUTING; IB MARKET DATA is allowed.** Order routing is forbidden (PB products are OTC bilateral, never submit through IB). IB broker-feed chain data (mid/IV/greeks via the MCP) is allowed as a `Snapshot.chain` source when in live-trade mode (per hard rule #2). Output is product-specific bilingual counter-offer + verdict per `aq-dq-framework.md` / `fcn-framework.md`. AQ/DQ additionally short-circuits on 6 refusal red lines before any chain pull.
6. **Bracket defaults** — TP at 50% max gain, SL at 2× credit received.
7. **Freshness gate (live-first)** — pull live at analysis time and walk
   the per-data-point acquisition ladder before declaring any gap;
   avoidable stale-data caveats are not acceptable, genuine gaps stay
   honest (state what was tried) and are never extrapolated/fabricated.
8. **Ticker analysis structure non-negotiable** — opens with the Layer
   Coverage table from `references/analysis-runbook.md`.

## Trader-policy defaults

These have sensible defaults but can be overridden in
`private/trader-profile.md`:

- **Macro hedge budget:** total annualized macro hedge cost ≤ **1.5%**
  of portfolio NLV.
- **Response language:** defaults to English; override to Chinese
  (with English technical terms) or any other style in the profile.
- **Tone:** concrete numbers, structures, verdicts; avoid hedging
  language ("you might consider", "可以考虑").

## Python environment

`uv` only. Venv at `.venv`. Python 3.13. Test with `.venv/bin/pytest`.

---

@private/trader-profile.md
