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

from scipy.stats import norm

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
) -> dict[str, Any]:
    """Compute FCN strike-ladder analysis from a market snapshot.

    `snapshot` must include: spot, iv, rv, iv_rank, skew_25d, max_drawdown_5y,
    gex_levels (with gamma_flip, put_wall, call_wall). Caller is responsible
    for fetching that data from UW (see scripts._clients.uw).
    """
    if snapshot is None:
        raise ValueError("snapshot is required; fetch UW data and pass it in")

    tenor_years = tenor_months / 12.0
    tenor_days = int(round(tenor_months * 21))
    vol = snapshot["iv"]
    spot = snapshot["spot"]

    ladder = []
    for strike_pct in strike_pcts:
        strike_dollar = spot * strike_pct
        p_ki = single_name_ki_prob(vol, barrier=strike_pct, days=tenor_days)
        fair_base = fair_coupon_proxy(
            p_ki, lgd, expected_alive_months, discount_rate, tenor_years
        )
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

    return {
        "ticker": ticker,
        "tenor_months": tenor_months,
        "observation_months": observation_months,
        "ko_pct": ko_pct,
        "spot": spot,
        "iv": vol,
        "iv_rank": snapshot.get("iv_rank"),
        "ladder": ladder,
    }
