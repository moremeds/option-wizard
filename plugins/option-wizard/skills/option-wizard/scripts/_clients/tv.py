"""TradingView desktop reader, used as a fallback for option mids.

When Interactive Brokers returns no quote (markets closed, no L1 options
subscription, contract halted), the daily position scan falls back here so
the trader still sees a real `% of credit decayed` and a real delta on
each row.

Depends on `opencli tradingview options-chain` (the himself65/finance-skills
plugin) attaching to a running TradingView.app over CDP. The endpoint is
read from OPENCLI_CDP_ENDPOINT in the environment.

Reads only — never modifies chart, watchlist, or alert state.
"""

from __future__ import annotations

import json
import subprocess
from functools import lru_cache

# IB symbol -> TV exchange. Equities default to NASDAQ; the ETFs we trade
# all live on NYSE Arca, which opencli/TV addresses as AMEX. Unknown
# symbols fall through to a NASDAQ-then-AMEX probe in `_resolve_exchange`.
_SYM_TO_TV_EXCHANGE: dict[str, str] = {
    "QQQ": "NASDAQ",
    "SPY": "AMEX",
    "GLD": "AMEX",
    "IWM": "AMEX",
    "DIA": "AMEX",
    "TLT": "NASDAQ",
}


def _resolve_exchange(symbol: str) -> list[str]:
    if symbol in _SYM_TO_TV_EXCHANGE:
        return [_SYM_TO_TV_EXCHANGE[symbol]]
    return ["NASDAQ", "AMEX"]


def _ib_expiry_to_tv(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


@lru_cache(maxsize=64)
def _fetch_chain(
    symbol: str, exchange: str, expiry: str, right: str
) -> tuple[dict, ...] | None:
    """Pull (and cache) one (symbol, expiry, right) chain from TV.

    Returns a tuple of strike rows or None if the call failed. Tuple so the
    lru_cache key is hashable; callers iterate it as a sequence.
    """
    cmd = [
        "opencli",
        "tradingview",
        "options-chain",
        "--ticker",
        symbol,
        "--exchange",
        exchange,
        "--expiry",
        expiry,
        "--type",
        right,
        "--strikes-around-spot",
        "120",
        "-f",
        "json",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if r.returncode != 0:
        return None
    try:
        chain = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(chain, list):
        return None
    return tuple(chain)


def get_option_quote(
    symbol: str,
    expiry_yyyymmdd: str,
    strike: float,
    right: str,
) -> dict | None:
    """Return a quote dict for one option contract or None.

    Shape on hit: {"mid": float, "delta": float|None, "iv": float|None,
    "bid": float, "ask": float, "source": "tv"}.

    `right` accepts "P"/"C" (IB convention) or "put"/"call" (TV convention).
    """
    tv_right = {"P": "put", "C": "call"}.get(right.upper(), right.lower())
    if tv_right not in ("put", "call"):
        return None
    expiry = _ib_expiry_to_tv(expiry_yyyymmdd)
    for exchange in _resolve_exchange(symbol):
        chain = _fetch_chain(symbol, exchange, expiry, tv_right)
        if not chain:
            continue
        # TV strikes can be int or float; match with float tolerance.
        for row in chain:
            if abs(float(row["strike"]) - float(strike)) < 1e-6:
                bid = row.get("bid")
                ask = row.get("ask")
                mid = row.get("mid")
                if mid is None and bid is not None and ask is not None:
                    mid = (bid + ask) / 2
                if mid is None:
                    return None
                return {
                    "mid": float(mid),
                    "delta": row.get("delta"),
                    "iv": row.get("iv"),
                    "bid": bid,
                    "ask": ask,
                    "source": "tv",
                }
        # Strike not in this exchange's chain; try the next exchange.
    return None


def clear_cache() -> None:
    """Invalidate the per-process chain cache (test helper)."""
    _fetch_chain.cache_clear()
