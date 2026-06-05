"""Derive gamma flip, put wall, and call wall from UW GEX-by-strike output.

UW does not pre-compute these named levels; this module reads the raw
strike-level GEX list and identifies them by definition:

  - gamma flip: zero crossing of cumulative GEX, closest to spot
  - put wall:  strike below spot with the largest positive net GEX
  - call wall: two definitions supported:
      'net_neg_gex' (default) — strike above spot with most negative net GEX;
                                dealers short here will sell into rallies.
                                Useful when net GEX flips above spot.
      'oi_cluster'           — strike above spot with the largest call_gex
                                concentration (positive). Useful for tactical
                                near-expiry reads where calls dominate the
                                hedging mechanics above spot and net GEX
                                stays positive everywhere. Requires rows to
                                include a 'call_gex' field (raw UW shape).

Input row format — either form accepted:
  {strike, gex}                — pre-aggregated net GEX (test inputs use this)
  {strike, call_gex, put_gex}  — raw UW shape from
                                 get_greek_exposure_by_strike or
                                 get_greek_exposure_by_strike_expiry
"""

from __future__ import annotations

from typing import Iterable, Optional


def _net_gex(row: dict) -> float:
    """Net GEX for a row. Accepts {gex} or {call_gex, put_gex}."""
    if "gex" in row:
        return float(row["gex"])
    return float(row.get("call_gex", 0)) + float(row.get("put_gex", 0))


def _call_gex_only(row: dict) -> Optional[float]:
    """Call-leg GEX. Returns None if the row only has a pre-aggregated net."""
    if "call_gex" in row:
        return float(row["call_gex"])
    return None


def _sorted_by_strike(rows: Iterable[dict]) -> list[dict]:
    """Sort rows by strike, dropping rows with non-finite strike or net gex.

    Preserves the original row dict (so call_gex / put_gex are still
    accessible downstream for the 'oi_cluster' definition).
    """
    import math

    cleaned = []
    for r in rows:
        try:
            s = float(r["strike"])
            g = _net_gex(r)
            if math.isfinite(s) and math.isfinite(g):
                cleaned.append(r)
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(cleaned, key=lambda r: float(r["strike"]))


def _gamma_flip(rows: list[dict], spot: float) -> Optional[float]:
    """Linear-interpolated strike at which cumulative GEX crosses zero.

    When the cumulative-GEX curve has multiple zero crossings — common when
    deep-OTM put OI is large enough to push the running sum negative at low
    strikes before call OI dominates near spot — returns the crossing
    nearest to spot. That is the trading-relevant flip: dealer hedging
    behavior changes around spot, not 80% below it.
    """
    if not rows:
        return None
    crossings: list[float] = []
    cum = 0.0
    prev_strike, prev_cum = None, 0.0
    for r in rows:
        strike = float(r["strike"])
        cum += _net_gex(r)
        if prev_strike is not None and prev_cum * cum < 0:
            span = strike - prev_strike
            frac = -prev_cum / (cum - prev_cum) if cum != prev_cum else 0.5
            crossings.append(prev_strike + frac * span)
        prev_strike, prev_cum = strike, cum
    if not crossings:
        return None
    return min(crossings, key=lambda x: abs(x - spot))


def _put_wall(rows: list[dict], spot: float) -> Optional[float]:
    below = [r for r in rows if float(r["strike"]) < spot and _net_gex(r) > 0]
    if not below:
        return None
    return float(max(below, key=_net_gex)["strike"])


def _call_wall(
    rows: list[dict], spot: float, definition: str = "net_neg_gex"
) -> Optional[float]:
    if definition == "net_neg_gex":
        above = [r for r in rows if float(r["strike"]) > spot and _net_gex(r) < 0]
        if not above:
            return None
        return float(min(above, key=_net_gex)["strike"])
    if definition == "oi_cluster":
        candidates: list[tuple[float, float]] = []
        for r in rows:
            if float(r["strike"]) <= spot:
                continue
            cg = _call_gex_only(r)
            if cg is None or cg <= 0:
                continue
            candidates.append((float(r["strike"]), cg))
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[1])[0]
    raise ValueError(
        f"unknown call_wall_definition: {definition!r} "
        f"(use 'net_neg_gex' or 'oi_cluster')"
    )


def compute_levels(
    gex_by_strike: Iterable[dict],
    spot: float,
    call_wall_definition: str = "net_neg_gex",
    *,
    chain_source: str = "UW",
    chain_timestamp: str | None = None,
) -> dict:
    """Return dict with keys gamma_flip, put_wall, call_wall, data_provenance.

    Each input row must have 'strike' plus either 'gex' (pre-aggregated net)
    or 'call_gex' + 'put_gex' (raw UW). Spot is the current underlying price.
    Returns None for any level that cannot be identified.

    call_wall_definition controls which method picks the call wall:
      'net_neg_gex' (default) — strike above spot with most negative net GEX
      'oi_cluster'           — strike above spot with largest positive call_gex
                                (requires call_gex in input rows)

    data_provenance tags every level as 'computed' from the given
    chain_source (default UW). Trader-visible audit trail consistent with
    the chain-mid discipline in fair_aq_dq / fair_coupon / macro_hedge.
    """
    rows = _sorted_by_strike(list(gex_by_strike))
    flip = _gamma_flip(rows, spot)
    put_wall = _put_wall(rows, spot)
    call_wall = _call_wall(rows, spot, definition=call_wall_definition)
    provenance = {
        "gamma_flip": {
            "value": flip,
            "source": "computed",
            "detail": f"net-GEX sign change in {chain_source} GEX-by-strike",
            "timestamp": chain_timestamp,
        },
        "put_wall": {
            "value": put_wall,
            "source": "computed",
            "detail": f"max positive net GEX below spot ${spot:.2f} in {chain_source} GEX-by-strike",
            "timestamp": chain_timestamp,
        },
        "call_wall": {
            "value": call_wall,
            "source": "computed",
            "detail": (
                f"call wall via {call_wall_definition} above spot ${spot:.2f} "
                f"in {chain_source} GEX-by-strike"
            ),
            "timestamp": chain_timestamp,
        },
    }
    return {
        "gamma_flip": flip,
        "put_wall": put_wall,
        "call_wall": call_wall,
        "data_provenance": provenance,
    }


def compute_levels_per_expiry(
    uw_rows: Iterable[dict],
    spot: float,
    call_wall_definition: str = "net_neg_gex",
    *,
    chain_source: str = "UW",
    chain_timestamps: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Per-expiry gamma flip + walls from a flat UW per-strike-per-expiry list.

    Trading reads of 'the' call wall are usually per-expiry — concentrated
    call OI on this Friday is mechanically distinct from concentrated call
    OI three months out. This function groups the rows by expiry and runs
    compute_levels for each, so the caller can read the wall at the trade
    horizon they actually care about instead of an aggregate across all
    listed expiries.

    Input: list of dicts from get_greek_exposure_by_strike_expiry. Each row
    must include 'expiry' plus the fields compute_levels expects.
    Returns: {expiry: {gamma_flip, put_wall, call_wall, data_provenance}}

    Pass-2 (P2-B): chain_source + chain_timestamps propagate through to
    each per-expiry compute_levels call so the data_provenance block
    carries the right source + per-expiry timestamp. Without this, the
    aggregated output had data_provenance with timestamp=None and a
    hardcoded UW default for every expiry — useless for an audit trail.
    """
    by_expiry: dict[str, list[dict]] = {}
    for r in uw_rows:
        try:
            exp = str(r["expiry"])
        except (KeyError, TypeError):
            continue
        by_expiry.setdefault(exp, []).append(r)

    timestamps = chain_timestamps or {}
    return {
        exp: compute_levels(
            rows,
            spot,
            call_wall_definition=call_wall_definition,
            chain_source=chain_source,
            chain_timestamp=timestamps.get(exp),
        )
        for exp, rows in by_expiry.items()
    }
