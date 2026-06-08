---
name: fundamental-analysis
description: >
  Equity fundamental analysis for US-listed tickers. Two modes: quick
  (3-section brief, slots into ticker analysis as fundamentals layer)
  and deep (11-section LULU-style report with peer matrix, PE percentile,
  turnaround case studies, EV scenario, MD+HTML+PDF export). Use for
  "deep dive on X", "is X cheap", "X 估值", "X 为什么 PE 这么低",
  "深度研究 X", "fundamentals on X", "equity research on X", peer
  comparison, long-term ownership thesis. NOT for trade-decision flow
  (use option-wizard SKILL.md for vol / GEX / preflight). Data: UW MCP
  for financials, Massive REST for SEC URLs + news sentiment + peer set
  + daily short volume, TradingView for spot, WebSearch for activist
  13D / proxy fights. Chinese response with English technical terms.
  No fabrication — every number cites source per shared/sources.md.
  Deep reports save to references/ticker/<TICKER>/ (public repo —
  strip proprietary NLV / positions before save).
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
| "深度研究 X" / "deep dive on X" / "全面分析 X" / "comprehensive" | **deep** | Full 11-section report with MD + HTML + PDF export. |
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
   `plugins/option-wizard/skills/fundamental-analysis/references/ticker/<TICKER>/`
   (lives inside the skill dir — committed alongside skill source as
   example artifacts); the trader
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
  fundamentals coverage is US-listed only. **ADRs are US-listed and
  covered, but with documented data caveats — see Known limitations.**

## Known limitations (observed in production runs)

These are real gaps surfaced when the skill was dogfooded end-to-end. Acknowledge them in the report's Sources/Gaps section rather than papering over.

- **TV reader skill is not invokable from Bash-tool sessions.** CLAUDE.md hard rule #2 names TradingView as the canonical spot source, but `finance-data-providers:tradingview-reader` is a Claude Code skill — it can only be invoked when the main option-wizard SKILL flow drives it. When fundamental-analysis runs standalone (`深度研究 X` triggers it directly), spot must come from Massive `/v3/snapshot/...` (preferred) or UW `get_company_info.price` (fallback). Flag the deviation in Gaps.

- **ADR data quality is uneven.** Surfaced on NVO 2026-06-06 run:
  - Massive `/v1/related-companies/<ADR>` often returns empty — go straight to manual peer selection by GICS sub-industry.
  - Massive `/v3/snapshot/.../<ADR>` returns 404 for some ADRs — fall back to UW spot.
  - UW `get_company_info.outstanding` may report a single share class (e.g., NVO B-shares only) — use Massive `weighted_shares_outstanding` for market cap.
  - Financials report in home currency (DKK for NVO, EUR for SNY); derive FX rate from `fundamental_breakdown.share_price` ÷ EPS or via WebSearch.
  - `get_earnings_history` may mix pre- and post-split quarters — prefer `fundamental_breakdown` EPS over summing quarters.

- **Historical PE percentile requires self-computation.** Neither UW nor Massive ships a pre-built PE series. See `deep/template.md` Section 4 for the three-tier fallback (self-compute via aggs + EPS / cite secondary source with CONSENSUS / skip with UNVERIFIED).

- **Massive endpoints are not fully documented for cross-asset behavior.** When a path that works for US common stocks returns 404 or empty for an ADR / OTC / preferred share, the first hypothesis should be "this endpoint may not cover this asset class" — don't retry the same path 3x.
