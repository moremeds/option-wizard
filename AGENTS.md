# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Dev commands

```bash
uv sync --all-extras          # install deps + dev extras
.venv/bin/pytest              # run full unit suite
.venv/bin/pytest tests/test_xenon_client.py -v   # single file
.venv/bin/pytest tests/test_xenon_client.py::test_health -v  # single test
XENON_KEY=... XENON_BASE=http://... .venv/bin/pytest tests/integration/ -v -s
uv run ruff check .           # lint (ruff is a dev dep)
```

## Architecture

All skill logic lives under `plugins/option-wizard/skills/option-wizard/`:
- **`scripts/`** — business logic. Each module is one workflow stage.
- **`scripts/_clients/`** — thin HTTP wrappers (`xenon.py`, `uw.py`, `tv.py`, `ib.py`, `fred.py`). No business logic; just auth + HTTP + retry.
- **`references/`** — authoritative policy docs (`SKILL.md`, `analysis-runbook.md`, `review-framework.md`, etc.). These are the source of truth for trading rules; the code enforces them.
- **`tests/`** at repo root. `tests/conftest.py` inserts the skill root onto `sys.path` so tests import `from scripts.X import Y` directly — no install needed.
- **`tests/integration/`** — live smoke tests, skipped unless `XENON_KEY` is set.

Key scripts and their role:
| Script | Role |
|---|---|
| `manage_positions.py` | Daily scan — reads book + greeks from xenon, runs `defined_risk_audit`, emails report |
| `live_quote.py` | `live_quote()` — xenon `/options/greeks` primary, ib_insync fallback, no BSM |
| `xenon_normalize.py` | Pure JSON→internal-shape mappers from xenon `/portfolio` + `/futu/portfolio` |
| `retrospective.py` | 复盘 weekly/monthly review — markout scoring via `parse_xenon_blotter()` + archive |
| `defined_risk_audit.py` | `audit_book()` — flags uncovered CSPs / naked shorts against cash balance |
| `xenon.py` | CLI shim: `python -m scripts.xenon <path> [-p K=V]` for ad-hoc xenon probing |

`private/` is gitignored — personal profile, NLV, journal, positions never leave the machine. Copy `docs/setup/trader-profile.md.example` → `private/trader-profile.md` to activate personal overrides.

Required env vars (`.env`, gitignored — see `.env.example`): `XENON_BASE`, `XENON_KEY`, `UW_API_KEY`, `IB_HOST`, `IB_PORT`.

---

## Trading policy (working agreements)

Generic skill philosophy below; personal trader preferences (broker
setup, language, response style, macro budget) come from
`private/trader-profile.md` when present.

## Data source order (universal)

1. **Unusual Whales MCP / REST API** — options-derivative metrics only UW serves: IV rank, RV, GEX by strike, skew, IV term structure, max pain, dark pool, flow, greeks / interpolated IV; **also serves chain mid / IV / greeks (analytical-mode default for AQ/DQ/FCN fair-value)**. Never use UW for spot or technical indicators.
2. **TradingView via `finance-data-providers:tradingview-reader`** — the canonical source for spot (default), OHLCV, technical indicators (SMA / EMA / RSI / MACD / BBANDS / ATR / volume bars), news, alerts, watchlists, chart structure. UW `get_extended_technical_indicator` / `get_ticker_indicator_series` are forbidden for L3 analysis (series lagged by weeks).
3. **xenon Query API** (read-only, base `XENON_BASE`, header `X-API-Key` from `XENON_KEY`) — **PRIMARY for account state (IB *and* Futu): `/portfolio`, `/futu/portfolio`, `/orders`, `/blotter`, `/journal`, `/performance`**; live **mid / NBBO / L2 liquidity** (`/market-depth`); live **per-contract greeks / IV** (`/options/greeks`, IB `modelGreeks`) for live-trade-mode decisions (<60s window, AQ/DQ "PB just quoted me"). **No client-side BSM** — greeks always from a live broker quote. Ad-hoc: `python -m scripts.xenon <path>` or `curl -H "X-API-Key: $XENON_KEY" "$XENON_BASE<path>"`.
4. **Interactive Brokers / ib_insync** — `ib_insync` for option **order submission** with brackets (execution stays here; xenon never routes orders). **Fallbacks** (when xenon is unreachable): IB MCP read tools for account state, `reqMktData` `modelGreeks` for live greeks, `get_price_snapshot` for spot. Do NOT use IB for IV rank / skew / GEX / max pain (IB doesn't compute these derivatives).

The invariant: **xenon** = state + live mid/liquidity + live greeks; **UW** = options-analytics aggregates + analytical-mode greeks; **TV** = spot/technicals; **ib_insync** = execution + fallback greeks.

Secondary brokers (Futu, Tastytrade, Schwab, etc.) — Futu is served through
xenon `/futu/portfolio`; others are configured in `private/trader-profile.md`
if used.

## Hard rules (summary; authoritative list in SKILL.md)

See `plugins/option-wizard/skills/option-wizard/SKILL.md` for the full
text. Summary:

1. **Defined-risk only** — no naked short calls, no margin-leveraged
   short puts.
2. **Source discipline** — xenon = account state (IB+Futu) + live
   mid/liquidity + live greeks/IV (no client-side BSM); UW = options
   analytics aggregates + analytical greeks; TV = price + technicals;
   ib_insync = execution + fallback greeks.
3. **Preflight + one YES/NO** — every order shows legs, mid, max
   loss/gain, BE, margin, P/L matrix (±5/10/20%), account check, UW
   regime check, liquidity, catalyst clock.
4. **21 DTE in book-review Action items** — not a mid-flow blocking
   YES/NO. Trader picks close / roll / hold from the consolidated menu.
5. **PB structured products (FCN / AQ / DQ): no IB ORDER ROUTING; IB MARKET DATA is allowed.** Order routing is forbidden (PB products are OTC bilateral, never submit through IB). IB broker-feed chain data (mid/IV/greeks via the MCP) is allowed as a `Snapshot.chain` source when in live-trade mode (per hard rule #2). Output is product-specific bilingual counter-offer + verdict per `aq-dq-framework.md` / `fcn-framework.md`. AQ/DQ additionally short-circuits on 7 refusal red lines before any chain pull.
6. **Bracket defaults** — TP at 50% max gain, SL at 2× credit received.
7. **Freshness gate (live-first)** — pull live at analysis time and walk
   the per-data-point acquisition ladder before declaring any gap;
   avoidable stale-data caveats are not acceptable, genuine gaps stay
   honest (state what was tried) and are never extrapolated/fabricated.
8. **Ticker analysis structure non-negotiable** — opens with the Layer
   Coverage table from `references/analysis-runbook.md`.
9. **复盘 source separation** — archive = analysis quality only; broker
   (IB + Futu, both required) = trade flow only; never cross-infer.
10. **Decision doctrine** — every actionable rec carries an aggression
    tier (PROBE → EXCEPTIONAL, max loss hard-capped at 5% NLV at every
    tier), competing hypotheses, a crowding check (one-sided consensus →
    the opposite case written first), ≥2 structures compared, and closes
    with the 决策块 decision block. Conviction never exceeds evidence
    quality. Full text: `references/decision-doctrine.md`.

## Trader-policy defaults

These have sensible defaults but can be overridden in
`private/trader-profile.md`:

- **Macro hedge budget:** total annualized macro hedge cost ≤ **1.5%**
  of portfolio NLV.
- **Response language:** defaults to English; override to Chinese
  (with English technical terms) or any other style in the profile.
- **Tone:** concrete numbers, structures, verdicts; avoid hedging
  language ("you might consider", "可以考虑").

---

@private/trader-profile.md
