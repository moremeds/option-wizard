"""Empirical convex macro hedge analysis.

Pulls SPX/SPY/QQQ/IWM/VIX historical data, prices put-ratio backspreads,
VIX call structures, and baseline (fly/spread/long-put) via BSM with that
day's ATM IV. Computes convexity ratios at peak vol days across 4 anchor
events plus 2017/2023 false-positive carry years.

All option prices are BSM estimates. Realized vol/IV uses VIX (^VIX) as
ATM 30d proxy for SPX, VIX9D for short-tenor VIX option IV proxy.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm

OUT = Path(__file__).parent
RISK_FREE = 0.04  # rough constant; sensitivity is tiny vs vega for short tenor

# ---- BSM ------------------------------------------------------------------


def bs_put(spot, strike, T, sigma, r=RISK_FREE):
    if T <= 0 or sigma <= 0:
        return max(strike - spot, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return strike * math.exp(-r * T) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def bs_call(spot, strike, T, sigma, r=RISK_FREE):
    if T <= 0 or sigma <= 0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return spot * norm.cdf(d1) - strike * math.exp(-r * T) * norm.cdf(d2)


def bs_put_greeks(spot, strike, T, sigma, r=RISK_FREE):
    if T <= 0 or sigma <= 0:
        return dict(delta=-1 if strike > spot else 0, gamma=0, vega=0, theta=0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    delta = norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (spot * sigma * math.sqrt(T))
    vega = spot * norm.pdf(d1) * math.sqrt(T) / 100.0  # per 1 vol pt
    theta = (
        -(spot * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
        + r * strike * math.exp(-r * T) * norm.cdf(-d2)
    ) / 365.0
    return dict(delta=delta, gamma=gamma, vega=vega, theta=theta)


def bs_call_greeks(spot, strike, T, sigma, r=RISK_FREE):
    if T <= 0 or sigma <= 0:
        return dict(delta=0, gamma=0, vega=0, theta=0)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    delta = norm.cdf(d1)
    gamma = norm.pdf(d1) / (spot * sigma * math.sqrt(T))
    vega = spot * norm.pdf(d1) * math.sqrt(T) / 100.0
    theta = (
        -(spot * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
        - r * strike * math.exp(-r * T) * norm.cdf(d2)
    ) / 365.0
    return dict(delta=delta, gamma=gamma, vega=vega, theta=theta)


# ---- Data -----------------------------------------------------------------

TICKERS = [
    "^GSPC",
    "^SPX",
    "SPY",
    "QQQ",
    "IWM",
    "^RUT",
    "^VIX",
    "^VIX9D",
    "^VIX3M",
    "^VVIX",
    "^SKEW",
    "ES=F",
]


def fetch_panel(start="2011-01-01", end="2024-12-31"):
    panel = {}
    for t in TICKERS:
        try:
            df = yf.download(t, start=start, end=end, progress=False, auto_adjust=False)
            if df.empty:
                print(f"  empty: {t}")
                continue
            # flatten multiindex columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            panel[t] = df
            print(f"  {t}: {len(df)} rows {df.index[0].date()} → {df.index[-1].date()}")
        except Exception as e:
            print(f"  FAIL {t}: {e}")
    return panel


def get_close(panel, ticker, dt):
    df = panel.get(ticker)
    if df is None:
        return None
    idx = df.index
    # find idx <= dt
    sub = df[df.index <= pd.Timestamp(dt)]
    if sub.empty:
        return None
    return float(sub["Close"].iloc[-1])


def get_row(panel, ticker, dt):
    df = panel.get(ticker)
    if df is None:
        return None
    sub = df[df.index <= pd.Timestamp(dt)]
    if sub.empty:
        return None
    return sub.iloc[-1]


def trading_offset(panel, ref_ticker, ref_date, days):
    """Return business-day offset using actual trading calendar from ref_ticker.
    days>0 forward, days<0 backward."""
    df = panel[ref_ticker]
    idx = df.index
    pos = idx.get_indexer([pd.Timestamp(ref_date)], method="nearest")[0]
    new_pos = pos + days
    if new_pos < 0 or new_pos >= len(idx):
        return None
    return idx[new_pos].date().isoformat()


# ---- Anchor events --------------------------------------------------------


@dataclass
class Event:
    name: str
    peak_date: str  # peak VIX close day
    drawdown_label: str


EVENTS = [
    # 2011 US debt downgrade — S&P cut US AAA on Aug 5 after Friday close;
    # crash on Monday Aug 8. NOTE: ^VIX9D was launched July 2011, so the
    # T-5 / T-10 lookback may have sparse/missing data for this event.
    Event("2011-08-08 US debt downgrade", "2011-08-08", "fast crash"),
    # 2015 China devaluation Black Monday — yuan devalued Aug 11,
    # culminating in -3.9% SPX on Aug 24 + flash-crash open.
    Event("2015-08-24 China Black Monday", "2015-08-24", "fast crash"),
    Event("2018-02-05 Volmageddon", "2018-02-05", "fast spike"),
    Event("2020-03-16 COVID-1", "2020-03-16", "crash"),
    Event("2020-03-23 COVID-2", "2020-03-23", "crash bottom"),
    Event("2022-03-08 hike-cycle", "2022-03-08", "grind"),
    Event("2024-08-05 JPY unwind", "2024-08-05", "fast spike"),
]


# ---- Structures -----------------------------------------------------------


def price_put_legs(spot, sigma, T, legs):
    """legs: list of (qty_signed, strike_pct).  qty>0 = long, qty<0 = short.
    Returns (net_cost_per_unit, greeks_dict)."""
    total = 0.0
    g = dict(delta=0, gamma=0, vega=0, theta=0)
    leg_prices = []
    for qty, kpct in legs:
        K = spot * kpct
        p = bs_put(spot, K, T, sigma)
        leg_prices.append(p)
        # cost convention: long(qty>0) PAYS p, so add to cost
        total += qty * p
        gk = bs_put_greeks(spot, K, T, sigma)
        for k in g:
            g[k] += qty * gk[k]
    return total, g, leg_prices


def price_call_legs(spot, sigma, T, legs):
    total = 0.0
    g = dict(delta=0, gamma=0, vega=0, theta=0)
    leg_prices = []
    for qty, K_dollar in legs:
        p = bs_call(spot, K_dollar, T, sigma)
        leg_prices.append(p)
        total += qty * p
        gk = bs_call_greeks(spot, K_dollar, T, sigma)
        for k in g:
            g[k] += qty * gk[k]
    return total, g, leg_prices


# Structure definitions: each returns (legs_at_entry, payoff_at_peak)
# legs format for puts: list of (qty, strike_pct) on the UNDERLYING
# For VIX calls: (qty, strike_dollar) on VIX index


def value_put_structure(spot_now, sigma_now, T_now, legs_strikes_dollar):
    """Value put structure given current spot/sigma/T and dollar strikes."""
    total = 0.0
    g = dict(delta=0, gamma=0, vega=0, theta=0)
    for qty, K in legs_strikes_dollar:
        p = bs_put(spot_now, K, T_now, sigma_now)
        total += qty * p
        gk = bs_put_greeks(spot_now, K, T_now, sigma_now)
        for k in g:
            g[k] += qty * gk[k]
    return total, g


def value_call_structure(spot_now, sigma_now, T_now, legs_strikes_dollar):
    total = 0.0
    g = dict(delta=0, gamma=0, vega=0, theta=0)
    for qty, K in legs_strikes_dollar:
        p = bs_call(spot_now, K, T_now, sigma_now)
        total += qty * p
        gk = bs_call_greeks(spot_now, K, T_now, sigma_now)
        for k in g:
            g[k] += qty * gk[k]
    return total, g


# ---- Per-event evaluation ------------------------------------------------

NOTIONAL = 1_000_000

UNDERLYINGS = {
    "SPX": dict(spot_ticker="^GSPC", iv_ticker="^VIX", multiplier=100),
    "SPY": dict(
        spot_ticker="SPY", iv_ticker="^VIX", multiplier=100
    ),  # SPY IV close to SPX IV in normal regimes
    "QQQ": dict(
        spot_ticker="QQQ", iv_ticker="^VXN", multiplier=100
    ),  # but VXN may not be on yfinance; fallback below
    "IWM": dict(spot_ticker="IWM", iv_ticker="^RVX", multiplier=100),  # RVX
}

# VXN/RVX may not be available; we proxy by VIX * vol_beta if missing.
# Empirically vol_beta for QQQ ~1.1-1.2 vs SPX, IWM ~1.2-1.4. We'll estimate per event.


def event_iv_for_underlying(panel, underlying, entry_date):
    """Return ATM IV proxy for underlying at entry_date (annualized vol pts/100)."""
    cfg = UNDERLYINGS[underlying]
    vix_row = get_close(panel, "^VIX", entry_date)
    if underlying in ("SPX", "SPY"):
        return vix_row / 100.0
    # For QQQ/IWM we approximate using historical IV ratio observed near event:
    # use 60-day realized vol ratio of underlying vs SPX as a proxy for IV ratio.
    spx = panel["^GSPC"]
    spx = spx[spx.index <= pd.Timestamp(entry_date)].tail(60)
    u_df = panel[cfg["spot_ticker"]]
    u_df = u_df[u_df.index <= pd.Timestamp(entry_date)].tail(60)
    if len(spx) < 30 or len(u_df) < 30:
        return vix_row / 100.0
    spx_ret = np.log(spx["Close"]).diff().dropna()
    u_ret = np.log(u_df["Close"]).diff().dropna()
    rv_spx = spx_ret.std() * np.sqrt(252)
    rv_u = u_ret.std() * np.sqrt(252)
    if rv_spx <= 0:
        return vix_row / 100.0
    beta = rv_u / rv_spx
    return (vix_row / 100.0) * beta


def run_event_structures(panel, event):
    """For one event, evaluate every structure × underlying combo.
    Entry = T-5 trading days before peak. Peak = event.peak_date.
    Exit = peak_date close."""
    peak = event.peak_date
    entry = trading_offset(panel, "^VIX", peak, -5)
    # We'll price options at 35 DTE so they have life left at peak.
    entry_T_days = 35
    exit_T_days = entry_T_days - 5

    rows = []

    # ---- Put structures over SPX/SPY/QQQ/IWM ----
    for underlying in ["SPX", "SPY", "QQQ", "IWM"]:
        cfg = UNDERLYINGS[underlying]
        spot_entry = get_close(panel, cfg["spot_ticker"], entry)
        spot_peak = get_close(panel, cfg["spot_ticker"], peak)
        if spot_entry is None or spot_peak is None:
            continue
        iv_entry = event_iv_for_underlying(panel, underlying, entry)
        iv_peak = event_iv_for_underlying(panel, underlying, peak)

        # Compute qty based on $1M notional
        # qty_contracts ~ NOTIONAL / (spot_entry * multiplier) but for index puts we just size to 1 unit and report cost/payoff in absolute $ per unit
        # We use NOTIONAL/spot_entry shares equivalent -> contracts = NOTIONAL/(spot_entry*100)
        contracts = NOTIONAL / (spot_entry * cfg["multiplier"])
        # round to nearest contract for realism (but for cost ratio doesn't matter)
        contracts_round = max(1, int(round(contracts)))

        structures = []
        # BASE1: put butterfly long 1× -2% / short 2× -5% / long 1× -8%
        structures.append(("Fly -2/-5/-8", [(+1, 0.98), (-2, 0.95), (+1, 0.92)]))
        # BASE2: put spread long ATM / short -10%
        structures.append(("PutSpread ATM/-10", [(+1, 1.00), (-1, 0.90)]))
        # BASE3: single long put -10%
        structures.append(("LongPut -10", [(+1, 0.90)]))
        # PRB Config 1: short 1× at -8% / long 2× at -15%
        structures.append(("Ratio2x1 -8/-15", [(-1, 0.92), (+2, 0.85)]))
        # PRB Config 2: short 1× at -10% / long 2× at -20%
        structures.append(("Ratio2x1 -10/-20", [(-1, 0.90), (+2, 0.80)]))

        for name, legs_pct in structures:
            # entry valuation
            strikes_dollar = [(q, spot_entry * kpct) for q, kpct in legs_pct]
            cost_per_unit, g_entry = value_put_structure(
                spot_entry, iv_entry, entry_T_days / 365, strikes_dollar
            )
            # peak valuation -- STRIKES UNCHANGED (we hold the structure)
            peak_value_per_unit, _ = value_put_structure(
                spot_peak, iv_peak, exit_T_days / 365, strikes_dollar
            )

            # cost in $ for $1M book
            cost_total = cost_per_unit * contracts_round * cfg["multiplier"]
            peak_pnl = (
                (peak_value_per_unit - cost_per_unit)
                * contracts_round
                * cfg["multiplier"]
            )
            peak_value = peak_value_per_unit * contracts_round * cfg["multiplier"]

            # Convexity ratio = peak_value / cost (gross), if cost > 0
            # if structure is net-credit (cost<=0) and peak_value>0 that's "free"; flag
            if cost_total > 0:
                conv = peak_value / cost_total
            else:
                conv = float("inf") if peak_value > 0 else 0.0

            # annualized cost pct
            ann_pct = (
                (cost_total / NOTIONAL) / (entry_T_days / 365.0) * 100
                if entry_T_days > 0
                else 0
            )

            rows.append(
                dict(
                    event=event.name,
                    underlying=underlying,
                    structure=name,
                    entry=entry,
                    peak=peak,
                    spot_entry=round(spot_entry, 2),
                    spot_peak=round(spot_peak, 2),
                    spx_dd_pct=round((spot_peak / spot_entry - 1) * 100, 2),
                    iv_entry=round(iv_entry * 100, 1),
                    iv_peak=round(iv_peak * 100, 1),
                    contracts=contracts_round,
                    cost_per_unit=round(cost_per_unit, 2),
                    cost_total=round(cost_total, 0),
                    ann_cost_pct=round(ann_pct, 2),
                    peak_value_per_unit=round(peak_value_per_unit, 2),
                    peak_value_total=round(peak_value, 0),
                    peak_pnl=round(peak_pnl, 0),
                    convexity=round(conv, 2) if math.isfinite(conv) else "inf",
                    delta=round(g_entry["delta"], 3),
                    gamma=round(g_entry["gamma"] * 1000, 3),
                    vega=round(g_entry["vega"], 2),
                    theta=round(g_entry["theta"], 2),
                    provenance="BSM estimate, not listed mid",
                )
            )

    # ---- VIX structures ----
    # PROXY: VIX options price off VX futures, not spot VIX. We approximate
    # the front-month VX future as 0.5*VIX + 0.5*VIX3M (captures contango in
    # normal regimes, collapses to VIX in backwardation). VVIX/100 = IV proxy.
    # This is still imperfect — sell-side prices are pricier in calm regimes
    # because VX1 > VIX, AND vol skew on VIX calls is steep — but it's an
    # upper bound on convexity (a lower bound on cost) for low-vol entries.
    vix_entry = get_close(panel, "^VIX", entry)
    vix_peak = get_close(panel, "^VIX", peak)
    vix3m_entry = get_close(panel, "^VIX3M", entry) or vix_entry
    vix3m_peak = get_close(panel, "^VIX3M", peak) or vix_peak
    vx1_entry = 0.5 * vix_entry + 0.5 * vix3m_entry  # front-month future proxy
    vx1_peak = 0.5 * vix_peak + 0.5 * vix3m_peak
    vvix_entry = get_close(panel, "^VVIX", entry)
    vvix_peak = get_close(panel, "^VVIX", peak)
    iv_vix_entry = (vvix_entry or 90) / 100.0
    iv_vix_peak = (vvix_peak or 90) / 100.0
    # Use VX1 proxy as the underlying for all VIX option calculations
    vix_entry_und = vx1_entry
    vix_peak_und = vx1_peak

    # B: VIX front-week single call, 7 DTE, K=25 or K=30
    # NOTE: VIX options track VX FUTURES, not spot VIX. As an empirical approximation
    # we use VIX itself as the underlying with VVIX as IV; this overstates moneyness
    # because front-week future ≠ spot. We will document this gap explicitly.
    # We test 5 DTE entry (so it has 5 days at peak too).
    for K in [25.0, 30.0]:
        T_entry = 7 / 365
        T_peak = 2 / 365
        c_entry = bs_call(vix_entry_und, K, T_entry, iv_vix_entry)
        c_peak = bs_call(vix_peak_und, K, T_peak, iv_vix_peak)
        # $1M book sizing: define hedge spend ~ 0.5% NLV initial cost
        # for VIX option, multiplier=100, contracts = floor(target_cost / (c_entry*100))
        target_spend = NOTIONAL * 0.005  # 0.5% bucket
        if c_entry > 0.01:
            contracts_v = max(1, int(target_spend / (c_entry * 100)))
        else:
            contracts_v = 0
        cost_total = c_entry * contracts_v * 100
        peak_value = c_peak * contracts_v * 100
        peak_pnl = peak_value - cost_total
        conv = peak_value / cost_total if cost_total > 0 else 0
        ann_pct = (cost_total / NOTIONAL) / (T_entry) * 100
        # greeks
        gk = bs_call_greeks(vix_entry_und, K, T_entry, iv_vix_entry)
        rows.append(
            dict(
                event=event.name,
                underlying="VIX",
                structure=f"WeeklyCall K={K}",
                entry=entry,
                peak=peak,
                spot_entry=round(vix_entry_und, 2),
                spot_peak=round(vix_peak_und, 2),
                spx_dd_pct=round((vix_peak_und / vix_entry_und - 1) * 100, 2),
                iv_entry=round(iv_vix_entry * 100, 1),
                iv_peak=round(iv_vix_peak * 100, 1),
                contracts=contracts_v,
                cost_per_unit=round(c_entry, 2),
                cost_total=round(cost_total, 0),
                ann_cost_pct=round(ann_pct, 2),
                peak_value_per_unit=round(c_peak, 2),
                peak_value_total=round(peak_value, 0),
                peak_pnl=round(peak_pnl, 0),
                convexity=round(conv, 2),
                delta=round(gk["delta"], 3),
                gamma=round(gk["gamma"] * 1000, 3),
                vega=round(gk["vega"], 2),
                theta=round(gk["theta"], 2),
                provenance="BSM-on-spot-VIX estimate (overstates true tracking — VIX options price off VX future)",
            )
        )

    # C: VIX OTM call ladder 25+35+45 at 30 DTE
    T_entry = 30 / 365
    T_peak = 25 / 365
    legs = [(1, 25.0), (1, 35.0), (1, 45.0)]
    cost_per_unit, g_entry, _ = price_call_legs(
        vix_entry_und, iv_vix_entry, T_entry, legs
    )
    peak_val_per, _, _ = price_call_legs(vix_peak_und, iv_vix_peak, T_peak, legs)
    target_spend = NOTIONAL * 0.005
    if cost_per_unit > 0.01:
        contracts_v = max(1, int(target_spend / (cost_per_unit * 100)))
    else:
        contracts_v = 0
    cost_total = cost_per_unit * contracts_v * 100
    peak_value = peak_val_per * contracts_v * 100
    peak_pnl = peak_value - cost_total
    conv = peak_value / cost_total if cost_total > 0 else 0
    ann_pct = (cost_total / NOTIONAL) / T_entry * 100
    rows.append(
        dict(
            event=event.name,
            underlying="VIX",
            structure="Ladder 25+35+45 (30DTE)",
            entry=entry,
            peak=peak,
            spot_entry=round(vix_entry, 2),
            spot_peak=round(vix_peak, 2),
            spx_dd_pct=round((vix_peak / vix_entry - 1) * 100, 2),
            iv_entry=round(iv_vix_entry * 100, 1),
            iv_peak=round(iv_vix_peak * 100, 1),
            contracts=contracts_v,
            cost_per_unit=round(cost_per_unit, 2),
            cost_total=round(cost_total, 0),
            ann_cost_pct=round(ann_pct, 2),
            peak_value_per_unit=round(peak_val_per, 2),
            peak_value_total=round(peak_value, 0),
            peak_pnl=round(peak_pnl, 0),
            convexity=round(conv, 2),
            delta=round(g_entry["delta"], 3),
            gamma=round(g_entry["gamma"] * 1000, 3),
            vega=round(g_entry["vega"], 2),
            theta=round(g_entry["theta"], 2),
            provenance="BSM-on-spot-VIX estimate (overstates true tracking — VIX options price off VX future)",
        )
    )

    return rows


# ---- 24h overnight analysis ----------------------------------------------


def overnight_decomposition(panel, event):
    """For ES=F across T-5..peak window, compute overnight vs intraday return.
    overnight = (open[t] / close[t-1] - 1)
    intraday  = (close[t] / open[t] - 1)
    Returns dict with totals."""
    peak = event.peak_date
    entry = trading_offset(panel, "^VIX", peak, -5)
    es = panel.get("ES=F")
    if es is None:
        return None
    sub = es[(es.index >= pd.Timestamp(entry)) & (es.index <= pd.Timestamp(peak))]
    if len(sub) < 2:
        return None
    es_full = es.copy()
    overnight_rets = []
    intraday_rets = []
    for i, dt in enumerate(sub.index):
        pos = es_full.index.get_loc(dt)
        if pos == 0:
            continue
        prev_close = es_full["Close"].iloc[pos - 1]
        today_open = sub["Open"].iloc[i]
        today_close = sub["Close"].iloc[i]
        on = today_open / prev_close - 1
        intr = today_close / today_open - 1
        overnight_rets.append(on)
        intraday_rets.append(intr)
    total_on = sum(overnight_rets)
    total_intr = sum(intraday_rets)
    abs_on = sum(abs(x) for x in overnight_rets)
    abs_intr = sum(abs(x) for x in intraday_rets)
    return dict(
        event=event.name,
        entry=entry,
        peak=peak,
        sum_overnight=round(total_on * 100, 2),
        sum_intraday=round(total_intr * 100, 2),
        abs_overnight=round(abs_on * 100, 2),
        abs_intraday=round(abs_intr * 100, 2),
        pct_total_overnight=round(100 * abs_on / (abs_on + abs_intr + 1e-9), 1),
        n_sessions=len(overnight_rets),
    )


# ---- False-positive carry -------------------------------------------------


def calm_year_carry(panel, year):
    """Roll each structure monthly through `year` and sum total $ cost on $1M book.
    Use SPX put structures (entry on month-end), VIX ladder, etc.
    Each leg held to expiry; structures expire worthless if SPX doesn't tank
    (we set payoff=0 if struck OTM)."""
    spx = panel["^GSPC"]
    vix = panel["^VIX"]
    vvix = panel.get("^VVIX")
    months = pd.date_range(start=f"{year}-01-01", end=f"{year}-12-31", freq="MS")
    structures = {
        "Fly -2/-5/-8": [(+1, 0.98), (-2, 0.95), (+1, 0.92)],
        "PutSpread ATM/-10": [(+1, 1.00), (-1, 0.90)],
        "LongPut -10": [(+1, 0.90)],
        "Ratio2x1 -8/-15": [(-1, 0.92), (+2, 0.85)],
        "Ratio2x1 -10/-20": [(-1, 0.90), (+2, 0.80)],
    }
    results = {
        n: {"cost_pos": 0.0, "cost_neg": 0.0, "realized_pnl": 0.0, "months": 0}
        for n in structures
    }
    results["VIXLadder 25+35+45"] = {
        "cost_pos": 0.0,
        "cost_neg": 0.0,
        "realized_pnl": 0.0,
        "months": 0,
    }
    results["VIXWeekly 25C"] = {
        "cost_pos": 0.0,
        "cost_neg": 0.0,
        "realized_pnl": 0.0,
        "months": 0,
    }

    for m_start in months:
        # entry = first trading day on/after m_start
        spx_sub = spx[spx.index >= m_start]
        if spx_sub.empty:
            continue
        entry_dt = spx_sub.index[0]
        spot = float(spx_sub["Close"].iloc[0])
        # 35 DTE -> ~ next month's 3rd Friday; we use 35 calendar days exact for BSM
        exit_dt_target = entry_dt + timedelta(days=35)
        # find exit row
        spx_exit = spx[spx.index >= exit_dt_target]
        if spx_exit.empty:
            continue
        exit_dt = spx_exit.index[0]
        spot_exit = float(spx_exit["Close"].iloc[0])
        iv = float(vix[vix.index <= entry_dt]["Close"].iloc[-1]) / 100
        T_entry = (exit_dt - entry_dt).days / 365
        T_exit = 0  # held to expiry effectively for cost analysis

        contracts = max(1, int(round(NOTIONAL / (spot * 100))))

        for name, legs in structures.items():
            strikes = [(q, spot * kpct) for q, kpct in legs]
            cost_pu, _ = value_put_structure(spot, iv, T_entry, strikes)
            cost_total = cost_pu * contracts * 100
            # payoff at expiry: for each leg, qty*max(K-spot_exit,0)
            payoff_pu = sum(q * max(K - spot_exit, 0) for q, K in strikes)
            payoff_total = payoff_pu * contracts * 100
            pnl = payoff_total - cost_total
            if cost_total > 0:
                results[name]["cost_pos"] += cost_total
            else:
                results[name]["cost_neg"] += cost_total  # net credit received
            results[name]["realized_pnl"] += pnl
            results[name]["months"] += 1

        # VIX structures
        v = float(vix[vix.index <= entry_dt]["Close"].iloc[-1])
        v_exit = float(vix[vix.index <= exit_dt]["Close"].iloc[-1])
        iv_v_entry = (
            float(
                (
                    vvix[vvix.index <= entry_dt]["Close"].iloc[-1]
                    if vvix is not None and not vvix[vvix.index <= entry_dt].empty
                    else 90
                )
            )
            / 100
        )
        # Ladder 25+35+45 30DTE
        cost_pu, _, _ = price_call_legs(
            v, iv_v_entry, 30 / 365, [(1, 25), (1, 35), (1, 45)]
        )
        target_spend = NOTIONAL * 0.005
        contracts_v = (
            max(1, int(target_spend / (cost_pu * 100))) if cost_pu > 0.01 else 0
        )
        cost_total = cost_pu * contracts_v * 100
        payoff_pu = max(v_exit - 25, 0) + max(v_exit - 35, 0) + max(v_exit - 45, 0)
        payoff_total = payoff_pu * contracts_v * 100
        pnl = payoff_total - cost_total
        results["VIXLadder 25+35+45"]["cost_pos"] += cost_total
        results["VIXLadder 25+35+45"]["realized_pnl"] += pnl
        results["VIXLadder 25+35+45"]["months"] += 1

        # Weekly 25C, 7DTE, roll weekly approx as monthly*4 spend
        # Simplified: 4 rolls/month
        cost_pu_w = bs_call(v, 25, 7 / 365, iv_v_entry)
        contracts_w = (
            max(1, int(target_spend / (cost_pu_w * 100))) if cost_pu_w > 0.01 else 0
        )
        # We approximate weekly carry by sampling exit at +7 days vs entry, four times
        weekly_pnl = 0
        weekly_cost = 0
        for wk in range(4):
            wk_entry_target = entry_dt + timedelta(days=7 * wk)
            wk_exit_target = entry_dt + timedelta(days=7 * (wk + 1))
            wk_entry_rows = vix[vix.index >= wk_entry_target]
            wk_exit_rows = vix[vix.index >= wk_exit_target]
            if wk_entry_rows.empty or wk_exit_rows.empty:
                continue
            v0 = float(wk_entry_rows["Close"].iloc[0])
            v1 = float(wk_exit_rows["Close"].iloc[0])
            iv0 = (
                float(
                    (
                        vvix[vvix.index <= wk_entry_rows.index[0]]["Close"].iloc[-1]
                        if vvix is not None
                        and not vvix[vvix.index <= wk_entry_rows.index[0]].empty
                        else 90
                    )
                )
                / 100
            )
            c0 = bs_call(v0, 25, 7 / 365, iv0)
            cw = max(1, int(target_spend / (c0 * 100))) if c0 > 0.01 else 0
            wk_cost = c0 * cw * 100
            wk_payoff = max(v1 - 25, 0) * cw * 100
            weekly_cost += wk_cost
            weekly_pnl += wk_payoff - wk_cost
        results["VIXWeekly 25C"]["cost_pos"] += weekly_cost
        results["VIXWeekly 25C"]["realized_pnl"] += weekly_pnl
        results["VIXWeekly 25C"]["months"] += 1

    out = []
    for name, r in results.items():
        out.append(
            dict(
                year=year,
                structure=name,
                n_periods=r["months"],
                total_premium_paid=round(r["cost_pos"], 0),
                total_credit_received=round(-r["cost_neg"], 0)
                if r["cost_neg"] < 0
                else 0,
                realized_pnl=round(r["realized_pnl"], 0),
                realized_pnl_pct_nlv=round(r["realized_pnl"] / NOTIONAL * 100, 3),
            )
        )
    return out


# ---- Regime preconditions -------------------------------------------------


def precondition_signals(panel, event):
    peak = event.peak_date
    t10 = trading_offset(panel, "^VIX", peak, -10)
    rows = []
    for label, offset in [("T-10", -10), ("T-5", -5), ("T-2", -2)]:
        dt = trading_offset(panel, "^VIX", peak, offset)
        if dt is None:
            continue
        v = get_close(panel, "^VIX", dt)
        v9 = get_close(panel, "^VIX9D", dt)
        v3m = get_close(panel, "^VIX3M", dt)
        vv = get_close(panel, "^VVIX", dt)
        sk = get_close(panel, "^SKEW", dt)
        # RV21d on SPX
        spx_hist = panel["^GSPC"][panel["^GSPC"].index <= pd.Timestamp(dt)].tail(22)
        rv21 = (
            float(np.log(spx_hist["Close"]).diff().dropna().std() * np.sqrt(252)) * 100
            if len(spx_hist) > 5
            else None
        )
        vrp = (v - rv21) if (v is not None and rv21 is not None) else None

        rows.append(
            dict(
                event=event.name,
                day=label,
                date=dt,
                VIX=round(v, 2) if v else None,
                VIX9D=round(v9, 2) if v9 else None,
                VIX3M=round(v3m, 2) if v3m else None,
                VVIX=round(vv, 2) if vv else None,
                SKEW=round(sk, 2) if sk else None,
                RV21d=round(rv21, 2) if rv21 else None,
                VRP=round(vrp, 2) if vrp else None,
                VIX9D_over_VIX=round(v9 / v, 3) if (v9 and v) else None,
                VIX_over_VIX3M=round(v / v3m, 3) if (v and v3m) else None,
            )
        )
    return rows


# ---- Cross-index drawdown -------------------------------------------------


def cross_index_drawdowns(panel, event):
    peak = event.peak_date
    entry = trading_offset(panel, "^VIX", peak, -5)
    out = dict(event=event.name, entry=entry, peak=peak)
    for u in ["^GSPC", "SPY", "QQQ", "IWM", "^RUT"]:
        s_e = get_close(panel, u, entry)
        s_p = get_close(panel, u, peak)
        if s_e and s_p:
            out[f"{u}_dd_pct"] = round((s_p / s_e - 1) * 100, 2)
    # IV ratios
    vix_e = get_close(panel, "^VIX", entry)
    # estimate IV ratios for QQQ and IWM using 60d RV ratio at entry
    iv_qqq = event_iv_for_underlying(panel, "QQQ", entry)
    iv_iwm = event_iv_for_underlying(panel, "IWM", entry)
    iv_spx = vix_e / 100
    out["IV_QQQ_over_SPX"] = round(iv_qqq / iv_spx, 3)
    out["IV_IWM_over_SPX"] = round(iv_iwm / iv_spx, 3)
    # realized ratio
    if all(f in out for f in ["^GSPC_dd_pct", "QQQ_dd_pct", "IWM_dd_pct"]):
        denom_q = abs(out["^GSPC_dd_pct"]) if out["^GSPC_dd_pct"] else 1
        out["RealizedDD_QQQ_over_SPX"] = (
            round(abs(out["QQQ_dd_pct"]) / denom_q, 3) if denom_q else None
        )
        out["RealizedDD_IWM_over_SPX"] = (
            round(abs(out["IWM_dd_pct"]) / denom_q, 3) if denom_q else None
        )
        # "Free convexity" if realized > IV
        out["QQQ_free_convexity"] = (
            round(out["RealizedDD_QQQ_over_SPX"] - out["IV_QQQ_over_SPX"], 3)
            if denom_q
            else None
        )
        out["IWM_free_convexity"] = (
            round(out["RealizedDD_IWM_over_SPX"] - out["IV_IWM_over_SPX"], 3)
            if denom_q
            else None
        )
    return out


# ============================================================================
def main():
    print("Fetching data panel...")
    panel = fetch_panel(start="2011-01-01", end="2024-12-31")

    # Try VXN/RVX too
    for t in ["^VXN", "^RVX"]:
        try:
            df = yf.download(
                t,
                start="2011-01-01",
                end="2024-12-31",
                progress=False,
                auto_adjust=False,
            )
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0] for c in df.columns]
                panel[t] = df
                print(f"  {t}: {len(df)} rows")
        except Exception as e:
            print(f"  failed {t}: {e}")

    all_struct_rows = []
    all_overnight = []
    all_precond = []
    all_xindex = []

    for ev in EVENTS:
        print(f"\n=== {ev.name} (peak {ev.peak_date}) ===")
        rows = run_event_structures(panel, ev)
        all_struct_rows.extend(rows)
        on = overnight_decomposition(panel, ev)
        if on:
            all_overnight.append(on)
            print(f"  overnight: {on}")
        pc = precondition_signals(panel, ev)
        all_precond.extend(pc)
        xi = cross_index_drawdowns(panel, ev)
        all_xindex.append(xi)
        print(f"  xindex: {xi}")

    # Carry years
    print("\n=== Carry: 2017 ===")
    carry17 = calm_year_carry(panel, 2017)
    print("\n=== Carry: 2023 ===")
    carry23 = calm_year_carry(panel, 2023)

    # Save everything
    pd.DataFrame(all_struct_rows).to_csv(OUT / "structures_by_event.csv", index=False)
    pd.DataFrame(all_overnight).to_csv(OUT / "overnight_decomp.csv", index=False)
    pd.DataFrame(all_precond).to_csv(OUT / "preconditions.csv", index=False)
    pd.DataFrame(all_xindex).to_csv(OUT / "cross_index_dd.csv", index=False)
    pd.DataFrame(carry17 + carry23).to_csv(OUT / "carry_2017_2023.csv", index=False)

    # Leaderboard
    df = pd.DataFrame(all_struct_rows)

    # exclude inf convexity (zero-cost weirdness) — flag separately
    def to_num(x):
        try:
            return float(x)
        except:
            return None

    df["conv_num"] = df["convexity"].apply(to_num)
    lb = (
        df.groupby(["structure", "underlying"])
        .agg(
            mean_conv=("conv_num", "mean"),
            median_conv=("conv_num", "median"),
            n=("conv_num", "count"),
            mean_ann_cost_pct=("ann_cost_pct", "mean"),
        )
        .sort_values("mean_conv", ascending=False)
        .reset_index()
    )
    lb.to_csv(OUT / "leaderboard.csv", index=False)
    print("\n=== LEADERBOARD ===")
    print(lb.to_string())

    print("\nDone. All CSVs written to", OUT)


if __name__ == "__main__":
    main()
