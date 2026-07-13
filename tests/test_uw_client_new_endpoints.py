"""New UW endpoints — paths verified against UW OpenAPI docs 2026-07-13:
GET /api/market/market-tide, GET /api/stock/{t}/greek-exposure/strike-expiry."""

from unittest.mock import MagicMock, patch

from scripts._clients.uw import UWClient


def _resp(payload):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def test_market_tide_path_and_params():
    with patch("scripts._clients.uw.httpx.get") as g:
        g.return_value = _resp({"data": [{"timestamp": "2026-07-10T09:30:00-04:00"}]})
        c = UWClient(api_key="k")
        out = c.market_tide(date="2026-07-10")
        assert (
            g.call_args[0][0] == "https://api.unusualwhales.com/api/market/market-tide"
        )
        assert g.call_args.kwargs["params"] == {
            "date": "2026-07-10",
            "interval_5m": "true",
        }
        assert out["data"][0]["timestamp"].startswith("2026-07-10")


def test_market_tide_no_date_omits_param():
    with patch("scripts._clients.uw.httpx.get") as g:
        g.return_value = _resp({"data": []})
        UWClient(api_key="k").market_tide()
        assert g.call_args.kwargs["params"] == {"interval_5m": "true"}


def test_gex_by_strike_expiry_path():
    with patch("scripts._clients.uw.httpx.get") as g:
        g.return_value = _resp({"data": [{"strike": "7500", "expiry": "2026-07-17"}]})
        c = UWClient(api_key="k")
        out = c.gex_by_strike_expiry("SPX")
        assert (
            g.call_args[0][0]
            == "https://api.unusualwhales.com/api/stock/SPX/greek-exposure/strike-expiry"
        )
        assert out["data"][0]["expiry"] == "2026-07-17"
