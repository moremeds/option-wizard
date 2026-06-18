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
        "mid": None,
        "mid_source": None,
        "bid": None,
        "ask": None,
        "iv": None,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
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
