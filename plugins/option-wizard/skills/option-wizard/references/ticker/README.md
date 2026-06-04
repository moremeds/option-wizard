# Ticker Case Studies

Trade or analysis case studies. Each file documents one decision, the data behind it, and the outcome. Format: `<slug>-YYYY-MM.md` or `<slug>-YYYY-MM-DD-<event>.md`.

**Public case studies only** — anonymized, no account-specific NLV / position / fill numbers. Trader's personal trade journal (with full account data) lives in `private/` (gitignored, auto-archived by SKILL.md §"Reporting & archive").

| Slug | Period | Status | One-line |
|------|--------|--------|----------|
| orcl-2026-06-fcn | 2026-06 | closed | ORCL FCN strike ladder + gamma flip insight |

## Adding a public case study

1. Copy `_template.md` to `<slug>-YYYY-MM[-DD-event].md`
2. Fill in frontmatter (`ticker`, `event`, `date`, `status`, `result`, `structures`, `tags`)
3. **Strip all account-specific numbers** (NLV, cash, margin, position-quantity, fills). If the case relies on those numbers, archive to `private/` instead.
4. Capture the framework insight that generalizes (the orcl-2026-06-fcn case is the model — it teaches the gamma-flip rule without exposing account data)
5. Add a row to the table above

For personal trade journals (with full account data), see `private/README.md`.
