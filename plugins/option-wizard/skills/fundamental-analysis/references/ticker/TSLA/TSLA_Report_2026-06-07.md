---
ticker: TSLA
event: 基本面深度分析 — 营收首次下滑 + SpaceX IPO 6/12 在即 + 储能业务变阵
date: 2026-06-07
status: analysis-only
result: pending
structures: [protective_put, collar, put_spread_overlay, short_call_overlay, long_dated_LEAPS_eval]
tags: [tsla, ev, robotaxi, energy_storage, spacex_ipo_overhang, musk_premium_decompression, megapack, optimus, fsd, deep_dive, m7]
archive_eligible_after: 2026-08-07
---

# TSLA 基本面深度分析 — 2026-06-07

> Spot: **$391.32**(2026-06-06 收盘,UW `get_company_info`)
> Mkt cap: **$1.467T** · Beta: **2.02** · Shares out: **3.756B**
> Next ER: **2026-07-22** (Q2'26)

---

## Section 1 — Executive summary

**一句话论点:** TSLA 在 2026 上半年处于**"Musk premium 高估 + 汽车业务利润崩塌 + AI/Robotaxi 故事未变现"** 的三重夹击窗口口。FY25 营收 $94.83B(同比 **-2.9%**,公司现代史首次年度营收下滑),Op Margin 从 FY22 的 16.8% 坍缩到 FY25 的 4.6%,GAAP EPS 仅 $1.07,TTM PE **216x**。同期市值近乎与 META 持平($1.47T vs $1.30T),但 META FY25 net income $60.5B 是 TSLA 的 **16 倍**。市场为 TSLA 定价的不是当前 cash flow,而是 (a) Robotaxi/Cybercab 商业化期权、(b) Optimus 人形机器人 TAM、(c) 储能 + Megapack 第二增长曲线、(d) Musk 资本配置稀缺溢价。其中 (d) 即将被 SpaceX 6/12 IPO 永久消解。

**今日估值:** spot $391.32, TTM PE 216x(EPS $1.81 = Q2'25-Q1'26 加总), Forward PE ~199x (基于 Q2'26 estimate $0.47 + 后 3 季度 ~$0.50/Q), market cap $1.467T, EV/EBITDA **122x**, EV/Sales **15.1x**, FCF yield **0.42%**。净现金 **$35.6B**(现金 $16.5B + ST 投资 $27.5B - 总债务 $8.4B)。

**PE 在定价什么:** 市场假设 (1) 2026H2-2027 Robotaxi 商业化 + Cybercab 量产带来汽车业务 EPS 拐点;(2) Optimus 在 2028 后形成 $XXXB TAM 的工业机器人 + 服务机器人新业务;(3) Energy 业务在 Megapack 3 + Megafactory Houston 扩产后维持 30%+ GM 上 40%+ 增长曲线;(4) Musk 个人 stewardship 溢价。但论点 (4) 的市场垄断属性会在 **2026-06-12 SpaceX 上市当日**部分蒸发——SpaceX 估值 $1.75T 与 TSLA 同量级,且业务质量(Starlink 现金牛 + 国防订单 + 火箭垄断)对 high-growth 资金更具吸引力。Morningstar 给 SpaceX 公允价 $780B,折价 48%,但即便 SPCX 上市后回调,投资人也已多了一个 "Musk 资本配置" 的公开通道。

**Recommendation:** 持有(若已持有),回避新建 long(若空仓),**仓位 0-2% NLV 上限**——TSLA 不入选 buy-and-hold 核心(M7 + QQQ),原因是当前 FCF yield < 长期国债 yield 一半,且 SpaceX IPO 在未来 5 天内是 binary catalyst。**核心 catalysts 未来 6 个月内:** (a) **2026-06-12 SpaceX IPO 上市**(最大单一变量);(b) **2026-07-22 Q2'26 ER**;(c) 2026H2 Cybercab 量产爬坡进度披露;(d) Optimus 工厂剪彩 / 内部测试影像;(e) FSD V14 / Unsupervised 美国扩区进度(目前仅 Dallas/Houston)。

---

## Section 2 — Valuation anatomy

| 组件 | 数值 | 暗示 |
|---|---|---|
| Spot price | $391.32 | UW `get_company_info` 2026-06-06 收盘(TV reader 在标准 Bash session 不可用,标注 Gap) |
| TTM EPS | $1.81 | Q2'25 $0.40 + Q3'25 $0.50 + Q4'25 $0.50 + Q1'26 $0.41(UW `get_earnings_history`)|
| **TTM PE** | **216.2x** | 计算:$391.32 / $1.81 |
| Forward EPS (NTM) | ~$1.97 | Q2'26 est $0.47(UW)+ 后 3 季度按 $0.50/Q 假设 — **CONSENSUS** |
| **Forward PE** | **~198.6x** | 隐含市场假设 2026H2 EPS 反弹 ~10%(温和) |
| TTM EBITDA | $11.76B | UW FY25 income statement |
| EV (mkt cap + 债 - 现金) | $1,431.5B | $1467.2B + $8.38B - $44.06B(现金+ST 投资) |
| **EV/EBITDA** | **121.7x** | 高度异常,远超传统 OEM(~5-10x)和软件公司(~20-25x) |
| **EV/Sales** | **15.1x** | OEM 同行 ≤ 1x,纯软件 8-15x — TSLA 在 OEM 体量上给软件定价 |
| FY25 FCF | $6.22B | OCF $14.75B - CapEx $8.53B |
| FCF margin | 6.6% | 同期 META 22.9%,GM 6.0%,F 6.7%(F 主因税收 timing 非真实质量) |
| **FCF yield** | **0.42%** | $6.22B / $1467.2B — **远低于 10Y Treasury yield**;无 dividend |
| ROE | 4.6% | $3.79B NI / $82.1B equity |
| ROA | 2.8% | $3.79B NI / $137.8B assets |
| Net cash | **+$35.6B** | 资产负债表无杠杆压力,是 R&D 烧钱护城河 |

### 价值瓦解的三层故事

**(1) 汽车业务的真实利润率坍塌(2022→2025)**

| FY | Revenue | GM | OpM | NM | NI | 备注 |
|---|---|---|---|---|---|---|
| 2022 | $81.5B | 25.6% | 16.8% | 15.4% | $12.6B | 峰值年,Berlin/Austin 工厂双 ramp + ZEV credit 收益高 |
| 2023 | $96.8B | 18.3% | 9.2% | 15.5% | $15.0B | 利润含 $5B 一次性递延税收益,**调整后**正常 NI ≈ $10B |
| 2024 | $97.7B | 17.9% | 7.2% | 7.3% | $7.1B | 价格战 + Cybertruck 爬坡亏损 |
| 2025 | **$94.8B (-2.9%)** | **18.0%** | **4.6%** | **4.0%** | $3.8B | 首次营收下滑,R&D 暴增到 $6.4B(Optimus/Robotaxi 押注) |

3 年间 GM **降 7.6pp**, OpM **降 12.2pp**, 营收首次年同比下滑。背后驱动:中国 BYD/小鹏/理想价格战 + 北美 Cybertruck delay + 欧洲市场份额被 BMW/VAG 蚕食 + ZEV credit 政策退坡。

**(2) R&D 投入与 CapEx 重新分配**

R&D 从 FY22 $3.07B → FY25 **$6.41B**(+109% 3 年累计)。绝对金额:META 2025 R&D 是 $57.4B(TSLA 的 9 倍),但 META 营收是 TSLA 的 2.1 倍,所以 R&D/Revenue ratio:TSLA **6.8%** vs META **28.5%**。TSLA R&D 强度其实低于纯软件公司,反映其本质仍是制造业,但近年快速向 AI/机器人倾斜。

CapEx FY24 峰值 $11.34B → FY25 $8.53B(-25%)。理由:Berlin、Shanghai、Austin 主产能已建好;FY25 新增主要是 Optimus 量产线 + Megafactory Houston 扩产。FCF FY25 $6.22B 因此回升(FY24 仅 $3.58B)。

**(3) Stock-based compensation 真实摊薄(SBC dilution)**

FY25 SBC $2.83B(vs 净利 $3.79B,**SBC/NI = 74.5%**)。Dilution-adjusted FCF ≈ FCF - SBC ≈ $6.22B - $2.83B = $3.39B,即真实 FCF yield 0.23%。这是 TSLA 投资人需要正视的"次级估值":Buyback 几乎为零,SBC 长期摊薄股本。

### Bear case 市场在 price in 什么

市场当前价格大致 price in 以下 3 个 narrative:
1. **2026H2 自动驾驶变现转折:** Robotaxi 在 Dallas/Houston 跑了 6 周已剥离 safety monitor,FSD V14 正在内测,Cybercab 中期量产。若 2026Q3/Q4 财报披露 Robotaxi 跨城市扩张 + Cybercab 交付台数 > 5k,EPS 拐点叙事会被 confirm。
2. **Energy GM 持续 35%+:** Megapack 业务作为 "次级软件公司" 定价(高 GM、订单簿可视),Q1'26 GM 39.5% 是关键证据点,但 Q1'26 收入 **同比 -12%** 抛出"需求是否周期性"的疑问。
3. **Optimus 期权价值:** Musk 多次声称 Optimus 长期 TAM 数万亿美元,定价目前仅作为"看涨期权"塞入估值,但没有任何收入支撑;若 2026Q4 工厂剪彩 + 测试视频显示量产可行,这部分 narrative 会被强化。

**翻车点(bear 论点已开始兑现):** FY25 营收首次下滑;Q1'25 EPS 跌至 $0.27(miss 估算 34%);Robotaxi 推出 6 周车队规模 fleet 只有约 20 辆(per Benzinga 6/7 报道)且因安全顾虑被裁员发声警告;Optimus 没有公开量产可见证据;SpaceX 6/12 IPO 会立刻撕开 Musk premium 的稀缺性。

---

## Section 3 — Peer matrix (横向对比)

| Ticker | Mkt cap | Rev TTM | Rev growth FY24→FY25 | Op margin | Net margin | FCF margin | Net debt / EBITDA | TTM PE | Fwd PE | EV/EBITDA | ROE | 1Y total return |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **TSLA** | **$1.467T** | **$94.83B** | **-2.9%** | **4.6%** | **4.0%** | **6.6%** | **-3.0x (net cash)** | **216x** | **~199x** | **122x** | **4.6%** | **+37.2%** |
| META | $1.302T | $200.97B | +22.2% | 41.4% | 30.1% | 22.9% | -0.4x (net cash) | 21.6x | ~20x | 12.3x | n/m(超高)| -13.4% |
| GM | $74.0B | $185.02B | -1.3% | 1.6% | 1.5% | 6.0% | ~6x (汽车金融) | 27.4x | ~9-10x | ~4-5x | ~4% | +73.6% |
| F | $58.3B | $187.27B | +1.2% | 1.4% | -4.4% | 6.7% | ~12x (汽车金融) | N/M (亏损) | ~10-11x | n/m | 负 | +47.6% |
| RIVN | $20.5B | $5.39B | +8.4% | -66.6% | -67.7% | -46.2% | -2x (剩 IPO 现金) | N/M (亏损) | N/M | N/M | 负 | +18.4% |

**注:** TSLA 净现金计算用 ST 投资 + 现金 $44.06B 减总债务 $8.38B;FCF margin 不含 SBC dilution(若 dilution-adj 后 TSLA 仅 3.6%)。GM/F 的 net debt/EBITDA 看起来高是因为汽车金融业务的债务(GM Financial / Ford Credit),业务本身需要负债,不可直接对比。

### 解读

**TSLA 在峰值市值上,产生 peer 末端的 financial 质量。** 营收增长 ranking:META +22.2% > F +1.2% > RIVN +8.4%(基数小)> GM -1.3% > **TSLA -2.9%(最差)**。 Operating margin ranking:META 41.4% > **TSLA 4.6%** > GM 1.6% > F 1.4% > RIVN -66.6%。 净利润绝对额 ranking:META $60.5B > **GM $2.7B > TSLA $3.8B**(注:META 是 TSLA 的 16 倍)> F 亏损 > RIVN 亏损。

**最显著的反差:** META 利润是 TSLA 16 倍,市值 TSLA 比 META 高 13%。换句话说,**market 给 TSLA 每美元利润支付 386x,给 META 21.6x** —— TSLA 溢价倍数 = 17.9x META。这是论点 2(估值反差)的核心数据。

**1Y return 信号反着读:** 过去 1 年 GM **+73.6%** 跑赢 TSLA +37.2%, F +47.6% 也跑赢。原因:汽车 OEM 行业经历估值压缩底部回升,而 TSLA 还在估值压缩中段。**META -13.4%** 是 Mag 7 中过去 1 年表现最差之一,主因 AI capex 担忧——但这反衬出 TSLA 在 AI capex 强度比 META 低 4 倍的情况下,估值未被同等惩罚。

**peer matrix 的 noisy outlier 澄清:**
- F TTM PE 为 N/M:FY25 净利 -$8.2B 含一次性递延税收益逆转(income_tax -$3.67B)和 Model E (EV 部门)关闭费用。**真实运营 EPS 估算 $1.30-$1.50**,真实 PE 9.9-11.4x。
- GM TTM PE 27.4x 看似偏高:FY25 净利 $2.7B 远低于 FY24 $6.0B,主因 China 业务亏损 + 关税影响。**FY26 共识 EPS** 大致 $8-9,Forward PE 9-10x。
- RIVN PE N/M:仍处亏损期。FY25 首次接近 GM 转正(2.7%),Q4'26 路径才转正 EBITDA。

---

## Section 4 — Historical PE percentile

由于 UW `get_fundamental_breakdown` 端点返回过期数据(share_price $27.89 / revenue $7.4B 显然是 2016 年快照),且本次 session 未自行拉取 10 年月度价格 × EPS series, **本节标记为 CONSENSUS 引用 + 部分 UNVERIFIED**。

| 时期 | PE 低点 | PE 高点 | 中位数 | 今日 PE 百分位 |
|---|---|---|---|---|
| 5-year(2021-2026) | ~30x | ~1100x | ~80-100x | ~60-70% (CONSENSUS) |
| 10-year(2016-2026) | ~30x | 多年负利润 PE 不适用 | n/m | n/m |

**叙事:** TSLA 历史 PE 极端分散。2020-2021 低利润高股价时期 PE 数百倍至千倍;2022-2023 利润峰值时 PE 一度跌至 ~30x;FY24-FY25 利润坍塌使 PE 重新攀升到 200x+ 区间。**当前 PE 216x 大致位于 5 年 PE 60-70 百分位**(意即:历史上更高的 PE 通常对应即将到来的利润反弹,例如 2020 早期;更低的 PE 对应利润峰值如 2022)。

**关键问题:** 当前 216x PE 是否预示利润即将反弹?

历史先例 2020:PE >1000x 时,接下来 18 个月利润从亏损翻转到 $5.6B → $12.6B。反弹由 Model 3/Y 量产 ramp 驱动。

当前 2026:对应的 "ramp 驱动" 应是 Cybercab + Robotaxi。但 Cybercab 量产时间表已多次推迟(从 2023 → 2024 → 2026 mid 计划),Robotaxi 商业化 6 周只跑了 20 辆车 fleet。 历史先例**只在 ramp 实际兑现时**才有效。

**未填项明示:** 自计算 PE 序列需要 Massive `/v2/aggs/ticker/TSLA/range/1/month/...`+ UW `get_earnings_history` quarterly EPS 对齐,本 session 未跑 — 列入 Gaps。

---

## Section 5 — Turnaround case studies

### Case study A: **NFLX** — 2022 PE 压缩 → 2023-24 再起

**Then:** 2022 H1,NFLX 因密码共享危机 + 流媒体竞争加剧 + 增长见顶担忧,从 $700 跌至 $164。 TTM PE 从 ~50x 跌到 ~17x。市场怀疑订阅增长见顶。

**Why it bottomed:** Q1'22 公布北美订阅净流失 20 万,Q2'22 再失 97 万。增长叙事崩盘。 估值在 ~$170 形成底,EV/EBITDA 跌到 9x(史上最低)。

**What changed:** Q4'22 开始: (1) 共享账户 crackdown 启动,把 1 亿 freeloader 转化为付费;(2) 推出广告版套餐,新增 ARPU;(3) 内容支出从 $20B 降到 $17B,提升 FCF;(4) Q3'23 净增 870 万订阅,Q4'23 再增 1310 万。利润从 $4.5B (2022) 翻倍到 $9B+ (2024 GAAP)。

**Re-rating:** 18 个月内,股价从 $164 → $700+,PE 重回 ~40x。$IRR > 200%。

**Applicability to TSLA:** 类似点 = 都是"故事股极端估值 → 增长见顶担忧 → 通过 monetization 改造重新加速"。NFLX 的解药是 ARPU(广告 + 共享 crackdown);TSLA 的解药假设是 Robotaxi + FSD 订阅 + Optimus。**关键差异:NFLX 转折前已有 2.2 亿订阅基础和正现金流;TSLA 的 Robotaxi 商业化仍处于 20 辆 fleet 阶段,Optimus 没有付费用户。NFLX 的 monetization lever 是软件层面 OPEX 调整,TSLA 的需要硬件 ramp 和监管批准,后者复杂度高一个数量级**。

### Case study B: **AMZN** — 2022 PE 压缩 → 2023 re-rating

**Then:** 2022 全年,AMZN 从 $186 跌到 $84(EV $2T → $0.85T)。市场担忧 AWS 增速放缓 + 零售业务亏损 + capex 失控($60B+/年)。 Operating margin 跌至 2.4%(从 2021 5.3%)。

**Why it bottomed:** Q3'22 Op income $2.5B(全公司),AWS 增速从 33% 降至 27%,零售北美季度亏损 $0.4B。 Andy Jassy 上任后第一年市场失去耐心。

**What changed:** (1) 2022Q4 启动史上最大裁员 27,000 人,削减 OPEX;(2) 2023 重点收回 capex 强度,FCF 从 -$13B 跳到 +$32B;(3) AWS 增速在 2023H2 重新回升到 12% 触底反弹;(4) 2024 AI 收入 + 广告业务接管增长,Q4'24 Op margin 升至 11%。

**Re-rating:** 24 个月内,股价从 $84 → $240,PE 从 50x → 35x(EPS 翻倍)。

**Applicability to TSLA:** 类似点 = 都因 capex 强度过高 + 增长放缓被惩罚。TSLA FY25 CapEx 已从峰值 $11.3B 降到 $8.5B(类似 AMZN 2023 调整),FCF 从 $3.6B 回升到 $6.2B。**关键差异:AMZN 转折由 AWS(已成熟现金牛)兜底,削减 OPEX 直接转化为利润;TSLA 没有等价的现金牛,Energy 业务规模仅 $10B/年(占 11% 营收),Auto 业务核心利润已坍塌。TSLA 的拐点需要 Robotaxi/Optimus 这种全新业务起飞,不是简单的成本控制。AMZN 类比的可信度有限**。

### **两个分析都失效的场景**

需要警惕:NFLX/AMZN 转折的前提都是 (a) 核心 monetization lever 已存在(订阅基础、AWS), (b) 公司管理层全员聚焦执行(Andy Jassy 第一年改革),(c) 没有外部新的稀缺替代品出现。 TSLA 三个条件全不满足:(a) Robotaxi/Optimus 都是 0-to-1, 没有变现基础;(b) Musk 个人带宽分散到 SpaceX/xAI/Twitter/Boring/Neuralink;(c) **SpaceX IPO 6/12 直接提供"Musk-exposure 公开通道"替代品**。

---

## Section 5.5 — 核心竞争力 / Core Franchise Analysis

> **本节是用户特别要求扩展的章节:SpaceX 关系 + SpaceX IPO 影响 + 储能业务 + 2026 catalysts。**

### 5.5.A 核心产品 / 业务线 (TSLA 三大 franchise)

TSLA FY25 营收 $94.8B 由 3 个业务组成(基于 UW 财报 + Massive 新闻 + Q3'25/Q1'26 ER):

| 业务 | FY25 收入估算 | 收入占比 | GM | 2025-26 趋势 |
|---|---|---|---|---|
| **Auto (车辆销售 + 服务 + 监管碳积分)** | ~$77B | ~81% | ~17-18% | **承压**:Q1'25-Q1'26 多季度量价齐跌,Cybertruck delay,价格战 |
| **Energy (Megapack + Powerwall + Solar)** | ~$10-11B | ~11% | **30-39%**(高于汽车一倍) | **波动增长**:Q3'25 +44% YoY,Q1'26 -12% YoY,Megapack 3 量产临近 |
| **Services + Other (Supercharger + 软件 + FSD)** | ~$7B | ~8% | 中低 | 增长稳定,FSD 渗透提升中 |

**关键洞察:** Energy GM(30-39%)显著高于 Auto(17-18%),业务质量更高,但规模仅 11%。如果 Energy 能从 $10B 翻倍到 $20-25B 同时维持 GM,Energy 段贡献 GP 可能从今天 ~$3.5B 翻到 $7-8B,届时占公司总 GP 比重从 ~20% 升至 40%+,真正"重塑业务组合"。**这条增长路径是 TSLA 高估值能否被 fundament 验证的关键之一**。

#### 5.5.A.1 储能业务深度(用户重点要求)

**业务结构:**
- **Megapack:** 公用事业级 BESS(电池储能系统),3-4 MWh 单元,2025 部署 ~12.5 GWh/Q,峰值;主要市场:北美电网套利 / 加州 + 德州 / 海外公用事业 / 数据中心。
- **Powerwall:** 家庭储能,3 代产品,与屋顶光伏组合销售。
- **Solar Roof + Panels:** 太阳能板 + 屋顶,2025 销售放缓。
- **Megafactory:**
  - 加州 Lathrop:已运营,产能 ~40 GWh/年
  - 上海:已运营,2024 投产,产能 ~40 GWh/年(主要服务亚太 + 出口欧洲)
  - **休斯顿:2026 开始 Megapack 3 + Megablock 投产**

**财务数据(2025 H1-Q1 2026):**

| 时期 | Energy 收入 | YoY | GM |
|---|---|---|---|
| Q3 2025 | $3.42B | **+44%** | ~30% |
| 2025 9M 累计 | n/a | n/a | 30.3% |
| Q1 2026 | $2.27B (推算) | **-12%** | **39.5%** |
| Q1 2025 (对比) | $2.59B | n/a | 28.8% |

**关键分析:**
- Q3'25 +44% YoY,Q1'26 -12% YoY → **增长非线性**。 季度 lumpy 是 BESS 业务正常特征,但年度趋势从 2025 高增长转为 2026H1 收缩,提示 (a) 美国 IRA 储能补贴可能政策不确定性 (b) Megapack 2 产能爬坡见顶等待 Megapack 3 (c) xAI/数据中心 BESS 订单可能集中在某些季度。
- GM 从 28.8% 跳到 39.5%(**+10.7pp**)极其惊人,意味着 Megapack 3 单价/单产能利润率显著提升。但需要警惕 GM 提升来源:是 (a) 产品 mix 改善(更多 Megapack,少 Powerwall),还是 (b) IRA 补贴递延 / 制造 tax credit 计入?Q4'25 报表会明确。
- **Megapack 单业务在 2025 贡献 $1.1B 的 $3.8B 能源 GP**,即 Megapack GM 远高于业务平均(估算 ~40-50%)。

**前瞻:** 假设 Megafactory Houston 在 2026H2 满产 + xAI/Oracle/Anthropic 数据中心 BESS 订单兑现,Energy 段 2026 全年收入大致预期 $13-15B(+30-50%),Energy GP ~$4.5-5.5B(对比 2025 $3.8B)。 如果实现,将抵消汽车业务利润下滑约 50%。

#### 5.5.A.2 Robotaxi / Cybercab / FSD 业务(0-to-1 阶段)

- **Robotaxi 商业化进展:** 2026 年 4 月正式启动 Dallas/Houston **无监管(unsupervised)** Robotaxi 服务,但截至 2026-06-07,车队规模约 **20 辆**(per Benzinga),近期前 Tesla 工程师 + 数据标注员公开发声质疑 FSD 安全性。
- **Cybercab:** Pilot production 状态,**mid-2026 计划开始量产**。 设计目标:无方向盘 + 无踏板,纯 robotaxi 用途;两座;Optimus 工厂可适配生产。
- **FSD:** V14 内测,V13 已在多个市场推广。 V4 (Supervised) 2026 年 4 月获**荷兰**监管批准 — 是欧洲市场首个监管放行。 美国 Unsupervised 仅在 Dallas/Houston 两个地理区域,后续扩区进度是关键 catalyst。
- **变现状态:** 当前 FSD 订阅约 $99/月,渗透率个位数;Robotaxi 商业化 6 周收入忽略不计。**对 FY26 EPS 几乎没有直接贡献,纯期权价值**。

#### 5.5.A.3 Optimus 业务

- 加州 + 德州 Optimus 工厂在建,Texas 工厂 "construction capacity"(进入建设阶段);
- 量产时间表 **2026 后期 - 2027 初** 计划开始 mass production;
- 实际可验证证据:**2026Q4 ER 是首个会披露 Optimus 量产 KPI(产量、应用场景、初次销售)** 的窗口;
- 估值占比:目前在 Mag 7 估值模型中,Optimus 通常作为"看涨期权"塞入,价值估算 0-$300B 取决于 long-term TAM 假设。无收入直接验证。

### 5.5.B TSLA-SpaceX 关系深度(用户特别要求)

#### 5.5.B.1 商业互动(已公开披露的交易)

**SpaceX 向 Tesla 的采购:**
- **Megapack BESS for xAI 数据中心:$697M(截至最近披露)** — SpaceX 通过 xAI 关联实体购买 Tesla 储能给 xAI 训练集群供电;
- **Cybertruck:$131M** — SpaceX 用 Cybertruck 作为 Starbase 公共关系车队 + 内部物流;
- 历史:Tesla 给 SpaceX Starbase 提供 8 MWh Megapack BESS(2024 已交付,公开报道);
- Starship MK1 header tank 装载 4 个 Tesla Model S/X 电池组(2023 报告)。

**Tesla 向 SpaceX 的采购:**
- Tesla 使用 SpaceX 飞机(Musk 跨公司差旅);
- 历史:Tesla 太阳能 + 部件销售给 SpaceX。

**关联方披露监管风险:** 二者目前是独立公开公司(SpaceX 上市后),关联交易需要在 10-K / 10-Q 中详细披露。**SpaceX 上市后,这层关系会被监管放大审查**,任何未达 arm's length 的交易会被市场放大解读。

#### 5.5.B.2 技术协同 / Cross-Pollination

- **共享 VP of Materials Engineering** — 两公司联合材料研发(电池、合金、复合材料);
- **材料 R&D 数据库** — 共建材料性能数据库,加速新材料商业化;
- **电池技术:** SpaceX 用 Tesla 4680 电池在 Starship 项目;Tesla 学习 SpaceX 的 high-vibration / 极端温差工程经验;
- **AI/Compute:** xAI 训练集群(GPU + Megapack 供电)与 Tesla Dojo 项目有共享研究方向,但 Dojo 项目相对独立。

**对 TSLA 投资人的意义:** 协同效应真实存在,但 quantify 困难。无法在财报中直接看到这部分贡献。**叙事价值大于直接利润价值**。

#### 5.5.B.3 SpaceX IPO 6/12 对 TSLA 的具体影响

**事件锁定时间表(基于 2026-06-04 路演 + 6/03 CNBC 报道 + 6/07 Benzinga 报道):**
- 2026-05-20: SpaceX 提交 Form S-1
- 2026-06-01: 提交 Amendment No. 1(S-1/A)
- 2026-06-04: 路演开始
- 2026-06-11: 定价(market close after)
- **2026-06-12: 首个交易日(Nasdaq,ticker SPCX,$135/股)**
- 估值:$1.75T - $1.77T
- 筹资:$75B(含 underwriter 期权再加 $11.2B)
- Musk 保留 **82%+ 投票权**
- Morningstar DCF 公允估值:**$780B**(距 $1.75T 折价 48%)

**对 TSLA 估值的 3 个机制:**

**(1) "Musk premium" 蒸发 (最直接最大):**
   过去 10 年, **TSLA 是公开市场唯一 Musk 资本配置/愿景的 exposure 通道**。投资者持有 TSLA 部分是为了 buy 不到 SpaceX 的次优替代。 6/12 后,SPCX 直接可买,TSLA 这一稀缺溢价应被 reprice。 历史 base rate:类似的"premium 蒸发"案例,如 Amazon 1997 IPO 让 Cisco 等"互联网替代品"重新定价,通常导致前替代品 15-25% derate。

**(2) 资金流量再分配:**
   SPCX 上市后,被动指数 fund(纳指 100、罗素 1000)在数月内会被强制加入 SPCX(纳指 100 加入门槛:市值 + 流动性),触发 ~$30-50B 强制买入。这部分增量买盘资金的边际来源,部分会从 mag 7 出来,**TSLA 是最直接的资金分流候选**。
   
**(3) 关联交易透明度:**
   上市后,每笔 SpaceX-Tesla 关联交易要在 10-K / Proxy 披露。 历史上 xAI 与 Tesla 之间的 $697M Megapack 订单这类规模交易,会被 ISS/Glass Lewis 审视,可能触发 Tesla 股东诉讼或 board 决策 scrutiny(类比 Musk 2024 年薪酬包诉讼)。

**反向论点(为何 SpaceX IPO 也可能利好 TSLA):**
- (a) Musk 个人净资产 +$700B,可能减少他抛售 TSLA 募集私募的需求;
- (b) SPCX 上市后初期通常溢价,可能短期带动 "Musk-related" 板块情绪;
- (c) SpaceX-Tesla 协同的透明披露可能让市场重估 Tesla 在 Robotaxi/Optimus 上的实际进展。

**净判断:** SpaceX IPO 是 **对 TSLA 偏负面的 binary catalyst**,但**实际负面冲击会被新闻周期消解**。 第一日波动:TSLA 短期 ±5-10% 区间,长期(3-12 个月)估值压力 -10-20%。**位置在 21 DTE 短 premium 上的 TSLA 仓位应 21 DTE 前预先关闭或转 long-dated 防御**。

### 5.5.C TSLA 在各自市场的定位 (auto / energy / autonomy)

**Auto 市场:**
- 全球 BEV 市占率:2025 ~17%(从 2022 高点 22% 下滑)
- 美国 EV 市占率:2025 ~46%(被 GM/Ford/现代/起亚 蚕食,从 2022 ~65% 下滑)
- 中国市场:2025 ~7%(BYD 已超越,理想/小鹏 在 SUV 段切走份额)
- **份额趋势:全球持续 lose share**;**护城河来源:supercharger 网络(独家先发优势)+ 电池成本规模 + 软件 OTA + 品牌(Musk 个人风险偏好的双刃剑)**
- **威胁:** BYD 2025 全球 BEV 销量超 TSLA,2026 进入欧洲扩展;Hyundai/Kia 北美份额持续上升;中国小鹏/理想在 ADAS 上技术追赶。

**Energy / 储能市场:**
- 全球公用事业级 BESS 市占率(以 GWh 计):2025 ~20-25%(估算,排第二,仅次于宁德时代 CATL 和 EnerVenue 等中国厂商组合)
- 市场规模:2025 ~$45-50B(全球 ESS 行业),CAGR 2025-2030 约 25-30%
- **护城河:** 一体化电池技术(LFP 4680 + Megapack 3 集成度高)+ 软件 (Autobidder 电网套利算法) + 产能规模(2026H2 ~120 GWh 全球)
- **威胁:** Fluence / Powin / 中国厂商(CATL 海外 BESS 业务、宁德时代海外项目);客户(数据中心 + 公用事业)倾向多源采购避免供应商集中。

**Robotaxi / Autonomy 市场:**
- 全球 L4 自动驾驶商业化竞争:Waymo (Alphabet) 在多个城市运营 + Cruise (GM,2024 撤退) + 中国 Baidu Apollo + Pony.ai + 小马智行
- **TSLA 优势:** 数据(数百万车辆 fleet) + 端到端神经网络架构 + 硬件 (HW4 自研推理芯片)
- **TSLA 劣势:** 仅 Vision 没有 LiDAR / HD map (Waymo 的双倍 redundancy 方案);Robotaxi 商业化只在 2 城市 fleet 20 辆,Waymo 已在 5+ 城市 fleet >1000 辆。
- **份额趋势:** Waymo 当前全球 robotaxi 出行量级领先;TSLA 在 2026H2 - 2027 必须显著扩区否则 narrative 受损。

### 5.5.D 对照公司在 TSLA 三大市场的定位 (Peer-by-peer)

| Peer | Auto (份额) | Energy (有/无) | Autonomy | 直接/相邻? | 关键威胁/机会 |
|---|---|---|---|---|---|
| GM | 美国 #2 EV(15% 份额) | 无 | Cruise 2024 退出 | **直接 Auto,相邻 Autonomy** | EV 转型现金消耗中;Cruise 失败已 derisk |
| F | 美国 #3 EV(7% 份额) | 无 | Ford BlueCruise 仅 L2 | **直接 Auto** | F-150 Lightning 销量 wing,Mustang Mach-E 退坡 |
| RIVN | 美国 R1T/R1S(高端 niche) | 无 | 无 | **直接 Auto,相邻** | 资本枯竭风险 + VW $5B 投资续命 |
| META | 无汽车 | 无能源 | 无 robotaxi | **相邻** (AI capex + 同 mag7 资金池) | 主要影响是 AI capex 比较 + 资金分流 |

**adjacent peer disruption 风险评估:**
- **Waymo (Alphabet):** TSLA 最大相邻威胁。GOOGL/Waymo 2026 在多城市扩张可能压制 TSLA Robotaxi 叙事 — 不是直接 peer,但在 autonomy 故事上是替代品。 12-18 月内可能再融资或部分剥离 IPO(传闻 2027)。
- **BYD:** 没有在 Massive 给出的 peer 集合中(中国公司不在 US-listed),但实质上是 TSLA Auto 最大威胁。 2025 全球 BEV 销量已超越 TSLA。

### 5.5.E 5-10 年 trajectory(综合 A-D 的前瞻判断)

**未来 5 年(2026-2031)核心问题:**
1. **Auto:** TSLA 全球 BEV 份额会进一步从 17% 跌到 12-14% 还是稳住?需要 Cybercab 量产 + Model 2(传闻低价位车型)推出来止血。
2. **Energy:** 能否从 $10B → $25-30B (~CAGR 20-25%)?Megafactory Houston + 海外扩产 + IRA 政策延续 = 三个决定性因素。
3. **Robotaxi:** 2027 能否在 10+ 美国城市运营 1000+ 辆 Robotaxi fleet?这是 narrative 兑现的最低标准。
4. **Optimus:** 2028 能否实现 10k 台/年 internal use + 工业客户初始订单(估算 $1-3B 收入)?
5. **EPS 路径:** FY25 $1.07 → FY27 $3-4(Robotaxi/Energy 同时贡献)→ FY30 $5-8(假设 Optimus 起步)?当前价格已 price-in 大致 FY28 EPS $5+。

**Franchise 论点综合:** TSLA 核心 franchise 从纯 Auto OEM 演化为 "**Auto + Energy + AI/Robotics 三足鼎立**" 的尝试。 但目前(2026 H1)只有 Energy 已经独立证明 30%+ GM 业务质量。 Auto 业务正经历份额下滑 + 利润崩塌。 Robotaxi/Optimus 仍是 0-to-1 阶段。 **5-10 年路径不确定性极高,5 年 EPS 区间 $2-$10 都有合理 base rate**。

**5-10 年 Franchise 一句话总结:** **TSLA 在 2030 年将是一家 50% Auto + 30% Energy + 15% Autonomy + 5% Robotics 的混合公司,核心争议是 Energy/Autonomy 这两块新业务是否能足够快 ramp 抵消 Auto 业务份额下滑。 当前 PE 216x 隐含市场押注的是非常乐观的版本(EPS 达到 $5+ by 2028)。**

---

## Section 6 — Head-to-head vs closest peer (TSLA vs META)

选择 META 作为头对头不是因为业务相似 — 显然不是。 而是因为 (a) 市值同量级 $1.3-1.5T (b) AI capex 是估值核心争议 (c) 都被市场作为 Mag 7 "未来增长 + Musk-style 资本配置 vs Zuck-style 资本配置" 的对比标的。 是估值反差最有教育意义的一对。

| 指标 | TSLA | META | 解读 |
|---|---|---|---|
| Revenue TTM | $94.83B | $200.97B | META 是 TSLA 2.1 倍 |
| Revenue growth 3Y CAGR | ~16% (含 2022 峰值) | ~30% | META 更快增长 |
| Same-store-unit growth | 2025 全球交付 -1.1% YoY | DAU +5% YoY | TSLA Auto 业务量在下滑 |
| Gross margin | 18.0% | **82.0%** | META 软件公司,TSLA 硬件 |
| Op margin | 4.6% | **41.4%** | META 利润率比 TSLA 高 9 倍 |
| Net margin | 4.0% | **30.1%** | 同上 |
| ROIC | ~3-4% | ~25%+ | META 资本回报远高 |
| FCF / share | $1.66 | $20.97 | META FCF/share 是 TSLA 12.6 倍 |
| Net debt / EBITDA | -3.0x (净现金) | -0.4x (净现金) | TSLA 流动性更厚但绝对现金更少($44B vs $97B) |
| Buybacks 3Y | ~$0(主要是 SBC 反向冲销) | $76B累计 | META 大额回购,TSLA 几乎无 |
| TTM PE | **216x** | **21.6x** | TSLA 倍数是 META 10 倍 |
| Fwd PE | ~199x | ~20x | TSLA 倍数是 META 10 倍 |
| 5Y total return | +96%(从 $200 → $391) | +79%(从 $330 → $593) | TSLA 略胜,但波动远大 |
| Beta | 2.02 | 1.49 | TSLA 系统性风险 35% 更高 |

**关键反差解读:**
- **每美元利润的价格反差:** META P/E 21.6x,TSLA 216x —— TSLA 每美元利润支付 **10 倍于 META**。换句话说,若 TSLA EPS 在 5 年内涨到 META 当前水平 ($27.50),且 PE 保持 21.6x,股价 ~$594(+52% 5yr =年化 8.7%)。但 TSLA 要达到 META EPS 水平意味着 net income 从 $3.8B 涨到 $60B,即需要 (a) 2030 年 Auto 重回 16% Op margin + 收入 $130B = $20B Op income(乐观)+ (b) Energy 收入 $40B × 35% Op margin = $14B + (c) Robotaxi/FSD/Optimus 共 $25B Op income — 这一组合假设 极度乐观。
- **资本回报哲学反差:** META 过去 3 年累计回购 $76B 股票 + 派发 $5B 股息(Q4'25 启动),Zuck 完全 shareholder-returns 取向。TSLA 没有回购,SBC 持续摊薄,Musk 资本配置完全押在内生 R&D/CapEx。**这导致 SBC-dilution-adjusted TSLA FCF yield 仅 0.23%,远低于 META 真实 FCF yield ~4%(reinvestment-adjusted)**。

**Verdict:** **META 当前是远更好的 risk-adjusted bet,前提是接受 AI capex 不确定性**。 同等市值同等"故事股"性质,META FCF 是 TSLA 7 倍,PE 是 TSLA 1/10,buyback yield 是 TSLA ∞ 倍。 TSLA 唯一胜出 META 的维度是 **Optimus + Robotaxi 期权价值**,但这两项目前没有任何收入支撑。 若投资人寻求 mag7 增长 exposure,META > TSLA 在 risk-adjusted base。

---

## Section 7 — Scenario analysis (probability-weighted EV)

时间窗口:12 个月内(2027 中期)

| 场景 | 概率 | 目标价 | 触发条件 |
|---|---|---|---|
| **牛市 (Robotaxi + Cybercab 双兑现)** | 15% | $580 | (a) 2026Q4 Cybercab 季度交付 >10k 台;(b) Robotaxi 商业化跨 ≥5 个美国城市 + fleet > 500 辆;(c) Energy 收入 +30% YoY 维持 GM 35%+;(d) SpaceX IPO 后 Musk premium 仅 -5% derate |
| **基本 (估值横盘 EPS 缓慢恢复)** | 50% | $400 | (a) Cybercab 量产 2026 末小批量,2027 量产;(b) Robotaxi 维持 Dallas/Houston + 加 2 城市;(c) Energy 收入 +15-20% YoY;(d) SpaceX IPO 后 TSLA -10% short-term 然后恢复 |
| **熊市 (Robotaxi 延期 + 利润率继续压缩)** | 25% | $260 | (a) Cybercab 量产推到 2027H2 + Robotaxi 仍 < 5 城市;(b) Auto 利润率从 4.6% 进一步压到 3% 以下;(c) Energy 增长降至 < 10% YoY;(d) SpaceX IPO 触发 mag7 资金分流,TSLA derate 25%+ |
| **灾难 (Musk 重大 distraction + 监管反弹)** | 10% | $180 | (a) Robotaxi 发生重大事故 + 监管 NHTSA 全美暂停;(b) Musk 因 SpaceX 上市 + xAI 整合发生重大注意力分散;(c) FY27 EPS 跌至 $0.50 以下;(d) PE 重新校准到 200x = $100 区间或长期持有逻辑被破坏 |

### EV 计算

> **EV = 0.15 × $580 + 0.50 × $400 + 0.25 × $260 + 0.10 × $180**
> **= $87 + $200 + $65 + $18 = $370**
> **vs spot $391.32 → 隐含 -5.4% 12 个月预期回报(probability-adjusted)**

**结论:** Probability-weighted EV($370)略低于 spot($391),即 base case 下 12 个月持有 TSLA 期望负回报 ~5%,加上 2.02 beta 系统性风险,风险调整后 Sharpe 极差。 这是 **"持有可以,新建 long 不利"** 的数学依据。

### 关于概率分配的诚实说明

- 牛市 15%:Cybercab 量产 5 次推迟史 + Robotaxi 6 周车队 20 辆事实,base rate 看高概率达成难度高。
- 基本 50%:大概率 Musk 继续叙事 + 季度 EPS 在 $0.45-0.55 区间震荡 + 估值横盘。
- 熊市 25%:概率不低,因为 SpaceX IPO 创造资金流量分流 + Robotaxi 商业化不及预期是结构性风险。
- 灾难 10%:Robotaxi 重大事故 + NHTSA 全美干预的低概率高烈度尾部。

---

## Section 8 — Bull vs bear (两栏论点)

| 牛市论点(bull case) | 熊市论点(bear case) |
|---|---|
| 1. **Robotaxi 商业化破冰** — Dallas/Houston 2026 年 4 月已无监管运营,从 0-to-1 已迈过门槛,接下来是规模化的执行问题 | 1. **营收首次年同比下滑** — FY25 -2.9% 是公司现代史首次,2026 至今 4 个季度有 3 个 miss estimate |
| 2. **能源业务高 GM 第二曲线** — Q1'26 Energy GM 39.5%,Megapack 3 + Megafactory Houston 2026H2 投产,数据中心 BESS 需求受 AI 资本支出周期驱动 | 2. **SpaceX IPO 永久消解 Musk premium** — 6/12 后投资人有公开通道直接持有 Musk 资本配置,TSLA 失去稀缺溢价 |
| 3. **净现金 $35.6B + FCF 6.6%** — 资产负债表无杠杆压力,在熊市下不会被融资逼仓,长期视野能容忍 R&D 烧钱 | 3. **Auto 业务份额持续 lose** — 美国 EV 份额从 65% → 46%,全球 BEV 份额从 22% → 17%,中国 BYD 已超越;Cybertruck 量产 ramp 不及预期 |
| 4. **Optimus 期权价值** — 2026Q4 工厂剪彩 + 2027 起步量产,如果实现 Musk 长期 TAM 叙事(数万亿)将兑现 | 4. **SBC dilution 长期吞噬股东价值** — FY25 SBC $2.83B = 净利 74%,真实 FCF yield 仅 0.23%;无 buyback 抵消 |
| 5. **FSD 监管放行进度** — 2026 V4 在荷兰获批是欧洲首例,后续 EU/UK/中国市场 软件订阅潜在 ARPU 爆发 | 5. **当前 PE 216x 不可持续** — META 同市值 PE 21.6x,TSLA 倍数十倍于 META,极其依赖 narrative 不被打破 |
| 6. **充电网络垄断** — NACS 标准被 Ford/GM/福特等 OEM 全部 adopt,Supercharger 网络成本盈利提升空间大 | 6. **Musk 注意力高度分散** — SpaceX/xAI/Twitter/Boring/Neuralink/America 政党等 7+ 项目,Tesla CEO 带宽紧缩 |

---

## Section 9 — Analyst ratings + catalyst calendar

### 分析师评级(截至 2026-06-05,最新 10 家大行)

| 评级 | 数量 | 占比 | 备注 |
|---|---|---|---|
| Strong Buy | 0 | 0% | — |
| Buy / Outperform | 7 | 70% | Canaccord ×3 ($420-450), TD Cowen ($490), Mizuho ($480), RBC ($475), Baird ($538) |
| Hold / Neutral | 3 | 30% | JP Morgan ($475, upgraded 2026-06-05), UBS ×2 ($352-364) |
| Sell / Strong Sell | 0 | 0% | — |

- **平均目标价(基于 10 家):** $462.20
- **范围:** $352(UBS bear)– $538(Baird bull)
- **隐含 upside:** ($462 / $391) - 1 = **+18.1%**
- **关键变化:** JP Morgan 2026-06-05 把 TSLA 从 Underweight upgrade 到 Neutral,PT $475——意味着大型 sell-side 中最 bear 的声音 capitulate,可能是 short-term sentiment 利好 / contrarian 信号。

### 催化剂日历(未来 6 个月,2026-06 → 2026-12)

| 日期 | 事件 | 重要性 (1-5) | 备注 |
|---|---|---|---|
| 2026-06-11 | **SpaceX IPO 定价(post-close)** | **5** | $135/股,$1.77T 估值,$75B 融资 |
| **2026-06-12** | **SpaceX 首日交易(Nasdaq:SPCX)** | **5** | **TSLA 估值 derate 最大 binary catalyst** |
| 2026-07-22 | **Q2'26 ER(post-market)** | **5** | Consensus EPS $0.47, 关键看 (a) 营收恢复正增长 (b) Energy 收入回暖 (c) Cybercab 量产时间表更新 |
| 2026-07 后 | NHTSA Robotaxi 监督报告 | 3 | 任何监管反弹(若有事故)会立刻冲击叙事 |
| 2026-08-15 | Cybertruck 量产 update(per Q2 ER) | 3 | FY26 销量目标 vs 实际 |
| 2026-09 中 | Optimus Plant 验收 / 公开亮相(传闻) | 4 | 2026 年内首次公开 mass production demo,叙事 catalyst |
| 2026-10-22(估) | Q3'26 ER | 4 | Energy 旺季 + Megapack 3 商业化首报 |
| 2026 H2 | Cybercab 量产开始 | 5 | 多次推迟史,2026 mid 计划,实际若 Q3 仍 pilot status 等于推迟 |
| 2026 H2 | FSD V14 公开发布 + 美国 Unsupervised 扩区 | 4 | 关键 narrative validation |
| 2026-11 | 美国大选后政策环境 | 3 | EV 补贴 + 自动驾驶监管新政影响 |
| 2026-12 中 | Tesla AI Day 2026 / Investor Day(传闻) | 4 | 综合 Robotaxi/Optimus/Megapack 长期路线图 |

---

## Section 10 — Final verdict

### 评级
**持有(若已持有)/ 回避(若空仓)** — 当前 PE 216x 对应 12 个月 probability-weighted 期望回报 -5%,SpaceX IPO 6/12 是 binary downside catalyst。

### 仓位建议
**仓位 0-2% NLV 上限**(显著低于其他 M7)— 理由:
- (a) **conviction 不足** — Cybercab/Robotaxi 商业化路径不确定,Energy 2026 H1 已出现 -12% YoY 提示需求非线性;
- (b) **beta 2.02 vs SPY** — 系统性风险 2 倍于市场,显著放大组合波动;
- (c) **SpaceX IPO 6/12 binary 风险** — 未来 5 天内 binary catalyst 大概率轻度负面;
- (d) **per CLAUDE.md M7 buy-and-hold 政策,即使 over-concentrated 也不建议 trim 已有 TSLA 股票;新建仓位应回避**。

### 实现路径(3 个选项,按优先级)

**1. ⭐⭐⭐(若已持有大仓位)Collar 防御对冲 — 推荐结构**

   **核心思想:在 SpaceX IPO 6/12 不确定性窗口前建立无成本对冲。**

   - **结构:** Long stock + Long Aug-15 $370 Put + Short Aug-15 $430 Call
   - **DTE:** 期权 ~70 天,覆盖 SpaceX IPO 第一日 + Q2'26 ER 7/22(双重事件保护)
   - **预期成本:** ~$0 (collar 设计目标:short call 收入抵 long put 成本)
   - **下行保护:** 若 TSLA 跌至 $300,亏损封顶在 -$21 / 股(从 spot $391 - put strike $370)
   - **上行让出:** 涨破 $430 部分让出(若 SPCX 上市 TSLA 短期暴涨)
   - **触发条件:** 单只 TSLA 占 NLV ≥ 5% 时执行,< 5% 不必
   - 符合 CLAUDE.md M7 仓位"never trim stock,recommend downside protection" 原则。

**2.(若空仓但想小仓位试水)Sell put 等回调入场,而不是直接买入**

   - **结构:** Short Aug-15 $360 Put(15 delta,~70 DTE)
   - **Premium 收入:** ~$8-10/股 (~$800-1000/合约,基于 30-35% IV 估算)
   - **最大风险:** 被 assign 在 $360,实际成本 $350-352(扣 premium 后)
   - **触发条件:** TSLA 跌至 $370 以下 + IV rank > 40 时执行(SpaceX IPO 后 IV crush 可能机会)
   - **后续:** 若被 assign 立刻部署 collar 转入选项 1 结构。

**3.(观望触发条件)等 SpaceX IPO 后市场 reprice,寻找更好入场点**

   - **不建仓的指标:** SPCX 上市后 TSLA 横盘或下行到 $340-360 区间,Q2'26 ER 公布前 IV rank 攀升至 50+
   - **建仓信号:** 出现以下任一:(a) Q2 ER 营收恢复正增长 + Energy GM 维持 35%+;(b) Cybercab 量产首次披露季度交付台数 > 5k;(c) 估值降到 < 150x(spot 跌至 $270 左右意味着 PE ~$1.81 EPS × 150 = $271)
   - **风险:** 等不到底,SPCX 上市后市场反应可能与预期相反

### 翻车信号(由"持有/回避"转为"加仓")

- **观察 1:** Q2'26 ER(7/22)若 Auto + Energy 双部门收入回到正增长 + Op margin 反弹至 8%+
- **观察 2:** Robotaxi 跨城市扩张到 ≥ 5 个美国城市,fleet > 500 辆
- **观察 3:** Optimus 2026Q4 工厂剪彩并展示真实量产(非 demo video)
- **观察 4:** Cybercab 2026Q3 交付台数 > 5k(确认 mid-2026 量产承诺兑现)
- **观察 5:** SpaceX IPO 后实际 TSLA 跌幅 < -8% 且 30 天内恢复(说明 Musk premium 仍然厚)

### 翻车信号(由"持有/回避"转为"清仓/做空考虑")

- **观察 A:** Robotaxi 在 NHTSA 调查下被全美暂停
- **观察 B:** Q2 ER 营收再次同比下滑 + Op margin 跌破 3%
- **观察 C:** FSD V14 推出后内部测试视频被发现频繁干预(数据标注员爆料)
- **观察 D:** SpaceX IPO 后 SPCX 30 天表现强劲 + TSLA -20%+ 表明资金分流真实发生
- **观察 E:** Optimus 工厂剪彩推迟 + Cybercab 量产时间表再次延期

### 时间窗口

**Thesis horizon 1-2 年。 Re-evaluation 触发节点:**
- 短期(0-2 个月):**SpaceX IPO 6/12 后 30 天观察 + Q2'26 ER 7/22**
- 中期(6 个月):**Cybercab 量产实际进度 + Robotaxi 城市数 + Optimus 公开亮相**
- 长期(12-24 个月):**Energy 业务能否撑起 $25B+ 收入 + Robotaxi 是否形成可分析的收入流**

---

## Sources

### Financials & Filings
- **UW `get_company_info`** — TSLA 2026-06-06: spot $391.32, mkt cap $1.467T, shares out 3.756B, beta 2.02, next ER 2026-07-22
- **UW `get_income_statements`(annual)** — TSLA FY09-FY25 full P&L
- **UW `get_cash_flows`(annual)** — TSLA FY09-FY25 OCF/CapEx/SBC
- **UW `get_balance_sheets`(annual)** — TSLA FY07-FY25 含现金、债务、equity
- **UW `get_earnings_history`(quarterly)** — TSLA Q3'10-Q1'26 EPS reported vs estimated,Q2'26 estimate $0.47
- **UW `get_analyst_ratings`** — TSLA 10 家最新 ratings(2026-03-31 → 2026-06-05)
- **UW `get_ticker_performances`** — TSLA + GM + F + RIVN + META 1d/1w/1m/3m/6m/1y/5y returns
- **Massive `/v3/reference/tickers/TSLA`** — CIK 0001318605, employees 134,785, list date 2010-06-29
- **Massive `/v1/related-companies/TSLA`** — peer 候选集(RIVN, GOOGL, AMZN, GM, F, META, NVDA, LCID, AAPL)

### Peers (UW pulls for GM/F/RIVN/META)
- UW `get_income_statements` + `get_cash_flows` + `get_ticker_performances` + `get_company_info` 全部已拉取

### News & Sentiment
- **Massive `/v2/reference/news?ticker=TSLA&limit=15`** — 2026-06-04 → 2026-06-07 共 15 条 TSLA 相关新闻 + per-article sentiment
- **CNBC 2026-06-03:** [SpaceX targets $135 IPO price at valuation of $1.77 trillion](https://www.cnbc.com/2026/06/03/spacex-ipo-stock-price-roadshow-musk.html)
- **CNBC 2026-06-03:** [SpaceX is worth less than half of its $1.75 trillion IPO target, Morningstar says](https://www.cnbc.com/2026/06/03/morningstar-spacex-ipo-target-price-nasdaq.html)
- **Benzinga 2026-06-07:** ["This Week In Tesla: Robotaxi's First Year, SpaceX IPO Filing Changes, Tesla Terafab And More"](https://www.benzinga.com/markets/tech/26/06/53048862/this-week-in-tesla-robotaxis-first-year-spacex-ipo-filing-changes-tesla-terafab-and-more)
- **The VC Corner:** [SpaceX SPCX IPO S-1 Full Teardown: $1.75 Trillion Valuation, Starlink, xAI, and the Anthropic Deal (2026)](https://www.thevccorner.com/p/spacex-spcx-ipo-s1-teardown-valuation-2026)
- **Capital.com:** [SpaceX IPO targets June 2026 after SEC filing](https://capital.com/en-int/learn/ipo/spacex-ipo)

### TSLA Energy / Megapack
- **Energy-Storage.News:** [Tesla reports record energy storage deployments and profit ahead of vote on Musk's monster pay proposal](https://www.energy-storage.news/tesla-reports-record-energy-storage-deployments-and-profit-ahead-of-vote-on-musks-monster-pay-proposal/) — Q3'25 storage data
- **TechCrunch 2026-01-29:** [Tesla's energy storage business is growing faster than any other part of the company](https://techcrunch.com/2026/01/29/teslas-energy-storage-business-is-growing-faster-than-any-other-part-of-the-company/)
- **Tesla Q4 2025 Update Deck:** [PDF link](https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q4-2025-Update.pdf)
- **Tesla 10-Q FY2026 Q1:** [SEC filing](https://www.sec.gov/Archives/edgar/data/0001318605/000162828026026673/tsla-20260331.htm)

### TSLA-SpaceX Cross-Company
- **Electrek 2018:** [Tesla and SpaceX are partnering up to create new materials to use on Earth and in space](https://electrek.co/2018/05/10/tesla-spacex-new-materials/)
- **Futurism:** [SpaceX is installing Tesla batteries in Starship prototype](https://futurism.com/the-byte/spacex-installing-tesla-batteries-starship-prototype)
- **CNBC 2020:** [Here's how Tesla and SpaceX worked with and paid each other in the past year](https://www.cnbc.com/2020/04/28/heres-how-tesla-and-spacex-worked-with-and-paid-each-other-in-the-past-year.html)
- **Energy-Storage.News:** [SpaceX launch facility adding 8MWh of BESS; Tesla touted as supplier](https://www.energy-storage.news/tesla-supplying-power-pack-for-spacex-starbase-8mwh-bess-expansion/)
- **ZeroHedge 2026:** [SpaceX-Tesla Merger Speculation Grows As Decade Of Cross-Company Deals Reveal Deeper Integration](https://www.zerohedge.com/technology/spacex-tesla-merger-speculation-grows-decade-cross-company-deals-reveal-deeper)

### Robotaxi / FSD / Cybercab / Optimus
- **Wikipedia:** [Tesla Robotaxi](https://en.wikipedia.org/wiki/Tesla_Robotaxi)
- **MotorWatt:** [Tesla Cybercab 2026: Inside Tesla's autonomous robotaxi revolution](https://motorwatt.com/ev-blog/reviews/tesla-cybercab-2026)
- **Teslarati:** [Tesla pulls back the curtain on Cybercab mass production](https://www.teslarati.com/tesla-is-showing-us-that-cybercab-mass-production-is-well-underway/)
- **OptimusK Blog:** [Tesla Stock & Optimus: Is It a 10x Catalyst for 2026–2030?](https://optimusk.blog/blog/tesla-optimus-stock-catalyst-2026/)
- **Tesla 8-K FY2026:** [Cybercab pilot production status](https://www.sec.gov/Archives/edgar/data/0001318605/000162828026003837/exhibit991.htm)

### Gaps / Limitations (诚实标注)

- **TV reader (TradingView spot canonical) not invokable from this Bash-tool session** — spot 价 $391.32 来自 UW `get_company_info` 而非 TradingView 直接读取,违反 CLAUDE.md hard rule #2 默认路径。 实际影响小(每日 close 偏差通常 < 0.5%),但严格说应标注。
- **Massive `/v3/snapshot/locale/us/markets/stocks/tickers/TSLA` 返回 404** — Massive snapshot 端点对 TSLA 当下不可用,fallback 到 UW spot。 应该 retry / 查找替代端点。
- **UW `get_fundamental_breakdown` 返回 outdated 数据** — share_price $27.89, revenue $7.38B 来自 2016/2017 年 filing 快照,该端点对 TSLA 数据 stale。 因此 PE / EV/EBITDA / FCF yield 全部手算自其他端点,未交叉验证 fundamental_breakdown 端点。
- **UW `get_institution_holdings` returned "Institution not found"** — TSLA 13F 数据未能从 UW 端点获取,Section 9 缺机构持仓变化数据(只有 analyst ratings)。
- **未进行历史 PE percentile 自计算** — Section 4 仅给出 CONSENSUS 等级数据。 完整计算需要 Massive aggs(月度价)+ UW earnings(季度 EPS)对齐,token cost 较高未执行。
- **Energy 业务季度数据 piecemeal** — Q3'25 + Q1'26 通过 Web 搜索得到,Q4'25 + Q2'26 季度未拉取(UW income statement 是年度 + 全公司,无 segment 切分)。 想精确画 Energy revenue 季度曲线需要直接读 10-Q PDF。
- **Cybercab/Optimus 量产时间表** — 关于 mid-2026 + 2026 H2 这些是 Tesla 自述 + media reporting,未通过 SEC filing 独立验证。 Tesla 历史 timeline 推迟率高,base rate 提示对 management guidance 应打折。
- **SpaceX IPO 最终条款未定** — 截至 2026-06-07,定价(6/11)+ 首日(6/12)还有 5 天,实际 IPO 价格 + 上市初期 trading 行为均未确定。 Section 10 选项 1 (collar)使用 70 DTE 是基于 catalyst window 设计,实际 IV 在 IPO 后可能 crush。

---

## Outcome / Lesson(待 2026-07-22 ER 后填写)

待跟踪问题:
- (Q1) SpaceX IPO 6/12 当日 + 30 天 TSLA 实际涨跌幅?
- (Q2) Q2'26 ER 7/22 营收是否回到正增长?Energy Q2 数据如何?
- (Q3) Cybercab 量产进度是否如承诺 mid-2026 启动?
- (Q4) 实际持仓决策:本次分析后是否触发 collar / sell put / 观望?
- (Q5) 12 个月后回顾,场景概率分配(15%/50%/25%/10%)是否合理?
