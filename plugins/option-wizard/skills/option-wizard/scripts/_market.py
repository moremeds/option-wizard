"""Shared market-data primitives used by scripts that read chain mids.

This module exists because fair_aq_dq, fair_coupon (chain path), and
macro_hedge (chain path) all need the same three operations:

  1. Look up a listed-strike option mid from a chain dict
  2. Pick the listed expiry closest to a target tenor (skipping past expiries)
  3. Tag every numeric they emit with a `data_provenance` entry so the
     trader can audit which input came from where (UW / IB / TV / computed
     / fallback) and when.

The chain shape is:

    chain[expiry_iso][strike_pct][right]['mid' | 'iv']

where:
  - expiry_iso : 'YYYY-MM-DD' string
  - strike_pct : float, fraction of spot (0.95 = 95% spot)
  - right      : 'put' or 'call'

The orchestrator (skill prompt) is responsible for normalizing real UW/IB
chain rows into this shape (round strike to nearest listed within a
tolerance) before passing the Snapshot in. This module does not call UW or
IB — it is pure functions over the already-fetched data.

See references/aq-dq-framework.md §3 and references/fcn-framework.md (TBD)
for the per-script discipline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

# ─── Chain lookup ───────────────────────────────────────────


def read_chain_mid(
    chain: dict,
    expiry: str,
    strike_pct: float,
    right: Literal["put", "call"],
    *,
    tolerance: float = 0.005,
) -> float | None:
    """Read mid price from chain at (expiry, strike_pct ± tolerance, right).

    Returns None if missing OR if the mid is non-positive (Pass-3 A2:
    real UW chains return mid=0.0 for illiquid / no-bid strikes; if we
    accepted it as a valid price, hedge legs would be priced at $0 and
    silently pass the cost cap. Treat <= 0 as 'no quote' so the caller
    falls back to BSM and the provenance correctly flags it).

    Tolerance (Pass-5 P5-CRITICAL, live UW verification): real chain keys
    come from `strike_dollar / spot` rounded to 4 decimals. Caller asks
    for round strike_pcts (0.75, 0.80, 0.85), but those rarely match
    actual listed strikes exactly (SPY at $757: nearest 75%-strike is
    $568 → key 0.7503, not 0.7500). Without tolerance, every chain lookup
    silently misses and falls back to BSM model — defeating the whole
    chain-mid sweep. Default 0.005 = 0.5% spot = half a strike-width on
    most names. Set tolerance=0 for exact lookup (orchestrator-validated
    chain keys).

    Caller decides whether to use a fallback pricing model — this function
    never fabricates a price. Returning None is the signal that the
    orchestrator must either pull a different strike or accept the
    BSM-fallback degradation (and record `fallback_used=True` in
    provenance).
    """
    by_strike = chain.get(expiry, {})
    # Fast path: exact key hit
    mid = by_strike.get(strike_pct, {}).get(right, {}).get("mid")
    if mid is not None and mid > 0:
        return mid
    # Tolerance path: nearest-strike-within-tolerance fuzzy match
    if tolerance > 0 and by_strike:
        candidates = [
            (abs(k - strike_pct), k)
            for k in by_strike.keys()
            if abs(k - strike_pct) <= tolerance
        ]
        if candidates:
            _, nearest_key = min(candidates)
            mid = by_strike[nearest_key].get(right, {}).get("mid")
            if mid is not None and mid > 0:
                return mid
    return None


def read_chain_iv(
    chain: dict, expiry: str, strike_pct: float, right: Literal["put", "call"]
) -> float | None:
    """Same as read_chain_mid but for IV. Used when computing barrier
    probabilities that need strike-specific IV (not ATM)."""
    return chain.get(expiry, {}).get(strike_pct, {}).get(right, {}).get("iv")


def nearest_expiry_to_tenor(
    chain: dict[str, Any], tenor_months: int, quote_start_iso: str
) -> str:
    """Pick the listed expiry closest to (quote_start + tenor_months).

    Filters past expiries first — a stale snapshot with only expired chain
    dates would otherwise pick a dead option (Pass-3 finding A4 from the
    AQ/DQ tribunal). Raises ValueError if no future-dated expiry exists.

    `tenor_months × 30` is used as the day-count approximation. Real
    expiries usually fall on the third Friday, so the "closest" match has
    up to ±15 days drift from a clean N-month forward. That drift is
    acceptable for fair-value heuristic work; callers needing exact
    duration matching must pre-resolve the expiry themselves.
    """
    target = datetime.fromisoformat(quote_start_iso.replace("Z", "+00:00"))
    target_days = tenor_months * 30

    best = None
    best_diff = None
    for exp in chain.keys():
        exp_dt = datetime.fromisoformat(exp + "T00:00:00+00:00")
        days_to_exp = (exp_dt - target).days
        if days_to_exp < 0:
            continue
        diff = abs(days_to_exp - target_days)
        if best_diff is None or diff < best_diff:
            best = exp
            best_diff = diff
    if best is None:
        raise ValueError(
            "No future-dated expiries in chain — orchestrator must refresh"
        )
    return best


# ─── Provenance schema ──────────────────────────────────────

# Conventional source tags. Use these strings consistently so the trader
# can grep / filter across all script outputs. Free-form descriptions are
# allowed for "computed" entries (e.g., "computed (BSM first-passage)").
SOURCE_UW = "UW"
SOURCE_IB = "IB"
SOURCE_TV = "TV"
SOURCE_COMPUTED = "computed"
SOURCE_FALLBACK = "fallback"


def provenance_entry(
    value: float | int | str | bool | None,
    source: str,
    *,
    timestamp: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    """Build one provenance entry for a numeric field.

    Standard shape:
      {"value": ..., "source": "UW" | "IB" | "TV" | "computed" | "fallback",
       "timestamp": "...", "detail": "free-form"}

    The `detail` field is for breadcrumbs like
    `"UW chain[2027-06-18][0.95]['put']['mid']"` or
    `"BSM fallback — chain mid unavailable at strike 0.50"`.
    """
    entry: dict[str, Any] = {"value": value, "source": source}
    if timestamp is not None:
        entry["timestamp"] = timestamp
    if detail is not None:
        entry["detail"] = detail
    return entry


def chain_leg_provenance(
    value: float,
    chain_source: Literal["UW", "IB"],
    expiry: str,
    strike_pct: float,
    right: Literal["put", "call"],
    field: Literal["mid", "iv"] = "mid",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Convenience builder for a chain-read provenance entry. Encodes the
    full chain path in `detail` so the trader can verify the exact strike
    that priced the leg."""
    return provenance_entry(
        value=value,
        source=chain_source,
        timestamp=timestamp,
        detail=f"{chain_source} chain[{expiry}][{strike_pct}]['{right}']['{field}']",
    )


def fallback_provenance(
    value: float, reason: str, *, timestamp: str | None = None
) -> dict[str, Any]:
    """Convenience builder for a fallback provenance entry. Use when the
    chain didn't cover the strike and the script computed a BSM/model
    price instead. The reason should explain why fallback was needed."""
    return provenance_entry(
        value=value,
        source=SOURCE_FALLBACK,
        timestamp=timestamp,
        detail=reason,
    )


# ─── Real-source row normalization ─────────────────────────


def _parse_occ_symbol(symbol: str) -> tuple[str, str, Literal["put", "call"], float]:
    """Parse OCC option symbol → (ticker, expiry_iso, right, strike_dollar).

    OCC format: TTTT[T...]YYMMDDR_PPPPPPPP where R is C or P, strike is
    8 digits with implicit 3-decimal precision (00757000 = $757.000).

    Live verified against UW `get_options_chain` response 2026-06-05:
    'SPY260604C00757000' → ('SPY', '2026-06-04', 'call', 757.0).
    """
    # Find the date+right boundary. Walk from the right: 8 strike digits,
    # then 1 right char (C/P), then 6 date digits.
    if len(symbol) < 15:
        raise ValueError(f"OCC symbol too short: {symbol!r}")
    strike_str = symbol[-8:]
    right_char = symbol[-9]
    date_str = symbol[-15:-9]
    ticker = symbol[:-15]

    if right_char not in ("C", "P"):
        raise ValueError(f"OCC symbol right char must be C or P: {symbol!r}")
    strike_dollar = int(strike_str) / 1000.0
    expiry_iso = f"20{date_str[0:2]}-{date_str[2:4]}-{date_str[4:6]}"
    right: Literal["put", "call"] = "put" if right_char == "P" else "call"
    return ticker, expiry_iso, right, strike_dollar


def normalize_uw_chain_rows(
    uw_rows: list[dict],
    spot: float,
    *,
    strike_pct_decimals: int = 4,
) -> dict:
    """Normalize raw UW `get_options_chain` / `get_chains_for_expiry` rows
    into the shape that scripts._market consumers expect.

    UW returns rows like (live-verified shape):
        {"option_symbol": "SPY260604C00757000",
         "nbbo_bid": "0.02", "nbbo_ask": "0.03",
         "implied_volatility": "0.0943...",
         "last_price": "0.02", ...}

    My consumer shape:
        chain[expiry_iso][strike_pct][right]['mid' | 'iv']

    Steps applied per row:
      1. Parse OCC symbol → (expiry, right, strike_dollar)
      2. strike_pct = round(strike_dollar / spot, decimals)  -- matches the
         macro_hedge _price_put_leg lookup convention (Pass-2 P2-A)
      3. mid = (float(nbbo_bid) + float(nbbo_ask)) / 2
      4. iv = float(implied_volatility)
      5. Skip rows where nbbo_bid or nbbo_ask are missing or non-numeric
         (UW returns these for halted / unquoted strikes)

    Rows with bid+ask both zero produce mid=0; read_chain_mid treats that
    as 'no quote' (Pass-3 A2) so callers fall back to BSM cleanly. We
    write the 0 mid here rather than filtering — keeps the IV field
    available, lets read_chain_mid be the single decision point.
    """
    chain: dict[str, dict[float, dict[str, dict[str, float]]]] = {}
    for row in uw_rows:
        try:
            sym = row["option_symbol"]
            _, expiry, right, strike_dollar = _parse_occ_symbol(sym)
        except (KeyError, ValueError):
            continue
        try:
            bid = float(row.get("nbbo_bid"))
            ask = float(row.get("nbbo_ask"))
        except (TypeError, ValueError):
            continue
        mid = (bid + ask) / 2.0
        try:
            iv = float(row.get("implied_volatility"))
        except (TypeError, ValueError):
            iv = 0.0

        strike_pct = round(strike_dollar / spot, strike_pct_decimals)
        chain.setdefault(expiry, {}).setdefault(strike_pct, {})[right] = {
            "mid": mid,
            "iv": iv,
        }
    return chain
