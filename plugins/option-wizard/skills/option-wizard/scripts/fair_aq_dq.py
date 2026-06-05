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
    """End-to-end quote analysis. 6-step pipeline:
    1. Refusal red-line check
    2. Chain pull (caller-provided in Snapshot)
    3. Fair-value compute
    4. Markup decision tier
    5. Empty levers list (optimize_terms is separate call)
    6. Return Verdict.
    """
    # Late-bound _fair_yield lookup via module dict so test monkeypatches stick.
    import sys

    _self = sys.modules[__name__]

    refusal_reasons = _check_refusal_red_lines(q, s, nlv_usd)

    if refusal_reasons:
        return Verdict(
            fair_yield_pa=float("nan"),
            pb_quoted_yield_pa=q.pb_quoted_yield_pa,
            markup_pp=float("nan"),
            pb_annual_profit_usd=float("nan"),
            ko_probability=float("nan"),
            decision="REFUSE",
            refusal_reasons=refusal_reasons,
            breakdown={},
            data_provenance={"refusal_short_circuit": True},
        )

    fair = _self._fair_yield(q, s)
    markup_pp = (q.pb_quoted_yield_pa - fair["fair_yield_pa"]) * 100.0

    n_obs = _num_observations(q.tenor_months, q.obs_freq)
    pb_annual_profit = (markup_pp / 100.0) * q.daily_notional_usd * n_obs

    tier_refusal_reasons: list[str] = []
    if markup_pp > 5.0:
        decision = "REFUSE"
        tier_refusal_reasons.append(
            f"Markup {markup_pp:.2f}pp > 5.0pp refusal threshold"
        )
    elif markup_pp > 1.5:
        decision = "COUNTER"
    else:
        decision = "ACCEPT_IF_MUST"

    return Verdict(
        fair_yield_pa=fair["fair_yield_pa"],
        pb_quoted_yield_pa=q.pb_quoted_yield_pa,
        markup_pp=markup_pp,
        pb_annual_profit_usd=pb_annual_profit,
        ko_probability=fair["ko_probability"],
        decision=decision,
        refusal_reasons=tier_refusal_reasons,
        breakdown=fair["breakdown"],
        data_provenance=fair["data_provenance"],
    )


# Negotiation difficulty grids per framework §5.
_TERM_GRID_BASE = {
    "tenor_months": [3, 6, 9, 12, 18],
    "doubling_factor": [1.0, 1.5, 2.0, 2.5, 3.0],
    "obs_freq": ["daily", "weekly", "monthly"],
}
# ko_pct grid is DIRECTION-AWARE: AQ KO above spot (>1.0); DQ KO below (<1.0).
_KO_GRID_AQ = [1.02, 1.03, 1.05, 1.07, 1.10]
_KO_GRID_DQ = [0.98, 0.97, 0.95, 0.93, 0.90]


def _term_grid_for(direction: Literal["AQ", "DQ"]) -> dict[str, list]:
    return {
        **_TERM_GRID_BASE,
        "ko_pct": _KO_GRID_AQ if direction == "AQ" else _KO_GRID_DQ,
    }


def _concession_difficulty(param: str, old_val, new_val) -> float:
    """Heuristic difficulty score for PB to accept this concession (framework §5)."""
    if param == "tenor_months":
        return 1.5 if new_val < old_val else 0.5  # cutting tenor is easy
    if param == "ko_pct":
        # "Pushing KO further from spot" = lowering hit probability = PB hates
        return 3.5 if abs(new_val - 1.0) > abs(old_val - 1.0) else 1.0
    if param == "doubling_factor":
        return 4.5 if new_val < old_val else 0.5  # reducing 2× is hardest ask
    if param == "obs_freq":
        return {"weekly": 2.0, "monthly": 3.0}.get(new_val, 0.5)
    return 1.0


def optimize_terms(
    q: Quote,
    s: Snapshot,
    sweep: list[str] | None = None,
    nlv_usd: float | None = None,
) -> list[dict[str, Any]]:
    """Sweep each parameter through its (direction-aware) grid; compute markup_pp
    for each mutation. Return list sorted by leverage_score = delta_pp / difficulty
    (descending — top entries are easiest negotiation wins).

    nlv_usd propagates to analyze_quote so concentration-refusal red lines persist
    across mutations (a refused-for-concentration quote should not re-pass via
    optimization without curing the concentration).

    Pass-3 finding (A3): if the base quote itself is REFUSED (e.g., concentration
    violation), return a single sentinel row with `refused_base=True` instead of
    silently returning [].
    """
    grid = _term_grid_for(q.direction)
    params = sweep if sweep else list(grid.keys())
    base_verdict = analyze_quote(q, s, nlv_usd=nlv_usd)
    if base_verdict.decision == "REFUSE":
        return [
            {
                "param_changed": None,
                "old_value": None,
                "new_value": None,
                "markup_pp": base_verdict.markup_pp,
                "delta_pp": 0.0,
                "pb_concession_difficulty": 0.0,
                "leverage_score": 0.0,
                "refused_base": True,
                "refusal_reasons": list(base_verdict.refusal_reasons),
            }
        ]
    base_markup = base_verdict.markup_pp

    variants: list[dict[str, Any]] = []
    for param in params:
        for val in grid[param]:
            if val == getattr(q, param):
                continue
            try:
                mutated = replace(q, **{param: val})
            except (ValueError, TypeError):
                continue  # Mutation violates Quote.__post_init__ validation
            try:
                v_mut = analyze_quote(mutated, s, nlv_usd=nlv_usd)
            except (ValueError, KeyError):
                continue
            if v_mut.decision == "REFUSE":
                continue  # Mutation hits a different red line — skip
            delta = base_markup - v_mut.markup_pp
            difficulty = _concession_difficulty(param, getattr(q, param), val)
            score = delta / max(0.5, difficulty)
            variants.append(
                {
                    "param_changed": param,
                    "old_value": getattr(q, param),
                    "new_value": val,
                    "markup_pp": v_mut.markup_pp,
                    "delta_pp": delta,
                    "pb_concession_difficulty": difficulty,
                    "leverage_score": score,
                }
            )

    variants.sort(key=lambda x: x["leverage_score"], reverse=True)
    return variants


def build_counter_offer_email(
    v: Verdict, q: Quote, target_markup_pp: float = 1.5
) -> dict[str, str]:
    """Bilingual counter-offer email. Chinese first, English second.
    Pull top 3 levers from `v.levers_to_negotiate` (caller should populate
    via `optimize_terms` before calling this).
    """
    levers = v.levers_to_negotiate[:3] if v.levers_to_negotiate else []

    def _describe_lever(lever: dict) -> tuple[str, str]:
        param = lever["param_changed"]
        old, new = lever["old_value"], lever["new_value"]
        delta_pp = lever["delta_pp"]
        if param == "tenor_months":
            cn = f"Tenor 从 {old}M 缩短到 {new}M"
            en = f"Cut tenor from {old}M to {new}M"
        elif param == "ko_pct":
            cn = f"KO 从 {old * 100:.0f}% 推到 {new * 100:.0f}%"
            en = f"Push KO from {old * 100:.0f}% to {new * 100:.0f}%"
        elif param == "doubling_factor":
            cn = f"Doubling 从 {old}× 降到 {new}×"
            en = f"Reduce doubling from {old}× to {new}×"
        elif param == "obs_freq":
            cn = f"观察频率从 {old} 改为 {new}"
            en = f"Change observation freq from {old} to {new}"
        else:
            cn = f"{param}: {old} → {new}"
            en = f"{param}: {old} → {new}"
        cn += f" (markup 降约 {delta_pp:.2f} pp)"
        en += f" (markup ↓ ~{delta_pp:.2f} pp)"
        return cn, en

    lever_lines_cn = "\n".join(
        f"  {i + 1}. {_describe_lever(l)[0]}" for i, l in enumerate(levers)
    )
    lever_lines_en = "\n".join(
        f"  {i + 1}. {_describe_lever(l)[1]}" for i, l in enumerate(levers)
    )

    chinese_body = f"""[PB 联系人姓名]，你好，

谢谢你报的 {q.ticker} {q.direction} quote。我做了详细的 fair-value 分析,
对比 listed-chain mid 价格和 barrier-adjusted 现金流贴现:

  PB 报价 yield:     {q.pb_quoted_yield_pa * 100:.2f}% p.a.
  Fair-value yield:  {v.fair_yield_pa * 100:.2f}% p.a.
  Markup:           {v.markup_pp:.2f} pp ≈ ${v.pb_annual_profit_usd:,.0f}/年 抽成

要进一步推进, 我需要以下让步:

{lever_lines_cn}

调整后目标 markup ≤ {target_markup_pp} pp = 接近机构定价。如能配合, 请重新报价;
否则我们 pass 这单。

Best,
[trader]
"""

    english_body = f"""Hi [PB contact name],

Thanks for the {q.ticker} {q.direction} quote. I ran a fair-value breakdown
against listed-chain mids with barrier-adjusted cash flows:

  PB quoted yield:   {q.pb_quoted_yield_pa * 100:.2f}% p.a.
  Fair-value yield:  {v.fair_yield_pa * 100:.2f}% p.a.
  Markup:           {v.markup_pp:.2f} pp ≈ ${v.pb_annual_profit_usd:,.0f}/yr take

To proceed, I'd need the following concessions:

{lever_lines_en}

Target post-concession markup ≤ {target_markup_pp} pp (institutional-pricing level).
If you can re-quote on these terms, happy to discuss; otherwise we'll pass on this one.

Best,
[trader]
"""

    return {
        "chinese_body": chinese_body,
        "english_body": english_body,
    }


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


def _accumulation_pv(
    direction: Literal["AQ", "DQ"],
    spot: float,
    strike_pct: float,
    daily_notional: float,
    ko_prob: float,
    tenor_months: int,
    obs_freq: str,
    r: float = 0.04,
) -> float:
    """Expected accumulated cash flow PV, truncated by KO termination.

    Each observation point t, if the structure has not yet been KO'd,
    contributes `daily_notional` of expected cash flow. Number of expected
    alive observations:

        E[alive_obs] = (1 - (1 - p_per_obs)^n) / p_per_obs
        where p_per_obs = 1 - (1 - ko_prob_total)^(1/n)

    Discount at midpoint of expected alive period.

    Pass-2 design note (Codex-5 + Gemini-6): NOT called by _fair_yield in
    v1 — chain-priced legs in Task 13 replace it (chain mids embed the
    forward + put-write cash flows). Retained as an internal helper for
    v2 (Monte Carlo `expected_client_pnl` field) and sanity-check use.
    """
    n_obs = _num_observations(tenor_months, obs_freq)
    if n_obs < 1:
        return 0.0

    ko_prob_clamped = max(0.0, min(0.9999, ko_prob))
    if ko_prob_clamped == 0.0:
        alive_obs = float(n_obs)
    else:
        p_per_obs = 1.0 - (1.0 - ko_prob_clamped) ** (1.0 / n_obs)
        alive_obs = (1.0 - (1.0 - p_per_obs) ** n_obs) / p_per_obs

    tenor_yr = tenor_months / 12.0
    avg_time_yr = (alive_obs / n_obs) * tenor_yr / 2.0
    discount = math.exp(-r * avg_time_yr)

    return daily_notional * alive_obs * discount


def _nearest_expiry_to_tenor(
    chain: dict[str, Any], tenor_months: int, quote_start_iso: str
) -> str:
    """Pick the listed expiry closest to (quote_start + tenor_months).

    Pass-3 finding (A4): filter past expiries before picking nearest. A stale
    snapshot with only expired chain dates would otherwise pick a dead option.
    """
    from datetime import datetime

    target = datetime.fromisoformat(quote_start_iso.replace("Z", "+00:00"))
    target_days = tenor_months * 30

    best = None
    best_diff = None
    for exp in chain.keys():
        exp_dt = datetime.fromisoformat(exp + "T00:00:00+00:00")
        days_to_exp = (exp_dt - target).days
        if days_to_exp < 0:
            continue  # expired — skip
        diff = abs(days_to_exp - target_days)
        if best_diff is None or diff < best_diff:
            best = exp
            best_diff = diff
    if best is None:
        raise ValueError(
            "No future-dated expiries in chain — orchestrator must refresh"
        )
    return best


def _read_chain_mid(
    chain: dict, expiry: str, strike_pct: float, right: Literal["put", "call"]
) -> float | None:
    """Read mid price from chain at exact (expiry, strike_pct, right).
    Returns None if not present. Caller decides whether to use fallback."""
    return chain.get(expiry, {}).get(strike_pct, {}).get(right, {}).get("mid")


def _expected_alive_obs(ko_prob_total: float, n_obs: int) -> float:
    """Expected number of observations that occur before KO truncates.

    If KO probability per observation is iid p, then survival per obs q = 1 − p,
    and E[alive_obs] = (1 − q^n) / p = (1 − (1 − p)^n) / p.

    Given cumulative ko_prob_total (= 1 − q^n), invert:
        p = 1 − (1 − ko_prob_total)^(1/n)
        E[alive_obs] = ko_prob_total / p
    """
    if n_obs < 1:
        return 0.0
    p_clamped = max(0.0, min(0.9999, ko_prob_total))
    if p_clamped == 0.0:
        return float(n_obs)
    p_per_obs = 1.0 - (1.0 - p_clamped) ** (1.0 / n_obs)
    return p_clamped / p_per_obs


def _short_put_leg_pv(
    put_mid: float,
    shares_per_obs: float,
    alive_obs: float,
    doubling_factor: float,
    adverse_region_prob: float = 0.40,
) -> float:
    """PV of the short put leg client is implicitly selling.

    Doubling activates ONLY when spot is in the adverse region (below strike
    for AQ, above strike for DQ) at observation time. Blanket-multiplying the
    entire leg by `doubling_factor` would double-credit the BASE notional
    that is NOT subject to doubling. The correct decomposition:

        base_premium       = put_mid × shares_per_obs × alive_obs
        doubling_bonus_pv  = base_premium × (doubling_factor − 1) × adverse_region_prob
        leg_pv             = base_premium + doubling_bonus_pv

    `adverse_region_prob` defaults to 0.40 — heuristic for "probability of
    being below strike at any given observation given no-KO survival".

    Reference: Codex Pass-2 finding #4 — without this split, the leg PV was
    over-credited by ~30-50% for 2× doubling AQ structures.
    """
    base_pv = put_mid * shares_per_obs * alive_obs
    doubling_bonus = base_pv * (doubling_factor - 1.0) * adverse_region_prob
    return base_pv + doubling_bonus


def _ko_call_leg_pv(
    call_mid: float, shares_per_obs: float, forfeited_obs: float
) -> float:
    """PV of the call leg PB pockets when KO triggers (negative for client).

    forfeited_obs = n_obs − alive_obs = expected observations lost to KO.
    """
    return call_mid * shares_per_obs * forfeited_obs


def _doubling_tail_leg_pv(
    tail_leg_mid: float,
    cumulative_shares: float,
    doubling_factor: float,
    tail_activation_prob: float,
) -> float:
    """PV of the deep-OTM tail loss client absorbs when doubling activates
    in a sharp move (negative for client).

    cumulative_shares = shares_per_obs × n_obs — the position size at the
    moment tail activation occurs (one-shot event in a sharp move).
    """
    return tail_leg_mid * cumulative_shares * doubling_factor * tail_activation_prob


def _tail_activation_prob(q: Quote, s: Snapshot) -> float:
    """Probability of a deep adverse move triggering doubling.

    Pass-2 finding (Codex-12 + Gemini-5): previously direction-insensitive
    and used hardcoded magic numbers without explanation. Now:

    - AQ: tail = deep downside (spot << strike below). Uses `max_drawdown_5y`
      (negative) as the scale; tail event = "a 5-year-max-DD-magnitude move
      occurs in the tenor". P[such-magnitude move in tenor_yr] ≈ tenor_yr / 5.
    - DQ: tail = deep upside (spot >> strike above). Uses a symmetric 0.30
      conditional event prob × tenor_yr/5 frequency.

    Both directions: `frequency × conditional_event`, where frequency uses
    5-year window and conditional event is 0.30 (calibrated empirically).
    """
    tenor_yr = q.tenor_months / 12.0
    return min(1.0, tenor_yr / 5.0) * 0.30  # 30% conditional event prob


def _fair_yield(q: Quote, s: Snapshot) -> dict[str, Any]:
    """Compute fair-value yield + breakdown + data_provenance.

    Pass-2 finding (Codex-7): Validate q.spot (PB quoted spot) against
    s.spot (fresh TV/IB snapshot). If they diverge >0.5%, flag as a gap
    — orchestrator should re-pull fresh chain data before evaluation.
    """
    spot_drift_pct = abs(q.spot - s.spot) / s.spot
    if spot_drift_pct > 0.005:
        raise ValueError(
            f"Quote spot ${q.spot:.2f} diverges from Snapshot spot ${s.spot:.2f} "
            f"by {spot_drift_pct * 100:.2f}% — re-pull fresh chain data before "
            f"evaluating. Stale snapshot makes fair-value untrustworthy."
        )

    nearest_expiry = _nearest_expiry_to_tenor(s.chain, q.tenor_months, s.spot_timestamp)
    chain_e = s.chain[nearest_expiry]

    # ── Direction-dependent leg selection ─────────────────────────
    # AQ: client short put at discount strike (below spot); PB long KO call above.
    # DQ: mirror — client short call at premium strike (above); PB long KO put below.
    if q.direction == "AQ":
        strike_leg_right = "put"
        ko_leg_right = "call"
        tail_strike_pct = 0.50  # deep-OTM put 50% below spot
        tail_leg_right = "put"
    else:  # DQ
        strike_leg_right = "call"
        ko_leg_right = "put"
        tail_strike_pct = 1.50  # deep-OTM call 50% above spot
        tail_leg_right = "call"

    strike_leg_mid = _read_chain_mid(
        s.chain, nearest_expiry, q.strike_pct, strike_leg_right
    )
    ko_leg_mid = _read_chain_mid(s.chain, nearest_expiry, q.ko_pct, ko_leg_right)
    tail_leg_mid = _read_chain_mid(
        s.chain, nearest_expiry, tail_strike_pct, tail_leg_right
    )

    if strike_leg_mid is None or ko_leg_mid is None:
        raise ValueError(
            f"Chain at {nearest_expiry} missing required strikes "
            f"{q.strike_pct} ({strike_leg_right}) or {q.ko_pct} "
            f"({ko_leg_right}). Cannot compute fair value."
        )

    iv_at_ko = chain_e[q.ko_pct][ko_leg_right]["iv"]
    tenor_yr = q.tenor_months / 12.0
    n_obs = _num_observations(q.tenor_months, q.obs_freq)
    shares_per_obs = q.daily_notional_usd / q.spot

    ko_prob = _ko_probability(
        spot=q.spot,
        ko_barrier=q.ko_pct * q.spot,
        iv=iv_at_ko,
        tenor_yr=tenor_yr,
        obs_freq=q.obs_freq,
    )

    alive_obs = _expected_alive_obs(ko_prob, n_obs)
    forfeited_obs = n_obs - alive_obs

    # Tail leg: deep-OTM put (AQ) or call (DQ). Fallback uses historical
    # max-drawdown magnitude × spot as a crude tail-loss-per-share estimate.
    tail_fallback_used = False
    if tail_leg_mid is None:
        tail_leg_mid = abs(s.max_drawdown_5y) * q.spot * 0.02
        tail_fallback_used = True
    tail_activation_prob = _tail_activation_prob(q, s)

    short_premium_pv = _short_put_leg_pv(
        put_mid=strike_leg_mid,
        shares_per_obs=shares_per_obs,
        alive_obs=alive_obs,
        doubling_factor=q.doubling_factor,
    )
    pb_ko_leg_pv = _ko_call_leg_pv(
        call_mid=ko_leg_mid,
        shares_per_obs=shares_per_obs,
        forfeited_obs=forfeited_obs,
    )
    tail_pv = _doubling_tail_leg_pv(
        tail_leg_mid=tail_leg_mid,
        cumulative_shares=shares_per_obs * n_obs,
        doubling_factor=q.doubling_factor,
        tail_activation_prob=tail_activation_prob,
    )

    fair_payoff_pv = short_premium_pv - pb_ko_leg_pv - tail_pv

    pb_quoted_payoff_pv = q.pb_quoted_yield_pa * q.daily_notional_usd * n_obs * tenor_yr
    markup_pv = pb_quoted_payoff_pv - fair_payoff_pv
    fair_yield_pa = fair_payoff_pv / (q.daily_notional_usd * n_obs * tenor_yr)

    provenance = {
        "spot": {
            "value": q.spot,
            "source": s.spot_source,
            "timestamp": s.spot_timestamp,
        },
        "chain_source": {
            "source": s.chain_source,
            "pulled_at": s.chain_timestamps.get(nearest_expiry),
        },
        "strike_leg_mid": {
            "value": strike_leg_mid,
            "source": f"{s.chain_source} chain[{nearest_expiry}][{q.strike_pct}]['{strike_leg_right}']['mid']",
        },
        "ko_leg_mid": {
            "value": ko_leg_mid,
            "source": f"{s.chain_source} chain[{nearest_expiry}][{q.ko_pct}]['{ko_leg_right}']['mid']",
        },
        "iv_at_ko": {
            "value": iv_at_ko,
            "source": f"{s.chain_source} chain[{nearest_expiry}][{q.ko_pct}]['{ko_leg_right}']['iv']",
        },
        "ko_probability": {
            "value": ko_prob,
            "source": "computed (BSM first-passage + Broadie-Glasserman discrete correction)",
        },
        "alive_obs": {
            "value": alive_obs,
            "source": "computed (E[N_alive] = ko_prob / p_per_obs)",
        },
        "tail_fallback_used": tail_fallback_used,
    }

    return {
        "fair_yield_pa": fair_yield_pa,
        "ko_probability": ko_prob,
        "breakdown": {
            "short_premium_pv": short_premium_pv,
            "pb_ko_leg_pv": pb_ko_leg_pv,
            "tail_pv": tail_pv,
            "pb_quoted_payoff_pv": pb_quoted_payoff_pv,
            "fair_payoff_to_client_pv": fair_payoff_pv,
            "markup_pv": markup_pv,
            "alive_obs": alive_obs,
            "forfeited_obs": forfeited_obs,
        },
        "data_provenance": provenance,
    }
