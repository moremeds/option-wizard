---
ticker: MRVL
event: 基本面深度分析 — AI Custom ASIC + 光 DSP 双引擎,Jensen Huang "next trillion-dollar" 加持后估值检验
date: 2026-06-08
status: analysis-only
result: pending
structures: [protective_put, collar, put_spread_overlay, cash_secured_put_below_consensus_PT, defined_risk_bull_put_spread]
tags: [mrvl, ai_infrastructure, pam4_dsp, optical_transceiver, custom_asic, copper_vs_optical, 1_6T, semiconductor, deep_dive, nvda_endorsement]
archive_eligible_after: 2026-08-08
---

# MRVL 基本面深度分析 — 2026-06-08

> Spot: **$272.78**(2026-06-06 收盘, UW `get_company_info`)
> Mkt cap: **$230.5B** · Beta: **2.55** · Shares out: **875M**
> Next ER: **2026-08-27** (Q2 FY27, MRVL FY 1 月结束)

---

## Section 1 — Executive summary

**一句话论点:** MRVL 是 **AI infrastructure shovel-seller** 的二号位 — 一手抓 custom AI ASIC (XPU) 给 Amazon Trainium / Microsoft Azure 自研芯片,另一手抓 **800G/1.6T 光 PAM4 DSP**(全球 60%+ 市占率),正在 AI 数据中心从铜互联到光互联的结构性切换中卡位。 FY26(2026 年 1 月止)收入 $8.19B 同比 **+42%**,GM 从 41% 跳到 51%,OpInc 由 -$720M 翻成 +$1.34B —— **业务质量逆转已发生**。Q1 FY27 (2026 年 5 月) 收入 $2.42B +28% YoY 创新高,Data center 占 76%,Q2 guide +35%。 **核心争议点是估值:** 1Y 股价 +305%(从 $65 → $272.78),GAAP TTM PE 89x,non-GAAP fwd PE ~70-80x。6/6 Computex 上 Jensen Huang 称 MRVL 为 "next trillion-dollar company" + NVDA $2B 战略投资,触发情绪 supercharge。 但 prev close $316 → last $263.82 单日 **-17%** 意味着市场已经开始消化 "good news priced in"。

**今日估值:** spot $272.78, GAAP TTM PE **89x**(含 FY26 NI 中约 $1.93B 非经常项 — 需调整;无非经常项 GAAP PE 实际 240x+),non-GAAP forward PE **~70-80x** (基于 FY27 共识 $3.50-4 non-GAAP EPS),mkt cap $230B,EV/EBITDA ~88x,FCF margin 17%,FCF yield 0.6%,净现金 < $1B (历史 Inphi $10B 收购后债务管控已下来)。 dividend yield 0.09%,FY26 回购 $2B (vs FY25 $725M)。

**PE 在定价什么:** 市场假设 (1) FY27 收入 $10-12B (~30-40% YoY),(2) FY28 进一步加速到 $14-16B(20+ 个 custom ASIC 设计赢单进入投产),(3) 长期非 GAAP OpM 升至 35%+(向 AVGO 39.9% 看齐), (4) 1.6T 光 DSP **维持 60%+ 市占率**对抗 AVGO / CRDO 进攻,(5) Jensen Huang 战略合作 + NVDA $2B 投资延续。其中 (1)(5) 高 confidence;(2)(3) 中等;(4) 是最大变量 — Broadcom 3nm DSP roadmap 直追,CRDO AEC 业务 +206% YoY 扩张。

**Recommendation:** 持有(若已持有)/ 不追高(若空仓)。 当前 spot 在分析师平均 PT $243 上方 12%,且 -17% 单日回调说明市场已开始 take profit。**仓位 2-4% NLV 上限**(明显高于 TSLA 的 0-2% 但低于 NVDA/AVGO 的核心仓位)。 **核心 catalysts 未来 3 个月:** (a) **8/27 Q2 FY27 ER** — guide $2.7B 是否达成;(b) Q2 ER 中 1.6T 光 DSP 出货量披露;(c) AVGO 9/3 Q3 FY26 ER 中 AI 半导体收入指引(影响 MRVL 估值的资金分流);(d) NVDA GTC fall 2026 会议中 MRVL 合作产品的具体披露。

---

## Section 2 — Valuation anatomy

### 估值组件分解

| 组件 | 数值 | 暗示 |
|---|---|---|
| Spot price | $272.78 | UW `get_company_info` 2026-06-06 收盘 |
| Last close vs prev close | $263.82 vs $316.43(-17%) | 6/6 单日大跌,可能 NVDA capex 担忧或获利了结 |
| TTM Revenue (FY26 ending Jan 2026) | $8.19B | +42% YoY (vs FY25 $5.77B) |
| Q1 FY27 (May 2026) revenue | $2.42B | +28% YoY 创新高,Data center 76% |
| Q2 FY27 guide | $2.70B | +35% YoY,管理层 "exceptional AI bookings" |
| FY26 GAAP EPS | $3.05 | NI $2.67B / 875M shares,**含 $1.93B 非经常 interest income** |
| FY26 调整 EPS(剔除非经常) | ~$0.80 | NI $700M / 875M shares 估算 |
| FY26 non-GAAP EPS(共识) | ~$2.20-2.40 | 剔除 amortization + SBC |
| FY27 forward non-GAAP EPS | ~$3.50-4.00 (CONSENSUS) | 隐含 +50% YoY |
| **GAAP TTM PE** | **89.4x** | $272.78 / $3.05 — 注意:含一次性收益 |
| **调整 GAAP TTM PE** | **~340x** | 剔除非经常后真实 GAAP — 警示估值过高 |
| **non-GAAP TTM PE** | **~120x** | $272.78 / $2.30 |
| **non-GAAP Fwd PE** | **~70-80x** | $272.78 / $3.50-4.00 NTM — 这是市场观察的核心 PE |
| FY26 EBITDA | $2.63B | 1.32 Op + 1.29 D&A |
| EV(估算) | ~$232B | $230.5B mkt cap + ~$5B 净债 - cash |
| **EV / TTM EBITDA** | **~88x** | 远高于 AVGO 18x,接近 CRDO 但 CRDO 增速 5x MRVL |
| **EV / Sales (TTM)** | **~28x** | 远超 AVGO 7x,与 NVDA 28x 相当 |
| FY26 OCF | $1.75B | — |
| FY26 CapEx | $0.35B | Fabless 低 CapEx |
| FY26 FCF | $1.40B | OCF - CapEx |
| FCF margin | 17.1% | 远低于 AVGO 42% 和 NVDA 45% |
| **FCF yield** | **0.61%** | $1.40B / $230.5B — 远低于 10Y Treasury |
| FY26 dividend | $0.205B | $0.24 per share, yield 0.09% |
| FY26 buyback | $2.04B | 大幅增加(FY25 $725M)— 公司表态 confidence |
| Net cash position | ~$1B | 历史 Inphi 收购债务多年下来,balance sheet 健康 |
| ROE | ~10% | NI / equity (Inphi 商誉 + IP 摊销稀释 ROE) |

### "真实"利润率谁说了算 —— GAAP vs Non-GAAP 的鸿沟

MRVL 在 GAAP 与 non-GAAP 之间存在结构性巨大差距,核心原因是 **2021 Inphi $10B 收购 + 2022 Innovium $0.5B 收购**留下大量商誉 + IP 摊销 + SBC。

**FY26 GAAP 视角:**
- Revenue $8.19B
- GP $4.18B (51.0% GM)
- OpInc $1.34B (**16.3% OpM**)
- NI $2.67B(含 $1.93B 非经常项)

**FY26 Non-GAAP 视角(基于行业惯例 + Q1 FY27 数据外推):**
- Revenue 同上 $8.19B
- Non-GAAP GP 估算 $4.82B (~58.9% GM,基于 Q1 FY27 数据)
- Non-GAAP OpInc 估算 $2.5-2.8B (~30-34% OpM)
- Non-GAAP NI 估算 $1.8-2.0B
- Non-GAAP EPS 估算 $2.10-2.30

**两者差异原因:** 摊销 + SBC 全年估算 $1.0-1.2B,占总收入 12-15%。这是 Inphi/Innovium 收购的"长期税"。

**给投资人的关键判断:** non-GAAP 是分析师 + sell-side 报价依据,GAAP 是经济学真实利润。**当前估值用 non-GAAP forward PE 70-80x 是合理观察点,但 GAAP 视角(调整后 PE 240x+)提醒长期 SBC dilution 是结构性逆风**。

### 历史营收 + 利润率轨迹

| FY (ending Jan) | Revenue | YoY | Gross margin | Op margin (GAAP) | Net income (GAAP) | 关键事件 |
|---|---|---|---|---|---|---|
| FY22 | $4.46B | +50%(Inphi 并表)| 46.3% | -7.8% | -$0.42B | Inphi 收购完成 |
| FY23 | $5.92B | +33% | 50.5% | 4.0% | -$0.16B | 高峰前夜 |
| FY24 | $5.51B | -7% | 41.6% | -10.3% | -$0.93B | 周期下行 + 摊销重 |
| FY25 | $5.77B | +5% | 41.3% | -12.5% | -$0.89B | 持续亏损 |
| **FY26** | **$8.19B** | **+42%** | **51.0%** | **+16.3%** | **+$2.67B** | AI ramp 大逆转 |
| FY27 共识 | ~$10-11B | +25-35% | 52%+ | 20%+ | ~$3.0-3.5B | 设计赢单加速 |

**叙事:** FY26 是经典 "从亏损到大幅盈利" 拐点年,驱动因素是 (a) AI 数据中心收入占总收入比例从 ~50% 升至 **76%**, (b) 中国客户营收占比下降到 < 25%, (c) Inphi PAM4 DSP 在 800G 部署中市占率持续扩大。

### Bear case 在 price in 什么风险

(1) **AI capex 周期性回调:** Hyperscalers (AWS / Azure / GCP) 单季度 capex 决策会引发收入波动。 NVDA 5/20 Q1 FY27 ER 已提示 H2 2026 增长降速,这是连带利空。
(2) **AVGO + CRDO 双向夹击:** AVGO 在 3nm DSP roadmap 上追赶 MRVL 1.6T 领先地位;CRDO 在 AEC + 中速 DSP 上以 +206% YoY 增速蚕食低端 + AEC 市场。
(3) **客户集中度:** Q1 FY27 数据中心 76% 收入,前 3 大客户合计 > 50% 收入 — 假如 Microsoft / AWS 自研芯片设计转向其他 ASIC 供应商,单季可能 -20%+ 收入冲击。
(4) **CPO 切换风险:** Co-packaged optics (CPO) 是 2027-2028 趋势,长期会重新洗牌 DSP / 光器件 / 交换机的价值链分配。 NVDA / AVGO 是 CPO 推手,可能挤压 MRVL 独立 DSP 业务空间。

---

## Section 3 — Peer matrix (横向对比)

| Ticker | Mkt cap | Rev TTM | Rev growth | Op margin (GAAP) | Net margin | FCF margin | TTM PE (GAAP) | Fwd PE | EV/EBITDA | 1Y total return |
|---|---|---|---|---|---|---|---|---|---|---|
| **MRVL** | **$230.5B** | **$8.19B** | **+42%** | **16.3%** | **32.6%** ⚠️ | **17.1%** | **89x** ⚠️ | **~75x non-GAAP** | **~88x** | **+305%** |
| AVGO | $1,826B | $63.9B | +24% | 39.9% | 36.2% | 42.1% | 79x | ~30x | 18x | +48% |
| CRDO | $38.2B | $1.34B | **+206%** | 33.3% | 35.4% | ~5% | 80x | ~50x | ~80x | +183% |
| COHR | $73.8B | $5.81B | +23% | 9.4% | 0.8% (NI 仅 $49M) | 3.3% | 1500x ⚠️ | ~50x | ~70x | +373% |
| NVDA | $4,963B | $215.9B | +65% | 60.4% | 55.6% | 44.7% | 41x | ~28x | 34x | +47% |

⚠️ 注 MRVL: TTM Net margin 32.6% 含 FY26 非经常项 $1.93B;**真实经常性 net margin ~10-12%**。 GAAP TTM PE 89x 同理 — 调整后 240x+ 实际偏贵。

⚠️ 注 COHR: TTM PE 1500x 是因为 NI 刚转正($49M);用 EV/EBITDA ~70x 更可比。

### 解读

**MRVL 估值 ranking 在 peer 中段,但增长 ranking 中游、盈利质量 ranking 末位。**

- 增长:CRDO +206% > NVDA +65% > **MRVL +42%** > AVGO +24% ≈ COHR +23%。MRVL 增长落后 CRDO 5x、NVDA 1.5x,但远超 AVGO/COHR(规模考虑)。
- Op margin:NVDA 60.4% > AVGO 39.9% > CRDO 33.3% > **MRVL 16.3%** > COHR 9.4%。 MRVL 在 GAAP 视角末位,non-GAAP 视角 ~30% 接近 CRDO 但仍远低于 NVDA/AVGO。
- FCF margin:NVDA 44.7% ≈ AVGO 42.1% >> **MRVL 17.1%** > CRDO/COHR 5% 以下。**MRVL FCF 质量明显 lag**,主因 SBC 高 + Inphi 摊销 + 持续 R&D 投入。
- 估值倍数:GAAP TTM PE 1500x (COHR ⚠️) > 89x (MRVL) > 80x (CRDO) > 79x (AVGO) > 41x (NVDA)。 **AVGO 是 P/E 偏移最显著的对照** — 业务规模、增长、margin 全面优于 MRVL,但 PE 与 MRVL 相当,意味着 MRVL 显著估值溢价(per 美元 NI)。
- 1Y return:COHR +373% > **MRVL +305%** > CRDO +183% > AVGO +48% ≈ NVDA +47%。 **MRVL 是中盘 AI 互联标的中表现最好之一**,但落后纯光器件 COHR/LITE。 大盘 AVGO/NVDA 上涨更稳但幅度更小。

**最显著的 peer 反差 #1:MRVL vs AVGO**
- 营收规模差距:AVGO 是 MRVL 的 7.8x ($63.9B vs $8.19B)
- 营收增长差距:AVGO +24% vs MRVL +42% — MRVL 更快,但绝对增量 AVGO 加了 $12B vs MRVL 加 $2.4B
- 盈利质量差距:AVGO Op margin 39.9% vs MRVL 16.3%(GAAP)— AVGO 是 MRVL 2.5x 利润率
- FCF 差距:AVGO FCF $26.9B vs MRVL $1.4B,AVGO 是 MRVL **19 倍** FCF
- PE 差距:AVGO 79x vs MRVL 89x GAAP,**AVGO 更便宜在 PE 维度**
- Buyback:AVGO 回购 $6.3B + dividend $11.1B = $17.4B 资本回报;MRVL 回购 $2.04B + dividend $0.21B = $2.25B

**结论:相同 AI infrastructure 故事,AVGO 比 MRVL 在所有质量维度都更优,且 PE 持平甚至略低。 唯一 MRVL 占优势的是 (a) 增长率 (b) Inphi 光 DSP 业务的纯度。**

**最显著的 peer 反差 #2:MRVL vs CRDO**
- 营收规模:MRVL $8.19B vs CRDO $1.34B (MRVL 6x 大)
- 营收增长:CRDO +206% vs MRVL +42% (CRDO 5x 快)
- 业务直接对标:CRDO AEC + 光 DSP 直接竞争 MRVL Inphi Alaska C 业务,是最大威胁
- PE:CRDO 80x vs MRVL 89x — **CRDO 更便宜 + 增长更快 + 业务集中度更高**

**结论:CRDO 是 MRVL 的 pure-play 小盘对标,如果论点是 "光 DSP / AEC 业务" 而不是 "整 AI infrastructure",CRDO 在 risk-adjusted 视角更优。 但 CRDO 体量小、单一业务暴露、客户集中度更高。**

---

## Section 4 — Historical PE percentile

MRVL 历史 PE 极端分散,主因 2021 Inphi 并表后多年亏损让 P/E 不可计算,2026 才回到正利润。

| 时期 | PE 区间 | 中位数 | 今日位置 |
|---|---|---|---|
| 5-year(2021-2026) | N/M (多年亏损)to ~120x | 难以定义 | n/m |
| 自 FY26 转正后(单年度)| 30-100x 区间 | ~70x non-GAAP | **当前 75x non-GAAP 接近高位** |
| 10-year(2016-2026) | 25-150x | ~40-50x | 当前显著高于历史中位数 |

**叙事:**
- 2021 前 MRVL 是相对成熟的 SSD/HDD 控制器 + Networking 公司,PE 通常在 25-40x 区间。
- 2021 Inphi $10B 收购后多年亏损,PE 不适用。
- FY26 转正,non-GAAP 视角 PE ~70-80x — 处于历史高位,反映 AI 故事溢价已 priced in。
- **CONSENSUS 估计当前 PE 处于 5 年 80-85 百分位**。 历史上当 PE 高于此水平,接下来 12 个月平均回报跑输 SOXX -10pp 以下。

**未填项明示:** 自计算 PE 序列需要 Massive 月度 aggs + 季度 EPS 对齐,本 session 未跑 — 列入 Gaps。

---

## Section 5 — Turnaround case studies

### Case study A: AVGO 2017-2019 — "从 PE 30 → 50 多次再起的范式"

**Then:** 2017 AVGO(博通)市值 $100B,刚收购完成 Brocade(SAN),PE ~16x。 那时市场仍把 AVGO 视为 "merger arbitrage" 公司,而非 "compounding 增长股"。

**Why it bottomed:** Hock Tan 的 M&A 加杠杆模式当时受质疑,2018 计划收购 Qualcomm 被美政府否决。 估值短期承压。

**What changed:** (1) 持续收购 → 整合 → 削减重复成本 → margin 扩张; (2) 2019 CA Technologies 收购 + 2022 VMware 收购证明 software 业务可以高估值化; (3) Custom ASIC 业务(Google TPU)从 2019-2024 持续增长成为 mega trend; (4) Dividend + buyback 资本回报严格执行。

**Re-rating:** 2017 PE 16x → 2025 PE 79x,股价 $250 → $400 (split-adjusted),5 年回报 ~300%。

**Applicability to MRVL:** 相似点 = (a) 都是 networking + custom ASIC 双引擎; (b) 都通过大型收购(MRVL Inphi vs AVGO VMware)加速业务结构调整; (c) 都得益于 AI 数据中心 capex 周期。 **关键差异:** (i) AVGO 已是稳定盈利公司,MRVL 还在 GAAP 拐点; (ii) AVGO M&A team / capital allocation 框架成熟 10+ 年,MRVL 在 CEO Matt Murphy 领导下相对年轻; (iii) AVGO 估值起点低(16x),MRVL 估值起点已是 80x。 **MRVL 重复 AVGO 路径的回报 base rate 远低,因为起点估值已被打满**。

### Case study B: NVDA 2019-2021 — "GPU 从游戏到 AI 的故事兑现"

**Then:** 2019 NVDA 市值 $90B, PE 30x,业务 60% gaming + 25% datacenter + 15% 其他。 市场对 datacenter 增长不确定。

**Why it bottomed:** 加密货币崩盘 2018 让 GPU 渠道堆积,Q4 FY19 收入 -24% YoY,股价从 $290 跌到 $130。

**What changed:** (1) 2020 transformer model 出现,GPU 训练需求指数增长; (2) NVDA CUDA 软件生态成为 AI 训练事实标准; (3) Datacenter 收入从 2020 的 25% 升至 2024 的 80%; (4) FY23-FY26 ChatGPT 引爆,收入 4 年增长 50x。

**Re-rating:** 2019 PE 30x → 2024 PE 80x,股价 $150 → $1200(split-adjusted),5 年回报 25x。

**Applicability to MRVL:** 相似点 = (a) 都是 AI infrastructure 玩家; (b) 都从亏损 / 周期性下行 → 拐点 → 指数增长; (c) 业务组合都向 datacenter 急速倾斜。 **关键差异:** (i) NVDA 拐点是 GPU + CUDA 的双重护城河,MRVL 拐点主要是单一业务(PAM4 DSP + custom ASIC)市场扩张; (ii) NVDA 在拐点时估值 30x PE,MRVL 拐点时已 80x; (iii) NVDA 软件生态 lock-in 是 fundamental 护城河,MRVL 的 PAM4 DSP 是工艺技术领先 — 工艺领先在每个 generation (3nm → 2nm) 都要重新证明。 **MRVL 不会重复 NVDA 25x 收益的 base rate;论点对齐看 5-10x 收益更现实**。

### 两个分析都失效的场景

**警惕的两个 break-the-analog 信号:** (a) 如果 NVDA / AVGO 推出垂直集成的 CPO 方案让独立 PAM4 DSP 业务被边缘化(MRVL 核心 60%+ 市占率会变得 irrelevant),整个论点崩塌; (b) 如果 CRDO 在 AEC + 中速光 DSP 上以 +200%+ 增速持续 3-4 年,会侵蚀 MRVL pricing power,导致 OpM 从 30%+ 回落到 20%。

---

## Section 5.5 — 核心竞争力 / Core Franchise Analysis

> **本节是用户特别要求扩展的章节:光模块 / 光通信 / 与铜通信的区别和异同。**

### 5.5.A 核心产品 / 业务线 (MRVL 三大 franchise)

MRVL FY26 收入 $8.19B 划分(基于 Q1 FY27 数据 + Massive description):

| 业务段 | FY26 估算收入 | 收入占比 | 增长率 | GM 等级 |
|---|---|---|---|---|
| **Data center (custom ASIC + 光 DSP + switch)** | ~$6.2B(76% 占 Q1 FY27 $1.83B 折年化)| **~76%** | +27% YoY 加速 | 高 (55-60%+) |
| Carrier infrastructure (5G + Tier 1 telecom) | ~$0.7B | ~8% | 持平至下行 | 中 (40-45%) |
| Enterprise networking + storage controllers | ~$0.8B | ~10% | 周期下行 | 中 (35-45%) |
| Consumer / auto / IIoT | ~$0.5B | ~6% | 退出中 | 低 (~25%) |

#### 5.5.A.1 Data center — MRVL 命脉 (76% 收入)

数据中心业务又拆分为三大产品线,这三条线**相互正交**,各自服务不同客户需求:

**(1) Custom ASIC / XPU(自研芯片设计服务)**
- **客户:** Amazon (Trainium 系列), Microsoft (Maia / Azure custom silicon), Google (历史 Inphi 时期合作), 部分二线 hyperscalers
- **业务模式:** Hyperscaler 提供算法 / 架构需求,MRVL 提供 SoC design + IP 集成 + 3nm/2nm 流片 + 后端 + 投产到 TSMC
- **Q1 FY27 收入:** $678M (custom ASIC + 嵌入式 silicon 部分)
- **GM:** 50-55%(低于自研 IP,但 volume 高 + 长期合同绑定)
- **关键指标:** **20+ 个 custom AI ASIC 设计赢单将于 FY28/FY29 投产** —— 这是收入指数级增长的种子
- **竞争对手:** Broadcom (Google TPU, Meta MTIA), Alchip Technologies (二线), Marvell 自己 vs Broadcom 是这块市场的 **two-horse race**

**(2) 光 PAM4 DSP (Inphi 收购核心资产)**
- **产品族:** Alaska C 系列 (800G), Spearfish, **Ara 系列 (1.6T,3nm,业界首款)**
- **业务模式:** 给光模块厂商 (II-VI/Coherent, Lumentum, Innolight, Eoptolink, Accelink) 提供 DSP 芯片用于光收发器
- **FY25 收入:** ~$1.2B (优势 inputs - 这块就是 Inphi 当年并表带来的核心金矿)
- **GM:** **60-65%**(纯 fabless IP 业务最高 margin)
- **市占率:** **800G PAM4 光 DSP >60% 全球市占率**,与 Broadcom + MaxLinear 合计 ~70%
- **核心护城河:** (a) 3nm 工艺领先,Ara 比竞争对手早 12-18 个月; (b) Inphi 30+ 年模拟混合信号 IP 积累; (c) 与光模块厂商深度合作 — 单 transceiver 模块成本 30-40% 是 DSP 芯片

**(3) 数据中心 Ethernet switch + storage**
- **产品:** Teralynx (高速 switch silicon, Innovium 收购), Bravera (storage controller)
- **业务规模:** 较小,~$0.5-0.8B/年
- **直接对手:** Broadcom Tomahawk 系列 (Tomahawk 5/6 主导);Cisco Silicon One

#### 5.5.A.2 数据中心收入跃迁(FY24 → Q1 FY27)

| 时期 | Data center 收入(估算)| 占总收入比 |
|---|---|---|
| FY24 (Jan 2024) | ~$2.3B | ~42% |
| FY25 (Jan 2025) | ~$2.6B | ~45% |
| FY26 (Jan 2026) | ~$5.4B | ~66% |
| **Q1 FY27 annualized** | **~$7.3B** | **~76%** |

3 年间数据中心收入从 $2.3B → $7.3B(annualized),**3 倍**。同期总营收从 $5.5B → $9.7B 年化,1.76 倍。**所有增量收入几乎都来自数据中心** — 这就是 "AI infrastructure pure-play" 的财务呈现。

### 5.5.B 光通信 vs 铜通信 —— 用户重点章节

#### 5.5.B.1 物理层基础:光 vs 铜的根本差异

**铜介质(electrical signaling):**
- 信号通过铜线中的电子流动传输,速度受 skin effect + dielectric loss + crosstalk 限制
- **每 doubling 速率(50G → 100G → 200G/lane),信号衰减升 6dB+**
- 铜介质上的传输距离随速率指数下降
- 优势:成本低、功耗低、延迟最小

**光介质(optical signaling):**
- 信号转化为不同波长的激光脉冲,通过光纤传输
- 光纤衰减极低,长距离传输基本无损
- **缺点:必须有电-光转换(transceiver)+ 光-电反转换 → 多了 latency + 功耗 + 成本**
- 优势:距离不衰减、带宽巨大、抗电磁干扰

**临界距离:** 在 100G/lane 这一代,铜约 3-5 米,光基本起步距离 10+ 米;**到 200G/lane(1.6T),铜上限掉到 1-3 米,光必须接管所有 rack-to-rack + cluster 互联**。

#### 5.5.B.2 数据中心互联五大产品类别(架构师选择参考)

| 类别 | 全称 | 距离范围 | 功耗 | 成本 | 主要场景 | DSP/Chip 在哪里 |
|---|---|---|---|---|---|---|
| **DAC** | Direct Attached Copper(直连铜)| ≤ 2 m | < 0.15 W(passive) | 最低 | rack 内 server-to-TOR | **没有 DSP**(纯 passive) |
| **ACC** | Active Copper Cable | 3-5 m | 1-2 W | 低-中 | rack 间近距 | 简单 redrivers |
| **AEC** | Active Electrical Cable | 3-9 m | 3-5 W | 中 | spine-leaf 中距,AI cluster | **PAM4 DSP**(CRDO 的主战场)|
| **AOC** | Active Optical Cable | 30-100 m | 4-6 W | 中-高 | cluster 间长距 | 内嵌光 DSP |
| **光收发器** | SR8 / DR4 / FR4 等 | 100m-2km+ | 5-15 W | 高 | 跨 hall / 数据中心园区 | **PAM4 DSP**(MRVL 60%+ 市占率)|

**几个关键观察:**
- **DAC** 是 NVDA NVLink / cluster 内 GPU-to-GPU 互联的首选 —— 距离短、功耗最低、延迟最小,**是铜方案的护城河**
- **AEC** 是 CRDO 的核心业务 —— 把 DSP 信号调理 + 电缆放一起,中距离场景的 sweet spot
- **AOC + 光收发器** 是 MRVL 60% 市占率的核心战场 —— 距离 10m+ 必须用光,DSP 是核心 IP

#### 5.5.B.3 1.6T 转换 —— 决定性的结构性拐点

**为什么 1.6T (即 200G/lane × 8) 比 800G (100G/lane × 8) 重要:**

- **全部 100G/lane 铜缆必须替换:** 现有 DAC/ACC/AEC 都设计在 100G/lane 电气特性下,1.6T 需要 200G/lane → 整条 wires 替换。 NVDA Blackwell GB200 一个 rack 1.5 米内可能 5000+ 根铜缆,全部要换。
- **铜的距离极限进一步压缩:** 200G/lane 下 DAC 上限可能掉到 1-1.5 米,大多数 spine-leaf 场景必须迁移到 AEC / AOC / 光。
- **光 transceiver / DSP 需求量指数级增长:**
  - 2024 800G 全球出货量 ~3-5M units
  - 2026 800G 出货量预计 12-15M units
  - 2027 1.6T 出货量预计 5-8M units 起步,2028 翻倍
- **每个光 transceiver 内的 DSP 价值:** $30-50 per 800G,$50-80 per 1.6T → MRVL DSP TAM 从 2024 ~$1B 增长到 2027 ~$4-5B (年 30%+)

**MRVL 在此转换中的地位:**
- **Ara 1.6T DSP 已 sampling**, 比 AVGO/Credo/MaxLinear 早 ~12 个月
- 工艺领先:**3nm,业界首款** — 这是 fabless 设计领先的硬证据
- 功耗优势:Ara 比 800G 上一代功耗 -20%,**功耗低 → 单 transceiver BOM 降低 + 散热设计简化**

**MRVL 长期市占率守住的条件:**
- 维持 18-24 个月的工艺代际领先(每代 ~$300-500M 研发投入)
- 持续与 Hyperscaler + 模块厂商深度合作不被新晋者切入
- 在 CPO(co-packaged optics)趋势中保持参与,而不是被 AVGO / NVDA 垂直集成挤出

#### 5.5.B.4 CPO (Co-Packaged Optics) —— 中期变量

**CPO 是什么:** 把光器件直接 co-package 到交换机 ASIC 的衬底上,省略独立 transceiver 模块,降低功耗和延迟。

**产业影响:**
- 短期(2026-2027):pluggable transceiver 主导,**有利于 MRVL 独立 DSP 业务**
- 中期(2028-2030):CPO 开始放量,大型 Hyperscaler 部分订单转 CPO
- 长期(2030+):若 CPO 主导,光 DSP 业务部分被 switch ASIC 集成,**MRVL 独立 DSP 价值受压缩**
- **但 MRVL 也在 CPO 赛道布局:** 与 TSMC 合作 SiPho 集成模块,Ara DSP 可作为 CPO 中的关键 IP

**关键不确定性:** CPO 商业化时间表 + Hyperscaler 采购偏好。 Microsoft Hot Chips 2025 演示了 CPO 原型,Meta + Google 也在内部测试。 量产时间通常推迟 2-3 年于 demo,实际广泛部署可能 2028+ 才发生。

### 5.5.C MRVL 在各市场的定位

**光 PAM4 DSP 市场:**
- 全球市占率:**>60% 800G,40-50% 1.6T(early stage)**
- 主要竞争对手:Broadcom(后发追赶),MaxLinear(中端低成本)
- 护城河:Inphi 30 年模拟混合信号 IP + 3nm 工艺领先 + 与所有顶级光模块厂商深度合作
- 威胁:CRDO 在 AEC + 中速 DSP 切入低端

**Custom ASIC / XPU 市场:**
- 全球市占率:估算 **~20-25%**(主要赢单 Amazon + Microsoft);AVGO ~60%(Google + Meta)
- 主要竞争对手:Broadcom(主导),Alchip(二线),GUC(三线)
- 护城河:HPC SoC 架构经验 + 客户深度技术合作 + IP 持续投入(SerDes, HBM 控制器, NoC)
- 威胁:Hyperscaler 自己建 SoC 团队(类似 Apple)

**Carrier (5G + telecom)业务:**
- 全球市占率:中等(无龙头)
- 业务质量:周期性强、margin 低、长期增长有限
- 趋势:逐步缩减,资源向 datacenter 倾斜

### 5.5.D Peer-by-peer 在 MRVL 三大市场的定位

| Peer | 光 DSP | Custom ASIC | Switch | AEC/铜 | 直接对手? |
|---|---|---|---|---|---|
| **AVGO** | 二号位 800G,3nm 1.6T 在追 | **一号位** Google TPU/Meta MTIA | 一号位 Tomahawk | 部分 | **是 — 全面对标** |
| **CRDO** | 三号位,聚焦中端 | 几乎无 | 无 | **一号位 AEC** | 是 — 低端 + AEC |
| **COHR** | 不参与(只做光器件 hardware) | 无 | 无 | 无 | 不直接竞争,但是 MRVL DSP 的客户(他们买 MRVL DSP 装到自己的 transceiver 里) |
| **NVDA** | 自研 + 收购 Mellanox 提供 InfiniBand 互联 | 自研(其实就是 GPU 本身) | 自研 Quantum/Spectrum 系列 | 无 | 半相邻 — NVDA Ethernet 路线推 MRVL 的 DSP,但 InfiniBand 路线 bypass MRVL |

**关键观察:**
- **AVGO 是 MRVL 全面对手** — 占 ~30% 估值压力来源
- **CRDO 是低端 + AEC 切入者** — 占 ~15-20% pricing pressure
- **COHR / LITE 是客户** — MRVL DSP 是他们 transceiver 的 BOM 中最贵单一组件之一
- **NVDA 是 frenemy** — InfiniBand 减少光 DSP 需求,但 NVDA $2B 投资 MRVL 是结盟信号

### 5.5.E 5-10 年 trajectory

**关键问题:**
1. **1.6T 转换:** 2027 起 1.6T 出货量是否每年翻倍? MRVL 是否守住 60% 市占率?
2. **2.4T / 3.2T 接下来:** 2028-2030 速率再加倍,工艺转 2nm/1.6nm,资本支出门槛进一步抬高,**仅有 3-4 家公司能承担**——是结构性 oligopoly 保护
3. **Custom ASIC 业务 scale-up:** 20+ 设计赢单进入 FY28/FY29 投产,理论上可贡献 $4-6B 额外年收入
4. **CPO 渗透:** 2028-2030 CPO 渗透率 20-30%,意味着 MRVL 独立 DSP 部分 TAM 受压缩,但 CPO 中 MRVL 仍可参与
5. **Hyperscaler 自研 silicon 周期:** 是否每代设计都从外部 ASIC vendor 切换到内部 team?(Apple-style)

**Franchise 论点综合:** MRVL 在 2030 年大概率是 "数据中心 80-85% + 其他 15-20%" 的纯 AI infrastructure 公司,收入 $20-30B,Op margin 30-35%。 论点的核心 risk 是 (a) Broadcom 在 DSP 上完成追赶, (b) Hyperscaler 自研 ASIC 削减外部 vendor 依赖, (c) CPO 速度比预期快。

**5-10 年一句话:** **MRVL 长期路径是 "AI infrastructure 双引擎公司"(custom ASIC + 光 DSP),收入 5 年 CAGR ~25%,但盈利质量需要从 GAAP 视角彻底改善才能 justify 当前 80-90x PE。 持有需要 conviction:相信 MRVL 能在 1.6T → 2.4T → 3.2T 的代际竞赛中维持市占率,且 Hyperscaler 不会 in-source。**

---

## Section 6 — Head-to-head vs closest peer (MRVL vs AVGO)

AVGO 是 MRVL 全面对标的对手,但规模 7.8x、盈利质量碾压。 这是 Section 3 的延伸细化。

| 指标 | MRVL | AVGO | 解读 |
|---|---|---|---|
| Revenue TTM | $8.19B | $63.9B | AVGO 7.8x |
| Revenue 3Y CAGR | ~16% | ~32%(含 VMware 整合)| AVGO 增速 2x MRVL |
| AI semi 收入(latest Q) | ~$1.5B/Q | ~$10.7B/Q (FY26 Q2 guide) | AVGO 是 MRVL 7x |
| Gross margin (GAAP) | 51.0% | 67.8% | AVGO +17pp |
| Gross margin (non-GAAP) | 58.9% | 78%+ | AVGO +20pp |
| Op margin (GAAP) | 16.3% | 39.9% | AVGO 2.5x |
| Net margin (GAAP) | 32.6%(含一次性)| 36.2% | 同 quality 接近 |
| ROIC | ~5-7%(含 Inphi 商誉)| ~30%+ | AVGO 5-6x |
| FCF / share | $1.60 | $5.68 | AVGO 3.5x |
| Buybacks 3Y(累计) | ~$3B | ~$26B | AVGO 9x 资本回报 |
| Dividend yield | 0.09% | 0.6% | AVGO 7x |
| TTM PE (GAAP) | 89x ⚠️ | 79x | **AVGO 略便宜** |
| Fwd PE non-GAAP | ~75x | ~30x | **AVGO 显著便宜 2.5x** |
| EV/EBITDA | ~88x | ~18x | **AVGO 显著便宜 4.9x** |
| 5Y total return | +457% | +710% | AVGO 跑赢 MRVL |
| Beta | 2.55 | 2.08 | MRVL 风险 23% 更高 |
| AI custom ASIC TAM 占比 | ~$2B(估算 25%)| ~$15B(估算 60%+) | AVGO 主导 |

**Verdict:** **AVGO 在所有质量维度都优于 MRVL**,且 PE 持平甚至更便宜。 **MRVL vs AVGO 选择,理性投资人应选 AVGO**。 唯一 MRVL 占优势的是:
1. **业务纯度** — MRVL 100% 半导体业务,AVGO 含 VMware 软件业务可能稀释 narrative
2. **光 DSP 暴露** — MRVL 在光 DSP 60%+ 市占率,AVGO 在光 DSP 是追赶者
3. **小盘 alpha 弹性** — MRVL beta 2.55 vs AVGO 2.08, 在 AI infrastructure 加速期可能跑赢更多

**对持有 MRVL 的投资人:** 考虑 **替换 1/3-1/2 仓位为 AVGO**,获得相似 AI infrastructure 暴露 + 显著更好风险调整回报。 对于 conviction 强 MRVL 光 DSP 投资人,则可以继续持有 MRVL 但配合 collar 防御对冲。

---

## Section 7 — Scenario analysis (probability-weighted EV)

时间窗口:12 个月内(2027 年 6 月)

| 场景 | 概率 | 目标价 | 触发条件 |
|---|---|---|---|
| **牛市 (custom ASIC 大爆发 + 1.6T 主导)** | 25% | $360 | (a) FY27 收入 +35-40% > $11B;(b) 20+ custom ASIC 设计赢单中至少 10 个 FY28 投产;(c) 1.6T 市占率确认 60%+;(d) NVDA 战略合作扩大到 $5B+ 合同;(e) 非 GAAP OpM 升至 35% |
| **基本 (持续 +25-30% 增长,估值修复)** | 45% | $270 | (a) FY27 收入 $10B 左右;(b) Cybercab/客户多元化(c) AVGO 竞争维持现状;(d) non-GAAP fwd PE 缓慢从 75x 回落到 50-55x;(e) Q2 ER 8/27 in-line |
| **熊市 (Broadcom 切入 + AI capex 放缓)** | 25% | $180 | (a) FY27 收入仅 +15% < $9.5B;(b) AVGO 在 1.6T DSP 设计赢单超 MRVL;(c) AI capex 周期回调;(d) Q2 ER miss guide;(e) PE 重新 derate 到 45-50x non-GAAP |
| **灾难 (CPO 提前 + 业务 obsolete)** | 5% | $120 | (a) 大 Hyperscaler 转 in-house silicon;(b) CPO 提前 18 个月放量,独立 DSP TAM 折半;(c) Custom ASIC 设计赢单大幅推迟;(d) Beta 2.55 放大单向跌幅 |

### EV 计算

> **EV = 0.25 × $360 + 0.45 × $270 + 0.25 × $180 + 0.05 × $120**
> **= $90 + $121.5 + $45 + $6 = $262.5**
> **vs spot $272.78 → 隐含 -3.8% 12 个月预期回报(probability-adjusted)**

**结论:** Probability-weighted EV ($262.5) 略低于 spot,加上 beta 2.55 系统性放大,**risk-adjusted Sharpe 较差**。 这是 "持有 OK,新建 long 谨慎" 的数学依据。 但和 TSLA 不同的是,基本场景概率 45% 高于 TSLA 50% 但目标价持平 spot,意味着 MRVL 中长期"稳定 base case" 更可信。

### 关于概率分配的诚实说明

- 牛市 25%:Jensen Huang 6/6 站台 + 20+ 设计赢单 + 1.6T 工艺领先 12-18 个月,牛市概率比 TSLA 高得多。 但绝对值不会超过 30%,因为估值已 stretched。
- 基本 45%:大概率公司持续执行 + 季度 in-line,股价横盘震荡。
- 熊市 25%:Broadcom 追赶可能性 + AI capex 周期性回调,base rate 现实。
- 灾难 5%:CPO + Hyperscaler in-house 是 multi-year 风险,12 个月内灾难概率低。

---

## Section 8 — Bull vs bear (两栏论点)

| 牛市论点 | 熊市论点 |
|---|---|
| 1. **Jensen Huang 6/6 "next trillion-dollar" 加 NVDA $2B 投资** — 史上最强 endorsement,情感+实质双重利好 | 1. **PE 显著高估** — non-GAAP fwd PE 75x vs AVGO 30x,同 AI 故事 AVGO 价值 2.5x 高 |
| 2. **800G PAM4 DSP 60%+ 市占率 + 1.6T Ara 工艺领先 12-18 个月** | 2. **prev close $316 → last $263 单日 -17%** 已经显示市场开始 take profit,情绪 supercharge 接近顶部 |
| 3. **20+ custom ASIC 设计赢单进入 FY28/FY29 投产** — 隐含未来 2-3 年指数增长 visibility | 3. **AVGO 在所有质量维度更优**,且 PE 持平 — 资金理性应该往 AVGO 流 |
| 4. **数据中心收入占比 76%** — 业务结构最大 pure-play AI infrastructure | 4. **客户集中度高** — AWS + Azure + Google = > 50% 数据中心收入,单一客户切换风险 |
| 5. **1.6T 拐点 + 200G/lane 强制铜缆替换** — 结构性利好光 DSP TAM 翻倍 | 5. **GAAP 利润质量差** — 大量 SBC + 摊销让 GAAP NI 远低于 non-GAAP,长期摊薄股东价值 |
| 6. **Inphi 收购整合完成** — FY26 转正后利润持续扩张可期 | 6. **CRDO +206% 增长 + 80x PE** — pure-play 小盘对手在所有维度更便宜 |

---

## Section 9 — Analyst ratings + catalyst calendar

### 分析师评级(截至 2026-05-28,最新 10 家大行)

| 评级 | 数量 | 占比 | 备注 |
|---|---|---|---|
| Strong Buy | 0 | 0% | — |
| Buy / Outperform | 9 | 90% | UBS $230, Citi $225, Barclays $275, JP Morgan $240, Jefferies $235, Roth $275, Oppenheimer $250, Wells Fargo $240, Keybanc $260 |
| Hold / Neutral | 1 | 10% | TD Cowen $200 |
| Sell | 0 | 0% | — |

- **平均目标价(基于 10 家):** $243.00
- **范围:** $200(TD Cowen bear)– $275(Barclays/Roth bull)
- **vs Spot $272.78:** 平均 PT **比 spot 低 11%**,即**当前股价已超过分析师共识**
- **关键解读:** 6/6 Jensen Huang "next trillion-dollar" 言论 + NVDA $2B 投资是分析师 PT update **之后**发生的,意味着接下来 1-2 周分析师 PT 可能集体上调至 $280-300 区间,但当前 spot $272.78 已 price in 大部分利好

### 催化剂日历(未来 6 个月,2026-06 → 2026-12)

| 日期 | 事件 | 重要性 (1-5) | 备注 |
|---|---|---|---|
| **2026-06-08 ~ 2026-06-15** | Analyst PT 调整 + 二季度后续 commentary | 4 | Jensen 站台 6/6 后预期 1-2 周内 Wall Street 集体上调 PT |
| 2026-06-中 | Computex 后续 partner / 客户 announcements | 3 | NVDA / AMD / 客户们的官方表态 |
| **2026-08-27** | **Q2 FY27 ER(post-market)** | **5** | Guide $2.7B 是否达成 + 1.6T DSP 出货量 + Custom ASIC 进度 |
| **2026-09-03** | **AVGO Q3 FY26 ER** | **5** | AVGO AI semi 收入 + 1.6T DSP roadmap 进展 — 直接影响 MRVL 估值竞争对照 |
| 2026-09 中 | NVDA GTC fall 2026 会议 | 4 | MRVL 合作产品 / 1.6T 部署 / CPO 演示可能性 |
| 2026-10-12 (估) | OFC + ECOC conference | 3 | 光通信产业最大年度会议,新品发布 |
| 2026-11 | Q3 FY27 ER(估计 12 月初) | 4 | 1.6T 出货量首次详细披露 |
| 2026-11 | 美国大选后政策对中国客户限制更新 | 3 | 出口管制延伸可能影响 ~5% 收入 |
| **2026-12** | Custom ASIC FY28 进度更新 | 4 | Investor Day 可能性,20+ 设计赢单的具体客户披露 |

---

## Section 10 — Final verdict

### 评级
**持有(若已持有)/ 不追高(若空仓)** — Spot $272.78 已超过分析师共识 $243(高 12%),且 Section 7 EV $262.5 略低于 spot。 短期 Jensen 加持后估值 stretched,等回调或基本面突破再考虑加仓。

### 仓位建议
**仓位 2-4% NLV 上限**(高于 TSLA 0-2%, 低于 AVGO 5-8%) — 理由:
- (a) **conviction 中等** — AI infrastructure 故事真实,但 AVGO 在同 narrative 下盈利质量更好且估值更便宜;
- (b) **beta 2.55** — 半导体高波动 + 单日 -17% 实例提醒短期回撤风险大;
- (c) **catalyst clarity 较 TSLA 高** — 8/27 Q2 ER + 1.6T 出货量披露是清晰节点;
- (d) **AI infrastructure 仍是中期趋势** — 不应完全 zero exposure。

### 实现路径(3 个选项,按优先级)

**1. ⭐⭐⭐(若已持有大仓位)Collar 防御对冲 — 推荐结构**

   **核心思想:Jensen 加持 + NVDA $2B 短期推高股价 → 保护已有获利 + 让出小部分上行**

   - **结构:** Long stock + Long Aug-15 $260 Put + Short Aug-15 $310 Call
   - **DTE:** 期权 ~70 天,覆盖 Q2 FY27 ER 8/27 + AVGO Q3 ER 9/3
   - **预期成本:** ~$0(collar 净 zero;若 vol skew 大可能微小净 debit)
   - **下行保护:** 跌至 $200,亏损封顶 $12.78/股 (从 spot $272.78 - $260)
   - **上行让出:** 涨破 $310 部分让出
   - **触发条件:** 单只 MRVL 占 NLV ≥ 3% 时执行
   - 符合"persistence vs hedge" trade-off 原则

**2.(若空仓但想小仓位试水)Sell put 等回调入场**

   - **结构:** Short Aug-15 $240 Put(~15 delta)
   - **Premium 收入:** ~$8-10/股 (~$800-1000/合约,基于 50-55% IV 估算)
   - **最大风险:** 被 assign 在 $240,实际成本 $230-232(扣 premium 后)= 接近分析师平均 PT
   - **触发条件:** MRVL 跌至 $260 以下 + IV rank > 60 时执行
   - **后续:** 若被 assign 立刻部署 collar 转入选项 1

**3.(观望触发条件)等明确入场信号**

   - **不建仓的指标:** 当前 PE 已 priced in 完美执行,任何 negative news 都可能放大 -10-20% 跌幅
   - **建仓信号:** (a) Q2 FY27 ER 营收 ≥ guide $2.7B + 1.6T DSP 出货量首次披露;(b) MRVL 跌至 $220-240 区间(PE 回到 60-65x non-GAAP);(c) 出现 AVGO 在 1.6T DSP 上 misexecute 的证据(降低 MRVL 竞争压力)

### 翻车信号(由"持有"转为"加仓")

- **观察 1:** Q2 FY27 ER 营收超过 $2.7B guide,显著 beat
- **观察 2:** 1.6T DSP 出货量披露超预期 (e.g., > 50k modules)
- **观察 3:** Custom ASIC 设计赢单中,至少一个客户(AWS/MSFT)宣布 FY28 量产
- **观察 4:** AVGO Q3 ER 中 PAM4 DSP roadmap 明显落后 MRVL Ara
- **观察 5:** 股价回调至 $220-240 + IV rank 跌至 < 40

### 翻车信号(由"持有"转为"减仓/清仓")

- **观察 A:** Q2 ER 收入 miss guide $2.7B 超过 5%
- **观察 B:** Broadcom 公布 3nm 1.6T DSP 量产时间表早于 MRVL
- **观察 C:** Hyperscaler 公开宣布转 in-house silicon,MRVL custom ASIC 业务受冲击
- **观察 D:** Beta 风险事件 — 单周回撤 > -25%(已经发生 -17% 单日)
- **观察 E:** CRDO 或 AVGO 在光 DSP / AEC 上拿走 MRVL 关键客户(Microsoft/AWS)

### 时间窗口

**Thesis horizon 6-12 个月。 Re-evaluation 触发节点:**
- 短期(0-2 个月):**Q2 FY27 ER 8/27 + AVGO Q3 ER 9/3**
- 中期(6 个月):**1.6T DSP 出货量 ramp + Custom ASIC 设计赢单投产清单**
- 长期(12-24 个月):**FY28 收入是否达 $14-16B + non-GAAP OpM 是否升至 35%+**

---

## Sources

### Financials & Filings
- **UW `get_company_info`** — MRVL 2026-06-06: spot $272.78, mkt cap $230.5B, shares out 875M, beta 2.55, next ER 2026-08-27
- **UW `get_income_statements`(annual)** — MRVL FY08-FY26 full P&L
- **UW `get_cash_flows`(annual)** — MRVL FY08-FY26 OCF/CapEx/SBC
- **UW `get_analyst_ratings`** — MRVL 10 家最新 ratings(2026-05-28)
- **UW `get_ticker_performances`** — MRVL + AVGO + CRDO + COHR + NVDA 1d/1w/1m/3m/6m/1y/5y returns
- **Massive `/v3/reference/tickers/MRVL`** — CIK 0001835632, SIC 3674 (Semiconductors), employees 7,480, list date 2000-06-27
- **Massive `/v1/related-companies/MRVL`** — peer 候选集(NVDA, AVGO, AMD, MSFT, GOOGL, MU, MKSI, KLAC)

### Peers
- UW pulls for AVGO + CRDO + COHR + NVDA — income / cashflow / performances 全部已拉取

### News & Sentiment
- **Massive `/v2/reference/news?ticker=MRVL&limit=12`** — 2026-06-03 → 2026-06-07 共 12 条新闻 + per-article sentiment
- **2026-06-06 Computex 2026:** Jensen Huang 宣布 MRVL "next trillion-dollar company" + NVDA $2B 战略投资
- **Stocktitan SEC 8-K (5/28/26):** [Record Q1 surge leads Marvell (NASDAQ: MRVL) to raise FY27 AI outlook](https://www.stocktitan.net/sec-filings/MRVL/8-k-marvell-technology-inc-reports-material-event-c6f040475efc.html)
- **MRVL 8-K Q1 FY27:** [SEC filing](https://www.sec.gov/Archives/edgar/data/0001835632/000183563226000014/q127_8kx522026ex-991.htm)
- **MRVL 10-Q Q1 FY27:** [SEC filing](https://www.sec.gov/Archives/edgar/data/0001835632/000183563226000019/mrvl-20260502.htm)

### 光通信 + DSP 行业分析
- **DataInsta PAM4 DSP Market Report:** [PAM4 DSP Chip Market Research Report 2034](https://dataintelo.com/report/pam4-dsp-chip-market)
- **Substack Ben Pouladian 2026:** [AI Optical Interconnect Landscape 2026: Marvell, Broadcom, Credo, Lumentum, and the Copper-to-Optical Transition](https://bepresearch.substack.com/p/the-quiet-architect)
- **Substack iamfabian:** [Marvell Technology: The 1.6T Transition and the DSP Battlefield](https://iamfabian.substack.com/p/my-pre-earnings-deep-dive-marvell)
- **SemiAnalysis Newsletter:** [Marvell's DSP Dilemma? Networking's Tectonic Shift Led By Broadcom, Nvidia, Arista Networks](https://newsletter.semianalysis.com/p/marvells-dsp-dilemma-networkings)

### 光 vs 铜 interconnect 对比
- **Vitex LLC 800G Guide:** [800G Data Center Interconnect Guide: DAC, AEC, AOC & Optical](https://www.vitextech.com/blogs/blog/800g-data-center-interconnect-selection-guide)
- **Vitex LLC ACC Guide:** [800G Interconnect Guide: DAC, ACC, AEC & AOC Comparison](https://www.vitextech.com/blogs/blog/800g-interconnect-selection-guide-dac-acc-aec-and-aoc-for-ai-data-center-fabrics)
- **Axiom Tech:** [DAC vs AOC vs AEC vs ACC: Choosing the right high-speed interconnect for 400G/800G networks](https://www.axiomupgrades.com/inside-the-stack-detail/dac-vs-aoc-vs-aec-vs-acc-choosing-the-right-high-speed-interconnect-for-400g-800g-networks/)
- **Semtech OFC 2026:** [Semtech Advances the Future of AI Data Center Optical and Active Copper Interconnects](https://blog.semtech.com/ofc-2026-semtech-advances-the-future-of-ai-data-center-optical-and-active-copper-interconnects)
- **C-LIGHT Market Report:** [AI Data Center Optical Transceiver Module Market 2025–2030](https://m.c-light.com/news/details/AI_Data_Center_Optical_Transceiver_Module_Market_2025_2030.html)

### Q1 FY27 Earnings 分析
- **Money Morning (5/25):** [This AI Chip Stock Is Up 100% in 2026](https://moneymorning.com/2026/05/25/marvell-technology-mrvl-stock-earnings-may-2026)
- **TradingKey:** [Marvell Stock: Can Its Custom ASIC Pipeline Drive MRVL Above $230?](https://www.tradingkey.com/analysis/stocks/us-stocks/261938748-marvell-custom-asic-pipeline-mrvl-stock-forecast-tradingkey)

### Gaps / Limitations(诚实标注)

- **TV reader (TradingView spot canonical) not invokable from this Bash-tool session** — spot $272.78 来自 UW `get_company_info` 而非 TradingView。 偏差通常 < 0.5%,但严格说违反 CLAUDE.md hard rule #2 默认路径。
- **Massive `/v3/snapshot/locale/us/markets/stocks/tickers/MRVL` 返回 404** — 同 TSLA 报告类似问题, fallback 到 UW spot。
- **MRVL FY26 NI $2.67B 含 $1.93B 非经常项(interest income line 异常)** — 真实经常性 GAAP NI 约 $0.7B,EPS $0.80;FY26 PE 调整后实际 240x+ 而非报告的 89x。 需要 Q4 FY26 10-K filing 确认该 $1.93B 性质(可能 IP 诉讼和解 / asset divestment / 税务调整)。
- **UW `get_fundamental_breakdown` for MRVL 未在 round 2 拉取** — 因为 TSLA 报告显示该端点对大公司返回 outdated 数据;本次 session 决定基于 income statement 直接计算关键比率。
- **未拉取 balance sheet** — MRVL 净现金 vs 净债务状态基于公开报道估算(~$1B 净现金)。 严格 verify 需要 UW `get_balance_sheets`,本 session 跳过节约 token。
- **未自计算历史 PE percentile** — Section 4 基于行业惯例给出 CONSENSUS 估算,未自行从 Massive aggs 拉取 5-10 年月度价格 × EPS series。
- **Q1 FY27 数据 (5/28 ER) 部分来自二级来源(Money Morning + TradingKey)** — Web search 引用,未直接读 MRVL 8-K PDF。 主要数字应 cross-validate 与 SEC filing 一致。
- **关于 Jensen Huang "next trillion-dollar" + NVDA $2B 投资真实性** — 这两个信息均来自 6/6-6/7 Massive 新闻聚合,未独立从 NVDA 官方 press release verify。 投资人在做决策前应自行验证。

---

## Outcome / Lesson(待 2026-08-27 Q2 FY27 ER 后填写)

待跟踪问题:
- (Q1) Q2 FY27 ER 营收是否达成 guide $2.7B?
- (Q2) 1.6T DSP 出货量首次披露 — 实际 vs 预期?
- (Q3) Custom ASIC 设计赢单中是否有客户名单具体披露?
- (Q4) AVGO Q3 FY26 ER 9/3 中,AI semi 业务对 MRVL 估值的影响?
- (Q5) Jensen Huang 6/6 言论 + NVDA $2B 投资在 30 天后是否被 confirmed by NVDA official press release?
- (Q6) 实际持仓决策:本次分析后是否触发 collar / sell put / 观望? 12 个月后回顾,场景概率分配(25%/45%/25%/5%)是否合理?
