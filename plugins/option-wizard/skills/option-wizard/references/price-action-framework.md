# Price Action Framework

## TradingView entry

The skill never scrapes TradingView directly. Numeric vol/GEX/skew is
already covered by Unusual Whales (see `data-sources.md`). What TV is
used for is the qualitative chart read: trend posture, candle
absorption, news flow, watchlist-level positioning prior. The entry
point is the **`finance-data-providers:tradingview-reader`** skill,
which returns rendered text snapshots of charts and news.

Typical asks:

- `"TV snapshot ORCL daily, last 90 days, with SMA20 + SMA50 + SMA200,
  volume bars"` — returns a textual description of the chart plus
  the three moving averages and current spot vs each. Used to decide
  whether the ticker is above or below its 200DMA and whether the 50/200
  cross is recent.
- `"TV RSI 14 ORCL daily, last 30 days"` — returns the rolling RSI
  series. Watch for >70 (overbought, defer short-vol selling at the
  current strike) and <30 (oversold, look at long-only structures).
- `"TV MACD 12/26/9 ORCL daily"` — for divergence detection on
  multi-week swings.
- `"TV news ORCL last 7 days"` — pulls headline list; cross-reference
  against earnings calendar for catalyst clock.

The reader returns text, not images. Consume it qualitatively, not as
data to overlay on the Python analytics. Numeric inputs to
`scripts/fair_coupon.py::analyze_fcn` still come from UW (`iv`,
`iv_rank`, `skew_25d`, `max_drawdown_5y`).

## Trend signals

Above 200DMA is the default qualifier for selling premium on the
downside (CSP, bull put spread) — supportive trend reduces the
probability that the short put strike gets tested. Below 200DMA flips
the default toward selling premium on the upside (bear call spread).

The 50/200 cross (golden / death) is a tape signal but a slow one. For
option-wizard's 30-45 DTE horizon, weight the cross less than the
distance-to-200DMA measure:

| Distance to 200DMA | Bias for short-vol selling |
|---|---|
| > +10% | Strong bull — favor bull put, monthly CSP, jade lizard |
| 0 to +10% | Mild bull — bull put spread; avoid jade lizard absent conviction |
| 0 to −10% | Mild bear — bear call spread; defer CSP |
| < −10% | Strong bear — long put / put debit spread; refuse CSP |

Worked example: ORCL spot $245, 200DMA $215 → +14% above → strong bull
qualifier. Combined with IV rank 91 (RICH), the matrix in
`strategies.md` points to bull put spread or jade lizard (subject to
the four-signal veto check).

## Tape absorption

A catalyst gap-up (earnings beat, guidance raise, contract win) shows
up as a large opening candle. The question for the next 1-3 sessions
is whether the gap is **absorbed** (continued strength: close near
high, next session opens flat-to-up) or **faded** (close near low,
next session opens down).

Why it matters for option selection:

- **Absorbed:** real money is accumulating. Short premium on the
  downside (CSP, bull put) is asymmetric in your favor — the stock
  is unlikely to retest the pre-catalyst level. This is signal #1 of
  the four-item strong-bullish veto in `strategies.md`.
- **Faded:** initial reaction was sentiment-driven, not flow-driven.
  Sell upside premium (bear call spread, iron condor short call leg)
  with confidence the gap will not extend.

Read absorption by asking the TV reader for the daily chart of the
catalyst date + 3 sessions after, with closing price and volume. If
volume is heaviest on the gap day and tapers, that's typical accumulation.
If volume is heaviest on the second/third day with the price reversing,
that's a fade.

## News integration

Pull recent headlines (`TV news <ticker> last 7 days`) for two purposes:

1. **Catalyst clock.** Identify upcoming events (earnings within 30 days,
   FDA dates, conferences, lockup expirations). For short-premium
   positions, the catalyst should sit **outside** the position window
   — otherwise the gamma risk near expiry coincides with binary news
   risk. SKILL.md hard rule #4 (21 DTE blocking review) is the
   backstop, but ideally the catalyst is already excluded at entry.
2. **Thematic re-rate validation.** Headlines about secular demand
   (AI capex, GLP-1 demand) reinforce signal #3 of the bullish veto.
   Headlines about idiosyncratic risk (executive turnover, regulatory
   action, customer concentration) override the macro thesis.

Map headlines onto the position decision tree in
`scripts/evaluate_position.py` (see `references/execution.md` for
how that script feeds the daily report).

## Watchlists are not used

The trader organizes TradingView watchlists for their own reasons (sector
grouping, idea tracking) — membership and color flags do not encode any
directional or conviction signal. Do not pull `tradingview watchlists`
during analysis and do not treat list membership as a tiebreaker.
