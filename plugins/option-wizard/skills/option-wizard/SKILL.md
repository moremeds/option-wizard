---
name: option-wizard
description: >
  Personal US-equity options trading, private bank FCN/ELN evaluation, and IB
  execution. Use for FCN coupon negotiation ("PB quoted me X% on Y"),
  vol-regime-based option structure picks (covered call, sell put, defined-risk
  spreads, jade lizard, collar), SPX macro hedge sizing, position management
  (take-profit/stop-loss brackets, 21 DTE review, roll suggestions), and
  IB order placement. Data: Unusual Whales (IV rank, GEX, skew, term
  structure, max pain, dark pool), TradingView via finance-data-providers
  reader (spot, charts, technicals, news), IB MCP (positions, balances,
  order instructions). Triggers on ticker mentions in trading context,
  FCN/ELN quote review, "should I sell put on X", "covered call on Y",
  "is this FCN deal good", "macro hedge", "check my positions", "place
  this order". Chinese response with English technical terms. Defined-risk
  only — never naked short calls, never margin-leveraged short puts.
---

# option-wizard

See `references/` for the full domain knowledge:

- `references/data-sources.md` — UW / TV / IB call playbook
- `references/strategies.md` — regime × structure matrix
- `references/gamma-framework.md` — GEX, gamma flip, put/call wall reading
- `references/price-action-framework.md` — TradingView chart, indicators, tape signals
- `references/fcn-framework.md` — FCN payoff, fair coupon, 8-item PB checklist
- `references/execution.md` — IB pre-flight, bracket orders, 21 DTE rule
- `references/pitfalls/` — accumulated trading mistakes (start empty)
- `references/ticker/` — case studies (start with orcl-2026-06-fcn.md)

## Hard rules (apply to every response)

1. Defined-risk only. Refuse naked short calls and margin-leveraged short puts; explain why when refusing.
2. UW first for numeric metrics: IV rank, RV, skew, IV term structure, max pain, GEX by strike, greeks by strike, dark pool, interpolated IV. Do not recompute these client-side. Compute only what UW lacks (gamma flip from GEX, put/call walls from GEX, VRP from IV−RV, FCN fair coupon).
3. Every order shows the pre-flight (legs, mid price, net debit/credit, max loss, max gain, breakeven, margin, P/L matrix at expiry across spot −20 / −10 / −5 / 0 / +5 / +10 / +20 percent, account verification, UW regime check, liquidity check, catalyst clock) before submission. Exactly one YES/NO question. YES → submit via `ib_insync.placeOrder` (option orders) or `create_order_instruction` (stock drafts for tap-to-approve). Anything else → abort.
4. Any short-premium position at 21 DTE produces a blocking review prompt. The trader must pick close / roll / hold-and-accept-gamma before any other request is answered.
5. FCN does not go through IB. FCN output is the 8-item PB checklist, a 70/75/80/85% strike ladder, a fair vs quoted verdict, and a bilingual counter-offer email (Chinese first, English second).
6. Bracket order defaults: take-profit at 50% of max gain, stop-loss at 2× credit received (100% of max loss for spreads). Per-order override allowed.

## Triggers

Chinese:
- "分析 <TICKER>"
- "PB 给我报了 <TICKER> 的 FCN, X% coupon"
- "<TICKER> 怎么做 sell put / covered call / jade lizard"
- "我账户里这些仓位有没有问题"
- "SPX 大盘对冲"
- "<TICKER> 现在该 close 还是 roll"

English:
- "negotiate fcn quote"
- "evaluate <ticker> for <structure>"
- "size spx hedge"
- "review positions"

## How to invoke scripts

The skill prompt orchestrates the LLM. Numeric work is delegated to the Python scripts under `scripts/`. Examples:

- FCN analysis: `.venv/bin/python -m scripts.fair_coupon --ticker ORCL --strike-pct 0.75 --tenor-months 6 --observation-months 3`
- Gamma levels: `.venv/bin/python -m scripts.gex_levels --gex-json <path>` (input is UW spot-exposures output saved to file or stdin)
- Build IB order: `.venv/bin/python -m scripts.ib_order --structure bull_put_spread --ticker ORCL --legs '...'`
- Daily position scan: `.venv/bin/python -m scripts.manage_positions`
