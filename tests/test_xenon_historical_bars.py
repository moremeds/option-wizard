"""historical_bars/daily_closes — fixture frozen from live xenon probe.

Frozen from live POST /historical/bars probe against XENON_BASE, QQQ,
duration="1 W", bar_size="1 day", use_rth=True, as-of 2026-07-10.
"""

from datetime import date
from unittest.mock import MagicMock, patch

from scripts._clients.xenon import XenonClient

# Frozen from live xenon POST /historical/bars probe, QQQ, 2026-07-10:
BARS_FIXTURE = {
    "bars": [
        {
            "date": "2026-07-09",
            "open": 718.33,
            "high": 724.23,
            "low": 715.12,
            "close": 723.28,
            "volume": 21293827,
        },
        {
            "date": "2026-07-10",
            "open": 720.7,
            "high": 726.39,
            "low": 717.0,
            "close": 725.51,
            "volume": 18128520,
        },
    ]
}


def _resp(payload):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def test_historical_bars_posts_documented_body():
    with patch("scripts._clients.xenon.httpx.post") as p:
        p.return_value = _resp(BARS_FIXTURE)
        c = XenonClient(base_url="http://h:8321", api_key="x")
        c.historical_bars("QQQ", duration="1 W")
        assert p.call_args[0][0] == "http://h:8321/historical/bars"
        body = p.call_args.kwargs["json"]
        assert body["contract"] == {
            "sec_type": "STK",
            "symbol": "QQQ",
            "exchange": "SMART",
            "currency": "USD",
        }
        assert body["bar_size"] == "1 day"
        assert body["use_rth"] is True


def test_daily_closes_parses_to_date_float_map():
    with patch("scripts._clients.xenon.httpx.post") as p:
        p.return_value = _resp(BARS_FIXTURE)
        c = XenonClient(base_url="http://h:8321", api_key="x")
        closes = c.daily_closes("QQQ", duration="1 W")
        assert closes[date(2026, 7, 10)] == 725.51
        assert all(isinstance(k, date) for k in closes)


def test_historical_bars_routes_spx_index_to_cboe():
    with patch("scripts._clients.xenon.httpx.post") as p:
        p.return_value = _resp(BARS_FIXTURE)
        c = XenonClient(base_url="http://h:8321", api_key="x")
        c.historical_bars("SPX", sec_type="IND")
        body = p.call_args.kwargs["json"]
        assert body["contract"]["exchange"] == "CBOE"


def test_historical_bars_routes_ndx_index_to_nasdaq():
    with patch("scripts._clients.xenon.httpx.post") as p:
        p.return_value = _resp(BARS_FIXTURE)
        c = XenonClient(base_url="http://h:8321", api_key="x")
        c.historical_bars("NDX", sec_type="IND")
        body = p.call_args.kwargs["json"]
        assert body["contract"]["exchange"] == "NASDAQ"


def test_historical_bars_equity_default_stays_smart():
    with patch("scripts._clients.xenon.httpx.post") as p:
        p.return_value = _resp(BARS_FIXTURE)
        c = XenonClient(base_url="http://h:8321", api_key="x")
        c.historical_bars("QQQ")
        body = p.call_args.kwargs["json"]
        assert body["contract"]["exchange"] == "SMART"
