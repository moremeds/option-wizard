# IB MCP capability findings

**Verified:** 2026-06-03 against the live `claude.ai` IBKR connector
(`mcp__claude_ai_Interactive_Brokers_IBKR__*` tool surface).

## Tool catalogue actually exposed

| Tool | Purpose | Mutating? |
|------|---------|-----------|
| `get_account_summary` | Net liq, margin, buying power | no |
| `get_account_balances` | Cash + market value by currency | no |
| `get_account_positions` | Open positions w/ contract_id, qty, P&L | no |
| `get_account_orders` | **Live** orders (NEW/FILLED/CANCELLED) | no |
| `get_account_trades` | Historical fills | no |
| `get_price_history` | OHLCV bars | no |
| `get_price_snapshot` | Last/bid/ask | no |
| `search_contracts` | Resolve symbol → underlying_contract_id | no |
| `create_order_instruction` | **Draft** order; user must approve via deep-link | yes (draft) |
| `delete_order_instruction` | Remove a draft | yes (draft) |
| `get_order_instructions` | List **drafts** (separate queue from live orders) | no |

## Capability gaps that change the architecture

### 1. Equity + ETF only — no options surface

`create_order_instruction` description:

> Supported security types are: **Equity and ETF orders only.**

⇒ option-wizard cannot place a single covered call, CSP, spread, condor, or
jade lizard via the MCP. All option execution **must** use `ib_insync`.

### 2. No OCA / no parent-child orders

`create_order_instruction` parameters:

```
contract_id, side, order_type, quantity, limit_price, time_in_force
```

No `oca_group`, no `parent_id`, no `child_orders`. ⇒ bracket
(take-profit / stop-loss) groups cannot be built via the MCP — they must be
attached at the `ib_insync` layer.

### 3. Instructions vs orders are two separate queues

- `get_order_instructions` → drafts (empty in our smoke run)
- `get_account_orders` → live orders (1 real QQQ BUY LIMIT GTC in our smoke run)

The fact that the live QQQ order shows up in `get_account_orders` but
`get_order_instructions` is empty proves the two queues are distinct.
Therefore `create_order_instruction` is **draft-only**: it does not place
a live order until the user opens the deep-link and approves.

### 4. `search_contracts` returns `underlying_contract_id`, not `contract_id`

Smoke output for `search_contracts(query="ORCL", security_type="STK")`:

```
underlying_contract_id: 272800
exchange: NYSE
symbol: ORCL
sections: [STK, BAG, CFD, IOPT, OPT, WAR]
```

⇒ to place an actual ORCL stock order, we need to resolve the
`underlying_contract_id` (272800) to the tradeable STK `contract_id`. The
positions endpoint returns the right `contract_id` for held instruments
(e.g. QQQ stock = 320227571), but for net-new symbols we'd need to dig
through sections or use `ib_insync` to qualify the contract.

## Implications for the option-wizard spec

1. **§9 execution rewrite.** Drop "MCP-first, ib_insync fallback." Replace
   with: **ib_insync** is the canonical path for every option order
   (always) and for stock orders we want submitted live. **IB MCP** is
   used for (a) read-only account/position state and (b) drafting **stock**
   orders that route to the user for tap-to-confirm approval.
2. **Bracket orders.** Built at the `ib_insync` layer using
   `bracketOrder(...)` helper which attaches OCA automatically. The MCP
   path does not enter the equation.
3. **Daily report audit section.** User asked for the existing book to
   be flagged against the defined-risk rule (see §10). The audit reads
   from `get_account_positions` and groups short puts by underlying,
   computes assignment exposure, and lists positions exceeding cash
   coverage.

## Live account context (one-off, 2026-06-03 snapshot — not persisted)

- Net liq: $66,332
- Cash: $38,177
- Open live orders: 1 (QQQ BUY LIMIT 630.96 GTC, order_id 1564434761)
- Existing short puts:
  | Underlying | Strike | Expiry | Contracts | Assignment cost |
  |---|---|---|---|---|
  | QQQ | 665 | 2026-06-30 | -2 | $133,000 |
  | QQQ | 695 | 2026-06-30 | -1 | $69,500 |
  | QQQ | 696 | 2026-06-26 | -1 | $69,600 |
  | SPY | 729 | 2026-06-26 | -1 | $72,900 |
  | GLD | 408 | 2026-07-02 | -1 | $40,800 |
  | **Total** | | | | **$385,800** |
- Cash-coverage ratio: 38,177 / 385,800 = **9.9%** — margin-secured, not
  cash-secured. Fails the spec's "defined-risk only" rule; will surface in
  the daily audit section once implemented.
