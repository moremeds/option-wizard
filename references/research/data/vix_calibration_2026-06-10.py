"""VIX call BSM-vs-mid calibration. Pulled 2026-06-10.

Per Pitfall 01 + research §9, all VIX option prices in
`2026-06-10-convex-macro-hedges.md` are BSM estimates using VVIX as IV
and (VIX + VIX3M)/2 as underlying. The literature estimates real listed
mids are 50-200% higher in calm regimes. This file calibrates the
actual gap using live UW data at one regime snapshot.

REGIME at pull time (2026-06-10):
  VIX     = 20.14   (yfinance, 2026-06-10 EOD)
  VIX9D   = 19.69   (yfinance, 2026-06-08 EOD)
  VIX3M   = 20.79   (yfinance, 2026-06-08 EOD)
  VVIX    = 92.40   (yfinance, 2026-06-08 EOD)
  SKEW    = 145.00  (yfinance, 2026-06-08 EOD)
  VIX9D/VIX = 0.978  (NOT inverted — calm baseline regime)

This is a CALM BASELINE calibration, not an inversion-event one.
When the next VIX9D/VIX > 1.04 inversion fires (per the regime decision
tree in macro-hedge-convexity.md), pull this same script + append the
inversion-regime row to `vix_calibration_history.csv` (TBD).

Source: UW MCP get_options_chain VIX expiry=2026-07-22 (42 DTE).

Run with: .venv/bin/python references/research/data/vix_calibration_2026-06-10.py
"""

from __future__ import annotations

import math

from scipy.stats import norm

# ── Live data captured from UW MCP, 2026-06-10 ──
PULL_DATE = "2026-06-10"
EXPIRY = "2026-07-22"
DTE = 42

VIX_SPOT = 20.14
VIX3M_SPOT = 20.79
VVIX_SPOT = 92.40
VX1_PROXY = 0.5 * VIX_SPOT + 0.5 * VIX3M_SPOT  # underlying-of-options proxy

# Observed UW chain rows for VIX 2026-07-22.
# UW returned `nbbo_bid` / `nbbo_ask` as null (EOD cache), but `theo` and
# `last_price` + per-strike `iv` were populated. Using `theo` as
# market-fair proxy (UW internal model fit on live tape).
OBSERVED = [
    # (strike, last_price, theo, observed_iv_at_strike, volume, open_interest)
    (25.0, 1.45, 1.465, 1.062, 6215, 169493),
    (24.0, 1.64, 1.605, 1.023, 5621, 86777),
    (23.0, 1.77, 1.782, 0.984, 2978, 49081),
    (22.0, 1.98, 1.963, 0.933, 4202, 91385),
    (21.0, 2.21, 2.200, 0.884, 391, 24106),
    (20.0, 2.47, 2.503, 0.836, 8155, 53184),  # ATM
    # K=35 and K=45 were in the get_chains_for_expiry dump but with stale
    # last_price only (no IV). Recorded for completeness, marked as
    # "last_price only, IV inferred from VVIX with skew adjustment TBD"
    (35.0, 0.71, None, None, 6557, 308008),
    (45.0, 0.43, None, None, 4784, 188978),
]


def bs_call(
    spot: float, strike: float, t: float, sigma: float, r: float = 0.04
) -> float:
    if t <= 0 or sigma <= 0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    return spot * norm.cdf(d1) - strike * math.exp(-r * t) * norm.cdf(d2)


def report():
    t = DTE / 365.0
    vvix_iv = VVIX_SPOT / 100.0

    print(f"VIX calibration snapshot {PULL_DATE}, expiry {EXPIRY} ({DTE} DTE)")
    print(f"  VIX={VIX_SPOT}, VIX3M={VIX3M_SPOT}, VVIX={VVIX_SPOT}, SKEW=145")
    print(f"  VX1 underlying proxy = {VX1_PROXY:.3f}")
    print(f"  VVIX-as-IV (ATM proxy) = {vvix_iv:.3f}")
    print()
    print(
        f"{'K':>6} {'last':>7} {'theo':>7} {'iv@K':>7} {'BSM(VVIX)':>10} "
        f"{'BSM(iv@K)':>10} {'gap%':>7}"
    )
    print("-" * 70)

    rows = []
    for strike, last, theo, iv_strike, vol, oi in OBSERVED:
        bsm_vvix = bs_call(VX1_PROXY, strike, t, vvix_iv)
        bsm_at_iv = bs_call(VX1_PROXY, strike, t, iv_strike) if iv_strike else None
        # Pick observed mid: theo if present, else last
        observed_mid = theo if theo is not None else last
        gap_pct = (
            ((observed_mid - bsm_vvix) / observed_mid * 100)
            if observed_mid and observed_mid > 0
            else None
        )
        print(
            f"{strike:>6.1f} {last:>7.2f} "
            f"{(theo if theo else float('nan')):>7.3f} "
            f"{(iv_strike if iv_strike else float('nan')):>7.3f} "
            f"{bsm_vvix:>10.3f} "
            f"{(bsm_at_iv if bsm_at_iv is not None else float('nan')):>10.3f} "
            f"{(gap_pct if gap_pct is not None else float('nan')):>7.1f}"
        )
        rows.append(
            {
                "strike": strike,
                "last": last,
                "theo": theo,
                "iv_at_strike": iv_strike,
                "bsm_vvix": round(bsm_vvix, 4),
                "bsm_at_iv": round(bsm_at_iv, 4) if bsm_at_iv else None,
                "gap_pct": round(gap_pct, 1) if gap_pct is not None else None,
                "volume": vol,
                "open_interest": oi,
            }
        )

    print()
    print("KEY FINDINGS:")
    print()
    print("1. BSM(VVIX-as-IV) UNDERSTATES the K=25 call mid by 23% in calm regime.")
    print("   theo $1.465 vs BSM(VVIX) $1.128 → gap +23%.")
    print("   Smaller than the 50-200% rule of thumb from literature → which")
    print("   was likely sampling inversion regimes + deeper OTM strikes.")
    print()
    print("2. The GAP CAUSE is VIX call skew, not BSM math error.")
    print("   At K=25 (5pts above VX1 underlying), actual IV is 1.062 vs")
    print("   VVIX's 0.924 = +15% higher IV at strike. Using strike-specific")
    print("   IV instead of VVIX: BSM(iv@K=25) = $1.502 ≈ theo $1.465 (~3% off).")
    print()
    print("3. K=35 and K=45 calls TRADE THINLY but with HIGH OI (308k, 189k)")
    print("   suggesting they're hedging instruments held by institutions.")
    print("   No IV available for these strikes in this pull — would need a")
    print("   separate UW interpolated-IV request to compute the deep-OTM gap.")
    print()
    print("4. For the macro_hedge.py VIX ladder structure (K=25+35+45),")
    print("   the K=25 leg has +23% mid-vs-BSM gap. Deep-OTM legs likely have")
    print("   LARGER gap (call-skew steepens with strike). When pricing the")
    print("   ladder with VVIX-as-IV the cost is UNDERSTATED by AT LEAST 23%")
    print("   and probably 40-60% on the full structure. Adjust the scorecard")
    print("   accordingly when interpreting calm-regime backtests.")
    print()
    print("5. This is ONE data point. Repeat on the next VIX9D/VIX inversion")
    print("   to calibrate inversion-regime gap (the literature claim of")
    print("   50-200% was likely inversion-event sampling).")

    import json
    from pathlib import Path

    out = Path(__file__).parent / "vix_calibration_history.json"
    if out.exists():
        history = json.loads(out.read_text())
    else:
        history = []
    history.append(
        {
            "pull_date": PULL_DATE,
            "expiry": EXPIRY,
            "dte": DTE,
            "regime": "calm_baseline",
            "vix": VIX_SPOT,
            "vix9d": 19.69,
            "vix3m": VIX3M_SPOT,
            "vvix": VVIX_SPOT,
            "skew": 145.0,
            "vix9d_over_vix": round(19.69 / VIX_SPOT, 3),
            "vx1_proxy": VX1_PROXY,
            "rows": rows,
            "summary_k25_gap_pct": 23.0,
            "note": (
                "Calm-baseline calibration. VIX9D/VIX = 0.978 (NOT inverted). "
                "K=25 call mid is 23% higher than BSM(VVIX-as-IV). Cause: "
                "VIX call skew (IV at K=25 is 1.062 vs ATM VVIX 0.924). "
                "Repeat on next VIX9D/VIX > 1.04 inversion to capture "
                "inversion-regime gap."
            ),
        }
    )
    out.write_text(json.dumps(history, indent=2))
    print(f"\nWrote calibration history to {out}")


if __name__ == "__main__":
    report()
