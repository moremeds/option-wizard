"""Thin HTTP client for the Unusual Whales public API.

Auth: Bearer token in env var UW_API_KEY. Client ID header per UW docs.
Wraps only the endpoints option-wizard actually uses; expand as needed.

Observed JSON top-level shapes (2026-06-03 against ORCL):
- iv_rank                    -> {"data": ...}
- realized_volatility        -> {"data": ...}
- historical_risk_reversal_skew -> {"data": ...}
- iv_term_structure          -> {"data": ...}
- max_pain                   -> {"data": ..., "date": "YYYY-MM-DD"}
- spot_gex_by_strike         -> {"data": ...}
- interpolated_iv            -> {"data": ...}
- greeks_by_strike           -> {"data": ...}
- dark_pool                  -> {"data": ...}
- technical_indicator/<fn>   -> {"data": ...}
- market_tide                -> {"data": [...]}; row keys (2026-07-13 live,
  no ticker): timestamp, date, net_call_premium, net_put_premium, net_volume
- gex_by_strike_expiry       -> {"data": [...]}; row keys (2026-07-13 live
  against QQQ): date, expiry, strike, call_gex, put_gex, call_delta,
  put_delta, call_charm, put_charm, call_vanna, put_vanna, dte. call_gex/
  put_gex are separate fields (no combined `gex`) — Task 4's
  gex_levels.compute_levels_per_expiry adapter should sum/net them itself.
  NOTE: strike, call_gex, put_gex come back as decimal STRINGS (e.g.
  "355", "0.0000") — cast with float() before any arithmetic.

Every consumer should unwrap `resp["data"]` before parsing. Re-run
tests/integration/test_uw_smoke.py to refresh this list.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

BASE_URL = "https://api.unusualwhales.com"


class UWClient:
    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        key = api_key if api_key is not None else os.environ.get("UW_API_KEY")
        if not key:
            raise RuntimeError(
                "UW_API_KEY is not set (env var or constructor argument)."
            )
        self._headers = {
            "Authorization": f"Bearer {key}",
            "UW-CLIENT-API-ID": "100001",
            "Accept": "application/json",
        }
        self._timeout = timeout

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """GET with exponential backoff on 429 and 5xx.

        Retries up to max_retries times with delays 1s, 2s, 4s.
        Non-retryable errors (4xx other than 429) raise immediately.
        """
        url = f"{BASE_URL}{path}"
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = httpx.get(
                    url, headers=self._headers, params=params, timeout=self._timeout
                )
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    last_exc = httpx.HTTPStatusError(
                        f"UW returned {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                    import time as _time

                    _time.sleep(2**attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.RequestError as e:
                last_exc = e
                import time as _time

                _time.sleep(2**attempt)
        assert last_exc is not None
        raise last_exc

    # --- endpoints (one method per UW endpoint we consume) ---

    def iv_rank(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/iv-rank")

    def realized_volatility(self, ticker: str) -> dict[str, Any]:
        # Path verified live 2026-06-03 via scripts/smoke/uw_smoke.py
        return self._get(f"/api/stock/{ticker}/volatility/realized")

    def historical_risk_reversal_skew(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/historical-risk-reversal-skew")

    def iv_term_structure(self, ticker: str) -> dict[str, Any]:
        # Path verified live 2026-06-03 via scripts/smoke/uw_smoke.py
        return self._get(f"/api/stock/{ticker}/volatility/term-structure")

    def max_pain(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/max-pain")

    def spot_gex_by_strike(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/spot-exposures/strike")

    def interpolated_iv(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/interpolated-iv")

    def greeks_by_strike(
        self, ticker: str, expiry: str | None = None
    ) -> dict[str, Any]:
        params = {"expiry": expiry} if expiry else None
        return self._get(f"/api/stock/{ticker}/greeks", params=params)

    def dark_pool(self, ticker: str) -> dict[str, Any]:
        return self._get(f"/api/darkpool/{ticker}")

    def market_tide(
        self, date: str | None = None, interval_5m: bool = True
    ) -> dict[str, Any]:
        # Path verified against UW OpenAPI docs 2026-07-13 (get_public_api_docs).
        params: dict[str, Any] = {"interval_5m": "true" if interval_5m else "false"}
        if date:
            params["date"] = date
        return self._get("/api/market/market-tide", params=params)

    def gex_by_strike_expiry(
        self, ticker: str, date: str | None = None
    ) -> dict[str, Any]:
        # Per-expiry GEX — the all-expiry aggregate (spot_gex_by_strike) produces
        # far-OTM wall artifacts; per-expiry is the trade-relevant read.
        # Path verified against UW OpenAPI docs 2026-07-13.
        params = {"date": date} if date else None
        return self._get(
            f"/api/stock/{ticker}/greek-exposure/strike-expiry", params=params
        )

    def technical_indicator(self, ticker: str, function: str) -> dict[str, Any]:
        return self._get(f"/api/stock/{ticker}/technical-indicator/{function}")
