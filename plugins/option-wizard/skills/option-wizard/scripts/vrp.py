"""Volatility risk premium: implied vol minus realized vol.

UW does not pre-compute VRP as a single number; this is just IV − RV.
Both inputs are annualized decimals (0.80 = 80% annualized). Labels:

  RICH    : VRP >= 0.05  (sell-premium regime favored)
  NEUTRAL : -0.05 < VRP < 0.05
  CHEAP   : VRP <= -0.05 (buy-premium regime favored)
"""

from __future__ import annotations

import math


def compute_vrp(iv: float, rv: float, with_label: bool = False) -> float | dict:
    if iv < 0 or rv < 0 or math.isnan(iv) or math.isnan(rv):
        raise ValueError(
            f"iv and rv must be non-negative numbers; got iv={iv}, rv={rv}"
        )
    vrp = iv - rv
    if not with_label:
        return vrp
    if vrp >= 0.05:
        label = "RICH"
    elif vrp <= -0.05:
        label = "CHEAP"
    else:
        label = "NEUTRAL"
    return {"vrp": vrp, "label": label}
