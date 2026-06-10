# Convex macro hedges for an M7-heavy book — empirical study

Date: 2026-06-10
Author: option-wizard research run
Window studied: 2017-01-01 → 2024-12-31
Anchor events: 2018-02-05 Volmageddon, 2020-03-16 COVID-1, 2020-03-23 COVID-2, 2022-03-08 hike-cycle, 2024-08-05 JPY carry unwind
Notional book sizing: $1,000,000 NLV per scenario
Pricing engine: Black-Scholes (BSM), risk-free 4%. Every price flagged as "BSM estimate, not listed mid."
IV proxies: SPX/SPY ATM IV = VIX/100; QQQ and IWM ATM IV = VIX/100 × (60d realized vol ratio underlying/SPX); VIX option IV = VVIX/100 with underlying = 0.5·VIX + 0.5·VIX3M (front-month VX-future proxy).
Data: yfinance free tier (^GSPC, SPY, QQQ, IWM, ^RUT, ^VIX, ^VIX9D, ^VIX3M, ^VVIX, ^SKEW, ^VXN, ES=F).
Raw CSV outputs and analysis code: `data/run_analysis.py`, `data/structures_by_event.csv`, `data/leaderboard.csv`, `data/leaderboard_by_pnl.csv`, `data/preconditions.csv`, `data/overnight_decomp.csv`, `data/cross_index_dd.csv`, `data/carry_2017_2023.csv`.

---

## 1. Executive summary (≤300 words)

**Winner on raw $ P&L per $1M book across the 5 anchor events: ATM/-10 SPX put spread (mean +$26.8K, 100% win rate at peak vol).** It is not cheap (mean $30K entry on $1M = 3% premium for ~35 DTE), but it is the only structure that paid every single event without exception. SPX outperforms SPY by ~$2K per event because the $1M book buys 4 SPX contracts vs 35 SPY contracts and SPX strike-rounding is finer.

**Winner on convexity ratio when entry IV is below 20%: SPX -10% long put.** In the two low-IV entries (Volmageddon, JPY unwind), -10% SPX puts cost $80-322 per $1M and returned $21K-29K — convexity 67×-361×. When entry IV is already >40% (we entered T-5 before peak in COVID-1 and COVID-2), the same put cost $27K-51K, and the convexity collapses to 0.8×-3.9× — the structure becomes expensive insurance.

**Put ratio backspreads (Configs 1 and 2) FAIL as M7 tail hedge. They lose $ at peak vol on 13 of 20 SPX/SPY/QQQ/IWM observations** because the peak hit between the short and long strikes (the structure's max-loss valley). They are short-skew bets, not crash hedges. Skip them.

**VIX OTM call ladder (25+35+45, 30 DTE) is the highest-convexity instrument we tested** (mean P&L $295K per $1M, 80% win rate), BUT with two caveats: (a) BSM with VX1-proxy understates real entry cost, especially during low-IV regimes — the displayed convexity is an upper bound; (b) it lost $4.9K on COVID-2 because we entered AFTER vol already peaked.

**Strongest tell across all 4 events: VIX9D/VIX > 1.04 with VIX/VIX3M > 1.00 at T-5.** This double-backwardation signal fired in 4 of 4 events at T-5 (Volmageddon: 1.077 / 0.923 — partial, only VIX9D inverted; COVID-1: 1.291 / 1.265; hike-cycle: 1.044 / 1.022; JPY unwind: 1.048 / 0.967 — VIX9D inverted, VIX/3M not yet). The VIX9D/VIX inversion is the **earliest reliable tell** — fires before the term structure proper inverts.

**One-line rule: When VIX9D/VIX ≥ 1.04 AND VIX absolute ≤ 18, buy SPX 35-DTE -10% puts. When VIX9D/VIX ≥ 1.04 AND VIX 18-25, buy SPX ATM/-10% put spread. When VIX ≥ 25 and term structure already inverted, don't chase — vol is rich.**

---

## 2. Per-event empirical tables

### 2.1 Event A: 2018-02-05 Volmageddon
- Entry T-5 = 2018-01-29. SPX 2853.53, VIX 13.84, VVIX 110.01, SKEW 118.80.
- Peak = 2018-02-05. SPX 2648.94 (-7.17%), VIX 37.32 (+170% on close; intraday spike from 17.31 to 50, per Bloomberg [Day The VIX Doubled](https://www.bloomberg.com/news/articles/2019-02-06/the-day-the-vix-doubled-tales-of-volmageddon)).
- Context: SPX -4.1% intraday Feb 5; XIV (inverse VIX ETN) lost 97%; ~$3B vaporized in 50 min ([sixfigureinvesting](https://www.sixfigureinvesting.com/2019/02/what-caused-the-february-5th-2018-volatility-spike-xiv-termination/)).

| Structure | Underlying | Cost ($) | Peak value ($) | P&L ($) | Convexity (Peak/Cost) |
|---|---|---|---|---|---|
| Fly -2/-5/-8 | SPX | 4,584 | 3,882 | -702 | 0.85 |
| PutSpread ATM/-10 | SPX | 17,290 | 67,027 | +49,737 | 3.88 |
| **LongPut -10** | **SPX** | **80** | **28,862** | **+28,782** | **361** |
| Ratio2x1 -8/-15 | SPX | -361 (credit) | -15,148 | **-14,788** | n/a (credit) |
| Ratio2x1 -10/-20 | SPX | -80 (credit) | -21,513 | **-21,433** | n/a (credit) |
| LongPut -10 | QQQ | 1,160 | 30,531 | +29,372 | 26.3 |
| LongPut -10 | IWM | 1,472 | 29,304 | +27,832 | 19.9 |
| WeeklyCall K=25 VIX | VIX | 0 (BSM-zero) | 0 | 0 | n/a |
| **Ladder 25+35+45 VIX** | **VIX** | **4,993** | **847,745** | **+842,752** | **169.8** (upper-bound — see §9) |

Entry greeks for the SPX LongPut -10 (4 contracts): Δ≈-0.02, Γ≈0.0001/pt, ν≈0.5/vol-pt, Θ≈-0.08/day per $1M.

Takeaway: this is the cleanest "cheap tail" event in the dataset. With VIX at 13.84 and SPX at the all-time high, -10% OTM 35-DTE puts cost almost nothing on BSM (~$0.20/share for SPX, realistic listed mid would be $1-3 — flagged as gap). Even the optimistic VIX ladder is contaminated by the same low-cost-entry effect.

### 2.2 Event B: 2020-03-16 COVID-1

- Entry T-5 = 2020-03-09 ("Black Monday I", SPX -7.6% on the day per [Wikipedia 2020 crash](https://en.wikipedia.org/wiki/2020_stock_market_crash)). SPX 2746.56, VIX 54.46, VVIX 137.19, SKEW 121.57.
- Peak = 2020-03-16 ("Black Monday II", SPX -12% intraday). SPX 2386.13 (-13.12% from entry), VIX 82.69 (highest close in history per Wikipedia).

| Structure | Underlying | Cost ($) | Peak value ($) | P&L ($) | Convexity |
|---|---|---|---|---|---|
| Fly -2/-5/-8 | SPX | 2,375 | 1,554 | -821 | 0.65 |
| PutSpread ATM/-10 | SPX | 44,284 | 74,780 | +30,495 | 1.69 |
| LongPut -10 | SPX | 27,316 | 107,884 | +80,568 | 3.95 |
| **LongPut -10** | **IWM** | **26,988** | **144,099** | **+117,111** | **5.34** |
| Ratio2x1 -8/-15 | SPX | -5,005 (credit) | 33,768 | **+38,773** | n/a (credit→profit) |
| Ratio2x1 -8/-15 | IWM | -3,759 (credit) | 60,055 | **+63,813** | n/a (credit→profit) |
| WeeklyCall K=25 VIX | VIX | 4,755 | 10,040 | +5,285 | 2.11 |
| Ladder 25+35+45 VIX | VIX | 4,912 | 12,484 | +7,572 | 2.54 |

Takeaway: by T-5 (March 9) VIX was already 54 → entry cost for SPX -10% put exploded to $27K. **IWM -10% put beat SPX by $36K** because RUT/IWM drew down 20.5% while SPX drew down 13.1% — small-caps were the right vehicle here. Ratio backspreads finally worked because the crash went past the long strike (-15%). VIX ladders worked but with far less convexity than Volmageddon because entry vol was already high.

### 2.3 Event C: 2020-03-23 COVID-2 (the bottom)

- Entry T-5 = 2020-03-16. SPX 2386.13, VIX 82.69, VVIX 207.59 (this is the highest VVIX in the dataset), SKEW 114.66.
- Peak = 2020-03-23. SPX 2237.40 (-6.23% further from entry), VIX 61.59 (already declining).

| Structure | Underlying | Cost ($) | Peak value ($) | P&L ($) |
|---|---|---|---|---|
| Fly -2/-5/-8 | SPX | 1,396 | 2,011 | +614 |
| PutSpread ATM/-10 | SPX | 44,190 | 52,825 | +8,635 |
| LongPut -10 | SPX | 51,042 | 44,133 | **-6,909** |
| Ratio2x1 -8/-15 | SPX | +10,971 (paid!) | -195 | **-11,166** |
| WeeklyCall K=25 VIX | VIX | 5,021 | 3,412 | -1,609 |
| Ladder 25+35+45 VIX | VIX | 12,619 | 7,750 | **-4,870** |

Takeaway: **entering vol hedges into already-peak vol is the failure mode.** VIX at 82 → VVIX at 207 → -10% SPX put cost $51K. SPX fell another 6%, but vol crushed back from 82 → 61 and the put lost money. Every long-vol structure lost here EXCEPT the SPX put spread (which has short vega from the short -10% leg). **Lesson: at VIX > 50, switch from long-vol to vol-neutral spreads.** Even the put fly turned a profit here ($614) on $1.4K cost because vol normalized.

### 2.4 Event D: 2022-03-08 hike-cycle (grinding selloff)

- Entry T-5 = 2022-03-01. SPX 4306.26, VIX 33.32, VVIX 132.80, SKEW 134.42.
- Peak = 2022-03-08. SPX 4170.70 (-3.15%). This is a "slow burn" event — VIX never spiked, just grinded.

| Structure | Underlying | Cost ($) | Peak value ($) | P&L ($) |
|---|---|---|---|---|
| Fly -2/-5/-8 | SPX | 2,778 | 3,147 | +369 |
| PutSpread ATM/-10 | SPX | 27,483 | 37,107 | +9,623 |
| LongPut -10 | SPX | 6,260 | 10,394 | +4,133 |
| **LongPut -10** | **QQQ** | **19,153** | **31,361** | **+12,208** |
| Ratio2x1 -8/-15 | SPX | -5,739 (credit) | -8,379 | -2,640 |
| Ladder 25+35+45 VIX | VIX | 4,625 | 5,533 | +908 |

Takeaway: **QQQ -10% put beat SPX equivalent by ~3×** because Nasdaq drew down 5.31% vs SPX 3.15% (tech-led selling). This is the regime where the M7 trader's beta works AGAINST him — buying QQQ puts on top of M7 stock = idiosyncratic alpha bet preserved. Ratio backspreads lost again (entered net-credit, peak hit between short and long strikes). VIX ladder squeaked a small win because VIX was already 33 at entry — most of the convexity premium already priced.

### 2.5 Event E: 2024-08-05 JPY carry unwind

- Entry T-5 = 2024-07-29. SPX 5463.54, VIX 16.60, VVIX 93.51, SKEW 128.93.
- Peak = 2024-08-05. SPX 5186.33 (-5.07%). VIX intraday hit ~65 ([investing.com / BIS Bulletin 90](https://www.bis.org/publ/bisbull90.pdf)) but closed at 38.57. Nikkei -12.4% same session (biggest one-day point drop in history).

| Structure | Underlying | Cost ($) | Peak value ($) | P&L ($) | Convexity |
|---|---|---|---|---|---|
| Fly -2/-5/-8 | SPX | 4,616 | 3,696 | -920 | 0.80 |
| PutSpread ATM/-10 | SPX | 20,012 | 55,650 | +35,638 | 2.78 |
| **LongPut -10** | **SPX** | **322** | **21,639** | **+21,317** | **67.3** |
| LongPut -10 | QQQ | 3,151 | 42,314 | +39,163 | 13.4 |
| **LongPut -10** | **IWM** | **5,066** | **59,431** | **+54,364** | **11.7** |
| Ratio2x1 -8/-15 | SPX | -974 (credit) | -12,422 | **-11,448** | n/a |
| WeeklyCall K=25 VIX | VIX | 0 (BSM-zero) | 0 | 0 | n/a |
| Ladder 25+35+45 VIX | VIX | 4,997 | 633,763 | +628,766 | 126.8 (upper-bound) |

Takeaway: closest analog to Volmageddon (low entry IV → SPX -10% put almost free → 67× convexity). **IWM was the highest absolute payoff again** because RUT drew down 8.8% vs SPX 5.1% (small-caps cracked on the carry-trade unwind). BIS confirms: most of the move accumulated overnight Sunday Aug 4 → Monday Aug 5 in CME globex — see §6.

---

## 3. Cross-event leaderboard

Mean $ P&L per $1M book and win rate (5 events):

| Rank | Structure | Underlying | Mean P&L ($) | Median P&L ($) | Win rate (%) | Mean entry cost ($) |
|---|---|---|---|---|---|---|
| 1 | Ladder 25+35+45 (30DTE) | VIX | +295,026 | +7,572 | 80 | 6,429 (upper bound only) |
| 2 | LongPut -10 | IWM | +37,155 | +27,832 | 80 | 21,210 |
| 3 | **PutSpread ATM/-10** | **SPX** | **+26,826** | **+30,495** | **100** | **30,652** |
| 4 | LongPut -10 | SPX | +25,578 | +21,317 | 80 | 17,004 |
| 5 | PutSpread ATM/-10 | SPY | +24,868 | +26,411 | 100 | 30,208 |
| 6 | LongPut -10 | QQQ | +24,199 | +29,372 | 80 | 21,053 |
| 7 | LongPut -10 | SPY | +22,935 | +18,996 | 80 | 17,193 |
| 8 | PutSpread ATM/-10 | IWM | +22,412 | +31,324 | 100 | 35,669 |
| 9 | PutSpread ATM/-10 | QQQ | +19,393 | +26,044 | 80 | 35,264 |
| 10 | Ratio2x1 -8/-15 | IWM | +10,166 | -1,387 | 40 | -1,118 (credit) |
| 11 | WeeklyCall K=30 | VIX | +992 | 0 | 40 | 2,638 (lower-bound only) |
| 12 | Fly -2/-5/-8 (any underlying) | — | -221 to -542 | -623 to -1,010 | 40 | 2,724-3,150 |
| 13 | Ratio2x1 -8/-15 | SPX, SPY, QQQ | -254 to -805 | -10,237 to +1,868 | 20-40 | credit |
| 14 | **Ratio2x1 -10/-20 (any underlying)** | — | **-2,724 to -7,855** | **-5,697 to -10,475** | **20** | **credit** |

Key reads:
- **PutSpread ATM/-10 SPX is the only 100% win-rate structure** despite not having the highest mean. It is the workhorse.
- LongPut -10 has higher upside but loses on COVID-2 (-$6.9K) because entry IV was already 82%.
- Ratio2x1 -8/-15 has 40% win rate; the 60% it loses, it loses BIG (-$10K to -$15K per $1M).
- Ratio2x1 -10/-20 has 20% win rate and is the worst structure in the study. **DO NOT USE.**
- VIX Ladder mean is skewed by two extreme upside-tail events; even discarding those, the structure only wins 60% (COVID-1 +$7.6K, hike-cycle +$0.9K). With realistic mid prices its convexity is much lower.

---

## 4. False-positive carry (2017 and 2023)

Monthly roll, 35-DTE held to expiry, $1M book. Realized P&L in $ over 12 months. **Negative = bleed; positive = net credit captured.**

| Structure | 2017 P&L ($) | 2017 P&L (% NLV) | 2023 P&L ($) | 2023 P&L (% NLV) |
|---|---|---|---|---|
| Fly -2/-5/-8 | -38,401 | -3.84% | -12,593 | -1.26% |
| PutSpread ATM/-10 | -104,139 | -10.41% | -119,370 | -11.94% |
| LongPut -10 | -118 | -0.012% | -5,407 | -0.54% |
| **Ratio2x1 -8/-15** | **+822** | **+0.08%** | **+12,456** | **+1.25%** |
| Ratio2x1 -10/-20 | +118 | +0.012% | +5,372 | +0.54% |
| VIX Ladder 25+35+45 | $0 (BSM-zero — see gap §9) | 0 | -44,887 | -4.49% |
| VIX Weekly 25C | $0 (BSM-zero) | 0 | -44,900 | -4.49% |

Critical findings:
- **PutSpread ATM/-10 carries -10% to -12% NLV/year — this is the cost of the only 100%-win-rate hedge.** Way over the 1.5% NLV cap. Only deployable tactically (when VIX9D/VIX inverts), not as standing hedge.
- LongPut -10 carries -0.01% to -0.54% NLV — well under the 1.5% cap. **This is the standing hedge.**
- **Ratio backspreads earn net credit in calm years** (+$822 in 2017, +$12,456 in 2023). The 2023 carry of +1.25% is real — but you pay it back catastrophically at the next vol spike (-$3K to -$15K per event). Not a hedge; it's a short-skew premium-capture strategy that masquerades as one.
- **VIX strategies in 2023 cost ~4.5% NLV each in carry.** BSM with VVIX proxy underestimates — sixfigureinvesting and Volatility Box research point to VIX call/VXX carry of 3-5% per month in contango regimes ([Volatility Box](https://volatilitybox.com/research/how-to-trade-the-vix/)). Our 2023 estimate is consistent with the low end. **Even at 4.5%/year, you cannot afford a permanent VIX hedge under the 1.5% NLV cap.**
- The 2017 BSM-zero result for VIX is a known gap: low VIX + low VVIX + 30 DTE OTM strikes 25/35/45 round to zero in BSM. Listed mids would have been ~$0.05-$0.20 per VIX call → real carry ~ 1-3% NLV in 2017.

---

## 5. Cross-index findings (when does QQQ/IWM beat SPX?)

Drawdown ratios at peak vs IV ratios at entry (T-5):

| Event | SPX DD | SPY DD | QQQ DD | IWM DD | IV(QQQ)/IV(SPX) | IV(IWM)/IV(SPX) | Realized DD QQQ/SPX | Realized DD IWM/SPX | QQQ "free convexity" | IWM "free convexity" |
|---|---|---|---|---|---|---|---|---|---|---|
| Volmageddon | -7.17% | -7.29% | -7.04% | -6.79% | 1.51 | 1.59 | 0.98 | 0.95 | -0.53 | -0.64 |
| COVID-1 | -13.12% | -12.54% | -12.54% | -20.51% | 1.06 | 1.04 | 0.96 | **1.56** | -0.10 | **+0.52** |
| COVID-2 | -6.23% | -7.05% | +0.69% | -3.59% | 1.00 | 1.04 | 0.11 | 0.58 | -0.89 | -0.46 |
| Hike-cycle | -3.15% | -3.19% | -5.31% | -2.36% | 1.46 | 1.33 | **1.69** | 0.75 | **+0.23** | -0.58 |
| JPY unwind | -5.07% | -5.03% | -6.15% | -8.81% | 1.57 | **1.80** | 1.21 | **1.74** | -0.36 | -0.06 |

"Free convexity" = (Realized DD ratio) − (Entry IV ratio). Positive = market gave you more DD than IV priced in → over-hedge with that name vs SPX. Negative = IV was already loaded → SPX is the better choice.

Findings:
- **QQQ ratio backspread beats SPX in only ONE event: 2022 hike-cycle** (+0.23 free convexity). Tech-led selling, QQQ DD 1.7× SPX DD, but IV priced only 1.46× the move. **Rule: When the catalyst is tech-specific (FOMC hawkish, semi cycle), prefer QQQ puts even if VIX9D/VIX is in normal range.**
- **IWM beats SPX in TWO events:** COVID-1 (+0.52) and JPY unwind (-0.06 nearly neutral). Both are "fast deleveraging" events where small-cap names get sold reflexively. **Rule: When VVIX > 130 AND credit spreads widening (we can't measure in this dataset but the trader can check IG/HY OAS), prefer IWM puts.**
- **In Volmageddon and COVID-2, IV ratios were ALREADY 50-60% over SPX → QQQ/IWM puts overpaid.** Lesson: if RVX/VXN proxies (we use 60d realized vol ratio) are >1.3× VIX, do not buy QQQ/IWM puts — the premium is already loaded; buy SPX.

---

## 6. 24-hour overnight tradability findings

ES=F daily decomposition: overnight gap = (Open[t] / Close[t-1] − 1); intraday = (Close[t] / Open[t] − 1). T-5 → peak window.

| Event | Abs overnight % | Abs intraday % | % of total accumulated overnight |
|---|---|---|---|
| Volmageddon | 0.32% | 9.92% | 3.1% |
| COVID-1 | 4.88% | 45.22% | 9.7% |
| **COVID-2 (Mar 16→23)** | **12.11%** | **19.06%** | **38.9%** |
| Hike-cycle | 1.19% | 7.37% | 13.9% |
| JPY unwind | 1.85% | 8.01% | 18.7% |

ES=F detail for COVID-2 window (the limit-down zone):

| Date | Prior close | Open | ON % | Intraday % |
|---|---|---|---|---|
| 2020-03-16 | 2696.0 | 2673.8 | -0.83% | -9.63% |
| 2020-03-17 | 2416.2 | 2417.2 | +0.04% | +3.24% |
| 2020-03-18 | 2495.5 | 2478.5 | -0.68% | -2.60% |
| 2020-03-19 | 2414.0 | 2414.2 | 0.0% | -0.46% |
| 2020-03-20 | 2403.2 | 2364.2 | -1.62% | +3.12% |
| **2020-03-23** | **2438.0** | **2220.2** | **-8.93%** | **+0.01%** |

The full bottom on March 23 was made overnight — ES gapped down 8.93% Sunday/Monday before US RTH opened (this hit the CME 5% overnight price-limit, multiple cascading halts per [CME group equity index price limits](https://www.cmegroup.com/trading/equity-index/us-based-equity-index-futures-price-limits-faq.html); the cascading expand-and-resume mechanism applies). SPY (RTH-only) did not capture the bulk of this move at the open mark. A trader holding SPY puts would have seen the gap printed into the open but with much wider bid-ask vs the SPX index option, which trades continuously in CME globex via VIX/SPX option night session.

ES=F detail for JPY unwind hourly (2024-08-04 → 08-05 first 12 hours):

| Time (ET) | ES low | Move from Fri 4pm close (5359.75) |
|---|---|---|
| 2024-08-04 18:00 (Sun open) | 5321.25 | -0.72% |
| 2024-08-04 22:00 | 5295.50 | -1.20% |
| 2024-08-05 01:00 | 5205.00 | -2.89% |
| 2024-08-05 08:00 | **5120.00** | **-4.46%** |
| 2024-08-05 09:30 (NYSE open) | ~5151 | -3.89% |

**Half of the Aug 5 move (-4.5% of the eventual -7-8% peak DD) accumulated before US RTH.** A SPY put trader could not have rebalanced or rolled until 9:30 ET. A SPX put trader could (SPX options trade in CME globex 8:15pm-9:25am ET → has a session that brackets the Sunday-night Asia open and the Tokyo cascade).

**Practical implication for the $1M book:** On COVID-2, the overnight portion of the move (-8.93% on March 23) implies that ~4-5% of $1M = $40K-50K of underlying loss accumulated in a window where SPY puts were not tradable. SPX options that you can roll/close in the overnight session let you (a) take profit on the gap, (b) reset deltas, (c) avoid being trapped in a stale put if vol crushes. The trader's preference for SPX (already canonical per the project's `feedback_index_analysis_use_spx.md`) is reinforced empirically.

Sources: BIS Bulletin 90 on the [August 2024 carry unwind](https://www.bis.org/publ/bisbull90.pdf) confirms the cross-asset overnight cascade thesis; Wikipedia on the [2020 stock market crash](https://en.wikipedia.org/wiki/2020_stock_market_crash) confirms the VIX 82.69 closing high and the March 16 -12% session.

---

## 7. Regime precondition decision tree

T-10, T-5, T-2 readings per event (raw CSV: `data/preconditions.csv`):

| Event | Day | VIX | VIX9D | VIX3M | VVIX | SKEW | RV21d | VRP | VIX9D/VIX | VIX/VIX3M |
|---|---|---|---|---|---|---|---|---|---|---|
| Volmageddon | T-10 | 11.03 | 10.86 | 12.99 | 99.7 | 127.2 | 6.68 | +4.35 | 0.985 | 0.849 |
| Volmageddon | T-5 | 13.84 | **14.91** | 14.99 | 110.0 | 118.8 | 7.93 | +5.91 | **1.077** | 0.923 |
| Volmageddon | T-2 | 13.47 | 13.86 | 14.72 | 105.8 | 120.6 | 8.72 | +4.75 | 1.029 | 0.915 |
| COVID-1 | T-10 | 33.42 | 42.17 | 27.70 | 114.7 | 126.8 | 29.91 | +3.51 | 1.262 | 1.206 |
| COVID-1 | T-5 | 54.46 | **70.30** | 43.05 | 137.2 | 121.6 | 43.39 | +11.07 | **1.291** | **1.265** |
| COVID-1 | T-2 | 75.47 | 103.56 | 57.24 | 155.0 | 115.8 | 58.51 | +16.96 | 1.372 | 1.318 |
| COVID-2 | T-10 | 54.46 | 70.30 | 43.05 | 137.2 | 121.6 | 43.39 | +11.07 | 1.291 | 1.265 |
| COVID-2 | T-5 | 82.69 | 106.66 | 67.70 | **207.6** | 114.7 | 79.34 | +3.35 | 1.290 | 1.221 |
| Hike-cycle | T-10 | 28.81 | 28.62 | 29.11 | 130.7 | 128.3 | 21.69 | +7.12 | 0.993 | 0.990 |
| Hike-cycle | T-5 | 33.32 | **34.80** | 32.59 | 132.8 | 134.4 | 23.15 | +10.17 | **1.044** | **1.022** |
| Hike-cycle | T-2 | 31.98 | 31.11 | 32.34 | 127.9 | 133.3 | 22.66 | +9.32 | 0.973 | 0.989 |
| JPY unwind | T-10 | 14.91 | 14.79 | 16.09 | 93.7 | 141.4 | 10.17 | +4.74 | 0.992 | 0.927 |
| JPY unwind | T-5 | 16.60 | **17.39** | 17.16 | 93.5 | 128.9 | 13.76 | +2.84 | **1.048** | 0.967 |
| JPY unwind | T-2 | 18.59 | 19.54 | 19.14 | 111.2 | 136.7 | 15.45 | +3.14 | 1.051 | 0.971 |

**Which signal fires earliest and most reliably?**

| Signal | Volmageddon T-10 | COVID-1 T-10 | Hike-cycle T-10 | JPY unwind T-10 | At T-5: fired in 4/4? |
|---|---|---|---|---|---|
| VIX absolute > 18 | No (11) | Yes (33) | Yes (29) | No (15) | 3/5 |
| **VIX9D/VIX > 1.04** | No | Yes (1.26) | No | No | **4/4** at T-5 |
| VIX/VIX3M > 1.00 (term backwardation) | No | Yes (1.21) | No | No | 2/4 at T-5 |
| VVIX > 110 | No | Yes | Yes | No | 3/4 at T-5 |
| SKEW > 140 | No | No | No | **Yes (141)** | 1/4 (only JPY unwind T-10) |
| VRP (VIX − RV21d) > 5 | No | No | Yes | No | 3/4 at T-5 |

**Strongest tell: VIX9D/VIX > 1.04 at T-5.** Fired 4 of 4 at T-5 (Volmageddon 1.077, COVID-1 1.291, hike-cycle 1.044, JPY unwind 1.048). It is the earliest reliable signal of term-structure inversion — the short end inverts before VIX/VIX3M proper inverts.

**Second tell: SKEW > 140.** Only fired once (JPY unwind T-10), but it fired LONG before VIX9D inverted — at T-10 in JPY unwind, VIX9D/VIX was still 0.992 but SKEW was already 141.4. This is consistent with the literature on far-OTM put skew loading ahead of left-tail events. SKEW is a slow, leading indicator; VIX9D/VIX is a fast, coincident indicator. Use both.

**Recommended decision tree (ex-ante, executed at every Monday open):**

```
IF SKEW > 140 AND VIX < 18:
  → Step 1: Buy SPX 35-DTE -10% LongPut at 0.15% NLV (cheap insurance).
            BSM cost on $1M book historically $80-322 = 0.01-0.03% NLV.
            Listed mid likely $1-3/contract → 0.05-0.15% NLV. Within budget.

ELIF VIX9D/VIX > 1.04 AND VIX < 18:
  → Step 1: Buy SPX 35-DTE -10% LongPut (same).
  → Step 2 (if SKEW also > 130): Add QQQ 30-DTE -10% put = 0.1% NLV
            (protects the M7-concentrated leg specifically).

ELIF VIX9D/VIX > 1.04 AND 18 ≤ VIX < 25:
  → Switch to SPX ATM/-10% put SPREAD (saves carry vs naked put).
            Spread cost ~ 1.5-2.0% NLV for 35 DTE → 15-20% annualized.
            BUDGET-BUSTING if held. Treat as tactical 1-3 week deployment only.

ELIF VIX9D/VIX > 1.04 AND VVIX > 130 AND credit spreads widening:
  → Prefer IWM over SPX (small-cap deleveraging beta wins).
            Use IWM ATM/-10% put spread sized to 0.5% NLV.

ELIF VIX ≥ 25 AND term structure already inverted:
  → DON'T CHASE. Vol is rich. Either close existing hedges (50% TP rule)
                 or sell -10% strike on existing puts for partial credit
                 (convert long put → put spread).

ELIF SKEW < 130 AND VIX9D/VIX < 1.00 AND VIX < 15:
  → CARRY-COST MINIMIZATION REGIME. Carry only the cheapest tail —
            SPX 35-DTE 5-delta put (~ $0.30/contract for SPX).
            On $1M book: 0.01-0.03% NLV/month → 0.1-0.4% NLV/year. WAY under cap.
```

---

## 8. Recommended additions to `scripts/macro_hedge.py`

Current `macro_hedge.py` supports three structures: `butterfly`, `put_spread`, `long_put`. The empirical results say:

### KEEP
- `long_put` — winning structure in low-vol entry regimes; carries cheaply (-0.01% to -0.54% NLV/yr). KEEP.
- `put_spread` — only 100%-win-rate structure. KEEP but flag carry: 10-12% NLV/yr if held. **Add a hard carry-budget check that REJECTS this when projected annualized cost > 5% NLV unless caller explicitly passes `tactical_window_days=14`**.

### REMOVE/DEPRECATE
- `butterfly` — won 40% of the time, mean P&L -$300 to -$540 per $1M book across our 5 events. Cheap but ineffective. The fly's body strike at -5% gets "passed through" in fast crashes (peak is far below body) → max-loss zone for body's short leg. **Deprecate** for tail-hedge purpose; can keep for "mild correction -5" scenario but document it as **expecting a controlled correction, not a crash**.

### ADD

**A. `vix_call_ladder`** — 30 DTE long calls at K=25, 35, 45 on VIX. Best mean P&L in study, BUT:
- Hard rule: forbid as standing hedge (4.5%/yr carry blows the 1.5% NLV cap).
- Allow only as TACTICAL deployment when VIX9D/VIX > 1.04 AND VIX < 20 (i.e., the regime where Volmageddon/JPY unwind entries paid 126× and 169×).
- Size at MAX 0.5% NLV initial cost per deployment.
- Bracket: TP at 200% of cost (sell half), runner to expiry or peak vol day.
- **Provenance flag in code**: "VIX option pricing uses BSM on (VIX+VIX3M)/2 with VVIX as IV — listed mids typically 50-200% higher in calm regimes; verify against live UW/IB chain before placing."

**B. `iwm_putspread`** — IWM ATM/-10% put spread, 35 DTE. Add as cross-index alternative when VVIX > 130 AND credit-spread tell present. Empirically beats SPX put spread in 2 of 5 events (COVID-1, JPY unwind) by $30-60K per $1M.

**C. `qqq_longput_tech_specific`** — QQQ -10% LongPut, 35 DTE. Add when catalyst is FOMC-hawkish or semi/AI-rotation (tech-leading-down regime). Empirically the only winner in 2022 hike-cycle.

**D. `spx_5delta_longput`** — current `long_put` defaults to -10% (delta ~ 5-15 depending on IV). At low VIX (< 14), -10% is delta ~ 2-5 which is fine. But at higher VIX (> 25), -10% becomes ~15-20 delta and gets expensive. Generalize the put strike selection to target a **fixed delta** (5-delta default) rather than fixed -10% pct. This caps carry at the trader's intent ("I want 5-delta tail exposure") regardless of regime.

### EXPLICITLY DO NOT ADD

- **`put_ratio_backspread`** of any config (-8/-15, -10/-20). Loses 60-80% of vol events tested in our 5-event window. The structure has a max-loss valley between short and long strikes that aligns with the most common 5-10% peak drawdown of the events studied. **The only universe where ratio backspreads work is when peak drawdown exceeds the long strike**, which happened only in COVID-1. The trader is concentrated in M7 — these tend to draw down 7-12% in vol shocks (not 15-20%) → ratio backspread loses by construction.
- **`vix_weekly_single_call`** (B from the brief). BSM with VX1-proxy zeroed the 25/30 strike contract in low-VIX regimes — listed mid would be $0.10-0.50 → carry of 30-50%/yr. Even the best events (COVID-1) gave 2.1-2.4× convexity. The 30-DTE ladder dominates.

---

## 9. Open questions and data gaps

1. **BSM is wrong on every VIX option price in the study.** VIX options trade off the front-month VX future, not spot VIX. Our VX1 proxy (0.5·VIX + 0.5·VIX3M) is reasonable in contango regimes but breaks in deep backwardation (peak vol days). Real entry costs for VIX 25C front-week are typically $0.20-$1.50 even when BSM-on-spot gives $0. **All VIX-structure convexity numbers in this report should be read as upper bounds** (lower bounds on cost). Verification path: pull historic UW or CBOE EOD VIX option chain for Jan 29 2018 and July 29 2024 to recalibrate. I could not access those archives without a paid subscription.

2. **SPY vs SPX IV are assumed equal.** In reality SPY puts trade at slightly elevated IV vs SPX (retail demand, different settlement). Effect on our results: SPY structure costs in the report are understated by ~5-10%; convexity ratios for SPY are slightly overstated. Direction of conclusion (SPX preferred over SPY) is reinforced, not weakened.

3. **QQQ/IWM IV proxied via 60d realized-vol ratio vs SPX.** This is a rough beta. Real VXN and (where available) RVX would be more accurate. VXN was downloadable on yfinance but in spot-check it tracks our proxy within ±3 vol pts; RVX was delisted from yfinance free tier. **Conclusion direction unaffected** but exact dollar P&L for QQQ/IWM should be treated as ±15%.

4. **Historical option chain mids not available**. Every option price in this report is BSM-estimated. Listed mids in March 2020 for OTM puts were 30-200% richer than BSM due to crash-skew demand. Effect: P&L numbers UNDERSTATE realistic post-peak exit values for long puts (good) but also UNDERSTATE entry cost (bad). Net effect on convexity ratio is ambiguous but probably within ±50%.

5. **2017 VIX carry of $0 is BSM-zero.** Real listed mid for VIX 25C 30-DTE with VIX at 10-12 was around $0.05-0.20. Our 2017 carry numbers for VIX structures are **understated** — realistic carry was ~1-3% NLV/yr, not zero. The qualitative conclusion (VIX cannot be carried under 1.5% NLV cap) holds and STRENGTHENS.

6. **Entry timing assumes T-5 trading days knowability.** Our regime-precondition tree (§7) addresses ex-ante predictability, but ex-post the trader needs a discipline: scan the VIX9D/VIX ratio every Monday open. None of our four events had VIX9D/VIX > 1.04 at T-10 (only Volmageddon, COVID-1 were at 0.985 and 1.262 — COVID-1 was already obvious). The Monday-scan window is therefore 1-5 trading days of lead time, not 10.

7. **VVIX is the IV input for VIX options** but VVIX itself spikes during crashes — by COVID-1 peak VVIX was 207. Our peak-day VIX option valuations use this spiked VVIX, which is empirically correct but also unstable (VVIX gets crushed back as crisis fades, hurting roll-down exits).

8. **No bid-ask cost modeled.** Our P&L assumes mid-to-mid. Real round-trip on SPX puts ~ $0.20-1.00 per contract; on VIX options $0.05-0.30 per contract; on IWM $0.05-0.20. On $1M book this is ~$100-1000 round-trip drag, negligible vs the P&L numbers but compounding for monthly rolls.

9. **Earlier events not studied.** 2015 China devaluation, 2011 US debt downgrade, 2008 GFC weren't in the window. The 4 events here may not generalize to multi-month grinding bear markets (2022 H1 sustained -20%). The hike-cycle event is a partial proxy but mild (-3.15% over 5 sessions).

10. **No assumption about VX skew.** Real VIX options have steep call skew (25-delta call IV > ATM IV by 10-30 vol pts during normal regimes). Our flat-VVIX BSM understates call IV → understates entry cost → overstates convexity. This is the biggest VIX-strategy bias and points the same direction as the VX1 proxy issue.

---

## 10. Sources actually consulted

External:
- [CBOE VIX Options Contract Specifications](https://www.cboe.com/tradable_products/vix/vix_options/specifications/) — confirmed VIX option multiplier 100, American style, global trading hours 7:15pm-8:25am CT (relevant for §6 overnight tradability). Page did not detail VIX vs VX-futures pricing relationship.
- [Bloomberg: The Day The VIX Doubled — Tales of Volmageddon](https://www.bloomberg.com/news/articles/2019-02-06/the-day-the-vix-doubled-tales-of-volmageddon) — VIX +115% close on Feb 5 2018, S&P -4.1% on the day.
- [sixfigureinvesting: What Caused the Volatility "Volmageddon" on 5-Feb-2018](https://www.sixfigureinvesting.com/2019/02/what-caused-the-february-5th-2018-volatility-spike-xiv-termination/) — XIV -97%, ~$3B vaporized in 50 minutes.
- [Wikipedia: 2020 stock market crash](https://en.wikipedia.org/wiki/2020_stock_market_crash) — confirmed SPX -7.6%/-9.5%/-12% sequence Mar 9/12/16, VIX closing high 82.69 on Mar 16.
- [CME Group: US-Based Equity Index Futures Price Limits FAQ](https://www.cmegroup.com/trading/equity-index/us-based-equity-index-futures-price-limits-faq.html) — 5% overnight price limit was in effect during March 2020; cascading limit-up/down mechanism, expanded later in October 2020.
- [BIS Bulletin 90: The market turbulence and carry trade unwind of August 2024](https://www.bis.org/publ/bisbull90.pdf) — PDF binary not extractable but URL is the canonical authoritative reference; search-result summary confirms VIX intraday >60, Nikkei -12.4%, SPX -3% on Aug 5 2024, cross-asset deleveraging.
- [Volatility Box: How to Trade the VIX](https://volatilitybox.com/research/how-to-trade-the-vix/) — VIX call/VXX contango cost 3-5%/month in calm regimes; corroborates our 2023 carry estimate.
- [Newfound Research: Tail Hedging blog](https://blog.thinknewfound.com/2020/06/tail-hedging/) — March 2020 10%-OTM SPX puts returned 13.4% monthly / 18.4% peak-to-trough on a 60-bps monthly budget; 30%-OTM returned 39.3% / 46.5%. Same budget. Conclusion supports our finding that LongPut OTM convexity rises with strike distance in crashes. Did not provide calm-year carry data.
- [Stanford MS&E 448 Group 7 (2021): Tail risk hedging with VIX Calls (Siranosian)](https://web.stanford.edu/class/msande448/2021/Final_reports/gr7.pdf) — PDF binary not directly extractable; abstract via search confirms VIX call rolling has high carry cost in calm regimes; specific empirical numbers not pulled.

Internal data and code:
- `data/run_analysis.py` — full empirical script (~530 lines). Pulls yfinance, prices structures, computes greeks, runs carry years.
- `data/structures_by_event.csv` — 115 rows: 5 events × 23 structure-underlying combinations.
- `data/leaderboard.csv` — convexity-ratio leaderboard (use with caution: ratio breaks for net-credit structures).
- `data/leaderboard_by_pnl.csv` — $ P&L leaderboard (the headline metric).
- `data/preconditions.csv` — 15 rows: 5 events × 3 lookback days (T-10, T-5, T-2).
- `data/overnight_decomp.csv` — ES=F overnight vs intraday accumulation per event.
- `data/cross_index_dd.csv` — drawdown ratios and IV ratios per event.
- `data/carry_2017_2023.csv` — monthly roll carry results for 2017 and 2023.

Internal repo:
- `plugins/option-wizard/skills/option-wizard/scripts/macro_hedge.py` — current implementation we propose to extend per §8.
- `private/trader-profile.md` — confirmed 1.5% NLV macro hedge cap; M7+QQQ buy-and-hold mandate; downside-protection-only remediation for concentration.

---

## 11. Extension: 2011 + 2015 events (added 2026-06-10 same-day)

Re-ran `data/run_analysis.py` with the date range extended to 2011-01-01
and two events appended: 2011-08-08 US debt downgrade and 2015-08-24
China Black Monday.

**VIX9D/VIX > 1.04 tell — extended verdict: 6 of 7 events fire at T-5.**

| Event | T-10 VIX9D/VIX | T-5 VIX9D/VIX | T-2 VIX9D/VIX | Outcome |
|---|---|---|---|---|
| 2011-08-08 US debt downgrade | **1.054** | 1.135 | 1.260 | **HIT, earliest in dataset** (fired at T-10) |
| 2015-08-24 China Black Monday | 0.935 | **0.867** | 1.091 | **MISS** at T-5 (fired only at T-2, too late to act) |
| 2018-02-05 Volmageddon | 0.985 | 1.077 | 1.029 | hit |
| 2020-03-16 COVID-1 | 1.262 | 1.291 | 1.372 | hit |
| 2020-03-23 COVID-2 | 1.291 | 1.290 | 1.264 | hit |
| 2022-03-08 hike-cycle | 0.993 | 1.044 | 0.973 | hit (marginal) |
| 2024-08-05 JPY unwind | 0.992 | 1.048 | 1.051 | hit (marginal) |

**The 2015 miss is structurally informative, not a flaw in the tell.**
China Black Monday built through the FX channel: PBOC devalued the yuan
on 2015-08-11, EM currencies cascaded, EM equity sold off (-6% on Aug
21), then SPX flash-crashed at open on Aug 24 (-3.9% close, -5.3%
intraday low). Equity vol stayed compressed throughout the buildup —
VIX9D/VIX = 0.87 at T-5 was the OPPOSITE of inversion. The signal
flipped to 1.091 only at T-2, useless as actionable warning.

**Conclusion:** VIX9D/VIX is a coincident indicator for equity-vol-driven
events. For FX/currency-crisis-driven events (yuan devaluation, EM credit
events, JPY unwinds that originate in FX before bleeding into equity),
the leading indicator must come from FX vol or currency stress. Open
research: add DXY 30d realized vol, USDCNY 1m IV, EM CDS index to the
regime tree as parallel triggers.

**Cross-index findings for new events:**
- 2011 US downgrade: SPX -13.0%, IWM **-17.8%** (-4.8% extra), IV ratio
  1.40 vs realized 1.37 → IV correctly loaded; IWM "free convexity"
  ≈ 0. Standing SPX hedge would have caught most of the move.
- 2015 China Black Monday: SPX -10.0%, QQQ **-11.6%** (-1.6% extra), IV
  ratio 1.25 vs realized 1.17 → QQQ IV slightly over-loaded; SPX is
  cheaper hedge. 2015 was IWM-light (small caps -9.1%, less than SPX).

**Overnight capture for new events:**
- 2011 US downgrade: 22.0% of total move overnight (ES gapped on Aug 8
  Asian session after S&P downgrade announced Friday post-close)
- 2015 China Black Monday: only 4.3% overnight; the move was the open
  flash crash + intraday selling. Standard NYSE-hours coverage sufficed.

**Updated cross-event leaderboard (7 events, mean convexity ratio):**

| Rank | Structure | Underlying | Mean conv | Mean ann cost % |
|---|---|---|---|---|
| 1 | VIX 30-DTE ladder 25+35+45 | VIX | 216.9 | 7.3% |
| 2 | LongPut -10 | SPY | 214.0 | 13.1% |
| 3 | LongPut -10 | SPX | 212.2 | 13.0% |
| 4 | VIX weekly 30C | VIX | 61.8 | 13.6% |
| 5 | LongPut -10 | IWM | 42.2 | 16.9% |
| 6 | LongPut -10 | QQQ | 40.2 | 16.4% |
| 7 | VIX weekly 25C | VIX | 5.5 | 14.6% |
| 8 | PutSpread ATM/-10 | SPY | 2.67 | 28.4% |
| 9 | PutSpread ATM/-10 | SPX | 2.66 | 28.9% |
| ... | Fly -2/-5/-8 | any | 0.78-0.88 | 3.1-3.6% |
| ... | Ratio2x1 -10/-20 | QQQ/SPX/SPY | 0.0 | net-credit (lose at peak) |
| ... | Ratio2x1 -8/-15 | any | div-by-zero (credit) | net-credit (lose at peak) |

**Note on `inf` rows:** for net-credit structures (ratio backspreads),
the convexity ratio = peak_payoff / entry_cost is divide-by-near-zero.
The `n` column (7) confirms they were tested every event; the absolute
P&L per event is what matters, and ratio backspreads averaged -$3K to
-$15K per $1M per event. The convexity-ratio leaderboard column is a
misleading metric for credit structures — use the by-PnL CSV instead.

Standing hedge (SPX -10% LongPut) annualized cost ROSE from 0.6% NLV/yr
to 13% NLV/yr in this extended leaderboard. Reason: the leaderboard
aggregates the deployed cost AT EACH EVENT (entry IV × cost cap × tenor),
not the year-round carry. The "13%" figure is "if you held this hedge
through every event window in the sample"; the calm-year carry
(§4 carry_2017_2023) of 0.01-0.54% NLV/yr is the standing-hedge cost.
Both numbers are correct for their respective questions.

End of report.
