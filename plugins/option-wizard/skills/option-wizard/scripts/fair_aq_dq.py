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


# ─── Internal math ──────────────────────────────────────────


# Calendar conventions for observation counts.
_OBS_PER_YEAR = {
    "daily": 252,  # trading days
    "weekly": 52,
    "monthly": 12,
}


def _num_observations(tenor_months: int, obs_freq: str) -> int:
    """Number of observation points over the tenor."""
    per_year = _OBS_PER_YEAR[obs_freq]
    return max(1, int(round(per_year * tenor_months / 12.0)))


def _check_refusal_red_lines(q: Quote, s: Snapshot, nlv_usd: float | None) -> list[str]:
    """6 hard refusals per framework §6. Returns list of triggered reason strings.
    Empty list = no red line triggered.
    """
    reasons: list[str] = []

    # 1. doubling >= 3x
    if q.doubling_factor >= 3.0:
        reasons.append(
            f"Doubling factor {q.doubling_factor:.1f}× ≥ 3× — institutional-only territory"
        )

    # 2. AQ + low IV rank
    if q.direction == "AQ" and s.iv_rank < 30.0:
        reasons.append(
            f"AQ with IV rank {s.iv_rank:.0f} < 30 — selling vol when vol is cheap"
        )

    # 3. KO within 1 ATR(14) of spot
    if s.atr_14_pct_of_spot is not None:
        ko_dist_pct = abs(q.ko_pct - 1.0)
        if ko_dist_pct < s.atr_14_pct_of_spot:
            reasons.append(
                f"KO distance {ko_dist_pct * 100:.1f}% < 1×ATR(14) "
                f"{s.atr_14_pct_of_spot * 100:.1f}% — KO virtually guaranteed to trigger"
            )

    # 4. notional > 10% NLV
    if nlv_usd is not None and nlv_usd > 0:
        n_obs = _num_observations(q.tenor_months, q.obs_freq)
        total_notional = q.daily_notional_usd * n_obs
        if total_notional > 0.10 * nlv_usd:
            reasons.append(
                f"Single-name notional ${total_notional:,.0f} > 10% NLV ${nlv_usd:,.0f}"
            )

    # 5. tenor > 18M
    if q.tenor_months > 18:
        reasons.append(
            f"Tenor {q.tenor_months}M > 18M — PB markup grows super-linearly"
        )

    # 6. ER in middle 50% of tenor
    if s.earnings_date_iso is not None:
        er_in_mid = _earnings_in_middle_50pct(
            s.earnings_date_iso, s.spot_timestamp, q.tenor_months
        )
        if er_in_mid:
            reasons.append(
                f"Earnings date {s.earnings_date_iso} in middle 50% of tenor — "
                f"binary event + doubling + KO unmanageable"
            )

    return reasons


def _earnings_in_middle_50pct(
    earnings_iso: str, quote_start_iso: str, tenor_months: int
) -> bool:
    """True if earnings date falls in [25%, 75%] of tenor window."""
    from datetime import datetime

    quote_start = datetime.fromisoformat(quote_start_iso.replace("Z", "+00:00"))
    er = datetime.fromisoformat(earnings_iso + "T00:00:00+00:00")
    tenor_days = tenor_months * 30  # approximate
    days_from_start = (er - quote_start).days
    if days_from_start < 0 or days_from_start > tenor_days:
        return False
    pct = days_from_start / tenor_days
    return 0.25 <= pct <= 0.75


from scipy.stats import norm


# Broadie-Glasserman (1997) discrete-monitoring constant. Derived from the
# Riemann zeta function ζ(1/2). Shifts the effective barrier away from spot
# by `BETA * sigma * sqrt(T/n)` to correct for discrete observation.
BETA_BG = 0.5826


def _ko_probability(
    spot: float, ko_barrier: float, iv: float, tenor_yr: float, obs_freq: str
) -> float:
    """Probability that the underlying touches the KO barrier at some
    observation point during the tenor.

    Continuous-monitoring formula: reflection principle with zero drift
    (Merton 1973). For upper barrier (AQ case, ko_barrier > spot):

        P[hit] = 2 * N(-|log(B/S)| / (sigma * sqrt(T)))

    Discrete-monitoring correction (Broadie-Glasserman 1997):

        effective_barrier = ko_barrier * exp(BETA_BG * sigma * sqrt(T/n))
                              for upper barrier (shift AWAY from spot, ↓ hit prob)
        effective_barrier = ko_barrier * exp(-BETA_BG * sigma * sqrt(T/n))
                              for lower barrier

    Zero drift simplification: AQ/DQ tenors are short enough (≤18M) that
    (r − q − sigma²/2) × T is dominated by sigma × sqrt(T). Errors well
    below ±2 pp on resulting markup estimate.
    """
    if tenor_yr <= 0 or iv <= 0:
        return 0.0

    n_obs = _OBS_PER_YEAR[obs_freq] * tenor_yr
    if n_obs < 1:
        n_obs = 1

    upper_barrier = ko_barrier > spot
    shift_magnitude = BETA_BG * iv * math.sqrt(tenor_yr / n_obs)

    if upper_barrier:
        effective_barrier = ko_barrier * math.exp(shift_magnitude)
    else:
        effective_barrier = ko_barrier * math.exp(-shift_magnitude)

    log_ratio = math.log(effective_barrier / spot)
    d = -abs(log_ratio) / (iv * math.sqrt(tenor_yr))
    p_hit = 2.0 * norm.cdf(d)
    return max(0.0, min(1.0, p_hit))
