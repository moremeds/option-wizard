"""Fair-value evaluation for AQ (Accumulator) / DQ (Decumulator) PB products.

The unified framework parameterizes AQ vs DQ via `direction`. Listed-strike
option prices, IV, greeks are READ from UW or IB chain (orchestrator's
choice — see SKILL.md hard rule #2). The script computes only barrier
termination probabilities, accumulation PV, and the fair vs quoted pp
delta. Every numeric Verdict field carries a `data_provenance` entry.

Hard rule: defined-risk only does NOT apply — AQ/DQ are inherently
undefined-tail products. The framework's job is to expose how much PB
markup the trader is paying, not to make AQ/DQ safe.

See references/aq-dq-framework.md for the domain knowledge layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Literal

# ─── Data contracts ──────────────────────────────────────────


@dataclass(frozen=True)
class Quote:
    direction: Literal["AQ", "DQ"]
    ticker: str
    spot: float
    strike_pct: float  # 0.95 = strike at 95% spot
    ko_pct: float  # 1.03 = KO at 103% spot (AQ); 0.97 (DQ)
    tenor_months: int
    obs_freq: Literal["daily", "weekly", "monthly"]
    doubling_factor: float
    daily_notional_usd: float
    pb_quoted_yield_pa: float
    settlement: Literal["cash", "physical"]

    def __post_init__(self):
        """Pass-3 finding (A1/A2): validate input ranges + direction/strike/ko
        alignment. Garbage in here propagates silently through fair_yield and
        yields a numerically-clean but semantically-wrong markup."""
        if self.spot <= 0:
            raise ValueError(f"Quote.spot must be > 0; got {self.spot}")
        if self.tenor_months < 1:
            raise ValueError(f"Quote.tenor_months must be ≥ 1; got {self.tenor_months}")
        if self.daily_notional_usd <= 0:
            raise ValueError(
                f"Quote.daily_notional_usd must be > 0; got {self.daily_notional_usd}"
            )
        if self.doubling_factor < 1.0:
            raise ValueError(
                f"Quote.doubling_factor must be ≥ 1.0; got {self.doubling_factor}"
            )
        if self.strike_pct <= 0 or self.ko_pct <= 0:
            raise ValueError(
                f"strike_pct and ko_pct must be > 0; got {self.strike_pct}/{self.ko_pct}"
            )
        if self.direction == "AQ":
            # AQ: strike < spot (discount), KO > spot (above)
            if not (self.strike_pct < 1.0 < self.ko_pct):
                raise ValueError(
                    f"AQ requires strike_pct < 1.0 < ko_pct; got "
                    f"strike={self.strike_pct}, ko={self.ko_pct}"
                )
        else:  # DQ
            # DQ: strike > spot (premium), KO < spot (below)
            if not (self.ko_pct < 1.0 < self.strike_pct):
                raise ValueError(
                    f"DQ requires ko_pct < 1.0 < strike_pct; got "
                    f"strike={self.strike_pct}, ko={self.ko_pct}"
                )


@dataclass
class Snapshot:
    spot: float
    spot_source: Literal["TV", "IB"]
    spot_timestamp: str
    chain: dict[str, dict[float, dict[str, dict[str, Any]]]]
    chain_source: Literal["IB", "UW"]
    chain_timestamps: dict[str, str]
    rv_30d: float
    rv_90d: float
    iv_rank: float
    skew_chain_derived: dict[int, dict[str, float]] = field(default_factory=dict)
    gex_levels: dict[str, float] = field(default_factory=dict)
    gex_by_strike_at_ko: float | None = None
    max_pain_per_expiry: dict[str, float] = field(default_factory=dict)
    max_drawdown_5y: float = -0.50
    atr_14_pct_of_spot: float | None = None
    earnings_date_iso: str | None = None


@dataclass
class Verdict:
    fair_yield_pa: float
    pb_quoted_yield_pa: float
    markup_pp: float
    pb_annual_profit_usd: float
    ko_probability: float
    decision: Literal["REFUSE", "COUNTER", "ACCEPT_IF_MUST"]
    refusal_reasons: list[str]
    breakdown: dict[str, float]
    data_provenance: dict[str, dict[str, Any]]
    levers_to_negotiate: list[dict[str, Any]] = field(default_factory=list)
    # ── Spec §5.1 risk metrics — v2 deferral ─────────────────────
    # The spec defines these but v1 closed-form heuristic doesn't produce
    # percentile-loss distributions. v2 backlog item §11.2 (Monte Carlo)
    # will populate these. Set to float("nan") in v1 with a provenance
    # entry "v2-deferred: requires MC simulation".
    doubling_trigger_probability: float = float("nan")
    max_loss_p5: float = float("nan")
    max_loss_p1: float = float("nan")
    expected_client_pnl: float = float("nan")


# ─── Public API (stubs — implemented in subsequent tasks) ───


def analyze_quote(q: Quote, s: Snapshot, nlv_usd: float | None = None) -> Verdict:
    raise NotImplementedError("Implemented in Task 14")


def optimize_terms(
    q: Quote,
    s: Snapshot,
    sweep: list[str] | None = None,
    nlv_usd: float | None = None,
) -> list[dict[str, Any]]:
    raise NotImplementedError("Implemented in Task 15")


def build_counter_offer_email(
    v: Verdict, q: Quote, target_markup_pp: float = 1.5
) -> dict[str, str]:
    raise NotImplementedError("Implemented in Task 16")


# ─── Internal math (implemented in subsequent tasks) ────────


def _num_observations(tenor_months: int, obs_freq: str) -> int:
    """Number of observation points over tenor."""
    raise NotImplementedError("Implemented in Task 10")
