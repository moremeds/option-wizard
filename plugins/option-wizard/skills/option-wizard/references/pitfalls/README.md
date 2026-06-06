# Pitfalls

Accumulated trading mistakes and the rules they generated. Each pitfall is a short markdown file. Format: `NN-slug.md`. The index below populates over time.

| # | Slug | One-line |
|---|------|----------|
| 01 | [vix-options-track-futures-not-spot](01-vix-options-track-futures-not-spot.md) | Far-dated VIX call spreads track the VX future for that expiry, not spot VIX — use front-week VIX or SPX put spread for short-term hedges |
| 02 | [aq-pb-yield-is-implicit](02-aq-pb-yield-is-implicit.md) | PB AQ quotes have no explicit yield — it's encoded in the strike discount × accumulation; use `pb_quoted_yield_pa=None` and implicit-yield mode |

## Adding a pitfall

1. Copy `_template.md` to the next sequence number: `01-something-i-did-wrong.md`.
2. Fill in the sections.
3. Add a row to the table above.
