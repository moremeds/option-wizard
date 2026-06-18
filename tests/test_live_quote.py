from unittest.mock import MagicMock

import httpx
import pytest
from scripts.live_quote import live_quote

from scripts import live_quote as lq


def _client(greeks_payload):
    c = MagicMock()
    c.option_greeks.return_value = greeks_payload
    return c


def test_greeks_and_mid_from_xenon():
    c = _client(
        {
            "bid": 10.5,
            "ask": 10.9,
            "greeks": {
                "impliedVol": 0.41,
                "delta": -0.30,
                "gamma": 0.01,
                "vega": 0.2,
                "theta": -0.15,
                "undPrice": 722.0,
            },
        }
    )
    q = live_quote("QQQ", "20260717", 692, "P", client=c)
    assert q["greeks_source"] == "xenon"
    assert q["iv"] == 0.41 and q["delta"] == -0.30
    assert q["mid"] == 10.7 and q["mid_source"] == "xenon"


def test_greeks_present_but_bidask_null_uses_held_leg_mid():
    c = _client(
        {
            "bid": None,
            "ask": None,
            "greeks": {
                "impliedVol": 0.41,
                "delta": -0.30,
                "gamma": 0.01,
                "vega": 0.2,
                "theta": -0.15,
                "undPrice": 722.0,
            },
        }
    )
    q = live_quote("QQQ", "20260717", 692, "P", client=c, fallback_market_price=10.74)
    assert q["greeks_source"] == "xenon"
    assert q["mid"] == 10.74 and q["mid_source"] == "held_leg"


def test_null_greeks_no_ib_is_honest_gap_no_fabrication():
    c = _client(
        {"bid": None, "ask": None, "greeks": None, "note": "no greeks returned"}
    )
    q = live_quote("QQQ", "20260717", 692, "P", client=c)
    assert q["greeks_source"] is None
    assert q["delta"] is None and q["iv"] is None
    assert q["mid"] is None and q["mid_source"] is None  # no fabrication


def test_null_greeks_falls_back_to_ib(monkeypatch):
    c = _client({"bid": None, "ask": None, "greeks": None})
    monkeypatch.setattr(
        lq,
        "_ib_modelgreeks",
        lambda ib, *a: {
            "iv": 0.42,
            "delta": -0.28,
            "gamma": 0.01,
            "theta": -0.14,
            "vega": 0.2,
            "bid": 10.4,
            "ask": 10.8,
        },
    )
    q = live_quote("QQQ", "20260717", 692, "P", client=c, ib=MagicMock())
    assert q["greeks_source"] == "ib"
    assert q["delta"] == -0.28
    assert q["mid"] == pytest.approx(10.6) and q["mid_source"] == "ib"


def test_xenon_http_error_falls_back_to_ib(monkeypatch):
    c = MagicMock()
    c.option_greeks.side_effect = httpx.HTTPStatusError(
        "502", request=MagicMock(), response=MagicMock()
    )
    monkeypatch.setattr(
        lq,
        "_ib_modelgreeks",
        lambda ib, *a: {
            "iv": 0.42,
            "delta": -0.28,
            "gamma": 0.01,
            "theta": -0.14,
            "vega": 0.2,
            "bid": None,
            "ask": None,
        },
    )
    q = live_quote(
        "QQQ",
        "20260717",
        692,
        "P",
        client=c,
        ib=MagicMock(),
        fallback_market_price=10.74,
    )
    assert q["greeks_source"] == "ib"
    assert q["mid"] == 10.74 and q["mid_source"] == "held_leg"
