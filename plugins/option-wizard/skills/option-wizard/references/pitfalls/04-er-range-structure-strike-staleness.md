---
type: Trading Pitfall
title: "Pitfall 04: ER range structures — set strikes at entry, add a bearish-breakdown veto"
description: ER vol-selling range structures (iron condor) must set strikes at the entry moment, not the analysis date; if the underlying has moved >1 implied move toward a short strike before entry, abort/re-strike. Add a bearish-breakdown veto alongside the bullish-conviction veto.
severity: HIGH
appliesTo: earnings, iron-condor, range-structure, entry-timing, strike-selection
tags: [earnings, iron-condor, strike-staleness, entry-timing, bearish-veto, implied-move]
timestamp: 2026-06-15T09:18:25Z
---

# Pitfall 04: ER 卖波动率的 range 结构 — strike 必须按入场时刻定，并设 bearish-breakdown veto

**Date:** 2026-06-08 (提出) / 2026-06-12 (resolved) / 2026-06-14 (复盘)
**Ticker / structure:** ADBE 6/12 iron condor (215P / 225P / 275C / 285C)
**Loss / forgone gain:** simulated max loss −$715/contract（未执行，实际 $0 — 纪律/未扣扳机避损）

## What I did

06-08 选 ADBE ER iron condor。Thesis = implied move 8.0% ≫ 历史 4Q realized 平均 3.85%，赌 ER 后窄幅 + IV crush。short put $225 在提出日 spot $247.93 下方 9.2%（put wall 之下），short call $275 上方 10.9%。计划 **06-11 下午（ER 当天）入场**，strike 锁定在 06-08 的快照上。入场前跑了 4-signal bullish-conviction veto，0/4 fire → 判定 iron condor 适用。

## What actually happened

ADBE 从提出日到计划入场日持续 de-risk：244.99 (6/8) → 237.88 (6/9) → 233.38 (6/10) → **218.80 (6/11)**。**到计划入场时刻，spot 已 $218.80，跌穿 $225 short put strike，而 ER 还没发布**。06-12 ER 后收 $204.02（ER 当根 −6.8%，6/8→6/12 累计 −16.7%）。若按原 strike 入场，put spread $225/$215 全部 ITM = full max loss。

## Why the assumption was wrong

1. **Strike 锚在分析日、入场在 3 天后。** 高 beta、ER 前 de-risking 的名字，3 个交易日能移动 > 1 个 implied move。$225 strike 在 06-08 是 9% OTM，到 06-11 已是 ATM/ITM。strike 的 OTM 缓冲是用过期的 spot 算出来的。
2. **只查了 bullish veto，没有 bearish-breakdown veto。** 4-signal veto 防的是"别在强趋势顶上做 neutral / 卖 call"。它对"标的正在 freefall 时做 range 结构"零防御。一个一周已 −9.5%、ER 前持续创新低的名字，发出的是方向信号，不是均值回归信号。
3. **vol edge 被 directional move 碾过。** "implied > 历史 realized" 的统计 edge，在一次大的有方向的移动面前直接归零。iron condor 的 EV 假设对称窄幅；breakdown 把概率质量全推到下尾。

## Rule going forward

ER（或任何事件）卖波动率的 range 结构：(a) strike 必须在**入场时刻**用实时 spot 重定，绝不用分析日快照；(b) 入场前若 underlying 已朝任一 short strike 移动 > 1× implied move（或一周累计移动 > 1× implied move），**abort 或 re-strike** —— 触发 bearish/directional-breakdown veto，与 bullish-conviction veto 并列必查。
