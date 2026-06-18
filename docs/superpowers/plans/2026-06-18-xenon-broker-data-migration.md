# Xenon Broker-Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route option-wizard's IB + Futu **state reads**, live **mid/liquidity**, and live **per-contract greeks/IV** through the one xenon read-only Query API, demoting the old fragmented paths (ib_insync direct, IB MCP, Futu CLI) to documented fallbacks — so every analysis can pull the most accurate *currently obtainable* value at any time.

**Architecture:** A new `XenonClient` (HTTP, `X-API-Key`, read-only) is the single entry point for broker state + market data. Pure normalization helpers map xenon JSON into the audit/scan shapes the existing scripts already consume. A `live_quote()` helper takes greeks/IV from the live broker quote (`/options/greeks` `modelGreeks`) with an ib_insync fallback — **never** a client-side BSM model. Consumers (`manage_positions`, `retrospective`) are rewired; execution stays on ib_insync.

**Tech Stack:** Python 3.13, `uv`, `httpx` (already a dep), `ib_insync` (fallback greeks only), `pytest` + `pytest-mock`. xenon FastAPI Query API v0.6.5.

## Global Constraints

Every task's requirements implicitly include this section. Exact values copied from the design doc (`docs/superpowers/specs/2026-06-18-xenon-broker-data-migration-design.md`) and verified live 2026-06-18.

- **Python runtime:** `uv` only — never bare `python`/`pip`. Tests run with `.venv/bin/pytest`. Python `>=3.13`.
- **Import path:** `tests/conftest.py` inserts `plugins/option-wizard/skills/option-wizard/` onto `sys.path`. All script code imports as `from scripts.X import Y` / `from scripts._clients.X import Y`. All new source files live under `plugins/option-wizard/skills/option-wizard/scripts/`; all new tests under `tests/`.
- **xenon endpoint:** base from env `XENON_BASE` (currently `http://100.66.147.98:8321`), key from env `XENON_KEY` (64-hex, read-only). Auth header is **`X-API-Key`** (NOT `Authorization: Bearer`). Both already in `.env` (gitignored) and `.env.example`.
- **Read-only:** the key reaches only the §2 allowlist; order routing/sync paths return 401. Execution stays on `ib_insync` (`scripts/ib_order.py`, `scripts/_clients/ib.py` — untouched).
- **No client-side BSM** for greeks/IV. Greeks/IV always come from a live broker quote (`/options/greeks` `modelGreeks` primary, `ib_insync.reqMktData` `modelGreeks` fallback). If both fail → honest greeks gap, never fabricated.
- **Source discipline (the invariant):** xenon = state + live mid/NBBO/L2 liquidity + live greeks/IV; UW = options-analytics aggregates (IV rank, RV, skew, IV term, GEX, max pain, dark pool, flow) + analytical-mode greeks; TV = spot/technicals/OHLCV; ib_insync = execution + fallback greeks.
- **Commit policy (user's global rule):** **never `git commit` without the user's explicit go-ahead.** Each task ends with a "Stage & propose commit" step — stage the files, show the proposed message, and PAUSE for approval. Never push to `main`; open a PR. No `Co-Authored-By` trailer.
- **No fabrication / freshness:** surface `last_sync` (IB) and `is_stale`/`fetched_at`/`data_as_of` (Futu); empty book / null greeks / null bid-ask are honest gaps, never substituted.

### Verified endpoint shapes (live captures, 2026-06-18, `:8321`)

These are the real shapes the fixtures below are built from. Do not invent fields.

**`GET /portfolio`** (IB) top-level: `account_summary`, `positions[]`, `last_sync`, `bankroll`, `position_count`, …
- `account_summary`: `{cash, settled_cash, net_liquidation, maintenance_margin, buying_power, available_funds, unrealized_pnl, …}`
- `positions[]` item: `{ticker, structure_type, direction("LONG"|"SHORT"), expiry, contracts, legs[]}`. **`expiry` is ISO `"2026-07-17"` for options, `"N/A"` for stock — and it lives on the POSITION, not the leg.**
- `legs[]` item: `{type("Put"|"Call"|"Stock"), conId, strike, avg_cost, contracts, direction("LONG"|"SHORT"), entry_cost, market_price, market_value, market_price_is_calculated}`. **No `right`, `symbol`, `expiry`, or signed `quantity` on the leg** — derive: symbol = position `ticker`; expiry = position `expiry`; right = `Put`→`P`/`Call`→`C`; signed qty = leg `contracts` × (`+1` LONG / `-1` SHORT). `avg_cost` is per-contract dollars (premium×100).

**`GET /futu/portfolio`** top-level: `{ok, fetched_at, data_as_of, is_stale, positions[], account_summary, account_raw, count, warnings}`
- `account_summary`: same keys as IB (`cash`, `settled_cash`, `net_liquidation`, `maintenance_margin`, …).
- `positions[]` item: `{futu_code, normalized, quantity(signed float, e.g. -1.0), avg_cost, market_price, position_side("LONG"|"SHORT"), currency, …}`
- `normalized`: `{kind("OPT"|"STK"), symbol, expiry("20270115" — already YYYYMMDD), strike, right("C"|"P"), exchange, …}`

**`GET /blotter`** top-level: `{configured, source, as_of, summary, closed_trades[], open_trades[]}`
- trade item: `{symbol, contract_desc, sec_type("OPT"|"STK"), is_closed, net_quantity, total_quantity, total_commission, realized_pnl, cost_basis, proceeds, total_cash_flow, executions[], perm_id}`. **No strike/expiry/right at trade level.**
- `executions[]` item: `{exec_id, time("2026-06-18T03:47:53+08:00" ISO+TZ), side("BUY"|"SELL"), quantity, price, commission, notional_value, net_cash_flow}`

**`GET /market-depth?symbol=…[&expiry&strike&right][&num_rows=1..20]`** → `{symbol, conId, secType, isSmartDepth, entitled, numRows, asOf, bids:[{price,size,marketMaker}], asks:[…], note?}`. Partial option tuple → 422. Empty book is a **200** (`note` = `"no depth returned"` / `"no L2 entitlement"` / `"depth line budget exhausted (309)"`). IB-cooldown **502** is transient → retry.

**`GET /options/greeks?symbol=…&expiry=YYYYMMDD&strike=…&right=C|P`** → `{symbol, conId, secType:"OPT", expiry, strike, right, asOf, bid, ask, greeks, note?}` where `greeks` = `{impliedVol, delta, gamma, vega, theta, undPrice}` or `null` (`note:"no greeks returned"`). Greeks populate around the clock (IB frozen mode); `bid`/`ask`/`undPrice` are `null` off-hours. Invalid `right` → 422. Server timeout 12s → client ~15s.

---

## Task 1: `XenonClient` — the HTTP client

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/_clients/xenon.py`
- Test: `tests/test_xenon_client.py`

**Interfaces:**
- Consumes: env `XENON_BASE`, `XENON_KEY`; `httpx`.
- Produces:
  - `XenonClient(base_url: str | None = None, api_key: str | None = None, timeout: float = 15.0)`
  - `.get(path: str, params: dict | None = None) -> Any` (public generic passthrough; retries 502 on `/market-depth`)
  - State: `.health() / .ib_portfolio() / .futu_portfolio() / .orders() / .blotter() / .journal(days=None, limit=None) / .trades_entry_dates() / .performance()` — each returns the parsed JSON (`dict`).
  - Market data: `.market_depth(symbol, expiry=None, strike=None, right=None, num_rows=10) -> dict`, `.option_greeks(symbol, expiry, strike, right) -> dict`, `.options_chain(symbol, expiry=None) -> dict`, `.options_expirations(symbol) -> dict`.
  - Raises `RuntimeError` on missing config; `httpx.HTTPStatusError` on non-200 (after 502-retry for market-depth).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_xenon_client.py`:

```python
from unittest.mock import MagicMock, patch

import httpx
import pytest
from scripts._clients.xenon import XenonClient


def _resp(status_code, payload):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = payload
    if status_code >= 400:
        r.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=MagicMock(), response=r
        )
    else:
        r.raise_for_status.return_value = None
    return r


def test_sets_api_key_header_and_base(monkeypatch):
    monkeypatch.setenv("XENON_BASE", "http://host:8321/")
    monkeypatch.setenv("XENON_KEY", "deadbeef")
    c = XenonClient()
    assert c._headers["X-API-Key"] == "deadbeef"
    assert c._base == "http://host:8321"  # trailing slash stripped


def test_missing_base_raises(monkeypatch):
    monkeypatch.delenv("XENON_BASE", raising=False)
    with pytest.raises(RuntimeError, match="XENON_BASE"):
        XenonClient(api_key="x")


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("XENON_KEY", raising=False)
    with pytest.raises(RuntimeError, match="XENON_KEY"):
        XenonClient(base_url="http://h:8321", api_key=None)


def test_ib_portfolio_hits_path_and_returns_json():
    with patch("scripts._clients.xenon.httpx.get") as g:
        g.return_value = _resp(200, {"positions": [], "account_summary": {}})
        c = XenonClient(base_url="http://h:8321", api_key="x")
        out = c.ib_portfolio()
        assert g.call_args[0][0] == "http://h:8321/portfolio"
        assert g.call_args.kwargs["headers"]["X-API-Key"] == "x"
        assert out == {"positions": [], "account_summary": {}}


def test_non_200_raises():
    with patch("scripts._clients.xenon.httpx.get") as g:
        g.return_value = _resp(401, {"detail": "Authentication required"})
        c = XenonClient(base_url="http://h:8321", api_key="x")
        with pytest.raises(httpx.HTTPStatusError):
            c.orders()


def test_market_depth_retries_on_502_then_succeeds():
    with patch("scripts._clients.xenon.httpx.get") as g, patch(
        "scripts._clients.xenon.time.sleep"
    ):
        g.side_effect = [
            _resp(502, {"detail": "IB Gateway connection recently failed."}),
            _resp(200, {"symbol": "AAPL", "bids": [], "asks": [], "entitled": True}),
        ]
        c = XenonClient(base_url="http://h:8321", api_key="x")
        out = c.market_depth("aapl", num_rows=5)
        assert g.call_count == 2
        assert out["entitled"] is True
        # symbol upper-cased, num_rows passed
        assert g.call_args.kwargs["params"]["symbol"] == "AAPL"
        assert g.call_args.kwargs["params"]["num_rows"] == 5


def test_option_greeks_passes_triplet_and_returns_null_greeks():
    with patch("scripts._clients.xenon.httpx.get") as g:
        g.return_value = _resp(
            200,
            {"symbol": "QQQ", "greeks": None, "bid": None, "ask": None,
             "note": "no greeks returned"},
        )
        c = XenonClient(base_url="http://h:8321", api_key="x")
        out = c.option_greeks("qqq", "20260717", 600, "c")
        p = g.call_args.kwargs["params"]
        assert p == {"symbol": "QQQ", "expiry": "20260717", "strike": 600, "right": "C"}
        assert out["greeks"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_xenon_client.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts._clients.xenon'`

- [ ] **Step 3: Write the client**

Create `plugins/option-wizard/skills/option-wizard/scripts/_clients/xenon.py`:

```python
"""Thin HTTP client for the xenon read-only Query API.

Single entry point for option-wizard's broker STATE reads (IB + Futu
account / positions / orders / blotter / journal / performance) plus the
live market-data reads (L2 depth, broker-computed option greeks). It does
NOT place orders — the key is read-only; execution stays on ib_insync.

Auth: X-API-Key header (read-only XENON_QUERY_API_KEY scope). Base URL and
key come from env XENON_BASE / XENON_KEY (both in .env, gitignored).

Verified live 2026-06-18 against http://100.66.147.98:8321. Consumer
reference (xenon repo): docs/reference/readonly-query-api.md. Design:
docs/superpowers/specs/2026-06-18-xenon-broker-data-migration-design.md.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx


class XenonClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        base = base_url if base_url is not None else os.environ.get("XENON_BASE")
        if not base:
            raise RuntimeError(
                "XENON_BASE is not set (env var or constructor argument)."
            )
        key = api_key if api_key is not None else os.environ.get("XENON_KEY")
        if not key:
            raise RuntimeError(
                "XENON_KEY is not set (env var or constructor argument)."
            )
        self._base = base.rstrip("/")
        self._headers = {"X-API-Key": key, "Accept": "application/json"}
        self._timeout = timeout

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        retry_502: bool = False,
        max_retries: int = 3,
    ) -> Any:
        """GET `path`. Raises on non-200. When `retry_502`, a 502 (IB
        cooldown on /market-depth) is retried with short backoff."""
        url = f"{self._base}{path}"
        for attempt in range(max_retries):
            resp = httpx.get(
                url, headers=self._headers, params=params, timeout=self._timeout
            )
            if retry_502 and resp.status_code == 502 and attempt < max_retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("unreachable: retry loop always returns or raises")

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Public generic passthrough (used by the scripts.xenon CLI)."""
        return self._get(path, params=params, retry_502=(path == "/market-depth"))

    # --- state reads ---

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def ib_portfolio(self) -> dict[str, Any]:
        return self._get("/portfolio")

    def futu_portfolio(self) -> dict[str, Any]:
        return self._get("/futu/portfolio")

    def orders(self) -> dict[str, Any]:
        return self._get("/orders")

    def blotter(self) -> dict[str, Any]:
        return self._get("/blotter")

    def journal(
        self, days: int | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if days is not None:
            params["days"] = days
        if limit is not None:
            params["limit"] = limit
        return self._get("/journal", params=params or None)

    def trades_entry_dates(self) -> dict[str, Any]:
        return self._get("/trades/entry-dates")

    def performance(self) -> dict[str, Any]:
        return self._get("/performance")

    # --- market data ---

    def market_depth(
        self,
        symbol: str,
        expiry: str | None = None,
        strike: float | None = None,
        right: str | None = None,
        num_rows: int = 10,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": symbol.upper(), "num_rows": num_rows}
        for k, v in (("expiry", expiry), ("strike", strike), ("right", right)):
            if v is not None:
                params[k] = v.upper() if k == "right" else v
        return self._get("/market-depth", params=params, retry_502=True)

    def option_greeks(
        self, symbol: str, expiry: str, strike: float, right: str
    ) -> dict[str, Any]:
        params = {
            "symbol": symbol.upper(),
            "expiry": expiry,
            "strike": strike,
            "right": right.upper(),
        }
        return self._get("/options/greeks", params=params)

    def options_chain(self, symbol: str, expiry: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": symbol.upper()}
        if expiry:
            params["expiry"] = expiry
        return self._get("/options/chain", params=params)

    def options_expirations(self, symbol: str) -> dict[str, Any]:
        return self._get("/options/expirations", params={"symbol": symbol.upper()})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_xenon_client.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Stage & propose commit** (do NOT commit without the user's go-ahead)

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/_clients/xenon.py tests/test_xenon_client.py
# Proposed message — wait for user approval before running `git commit`:
#   feat(xenon): read-only XenonClient (state + market-data) over Query API
```

---

## Task 2: Normalization helpers (xenon JSON → audit / scan shapes)

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/xenon_normalize.py`
- Test: `tests/test_xenon_normalize.py`

**Interfaces:**
- Consumes: `XenonClient.ib_portfolio()` / `.futu_portfolio()` dicts (shapes above). Pure functions — no network.
- Produces:
  - `to_audit_positions(ib_portfolio: dict) -> tuple[list[dict], float]` — list of `{"contract_description": str, "position": float}` (the shape `defined_risk_audit.audit_book` parses) + cash. Stock legs emit a bare-symbol description; option legs emit a synthesized OCC description.
  - `to_manage_legs(ib_portfolio: dict) -> list[dict]` — one dict per **option** leg: `{"symbol", "conId", "strike": float, "right": "P"|"C", "expiry": "YYYYMMDD", "qty": float(signed), "avg_cost": float, "market_price": float|None}`. Stock legs excluded.
  - `to_futu_audit_positions(futu_portfolio: dict) -> tuple[list[dict], float]` — same audit shape as `to_audit_positions`, from Futu `normalized`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_xenon_normalize.py`:

```python
from scripts.defined_risk_audit import audit_book
from scripts.xenon_normalize import (
    to_audit_positions,
    to_futu_audit_positions,
    to_manage_legs,
)

# Real-shape IB /portfolio fixture (representative values).
IB_PORTFOLIO = {
    "last_sync": "2026-06-18T10:30:19.387534",
    "account_summary": {"cash": 44316.81, "settled_cash": 44316.81,
                        "net_liquidation": 65876.66, "maintenance_margin": 3576.41},
    "positions": [
        {"ticker": "QQQ", "structure_type": "Short Put", "direction": "SHORT",
         "expiry": "2026-07-17", "contracts": 1,
         "legs": [{"type": "Put", "conId": 884159412, "strike": 692.0,
                   "avg_cost": 1277.9196, "contracts": 1, "direction": "SHORT",
                   "market_price": 10.74}]},
        {"ticker": "QQQ", "structure_type": "Stock", "direction": "LONG",
         "expiry": "N/A", "contracts": 18,
         "legs": [{"type": "Stock", "conId": 320227571, "strike": 0.0,
                   "avg_cost": 640.20, "contracts": 18, "direction": "LONG",
                   "market_price": 734.41}]},
        {"ticker": "SPX", "structure_type": "Long Put", "direction": "LONG",
         "expiry": "2026-07-17", "contracts": 1,
         "legs": [{"type": "Put", "conId": 873618680, "strike": 6855.0,
                   "avg_cost": 1441.64, "contracts": 1, "direction": "LONG",
                   "market_price": 15.7}]},
    ],
}

FUTU_PORTFOLIO = {
    "is_stale": False, "fetched_at": "2026-06-18T10:30:36.694Z",
    "account_summary": {"cash": 12000.0, "settled_cash": 12000.0},
    "positions": [
        {"futu_code": "US.TSLA270115C650000", "quantity": -1.0, "avg_cost": 50.0,
         "market_price": 60.0, "position_side": "SHORT",
         "normalized": {"kind": "OPT", "symbol": "TSLA", "right": "C",
                        "strike": 650.0, "expiry": "20270115"}},
        {"futu_code": "US.AAPL", "quantity": 100.0, "avg_cost": 150.0,
         "market_price": 210.0, "position_side": "LONG",
         "normalized": {"kind": "STK", "symbol": "AAPL", "right": None,
                        "strike": None, "expiry": None}},
    ],
}


def test_to_audit_positions_emits_parseable_descriptions_and_cash():
    rows, cash = to_audit_positions(IB_PORTFOLIO)
    assert cash == 44316.81
    # short put leg, signed negative
    qqq_put = next(r for r in rows if r["contract_description"].startswith("QQQ   2026"))
    assert qqq_put["position"] == -1.0
    # stock leg → bare symbol, positive qty
    assert {"contract_description": "QQQ", "position": 18.0} in rows


def test_to_audit_positions_round_trips_through_audit_book():
    rows, cash = to_audit_positions(IB_PORTFOLIO)
    # cash 44316 < QQQ 692 short put assignment (69_200) → flagged uncovered CSP
    findings = audit_book(rows, cash_balance=cash)
    qqq = next(f for f in findings if f["underlying"] == "QQQ")
    assert qqq["fails"] == "cash_secured_put"
    assert qqq["coverage_ratio"] < 1.0


def test_to_manage_legs_options_only_with_signed_qty_and_yyyymmdd():
    legs = to_manage_legs(IB_PORTFOLIO)
    syms = [(l["symbol"], l["right"], l["expiry"], l["qty"]) for l in legs]
    assert ("QQQ", "P", "20260717", -1.0) in syms
    assert ("SPX", "P", "20260717", 1.0) in syms
    # stock excluded
    assert all(l["right"] in ("P", "C") for l in legs)
    qqq = next(l for l in legs if l["symbol"] == "QQQ")
    assert qqq["conId"] == 884159412
    assert qqq["strike"] == 692.0
    assert qqq["market_price"] == 10.74


def test_to_futu_audit_positions():
    rows, cash = to_futu_audit_positions(FUTU_PORTFOLIO)
    assert cash == 12000.0
    tsla = next(r for r in rows if "TSLA" in r["contract_description"])
    assert tsla["position"] == -1.0
    assert "270115C00650000" in tsla["contract_description"]
    assert {"contract_description": "AAPL", "position": 100.0} in rows
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_xenon_normalize.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.xenon_normalize'`

- [ ] **Step 3: Write the normalization module**

Create `plugins/option-wizard/skills/option-wizard/scripts/xenon_normalize.py`:

```python
"""Pure functions mapping xenon Query-API JSON into option-wizard's
internal shapes. No network, no I/O.

IB /portfolio leg encoding (verified 2026-06-18):
  - leg.type ∈ {"Put","Call","Stock"}; map Put→P, Call→C.
  - leg carries conId, strike, avg_cost (per-contract $), market_price,
    contracts, direction.
  - symbol + expiry live on the POSITION (ticker; expiry ISO "YYYY-MM-DD"
    or "N/A" for stock), NOT the leg.
  - signed qty = leg.contracts × (+1 LONG / -1 SHORT).
Futu /futu/portfolio (verified):
  - positions[].normalized.{symbol,kind,right,strike,expiry(YYYYMMDD)},
    signed `quantity`.

The synthesized `contract_description` matches the regexes in
defined_risk_audit (_OPTION_RE + _OCC_RE) so audit_book is reused
unchanged.

KNOWN LIMITATION: IB expiry is position-level, so a multi-expiry structure
(diagonal / calendar) collapses every leg to the position expiry. The
current book is all single-expiry; revisit if calendars are added.
"""

from __future__ import annotations

from typing import Any

_LEG_TYPE_TO_RIGHT = {"Put": "P", "Call": "C"}


def _to_yyyymmdd(s: str | None) -> str | None:
    """'2026-07-17'→'20260717'; '20260717'→'20260717'; 'N/A'/None/''→None."""
    if not s or s == "N/A":
        return None
    digits = s.replace("-", "")
    return digits if len(digits) == 8 and digits.isdigit() else None


def _occ_description(
    symbol: str, expiry_yyyymmdd: str, strike: float, right: str
) -> str:
    """IB-MCP-style description that defined_risk_audit parses, e.g.
    'QQQ   20260717 692 P [QQQ  260717P00692000 100]'."""
    strike_str = f"{strike:g}"
    occ_expiry = expiry_yyyymmdd[2:]  # YYMMDD
    occ_strike = f"{int(round(strike * 1000)):08d}"
    return (
        f"{symbol}   {expiry_yyyymmdd} {strike_str} {right} "
        f"[{symbol}  {occ_expiry}{right}{occ_strike} 100]"
    )


def _signed(qty_magnitude: Any, direction: Any) -> float:
    return float(qty_magnitude or 0.0) * (
        -1.0 if str(direction).upper() == "SHORT" else 1.0
    )


def to_audit_positions(ib_portfolio: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
    out: list[dict[str, Any]] = []
    for p in ib_portfolio.get("positions") or []:
        symbol = str(p.get("ticker", "")).strip()
        expiry = _to_yyyymmdd(p.get("expiry"))
        for leg in p.get("legs") or []:
            qty = _signed(leg.get("contracts"), leg.get("direction", p.get("direction")))
            if leg.get("type") == "Stock":
                out.append({"contract_description": symbol, "position": qty})
                continue
            right = _LEG_TYPE_TO_RIGHT.get(leg.get("type"))
            if right is None or expiry is None:
                continue
            desc = _occ_description(symbol, expiry, float(leg.get("strike", 0.0)), right)
            out.append({"contract_description": desc, "position": qty})
    acct = ib_portfolio.get("account_summary") or {}
    cash = float(acct.get("cash", acct.get("settled_cash", 0.0)) or 0.0)
    return out, cash


def to_manage_legs(ib_portfolio: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in ib_portfolio.get("positions") or []:
        symbol = str(p.get("ticker", "")).strip()
        expiry = _to_yyyymmdd(p.get("expiry"))
        for leg in p.get("legs") or []:
            right = _LEG_TYPE_TO_RIGHT.get(leg.get("type"))
            if right is None or expiry is None:
                continue  # skip stock + malformed
            out.append(
                {
                    "symbol": symbol,
                    "conId": leg.get("conId"),
                    "strike": float(leg.get("strike", 0.0)),
                    "right": right,
                    "expiry": expiry,
                    "qty": _signed(
                        leg.get("contracts"), leg.get("direction", p.get("direction"))
                    ),
                    "avg_cost": float(leg.get("avg_cost", 0.0) or 0.0),
                    "market_price": leg.get("market_price"),
                }
            )
    return out


def to_futu_audit_positions(
    futu_portfolio: dict[str, Any],
) -> tuple[list[dict[str, Any]], float]:
    out: list[dict[str, Any]] = []
    for p in futu_portfolio.get("positions") or []:
        nm = p.get("normalized") or {}
        symbol = str(nm.get("symbol", "")).strip()
        qty = float(p.get("quantity", 0.0) or 0.0)
        kind = str(nm.get("kind", "")).upper()
        if kind == "STK":
            out.append({"contract_description": symbol, "position": qty})
            continue
        if kind == "OPT":
            right = str(nm.get("right", "")).upper()
            expiry = _to_yyyymmdd(nm.get("expiry"))
            if right not in ("P", "C") or expiry is None:
                continue
            desc = _occ_description(symbol, expiry, float(nm.get("strike", 0.0)), right)
            out.append({"contract_description": desc, "position": qty})
    acct = futu_portfolio.get("account_summary") or {}
    cash = float(acct.get("cash", acct.get("settled_cash", 0.0)) or 0.0)
    return out, cash
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_xenon_normalize.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Stage & propose commit** (await user go-ahead)

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/xenon_normalize.py tests/test_xenon_normalize.py
#   feat(xenon): normalize IB/Futu portfolio JSON → audit + manage-leg shapes
```

---

## Task 3: `live_quote()` — live mid + greeks/IV (xenon primary, ib_insync fallback, no BSM)

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/live_quote.py`
- Test: `tests/test_live_quote.py`

**Interfaces:**
- Consumes: a `XenonClient`-shaped object exposing `.option_greeks(symbol, expiry, strike, right)`; optionally an `IBClient`-shaped object (`scripts._clients.ib.IBClient`) for fallback; `httpx` exceptions.
- Produces: `live_quote(symbol, expiry, strike, right, *, client, ib=None, fallback_market_price=None) -> dict` with keys `{mid, mid_source, bid, ask, iv, delta, gamma, theta, vega, greeks_source}`. Any field may be `None` (honest gap, never fabricated). `mid_source` ∈ `{"xenon","ib","held_leg",None}`; `greeks_source` ∈ `{"xenon","ib",None}`.
- Internal: `_ib_modelgreeks(ib, symbol, expiry, strike, right) -> dict | None` (reqMktData fallback).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_live_quote.py`:

```python
from unittest.mock import MagicMock

import httpx
from scripts import live_quote as lq
from scripts.live_quote import live_quote


def _client(greeks_payload):
    c = MagicMock()
    c.option_greeks.return_value = greeks_payload
    return c


def test_greeks_and_mid_from_xenon():
    c = _client({"bid": 10.5, "ask": 10.9,
                 "greeks": {"impliedVol": 0.41, "delta": -0.30, "gamma": 0.01,
                            "vega": 0.2, "theta": -0.15, "undPrice": 722.0}})
    q = live_quote("QQQ", "20260717", 692, "P", client=c)
    assert q["greeks_source"] == "xenon"
    assert q["iv"] == 0.41 and q["delta"] == -0.30
    assert q["mid"] == 10.7 and q["mid_source"] == "xenon"


def test_greeks_present_but_bidask_null_uses_held_leg_mid():
    c = _client({"bid": None, "ask": None,
                 "greeks": {"impliedVol": 0.41, "delta": -0.30, "gamma": 0.01,
                            "vega": 0.2, "theta": -0.15, "undPrice": 722.0}})
    q = live_quote("QQQ", "20260717", 692, "P", client=c, fallback_market_price=10.74)
    assert q["greeks_source"] == "xenon"
    assert q["mid"] == 10.74 and q["mid_source"] == "held_leg"


def test_null_greeks_no_ib_is_honest_gap_no_fabrication():
    c = _client({"bid": None, "ask": None, "greeks": None,
                 "note": "no greeks returned"})
    q = live_quote("QQQ", "20260717", 692, "P", client=c)
    assert q["greeks_source"] is None
    assert q["delta"] is None and q["iv"] is None
    assert q["mid"] is None and q["mid_source"] is None  # no fabrication


def test_null_greeks_falls_back_to_ib(monkeypatch):
    c = _client({"bid": None, "ask": None, "greeks": None})
    monkeypatch.setattr(
        lq, "_ib_modelgreeks",
        lambda ib, *a: {"iv": 0.42, "delta": -0.28, "gamma": 0.01, "theta": -0.14,
                        "vega": 0.2, "bid": 10.4, "ask": 10.8},
    )
    q = live_quote("QQQ", "20260717", 692, "P", client=c, ib=MagicMock())
    assert q["greeks_source"] == "ib"
    assert q["delta"] == -0.28
    assert q["mid"] == 10.6 and q["mid_source"] == "ib"


def test_xenon_http_error_falls_back_to_ib(monkeypatch):
    c = MagicMock()
    c.option_greeks.side_effect = httpx.HTTPStatusError(
        "502", request=MagicMock(), response=MagicMock()
    )
    monkeypatch.setattr(
        lq, "_ib_modelgreeks",
        lambda ib, *a: {"iv": 0.42, "delta": -0.28, "gamma": 0.01, "theta": -0.14,
                        "vega": 0.2, "bid": None, "ask": None},
    )
    q = live_quote("QQQ", "20260717", 692, "P", client=c, ib=MagicMock(),
                   fallback_market_price=10.74)
    assert q["greeks_source"] == "ib"
    assert q["mid"] == 10.74 and q["mid_source"] == "held_leg"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_live_quote.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.live_quote'`

- [ ] **Step 3: Write the helper**

Create `plugins/option-wizard/skills/option-wizard/scripts/live_quote.py`:

```python
"""Live option mid + broker-computed greeks/IV.

xenon /options/greeks is PRIMARY (IB modelGreeks — real market data, not a
model). ib_insync reqMktData modelGreeks is the FALLBACK. There is NO
client-side BSM — if both sources fail, the greek is an honest gap (None).

Ladder (design §3.1, §5.3):
  1. xenon /options/greeks → bid/ask + greeks{impliedVol,delta,gamma,vega,theta}.
     Greeks populate around the clock (IB frozen mode); bid/ask null off-hours.
  2. greeks null OR xenon error → ib_insync reqMktData modelGreeks (if `ib` given).
  3. mid: (bid+ask)/2 when both > 0; else held-leg market_price; else None.
"""

from __future__ import annotations

import math
from typing import Any

import httpx


def _mid_from(bid: Any, ask: Any) -> float | None:
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        return (bid + ask) / 2
    return None


def live_quote(
    symbol: str,
    expiry: str,
    strike: float,
    right: str,
    *,
    client: Any,
    ib: Any = None,
    fallback_market_price: float | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "mid": None, "mid_source": None, "bid": None, "ask": None,
        "iv": None, "delta": None, "gamma": None, "theta": None, "vega": None,
        "greeks_source": None,
    }
    greeks = None
    try:
        q = client.option_greeks(symbol, expiry, strike, right)
        out["bid"], out["ask"] = q.get("bid"), q.get("ask")
        greeks = q.get("greeks")
        if greeks:
            out.update(
                {
                    "iv": greeks.get("impliedVol"),
                    "delta": greeks.get("delta"),
                    "gamma": greeks.get("gamma"),
                    "theta": greeks.get("theta"),
                    "vega": greeks.get("vega"),
                    "greeks_source": "xenon",
                }
            )
    except httpx.HTTPError:
        greeks = None

    if greeks is None and ib is not None:
        fb = _ib_modelgreeks(ib, symbol, expiry, strike, right)
        if fb is not None:
            out.update(
                {k: fb.get(k) for k in ("iv", "delta", "gamma", "theta", "vega")}
            )
            out["greeks_source"] = "ib"
            if out["bid"] is None:
                out["bid"] = fb.get("bid")
            if out["ask"] is None:
                out["ask"] = fb.get("ask")

    mid = _mid_from(out["bid"], out["ask"])
    if mid is not None:
        out["mid"] = mid
        out["mid_source"] = out["greeks_source"] or "xenon"
    elif fallback_market_price is not None:
        out["mid"] = float(fallback_market_price)
        out["mid_source"] = "held_leg"
    return out


def _ib_modelgreeks(
    ib: Any, symbol: str, expiry: str, strike: float, right: str
) -> dict[str, Any] | None:
    """ib_insync reqMktData modelGreeks fallback. Reconstructs the Option
    from the triplet. Returns greek dict + bid/ask, or None if IB yields
    nothing. Subscription is cancelled in finally."""
    from ib_insync import Option

    contract = Option(symbol, expiry, float(strike), right.upper(), "SMART")
    t = None
    try:
        ib._ib.qualifyContracts(contract)
        t = ib._ib.reqMktData(contract, genericTickList="", snapshot=False)
        ib._ib.sleep(3)
    except Exception:
        return None
    try:
        mg = t.modelGreeks if t is not None else None

        def _num(x: Any) -> float | None:
            return x if x is not None and not math.isnan(x) else None

        res = {
            "iv": _num(getattr(mg, "impliedVol", None)) if mg else None,
            "delta": _num(getattr(mg, "delta", None)) if mg else None,
            "gamma": _num(getattr(mg, "gamma", None)) if mg else None,
            "theta": _num(getattr(mg, "theta", None)) if mg else None,
            "vega": _num(getattr(mg, "vega", None)) if mg else None,
            "bid": t.bid if (t and t.bid and t.bid > 0) else None,
            "ask": t.ask if (t and t.ask and t.ask > 0) else None,
        }
        if all(res[k] is None for k in ("iv", "delta", "gamma", "theta", "vega")):
            return None
        return res
    finally:
        if t is not None:
            try:
                ib._ib.cancelMktData(t.contract)
            except Exception:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_live_quote.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Stage & propose commit** (await user go-ahead)

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/live_quote.py tests/test_live_quote.py
#   feat(xenon): live_quote — xenon modelGreeks primary, ib_insync fallback, no BSM
```

---

## Task 4: Rewire `manage_positions` onto xenon (state + audit + greeks)

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/manage_positions.py`
- Test: `tests/test_manage_positions.py`

**Interfaces:**
- Consumes: `XenonClient` (Task 1), `to_audit_positions`/`to_manage_legs` (Task 2), `live_quote` (Task 3), existing `audit_book`/`format_audit_findings` (`defined_risk_audit`), `evaluate_short_premium`/`SHORT_PREMIUM_STRUCTURES` (`evaluate_position`).
- Produces (changed signatures): `_position_key(leg: dict) -> str`, `_infer_structure(leg: dict) -> str`, `scan_positions(legs: list[dict], market: dict, today: str) -> list[dict]`, `_fetch_market_data(legs: list[dict], client, ib=None) -> dict`. `format_scan_report` unchanged.
- Default behavior is **xenon-only** for greeks (no IB connection): the daily scan no longer opens IB Gateway. `--ib-fallback` (opt-in) opens an `IBClient` so `live_quote` can fall back to `reqMktData` when xenon greeks are null. `_ib_positions_to_audit_format` is kept but marked fallback-only (no longer called by `main()`).

- [ ] **Step 1: Update the failing tests**

Replace the body of `tests/test_manage_positions.py` with:

```python
from scripts.manage_positions import format_scan_report, scan_positions

FAKE_LEGS = [
    {"symbol": "ORCL", "strike": 235, "right": "P", "expiry": "20260725",
     "qty": -5, "avg_cost": 420.0, "conId": 1, "market_price": 2.0},
    {"symbol": "NVDA", "strike": 800, "right": "C", "expiry": "20260725",
     "qty": -1, "avg_cost": 1200.0, "conId": 2, "market_price": 28.0},
]


def test_scan_returns_one_row_per_leg():
    market = {
        "ORCL 235 P 20260725": {"current_price": 2.00, "delta": -0.18, "dte": 52,
                                "source": "xenon"},
        "NVDA 800 C 20260725": {"current_price": 28.00, "delta": -0.65, "dte": 52,
                                "source": "xenon"},
    }
    rows = scan_positions(legs=FAKE_LEGS, market=market, today="2026-06-03")
    assert len(rows) == 2
    assert {r["symbol"] for r in rows} == {"ORCL", "NVDA"}


def test_format_scan_report_prioritizes_REVIEW_rows():
    rows = [
        {"symbol": "AAA", "action": "HOLD", "dte": 50, "rationale": "fine"},
        {"symbol": "BBB", "action": "REVIEW", "dte": 19, "rationale": "21 DTE window"},
        {"symbol": "CCC", "action": "CLOSE", "dte": 40, "rationale": "take-profit"},
    ]
    report = format_scan_report(rows)
    assert report.index("BBB") < report.index("CCC")
    assert report.index("BBB") < report.index("AAA")


def test_report_includes_no_action_line_when_empty():
    report = format_scan_report([])
    assert "no" in report.lower() or "0 positions" in report.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_manage_positions.py -q`
Expected: FAIL — `scan_positions` still expects ib_insync position objects / `_position_key` does `pos.contract` (AttributeError on dict).

- [ ] **Step 3: Rewrite the consumer functions**

In `scripts/manage_positions.py`:

(a) Replace the `tv` import line and `audit_book` import block at the top:

```python
from scripts._clients.xenon import XenonClient
from scripts.defined_risk_audit import audit_book, format_audit_findings
from scripts.evaluate_position import (
    SHORT_PREMIUM_STRUCTURES,
    evaluate_short_premium,
)
from scripts.live_quote import live_quote
from scripts.xenon_normalize import to_audit_positions, to_manage_legs
```

(Remove `from scripts._clients import tv as tv_client` — TV stays for spot/technicals elsewhere, but the option-mid fallback here is now the held-leg `market_price`.)

(b) Replace `_position_key`, `_infer_structure`, `scan_positions`, and `_fetch_market_data` with leg-dict versions:

```python
def _position_key(leg: dict[str, Any]) -> str:
    # Preserve fractional strikes (weekly $252.50 etc.) — :g avoids truncation.
    strike_str = f"{leg['strike']:g}"
    return f"{leg['symbol']} {strike_str} {leg['right']} {leg['expiry']}"


def _infer_structure(leg: dict[str, Any]) -> str:
    qty = leg["qty"]
    right = leg["right"].upper()
    if qty < 0 and right == "P":
        return "cash_secured_put"
    if qty < 0 and right == "C":
        return "covered_call"
    return "unknown"


def scan_positions(
    legs: list[dict[str, Any]], market: dict[str, dict], today: str
) -> list[dict]:
    rows = []
    for leg in legs:
        key = _position_key(leg)
        m = market.get(key, {})
        structure = _infer_structure(leg)
        symbol = leg["symbol"]
        if structure not in SHORT_PREMIUM_STRUCTURES:
            rows.append(
                {
                    "symbol": symbol,
                    "key": key,
                    "action": "HOLD",
                    "dte": m.get("dte", -1),
                    "rationale": "non-short-premium position; manual review",
                }
            )
            continue
        try:
            evaluation = evaluate_short_premium(
                opening_credit=abs(float(leg["avg_cost"])) / 100,
                current_price=m.get("current_price"),
                dte=m.get("dte", 0),
                delta=m.get("delta"),
                structure=structure,
            )
            rationale = evaluation["rationale"]
            source = m.get("source")
            if source and m.get("current_price") is not None:
                rationale = f"{rationale} [{source}]"
            rows.append(
                {
                    "symbol": symbol,
                    "key": key,
                    "action": evaluation["recommended_action"],
                    "dte": evaluation["dte"],
                    "rationale": rationale,
                }
            )
        except Exception as e:
            rows.append(
                {
                    "symbol": symbol,
                    "key": key,
                    "action": "REVIEW",
                    "dte": m.get("dte", -1),
                    "rationale": f"evaluation error: {e}",
                }
            )
    return rows


def _fetch_market_data(
    legs: list[dict[str, Any]], client: Any, ib: Any = None
) -> dict[str, dict]:
    """Price each option leg via live_quote (xenon /options/greeks primary,
    ib_insync reqMktData fallback only when `ib` is supplied). Mid falls back
    to the held leg's market_price, then to a gap — never fabricated."""
    market: dict[str, dict] = {}
    today = datetime.utcnow().date()
    for leg in legs:
        try:
            expiry = datetime.strptime(leg["expiry"], "%Y%m%d").date()
            dte = (expiry - today).days
        except Exception:
            dte = 0
        q = live_quote(
            leg["symbol"], leg["expiry"], leg["strike"], leg["right"],
            client=client, ib=ib, fallback_market_price=leg.get("market_price"),
        )
        market[_position_key(leg)] = {
            "current_price": q["mid"],
            "delta": q["delta"],
            "dte": dte,
            "source": q["mid_source"],
        }
    return market
```

(c) Add a docstring note to `_ib_positions_to_audit_format` (keep the function, it is now fallback-only):

```python
def _ib_positions_to_audit_format(
    positions: list, account_summary: dict
) -> tuple[list[dict], float]:
    """FALLBACK ONLY (ib_insync direct path). main() now sources the book
    from xenon via scripts.xenon_normalize.to_audit_positions. Retained for
    the documented offline/ib_insync fallback ladder; not called in the
    happy path.
    ...
    """
```

(d) Rewrite `main()`'s args + body (keep the lock/`--no-email`/`--audit-only`/`--force` behavior):

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="skip email delivery")
    parser.add_argument(
        "--audit-only", action="store_true",
        help="run the defined-risk audit and exit; skip per-position routine review",
    )
    parser.add_argument(
        "--ib-fallback", action="store_true",
        help="open ib_insync as a greeks fallback when xenon returns null greeks "
        "(default: xenon-only — the daily scan no longer needs IB Gateway)",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="IB Gateway port for --ib-fallback (overrides IB_PORT env; default 4001)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="ignore lockfile (override if you know another run is stuck)",
    )
    args = parser.parse_args(argv)

    if not args.force and not _acquire_lock():
        print("manage_positions: another run is in progress (lockfile fresh); skipping")
        return 0

    rows: list[dict] = []
    try:
        client = XenonClient()
        ib_portfolio = client.ib_portfolio()
        audit_positions, cash = to_audit_positions(ib_portfolio)
        audit_findings = audit_book(audit_positions, cash_balance=cash)
        audit_section = format_audit_findings(audit_findings)

        if args.audit_only:
            print(audit_section or "Defined-risk audit: no failures (clean book).")
            return 0

        legs = to_manage_legs(ib_portfolio)
        ib_ctx = None
        ib = None
        if args.ib_fallback:
            from scripts._clients.ib import IBClient

            ib_kwargs = {"port": args.port} if args.port is not None else {}
            ib_ctx = IBClient(**ib_kwargs)
            ib_ctx.connect()
            ib = ib_ctx
        try:
            market = _fetch_market_data(legs, client, ib=ib)
        finally:
            if ib_ctx is not None:
                ib_ctx.disconnect()

        rows = scan_positions(legs, market, today=str(datetime.utcnow().date()))
        scan_section = format_scan_report(rows)
        report = (
            (audit_section + "\n" + scan_section) if audit_section else scan_section
        )
        print(report)

        if not args.no_email:
            from scripts.email_sender import send_daily_scan

            send_daily_scan(report, rows)
    finally:
        _release_lock()

    return 0
```

Remove the now-unused `import math` only if nothing else uses it (the TV-fallback block that used `math.isnan` is gone). Verify with `grep -n "math\." scripts/manage_positions.py` before removing the import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_manage_positions.py tests/test_defined_risk_audit.py -q`
Expected: PASS (manage_positions: 3 passed; defined_risk_audit: 5 passed — audit_book untouched).

- [ ] **Step 5: Stage & propose commit** (await user go-ahead)

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/manage_positions.py tests/test_manage_positions.py
#   refactor(manage_positions): source book+account+greeks from xenon (ib_insync fallback opt-in)
```

---

## Task 5: Rewire `retrospective` (复盘) trade flow onto xenon `/blotter`

**Files:**
- Modify: `plugins/option-wizard/skills/option-wizard/scripts/retrospective.py`
- Test: `tests/test_retrospective.py` (append one test; existing tests untouched)

**Interfaces:**
- Consumes: existing `Trade` dataclass, `_iso_to_date`, `date`, `Literal` (all already imported in `retrospective.py`). A xenon `/blotter` dict (shape above).
- Produces: `parse_xenon_blotter(blotter: dict, window_start: date, window_end: date) -> list[Trade]`. Supersedes `parse_ib_trades` (IB MCP) + `parse_futu_trades` (Futu CLI) for the Layer-B trade-flow pull; both retained as documented fallbacks. Per-fill `Trade`s; `option_meta=None` (blotter carries no strike/expiry/right — same limitation as `parse_ib_trades`); trade-level `realized_pnl` attached to the last execution of each closed trade.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_retrospective.py`:

```python
from datetime import date

from scripts.retrospective import parse_xenon_blotter

_BLOTTER = {
    "configured": True,
    "source": "postgres",
    "as_of": "2026-06-17T19:47:53+00:00",
    "summary": {"realized_pnl": -479.14},
    "open_trades": [],
    "closed_trades": [
        {
            "symbol": "GLD", "contract_desc": "Stock", "sec_type": "OPT",
            "is_closed": True, "net_quantity": 0, "realized_pnl": -479.14,
            "perm_id": None,
            "executions": [
                {"exec_id": "a.1", "time": "2026-06-12T03:40:00+08:00",
                 "side": "SELL", "quantity": 1, "price": 28.00, "commission": 1.0},
                {"exec_id": "a.2", "time": "2026-06-16T03:47:53+08:00",
                 "side": "BUY", "quantity": 1, "price": 22.69, "commission": 1.0},
            ],
        }
    ],
}


def test_parse_xenon_blotter_emits_per_fill_trades_with_realized_on_last():
    trades = parse_xenon_blotter(_BLOTTER, date(2026, 6, 1), date(2026, 6, 30))
    assert len(trades) == 2
    assert all(t.ticker == "GLD" and t.contract_type == "OPT" for t in trades)
    assert all(t.option_meta is None for t in trades)
    opener, closer = trades
    assert opener.side == "SELL" and opener.fill_price == 28.00
    assert opener.realized_pnl is None  # only the last (closing) fill carries it
    assert closer.side == "BUY" and closer.fill_price == 22.69
    assert closer.realized_pnl == -479.14


def test_parse_xenon_blotter_filters_to_window():
    trades = parse_xenon_blotter(_BLOTTER, date(2026, 6, 14), date(2026, 6, 30))
    # only the 6/16 fill is in-window
    assert len(trades) == 1 and trades[0].fill_price == 22.69
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_retrospective.py -k xenon_blotter -q`
Expected: FAIL — `ImportError: cannot import name 'parse_xenon_blotter'`

- [ ] **Step 3: Add `parse_xenon_blotter` and demote the old parsers**

In `scripts/retrospective.py`, immediately after `parse_futu_trades`, add:

```python
def parse_xenon_blotter(
    blotter: dict[str, Any],
    window_start: date,
    window_end: date,
) -> list[Trade]:
    """Convert a xenon ``GET /blotter`` response → Trade[] (IB + Futu fills
    from Postgres). PRIMARY trade-flow source for Layer B (hard rule #9);
    parse_ib_trades (IB MCP) and parse_futu_trades (Futu CLI) are retained
    as documented fallbacks.

    Walks ``closed_trades[].executions[]`` + ``open_trades[].executions[]``;
    each execution → one Trade, filtered to [window_start, window_end]
    inclusive. The blotter carries no option strike/expiry/right at the
    execution level, so ``option_meta`` is None (same limitation as
    parse_ib_trades; the caller pre-enriches if needed). The trade-level
    ``realized_pnl`` is attached to the LAST in-window execution of each
    closed trade (mirrors parse_futu_trades attaching realizedPnl to the
    close leg) so it is not double-counted across fills.
    """
    out: list[Trade] = []
    groups = (blotter.get("closed_trades") or []) + (blotter.get("open_trades") or [])
    for tr in groups:
        sec = str(tr.get("sec_type", "STK")).upper()
        ctype: Literal["STK", "OPT"] = "OPT" if sec == "OPT" else "STK"
        ticker = str(tr.get("symbol", "")).upper()
        realized = tr.get("realized_pnl")
        realized_f = float(realized) if realized is not None else None
        is_closed = bool(tr.get("is_closed"))
        execs = tr.get("executions") or []
        last_idx = len(execs) - 1
        for i, ex in enumerate(execs):
            d = _iso_to_date(str(ex.get("time", "")))
            if d is None or not (window_start <= d <= window_end):
                continue
            attach_pnl = realized_f if (is_closed and i == last_idx) else None
            out.append(
                Trade(
                    ticker=ticker,
                    trade_date=d,
                    side="BUY" if str(ex.get("side", "")).upper() == "BUY" else "SELL",
                    quantity=int(abs(ex.get("quantity", 0))),
                    fill_price=float(ex.get("price", 0.0)),
                    contract_type=ctype,
                    option_meta=None,
                    realized_pnl=attach_pnl,
                )
            )
    return out
```

Then add a one-line fallback note to the docstrings of `parse_ib_trades` and `parse_futu_trades` (first line after the summary): `"FALLBACK: prefer parse_xenon_blotter (xenon /blotter) — this path is the IB-MCP / Futu-CLI fallback."`

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_retrospective.py -q`
Expected: PASS (existing tests + 2 new `xenon_blotter` tests).

- [ ] **Step 5: Stage & propose commit** (await user go-ahead)

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/retrospective.py tests/test_retrospective.py
#   feat(retrospective): parse_xenon_blotter — Layer-B trade flow from xenon /blotter
```

---

## Task 6: Agent CLI (`python -m scripts.xenon`) + docs/policy rewrite

**Files:**
- Create: `plugins/option-wizard/skills/option-wizard/scripts/xenon.py`
- Test: `tests/test_xenon_cli.py`
- Modify (docs — all reference docs live under `plugins/option-wizard/skills/option-wizard/`):
  - `plugins/option-wizard/skills/option-wizard/references/data-sources.md`
  - `plugins/option-wizard/skills/option-wizard/SKILL.md`
  - `plugins/option-wizard/skills/option-wizard/references/review-framework.md`
  - `plugins/option-wizard/skills/option-wizard/references/workflows-overview.md`
  - `CLAUDE.md` (the option-wizard **project** CLAUDE.md at repo root — has the "Data source order (universal)" section)
  - `private/trader-profile.md` (repo root; **gitignored**)
  - **Out of scope:** the workspace-coordinator `~/projects/CLAUDE.md` — its "Data source priority" is a generic cross-project default (IB → UW → FMP → Yahoo), not the option-wizard xenon migration. Leave it unless the user asks.

**Interfaces:**
- Consumes: `XenonClient.get(path, params)` (Task 1).
- Produces: `scripts/xenon.py` with `main(argv=None) -> int`; invoked `python -m scripts.xenon <path> [-p K=V ...]`, prints JSON to stdout. (Module `scripts.xenon` — distinct from the client module `scripts._clients.xenon`.)

- [ ] **Step 1: Write the failing CLI test**

Create `tests/test_xenon_cli.py`:

```python
from unittest.mock import MagicMock, patch

import pytest
from scripts.xenon import main


def test_cli_calls_get_with_path_and_params(capsys):
    fake = MagicMock()
    fake.get.return_value = {"symbol": "AAPL", "bids": []}
    with patch("scripts.xenon.XenonClient", return_value=fake):
        rc = main(["/market-depth", "-p", "symbol=AAPL", "-p", "num_rows=5"])
    assert rc == 0
    fake.get.assert_called_once_with("/market-depth", {"symbol": "AAPL", "num_rows": "5"})
    out = capsys.readouterr().out
    assert '"symbol": "AAPL"' in out


def test_cli_no_params(capsys):
    fake = MagicMock()
    fake.get.return_value = {"positions": []}
    with patch("scripts.xenon.XenonClient", return_value=fake):
        rc = main(["/portfolio"])
    assert rc == 0
    fake.get.assert_called_once_with("/portfolio", None)


def test_cli_bad_param_errors():
    with patch("scripts.xenon.XenonClient"):
        with pytest.raises(SystemExit):
            main(["/portfolio", "-p", "noequalssign"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_xenon_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.xenon'`

- [ ] **Step 3: Write the CLI**

Create `plugins/option-wizard/skills/option-wizard/scripts/xenon.py`:

```python
"""Thin CLI over the xenon read-only Query API for ad-hoc agent use.

    python -m scripts.xenon /portfolio
    python -m scripts.xenon /market-depth -p symbol=AAPL -p num_rows=5
    python -m scripts.xenon /options/greeks -p symbol=QQQ -p expiry=20260717 \\
        -p strike=600 -p right=C

Prints the JSON response to stdout. Read-only — see scripts/_clients/xenon.py.
Equivalent raw curl: curl -H "X-API-Key: $XENON_KEY" "$XENON_BASE/portfolio".
"""

from __future__ import annotations

import argparse
import json
import sys

from scripts._clients.xenon import XenonClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="xenon read-only Query API CLI")
    parser.add_argument("path", help="API path, e.g. /portfolio or /market-depth")
    parser.add_argument(
        "-p", "--param", action="append", default=[], metavar="K=V",
        help="query param (repeatable), e.g. -p symbol=AAPL",
    )
    args = parser.parse_args(argv)

    params: dict[str, str] = {}
    for kv in args.param:
        if "=" not in kv:
            parser.error(f"bad --param {kv!r}; expected K=V")
        k, v = kv.split("=", 1)
        params[k] = v

    client = XenonClient()
    data = client.get(args.path, params or None)
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_xenon_cli.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Rewrite the data-source policy docs**

Apply the **same canonical wording** across all seven docs. The two authoritative blocks below are the source of truth; the other files reference the same routing.

**(5a) `…/references/data-sources.md` — replace the "Source split" table** so the account row points to xenon and two live-market-data rows are added:

```markdown
| Domain | Source | Forbidden alternative |
|---|---|---|
| Spot, OHLCV, daily/intraday candles, volume bars | **TV** via `finance-data-providers:tradingview-reader` | UW `get_company_info`, chain `price_data` (for "live spot"), `get_ticker_candles_by_range` |
| SMA/EMA/RSI/MACD/BBANDS/ATR | **TV** | UW `get_extended_technical_indicator`, `get_ticker_indicator_series` — banned for L3 (multi-week stale) |
| IV rank, RV, 25Δ skew, IV term structure | **UW** | TV (does not serve these) |
| Max pain, GEX-by-strike, greeks-by-strike, interpolated IV (analytical mode) | **UW** | — (UW exclusive) |
| Flow alerts, flow per expiry, dark pool prints | **UW** | — (UW exclusive) |
| Account state (positions, balances, margin, orders, fills) — IB **and** Futu | **xenon** Query API (`/portfolio`, `/futu/portfolio`, `/orders`, `/blotter`, `/journal`, `/performance`) | IB MCP read tools / Futu `portfolio-analyser` CLI = **documented fallback only** |
| Live mid / NBBO / L2 liquidity | **xenon** `/market-depth` | — |
| Live per-contract greeks / IV (live-trade mode) | **xenon** `/options/greeks` (IB `modelGreeks`) → **ib_insync `reqMktData`** fallback | **client-side BSM — forbidden**; UW analytical greeks are a cross-check, not the live source |
```

**(5b) `…/references/data-sources.md` — replace the "Freshness gate" section** with the live-first / exhaust-before-gap discipline (design §3.1):

```markdown
## Freshness gate + live-first acquisition (SKILL.md hard rule #7)

Every quoted number must be the **most accurate currently-obtainable** value,
pulled **live at the moment of analysis** — not a prior-session close, a
converted prior-day technical, or an extrapolation. The xenon Query API
(`XENON_BASE`, key `XENON_KEY`, header `X-API-Key`) makes live data
acquirable at any time: account/positions/orders/blotter/journal/performance,
`/market-depth` (live NBBO + L2), and `/options/greeks` (live greeks/IV — IB
frozen mode returns them around the clock).

**Per-data-point acquisition ladder** — try in order; declare a gap only after
every rung fails or returns empty:

| Data point | Ladder |
|---|---|
| Spot | TV live → xenon `/market-depth` underlying mid → UW chain `price_data` |
| Option IV / per-strike greeks | xenon `/options/greeks` → UW `interpolated_iv`/`greeks_by_strike` → ib_insync `reqMktData` |
| 25Δ skew / IV term | live `/options/greeks` strike+expiry sweep → UW `historical-risk-reversal-skew`/`iv_term_structure` |
| IV rank / RV | UW (exclusive — no rebuild) |
| GEX by strike/expiry/ticker | UW by-strike-expiry → by-strike → by-ticker (exclusive) |
| Max pain / dark pool / flow | UW (exclusive) |
| Technicals (RSI/SMA/EMA/MACD/ATR/BBANDS) | TV live **today** — never a converted prior-day value |
| VIX / VIX9D / VXN | TV exchange codes (`CBOE:VIX`, `CBOE:VIX9D`, `CBOE:VXN`/`NASDAQ:VXN`) → UW → derive front-end IV from `/options/greeks` on SPX/QQQ near-term |
| Account / positions / orders / fills | xenon `/portfolio` `/futu/portfolio` `/orders` `/blotter` → IB MCP / Futu CLI fallback |

**Exhaust-before-gap + self-check.** Before writing any "STALE / 未重拉 / gap"
caveat, self-check: *Did I actually call the live endpoint? Did I try
alternative symbols / exchange codes / endpoint variants / other sources,
including the xenon live surface?* A caveat is permitted only after a
**documented** attempt across the ladder, and must state **what was tried**
(e.g. "UW GEX-by-strike-expiry empty for SPX 6/19; tried by-strike and
by-ticker, both empty — genuine UW gap"), never a bare "未重拉".

- **Avoidable gap** (live source existed and was reachable but not pulled —
  stale chains, converted RSI, wrong VIX exchange code): **not acceptable.**
- **Genuine gap** (no source serves that slice): flag honestly, characterize
  by what was tried; the remedy is to acquire live, never to extrapolate or
  convert a stale number into a "today" value (no fabrication).

Surface freshness explicitly: xenon IB `last_sync`; Futu `is_stale` /
`fetched_at` / `data_as_of`; UW `price_data.date` / chain `last_price.date`.
```

**(5c) `SKILL.md` hard rule #2** — update the IB Gateway bullet and the `reqMktData` line:
- Change the account-state source from "IB Gateway / IB MCP" to: **"xenon Query API (`/portfolio`, `/futu/portfolio`, `/orders`, `/blotter`, `/journal`, `/performance`) — IB **and** Futu in one read-only surface; IB MCP read tools / Futu CLI = documented fallback."**
- Add: **"Live mid / L2 liquidity → xenon `/market-depth`. Live per-contract greeks/IV → xenon `/options/greeks` (IB `modelGreeks`), ib_insync `reqMktData` fallback. No client-side BSM."**
- The existing line "IB via `ib_insync.reqMktData` returns a `Ticker` with `modelGreeks`…" → reframe as the **fallback** path, with xenon `/options/greeks` as primary.

**(5d) `SKILL.md` hard rule #7** — replace the freshness-gate text with a one-paragraph version of (5b): freshness gate is now **live-first + exhaust-before-gap**; reference the per-data-point ladder in `references/data-sources.md`; "avoidable" stale caveats are not acceptable, "genuine" gaps stay honest and state what was tried.

**(5e) `SKILL.md` hard rule #9 (Layer B) + the two "When to read which file" rows (book review, weekly review)** — change the Layer-B / book-review trade-flow + position source from "IB MCP `get_account_trades` + Futu via `portfolio-analyser` CLI" to **"xenon `/blotter` (fills, both brokers) + `/portfolio` + `/futu/portfolio` (positions); IB MCP / Futu CLI = documented fallback."** Keep "both brokers required."

**(5f) `CLAUDE.md` (option-wizard project root)** — update the "Data source order (universal)" section: insert xenon as item **3 → primary for account state + live mid/liquidity + live greeks**; demote IB MCP read tools + Futu CLI to documented fallback; keep UW (#1 analytics) and TV (#2 spot/technicals). Add the one-line invariant + the `python -m scripts.xenon <path>` / `curl -H "X-API-Key: $XENON_KEY" "$XENON_BASE<path>"` entry point. (Do **not** touch the workspace-coordinator `~/projects/CLAUDE.md` — out of scope per the Files block.)

**(5g) `…/references/review-framework.md`** — in the Layer-B section, make the Futu/IB pull go through xenon `/blotter` + `/futu/portfolio` (programmatic) as primary; keep the `portfolio-analyser --rerun` CLI note as the documented fallback (and keep the existing staleness-gate logic, which now also applies to xenon `is_stale`).

**(5h) `…/references/workflows-overview.md`** — update any data-acquisition step that names IB MCP / Futu CLI / `reqMktData` for state or greeks to name the xenon endpoints first, fallback second; reference `references/data-sources.md` for the ladder.

**(5i) `private/trader-profile.md`** — update the "Brokers" + "Position-review scope" blocks: pull IB **and** Futu via xenon (`/portfolio`, `/futu/portfolio`, `/blotter`); keep the `portfolio-analyser` `--rerun` command as the documented fallback. Keep the bilingual / M7-buy-and-hold / macro-budget content unchanged.

- [ ] **Step 6: Verify no stale routing remains + run the whole suite**

Run (sanity grep — every hit should now be in a "fallback" context, not "primary"):
```bash
cd /Users/chenxi/projects/option-wizard
grep -rn "portfolio-analyser\|IB MCP\|reqMktData\|get_account_trades\|get_account_positions" \
  plugins/option-wizard/skills/option-wizard/SKILL.md \
  plugins/option-wizard/skills/option-wizard/references/ \
  CLAUDE.md private/trader-profile.md
```
Then: `.venv/bin/pytest -q`
Expected: full suite PASS.

- [ ] **Step 7: Stage & propose commit** (await user go-ahead)

```bash
git add plugins/option-wizard/skills/option-wizard/scripts/xenon.py tests/test_xenon_cli.py \
  plugins/option-wizard/skills/option-wizard/references/data-sources.md \
  plugins/option-wizard/skills/option-wizard/SKILL.md \
  plugins/option-wizard/skills/option-wizard/references/review-framework.md \
  plugins/option-wizard/skills/option-wizard/references/workflows-overview.md \
  CLAUDE.md
#   feat(xenon): agent CLI + repoint data-source policy to xenon (live-first §3.1)
```
(Note: `private/` is gitignored — `private/trader-profile.md` won't stage; edit it locally and skip from the commit. Confirm with `git status` before staging.)

---

## Task 7: Integration smoke test (network-gated)

**Files:**
- Create: `tests/integration/test_xenon_smoke.py`

**Interfaces:**
- Consumes: live xenon server via `XenonClient` (env `XENON_BASE` + `XENON_KEY`). Skips when `XENON_KEY` is unset (mirrors `test_uw_smoke.py`).
- Produces: structural assertions only (no value assertions — they change), printing observed shapes.

- [ ] **Step 1: Write the smoke test**

Create `tests/integration/test_xenon_smoke.py`:

```python
"""Live xenon Query-API smoke test. Requires XENON_KEY (+ XENON_BASE) env.
Pytest skips if XENON_KEY is missing. Asserts structure, not values.

    XENON_KEY=... XENON_BASE=http://100.66.147.98:8321 \\
      .venv/bin/pytest tests/integration/test_xenon_smoke.py -v -s
"""

import os

import pytest
from scripts._clients.xenon import XenonClient

pytestmark = pytest.mark.skipif(
    "XENON_KEY" not in os.environ,
    reason="XENON_KEY not set; skip live xenon smoke test",
)


@pytest.fixture(scope="module")
def client():
    return XenonClient()


def test_health(client):
    h = client.health()
    assert h.get("status") == "ok"
    print("health ib_gateway:", h.get("ib_gateway", {}).get("service_state"))


def test_ib_portfolio_shape(client):
    p = client.ib_portfolio()
    assert "account_summary" in p and "positions" in p
    assert "cash" in p["account_summary"]
    print("portfolio positions:", p.get("position_count"), "last_sync:", p.get("last_sync"))


def test_futu_portfolio_shape(client):
    f = client.futu_portfolio()
    assert "positions" in f and "account_summary" in f
    print("futu is_stale:", f.get("is_stale"), "count:", f.get("count"))


def test_blotter_shape(client):
    b = client.blotter()
    assert "closed_trades" in b and "open_trades" in b
    print("blotter source:", b.get("source"), "as_of:", b.get("as_of"))


def test_market_depth_empty_book_is_200(client):
    d = client.market_depth("AAPL", num_rows=5)
    assert "entitled" in d and "bids" in d and "asks" in d
    print("AAPL depth entitled:", d.get("entitled"), "note:", d.get("note"))


def test_option_greeks_live(client):
    # QQQ 600C 20260717 — deep ITM, greeks populate around the clock (frozen mode).
    g = client.option_greeks("QQQ", "20260717", 600, "C")
    assert g.get("secType") == "OPT"
    assert "greeks" in g  # may be a dict or None (note "no greeks returned")
    print("QQQ 600C greeks:", g.get("greeks"), "bid/ask:", g.get("bid"), g.get("ask"))
```

- [ ] **Step 2: Run the smoke test live (manual, network-gated)**

Run (loads `.env`):
```bash
cd /Users/chenxi/projects/option-wizard
set -a && . ./.env && set +a && .venv/bin/pytest tests/integration/test_xenon_smoke.py -v -s
```
Expected: 6 passed (server reachable). Confirm `test_option_greeks_live` prints a populated `greeks` dict.

- [ ] **Step 3: Confirm the default suite still skips it**

Run: `.venv/bin/pytest -q`
Expected: full suite PASS; the smoke test is collected but **skipped** unless `XENON_KEY` is in the env (it is, via shell — so run the default suite in a shell without sourcing `.env`, or accept it runs). Document both modes in the test docstring (done).

- [ ] **Step 4: Stage & propose commit** (await user go-ahead)

```bash
git add tests/integration/test_xenon_smoke.py
#   test(xenon): live integration smoke (health/portfolio/futu/blotter/depth/greeks)
```

---

## Self-Review

**1. Spec coverage** (design doc § → task):
- §2 verified API surface → Task 1 (`XenonClient` covers all 7 state + market-depth + greeks + enumerators). ✓
- §2.1 `/market-depth` (502-retry, empty-book 200) → Task 1 (`market_depth`, 502-retry test) + Task 7 (empty-book smoke). ✓
- §2.2 `/options/greeks` (triplet, greeks-vs-mid independence, null greeks) → Task 1 (`option_greeks`) + Task 3 (`live_quote`). ✓
- §3 invariant → Global Constraints + Task 6 (5a–5i docs). ✓
- §3.1 live-first / exhaust-before-gap / ladder → Task 6 (5b SKILL #7 + data-sources.md). ✓
- §4 decisions 1–8 → scope (Task 1–7), fallback (Task 4 `--ib-fallback`, Task 5 demotion), mid+liquidity (Task 1/3), position source (Task 4), agent CLI (Task 6), greeks source (Task 3), §3.1 (Task 6). ✓
- §5.1 `XenonClient` → Task 1. §5.2 normalization → Task 2. §5.3 `live_quote` → Task 3. §5.4 consumer rewires (manage_positions, defined_risk_audit untouched, retrospective, ib_order untouched) → Tasks 4–5. §5.5/5.6 CLI + docs → Task 6. ✓
- §6 data flow / §7 error handling → Task 1 (502/401), Task 3 (null greeks/mid gap), Task 4 (held-leg mid). ✓
- §8 out of scope (no BSM, no execution, no `/historical/bars`, enumerators deprioritized) → respected; enumerators wired but unused (Task 1). ✓
- §9 testing (unit normalization, unit client, integration smoke) → Tasks 1/2/3 unit + Task 7 integration. ✓

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to" — every code step is complete; doc steps give exact replacement blocks (5a/5b) + located instructions (5c–5i). ✓

**3. Type consistency:** `to_manage_legs` emits `{symbol, conId, strike, right, expiry, qty, avg_cost, market_price}`; `_position_key`/`_infer_structure`/`_fetch_market_data` (Task 4) read exactly those keys. `live_quote` returns `{mid, mid_source, bid, ask, iv, delta, gamma, theta, vega, greeks_source}`; `_fetch_market_data` reads `mid`/`delta`/`mid_source`. `XenonClient.option_greeks` return is consumed by `live_quote` as `{bid, ask, greeks:{impliedVol,delta,gamma,vega,theta,undPrice}}`. `parse_xenon_blotter` builds `Trade(ticker, trade_date, side, quantity, fill_price, contract_type, option_meta, realized_pnl)` — matches the dataclass. ✓

**4. Known limitation flagged:** IB position-level expiry collapses multi-expiry structures (diagonals/calendars) — noted in `xenon_normalize.py` docstring; current book is single-expiry. ✓
