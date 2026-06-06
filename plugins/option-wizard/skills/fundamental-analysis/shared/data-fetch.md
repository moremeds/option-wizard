# Data fetch catalog

What to pull, from which tool, in what order. Same pipeline for quick
and deep — deep mode just uses more of it.

## Tool inventory (all Unusual Whales MCP unless noted)

| Tool | What it returns | Token-cost flag |
|---|---|---|
| `get_company_info` | name, sector, industry, exchange, market cap, shares outstanding, brief description | Small — always pull first. |
| `get_income_statements` (period=annual) | revenue, gross profit, operating income, EBITDA, net income, EPS — last 5 FY | Medium. **Quarterly mode > 75K chars — avoid.** |
| `get_cash_flows` (period=annual) | operating CF, capex, FCF, dividends paid, buybacks — last 5 FY | Medium. |
| `get_balance_sheets` (period=annual) | total assets, total debt, cash, equity, working capital — last 5 FY | **Large — often > 75K. File-redirect if hitting limit.** |
| `get_ticker_performances` | 1d / 1w / 1m / 3m / 6m / 1y / 3y / 5y total return, max drawdown | Small. |
| `get_earnings_history` | reported EPS vs estimate, beat/miss/inline, revenue actual vs estimate — last ~8 quarters | Small. |
| `get_analyst_ratings` | current rating distribution (buy / hold / sell), average PT, PT range | Small. |
| `get_fundamental_breakdown` | comprehensive snapshot: PE, PB, PS, EV/EBITDA, ROE, ROA, margins, dividend yield, etc. | **Large — > 75K common. File-redirect.** |
| `get_short_data_by_ticker` | short interest, days-to-cover, borrow rate, off-exchange short volume | **Large — > 75K common. File-redirect.** |
| `get_institution_holdings` | top institutional holders, position size, change qtr-over-qtr | Medium. Deep mode only. |
| `get_institutions` | institution profile, AUM, sector tilt, 13F history | Small. Used to research a specific holder. |

Non-UW data:
- **Spot price (current):** TradingView via `finance-data-providers:tradingview-reader` — **never UW for spot** (CLAUDE.md hard rule #2). If TV unavailable, fall back to IB `get_price_snapshot`.
- **Recent news / CEO changes / activist filings / proxy fights:** `WebSearch` for last 30-90 days. UW only carries flow-related news.
- **Forward PE / NTM consensus estimates:** UW `get_analyst_ratings` gives PTs but not full forward earnings model — confirm via `WebSearch` on consensus EPS from Yahoo / Seeking Alpha / Bloomberg snippet.

## Quick mode — minimum pull (5 tools)

```
1. get_company_info(ticker)
2. get_income_statements(ticker, period=annual)     # 5 FY
3. get_cash_flows(ticker, period=annual)            # 5 FY  → derive FCF
4. get_ticker_performances(ticker)
5. get_analyst_ratings(ticker)
+ TV spot price
```

Compute from these:
- TTM revenue + revenue 3Y CAGR
- Gross / operating / net margin (latest FY)
- FCF latest FY, FCF margin
- Trailing PE = spot / TTM EPS
- 1Y total return, 5Y total return, max DD
- Analyst rating skew + PT vs spot

Stop here for quick mode.

## Deep mode — extended pull (add 5 more)

```
6. get_balance_sheets(ticker, period=annual)        # 5 FY
7. get_earnings_history(ticker)                     # ~8 quarters
8. get_fundamental_breakdown(ticker)                # PE/PB/PS/EV-EBITDA
9. get_short_data_by_ticker(ticker)
10. get_institution_holdings(ticker)                # top 10
+ Per-peer repeats of 1-5 for each name in the peer matrix
+ WebSearch for recent catalysts (CEO, activist, guidance, M&A rumors)
```

Compute from these:
- Net debt = total debt − cash
- BV / share, P/B, ROE, ROA
- EV / EBITDA, EV / sales
- EPS surprise pattern (% positive surprises last 8 Q)
- Short interest % float, DTC, borrow rate
- Top 5 holders, position changes last quarter
- For each peer: same TTM PE / fwd PE / margin / FCF margin / net debt / ROE — assemble into peer matrix
- Historical PE percentile (TTM PE today vs 5Y / 10Y range — query via repeated `get_ticker_performances` history + analyst snapshots)

## Token-cost playbook

UW responses > 75K chars get truncated by the tool layer; the workaround:

1. **Default to annual, not quarterly.** Annual responses are ~5-15K; quarterly are ~50-150K because they're 4x rows with the same column count.
2. **For `get_fundamental_breakdown` / `get_balance_sheets` / `get_short_data_by_ticker`:** if the response exceeds limit, the tool layer writes the full JSON to a temp file and returns the file path. Read only the keys you need via grep/jq, not the whole file.
3. **Peer matrix in deep mode:** N peers × 5 tools each = 5N calls. Batch the calls in parallel (one tool-use block, multiple tool calls). For 7 peers you spawn ~35 calls in one round.
4. **WebSearch is expensive.** Use it sparingly — one well-formed query beats five vague ones. Format: `"<TICKER> CEO 2026"` or `"<TICKER> Q4 2025 earnings guidance"`.

## Parallel-pull pattern (deep mode kickoff)

For a deep-mode report on `<TICKER>` with N peers, the right first move
is one parallel batch:

```
Round 1 (single message, ~(N+1) × 5 parallel calls):
  for each name in [<TICKER>, peer1, peer2, ..., peerN]:
    get_company_info(name)
    get_income_statements(name, annual)
    get_cash_flows(name, annual)
    get_ticker_performances(name)
    get_analyst_ratings(name)
```

Then a smaller second round for the target ticker's deep-mode extras
(balance sheet, earnings history, etc.). This sequencing keeps the bulk
of latency in one round-trip instead of serializing.

## Common data gotchas (from LULU report build)

- `get_income_statements` for some tickers returns empty `result: []` even when the company is alive (Gap Inc. example). Fall back to `WebSearch "<TICKER> FY26 EPS revenue 10-K"`.
- `get_company_info` may return `price: null` for some names (VSCO). Compute trailing PE from market cap / net income directly, don't anchor on a missing single-share price.
- TTM EPS isn't a UW field. Compute: sum of last 4 quarterly EPS (from `get_earnings_history`), or use latest FY EPS as proxy if you're staying annual.
- Forward PE = spot / NTM EPS consensus. Consensus EPS isn't always in UW; cross-check via `WebSearch`.
- Activist / 13D positions held via Total Return Swaps (TRS) do NOT appear in 13F. Don't conclude "no position" from an empty 13F if the trader is asking about an activist whose name surfaced in news.
