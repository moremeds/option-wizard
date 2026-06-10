"""Thin HTTP client for FRED (Federal Reserve Economic Data) public API.

Auth: api_key query param. Env var FRED_API_KEY.

Used for macro-hedge regime signals — primarily HY OAS (BAMLH0A0HYM2),
the ICE BofA US High Yield Index Option-Adjusted Spread. The IWM
put-spread gate fires when HY OAS is "rising" (current > prior 30d
80th percentile), which is the empirically-validated tell for
fast-deleveraging regimes (COVID-1, JPY unwind) where small-cap hedges
beat broad-index hedges.

Single endpoint pattern: GET observations.

Series of interest:
- BAMLH0A0HYM2 — HY OAS (primary signal)
- BAMLC0A0CMOAS — IG OAS (corroborating signal, optional)
- DGS10        — 10Y Treasury yield (rate-cut speed proxy)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


class FREDClient:
    def __init__(self, api_key: str | None = None, timeout: float = 10.0) -> None:
        key = api_key if api_key is not None else os.environ.get("FRED_API_KEY")
        if not key:
            raise RuntimeError(
                "FRED_API_KEY is not set (env var or constructor argument)."
            )
        self._api_key = key
        self._timeout = timeout

    def _get(self, params: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
        """GET with exponential backoff on 429 / 5xx."""
        params = {**params, "api_key": self._api_key, "file_type": "json"}
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = httpx.get(BASE_URL, params=params, timeout=self._timeout)
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    last_exc = httpx.HTTPStatusError(
                        f"FRED returned {resp.status_code}",
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

    def observations(
        self,
        series_id: str,
        observation_start: str | None = None,
        observation_end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch raw observations. Returns list of {date, value} dicts.

        FRED returns `value` as string with "." for missing — caller
        filters those. Dates are ISO YYYY-MM-DD.
        """
        params: dict[str, Any] = {"series_id": series_id}
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end
        resp = self._get(params)
        return resp.get("observations", [])


def hy_oas_signal(
    client: FREDClient | None = None,
    *,
    lookback_days: int = 60,
    today: str | None = None,
) -> dict[str, Any]:
    """Compute the IWM-gate HY OAS signal.

    Returns dict with:
      - hy_oas               : current level in PERCENT (e.g., 2.75 = 275 bps).
                                FRED publishes BAMLH0A0HYM2 in percent.
                                Multiply by 100 to get bps.
      - hy_oas_date          : date of the current observation (FRED is T-1)
      - hy_oas_30d_mean      : mean of last 30 trading days (percent)
      - hy_oas_30d_pct       : current level's percentile vs last 30 days
                                (0-100; 80+ = "elevated")
      - hy_oas_trend         : "rising" | "flat" | "falling"
                                rising: 30d_pct >= 80 AND last_7d > last_30d_mean
                                falling: 30d_pct <= 20 AND last_7d < last_30d_mean
                                flat: otherwise
      - history              : list[(date, value)] for the lookback window
                                (for downstream charting / audit)

    Historical reference: HY OAS "normal" range is ~3-5% (300-500 bps).
    Crisis levels: COVID-1 March 2020 hit 11% (1100 bps). 2024 JPY
    unwind: peaked at ~3.5% (350 bps). The IWM-putspread gate is sensitive
    to TREND, not absolute level — a move from 2.7 → 3.2% over 7 days is
    a "rising" signal even though 3.2% is still historically calm.

    For the IWM put-spread gate in macro_hedge.py, the trigger condition
    is `hy_oas_trend == "rising"` (plus VVIX > 130 from a separate
    source). Note FRED HY OAS is published with ~1 trading day lag, so
    the "current" level is T-1, not T-0. Acceptable for weekly Monday
    regime scans.

    `today` is a string YYYY-MM-DD; defaults to actual today. Used by
    tests to inject a fixed date.
    """
    client = client or FREDClient()
    if today is None:
        today = datetime.now(timezone.utc).date().isoformat()
    start = (
        (datetime.fromisoformat(today) - timedelta(days=lookback_days))
        .date()
        .isoformat()
    )

    obs = client.observations(
        "BAMLH0A0HYM2", observation_start=start, observation_end=today
    )
    # Filter out missing values (FRED uses ".")
    valid = [
        (o["date"], float(o["value"])) for o in obs if o.get("value") not in (None, ".")
    ]
    if not valid:
        raise RuntimeError(f"No valid HY OAS observations between {start} and {today}")

    current_date, current_value = valid[-1]
    last_30 = [v for _, v in valid[-30:]]
    last_7 = [v for _, v in valid[-7:]]

    mean_30 = sum(last_30) / len(last_30)
    mean_7 = sum(last_7) / len(last_7)

    # Midrank percentile of current value vs last 30 (Pass-2 C-MED2).
    # Using strict `v <= current` rank biases percentile to 100 in flat or
    # clustered markets (every equal-value tie counts as "<=", so flat 3.0
    # yields rank=30, pct=100 even though current is at the median). The
    # trend logic above happens to mask this in tests (mean_7 > mean_30 is
    # false in flat data), but `hy_oas_30d_pct` is also exposed directly to
    # downstream orchestrators via add_fred_signals_to_snapshot, where the
    # raw percentile DOES matter. Midrank gives ties a half-weight so flat
    # data → percentile 50, clustered data → centered percentile.
    below = sum(1 for v in last_30 if v < current_value)
    equal = sum(1 for v in last_30 if v == current_value)
    pct = ((below + 0.5 * equal) / len(last_30)) * 100.0

    if pct >= 80 and mean_7 > mean_30:
        trend = "rising"
    elif pct <= 20 and mean_7 < mean_30:
        trend = "falling"
    else:
        trend = "flat"

    return {
        "hy_oas": current_value,
        "hy_oas_date": current_date,
        "hy_oas_30d_mean": round(mean_30, 2),
        "hy_oas_30d_pct": round(pct, 1),
        "hy_oas_trend": trend,
        "history": valid,
    }


def add_fred_signals_to_snapshot(
    snapshot: dict, client: FREDClient | None = None, *, today: str | None = None
) -> dict:
    """Augment a macro_hedge snapshot with FRED-sourced regime signals.

    Reads `snapshot["regime_check"]` (creating if absent) and adds the
    HY OAS fields. Returns the snapshot (mutated in place AND returned
    for chainability).

    The macro_hedge IWM-putspread gate currently checks `vvix > 130`
    only. The framework doc + Pitfall 03 recommend ALSO requiring
    `hy_oas_trend == "rising"` — this function makes that signal
    available so the orchestrator can compose the gate.
    """
    signal = hy_oas_signal(client, today=today)
    regime = snapshot.setdefault("regime_check", {})
    regime["hy_oas"] = signal["hy_oas"]
    regime["hy_oas_30d_pct"] = signal["hy_oas_30d_pct"]
    regime["hy_oas_trend"] = signal["hy_oas_trend"]
    regime["hy_oas_date"] = signal["hy_oas_date"]
    return snapshot
