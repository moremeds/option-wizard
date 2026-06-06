# CRDO — Credo Technology · Quick fundamental read

*Generated 2026-06-06 (after Friday 6/5 close; FY26 earnings reported 2026-06-01)*

Mode: **quick** (3 sections, ≤ 40 lines). For full LULU-style deep dive (10 sections, peer matrix, scenario EV, MD/HTML/PDF), rerun with "深度研究 CRDO".

---

## Snapshot

| 指标 | 数值 | 备注 |
|---|---|---|
| Spot | **$217.50** | IB `get_price_snapshot`, Friday close (`is_close=true`) |
| Market cap | **$40.1B** | $217.50 × 184.45M shares [UW: `get_company_info`] |
| TTM PE | **~85x** | $217.50 ÷ FY26 EPS $2.56 (NI $472.3M / 184.45M shares) [UW: `get_income_statements`] |
| Forward PE | **UNVERIFIED** | NTM consensus 未拉;参考点:post-earnings analyst PT 均值 **$260.78** (n=9, range $215-$300) |
| 1Y return | **+198%** (1Y close $73 → spot $217.50);1W **-12%**;YTD **+51%** | [UW: `get_ticker_performances`] + IB |

> **Regime: momentum stretched** — 52w range $66.75-$245.95,spot 在 84%-tile,beta 3.03。基本面在加速、不是恶化 → "拒绝 short"。

---

## Fundamentals

- **Revenue:** $1,335M FY26 (4/30),+206% YoY,3Y CAGR **~93%** [UW: `get_income_statements`]。FY25 $437M → FY26 $1,335M 不是慢热,是阶梯跃迁,对应 AI/800G AEC 渗透。
- **Margins:** GM **68.0%** / OM **33.3%** / Net **35.4%** — FY25 OM 仅 8.7%,operating leverage 一年内翻 4 倍 (FY26 R&D $279M = 21% of rev,固定成本被规模摊薄)。
- **FCF:** FY25 OCF $65.1M − capex $36.1M = **FCF $29M, FCF margin 6.6%** [UW: `get_cash_flows`]。⚠️ **FY25 SBC $77.4M = 2.7× FCF** — 现金利润被股票稀释吃掉。FY26 FCF **UNVERIFIED**(UW 未解析)。
- **Balance sheet:** net cash(FY22 募 $204M + FY24 净融资 $175M);具体 FY26 net cash 数 **UNVERIFIED** for quick mode。

---

## Verdict

**观望 (持有不加仓)** — 单一最大原因:85x TTM PE 已经把"FY27 再翻倍 + 35% net margin 持续"price in 完美,但 1W -12% 表明 earnings 一过就开始消化,**风险回报在这个位置不对称**。

今日 PE 隐含的市场信念是"hyperscaler capex 不降速 + 单客户(历史 MSFT >40% 集中度,**UNVERIFIED for FY26**)不流失"——任何一条破裂都会触发 multiple compression(从 85x → 50x 意味着 -40%)。

**催化剂 3 个:**
1. **2026-09-02 FY27 Q1 财报**(首个验证季,最重要)
2. 客户集中度披露 / 10-K 中的 customer concentration risk factor
3. 800G / 1.6T AEC 产能爬坡 + hyperscaler RFP 公告

**翻车信号:**
- 上行 → 回踩 $170-180 区间(GS / Jefferies 早期 PT 锚定区)+ 基本面无负面 → 用 put-spread 接货升级到"加仓"
- 下行 → 任何单客户营收占比上升 OR 环比 revenue 下滑 → 回避

---

**Sources:**

- UW MCP: `get_company_info`, `get_income_statements` (annual, 7 FY 数据), `get_cash_flows` (annual), `get_ticker_performances`, `get_analyst_ratings` (15 rows, 2026-03-23 → 2026-06-02) — pulled 2026-06-06.
- IB `get_price_snapshot` — CRDO contract_id 541265127, NASDAQ, Friday 2026-06-05 close.

**Data gaps (not papered over):**

- FY26 cash flow statement 未在 UW 入库 → FY26 FCF, capex, SBC, 净现金 全部 UNVERIFIED。需要等 10-K 入库或 WebFetch SEC filing。
- NTM consensus EPS 未拉 → Forward PE UNVERIFIED。需要 WebSearch Yahoo / Seeking Alpha / Bloomberg consensus。
- 客户集中度 FY26 数 UNVERIFIED → 需要 10-K (item 1 / customer concentration risk factor) 或 IR call transcript。

**Skill:** `option-wizard:fundamental-analysis` (quick mode), branch `feat/fundamental-analysis-skill` PR #8.
