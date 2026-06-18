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
