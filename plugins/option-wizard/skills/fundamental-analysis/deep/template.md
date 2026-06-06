# Deep-mode template

10-section equity research report, modeled on the LULU report
(`/Users/chenxi/projects/option-wizard/references/ticker/LULU/LULU_Report_2026-06-06.md`).
Generates 3 files: MD source + HTML (pandoc) + PDF (Chrome headless).

Chinese narrative, English technical terms. Footnoted citations
per `shared/sources.md` (NOT inline — the report is long; inline
citations clutter).

## Pre-flight

Before writing a single section:

1. **Confirm peer set.** Ask the trader if you don't already know who counts as a comparable. Default heuristic: same GICS sub-industry + similar revenue scale (within 5x). Aim for 4-7 peers.
2. **Define a "closest peer"** for the head-to-head (Section 6). This is the name whose business model most closely mirrors the target — usually the highest-revenue overlap competitor.
3. **Identify 1-2 turnaround comparables** for Section 5. These are NOT necessarily current peers — they're historical analogues where a similar name went through PE compression and re-rated (up or down). E.g., for LULU you used ANF + AEO (specialty retail PE-floor analogues), not Nike.
4. **Verify save path exists:** `mkdir -p /Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/`.
5. **Verify Chrome path:** `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome` (see `[[pdf-generation-on-mac]]` memory). If missing, fall back to MD + HTML only and flag.

## Section 1 — Executive summary

3-4 paragraphs. The full report compressed into something the trader
can read in 60 seconds.

Required content:
- **One-line thesis:** "<TICKER> 是 <quality / value / turnaround / momentum / pass>,因为 <single biggest reason>。"
- **Today's valuation:** spot, TTM PE, fwd PE, market cap.
- **What the PE is pricing:** the implied market belief (deceleration, margin compression, structural decline, etc.).
- **Recommendation:** 买 / 加仓 / 持有 / 减仓 / 回避 + sizing band (e.g., 2-4% NLV).
- **Key catalysts in the next 6 months:** 2-3 dated events.

Avoid hedging language ("might consider"). Per trader profile: concrete
numbers, structures, verdicts.

## Section 2 — Valuation anatomy

Why does the PE look the way it does? Breakdown table + narrative.

```markdown
| 组件 | 数值 | 暗示 |
|---|---|---|
| Spot price | $XXX.XX | — |
| TTM EPS | $XX.XX | 来源 last 4 Q earnings |
| TTM PE | XX.Xx | 历史 percentile XX% |
| Forward EPS (NTM) | $XX.XX | CONSENSUS |
| Forward PE | XX.Xx | growth assumption: XX% |
| EV / EBITDA | XX.Xx | net debt = $X.XB |
| EV / Sales | X.Xx | — |
| FCF yield | X.X% | FCF / market cap |
```

Then a narrative paragraph: what's the bear case priced in? Is it
margin compression, revenue deceleration, terminal-value uncertainty,
sector-wide derate?

## Section 3 — Peer matrix (horizontal compare)

Single wide table. One row per peer. Required columns:

```markdown
| Ticker | Mkt cap | Rev TTM | Rev growth | Op margin | Net margin | FCF margin | Net debt / EBITDA | TTM PE | Fwd PE | EV/EBITDA | ROE | 1Y return |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **<TARGET>** | | | | | | | | | | | | |
| Peer 1 | | | | | | | | | | | | |
| ...   | | | | | | | | | | | | |
```

Bold the target row. After the table, write 2-3 paragraphs:
- Where the target ranks (top quartile / median / bottom) on margin, growth, balance sheet.
- The single most striking dispersion (e.g., "target has 2x peer median net margin yet trades at peer-bottom PE").
- Any peer with a noisy / outlier number — flag and explain (e.g., "Peer X TTM PE meaningless because of one-time goodwill impairment last quarter").

## Section 4 — Historical PE percentile

Where does today's TTM PE sit in the target's own 5-year (and 10-year if available) range?

```markdown
| 时期 | PE 低点 | PE 高点 | 中位数 | 今日 PE 百分位 |
|---|---|---|---|---|
| 5-year | X.Xx | XX.Xx | XX.Xx | XX% |
| 10-year | X.Xx | XX.Xx | XX.Xx | XX% |
```

Narrative paragraph: what's the historical context? Has the company
been at this PE before, and what happened next? Did margins normalize?
Did the multiple expand or contract from here?

If you don't have 10-year history (newer IPO), say so explicitly — do
not extrapolate.

## Section 5 — Turnaround case studies

1-2 analogous names that went through a similar PE compression and
either re-rated (up or down). For each:

```markdown
### Case study: <ANALOG TICKER> — <one-line setup>

**Then:** <year>, PE bottomed at X.Xx after <catalyst>.

**Why it bottomed:** <2-3 sentences>.

**What changed:** <2-3 sentences — operational fix, mgmt change, sector tailwind, etc.>

**Re-rating:** <year>, PE expanded to XX.Xx over <duration>.

**Applicability to <TARGET>:** <2-3 sentences — what's similar, what's
different, where the analogy breaks down>.
```

The "where the analogy breaks down" part is mandatory. Don't sell the
analog as a clean comp if it isn't.

## Section 6 — Head-to-head vs closest peer

Side-by-side detailed compare. Same metrics as Section 3 but with more
explanation per row.

```markdown
| 指标 | <TARGET> | <CLOSEST PEER> | 解读 |
|---|---|---|---|
| Revenue TTM | | | |
| Revenue growth 3Y CAGR | | | |
| Same-store-sales / unit growth | | | <if applicable to sector> |
| Gross margin | | | |
| Op margin | | | |
| Net margin | | | |
| ROIC | | | |
| FCF / share | | | |
| Net debt / EBITDA | | | |
| Buybacks 3Y | | | |
| TTM PE | | | |
| Fwd PE | | | |
| 5Y total return | | | |
```

Close with a verdict paragraph: which name is the better risk-adjusted
bet today, and why?

## Section 7 — Scenario analysis (probability-weighted EV)

4 scenarios. Each gets a probability, a target price, and a one-line
trigger description.

```markdown
| 场景 | 概率 | 目标价 | 触发条件 |
|---|---|---|---|
| 牛市 (full re-rating) | XX% | $XXX | <what has to happen> |
| 基本 (multiple holds, EPS grows) | XX% | $XXX | <what has to happen> |
| 熊市 (margin compression continues) | XX% | $XXX | <what has to happen> |
| 灾难 (structural break) | XX% | $XXX | <what has to happen> |
```

Probabilities MUST sum to 100. Compute the expected value:

> **EV = ΣᵢPᵢ × Targetᵢ = $XXX (+XX% vs spot $YYY)**

Show the arithmetic. This is the central output of the report — the
single number that answers "what's it worth today, probability-adjusted".

## Section 8 — Bull vs bear (two-column thesis)

```markdown
| 牛市论点 | 熊市论点 |
|---|---|
| 1. ... | 1. ... |
| 2. ... | 2. ... |
| 3. ... | 3. ... |
| 4. ... | 4. ... |
| 5. ... | 5. ... |
```

Aim for 4-6 points per side. Each point one sentence. Don't repeat
points across columns — if the bear case is the inverse of the bull
case, write only one of them (whichever is more decisive).

## Section 9 — Analyst ratings + catalyst calendar

Two sub-tables.

```markdown
### 分析师评级 (as of YYYY-MM-DD)

| 评级 | 数量 | 占比 |
|---|---|---|
| Strong Buy | | |
| Buy | | |
| Hold | | |
| Sell | | |
| Strong Sell | | |

平均目标价: $XXX (range: $XX – $XX)

### 催化剂日历

| 日期 | 事件 | 重要性 (1-5) |
|---|---|---|
| YYYY-MM-DD | Next earnings | 5 |
| YYYY-MM-DD | <CEO announcement> | |
| YYYY-MM-DD | <FY guide update> | |
| YYYY-MM-DD | <product launch / capital markets day> | |
```

## Section 10 — Final verdict

The single most important section. Compresses the whole report into a
decision.

```markdown
### 评级
**买 / 加仓 / 持有 / 减仓 / 回避** — <one-line reason>.

### 仓位建议
**仓位 X-Y% NLV** — <why this band — conviction × beta × catalyst clarity>.

### 实现路径 (3 个选项,按优先级)

1. **<最推荐结构>** — <strike, expiry, why>. <If this is M7 buy-and-hold per trader profile, link to protective put / collar instead>.
2. **<次推荐>** — <when this is better>.
3. **<观望触发条件>** — <if you don't pull the trigger now, what would be the signal that says "now">.

### 翻车信号 (what would flip me to <opposite rating>)

- <observable 1>
- <observable 2>
- <observable 3>

### 时间窗口
<thesis horizon — quarters to play out, when to revisit>.
```

## Sources section

End the report with a `## Sources` section per the template in
`shared/sources.md`. Group by Financials / Filings / News / Market data.

## File export (after the MD is written)

Three files, all under `/Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/`.
Filename convention from `[[research-report-storage]]` memory:
`<TICKER>_Report_<YYYY-MM-DD>.{md,html,pdf}`.

### Step 1 — Write MD

Use the Write tool. Already done if you got here.

### Step 2 — MD → HTML via pandoc

```bash
pandoc \
  /Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/<TICKER>_Report_<DATE>.md \
  -o /Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/<TICKER>_Report_<DATE>.html \
  --standalone \
  --metadata title="<TICKER> 基本面分析 — <DATE>"
```

If you want inline CSS for Chinese fonts (PingFang SC) + table styling,
add `-H` with a small style block (write the style to a temp file
first; pandoc rejects raw HTML on the CLI).

### Step 3 — HTML → PDF via Chrome headless

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=/Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/<TICKER>_Report_<DATE>.pdf \
  "file:///Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/<TICKER>_Report_<DATE>.html"
```

Stderr noise (`DEPRECATED_ENDPOINT`, allocator warnings) is harmless —
verify the file landed with `ls -la`. See memory
`[[pdf-generation-on-mac]]`.

### Step 4 — Report file paths in chat

End the chat response with:

```
📂 文件
- MD:   /Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/<TICKER>_Report_<DATE>.md
- HTML: /Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/<TICKER>_Report_<DATE>.html
- PDF:  /Users/chenxi/projects/option-wizard/references/ticker/<TICKER>/<TICKER>_Report_<DATE>.pdf
```

Do NOT auto-commit. The trader controls the git push.

## What this template forbids

- **Fewer than 10 sections.** If you can't fill a section meaningfully, write it as `**Section X — <title> (limited data)**` with the gap explained. Do not silently drop sections.
- **Sections without numeric backing.** Every table must have at least one cited number. A table that's all `UNVERIFIED` should be deleted, not published with placeholders.
- **Sell-side language.** Don't write "we believe", "we see", "the company appears poised to". Write subject-verb-object: "LULU's net margin is 14.2% [UW: get_income_statements]. Peer median is 7.5%."
- **Conclusion before evidence.** The 牛/熊 case must follow the data tables, not lead them.
- **Skipping the scenario EV calc.** Section 7's expected value is the single most-used output. If you can't produce it (probabilities can't be defended), say so — but don't replace it with a hand-wavy "fair value range".
