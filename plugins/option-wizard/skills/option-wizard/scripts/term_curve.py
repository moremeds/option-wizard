"""IV term-curve regime labeling across held / analyzed expiries.

Centralizes the contango / flat / inverted decision so Workflow 1
(new-position analysis), Workflow 3 (book review), and Workflow 6
(复盘 retrospective) label the same curve identically. Inline LLM
labeling produced inconsistent results across runs — this helper
forces a single source of truth.

## Conventions

- ATM IV is annualized decimal (0.45 = 45% annualized).
- Expiry keys are ISO date strings ("YYYY-MM-DD") and are sorted
  ascending before labeling.
- Basis = IV_later − IV_earlier. Positive = contango (normal vol term
  structure). Negative = inversion (front catalyst priced in).
- `eps_flat` is the dead-band where a pair is labeled "flat". Default
  0.01 = 1 vol point. ATM IV differences under 1pp are noise on most
  liquid names; tighten for very liquid mega-cap names if needed.

## Aggregate regime labels

- `all_contango` — every adjacent pair is contango (textbook normal)
- `all_inverted` — every adjacent pair is inverted (multiple catalysts
  stacked in a row, e.g. ER then FOMC then div ex-date)
- `all_flat` — every pair within eps (deep calm, common in late-summer
  drift markets)
- `mixed_contango_inverted` — at least one inversion and at least one
  contango. The most actionable regime — usually means catalyst is
  isolated to one window; deferring the trade out of that window may
  recover skew premium
- `mixed_with_flat` — mix of flat and one direction, no opposite-sign
  pair

Use `summarize_regime` to collapse a list of pairs into a single label
for stage-2 book-review tables.
"""

from __future__ import annotations

from typing import Iterable


def label_regime(
    atm_iv_by_expiry: dict[str, float],
    eps_flat: float = 0.01,
) -> list[dict]:
    """Label each adjacent expiry pair as contango / flat / inverted.

    Args:
        atm_iv_by_expiry: dict mapping ISO expiry string ("YYYY-MM-DD")
            to ATM IV (annualized decimal). Caller is responsible for
            computing ATM IV per expiry — use `atm_iv_from_chain_rows`
            if pulling from a raw UW chain response.
        eps_flat: half-width of the dead-band around zero basis. A pair
            with |basis| <= eps_flat is labeled "flat". Default 0.01
            (1 vol point).

    Returns:
        List of dicts, one per adjacent expiry pair, in ascending expiry
        order. Each dict carries:
            from_expiry, to_expiry  : ISO date strings
            iv_from, iv_to          : ATM IV at each end
            basis                   : iv_to − iv_from
            regime                  : "contango" | "flat" | "inverted"

    Raises:
        ValueError: if fewer than 2 expiries, or any IV is negative / NaN.
    """
    if not isinstance(atm_iv_by_expiry, dict):
        raise ValueError("atm_iv_by_expiry must be a dict mapping expiry -> ATM IV")
    if len(atm_iv_by_expiry) < 2:
        raise ValueError(
            f"need at least 2 expiries to label a term curve; "
            f"got {len(atm_iv_by_expiry)}"
        )
    if eps_flat < 0:
        raise ValueError(f"eps_flat must be non-negative; got {eps_flat}")

    for expiry, iv in atm_iv_by_expiry.items():
        if iv is None or iv < 0 or iv != iv:  # NaN catches via self-compare
            raise ValueError(
                f"ATM IV must be a non-negative number; "
                f"got iv={iv!r} for expiry={expiry!r}"
            )

    sorted_expiries = sorted(atm_iv_by_expiry.keys())

    pairs: list[dict] = []
    for earlier, later in zip(sorted_expiries[:-1], sorted_expiries[1:]):
        iv_from = atm_iv_by_expiry[earlier]
        iv_to = atm_iv_by_expiry[later]
        basis = iv_to - iv_from
        if basis > eps_flat:
            regime = "contango"
        elif basis < -eps_flat:
            regime = "inverted"
        else:
            regime = "flat"
        pairs.append(
            {
                "from_expiry": earlier,
                "to_expiry": later,
                "iv_from": iv_from,
                "iv_to": iv_to,
                "basis": basis,
                "regime": regime,
            }
        )
    return pairs


def summarize_regime(pairs: Iterable[dict]) -> str:
    """Collapse a labeled term curve into a single aggregate label.

    Args:
        pairs: iterable of pair dicts as returned by `label_regime`.

    Returns:
        One of:
            "all_contango", "all_inverted", "all_flat",
            "mixed_contango_inverted", "mixed_with_flat"

    Raises:
        ValueError: if the iterable is empty.
    """
    regimes = [p["regime"] for p in pairs]
    if not regimes:
        raise ValueError("pairs is empty; call label_regime first")

    unique = set(regimes)
    if unique == {"contango"}:
        return "all_contango"
    if unique == {"inverted"}:
        return "all_inverted"
    if unique == {"flat"}:
        return "all_flat"
    if "contango" in unique and "inverted" in unique:
        return "mixed_contango_inverted"
    return "mixed_with_flat"


def _pivot_uw_contract_rows(rows: list[dict], *, strike_key: str) -> list[dict]:
    """Pivot per-contract chain rows into the per-strike {call_iv, put_iv}
    shape `atm_iv_from_chain_rows` expects.

    `get_chains_for_expiry` (the MCP tool actually used at Workflow-6
    step 3b) returns one row per (strike, option_type) with a single `iv`
    field — e.g. `{"strike": "7215", "option_type": "put", "iv": null}` —
    not the {strike, call_iv, put_iv} wide shape this module was designed
    against. Observed live 2026-07-02: every caller had to hand-write this
    same defaultdict pivot before the ATM lookup worked at all.
    """
    by_strike: dict[float, dict] = {}
    for r in rows:
        s = float(r[strike_key])
        entry = by_strike.setdefault(s, {strike_key: s})
        iv = r.get("iv")
        if iv is None:
            continue
        side = str(r.get("option_type", "")).lower()
        key = (
            "call_iv"
            if side.startswith("c")
            else "put_iv"
            if side.startswith("p")
            else None
        )
        if key:
            entry[key] = iv
    return list(by_strike.values())


def atm_iv_from_chain_rows(
    rows: list[dict],
    spot: float,
    *,
    strike_key: str = "strike",
    call_iv_key: str = "call_iv",
    put_iv_key: str = "put_iv",
) -> float | None:
    """Compute ATM IV from a UW chain response (single expiry).

    Picks the strike closest to spot, averages call and put IV. Falls
    back to whichever side is present if the other is missing. Returns
    None if neither side has a valid IV at the closest strike.

    Args:
        rows: list of rows from `get_chains_for_expiry`. Accepts either
            shape: the per-strike {strike, call_iv, put_iv} shape (pass
            straight through), or the actual MCP per-contract shape — one
            row per (strike, option_type) carrying a single `iv` field —
            which is auto-pivoted via `_pivot_uw_contract_rows` when
            detected (rows carry `option_type` but not `call_iv_key`).
            Missing / null IV fields are tolerated either way.
        spot: current spot price of the underlying.
        strike_key, call_iv_key, put_iv_key: column names. Defaults match
            the canonical UW shape; override for alternate providers.

    Returns:
        ATM IV (annualized decimal) or None if no usable IV at the
        ATM strike.

    Raises:
        ValueError: if rows is empty or spot is non-positive.
    """
    if not rows:
        raise ValueError("rows is empty; cannot pick ATM strike")
    if spot <= 0:
        raise ValueError(f"spot must be positive; got {spot}")

    if "option_type" in rows[0] and call_iv_key not in rows[0]:
        rows = _pivot_uw_contract_rows(rows, strike_key=strike_key)

    def _strike(row: dict) -> float:
        return float(row[strike_key])

    atm_row = min(rows, key=lambda r: abs(_strike(r) - spot))

    call_iv = atm_row.get(call_iv_key)
    put_iv = atm_row.get(put_iv_key)

    ivs: list[float] = []
    for iv in (call_iv, put_iv):
        if iv is None:
            continue
        try:
            iv_f = float(iv)
        except (TypeError, ValueError):
            continue
        if iv_f < 0 or iv_f != iv_f:
            continue
        ivs.append(iv_f)

    if not ivs:
        return None
    return sum(ivs) / len(ivs)


def atm_iv_by_expiry_from_term_structure(
    rows: list[dict],
    expiries: Iterable[str],
    *,
    expiry_key: str = "expiry",
    iv_key: str = "volatility",
) -> dict[str, float]:
    """Extract ATM IV per held expiry from a UW `iv_term_structure` response.

    One `iv_term_structure(ticker)` call covers the ticker's full listed
    term structure (verified live 2026-07-02: `dte: 0` through the
    furthest-dated contract, `volatility` field per row) — far cheaper
    than pulling `get_chains_for_expiry` once per expiry via
    `atm_iv_from_chain_rows`. Use this first; fall back to
    `atm_iv_from_chain_rows` only for expiries this doesn't cover (some
    non-monthly/quarterly dates are absent — observed missing for SPX
    2026-07-10 and 2026-07-13 the same day).

    Args:
        rows: `iv_term_structure(ticker)["data"]`.
        expiries: ISO expiry strings to extract (the trader's held dates).
        expiry_key, iv_key: column names; defaults match the UW shape.

    Returns:
        dict mapping only the FOUND expiries to their ATM IV (float).
        Missing expiries are simply absent from the result — the caller
        chains `atm_iv_from_chain_rows` for those, then feeds the union
        into `label_regime`.
    """
    by_expiry = {str(r[expiry_key]): r for r in rows}
    out: dict[str, float] = {}
    for exp in expiries:
        row = by_expiry.get(exp)
        if row is None or row.get(iv_key) is None:
            continue
        out[exp] = float(row[iv_key])
    return out
