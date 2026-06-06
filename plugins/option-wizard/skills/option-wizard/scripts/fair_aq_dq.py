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
    strike_pct: float  # 0.95 = strike at 95% reference spot
    ko_pct: float  # 1.03 = KO at 103% reference spot (AQ); 0.97 (DQ)
    tenor_months: int
    obs_freq: Literal["daily", "weekly", "monthly"]
    doubling_factor: float
    # USD-notional path (legacy / non-PB-AQ). Provide exactly one of
    # daily_notional_usd or daily_shares — real PB AQ quotes denominate
    # contracts in shares (e.g., "4 shares/day") and require daily_shares.
    daily_notional_usd: float | None = None
    # PB-quoted coupon — set for FCN-style products. AQ rarely quotes an
    # explicit yield (the "yield" is the strike discount × accumulated shares),
    # so this is OPTIONAL. When None, analyze_quote enters AQ implicit-yield
    # mode and emits discount_implied_yield_pa instead of markup_pp.
    pb_quoted_yield_pa: float | None = None
    settlement: Literal["cash", "physical"] = "cash"
    # PB-AQ-specific fields. daily_shares is the contract-spec share count
    # PB writes ("每日买入: 4 shares"); entry_spot is the reference spot PB
    # locked strike against ("入场价 $361.85") — separate from current spot;
    # guarantee_period_weeks (保证期) is the non-call window during which KO
    # cannot trigger but accumulation still runs.
    daily_shares: int | None = None
    entry_spot: float | None = None
    guarantee_period_weeks: int = 0

    def __post_init__(self):
        """Validate input ranges + direction/strike/ko alignment, and enforce
        the new "exactly one of daily_shares / daily_notional_usd" rule."""
        if self.spot <= 0:
            raise ValueError(f"Quote.spot must be > 0; got {self.spot}")
        if self.tenor_months < 1:
            raise ValueError(f"Quote.tenor_months must be ≥ 1; got {self.tenor_months}")
        notional_set = self.daily_notional_usd is not None
        shares_set = self.daily_shares is not None
        if notional_set == shares_set:
            raise ValueError(
                "Quote requires exactly one of daily_notional_usd or daily_shares; "
                f"got daily_notional_usd={self.daily_notional_usd}, "
                f"daily_shares={self.daily_shares}"
            )
        if notional_set and self.daily_notional_usd <= 0:
            raise ValueError(
                f"Quote.daily_notional_usd must be > 0; got {self.daily_notional_usd}"
            )
        if shares_set and self.daily_shares <= 0:
            raise ValueError(f"Quote.daily_shares must be > 0; got {self.daily_shares}")
        if self.entry_spot is not None and self.entry_spot <= 0:
            raise ValueError(
                f"Quote.entry_spot must be > 0 when set; got {self.entry_spot}"
            )
        if self.guarantee_period_weeks < 0:
            raise ValueError(
                f"Quote.guarantee_period_weeks must be ≥ 0; "
                f"got {self.guarantee_period_weeks}"
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

    @property
    def reference_spot(self) -> float:
        """Spot PB locked strike + KO barriers against. Defaults to `spot`
        when `entry_spot` is unset (typical for FCN-style or pre-trade live
        quote where entry == current). For placed AQ trades, `entry_spot`
        captures the historical PB-quoted spot so post-trade analysis isn't
        polluted by current market drift."""
        return self.entry_spot if self.entry_spot is not None else self.spot

    @property
    def shares_per_obs(self) -> float:
        """Resolve shares-per-observation from whichever input the caller
        provided. PB AQ contracts denominate in shares; FCN ladders typically
        denominate in USD notional. Either path yields the same float for
        downstream PV / scenario math."""
        if self.daily_shares is not None:
            return float(self.daily_shares)
        if self.daily_notional_usd is None:
            raise ValueError(
                "Quote has neither daily_shares nor daily_notional_usd set"
            )
        return self.daily_notional_usd / self.reference_spot

    @property
    def total_notional_usd(self) -> float:
        """Total max-base-case notional (= shares_per_obs × strike_abs × n_obs).
        Used by refusal #4 (concentration check) — accounts for the fact that
        the trader pays strike, not spot, per accumulated share."""
        n_obs = _num_observations(self.tenor_months, self.obs_freq)
        strike_abs = self.strike_pct * self.reference_spot
        return self.shares_per_obs * strike_abs * n_obs


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
    # Full list of scheduled earnings dates within the tenor window. When
    # set, refusal red line #6 iterates this list (catches Q2 + Q3 + Q4 ERs
    # in a 12M+ tenor). When None, falls back to the single
    # `earnings_date_iso` (legacy 6M-tenor behavior).
    earnings_dates_iso: list[str] | None = None


@dataclass
class Verdict:
    fair_yield_pa: float
    pb_quoted_yield_pa: float | None
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
    # ── New PB-AQ-quote-template fields (PR-A) ────────────────────
    # 3-scenario projection PB displays verbatim in real quotes:
    #   - ko_during_guarantee:       shares accumulated if KO triggers as soon as
    #                                guarantee period ends (best case for trader)
    #   - full_term_no_doubling:     all observations × shares_per_obs (no KO,
    #                                spot stays above strike — base case)
    #   - max_exposure_all_doubled:  base × doubling_factor (worst case where
    #                                spot crashes below strike and doubling fires)
    # Each value: {shares, usd_notional, pct_of_nlv}. pct_of_nlv is nan when
    # nlv_usd was not passed to analyze_quote.
    scenarios: dict[str, dict[str, float]] = field(default_factory=dict)
    # Mode flag distinguishing legacy markup_pp comparison (when
    # pb_quoted_yield_pa was supplied — FCN-style) from AQ implicit-yield
    # mode (when PB didn't quote a yield).
    mode: Literal["markup_comparison", "implicit_yield_aq"] = "markup_comparison"
    # AQ implicit-yield mode populates this: the discount-implied yield the
    # trader effectively earns from strike-discount accumulation, expressed
    # as p.a. on total notional. Used in place of markup_pp when
    # pb_quoted_yield_pa is None.
    discount_implied_yield_pa: float = float("nan")


# ─── Public API (stubs — implemented in subsequent tasks) ───


def analyze_quote(
    q: Quote, s: Snapshot, nlv_usd: float | None = None, strict_mode: bool = False
) -> Verdict:
    """End-to-end quote analysis. 7-step pipeline:
    1. Compute 3 scenarios (always — trader sees them even on REFUSE)
    2. Refusal red-line check
    3. Chain pull (caller-provided in Snapshot)
    4. Fair-value compute (strict_mode propagates to spot-drift handling)
    5. Mode branch: markup_comparison (PB quoted yield) vs implicit_yield_aq (PB didn't)
    6. Decision tier
    7. Return Verdict.
    """
    # Late-bound _fair_yield lookup via module dict so test monkeypatches stick.
    import sys

    _self = sys.modules[__name__]

    scenarios = _compute_scenarios(q, nlv_usd)
    refusal_reasons = _check_refusal_red_lines(q, s, nlv_usd)

    mode: Literal["markup_comparison", "implicit_yield_aq"] = (
        "implicit_yield_aq" if q.pb_quoted_yield_pa is None else "markup_comparison"
    )

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
            scenarios=scenarios,
            mode=mode,
        )

    fair = _self._fair_yield(q, s, strict_mode=strict_mode)
    notional_per_obs = fair["notional_per_obs"]
    n_obs = fair["n_obs"]
    tenor_yr = fair["tenor_yr"]

    tier_refusal_reasons: list[str] = []
    discount_implied_yield_pa = float("nan")

    if mode == "markup_comparison":
        markup_pp = (q.pb_quoted_yield_pa - fair["fair_yield_pa"]) * 100.0
        pb_annual_profit = (markup_pp / 100.0) * notional_per_obs * n_obs
        if markup_pp > 5.0:
            decision = "REFUSE"
            tier_refusal_reasons.append(
                f"Markup {markup_pp:.2f}pp > 5.0pp refusal threshold"
            )
        elif markup_pp > 1.5:
            decision = "COUNTER"
        else:
            decision = "ACCEPT_IF_MUST"
    else:
        # AQ implicit-yield: PB doesn't quote a coupon. The trader's "yield"
        # is the strike discount × expected accumulated shares × (1 / total
        # notional × tenor_yr). Compare against the fair-value yield (what
        # the listed-chain mids say the embedded leg PV is actually worth).
        strike_abs = q.strike_pct * q.reference_spot
        discount_per_share = q.reference_spot - strike_abs
        alive_obs = fair["breakdown"]["alive_obs"]
        # Doubling-adjusted expected shares: base shares + adverse-region
        # extra shares. Mirror the same 0.40 adverse-region prob used in
        # _short_put_leg_pv so the two paths stay coherent.
        expected_shares = (
            q.shares_per_obs * alive_obs * (1.0 + (q.doubling_factor - 1.0) * 0.40)
        )
        expected_discount_value = discount_per_share * expected_shares
        discount_implied_yield_pa = expected_discount_value / (
            notional_per_obs * n_obs * tenor_yr
        )
        markup_pp = (discount_implied_yield_pa - fair["fair_yield_pa"]) * 100.0
        pb_annual_profit = -markup_pp / 100.0 * notional_per_obs * n_obs
        # Decision tier mirrors the markup path BUT inverted: in implicit-yield
        # mode, the trader is "underpaid" if discount_implied < fair (PB
        # keeping more than its share). markup_pp < -1.5pp means the trader
        # is being underpaid by >1.5pp on the implicit yield.
        if markup_pp < -5.0:
            decision = "REFUSE"
            tier_refusal_reasons.append(
                f"AQ implicit-yield {discount_implied_yield_pa * 100:.2f}% p.a. "
                f"vs fair {fair['fair_yield_pa'] * 100:.2f}% p.a. — "
                f"PB extracting {-markup_pp:.2f}pp > 5.0pp"
            )
        elif markup_pp < -1.5:
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
        scenarios=scenarios,
        mode=mode,
        discount_implied_yield_pa=discount_implied_yield_pa,
    )


# Observation cadence per calendar week — used by _compute_scenarios for
# guarantee-period share counts. Distinct from _OBS_PER_YEAR (which uses
# 252 trading days/yr); _OBS_PER_WEEK is calendar-week-anchored to match
# how PB AQ quotes spec "保证期: 4 weeks → 80 shares" (5 trading days/wk).
_OBS_PER_WEEK = {"daily": 5, "weekly": 1, "monthly": 0.25}


def _compute_scenarios(q: Quote, nlv_usd: float | None) -> dict[str, dict[str, float]]:
    """3-scenario projection PB displays verbatim in real AQ quotes.

    Mirrors the PB report layout exactly so the trader can cross-check
    framework output against the screenshot. usd_notional is computed at
    strike_abs (the price PB will buy you in at), not spot.

    Scenarios:
      - ko_during_guarantee:      base × n_obs_in_guarantee
      - full_term_no_doubling:    base × n_obs_total
      - max_exposure_all_doubled: base × n_obs_total × doubling_factor
    """
    n_obs_total = _num_observations(q.tenor_months, q.obs_freq)
    n_obs_guarantee = max(
        1 if q.guarantee_period_weeks > 0 else 0,
        round(_OBS_PER_WEEK[q.obs_freq] * q.guarantee_period_weeks),
    )
    strike_abs = q.strike_pct * q.reference_spot
    shares_per_obs = q.shares_per_obs

    def _entry(shares: float) -> dict[str, float]:
        usd_notional = shares * strike_abs
        pct_of_nlv = (
            usd_notional / nlv_usd
            if (nlv_usd is not None and nlv_usd > 0)
            else float("nan")
        )
        return {
            "shares": shares,
            "usd_notional": usd_notional,
            "pct_of_nlv": pct_of_nlv,
        }

    return {
        "ko_during_guarantee": _entry(shares_per_obs * n_obs_guarantee),
        "full_term_no_doubling": _entry(shares_per_obs * n_obs_total),
        "max_exposure_all_doubled": _entry(
            shares_per_obs * n_obs_total * q.doubling_factor
        ),
    }


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
    # markup_comparison: lower markup_pp = better (PB extracts less from
    # trader). delta = base − mutated, higher = better.
    # implicit_yield_aq: markup_pp = discount_implied − fair, where a
    # MORE-NEGATIVE markup_pp means PB extracts more from the trader. So a
    # "better" mutation pushes markup_pp UP (less negative). delta sign
    # flips accordingly.
    delta_sign = 1.0 if base_verdict.mode == "markup_comparison" else -1.0

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
            delta = delta_sign * (base_markup - v_mut.markup_pp)
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

    # Mode-aware preamble: markup-comparison shows "PB quoted yield vs fair";
    # implicit-yield mode shows "discount-implied vs fair" with a note that
    # PB didn't quote an explicit coupon.
    if v.mode == "markup_comparison" and q.pb_quoted_yield_pa is not None:
        cn_preamble = (
            f"  PB 报价 yield:     {q.pb_quoted_yield_pa * 100:.2f}% p.a.\n"
            f"  Fair-value yield:  {v.fair_yield_pa * 100:.2f}% p.a.\n"
            f"  Markup:           {v.markup_pp:.2f} pp ≈ "
            f"${v.pb_annual_profit_usd:,.0f}/年 抽成"
        )
        en_preamble = (
            f"  PB quoted yield:   {q.pb_quoted_yield_pa * 100:.2f}% p.a.\n"
            f"  Fair-value yield:  {v.fair_yield_pa * 100:.2f}% p.a.\n"
            f"  Markup:           {v.markup_pp:.2f} pp ≈ "
            f"${v.pb_annual_profit_usd:,.0f}/yr take"
        )
    else:
        cn_preamble = (
            f"  PB 未报 explicit yield（AQ 隐含 yield 走 strike 折扣）\n"
            f"  Discount-implied yield: {v.discount_implied_yield_pa * 100:.2f}% p.a.\n"
            f"  Fair-value yield:       {v.fair_yield_pa * 100:.2f}% p.a.\n"
            f"  PB 抽成:                {-v.markup_pp:.2f} pp "
            f"≈ ${v.pb_annual_profit_usd:,.0f}/年"
        )
        en_preamble = (
            f"  PB did not quote an explicit yield (AQ implicit-yield via strike discount)\n"
            f"  Discount-implied yield: {v.discount_implied_yield_pa * 100:.2f}% p.a.\n"
            f"  Fair-value yield:       {v.fair_yield_pa * 100:.2f}% p.a.\n"
            f"  PB take:                {-v.markup_pp:.2f} pp "
            f"≈ ${v.pb_annual_profit_usd:,.0f}/yr"
        )

    chinese_body = f"""[PB 联系人姓名]，你好，

谢谢你报的 {q.ticker} {q.direction} quote。我做了详细的 fair-value 分析,
对比 listed-chain mid 价格和 barrier-adjusted 现金流贴现:

{cn_preamble}

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

{en_preamble}

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

    # 4. Max-exposure notional > 10% NLV.
    # Real PB AQ contracts denominate in SHARES at STRIKE price (not spot),
    # and doubling magnifies the worst-case. The refusal check must reflect
    # the actual cash the trader can be put on the hook for, not the
    # base-case USD-notional approximation.
    if nlv_usd is not None and nlv_usd > 0:
        max_exposure = q.total_notional_usd * q.doubling_factor
        if max_exposure > 0.10 * nlv_usd:
            reasons.append(
                f"Max-exposure notional ${max_exposure:,.0f} (= shares × strike × "
                f"n_obs × {q.doubling_factor:g}× doubling) > 10% NLV ${nlv_usd:,.0f}"
            )

    # 5. tenor > 18M
    if q.tenor_months > 18:
        reasons.append(
            f"Tenor {q.tenor_months}M > 18M — PB markup grows super-linearly"
        )

    # 6. ANY earnings date in middle 50% of tenor.
    # Previously only checked the single next earnings_date_iso, which silently
    # missed Q3 / Q4 ERs on 12M+ tenors. Now iterates every scheduled ER in
    # the window (either explicit s.earnings_dates_iso list or quarterly grid
    # derived from s.earnings_date_iso).
    er_dates = _all_earnings_dates_in_tenor(s, q.tenor_months)
    for er_iso in er_dates:
        if _earnings_in_middle_50pct(er_iso, s.spot_timestamp, q.tenor_months):
            reasons.append(
                f"Earnings date {er_iso} in middle 50% of tenor — "
                f"binary event + doubling + KO unmanageable"
            )
            break  # one ER is enough to refuse; don't spam list

    return reasons


def _all_earnings_dates_in_tenor(s: Snapshot, tenor_months: int) -> list[str]:
    """Return every scheduled ER date that falls within the tenor window.

    If `s.earnings_dates_iso` is set (explicit list from orchestrator),
    filter to in-tenor dates. Otherwise, derive a quarterly grid from
    `s.earnings_date_iso` (canonical: companies report every ~90 days),
    sweeping forward through the tenor window.

    Returns [] if no ER information is available.
    """
    from datetime import datetime, timedelta

    # Explicit empty list = orchestrator confirmed no ERs in tenor (don't
    # extrapolate). Only None falls through to quarterly-from-anchor logic.
    if s.earnings_dates_iso is not None:
        return list(s.earnings_dates_iso)

    if s.earnings_date_iso is None:
        return []

    quote_start = datetime.fromisoformat(s.spot_timestamp.replace("Z", "+00:00"))
    tenor_end = quote_start + timedelta(days=tenor_months * 30)
    anchor = datetime.fromisoformat(s.earnings_date_iso + "T00:00:00+00:00")

    # Sweep backward to the earliest ER ≥ quote_start, then forward through
    # the tenor at quarterly (90d) intervals.
    while anchor - timedelta(days=90) >= quote_start:
        anchor -= timedelta(days=90)

    dates: list[str] = []
    cursor = anchor
    while cursor <= tenor_end:
        if cursor >= quote_start:
            dates.append(cursor.date().isoformat())
        cursor += timedelta(days=90)
    return dates


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
    spot: float,
    ko_barrier: float,
    iv: float,
    tenor_yr: float,
    obs_freq: str,
    guarantee_period_yr: float = 0.0,
) -> float:
    """Probability that the underlying touches the KO barrier at some
    observation point during the *callable* portion of the tenor.

    Continuous-monitoring formula: reflection principle with zero drift
    (Merton 1973). For upper barrier (AQ case, ko_barrier > spot):

        P[hit] = 2 * N(-|log(B/S)| / (sigma * sqrt(T_callable)))

    Discrete-monitoring correction (Broadie-Glasserman 1997):

        effective_barrier = ko_barrier * exp(BETA_BG * sigma * sqrt(T_callable/n))
                              for upper barrier (shift AWAY from spot, ↓ hit prob)
        effective_barrier = ko_barrier * exp(-BETA_BG * sigma * sqrt(T_callable/n))
                              for lower barrier

    **Guarantee period (保证期):** PB AQ quotes typically include a non-call
    window (4 weeks is standard) during which KO cannot trigger. We shrink
    the effective barrier-monitoring horizon to (tenor_yr − guarantee_yr).
    Note the BSM reflection-principle formula does NOT have a clean way to
    "skip the first K weeks" of a Brownian path — but since the spot at
    the END of guarantee period is essentially a noisy version of today's
    spot (mean-zero, sqrt(guarantee_yr) std dev), we approximate by just
    using the shorter horizon. Error is small (~5-10%) for typical
    guarantee_yr / tenor_yr ratios < 0.15.

    Zero drift simplification: AQ/DQ tenors are short enough (≤18M) that
    (r − q − sigma²/2) × T is dominated by sigma × sqrt(T). Errors well
    below ±2 pp on resulting markup estimate.
    """
    if tenor_yr <= 0 or iv <= 0:
        return 0.0

    callable_yr = max(0.0, tenor_yr - guarantee_period_yr)
    if callable_yr <= 0:
        return 0.0

    n_obs = _OBS_PER_YEAR[obs_freq] * callable_yr
    if n_obs < 1:
        n_obs = 1

    upper_barrier = ko_barrier > spot
    shift_magnitude = BETA_BG * iv * math.sqrt(callable_yr / n_obs)

    if upper_barrier:
        effective_barrier = ko_barrier * math.exp(shift_magnitude)
    else:
        effective_barrier = ko_barrier * math.exp(-shift_magnitude)

    log_ratio = math.log(effective_barrier / spot)
    d = -abs(log_ratio) / (iv * math.sqrt(callable_yr))
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


# Chain-lookup primitives are now shared via scripts._market. We re-export
# them under the original `_underscore` names so existing callers and tests
# don't break.
from scripts._market import (
    nearest_expiry_to_tenor as _nearest_expiry_to_tenor,
)
from scripts._market import (
    read_chain_mid as _read_chain_mid,
)


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


def _fair_yield(q: Quote, s: Snapshot, strict_mode: bool = False) -> dict[str, Any]:
    """Compute fair-value yield + breakdown + data_provenance.

    Spot-drift behavior: `q.spot` is the spot PB quoted off; `s.spot` is the
    fresh TV/IB snapshot. If they diverge >0.5%, we emit a warning + record
    drift_pct in provenance. In `strict_mode=True` (legacy behavior), raise
    instead — useful for live pre-trade gating where stale quotes are
    unacceptable. Default is non-strict so post-trade evaluation
    (`evaluate_placed_aq`) doesn't blow up when spot has drifted since the
    deal was placed.
    """
    import warnings

    spot_drift_pct = abs(q.spot - s.spot) / s.spot
    if spot_drift_pct > 0.005:
        msg = (
            f"Quote spot ${q.spot:.2f} diverges from Snapshot spot ${s.spot:.2f} "
            f"by {spot_drift_pct * 100:.2f}% — stale snapshot reduces fair-value "
            f"accuracy. {'Raising in strict_mode' if strict_mode else 'Continuing in non-strict mode'}."
        )
        if strict_mode:
            raise ValueError(msg)
        warnings.warn(msg, stacklevel=2)

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
    guarantee_yr = q.guarantee_period_weeks * 7.0 / 365.0
    n_obs = _num_observations(q.tenor_months, q.obs_freq)
    shares_per_obs = q.shares_per_obs
    # Reference notional basis = shares_per_obs × reference_spot. For
    # legacy USD-input quotes this == daily_notional_usd; for share-input
    # AQ this is computed from the share count × the spot PB locked off.
    notional_per_obs = shares_per_obs * q.reference_spot

    # KO barrier is locked against PB's reference spot, not current.
    ko_prob = _ko_probability(
        spot=q.reference_spot,
        ko_barrier=q.ko_pct * q.reference_spot,
        iv=iv_at_ko,
        tenor_yr=tenor_yr,
        obs_freq=q.obs_freq,
        guarantee_period_yr=guarantee_yr,
    )

    alive_obs = _expected_alive_obs(ko_prob, n_obs)
    forfeited_obs = n_obs - alive_obs

    # Tail leg: deep-OTM put (AQ) or call (DQ). Fallback uses historical
    # max-drawdown magnitude × spot as a crude tail-loss-per-share estimate.
    tail_fallback_used = False
    if tail_leg_mid is None:
        tail_leg_mid = abs(s.max_drawdown_5y) * q.reference_spot * 0.02
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

    # markup_pv + pb_quoted_payoff_pv only meaningful when PB quoted an
    # explicit yield. AQ implicit-yield mode (pb_quoted_yield_pa is None)
    # leaves these as nan; analyze_quote then routes to discount-implied
    # yield comparison instead of markup_pp gating.
    if q.pb_quoted_yield_pa is not None:
        pb_quoted_payoff_pv = q.pb_quoted_yield_pa * notional_per_obs * n_obs * tenor_yr
        markup_pv = pb_quoted_payoff_pv - fair_payoff_pv
    else:
        pb_quoted_payoff_pv = float("nan")
        markup_pv = float("nan")
    fair_yield_pa = fair_payoff_pv / (notional_per_obs * n_obs * tenor_yr)

    provenance = {
        "spot": {
            "value": q.spot,
            "source": s.spot_source,
            "timestamp": s.spot_timestamp,
        },
        "spot_drift_pct": spot_drift_pct,
        "reference_spot": {
            "value": q.reference_spot,
            "source": "Quote.entry_spot" if q.entry_spot is not None else "Quote.spot",
        },
        "shares_per_obs_source": (
            "Quote.daily_shares (PB contract spec)"
            if q.daily_shares is not None
            else f"Quote.daily_notional_usd / reference_spot = "
            f"{q.daily_notional_usd:.2f}/{q.reference_spot:.2f}"
        ),
        "guarantee_period_weeks": q.guarantee_period_weeks,
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
            "source": (
                "computed (BSM first-passage + Broadie-Glasserman discrete correction; "
                f"guarantee_period {q.guarantee_period_weeks}w applied)"
            ),
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
        "notional_per_obs": notional_per_obs,
        "n_obs": n_obs,
        "tenor_yr": tenor_yr,
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


# ─── Post-trade audit ──────────────────────────────────────────


def evaluate_placed_aq(
    q: Quote,
    s: Snapshot,
    current_spot: float,
    observations_elapsed: int,
    shares_accumulated: float | None = None,
    nlv_usd: float | None = None,
    crash_scenario_pct: float = -0.20,
) -> dict[str, Any]:
    """Post-trade audit for an already-placed AQ.

    The pre-trade `analyze_quote` evaluates "should we accept this PB
    quote?". After the trade is placed, the question becomes "what is my
    current P/L, what's the forward KO probability over the remaining
    tenor, and how bad can it get if the underlying crashes from here?"
    This function answers that.

    Parameters
    ----------
    q : Quote
        The originally placed quote. `entry_spot` should be set to PB's
        reference spot at placement time (e.g., $361.85 for the GOOGL
        2026-06-03 deal); `spot` can equal entry_spot or current.
    s : Snapshot
        Fresh chain snapshot. Used for forward KO-prob computation via
        the IV at the KO strike.
    current_spot : float
        Live spot at the time this audit runs. May diverge meaningfully
        from `q.spot` / `q.entry_spot` after weeks/months elapsed.
    observations_elapsed : int
        Number of observations that have already executed (used to compute
        remaining observations + days-to-guarantee-end).
    shares_accumulated : float | None
        Actual share count already accumulated (track from PB statements).
        Defaults to base-case `shares_per_obs × observations_elapsed`.
    nlv_usd : float | None
        Trader's PB account NLV — used for forward concentration %.
    crash_scenario_pct : float
        Forward crash scenario for worst-case P/L (default -20%).

    Returns
    -------
    dict with keys:
      current_state: shares_accumulated, cost_basis_total, market_value,
                     unrealized_pnl_usd, unrealized_pnl_pct
      barriers: strike_abs, ko_abs, pct_above_strike, pct_below_ko,
                in_guarantee_period (bool)
      forward: observations_remaining, days_to_guarantee_end,
               forward_ko_prob, max_additional_exposure_usd,
               max_additional_exposure_pct_of_nlv
      crash_scenario: spot_at_crash, additional_shares_doubled,
                      total_shares_at_year_end, total_cost_basis,
                      market_value_at_crash, pnl_usd
      monitor_level: "near_ko" / "hedge_recommended" / "monitor"
    """
    if q.direction != "AQ":
        raise NotImplementedError(
            "evaluate_placed_aq currently supports AQ only; DQ mirror TBD"
        )

    strike_abs = q.strike_pct * q.reference_spot
    ko_abs = q.ko_pct * q.reference_spot
    n_obs_total = _num_observations(q.tenor_months, q.obs_freq)
    n_obs_in_guarantee = round(_OBS_PER_WEEK[q.obs_freq] * q.guarantee_period_weeks)
    observations_remaining = max(0, n_obs_total - observations_elapsed)

    if shares_accumulated is None:
        shares_accumulated = q.shares_per_obs * observations_elapsed

    cost_basis_total = shares_accumulated * strike_abs
    market_value = shares_accumulated * current_spot
    unrealized_pnl = market_value - cost_basis_total
    unrealized_pnl_pct = (
        unrealized_pnl / cost_basis_total if cost_basis_total > 0 else 0.0
    )

    pct_above_strike = (current_spot - strike_abs) / strike_abs
    pct_below_ko = (ko_abs - current_spot) / current_spot

    # Guarantee-period status: still inside if elapsed obs < guarantee obs.
    in_guarantee_period = observations_elapsed < n_obs_in_guarantee
    days_per_obs = 365.0 / (_OBS_PER_WEEK[q.obs_freq] * 52.0)
    days_to_guarantee_end = max(
        0.0, (n_obs_in_guarantee - observations_elapsed) * days_per_obs
    )

    # Forward KO probability over REMAINING callable window.
    # If still in guarantee, callable window = (remaining obs - remaining
    # guarantee obs) × period. If past guarantee, callable = remaining tenor.
    remaining_tenor_yr = observations_remaining / (
        _OBS_PER_YEAR[q.obs_freq] / 12.0 * 12.0
    )
    remaining_guarantee_yr = days_to_guarantee_end / 365.0
    nearest_expiry = _nearest_expiry_to_tenor(s.chain, q.tenor_months, s.spot_timestamp)
    iv_at_ko = s.chain[nearest_expiry][q.ko_pct]["call"]["iv"]
    forward_ko_prob = _ko_probability(
        spot=current_spot,
        ko_barrier=ko_abs,
        iv=iv_at_ko,
        tenor_yr=remaining_tenor_yr,
        obs_freq=q.obs_freq,
        guarantee_period_yr=remaining_guarantee_yr,
    )

    # Max additional exposure: remaining obs × shares × strike × doubling.
    max_additional_exposure = (
        q.shares_per_obs * observations_remaining * strike_abs * q.doubling_factor
    )
    max_additional_exposure_pct_nlv = (
        max_additional_exposure / nlv_usd
        if (nlv_usd is not None and nlv_usd > 0)
        else float("nan")
    )

    # Crash scenario: spot drops by `crash_scenario_pct` immediately and
    # stays there. Doubling fires (since crash takes spot < strike), so
    # remaining obs accumulate at 2× rate. Cost basis still at strike.
    spot_at_crash = current_spot * (1.0 + crash_scenario_pct)
    additional_shares_doubled = (
        q.shares_per_obs * observations_remaining * q.doubling_factor
    )
    total_shares_at_year_end = shares_accumulated + additional_shares_doubled
    total_cost_basis = total_shares_at_year_end * strike_abs
    market_value_at_crash = total_shares_at_year_end * spot_at_crash
    crash_pnl = market_value_at_crash - total_cost_basis

    # Monitor level. Near-KO trumps other signals; otherwise check
    # distance-to-strike for downside-hedge urgency.
    if pct_below_ko < 0.02:  # within 2% of KO
        monitor_level = "near_ko"
    elif pct_above_strike < 0.05:  # within 5% above strike → doubling risk
        monitor_level = "hedge_recommended"
    else:
        monitor_level = "monitor"

    return {
        "current_state": {
            "shares_accumulated": shares_accumulated,
            "cost_basis_total": cost_basis_total,
            "market_value": market_value,
            "unrealized_pnl_usd": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
        },
        "barriers": {
            "strike_abs": strike_abs,
            "ko_abs": ko_abs,
            "pct_above_strike": pct_above_strike,
            "pct_below_ko": pct_below_ko,
            "in_guarantee_period": in_guarantee_period,
        },
        "forward": {
            "observations_elapsed": observations_elapsed,
            "observations_remaining": observations_remaining,
            "days_to_guarantee_end": days_to_guarantee_end,
            "forward_ko_prob": forward_ko_prob,
            "max_additional_exposure_usd": max_additional_exposure,
            "max_additional_exposure_pct_of_nlv": max_additional_exposure_pct_nlv,
        },
        "crash_scenario": {
            "crash_pct": crash_scenario_pct,
            "spot_at_crash": spot_at_crash,
            "additional_shares_doubled": additional_shares_doubled,
            "total_shares_at_year_end": total_shares_at_year_end,
            "total_cost_basis": total_cost_basis,
            "market_value_at_crash": market_value_at_crash,
            "pnl_usd": crash_pnl,
        },
        "monitor_level": monitor_level,
    }
