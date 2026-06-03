# Execution

## Execution layering

Spec §9.1 (verified 2026-06-03 via `scripts/smoke/ib_mcp_findings.md`):

| Order type | Path | Why |
|---|---|---|
| Any option order (CC short call, CSP, spread, condor, jade lizard) | `ib_insync.IB.placeOrder` | IB MCP `create_order_instruction` is **equity/ETF only** — cannot place options at all |
| Bracket order (take-profit + stop-loss) | `ib_insync.IB.bracketOrder` | IB MCP has no OCA / no parent-child support |
| Stock leg of covered call / FCN underlying purchase | `IB MCP create_order_instruction` (tap-to-approve) | Trader explicitly wants the IBKR app deep-link approval flow |
| Read-only state (positions, balances, orders, trades) | IB MCP `get_account_*` | Cleanest API; works in-Claude |

Execution flow: `scripts/ib_order.py` builds the `Order` (and bracket
children if applicable) but does **not** submit. `scripts/manage_positions.py`
prints the pre-flight, asks the one YES/NO question, and on YES calls
`ib_insync.IB.placeOrder(contract, order)` (or for stock-only drafts,
`mcp__claude_ai_Interactive_Brokers_IBKR__create_order_instruction`).

## Pre-trade pre-flight checklist

(Spec §9.2. Every line must be present in the printed pre-flight before
the one YES/NO question.)

- **Legs** — for each leg: ticker, expiry, strike, right (C/P), action
  (BUY/SELL), quantity, exchange routing.
- **Mid price** — `(bid + ask) / 2`, both per-leg and combined for the
  spread.
- **Net debit / credit** — signed per-contract dollar amount; total
  for the position (×100 ×contracts).
- **Max loss / Max gain / Breakeven** — for defined-risk structures
  these are bounded; surface them at the contract level.
- **Margin requirement** — `IB.whatIfOrder(...)` returns the initial
  margin estimate; surface as both dollar and % of NLV.
- **P/L matrix at expiry** across spot scenarios −20% / −10% / −5% / 0
  / +5% / +10% / +20% — single table.
- **Account verification** — net liq, available cash, current
  positions in this name (don't pile a CSP under a covered call you
  already have).
- **UW regime check** — IV rank, VRP, gamma flip vs strike, put/call
  wall placement.
- **Liquidity check** — bid/ask spread as % of mid (>5% is illiquid),
  open interest on each leg, today's volume.
- **Catalyst clock** — earnings date, FDA dates, conferences within
  the position window.

Exactly one question follows: `"Submit? YES/NO"`. Any answer that
isn't a clean YES → abort the order.

## Bracket order defaults

Spec hard rule #6:

| Structure | Take-profit (% of max gain) | Stop-loss |
|---|---|---|
| Covered call | 50% | (none — exit via underlying) |
| Cash-secured put | 50% | 2× credit received |
| Bull put spread | 50% | (none for full-width stop; close at 50% of width below short) |
| Bear call spread | 50% | (close at 50% of width above short) |
| Iron condor | 25% (closer because two-sided gamma) | None — hard 21 DTE exit |
| Jade lizard | 50% | Below short put strike, manual close |
| Macro hedge (SPX put spread) | (let expire or roll at 21 DTE) | (none — defensive position) |

**Build mechanics.** `ib_insync.IB.bracketOrder(action, totalQuantity,
limitPrice, takeProfitPrice, stopLossPrice)` returns a list of 3
`Order` objects: parent (LMT), take-profit (LMT), stop-loss (STP). The
two children share an OCA group set by ib_insync internally; when one
fills, the other is auto-cancelled. Submit by iterating:

```python
bracket = ib.bracketOrder('SELL', 1, limitPrice=2.40,
                          takeProfitPrice=1.20, stopLossPrice=4.80)
for o in bracket:
    ib.placeOrder(contract, o)
```

For spreads, the parent is a `ComboOrder` on the combined contract; the
brackets attach to the parent's combined P&L not each leg independently.

## 21 DTE hard review

Spec hard rule #4: at 21 days to expiry, every short-premium position
produces a **blocking review prompt** on the next interaction with
option-wizard. The trader picks one of three:

1. **CLOSE.** Submit a closing order at current mid. Captures remaining
   theta as realized.
2. **ROLL.** Build a new position one or two expiries out at a similar
   delta; net credit or limited debit only (see Roll constraints below).
3. **ACCEPT-GAMMA.** Explicit override. Acknowledges that gamma risk
   spikes inside 21 DTE and the trader accepts the increased volatility
   on the remaining position.

Until the choice is made, **no other request gets answered**. This is
enforced by `scripts/manage_positions.py` checking for 21 DTE positions
at every invocation and short-circuiting on any unresolved one.

## Roll constraints

When the trader picks ROLL:

- **Defined-risk preservation.** A bull put spread rolls to a bull put
  spread of the same width or narrower. Never roll out to a naked short
  put.
- **Net credit or limited debit.** Roll should be net credit when
  possible. Net debit allowed up to 30% of the original credit when
  catalyst risk explains the move; document why in the roll comment.
- **No earnings span.** The new expiry must not span an upcoming
  earnings date for the underlying. Verify via TV news pull or a stored
  earnings calendar.
- **Same delta band.** Target similar short delta as original (e.g.,
  if original was 0.20Δ short, roll to 0.18-0.22Δ short). Don't tighten
  the strike just to chase credit.

## No-assignment policy

The 21 DTE rule is the primary safety. If a position is missed and
goes ITM with <7 DTE remaining:

- **Prefer roll** over accept-assignment, even at small net debit. Roll
  out one cycle to recapture optionality.
- **Refuse early-exercise risk** for short calls on ex-dividend dates;
  close 2 days before ex-date instead of rolling.

Assignment is acceptable only when:

1. The trader explicitly chose CSP with intent to own the stock at the
   strike (laddered entry).
2. The cash to take delivery is verified present (no margin call
   triggered).
3. There's no concurrent covered position that would create a wash sale
   or pattern day trader violation.

## OCA group mechanics at the ib_insync layer

`ib_insync.Order` exposes `ocaGroup: str` and `ocaType: int`:

- `ocaGroup` — any string; orders sharing the same string are linked.
  `bracketOrder()` auto-generates a unique group name.
- `ocaType` — three semantics in IB:
  - `1` = cancel-all-with-block (most strict; cancelling one cancels
    all siblings, no manual override mid-fill)
  - `2` = reduce-with-block (resize siblings based on fill, no manual
    cancel)
  - `3` = reduce-no-block (resize siblings, allow manual cancel)

`bracketOrder()` uses `ocaType=1` by default — fill on take-profit
auto-cancels the stop-loss and vice versa. To cancel manually, call
`ib.cancelOrder(takeProfit)`; the stop-loss is automatically cancelled
because `ocaType=1` links them.

## Failure modes

- **IB disconnection during submission.** `ib_insync` raises
  `IB.disconnected` exception; the order may or may not be at IB. Re-
  query `get_account_orders` (via IB MCP, which is independent of
  the Python connection) to verify status before resubmitting.
- **Partial fill on combo order.** With `ComboOrder`, IB only fills if
  all legs can fill; partial fills shouldn't happen on combos. If they
  do (mis-configured order), call `ib.cancelOrder(parent)` and rebuild.
- **Margin call mid-position.** Surfaces in `get_account_balances` as
  `excess_liquidity < 0`. `manage_positions.py` flags this as the
  highest-priority alert in the daily report; close the highest-margin
  position first (typically the iron condor's short side), not just
  the worst-performer.
- **MCP equity-only draft rejected as "options not supported".** If
  the trader accidentally pastes an option order into the MCP path, the
  draft fails with a clear error. Route to `ib_insync.placeOrder`
  instead; see Execution layering table at top of this doc.
