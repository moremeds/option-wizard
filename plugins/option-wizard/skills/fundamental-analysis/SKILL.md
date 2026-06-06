---
name: fundamental-analysis
description: >
  Equity fundamental analysis for US-listed tickers — pulls the financial
  fact sheet (revenue / margins / FCF / balance sheet / capital returns)
  and synthesizes a valuation read. Two depth modes: --depth=quick (3-section
  brief, ~5 min, slots into option-wizard's ticker analysis as a fundamentals
  layer) and --depth=deep (10-section LULU-style equity research report
  with peer matrix, historical PE percentile, turnaround case studies, EV
  scenario, MD+HTML+PDF export). Use when the trader asks about company
  quality, valuation re-rating, "why is the PE so low / high", "deep dive
  on X", "is this cheap / expensive", "fundamental analysis on X", peer
  comparison, long-term ownership thesis. NOT for trade-decision flow
  (use SKILL.md analysis-runbook for that — vol / GEX / preflight). Data:
  Unusual Whales (primary) for financials (get_income_statements /
  get_cash_flows / get_balance_sheets / get_fundamental_breakdown /
  get_earnings_history / get_analyst_ratings / get_ticker_performances /
  get_short_data_by_ticker / get_institution_holdings) + Massive REST
  (tertiary; api.massive.com, Polygon rebrand; requires $MASSIVE_API_KEY)
  for direct SEC 10-K URLs (source_filing_url), line-item financials,
  per-article news sentiment, related-companies auto peer-set, and daily
  short volume per-venue + TradingView for spot + WebSearch fallback for
  activist 13D / proxy fights (categories Massive news under-indexes).
  Chinese response with English technical terms (PE, EBITDA, FCF, ROE,
  margin, etc.). No fabrication — every quoted number cites source per
  shared/sources.md. Deep reports save to
  /Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/ in MD,
  HTML, PDF (public GitHub repo — do not save anything proprietary).
  Triggers on: "分析 X 基本面", "X 估值", "X 为什么 PE 这么低", "X 现在
  便宜吗", "X 公司质量怎么样", "深度研究 X", "fundamentals on X",
  "deep dive on X", "is X cheap", "equity research on X", "why is X PE
  so low", "compare X vs Y vs Z fundamentals".
---

# fundamental-analysis

Equity fundamental analysis skill. Two depth modes, one shared data
pipeline. Quick mode lives inside ticker analysis as a fundamentals
sub-layer; deep mode is a standalone research report (LULU-style).

## When to invoke which mode

| Trader signal | Depth | Why |
|---|---|---|
| "X 基本面怎么样" / "fundamentals on X" / no other qualifier | **quick** | Cheap default — 3 sections, no peer matrix. ~5 minutes. |
| Mentioned as a sub-step of `分析 <TICKER>` flow | **quick** | Drops into the existing 8-layer runbook as a fundamentals layer; do not derail into deep dive. |
| "深度研究 X" / "deep dive on X" / "全面分析 X" / "comprehensive" | **deep** | Full 10-section report with MD + HTML + PDF export. |
| "X 为什么 PE 这么低" / "why is X PE so low / high" | **deep** | Re-rating questions need peer matrix + historical PE percentile + scenario analysis. |
| "比较 X vs Y vs Z" with ≥ 3 peers | **deep** | Peer matrix only makes sense in deep mode. |
| Activist / turnaround / CEO change context | **deep** | Catalyst-driven re-rating thesis needs case-study comparables. |

When in doubt, ask the trader: "quick brief 还是 deep dive?"

## Hard rules

1. **No fabrication.** Every quoted number cites source via
   `shared/sources.md`. If UW returns null / empty / stale, mark it
   `UNVERIFIED` inline — do NOT fill in a plausible-looking guess.
2. **Source discipline.** Fundamentals from UW (`get_income_statements`,
   `get_cash_flows`, etc.) as primary; Massive REST as tertiary augment
   for direct SEC 10-K URLs, line-item financials, related-companies
   peer set, daily short volume, and news sentiment (requires
   `$MASSIVE_API_KEY` — if unset, fall back to UW only and flag the gap).
   Spot price from TV (not UW, not Massive — per
   `~/projects/option-wizard/CLAUDE.md` hard rule #2). Recent catalysts
   from Massive news with sentiment as primary; WebSearch for activist
   13D / proxy fights / regulatory actions only (categories Massive
   under-indexes).
3. **Freshness gate.** Same rule as analysis-runbook: any number
   > 1 trading day stale = `gap`, flag explicitly, do not extrapolate.
   For annual financials, "stale" means the most recent reported FY is
   the floor — flag if pulling from FY > 18 months ago.
4. **Annual not quarterly by default.** UW `get_income_statements`
   quarterly mode returns >75K chars and blows the context budget.
   Default to annual; pull quarterly ONLY when explicitly modeling
   trend/seasonality and you've planned for the token cost.
5. **Chinese response, English technical terms.** Per trader profile.
   PE / EBITDA / FCF / ROE / EPS / margin / capex / TTM / fwd / NTM
   stay English. Verdicts in Chinese.
6. **Deep mode generates 3 files.** MD source + HTML (pandoc standalone)
   + PDF (Chrome headless — see `[[pdf-generation-on-mac]]` memory).
   Save path per `[[research-report-storage]]` memory.
7. **No auto-commit.** Files land in
   `references/ticker/<TICKER>/` (public GitHub-synced); the trader
   controls when to push.
8. **No long-form output if quick mode.** Quick mode is 3 sections
   max. If your response is >40 lines, you're doing deep work — ask
   the trader to confirm before continuing.

## Flow

```
1. Parse args → depth ∈ {quick, deep}, ticker (required)
2. Pull data per shared/data-fetch.md (skip steps not needed for quick)
3. Compose report per quick/template.md OR deep/template.md
4. Verify every numeric claim has a source citation (shared/sources.md)
5. (Deep only) Write MD → HTML via pandoc → PDF via Chrome headless
6. Output: summary in chat; deep mode also lists 3 file paths
```

## When to read which file

| Step | Read |
|---|---|
| Data pull plan | `shared/data-fetch.md` |
| Citation format / source taxonomy | `shared/sources.md` |
| Quick mode report skeleton | `quick/template.md` |
| Deep mode report skeleton | `deep/template.md` |
| PDF generation chain | memory `[[pdf-generation-on-mac]]` |
| Save path convention | memory `[[research-report-storage]]` |

## What this skill does NOT do

- **Does not make trade decisions.** That's `skills/option-wizard/SKILL.md`
  (the 8-layer runbook). Fundamental conviction informs sizing and
  defined-risk structure choice elsewhere; this skill stops at the
  "buy / hold / pass" verdict on the equity itself.
- **Does not handle options-derivative metrics.** No IV rank, no GEX, no
  skew, no max pain. Those are L1-L4 in analysis-runbook.
- **Does not pull private bank quotes or place orders.** FCN/AQ/DQ flow
  lives in `aq-dq-framework.md` / `fcn-framework.md`; IB order flow
  lives in `execution.md`.
- **Does not cover crypto, futures, or non-US equities.** UW
  fundamentals coverage is US-listed only.
