# Smoke tests

Standalone scripts that exercise external dependencies (UW REST, IB MCP)
**before** the full skill code exists. Each one is self-contained and
runnable with no project bootstrap.

## `uw_smoke.py`

Hits all 10 UW endpoints option-wizard depends on, against ORCL. Prints
HTTP status + observed top-level JSON keys per endpoint.

```bash
# from the project root, with UW_API_KEY in .env:
uv run scripts/smoke/uw_smoke.py
```

Endpoints verified on 2026-06-03 (all 200 OK against ORCL):

| Method | Path |
|---|---|
| iv_rank | `/api/stock/{ticker}/iv-rank` |
| realized_volatility | `/api/stock/{ticker}/volatility/realized` |
| historical_risk_reversal_skew | `/api/stock/{ticker}/historical-risk-reversal-skew` |
| iv_term_structure | `/api/stock/{ticker}/volatility/term-structure` |
| max_pain | `/api/stock/{ticker}/max-pain` |
| spot_gex_by_strike | `/api/stock/{ticker}/spot-exposures/strike` |
| interpolated_iv | `/api/stock/{ticker}/interpolated-iv` |
| greeks_by_strike | `/api/stock/{ticker}/greeks` |
| dark_pool | `/api/darkpool/{ticker}` |
| technical_indicator | `/api/stock/{ticker}/technical-indicator/{function}` |

The plan's `Task 1.1` UW client (`scripts/_clients/uw.py`) reflects these
verified paths inline.

## `ib_mcp_findings.md`

Static document recording what was verified about the IB MCP via direct
tool invocation on 2026-06-03. Not a runnable script — the IB MCP tools
live in the Claude session and can only be called from inside a Claude
Code conversation, not from a shell.

Key takeaways:

- `create_order_instruction` is **equity/ETF only** (no options).
- IB MCP has **no OCA semantics** — brackets must be attached via
  `ib_insync.bracketOrder(...)`.
- Instructions are **drafts** (separate `get_order_instructions` queue
  from `get_account_orders`), requiring user approval via deep-link.
