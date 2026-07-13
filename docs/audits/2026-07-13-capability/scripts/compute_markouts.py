#!/usr/bin/env python3
"""Join calls.json x prices.json -> markouts.json + printed report.

Honesty rules: every price traces to prices.json (real API responses).
No fabricated prices. Tickers without a fetched series are UNSCOREABLE.
"""

import json
import math
import statistics
from datetime import date, datetime
from pathlib import Path

SCRATCH = Path(
    "/private/tmp/claude-501/-Users-chenxi-projects-option-wizard/f786956f-6c57-46e9-b5e9-4bca0b9772a3/scratchpad"
)
CALLS_PATH = SCRATCH / "calls.json"
PRICES_PATH = SCRATCH / "prices.json"
OUT_PATH = SCRATCH / "markouts.json"

TODAY = date(2026, 7, 13)
LAST_TRADING_DAY = date(2026, 7, 10)
HORIZONS = [1, 5, 10, 21]
NOISE_BAND = 0.02

INDEX_SET = {
    "SPX",
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "VIX",
    "NDX",
    "RUT",
    "SMH",
    "MAGS",
    "SOXX",
}
NON_TICKER_LABELS = {
    "FUTU-BOOK",
    "MACRO+BOOK",
    "BOOK",
    "SKILL-AUDIT",
    "SYNTHETIC/GATE-TEST",
}

DIRECTION_SIGN = {"bullish": 1, "bearish": -1}


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_data():
    calls = json.loads(CALLS_PATH.read_text())["calls"]
    prices_doc = json.loads(PRICES_PATH.read_text())
    return calls, prices_doc


def build_series(prices_doc):
    series = {}
    for ticker, rows in prices_doc["prices"].items():
        s = sorted(rows, key=lambda r: r["date"])
        series[ticker] = [(parse_date(r["date"]), r["c"]) for r in s]
    return series


def find_base_index(dates, as_of):
    """Index of as_of date in dates list, or first date >= as_of (next trading day)."""
    for i, d in enumerate(dates):
        if d >= as_of:
            return i
    return None


def june_sigma(series_for_ticker):
    """Daily log-return stdev over June 2026 closes (population within fetched series)."""
    june_closes = [c for d, c in series_for_ticker if d.month == 6 and d.year == 2026]
    if len(june_closes) < 5:
        return None
    rets = [
        math.log(june_closes[i] / june_closes[i - 1])
        for i in range(1, len(june_closes))
    ]
    if len(rets) < 2:
        return None
    return statistics.pstdev(rets)


def realized_vol_window(dates_closes, center_idx, n):
    """Annualized-free realized vol (stdev of daily log returns) over n days ending/starting at center_idx."""
    pass


def nearest_horizon_days(horizon_days):
    if horizon_days is None:
        return 5
    trading_est = horizon_days * (5 / 7)
    return min(HORIZONS, key=lambda h: abs(h - trading_est))


def split_tickers(ticker_field):
    return [t.strip() for t in ticker_field.split(",") if t.strip()]


def classify_prior_verdict(text):
    if not text:
        return None
    t = text.upper()
    # crude keyword scan, prefer explicit WRONG/CORRECT/RIGHT tokens
    if "WRONG" in t:
        return "WRONG"
    if "CORRECT" in t or " RIGHT" in t or t.startswith("RIGHT"):
        return "RIGHT" if "CORRECT" not in t else "RIGHT"
    if "UNDERSHOT" in t or "MISS" in t:
        return "WRONG"
    return None


def main():
    calls, prices_doc = load_data()
    series = build_series(prices_doc)
    failed_tickers = set(prices_doc["meta"]["failed_tickers"])
    ticker_sigma = {t: june_sigma(s) for t, s in series.items()}

    rows = []
    skipped = []

    for call in calls:
        if call["id"] == "elog01":
            continue  # synthetic gate-test entry, excluded per instructions

        as_of = (
            parse_date(call["as_of_date"].split(" to ")[0])
            if " to " in call["as_of_date"]
            else parse_date(call["as_of_date"])
        )
        tickers = split_tickers(call["ticker"])
        direction = call["direction"]
        horizon_days = call["horizon_days"]
        nearest_h = nearest_horizon_days(horizon_days)

        for tkr in tickers:
            base_row = {
                "call_id": call["id"],
                "ticker": tkr,
                "source_file": call["source_file"],
                "as_of_date": call["as_of_date"],
                "direction": direction,
                "horizon_days": horizon_days,
                "nearest_horizon_td": nearest_h,
                "structure_recommended": call["structure_recommended"],
                "thesis_oneliner": call["thesis_oneliner"],
                "prior_verdict_raw": call["prior_verdict"],
            }

            if tkr in NON_TICKER_LABELS:
                base_row.update(
                    {
                        "status": "UNSCOREABLE",
                        "reason": f"ticker field '{tkr}' is a book/skill-audit label, not a priceable instrument. Not decomposed further to avoid guessing which underlying(s) it refers to.",
                    }
                )
                rows.append(base_row)
                continue

            if tkr not in series or tkr in failed_tickers:
                base_row.update(
                    {
                        "status": "UNSCOREABLE",
                        "reason": prices_doc["meta"]["sources"].get(
                            tkr, f"no price series fetched for {tkr}"
                        ),
                    }
                )
                rows.append(base_row)
                continue

            dates_closes = series[tkr]
            dates = [d for d, c in dates_closes]
            idx = find_base_index(dates, as_of)
            if idx is None:
                base_row.update(
                    {
                        "status": "UNSCOREABLE",
                        "reason": f"as_of_date {as_of} has no on/after trading day within fetched window (2026-06-01..2026-07-10) for {tkr}",
                    }
                )
                rows.append(base_row)
                continue

            base_date, base_close = dates_closes[idx]
            spot_at_call = call["spot_at_call"]
            base_source = "series_close"
            sanity_flag = None
            if spot_at_call is not None:
                pct_diff = abs(spot_at_call - base_close) / base_close
                if pct_diff > 0.05:
                    sanity_flag = f"spot_at_call {spot_at_call} differs from {tkr} close on {base_date} ({base_close}) by {pct_diff:.1%} -- likely intraday/premarket spot vs EOD close, or multi-ticker call where spot_at_call belongs to a different ticker in the list"

            horizon_data = {}
            for h in HORIZONS:
                target_idx = idx + h
                if target_idx < len(dates_closes):
                    t_date, t_close = dates_closes[target_idx]
                    ret = (t_close / base_close) - 1
                    horizon_data[f"T{h}"] = {
                        "date": t_date.isoformat(),
                        "close": t_close,
                        "return": round(ret, 5),
                        "incomplete": False,
                    }
                else:
                    horizon_data[f"T{h}"] = {
                        "date": None,
                        "close": None,
                        "return": None,
                        "incomplete": True,
                    }

            # pick verdict horizon: nearest_h if available, else fall back to largest available <= nearest_h, else smallest available
            available_h = [
                h for h in HORIZONS if not horizon_data[f"T{h}"]["incomplete"]
            ]
            horizon_incomplete_flag = horizon_data[f"T{nearest_h}"]["incomplete"]
            if not horizon_data[f"T{nearest_h}"]["incomplete"]:
                verdict_h = nearest_h
            elif available_h:
                # fall back to the closest available horizon below nearest_h
                lower = [h for h in available_h if h < nearest_h]
                verdict_h = max(lower) if lower else min(available_h)
            else:
                verdict_h = None

            sigma = ticker_sigma.get(tkr)

            def sigma_context(h):
                if sigma is None or h is None:
                    return None
                ret = horizon_data[f"T{h}"]["return"]
                if ret is None:
                    return None
                denom = sigma * math.sqrt(h)
                if denom == 0:
                    return None
                return round(ret / denom, 3)

            verdict = None
            proxy_only = False
            move_at_verdict_h = None
            if direction in ("vol_up", "vol_down"):
                # UNSCOREABLE for direction; proxy: realized vol next-5d vs prior-20d from as_of
                verdict = "UNSCOREABLE"
                proxy_only = True
                # realized vol proxy
                prior_start = max(0, idx - 20)
                prior_closes = [c for d, c in dates_closes[prior_start : idx + 1]]
                next_end = min(len(dates_closes), idx + 6)
                next_closes = [c for d, c in dates_closes[idx:next_end]]

                def stdev_logret(cl):
                    if len(cl) < 3:
                        return None
                    r = [math.log(cl[i] / cl[i - 1]) for i in range(1, len(cl))]
                    return statistics.pstdev(r) if len(r) >= 2 else None

                rv_prior20 = stdev_logret(prior_closes)
                rv_next5 = stdev_logret(next_closes)
                base_row["vol_proxy"] = {
                    "rv_prior20_daily_sigma": round(rv_prior20, 5)
                    if rv_prior20
                    else None,
                    "rv_next5_daily_sigma": round(rv_next5, 5) if rv_next5 else None,
                    "rv_expansion": (rv_next5 > rv_prior20)
                    if (rv_prior20 and rv_next5)
                    else None,
                    "note": "proxy_only -- no historical IV-rank source available; compares realized vol, not implied vol",
                }
            elif verdict_h is None:
                verdict = "UNSCOREABLE"
                base_row["reason_no_verdict"] = (
                    "no horizon reached T+1 within fetched window from as_of_date"
                )
            else:
                move = horizon_data[f"T{verdict_h}"]["return"]
                move_at_verdict_h = move
                if direction in ("bullish", "bearish"):
                    signed = DIRECTION_SIGN[direction] * move
                    if signed >= NOISE_BAND:
                        verdict = "RIGHT"
                    elif signed <= -NOISE_BAND:
                        verdict = "WRONG"
                    else:
                        verdict = "NEUTRAL"
                else:  # range / neutral -> scored as range
                    verdict = "RIGHT" if abs(move) < NOISE_BAND else "WRONG"

            base_row.update(
                {
                    "base_date": base_date.isoformat(),
                    "base_close": base_close,
                    "base_source": base_source,
                    "spot_at_call": spot_at_call,
                    "sanity_flag": sanity_flag,
                    "horizons": horizon_data,
                    "verdict_horizon_td": verdict_h,
                    "verdict_horizon_requested_td": nearest_h,
                    "horizon_incomplete_at_requested": horizon_incomplete_flag,
                    "verdict": verdict,
                    "move_at_verdict_horizon": move_at_verdict_h,
                    "sigma_daily_june": round(sigma, 5) if sigma else None,
                    "sigma_context_T1": sigma_context(1),
                    "sigma_context_T5": sigma_context(5),
                    "sigma_context_T10": sigma_context(10),
                    "sigma_context_T21": sigma_context(21),
                    "status": "SCORED"
                    if verdict != "UNSCOREABLE"
                    else "UNSCOREABLE_VOL"
                    if proxy_only
                    else "UNSCOREABLE",
                }
            )

            # cross-check vs prior_verdict text
            prior_class = classify_prior_verdict(call["prior_verdict"])
            base_row["prior_verdict_parsed"] = prior_class
            base_row["disagrees_with_prior"] = bool(
                prior_class
                and verdict not in ("UNSCOREABLE",)
                and prior_class != verdict
            )

            rows.append(base_row)

    OUT_PATH.write_text(json.dumps(rows, indent=2, default=str))
    print(f"Wrote {len(rows)} rows to {OUT_PATH}")

    # ---------------- REPORT ----------------
    scored = [r for r in rows if r.get("verdict") in ("RIGHT", "WRONG", "NEUTRAL")]
    vol_proxy_rows = [r for r in rows if r.get("status") == "UNSCOREABLE_VOL"]
    unscoreable = [r for r in rows if r.get("status") == "UNSCOREABLE"]

    def count_verdicts(rs):
        c = {"RIGHT": 0, "WRONG": 0, "NEUTRAL": 0}
        for r in rs:
            v = r.get("verdict")
            if v in c:
                c[v] += 1
        return c

    print("\n=== OVERALL ===")
    print(f"total rows (excl synthetic): {len(rows)}")
    print(
        f"scored: {len(scored)} | unscoreable: {len(unscoreable)} | vol-proxy-only: {len(vol_proxy_rows)}"
    )
    print(count_verdicts(scored))

    print("\n=== BY DIRECTION ===")
    for d in ("bullish", "bearish", "range", "neutral"):
        rs = [r for r in scored if r["direction"] == d]
        print(d, count_verdicts(rs), f"n_scored={len(rs)}")

    print("\n=== BY MONTH ===")
    for label, pred in [
        ("June", lambda r: r["as_of_date"] < "2026-07-01"),
        ("July", lambda r: r["as_of_date"] >= "2026-07-01"),
    ]:
        rs = [r for r in scored if pred(r)]
        print(label, count_verdicts(rs), f"n_scored={len(rs)}")

    print("\n=== BY CALL TYPE (index/macro vs single-name) ===")
    for label, pred in [
        ("index/macro", lambda r: r["ticker"] in INDEX_SET),
        ("single-name", lambda r: r["ticker"] not in INDEX_SET),
    ]:
        rs = [r for r in scored if pred(r)]
        print(label, count_verdicts(rs), f"n_scored={len(rs)}")

    print("\n=== WORST 5 MISSES (WRONG, most negative signed move) ===")
    wrong = [r for r in scored if r["verdict"] == "WRONG"]

    def signed_move(r):
        m = r["move_at_verdict_horizon"]
        if r["direction"] in ("bullish", "bearish"):
            return DIRECTION_SIGN[r["direction"]] * m
        return -abs(m)

    for r in sorted(wrong, key=signed_move)[:5]:
        print(
            f"{r['call_id']} {r['ticker']} {r['as_of_date']} dir={r['direction']} T+{r['verdict_horizon_td']} move={r['move_at_verdict_horizon']:.4f} signed={signed_move(r):.4f}"
        )

    print("\n=== BEST 3 HITS (RIGHT, most positive signed move) ===")
    right = [r for r in scored if r["verdict"] == "RIGHT"]
    for r in sorted(right, key=signed_move, reverse=True)[:3]:
        print(
            f"{r['call_id']} {r['ticker']} {r['as_of_date']} dir={r['direction']} T+{r['verdict_horizon_td']} move={r['move_at_verdict_horizon']:.4f} signed={signed_move(r):.4f}"
        )

    print("\n=== T+1 vs T+21 VERDICT FLIPS ===")
    flips = 0
    both_avail = 0
    for r in rows:
        if r.get("status") not in ("SCORED",):
            continue
        h = r["horizons"]
        if h["T1"]["incomplete"] or h["T21"]["incomplete"]:
            continue
        both_avail += 1
        d = r["direction"]

        def verdict_at(ret):
            if d in ("bullish", "bearish"):
                signed = DIRECTION_SIGN[d] * ret
                if signed >= NOISE_BAND:
                    return "RIGHT"
                elif signed <= -NOISE_BAND:
                    return "WRONG"
                return "NEUTRAL"
            else:
                return "RIGHT" if abs(ret) < NOISE_BAND else "WRONG"

        v1 = verdict_at(h["T1"]["return"])
        v21 = verdict_at(h["T21"]["return"])
        if v1 != v21:
            flips += 1
    print(f"{flips} flips out of {both_avail} calls with both T+1 and T+21 available")

    print("\n=== DISAGREEMENTS WITH prior_verdict ===")
    for r in rows:
        if r.get("disagrees_with_prior"):
            print(
                f"{r['call_id']} {r['ticker']}: computed={r['verdict']} prior_parsed={r['prior_verdict_parsed']} | prior_raw={r['prior_verdict_raw']!r}"
            )

    print("\n=== SIGMA TABLE (ticker, daily sigma June, 2% in sigma units @T+5) ===")
    for t in sorted(ticker_sigma):
        s = ticker_sigma[t]
        if s is None:
            print(f"{t}: no June sigma (insufficient data)")
            continue
        band_sigma_units = NOISE_BAND / (s * math.sqrt(5))
        print(
            f"{t}: daily_sigma={s:.4f} ({s * 100:.2f}%) | 2% band @T+5 = {band_sigma_units:.2f}sigma"
        )

    print("\n=== UNSCOREABLE ROWS (no price data) ===")
    for r in unscoreable:
        print(
            f"{r['call_id']} {r['ticker']}: {r.get('reason', r.get('reason_no_verdict', ''))}"
        )

    print("\n=== VOL_UP / VOL_DOWN PROXY ROWS (realized vol next5 vs prior20) ===")
    for r in vol_proxy_rows:
        vp = r.get("vol_proxy", {})
        print(
            f"{r['call_id']} {r['ticker']} ({r['direction']}) {r['as_of_date']}: "
            f"prior20_sigma={vp.get('rv_prior20_daily_sigma')} next5_sigma={vp.get('rv_next5_daily_sigma')} "
            f"expansion={vp.get('rv_expansion')}"
        )

    print("\n=== SANITY FLAGS (spot_at_call vs series close mismatch >5%) ===")
    for r in rows:
        if r.get("sanity_flag"):
            print(f"{r['call_id']} {r['ticker']}: {r['sanity_flag']}")


if __name__ == "__main__":
    main()
