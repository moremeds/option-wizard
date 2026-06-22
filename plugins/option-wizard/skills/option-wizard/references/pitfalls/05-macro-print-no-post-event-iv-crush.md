---
type: Trading Pitfall
title: "Pitfall 05: Macro prints are not single-name ER — buy the hedge BEFORE the print"
description: Macro data prints (NFP / CPI / FOMC) are not single-name earnings — the data IS the vol shock, so a miss expands VIX rather than crushing it. Buy the macro hedge before the print; the cheap-IV window is pre-event. Post-event IV-crush logic only applies to single-name earnings.
severity: HIGH
appliesTo: macro-hedge, hedge-timing, vol-mechanics, nfp, cpi, fomc
tags: [macro-hedge, hedge-timing, iv-crush, nfp, cpi, fomc, vix]
timestamp: 2026-06-15T09:18:25Z
---

# Pitfall 05: macro 数据事件 ≠ 单名 ER — 不要等"事件后 IV crush"再买 hedge

**Date:** 2026-06-03 / 06-04 (analysis) · 2026-06-14 (复盘)
**Ticker / structure:** SPX / QQQ macro hedge（NFP 6/5 + CPI 6/10 catalyst window）
**Loss / forgone gain:** hedge 推迟到事件后买 → 成本不降反升（VIX 15.4 → 22.66），错过 pre-event 便宜窗口

## What I did

06-03/04 的大盘分析方向判对了：compressed spring at ATH、dealer short-γ、机构在 hedge，建议 SPX/QQQ put spread macro hedge。但 sizing note 写「**最佳时机：NFP 之后，IV 可能短暂回落**」—— 把单名 ER 的「事件落地 → IV crush」逻辑套到了 macro 数据印上。

## What actually happened

NFP 6/5 → VIX 15.40 → 21.51（+40%）；CPI 6/10 → 盘中冲到 22.66。等事件后再买 hedge **更贵**，不是更便宜。便宜的 IV 窗口在**事件之前**。SPX 同期 trough −4.2% / QQQ −6.9%，方向判对了，但「等更便宜」的时机判断让 hedge 要么没上、要么上得又晚又贵。

## Why the assumption was wrong

单名 ER 的 IV crush 来自「不确定性被解决」：财报一出，未知变已知，front IV vega 崩。但 scheduled macro 数据印（NFP / CPI / FOMC）**本身就是潜在的 vol shock 源** —— 数据 miss 会同时引爆抛售 + vol expansion。事件不是在解决不确定性，而是在制造它。把 ER 的 vol 路径套到 macro print 上，IV 的方向假设正好反了。

这也是 Failure mode 2（vol 已经 spike 后别追）的镜像：对 macro print，spike 就是事件本身，所以唯一便宜的入场点在事件**之前**。

## Rule going forward

Scheduled macro 数据事件（NFP / CPI / FOMC）：hedge 在**事件前**建仓，不在事件后等 IV crush。「等事件后 IV 回落再 hedge」只适用于单名 ER（事件解决不确定性）。规则已写入 `macro-hedge-convexity.md` Failure mode 4 + `strategies.md` §Macro hedge trigger heuristics。
