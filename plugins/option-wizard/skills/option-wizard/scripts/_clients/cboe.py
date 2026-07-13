"""Thin HTTP client for CBOE's public daily index-price feed.

CBOE's `daily_prices` CSV is the authoritative public source for daily
closes on its listed indices — the same source livewire's
`fetch_cboe_volatility` treats as authoritative. RUT, SPX, and VIX are all
covered. No auth, no env var. Verified live 2026-07-13 (HTTP 200):
`https://cdn.cboe.com/api/global/us_indices/daily_prices/{symbol}_History.csv`

Response body is CSV: header line `DATE,{symbol}` then rows
`MM/DD/YYYY,close` (e.g. `07/10/2026,2977.805200`). Dates are `MM/DD/YYYY`.

Used as a fallback in `grade_calls.build_spot_history` for indices xenon has
no IB exchange route for (currently just RUT) — see `CBOE_FALLBACK_INDICES`
there. This client stays a thin HTTP wrapper; the fallback composition
lives in grade_calls, not here.
"""

from __future__ import annotations

import time
from datetime import date, datetime

import httpx

BASE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices"


class CBOEClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    def daily_closes(self, symbol: str = "RUT") -> dict[date, float]:
        """Fetch and parse the daily-close CSV for `symbol`.

        Skips the header, blank lines, and any malformed row (wrong field
        count or non-float price) rather than raising on a single bad row.
        """
        text = self._get(symbol)
        closes: dict[date, float] = {}
        for line in text.splitlines()[1:]:  # skip header
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) != 2:
                continue
            d_str, price_str = parts
            try:
                d = datetime.strptime(d_str, "%m/%d/%Y").date()
                price = float(price_str)
            except ValueError:
                continue
            closes[d] = price
        return closes

    def _get(self, symbol: str, max_retries: int = 3) -> str:
        """GET with exponential backoff on 5xx and request errors.

        Retries up to max_retries times with delays 1s, 2s, 4s.
        Non-retryable errors (4xx other than what's covered above) raise
        immediately.
        """
        url = f"{BASE_URL}/{symbol}_History.csv"
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = httpx.get(url, timeout=self._timeout)
                if 500 <= resp.status_code < 600:
                    last_exc = httpx.HTTPStatusError(
                        f"CBOE returned {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                    time.sleep(2**attempt)
                    continue
                resp.raise_for_status()
                return resp.text
            except httpx.RequestError as e:
                last_exc = e
                time.sleep(2**attempt)
        assert last_exc is not None
        raise last_exc
