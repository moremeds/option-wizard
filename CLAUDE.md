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

1. **Unusual Whales MCP / REST API** — **options data only**: IV rank,
   RV, GEX, skew, IV term structure, max pain, dark pool, flow,
   greeks/interpolated IV. UW first for any number UW serves directly.
2. **TradingView via `finance-data-providers:tradingview-reader`** —
   **the only source for price + technicals**: spot, OHLCV, volume bars,
   SMA/EMA(20/50/200), RSI(14), MACD, BBANDS, ATR(14), chart structure,
   news. UW indicator endpoints (`get_extended_technical_indicator` /
   `get_ticker_indicator_series`) are forbidden for L3 analysis use.
3. **Interactive Brokers** — MCP for account state (positions, balances,
   margin) and equity-stock order drafts; `ib_insync` for options order
   submission with brackets.

Secondary brokers (Futu, Tastytrade, Schwab, etc.) are configured in
`private/trader-profile.md` if used.

## Hard rules (summary; authoritative list in SKILL.md)

See `plugins/option-wizard/skills/option-wizard/SKILL.md` for the full
text. Summary:

1. **Defined-risk only** — no naked short calls, no margin-leveraged
   short puts.
2. **Source discipline** — UW = options data only; TV = price +
   technicals only; IB = account state.
3. **Preflight + one YES/NO** — every order shows legs, mid, max
   loss/gain, BE, margin, P/L matrix (±5/10/20%), account check, UW
   regime check, liquidity, catalyst clock.
4. **21 DTE in book-review Action items** — not a mid-flow blocking
   YES/NO. Trader picks close / roll / hold from the consolidated menu.
5. **FCN never routes through IB** — output is bilingual counter-offer
   email + strike/coupon ladder.
6. **Bracket defaults** — TP at 50% max gain, SL at 2× credit received.
7. **Freshness gate** — every quoted number ≤ 1 trading day stale, else
   it's a gap; do not extrapolate.
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
