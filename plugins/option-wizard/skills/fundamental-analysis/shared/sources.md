# Citation discipline

Every quoted number in the report must cite its source. This is the
defense against the global no-fabrication rule from
`~/.claude/CLAUDE.md`.

## Source taxonomy

Six source types covered by this skill. Each gets a specific citation
format.

| Source type | When | Citation format |
|---|---|---|
| **UW MCP tool** | Financial fundamentals (revenue, margins, FCF, balance sheet, performance, ratings) | `[UW: get_<tool>]` after the number, OR group at the end of the section |
| **Massive REST** | Line-item financials with direct SEC URL, ticker overview (CIK/SIC), related companies, daily short volume, short interest | `[Massive: <endpoint>]`, e.g. `[Massive: /vX/reference/financials]`. When citing a number whose `source_filing_url` is populated, prefer the SEC link form instead — see SEC row below. |
| **TradingView** | Spot price, intraday, technicals, news | `[TV: <symbol>, <date>]` |
| **SEC filing (10-K / 10-Q / 13F / 13D / DEF 14A)** | Audited annuals, beneficial ownership, proxy material | `[10-K FY<year>, p. <page>]` with markdown link **pulled from Massive financials `source_filing_url`** (do not hand-construct EDGAR URLs — see "What you may NOT do" below). If Massive lacks the row, link only when WebFetched. |
| **Company press release / investor relations** | Guidance, CEO announcements, buyback authorizations | `[<Company> IR, <YYYY-MM-DD>]` with link |
| **Massive news + sentiment** | Recent catalysts (CEO changes, guidance, product, M&A rumors) | `[Massive news, <YYYY-MM-DD>, sentiment: <positive\|neutral\|negative>]` with `article_url` as the link. Quote `sentiment_reasoning` verbatim if you're going to lean on the sentiment label. |
| **Tier-1 news (WSJ / FT / Bloomberg / Reuters / CNBC) via WebSearch** | Activist 13D disclosures, proxy fights, regulatory actions (categories Massive news under-indexes) | `[<Outlet>, <YYYY-MM-DD>]` with link |
| **Analyst report** | Sell-side PT changes, rating actions | `[<Bank> analyst, <YYYY-MM-DD>]` — only cite if the analyst report was directly read; do NOT cite analyst rationale you inferred |

## Citation placement

Two acceptable patterns — pick one and stay consistent within a report:

**Inline:**
> LULU revenue grew 10.4% YoY to $10.6B in FY25 [UW: get_income_statements].

**Footnoted Sources section at the end of the report:**
```
LULU revenue grew 10.4% YoY to $10.6B in FY25.[^1]

...

## Sources
[^1]: UW get_income_statements (annual), pulled 2026-06-06
[^2]: TV NASDAQ:LULU spot, 2026-06-06 close
[^3]: LULU 10-K FY24, p. 47 — https://...
```

Deep mode reports MUST use the footnoted pattern (cleaner output).
Quick mode can use inline.

## Uncertainty markers

Per global CLAUDE.md "Flag uncertainty inline" rule:

| Tag | When to use |
|---|---|
| `UNVERIFIED` | Source not available, number came from memory or rough estimate, OR data field was null/empty in UW |
| `STALE` | Number > 1 trading day old (per freshness gate) — same standard as analysis-runbook L0 |
| `CIRCA` | Year-over-year deltas where the exact basis-period number isn't pinned (e.g., "revenue grew ~10% YoY" — use only if you don't have both endpoints) |
| `CONSENSUS` | NTM forward EPS / forward PE — these are by definition estimates, not facts |

Example:
> Forward PE ~10.3x [CONSENSUS, source: WebSearch Yahoo Finance, 2026-06-05].
>
> Q1 FY26 same-store-sales decline: [UNVERIFIED — pulled from press summary, not 10-Q].

## What you may NOT do

- **Hand-construct SEC EDGAR URLs.** Either use the `source_filing_url` field returned by Massive `/vX/reference/financials` (the canonical source) or WebFetch the actual filing page; never assemble an EDGAR path from an accession number guess. EDGAR URLs follow a stable pattern but the accession numbers must be real.
- **Cite Massive sentiment as if it were proprietary analysis.** The `sentiment` + `sentiment_reasoning` fields are machine-classified from the article body. When the trade decision hinges on the sentiment, quote `sentiment_reasoning` verbatim so the trader sees what the classifier saw — don't paraphrase it into "Massive is bullish."
- **Cite analyst rationale you didn't read.** "JPM says..." requires the actual note. Citing only the published headline (rating + PT) is fine if pulled from a credible aggregator.
- **Cite "internal model" or "house view."** This skill is a research output, not a proprietary model. If the number is computed, write out the computation (`PE = $114 / $12.39 EPS = 9.2x`) rather than hiding it behind a "model" label.
- **Use Yahoo Finance as primary fundamental source.** Cross-validation only — primary is UW or Massive or the actual 10-K. CLAUDE.md global rule (option-wizard CLAUDE.md inherits): "Never Yahoo Finance as primary."
- **Round and present as exact.** $10.6B is fine. $10,567,212,000 implies precision you don't have unless that's the exact 10-K figure.

## Sources section template

Every deep-mode report ends with a section like this:

```markdown
## Sources

### Financials
- [^uw-inc]   UW `get_income_statements` annual — pulled 2026-06-06
- [^uw-cf]    UW `get_cash_flows` annual — pulled 2026-06-06
- [^uw-bs]    UW `get_balance_sheets` annual — pulled 2026-06-06
- [^uw-eh]    UW `get_earnings_history` — pulled 2026-06-06
- [^mass-fin] Massive `/vX/reference/financials` annual (line-item, with `source_filing_url`) — pulled 2026-06-06

### Filings
- [^10k]    <TICKER> 10-K FY<year> — [SEC EDGAR](https://...) (URL from Massive financials `source_filing_url`)
- [^13f-Q1] <Holder> Q1 2026 13F — [SEC EDGAR](https://...)

### Company overview
- [^mass-tk] Massive `/v3/reference/tickers/<TICKER>` (CIK, SIC, employee count) — pulled YYYY-MM-DD

### Peer set
- [^mass-rel] Massive `/v1/related-companies/<TICKER>` — peer cohort source, pulled YYYY-MM-DD

### News
- [^mass-news-1] Massive news — "Headline", YYYY-MM-DD, sentiment: <positive/neutral/negative> — [link](article_url)
- [^wsj-1]       WSJ "Headline", YYYY-MM-DD — [link](https://...)  (WebSearch — categories Massive under-indexes: activist 13D, proxy)

### Market data
- [^tv-spot]    TV NASDAQ:<TICKER> spot, YYYY-MM-DD close
- [^uw-perf]    UW `get_ticker_performances` — pulled YYYY-MM-DD
- [^mass-shv]   Massive `/stocks/v1/short-volume` daily per-venue — pulled YYYY-MM-DD
```

Quick mode reports can compress this to a single "Sources" paragraph.
