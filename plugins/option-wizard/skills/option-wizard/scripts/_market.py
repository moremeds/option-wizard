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
    chain: dict, expiry: str, strike_pct: float, right: Literal["put", "call"]
) -> float | None:
    """Read mid price from chain at exact (expiry, strike_pct, right).

    Returns None if not present. Caller decides whether to use a fallback
    pricing model — this function never fabricates a price. Returning None
    is the signal that the orchestrator must either pull a different strike
    or accept the BSM-fallback degradation (and record `fallback_used=True`
    in provenance).
    """
    return chain.get(expiry, {}).get(strike_pct, {}).get(right, {}).get("mid")


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
