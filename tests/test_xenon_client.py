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
    with (
        patch("scripts._clients.xenon.httpx.get") as g,
        patch("scripts._clients.xenon.time.sleep"),
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
            {
                "symbol": "QQQ",
                "greeks": None,
                "bid": None,
                "ask": None,
                "note": "no greeks returned",
            },
        )
        c = XenonClient(base_url="http://h:8321", api_key="x")
        out = c.option_greeks("qqq", "20260717", 600, "c")
        p = g.call_args.kwargs["params"]
        assert p == {"symbol": "QQQ", "expiry": "20260717", "strike": 600, "right": "C"}
        assert out["greeks"] is None
