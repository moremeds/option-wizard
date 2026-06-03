# option-wizard working agreements

## Trader profile

Active US-equity options trader, recent focus on mega-cap tech and semiconductors. Private bank client; receives FCN/ELN quotes regularly. Self-directed account on IB Gateway live (port 4001). Reads and writes Chinese; technical terms (delta, IV crush, gamma flip, KI, etc.) stay in English.

## Data source order

1. **Unusual Whales MCP / REST API** — vol, dealer, options microstructure (IV rank, GEX, skew, term structure, max pain, dark pool). UW first for any number UW serves directly.
2. **TradingView via Playwright** — realtime spot, technical indicators, chart, news. Reuse `finance-data-providers:tradingview-reader` skill rather than re-implement.
3. **Interactive Brokers MCP / ib_insync** — account positions, balances, contract resolution, order instructions.
4. **Futu via portfolio-analyser CLI** — secondary broker positions / trades. Pull with `cd ~/projects/portfolio-analyser && npx tsx src/cli.ts ft --range 1y` (OpenD daemon on port 11111 required); read just the positions block from the resulting JSON and feed it into the same option-wizard pipeline (`defined_risk_audit`, 21-DTE scan, `manage_positions --audit-only`). Skip the 3-persona HTML enrichment — that's a separate workflow. Cash balance is not in the report; pull separately via futu-api if a CSP coverage check needs it.

## Position-review scope

Any "review positions" / "我账户里这些仓位有没有问题" request pulls **both brokers**: IB MCP first, Futu via portfolio-analyser second. Report findings as one consolidated book; do not silently skip Futu when IB is the primary broker.

## Hard rules

1. Defined-risk only. No naked short calls. No margin-leveraged short puts.
2. Every order shows P/L matrix, account verification, UW regime check, catalyst clock before submission. One YES/NO question per order.
3. Any short-premium position at 21 DTE surfaces as an entry in the consolidated **Action items** section at the end of the book review (see SKILL.md §"Book-review output structure"). Not a mid-flow blocking prompt — trader picks close / roll / hold from the action-items menu, then preflight expands.
4. FCN does not go through IB. FCN output is a bilingual counter-offer email and a strike/coupon ladder.
5. Total annualized macro hedge cost ≤ 1.5% of portfolio net liquidation.
6. Bracket order defaults: take-profit at 50% of max gain, stop-loss at 2× credit received. Configurable per order.

## Response style

Chinese response. English technical terms. Concrete numbers, structures, verdicts — no "可以考虑" hedging language. Honest about PB markup; honest about thesis decay.

## Python environment

`uv` only. Venv at `.venv`. Python 3.13. Test with `.venv/bin/pytest`.
