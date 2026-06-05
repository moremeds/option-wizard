"""Fair coupon proxy for FCN evaluation.

The continuous-touch barrier approximation overstates the true KI rate for
discretely-observed FCN structures, but it is the right ceiling input to
the four-rung strike ladder we emit. Downstream interpretation (real
institutional fair coupon is roughly half the model output; retail PB
adds 25-40% markup) lives in references/fcn-framework.md.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
from scipy.stats import norm

from scripts._market import (
    chain_leg_provenance,
    fallback_provenance,
    nearest_expiry_to_tenor,
    read_chain_mid,
)

LGD_BASE = 0.50
LGD_STRESS = 0.65
DEFAULT_DISCOUNT_RATE = 0.045


def single_name_ki_prob(vol: float, barrier: float, days: int = 252) -> float:
    if vol is None or vol <= 0:
        return float("nan")
    sigma_t = vol * math.sqrt(days / 252.0)
    if sigma_t == 0:
        return 0.0
    return 2.0 * norm.cdf(math.log(barrier) / sigma_t)


def fair_coupon_proxy(
    p_ki: float,
    expected_loss_given_ki: float,
    expected_alive_months: float,
    discount_rate: float,
    tenor_years: float,
) -> float:
    if p_ki is None or math.isnan(p_ki) or expected_alive_months <= 0:
        return float("nan")
    if p_ki == 0:
        return 0.0
    pv_expected_loss = (
        p_ki * expected_loss_given_ki * math.exp(-discount_rate * tenor_years)
    )
    return pv_expected_loss / (expected_alive_months / 12.0)


def fair_coupon_chain(
    put_mid_per_share: float,
    strike_dollar: float,
    expected_alive_months: float,
) -> float:
    """Chain-priced fair coupon for the embedded short-put leg.

    The FCN's economic content is "client receives coupon X% in exchange for
    being short a put at the KI strike". Listed put mid at that strike IS
    the market's price for that exact short-put exposure — including the
    skew premium that the closed-form proxy (which uses ATM IV) misses.

    Annualization: client pays `put_mid` per share once, receives coupon
    monthly over the expected alive period. To make the cashflows
    equivalent on an annual basis:

        fair_coupon_pa = put_mid_per_share / (strike_dollar × alive_yr)

    where strike_dollar is the per-share notional client is on the hook for
    at the KI level. Discount factor omitted: alive period is short enough
    (≤6M typical) that 4.5% × 0.5 ≈ 2% drift on the answer — well inside
    the heuristic precision band.

    This number is what an INSTITUTIONAL fair coupon would look like with
    no markup. Retail PB quotes are 25-40% of model fair (per framework);
    chain-priced is closer to 50-70% of model fair because it captures
    skew correctly.
    """
    if put_mid_per_share is None or strike_dollar <= 0 or expected_alive_months <= 0:
        return float("nan")
    alive_yr = expected_alive_months / 12.0
    return put_mid_per_share / (strike_dollar * alive_yr)


def _fair_coupon_from_chain_or_model(
    *,
    snapshot: dict,
    strike_pct: float,
    spot: float,
    tenor_months: int,
    expected_alive_months: float,
    quote_start_iso: str,
    # model fallback inputs
    p_ki: float,
    lgd: float,
    discount_rate: float,
    tenor_years: float,
) -> tuple[float, dict[str, Any]]:
    """Return (fair_coupon, provenance_dict). Chain-priced if snapshot
    carries a chain that covers the strike; BSM-proxy fallback otherwise.

    The provenance dict has shape:
        {
            "fair_coupon_source": "chain" | "model",
            "leg": {<chain_leg_provenance or fallback_provenance entry>},
        }

    Callers attach this dict to the rung output so the trader can see at a
    glance whether a number came from a real listed mid or a closed-form
    approximation."""
    chain = snapshot.get("chain")
    chain_source = snapshot.get("chain_source", "UW")

    # Pass-1 fix (F3): one expiry lookup, not two. The previous version
    # walked the chain via _nearest_expiry_or_none to fetch the timestamp,
    # then walked it again via nearest_expiry_to_tenor to read the mid.
    expiry: str | None = None
    if chain:
        try:
            expiry = nearest_expiry_to_tenor(chain, tenor_months, quote_start_iso)
        except ValueError:
            expiry = None

    chain_timestamp = (
        snapshot.get("chain_timestamps", {}).get(expiry) if expiry else None
    )

    if expiry is not None:
        put_mid = read_chain_mid(chain, expiry, strike_pct, "put")
        if put_mid is not None:
            strike_dollar = spot * strike_pct
            fair = fair_coupon_chain(put_mid, strike_dollar, expected_alive_months)
            return fair, {
                "fair_coupon_source": "chain",
                "leg": chain_leg_provenance(
                    value=put_mid,
                    chain_source=chain_source,
                    expiry=expiry,
                    strike_pct=strike_pct,
                    right="put",
                    field="mid",
                    timestamp=chain_timestamp,
                ),
            }

    fair_model = fair_coupon_proxy(
        p_ki, lgd, expected_alive_months, discount_rate, tenor_years
    )
    return fair_model, {
        "fair_coupon_source": "model",
        "leg": fallback_provenance(
            value=fair_model,
            reason=(
                "BSM hazard-rate proxy — chain not provided or strike not listed; "
                "answer carries hardcoded LGD 0.50 and ATM IV (no skew premium)."
            ),
        ),
    }


def _tag_zone(strike_dollar: float, gex_levels: dict) -> str:
    flip = gex_levels.get("gamma_flip")
    if flip is None:
        return "unknown (gamma flip not identifiable)"
    if strike_dollar < flip:
        return "RISK: below gamma flip (dealer short gamma)"
    put_wall = gex_levels.get("put_wall")
    if put_wall and strike_dollar < put_wall:
        return "OK: above flip, below put wall"
    return "OK: above flip"


def _checklist(
    strike_pct: float,
    strike_dollar: float,
    snapshot: dict,
    fair_base: float,
    pb_quoted_coupon: float | None,
) -> list[dict]:
    """Eight-item PB defense checklist. Each item returns id, status, detail."""
    flip = snapshot["gex_levels"].get("gamma_flip")
    max_dd = snapshot.get("max_drawdown_5y", -1.0)
    iv_rank = snapshot.get("iv_rank")
    skew = snapshot.get("skew_25d")

    items = []

    if flip is None:
        s1 = {"status": "WARN", "detail": "gamma flip not identifiable"}
    elif strike_dollar < flip:
        s1 = {
            "status": "FAIL",
            "detail": f"strike ${strike_dollar:.2f} below flip ${flip:.2f}; demand +5pp coupon or raise strike",
        }
    else:
        s1 = {
            "status": "PASS",
            "detail": f"strike ${strike_dollar:.2f} above flip ${flip:.2f}",
        }
    items.append({"id": "strike_vs_gamma_flip", **s1})

    if pb_quoted_coupon is not None and fair_base > 0:
        markup_ratio = pb_quoted_coupon / fair_base
        if markup_ratio < 0.25:
            s2 = {
                "status": "FAIL",
                "detail": f"quote {pb_quoted_coupon:.1%} is {markup_ratio:.0%} of model fair {fair_base:.1%}; predatory",
            }
        elif markup_ratio < 0.30:
            s2 = {
                "status": "WARN",
                "detail": f"quote at {markup_ratio:.0%} of model; counter for +2pp",
            }
        else:
            s2 = {
                "status": "PASS",
                "detail": f"quote at {markup_ratio:.0%} of model fair, within normal retail band",
            }
    else:
        s2 = {"status": "SKIP", "detail": "no PB quote provided"}
    items.append({"id": "markup_vs_iv_rank", **s2})

    cushion_pp = (strike_pct - 1.0) - max_dd
    if cushion_pp < 0.10:
        s3 = {
            "status": "FAIL",
            "detail": f"only {cushion_pp * 100:+.1f}pp above 5y max DD; ticker has been at this strike before",
        }
    else:
        s3 = {
            "status": "PASS",
            "detail": f"{cushion_pp * 100:+.1f}pp cushion above 5y max DD",
        }
    items.append({"id": "ki_buffer_vs_5y_max_dd", **s3})

    if iv_rank is None:
        s4 = {"status": "WARN", "detail": "IV rank not provided"}
    elif iv_rank < 50:
        s4 = {
            "status": "WARN",
            "detail": f"IV rank {iv_rank} below 50; consider monthly short put instead of 6m FCN lock-in",
        }
    else:
        s4 = {"status": "PASS", "detail": f"IV rank {iv_rank} supports selling vol"}
    items.append({"id": "iv_rank_threshold", **s4})

    if skew is None:
        s5 = {"status": "WARN", "detail": "skew not provided"}
    elif skew < -0.25:
        s5 = {
            "status": "WARN",
            "detail": f"25Δ skew {skew:.2f} extremely negative; demand +3-5pp coupon for left-tail risk",
        }
    else:
        s5 = {"status": "PASS", "detail": f"25Δ skew {skew:.2f} within normal range"}
    items.append({"id": "skew_penalty", **s5})

    items.append(
        {
            "id": "tenor_anchor",
            "status": "INFO",
            "detail": "translate annualized coupon to absolute dollar return given expected alive months ≈ 3.5",
        }
    )
    items.append(
        {
            "id": "liquidity_no_secondary",
            "status": "INFO",
            "detail": "FCN has no secondary market; only exit is holding to maturity",
        }
    )
    items.append(
        {
            "id": "issuer_credit_risk",
            "status": "INFO",
            "detail": "pull PB parent senior unsecured rating and 5y CDS; flag SPV-issued notes",
        }
    )

    return items


def _verdict(fair_base: float, pb_quoted_coupon: float) -> str:
    if fair_base <= 0:
        return "unknown"
    floor = fair_base * 0.25
    ceil_ = fair_base * 0.40
    if pb_quoted_coupon < floor:
        return "rich"
    if pb_quoted_coupon > ceil_:
        return "cheap"
    return "fair"


def build_counter_offer_email(
    ticker: str,
    rung: dict,
    recommended_strike_pct: float,
    recommended_coupon_low: float,
    recommended_coupon_high: float,
) -> str:
    """Generate a bilingual (Chinese first, English second) counter-offer
    email body for forwarding back to the private bank.
    """
    failed = [c for c in rung.get("checklist", []) if c["status"] in ("FAIL", "WARN")]
    concerns_zh = (
        "\n".join(f"  - {c['detail']}" for c in failed)
        or "  - (无具体技术问题，仅价格不合理)"
    )
    concerns_en = (
        "\n".join(f"  - {c['detail']}" for c in failed)
        or "  - (no specific concerns beyond pricing)"
    )

    subject = f"Re: FCN quote on {ticker} – Counter-offer"
    spot_inferred = rung.get("strike_dollar", 0) / rung.get("strike_pct", 1)
    body = f"""Subject: {subject}

—— 中文 ——

你好 [Banker],

谢谢你给的 FCN 报价。我这边跑了一下数据：

- 现价: ${spot_inferred:.2f}
- 行权价: {rung["strike_pct"] * 100:.0f}% (${rung["strike_dollar"]:.2f})
- 6m 敲入概率(模型): {rung["p_ki_6m"] * 100:.1f}%
- 模型公允票息: {rung["fair_coupon_base"] * 100:.1f}%
- PB 报价: {rung.get("pb_quoted_coupon", 0) * 100:.1f}%
- 经销区域: {rung["dealer_zone"]}

具体顾虑:
{concerns_zh}

希望你能按以下条款重新结构化:
- 行权价: {recommended_strike_pct * 100:.0f}%
- Coupon: {recommended_coupon_low * 100:.1f}% – {recommended_coupon_high * 100:.1f}%

或者保持当前 coupon 但把行权价降到合适位置。等你回复。

谢谢。


—— English ——

Hi [Banker],

Thanks for the quote. After running the numbers on our end:

- Spot: ${spot_inferred:.2f}
- Strike: {rung["strike_pct"] * 100:.0f}% (${rung["strike_dollar"]:.2f})
- Model KI probability (6m): {rung["p_ki_6m"] * 100:.1f}%
- Model fair coupon: {rung["fair_coupon_base"] * 100:.1f}%
- Your quoted coupon: {rung.get("pb_quoted_coupon", 0) * 100:.1f}%
- Dealer flow zone: {rung["dealer_zone"]}

Specific concerns:
{concerns_en}

We'd be interested if you can restructure at:
- Strike: {recommended_strike_pct * 100:.0f}%
- Coupon: {recommended_coupon_low * 100:.1f}% – {recommended_coupon_high * 100:.1f}%

Or alternatively reduce strike to a similar level at your current coupon.

Looking forward to your response.

Best,
"""
    return body


def analyze_fcn(
    ticker: str,
    strike_pcts: Iterable[float] = (0.70, 0.75, 0.80, 0.85),
    tenor_months: int = 6,
    observation_months: int = 3,
    ko_pct: float = 1.0,
    pb_quoted_coupon: float | None = None,
    snapshot: dict[str, Any] | None = None,
    expected_alive_months: float = 3.5,
    lgd: float = LGD_BASE,
    lgd_stress: float = LGD_STRESS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    quote_start_iso: str | None = None,
) -> dict[str, Any]:
    """Compute FCN strike-ladder analysis from a market snapshot.

    `snapshot` must include: spot, iv, rv, iv_rank, skew_25d, max_drawdown_5y,
    gex_levels (with gamma_flip, put_wall, call_wall). Caller is responsible
    for fetching that data from UW (see scripts._clients.uw).

    Optional `snapshot["chain"]` activates the chain-priced fair-coupon path
    (per hard rule #2 + aq-dq-framework §3 data discipline): listed put mids
    at the FCN strikes replace the BSM hazard-rate proxy. Each rung's output
    carries `fair_coupon_provenance` so the trader can see which method was
    used (chain vs model) and which exact listed strike priced it.

    `quote_start_iso` anchors the nearest-expiry lookup. Resolution order:
    explicit parameter → `snapshot["spot_timestamp"]` → today's UTC ISO. The
    last fallback exists so existing model-only callers don't need to plumb
    a timestamp through; chain-aware callers SHOULD pass it explicitly so
    expiry resolution is deterministic across days.
    """
    if snapshot is None:
        raise ValueError("snapshot is required; fetch UW data and pass it in")

    if quote_start_iso is None:
        from datetime import datetime, timezone

        quote_start_iso = snapshot.get(
            "spot_timestamp", datetime.now(timezone.utc).isoformat()
        )

    tenor_years = tenor_months / 12.0
    tenor_days = int(round(tenor_months * 21))
    vol = snapshot["iv"]
    spot = snapshot["spot"]

    ladder = []
    for strike_pct in strike_pcts:
        strike_dollar = spot * strike_pct
        p_ki = single_name_ki_prob(vol, barrier=strike_pct, days=tenor_days)
        # Chain-aware fair coupon (Phase B); falls back to model proxy when
        # the snapshot has no chain or the chain lacks this strike.
        fair_base, fair_base_provenance = _fair_coupon_from_chain_or_model(
            snapshot=snapshot,
            strike_pct=strike_pct,
            spot=spot,
            tenor_months=tenor_months,
            expected_alive_months=expected_alive_months,
            quote_start_iso=quote_start_iso,
            p_ki=p_ki,
            lgd=lgd,
            discount_rate=discount_rate,
            tenor_years=tenor_years,
        )
        # Stress remains model-derived: chain doesn't price LGD-stress
        # scenarios, only the realised loss distribution.
        fair_stress = fair_coupon_proxy(
            p_ki, lgd_stress, expected_alive_months, discount_rate, tenor_years
        )
        zone = _tag_zone(strike_dollar, snapshot["gex_levels"])
        checklist = _checklist(
            strike_pct, strike_dollar, snapshot, fair_base, pb_quoted_coupon
        )
        rung = {
            "strike_pct": strike_pct,
            "strike_dollar": round(strike_dollar, 2),
            "p_ki_6m": round(p_ki, 4),
            "fair_coupon_base": round(fair_base, 4),
            "fair_coupon_stress": round(fair_stress, 4),
            "fair_coupon_source": fair_base_provenance["fair_coupon_source"],
            "fair_coupon_provenance": fair_base_provenance,
            "dealer_zone": zone,
            "checklist": checklist,
        }
        if pb_quoted_coupon is not None:
            rung["pb_quoted_coupon"] = pb_quoted_coupon
            rung["verdict"] = _verdict(fair_base, pb_quoted_coupon)
        verdict_rich = rung.get("verdict") == "rich"
        any_fail = any(c["status"] == "FAIL" for c in checklist)
        if verdict_rich or any_fail:
            rec_strike_pct = min(strike_pct + 0.05, 0.85)
            rec_low = round(fair_base * 0.30, 4)
            rec_high = round(fair_base * 0.40, 4)
            rung["counter_offer_email"] = build_counter_offer_email(
                ticker=ticker,
                rung=rung,
                recommended_strike_pct=rec_strike_pct,
                recommended_coupon_low=rec_low,
                recommended_coupon_high=rec_high,
            )
        ladder.append(rung)

    anchor_rung = (
        min(ladder, key=lambda r: abs(r["strike_pct"] - 0.75)) if ladder else None
    )
    return {
        "ticker": ticker,
        "tenor_months": tenor_months,
        "observation_months": observation_months,
        "ko_pct": ko_pct,
        "spot": spot,
        "iv": vol,
        "iv_rank": snapshot.get("iv_rank"),
        "ladder": ladder,
        "anchor_strike_pct": anchor_rung["strike_pct"] if anchor_rung else None,
        "verdict": anchor_rung.get("verdict") if anchor_rung else None,
    }


def joint_ki_prob_mc(
    vol_a: float,
    vol_b: float,
    rho: float,
    barrier: float = 0.50,
    days: int = 252,
    n_sims: int = 20_000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Monte Carlo joint KI for a worst-of-2 FCN.

    Returns (p_either, p_all, p_exactly_one). p_either is the worst-of touch
    probability used to price the basket.

    Drift convention: matches the single-name closed-form
    2*Phi(ln(B)/(sigma*sqrt(T))), which assumes a driftless Brownian motion
    in log-returns (no -0.5*sigma^2 correction). The two paths use the same
    stochastic model so that at rho->1 the MC collapses to the closed-form
    single-name result (validated by
    test_joint_ki_prob_at_full_correlation_equals_single_name).
    """
    rho = max(-0.999, min(0.999, rho))
    rng = np.random.default_rng(seed)
    dt = 1.0 / 252.0
    chol = np.array([[1.0, 0.0], [rho, math.sqrt(max(0.0, 1.0 - rho * rho))]])
    z = rng.standard_normal(size=(n_sims, days, 2)) @ chol.T
    vols = np.array([vol_a, vol_b])
    diffusion = vols * math.sqrt(dt)
    log_paths = np.cumsum(diffusion * z, axis=1)
    min_paths = np.exp(log_paths.min(axis=1))
    hits = min_paths <= barrier
    return (
        float(hits.any(axis=1).mean()),
        float(hits.all(axis=1).mean()),
        float((hits.sum(axis=1) == 1).mean()),
    )


def analyze_fcn_basket(
    tickers: list[str],
    snapshots: dict[str, dict],
    corr_matrix,
    strike_pct: float,
    tenor_months: int = 6,
    observation_months: int = 3,
    ko_pct: float = 1.0,
    pb_quoted_coupon: float | None = None,
    expected_alive_months: float = 3.5,
    lgd: float = LGD_BASE,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
) -> dict[str, Any]:
    """Worst-of basket FCN analysis.

    Currently supports baskets of 2 names (joint_ki_prob_mc). For 3+ names,
    extend to joint_ki_prob_nd (not in v1 scope).
    """
    if len(tickers) != 2:
        raise NotImplementedError("v1 basket FCN supports exactly 2 tickers")

    tenor_years = tenor_months / 12.0
    tenor_days = int(round(tenor_months * 21))

    per_name = {}
    single_p_kis = []
    for t in tickers:
        snap = snapshots[t]
        p = single_name_ki_prob(snap["iv"], barrier=strike_pct, days=tenor_days)
        single_p_kis.append(p)
        per_name[t] = {
            "spot": snap["spot"],
            "iv": snap["iv"],
            "iv_rank": snap.get("iv_rank"),
            "p_ki_single": round(p, 4),
        }

    rho = float(corr_matrix[0, 1])
    p_either, p_all, p_one = joint_ki_prob_mc(
        vol_a=snapshots[tickers[0]]["iv"],
        vol_b=snapshots[tickers[1]]["iv"],
        rho=rho,
        barrier=strike_pct,
        days=tenor_days,
    )

    fair_basket = fair_coupon_proxy(
        p_either, lgd, expected_alive_months, discount_rate, tenor_years
    )
    worst_single = max(single_p_kis)
    fair_worst_single = fair_coupon_proxy(
        worst_single, lgd, expected_alive_months, discount_rate, tenor_years
    )
    premium_min_pp = (1.0 - rho) * 0.30 * fair_worst_single

    basket = {
        "p_ki_either": round(p_either, 4),
        "p_ki_all": round(p_all, 4),
        "p_ki_exactly_one": round(p_one, 4),
        "fair_coupon": round(fair_basket, 4),
        "fair_coupon_worst_single": round(fair_worst_single, 4),
        "correlation": round(rho, 3),
        "diversification_premium_pp": round(premium_min_pp, 4),
    }
    if pb_quoted_coupon is not None:
        basket["pb_quoted_coupon"] = pb_quoted_coupon
        basket["verdict"] = _verdict(fair_basket, pb_quoted_coupon)

    return {
        "tickers": tickers,
        "strike_pct": strike_pct,
        "tenor_months": tenor_months,
        "observation_months": observation_months,
        "ko_pct": ko_pct,
        "per_name": per_name,
        "basket": basket,
    }
