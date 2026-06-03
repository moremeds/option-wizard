# option-wizard — Design Specification

**Date:** 2026-06-03
**Status:** Draft awaiting user review
**Project root:** `~/projects/option-wizard/`

---

## 1. Purpose

A personal Claude Code skill for an active retail options trader who is also a private bank (PB) client. It does three jobs:

1. **Defends against PB markup** on Fixed Coupon Notes (FCN) and similar structured products by computing fair coupon vs. quoted coupon and generating a counter-offer email.
2. **Recommends single-name option income structures** (Covered Call, Cash-Secured Put, defined-risk credit spreads, Collar, Jade Lizard) based on the current volatility / dealer-flow regime of the chosen ticker.
3. **Executes orders through Interactive Brokers** with defined-risk guardrails, automatic take-profit / stop-loss brackets, and a strict 21-DTE position review.

It also provides macro hedge sizing (SPX butterfly / put spread / long put) so the trader's short-vol income book does not run unhedged.

The skill follows the layout conventions of `himself65/trade-skills` (public reference). All prose, scripts, and reference content in this project are written fresh; no content is reproduced verbatim from that repo.

## 2. Non-Goals

- Replacing TradingView or Unusual Whales as visualization tools — the skill consumes their data but does not duplicate their dashboards.
- Auto-trading without human approval — every order submission requires an explicit `YES` from the trader.
- Backtesting or research — those live in the separate `fcn-wizard` Python project.
- Structured products other than FCN — ELN, accumulator, autocallable, and exotic basket products are out of scope for v1.

## 3. Trader Profile (project CLAUDE.md, abridged)

- Active US-equity options trader, with recent focus on mega-cap tech and semiconductors.
- Private bank client; receives PB quotes for FCN / ELN regularly and needs to negotiate from a position of model-backed knowledge.
- Holds an IB Gateway live account (port 4001) for self-directed orders.
- Reads Chinese, writes Chinese; technical terms (delta, IV crush, gamma flip, KI, etc.) stay in English.
- Risk preference: no naked short calls. Short puts must be cash-secured (no margin leverage). Multi-leg spreads, butterflies, collars, and Jade Lizard structures are acceptable. Cash-collateralized assignment risk on short puts is treated as accepted, not "undefined".

## 4. Data Architecture

### 4.1 Three Sources, Three Roles

| Source | Type | Role | When to call |
|---|---|---|---|
| Unusual Whales MCP | Remote HTTP MCP (user's API key) | Numeric truth source for vol / dealer / options microstructure | First step of every analysis |
| TradingView via Playwright | Browser automation (reuses existing `finance-data-providers:tradingview-reader` skill) | Realtime spot, technical indicators (MA / RSI / MACD / BB), chart screenshots, news headlines, watchlist state | When chart context, technical indicators, or news is needed |
| Interactive Brokers MCP | Remote MCP (account-bound) | Account positions / balances, contract resolution, order instructions | Any write action and supplementary historical data |

### 4.2 Policy: UW First for Numbers

Any metric Unusual Whales serves directly must be fetched from UW — no client-side recomputation, no scraping from TradingView. This rule guards consistency, auditability, and keeps the skill from disagreeing with the trader's own UW dashboard.

UW serves these directly (use the endpoint, do not recompute):

- IV Rank — `/api/stock/{ticker}/iv-rank`
- Realized Volatility — `/api/stock/{ticker}/realized-volatility`
- Risk Reversal Skew — `/api/stock/{ticker}/historical-risk-reversal-skew`
- IV Term Structure — `/api/stock/{ticker}/implied-volatility-term-structure`
- Max Pain — `/api/stock/{ticker}/max-pain`
- Spot GEX by strike — `/api/stock/{ticker}/spot-exposures/strike`
- Interpolated IV with percentiles — `/api/stock/{ticker}/interpolated-iv`
- Greeks by strike — `/api/stock/{ticker}/greeks`
- Dark pool prints — `/api/darkpool/{ticker}`
- Historical OHLC — `/api/stock/{ticker}/technical-indicator/{function}`

UW does not serve these — they are computed client-side from the strike-level GEX endpoint or from arithmetic on two UW endpoints:

- Gamma flip price (zero crossing of cumulative GEX)
- Put wall (strike with largest positive gamma)
- Call wall (strike with largest negative gamma)
- VRP numeric value (IV minus RV)
- FCN fair coupon (UW has no concept of bilateral structured products)

### 4.3 TradingView Domain

For price-action and technical-indicator data where the trader's chart is annotated with personal templates and Pine scripts, TradingView is the primary source. The skill calls `finance-data-providers:tradingview-reader` rather than re-implementing TV scraping. Typical uses:

- Realtime spot price confirmation (UW quotes can lag)
- Moving averages (20 / 50 / 200) relative to current price
- RSI / MACD / Bollinger states
- Recent news on the ticker
- Watchlist context and alert fire log

### 4.4 IB Domain

The IB MCP is the only source allowed to write state. It also fills gaps on the read side — contract resolution for less common products and account-specific data.

## 5. Skill Layout

```
~/projects/option-wizard/
├── .claude-plugin/
│   └── plugin.json
├── .gitignore
├── CLAUDE.md                                  Trader profile + hard rules
├── README.md                                  Repo entry point
├── package.json                               Optional, for `npx skills add`
├── plugins/option-wizard/skills/option-wizard/
│   ├── SKILL.md                               Frontmatter, triggers, hard rules
│   ├── README.md
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── gex_levels.py                      Compute gamma flip + walls from UW GEX
│   │   ├── vrp.py                             IV minus RV
│   │   ├── fair_coupon.py                     FCN fair coupon, strike ladder, basket
│   │   ├── ib_order.py                        Order construction with bracket orders
│   │   ├── manage_positions.py                Open positions scan + 21 DTE enforcement
│   │   ├── evaluate_position.py               Single-position roll/close decision tree
│   │   ├── macro_hedge.py                     SPX put fly / put spread / long put
│   │   └── email_sender.py                    Gmail SMTP delivery of daily scan
│   └── references/
│       ├── data-sources.md                    UW MCP / TV / IB MCP playbook
│       ├── strategies.md                      Regime ↔ structure matrix
│       ├── gamma-framework.md                 GEX reading guide
│       ├── price-action-framework.md          TV-based tape reading
│       ├── fcn-framework.md                   FCN payoff, fair coupon math, PB checklist
│       ├── execution.md                       IB order flow, brackets, 21 DTE rule
│       ├── pitfalls/
│       │   ├── README.md
│       │   └── _template.md                   Empty, user fills as they trade
│       └── ticker/
│           ├── README.md
│           ├── _template.md
│           └── orcl-2026-06-fcn.md            First case study from this session
├── docs/specs/
│   └── 2026-06-03-option-wizard-design.md     This file
└── tests/                                     Optional pytest for fair_coupon / gex_levels
```

The layout pattern (plugins / skills / references / pitfalls / ticker) mirrors `himself65/trade-skills` so that future contributors familiar with that project find their bearings quickly. All file contents are original to this project.

## 6. FCN Module

### 6.1 Eight-Item PB Defense Checklist

Every FCN analysis runs through these checks; failures surface in the verdict and counter-offer email.

1. **Strike vs gamma flip.** If the FCN strike sits below the dealer gamma flip, the dealer is in negative-gamma territory and price decline is amplified — model KI probability understates real risk. Either step strike up one notch or demand five points of additional coupon.
2. **Markup vs IV Rank.** Real institutional fair coupon is roughly 50–65% of the continuous-touch model output. Retail PB layers a 25–40% distribution markup on top, so an honest quote is at least 30% of the model figure. Anything below 25% is predatory; counter for 2–3 points of additional coupon.
3. **KI buffer vs 5-year max drawdown.** If the strike is within 10 percentage points of the ticker's worst 5-year trough, reject regardless of coupon — the ticker has historically traded through that strike.
4. **IV Rank threshold.** Below 50, selling a 6-month locked-in vega position via FCN is poor use of capital; recommend rolling monthly short puts instead.
5. **Skew (25-delta risk reversal).** Severely negative skew (worse than −0.25) indicates the option market has already priced left-tail risk; the seller deserves an additional 3–5 points of coupon to absorb it.
6. **Tenor anchor.** Six-month tenors with 100% knock-out and quarterly observation are the PB favorite because they auto-call quickly; the annualized coupon advertised may correspond to a three-month effective holding period. Translate the headline annual figure to absolute dollar return before agreeing.
7. **Liquidity.** FCNs trade on the PB's internal book with no secondary market. Holding to maturity is the only exit. Document this explicitly in every analysis output.
8. **Issuer credit risk.** The note pays only if the issuer (typically the PB's parent or an SPV) is solvent at maturity. Pull the parent's senior unsecured rating and 5-year CDS spread; SPV-issued notes require additional scrutiny of the collateral pool structure.

### 6.2 `fair_coupon.py` Interface

```
analyze_fcn(ticker, strike_pct, tenor_months, observation_months,
            ko_pct=1.0, pb_quoted_coupon=None) -> dict

analyze_fcn_basket(tickers, ... same product terms ...) -> dict
```

Default behavior is to emit a four-rung strike ladder (70 / 75 / 80 / 85% of spot) so the trader can see the trade-off. When `pb_quoted_coupon` is supplied the output adds a `verdict` field of `fair` / `rich` / `cheap`. The output always includes a bilingual counter-offer email draft (Chinese first, English version below for forwarding) when the verdict is `rich` or any checklist item fails.

### 6.3 Basket Handling

When the trader passes multiple tickers, the basket path computes a worst-of FCN using a correlation-adjusted joint KI probability. The basket coupon should exceed the worst single-name coupon by at least `(1 − correlation) × 30%` — anything less means the PB is not paying for diversification.

## 7. Income Structures (single-name)

The skill supports five income structures and refuses the rest. Risk posture summary: no naked calls; short puts must be cash-secured (sufficient cash to cover assignment at strike); multi-leg structures and collars use defined-risk option spreads. CSP and Jade Lizard's short put leg are cash-collateralized — the trader explicitly accepts assignment risk in exchange for credit.

| Structure | Cash / collateral requirement | Notable rules |
|---|---|---|
| Covered Call | Trader holds ≥ 100 shares of the underlying | Cannot sell more contracts than `floor(shares / 100)` |
| Cash-Secured Put | Trader has cash ≥ strike × 100 × contracts | No margin leverage on the short put leg |
| Defined-risk credit spread (PCS / BCS / IC) | Buying power ≥ max loss | Two legs same expiry, same underlying |
| Collar | Trader holds ≥ 100 shares | Put strike below call strike, same expiry |
| Jade Lizard | Short put cash-secured + short call spread | Net credit must be ≥ short call spread width (eliminates upside loss). Banned when bullish conviction is strong, because capped upside punishes you in a rally. |

### 7.1 Strong-Bullish-Conviction Test (Jade Lizard Veto)

If three or more of the following signals concur for the ticker, Jade Lizard is forbidden and the skill recommends naked CSP, bull put spread, or long calls:

- Recent earnings beat with a ≥ 5% gap-up that the tape absorbed (no fade)
- Three or more independent channel checks pointing the same direction
- A thematic re-rate that has already shown follow-through
- Inverted IV term structure that has normalized

The veto exists because capped-upside structures fail when the underlying actually rallies through the short call spread.

### 7.2 Rejected Structures

The skill explicitly rejects (with explanation, even when asked directly):

- Naked short calls
- Margin-leveraged short puts (cash-secured only)
- Ratio spreads with unhedged sides (1:2 or wider, infinite-risk wing)
- Calendars / diagonals where the long leg expires before the short leg
- FCN orders through IB (the FCN path produces a counter-offer email, not an order)

## 8. Macro Hedge Module

A parallel category to the income structures. Goal: protect the trader's short-vol book against a market drawdown, not generate income.

### 8.1 Sizing Cap

Total annualized hedge premium ≤ 1.5% of portfolio net liquidation value. Above that the hedge is too expensive relative to its protection benefit.

### 8.2 Three Supported Structures on SPX / SPY / NDX / QQQ

| Structure | Use when | Cost profile |
|---|---|---|
| Put butterfly | Trader has a specific drawdown target (e.g., −7%) | Lowest cost, requires accurate landing |
| Put spread | Trader expects a drawdown but unsure of magnitude | Medium cost, broader coverage |
| Long OTM put | Trader fears a ≥ −15% tail event | Highest cost, largest crash payout |

### 8.3 `macro_hedge.py` Interface

```
build_macro_hedge(portfolio_notional, hedge_horizon_days, scenario,
                  underlying="SPX", structure="auto",
                  max_annual_cost_pct=0.015) -> dict
```

`structure="auto"` maps scenario to default: mild correction → butterfly, deep correction → spread, crash → long put.

### 8.4 Trigger Heuristics (in `references/strategies.md`)

The skill proactively suggests adding or sizing-up macro hedge when:

- Total short vega across open positions exceeds a trader-set threshold
- VIX term structure flips into backwardation
- The trader opened three or more single-name short put positions in the past 30 days

## 9. Execution Module

### 9.1 IB MCP Two-Step Model

The IB MCP exposes `create_order_instruction` rather than direct execution. The skill creates an instruction; the trader approves it in TWS (Trader Workstation) before it becomes a working order. This separation gives a final out: even after `YES` in the skill, the trader can reject in TWS.

A paper-account dry run is mandatory before any live order. The skill verifies whether `create_order_instruction` produces a pending-approval state or a live order before being trusted with real capital.

### 9.2 Pre-Trade Pre-Flight (every order)

Before any `create_order_instruction` call, the skill displays:

- Underlying spot (from TradingView realtime)
- Each leg with action, right, strike, expiry, quantity, mid price
- Net debit or credit
- Max loss, max gain, breakeven points
- Margin / collateral required
- UW regime check (IV Rank, gamma flip, put wall, call wall, max pain)
- A P/L matrix at expiry for spot moves of −20% / −10% / −5% / 0 / +5% / +10% / +20%
- Account verification (buying power, existing positions)
- Liquidity check (bid-ask spread on each leg)
- Catalyst clock (earnings date relative to expiry)

The skill emits exactly one `YES / NO` question. Only `YES` triggers submission.

### 9.3 Default Bracket Orders

Every short-premium opening order is paired with two GTC orders in an OCA group:

| Trigger | Default | Configurable? |
|---|---|---|
| Take-profit | Close at 50% of max profit | Yes, per-order |
| Stop-loss | Close at 2× credit received (or 100% of max loss for spreads) | Yes, per-order |
| Time stop | Forced review at 21 DTE | No, this is a hard rule |

For long-vol macro hedges, only the take-profit bracket is set (lock in gains on +50% appreciation); stop-loss is not applied because the premium paid is the budgeted insurance cost.

### 9.4 21-DTE Hard Review

When any short-premium position reaches 21 days to expiry, the skill emits a blocking prompt the next time the trader interacts:

```
GAMMA WINDOW — POSITION REQUIRES DECISION TODAY

ORCL 240620 235 PUT SHORT × 5  (Bull Put Spread short leg)
  Current state: ...
  Three options: CLOSE / ROLL / HOLD-AND-ACCEPT-GAMMA
```

The trader must pick one before the skill answers any unrelated question. The point is to prevent ITM short options from drifting into expiry where gamma can cause severe overnight losses.

### 9.5 Roll Constraints

Rolls must satisfy all of:

- New position remains defined-risk
- Net of roll: either credit, or debit ≤ 50% of original credit
- New expiry does not span an earnings date for the underlying
- Structure preserved (CC rolls to CC; never to naked)

### 9.6 No-Assignment Policy

The trader prefers not to take assignment on short puts. The 21-DTE hard review is the primary defense — an ITM short put surfaced at 21 DTE must be rolled or closed before it can drift to expiry.

## 10. Position Management

`manage_positions.py` calls `get_account_positions` and emits a per-position row:

- Symbol, structure, opening date, opening price, current price, P/L
- DTE, current Greeks
- UW regime sanity check (e.g., is the strike still above gamma flip?)
- One-line action: `HOLD` / `CLOSE` / `ROLL` / `REVIEW`

A position with `REVIEW` status at 21 DTE moves to the top of the output with a blocking prompt as described in 9.4.

`evaluate_position.py` deepens a single row into four explicit options (close / roll up+out / roll out only / accept assignment) with the P/L for each and a recommendation tied to whether the trader's original thesis is still intact.

### 10.1 Automatic Daily Run

A Claude Code hook (configured in `~/.claude/settings.json`) runs `manage_positions.py` once per trading day within 30 minutes of US market open. Results are surfaced as a SessionStart context block so the trader sees status before issuing any other request.

The hook is enabled by default. The trader can disable it via a single config flag in `CLAUDE.md`.

### 10.2 Daily Email Delivery

Results from the daily run are also delivered by email to `chenxi.li08@outlook.com`. Delivery uses Gmail SMTP from a `scripts/email_sender.py` helper, authenticated with a Gmail App Password stored outside the repo (either an OS-level env var `GMAIL_APP_PASSWORD` or a file at `~/.config/option-wizard/gmail-app-password` with `0600` permissions). The App Password and sender Gmail address are not committed.

The Gmail MCP available in this environment exposes `create_draft` but not `send_message`, so the email path cannot run through MCP alone. SMTP is the simplest fully-automated alternative; the implementation phase will add `scripts/email_sender.py` and the hook glue.

Email payload structure:

- Subject: `[option-wizard] YYYY-MM-DD Daily position scan — N positions, M require review`
- Body (plain text + HTML alternative): same content as the in-session SessionStart block, plus a one-line summary header so it reads as a useful preview on mobile.
- Positions flagged at 21 DTE are prepended with `⚠` in the subject count and surfaced at the top of the body.
- If the daily run finds nothing actionable, the email still sends a "no action needed" one-liner so the trader knows the job ran.

Failure modes:

- SMTP credential missing or rejected → log to `~/.config/option-wizard/email-errors.log`, do not block the hook, surface the failure in the next SessionStart block.
- Email send timeout → retry once after 30 seconds, then log and continue.
- Manual override: a `--no-email` flag on `manage_positions.py` skips the send step for one-off runs.

## 11. SKILL.md Frontmatter

The `name` is `option-wizard`. The `description` enumerates triggers:

- Ticker mentions in trading context
- FCN / ELN quote review phrases ("PB quoted X% on Y")
- Strategy questions ("sell put on", "covered call on", "macro hedge")
- Position management ("check my positions", "is this position OK")
- Order execution ("place this order", "submit to IB")

Response language is Chinese with English technical terms preserved. Default risk posture is defined-risk only.

## 12. Installation

```
mkdir -p ~/projects/option-wizard
cd ~/projects/option-wizard
git init
# Implementation phase creates the file tree listed in Section 5
ln -s ~/projects/option-wizard/plugins/option-wizard/skills/option-wizard \
      ~/.claude/skills/option-wizard
```

UW MCP configuration is added to `~/.claude.json` with the user's bearer token sourced from an environment variable. The implementation plan provides the exact JSON snippet.

The daily hook for `manage_positions.py` is added to `~/.claude/settings.json` in the implementation phase.

## 13. Open Items for Implementation Phase

These were left intentionally for the implementation plan to resolve:

1. Confirm `create_order_instruction` behavior on a paper account before any live order is placed.
2. Confirm IB MCP support for OCA groups (bracket order linkage); fall back to manual cancel-on-fill detection in `manage_positions.py` if not supported.
3. Verify exact UW endpoint paths and JSON field names against the live API documentation; the paths in Section 4.2 were derived from the UW skill manifest and need confirmation before scripts are written.
4. Choose exact underlying for macro hedge (`SPX` cash-settled index vs `SPY` ETF — the trader picks during implementation).
5. Pick per-order position-sizing cap (suggested: ≤ 2% of account net liquidation value per single-name short-premium trade, ≤ 1.5% annualized total for macro hedge).
6. Default short-leg delta target for Sell Put / Bull Put Spread (suggested: −0.25 unless overridden).
7. Whether to publish to a GitHub repo for multi-machine sync via `npx skills add`.
8. Confirm the Gmail sender address and generate the App Password before the email hook is enabled. Sender address and password are not part of the repo.
9. Macro hedge Black-Scholes pricer omits dividend yield `q`. Negligible for SPX cash-settled index (~0% effective yield), but for SPY (~1.3% trailing yield) put values are slightly overpriced. Add `q` parameter if SPY becomes the default underlying.

## 14. Acceptance Criteria for v1

The skill ships when all of the following hold:

- Given a ticker and an FCN quote, output includes the 8-item checklist, fair coupon ladder, and a bilingual counter-offer email.
- Given a ticker without an FCN quote, output includes one full-menu recommendation across all five income structures plus a regime-aware fourth-structure pick where appropriate.
- Given two or three tickers, output includes a worst-of basket FCN analysis alongside per-name single-strategy picks.
- A paper-account run successfully creates a `create_order_instruction` for a defined-risk spread and the OCA bracket pair (or documents the fallback if OCA is not supported).
- `manage_positions` correctly emits a 21-DTE blocking prompt on at least one paper-account position.
- The daily run sends a test email successfully to `chenxi.li08@outlook.com` via Gmail SMTP with the expected subject format.
- A macro hedge call with `structure="auto"` returns one regime-routed recommendation with cost ≤ the configured cap. A separate `build_macro_hedge_menu` call returns up to three candidate structures (butterfly, spread, long put) ranked by cost-per-protection where applicable.
- Refusal path is exercised: asking for a naked short call must produce an explicit decline with reasoning.

## 15. Out of Scope for v1 (Future)

- ELN, accumulator, autocallable, and exotic basket structured products beyond FCN.
- Multi-account aggregation (the trader has only one IB account in scope).
- Tax-lot tracking and wash-sale handling.
- Notification delivery to Discord / Slack — only Gmail SMTP email to `chenxi.li08@outlook.com` is wired in v1.
- Cross-broker support (Futu, Longbridge, etc.).
