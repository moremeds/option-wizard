# Quick-mode template

3 sections. Total output ≤ 40 lines (excluding tables). Chinese
narrative, English technical terms. Inline citations (don't generate a
footnoted Sources section for quick mode — append a one-line Sources
paragraph at the end).

## Section 1 — Snapshot

A 5-row data table. Pull these from the minimum data set defined in
`shared/data-fetch.md`. If a row is `null` / unavailable, mark
`UNVERIFIED` per `shared/sources.md`.

```markdown
## Snapshot

| 指标 | 数值 | 备注 |
|---|---|---|
| Spot | $XXX.XX | TV close YYYY-MM-DD |
| Market cap | $XX.XB | UW get_company_info |
| TTM PE | XX.Xx | spot ÷ TTM EPS = $X.XX |
| Forward PE | XX.Xx | CONSENSUS, source XYZ |
| 1Y return | ±XX% | UW get_ticker_performances |
```

Add a one-line "regime read":

> **Regime**: <growth at reasonable price / value re-rating / quality compounder / distressed turnaround / momentum stretched>

Pick one of those five labels — don't invent new ones.

## Section 2 — Fundamentals quick-take

4 bullets, each one tight sentence. Numbers must cite source inline.

```markdown
## Fundamentals

- **Revenue:** $XX.XB latest FY, +XX% YoY, 3Y CAGR XX% [UW: get_income_statements].
- **Margins:** Gross XX% / Op XX% / Net XX% — <trending up / stable / compressing X bp YoY>.
- **FCF:** $X.XB latest FY, FCF margin XX%, capex intensity XX% of revenue [UW: get_cash_flows].
- **Balance sheet:** Net debt $X.XB (or net cash), debt/EBITDA X.Xx — <strong / OK / stretched>.
```

If any of the four can't be sourced, write the bullet as
`UNVERIFIED — <reason>` rather than dropping the row.

## Section 3 — Verdict

One paragraph, four sentences max:

1. **One-line rating:** 买 / 持有 / 观望 / 回避 — and the single biggest reason.
2. **What the PE is pricing:** what does today's TTM PE imply the market believes? (Growth deceleration? Margin compression? Re-rating? Quality?)
3. **2-3 named catalysts:** dated if possible. ("Next earnings YYYY-MM-DD, FY guide update, CEO search outcome by Q3, etc.")
4. **What would change the verdict:** the single observable that would flip you from this rating to the next one (up or down).

Close with a one-line Sources paragraph:

```markdown
**Sources:** UW (get_company_info, get_income_statements, get_cash_flows,
get_ticker_performances, get_analyst_ratings), TV spot YYYY-MM-DD,
WebSearch (CEO context / catalyst).
```

## Output rules

- **No headers below H2.** Quick mode is flat — H1 title (optional, skip if conversational), H2 for the three sections, no H3 subdivisions.
- **No peer matrix.** That's deep-mode territory.
- **No scenario analysis.** Verdict only.
- **No file export.** Quick mode stays in chat — no MD/HTML/PDF write.
- **If the trader's follow-up asks for any of the above, switch to deep mode** (announce the switch — "升级到 deep mode 因为 X") and proceed with the deep template.

## When this template fails

If after the minimum data pull you don't have enough to write all three
sections (e.g., UW returned empty for income_statements, TV spot is
`STALE`, no analyst coverage), output a `BLOCKED` summary instead:

```
**BLOCKED — insufficient data**
- Missing: <list>
- Tried: <list>
- Next step: <suggest WebSearch / WebFetch / manual lookup>
```

Don't paper over the gap with a guess. That's the global no-fab rule.
