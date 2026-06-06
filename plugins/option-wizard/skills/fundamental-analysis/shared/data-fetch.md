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
- **Recent news / CEO changes / activist filings / proxy fights:** Massive news endpoint with per-article sentiment (see "Tertiary source: Massive" below) as primary; `WebSearch` as fallback for last 30-90 days when Massive returns thin.
- **Forward PE / NTM consensus estimates:** UW `get_analyst_ratings` gives PTs but not full forward earnings model — confirm via `WebSearch` on consensus EPS from Yahoo / Seeking Alpha / Bloomberg snippet.

## Tertiary source: Massive (Polygon-rebrand)

Massive (`api.massive.com`, formerly `api.polygon.io`) fills gaps UW does not cover: direct SEC filing URLs, line-item-rich annuals, daily short volume per-venue, per-article news sentiment, and auto-ranked related companies. Use as augment, not replacement — UW remains primary for standard fundamentals.

**Auth & invocation pattern:**

The key lives in the project's gitignored `.env` (alongside `UW_API_KEY` etc., per the existing pattern in `uw.py`). Claude Code's Bash tool spawns non-interactive shells that skip `~/.zshrc`, so the skill **must source `.env` explicitly** before each Massive call rather than relying on shell config:

```bash
# Run from project root (or any directory containing .env).
set -a; source .env; set +a
curl -s -H "Authorization: Bearer $MASSIVE_API_KEY" "https://api.massive.com/<path>"
```

The `set -a` / `set +a` bracket auto-exports every assignment inside `source` — this is how the project's Python scripts already pick up `UW_API_KEY`, so the convention carries over.

If `.env` is missing or `MASSIVE_API_KEY` is empty after sourcing, fall back to UW only and flag the gap in the report (do not prompt the trader mid-flow). Check via:

```bash
[ -n "$MASSIVE_API_KEY" ] && echo "massive: ok" || echo "massive: skip — key unset"
```

Project setup (one-time): copy `.env.example` → `.env` and fill in `MASSIVE_API_KEY=<your-key>` (see Massive dashboard for the key). `.env` is gitignored; the key never reaches the repo.

**Verified endpoints (paths confirmed against live API):**

| Endpoint | Path | What it adds vs UW |
|---|---|---|
| Ticker overview | `GET /v3/reference/tickers/<TICKER>` | CIK, SIC code, employee count, list date — UW `get_company_info` lacks CIK / SIC, which means UW can't construct EDGAR URLs and you'd have to guess. |
| Financials (annual / quarterly / TTM) | `GET /vX/reference/financials?ticker=<TICKER>&timeframe=annual&limit=5` | 30-50 line items per statement (UW gives ~15 top-level), AND every result row carries `source_filing_url` — a direct SEC EDGAR link to the 10-K/10-Q. **This eliminates the "do not invent EDGAR URLs" prohibition in sources.md.** |
| News + sentiment | `GET /v2/reference/news?ticker=<TICKER>&limit=10` | Per-article `insights[{ticker, sentiment, sentiment_reasoning}]` — Claude-readable structured sentiment, replaces WebSearch for the bulk of catalyst-screening work. |
| Related companies (peer set) | `GET /v1/related-companies/<TICKER>` | Returns ~10 ranked related tickers. **Use this as the default peer set in deep mode Pre-flight step 1** — trader still overrides if they want a specific cohort. |
| Short volume (daily) | `GET /stocks/v1/short-volume?ticker=<TICKER>&limit=10` | Per-day total / short / exempt volume **broken out by venue** (NYSE / NASDAQ Carteret / NASDAQ Chicago / ADF). UW only has bi-weekly short interest — this is finer-grained tape input usable by analysis-runbook L4. |
| Short interest (bi-weekly) | `GET /stocks/v1/short-interest?ticker=<TICKER>&limit=10` | Same shape as UW `get_short_data_by_ticker` (settlement_date / short_interest / avg_daily_volume / days_to_cover) — use either; UW is fine. |

**Where Massive does NOT replace anything:**
- IV rank, RV, skew, GEX, max pain, dark pool, flow alerts → UW (Massive has no options analytics)
- Spot, OHLCV, technical indicators → TradingView (CLAUDE.md hard rule #2; Massive technicals are forbidden under the same rule that forbids UW's)
- Account state → IB

**Token-cost notes for Massive:**
- `/vX/reference/financials` with `limit=5&timeframe=annual` returns ~50-80K (5 FY × 3 statements × 30-50 line items). Set `limit=1` for spot-check, `limit=5` for trend; never request `timeframe=quarterly&limit=20+` without a plan — that breaks 250K easily.
- `/v2/reference/news?limit=10` returns ~20-30K when sentiment + reasoning are populated. `limit=20` is the practical ceiling.
- `/v1/related-companies` returns < 1K — free pull, do it on every deep-mode kickoff.
- `/stocks/v1/short-volume?limit=10` returns ~5K. Adequate for a 2-week window.

**Massive-specific gotchas:**
- `vX` prefix marks beta-stability endpoints (financials lives here). Monitor for path changes if you script automation.
- SIC code is the SEC industry taxonomy, not GICS. Cross-check sector classification against UW `get_company_info` if the sector matters for peer comparison.
- The financials endpoint's `source_filing_url` returns `api.polygon.io` URLs in the response body (artifact of the rebrand) — these still resolve and are valid SEC EDGAR redirects.
- News `insights[*].sentiment` is one of `positive / neutral / negative`; treat `neutral` as no signal, not "mildly bullish".

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

## Deep mode — extended pull (UW extras + Massive augments)

```
UW extras:
 6. get_balance_sheets(ticker, period=annual)        # 5 FY
 7. get_earnings_history(ticker)                     # ~8 quarters
 8. get_fundamental_breakdown(ticker)                # PE/PB/PS/EV-EBITDA
 9. get_short_data_by_ticker(ticker)
10. get_institution_holdings(ticker)                # top 10

Massive augments (run BEFORE peer repeats so peer set is auto-derived):
11. GET /v1/related-companies/<TICKER>              # ranked top-10 peers → default peer set
12. GET /v3/reference/tickers/<TICKER>              # CIK + SIC + employee count
13. GET /vX/reference/financials?ticker=<TICKER>&timeframe=annual&limit=5
                                                    # line-item financials WITH source_filing_url for SEC citations
14. GET /v2/reference/news?ticker=<TICKER>&limit=10  # per-article sentiment + reasoning (replaces WebSearch for catalysts)
15. GET /stocks/v1/short-volume?ticker=<TICKER>&limit=10
                                                    # daily short volume per-venue (also feeds analysis-runbook L4 tape)

Per-peer repeats of UW steps 1-5 for each name in the peer matrix
WebSearch ONLY for catalyst types Massive news doesn't cover well: activist 13D filings,
proxy fights, regulatory actions; otherwise news + sentiment via Massive (step 14)
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

For a deep-mode report on `<TICKER>` with N peers, the kickoff is two
rounds: first derive the peer set from Massive, then fan out everything
in parallel.

```
Round 0 (peer-set derivation, ~3 parallel calls):
  GET /v1/related-companies/<TICKER>        # auto peer set (Massive)
  get_company_info(<TICKER>)                # UW target overview
  GET /v3/reference/tickers/<TICKER>        # Massive CIK + SIC

  → If trader specified peers in the prompt, use those instead. If
    related-companies returned < 4 names, prompt the trader for the
    cohort before continuing.

Round 1 (target + peer fan-out, single message, ~(N+1) × 5 UW calls
+ 4 target-only Massive calls in parallel):
  for each name in [<TICKER>, peer1, ..., peerN]:
    get_income_statements(name, annual)
    get_cash_flows(name, annual)
    get_ticker_performances(name)
    get_analyst_ratings(name)
    get_company_info(name)                  # skip for <TICKER>, already pulled

  Target-only Massive augments (run in same parallel batch):
    GET /vX/reference/financials?ticker=<TICKER>&timeframe=annual&limit=5
    GET /v2/reference/news?ticker=<TICKER>&limit=10
    GET /stocks/v1/short-volume?ticker=<TICKER>&limit=10
    GET /stocks/v1/short-interest?ticker=<TICKER>&limit=10
```

Then a smaller third round for the target ticker's deep-mode UW extras
(balance sheet, earnings history, fundamental breakdown, institution
holdings). This sequencing keeps the bulk of latency in two
round-trips — peer discovery, then everything else.

**Why peer-set derivation is its own round:** the rest of Round 1 needs
the peer names. Pulling related-companies in Round 1 alongside the
fan-out means you'd have to guess peers (defeating the point) or
serialize. One extra round-trip for ~1KB of peer data is worth it.

## Common data gotchas (from LULU report build)

- `get_income_statements` for some tickers returns empty `result: []` even when the company is alive (Gap Inc. example). Fall back to `WebSearch "<TICKER> FY26 EPS revenue 10-K"`.
- `get_company_info` may return `price: null` for some names (VSCO). Compute trailing PE from market cap / net income directly, don't anchor on a missing single-share price.
- TTM EPS isn't a UW field. Compute: sum of last 4 quarterly EPS (from `get_earnings_history`), or use latest FY EPS as proxy if you're staying annual.
- Forward PE = spot / NTM EPS consensus. Consensus EPS isn't always in UW; cross-check via `WebSearch`.
- Activist / 13D positions held via Total Return Swaps (TRS) do NOT appear in 13F. Don't conclude "no position" from an empty 13F if the trader is asking about an activist whose name surfaced in news.
