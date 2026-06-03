# option-wizard working agreements

## Trader profile

Active US-equity options trader, recent focus on mega-cap tech and semiconductors. Private bank client; receives FCN/ELN quotes regularly. Self-directed account on IB Gateway live (port 4001). Reads and writes Chinese; technical terms (delta, IV crush, gamma flip, KI, etc.) stay in English.

## Data source order

1. **Unusual Whales MCP / REST API** — vol, dealer, options microstructure (IV rank, GEX, skew, term structure, max pain, dark pool). UW first for any number UW serves directly.
2. **TradingView via Playwright** — realtime spot, technical indicators, chart, news. Reuse `finance-data-providers:tradingview-reader` skill rather than re-implement.
3. **Interactive Brokers MCP / ib_insync** — account positions, balances, contract resolution, order instructions.

## Hard rules

1. Defined-risk only. No naked short calls. No margin-leveraged short puts.
2. Every order shows P/L matrix, account verification, UW regime check, catalyst clock before submission. One YES/NO question per order.
3. Any short-premium position at 21 DTE produces a blocking review prompt — close, roll, or accept-gamma-risk choice required.
4. FCN does not go through IB. FCN output is a bilingual counter-offer email and a strike/coupon ladder.
5. Total annualized macro hedge cost ≤ 1.5% of portfolio net liquidation.
6. Bracket order defaults: take-profit at 50% of max gain, stop-loss at 2× credit received. Configurable per order.

## Response style

Chinese response. English technical terms. Concrete numbers, structures, verdicts — no "可以考虑" hedging language. Honest about PB markup; honest about thesis decay.

## Python environment

`uv` only. Venv at `.venv`. Python 3.13. Test with `.venv/bin/pytest`.
