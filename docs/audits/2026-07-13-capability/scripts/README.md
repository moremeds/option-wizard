# Capability-audit scripts — 2026-07-13

Scripts used to produce the data behind the 2026-07-13 capability audit
(markout validation of archived calls + live regime snapshot). Run with the
repo venv: `.venv/bin/python <script>` from the repo root (they import
`scripts._clients.*` via the same sys.path convention as tests).

Data files live in `private/audits/2026-07-13/` (gitignored — calls are
extracted from the personal analysis archive):

- `calls.json` — 52 falsifiable calls extracted from
  `plugins/option-wizard/skills/option-wizard/references/private/` +
  the stale `references/private/` tree (agent-extracted, schema in file)
- `prices.json` — daily closes 2026-06-01 → 2026-07-10 per ticker, source
  per ticker recorded inline (UW `get_ticker_close_prices` / massive)
- `markouts.json` — per-call T+1/T+5/T+10/T+21 returns, verdicts vs the
  review-framework ±2% band, σ-context
- `refs.txt` — source/endpoint notes from the pull agents

## Scripts

| Script | Role |
|---|---|
| `compute_markouts.py` | Joins calls.json × prices.json → markouts.json. Trading-day offsets, ±2% verdict per review-framework, σ-context (move / daily σ × √h), prior-verdict cross-check. |
| `uw_pull.py`, `uw_pull2.py` | UW REST pulls via the repo's own `UWClient` — iv_rank / term structure / skew for the regime snapshot (doubles as a live smoke test of `_clients/uw.py`). |
| `uw_spx_retry.py` | SPX skew retry — confirmed the endpoint returns empty for SPX (recorded as a genuine gap, not retried further). |
| `vix_pull.py` | VIX level + IV rank via UW REST. |
| `gex_compute.py` | Feeds UW `get_greek_exposure_by_strike` rows (SPX/QQQ) through the repo's `scripts/gex_levels.py::compute_levels` — gamma flip / put wall / call wall. Caveat recorded: all-expiry aggregate, per-expiry pull unused (see audit). |
| `fred_pull.py` | HY OAS via `scripts/_clients/fred.py::hy_oas_signal()`. Failed in this session: sandbox proxy blocks TLS to api.stlouisfed.org (domain allowlist gap, not a code/key problem — reproduced twice). |

All numbers in the audit trace to these scripts' output or to MCP tool
responses quoted in the audit doc; no fabricated values.
