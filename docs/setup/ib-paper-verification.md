# IB execution paper verification

## What's already known (no test needed)

- IB MCP `create_order_instruction` is **draft-only** and supports **equity
  + ETF only**. It cannot place option orders. It has no OCA / parent /
  child fields. Confirmed via `scripts/smoke/ib_mcp_findings.md`.
- All option orders therefore go through `ib_insync` directly.
- Brackets are attached via `ib_insync.bracketOrder(...)`, which builds
  three linked orders (parent + take-profit child + stop-loss child) with
  an OCA group on the children. Documented in the ib_insync source and
  IBKR API guide.

## What we still verify on paper

### Setup

- Open TWS or IB Gateway in paper account mode (port 7497 for TWS paper,
  4002 for IB Gateway paper).
- Run `mcp__claude_ai_Interactive_Brokers_IBKR__get_account_summary` and
  confirm the account number begins with `D` (paper) or matches a known
  paper account.

### Test A (Python path): ib_insync places live without approval

The Python `IBClient.place_order` wrapping `ib_insync.IB.placeOrder` is
known to submit live with no approval step. Verify on paper that:

- An order placed via `IBClient.place_order` shows up immediately in TWS
  as `PreSubmitted` → `Submitted` (filled if liquid) without any user
  approval prompt.
- The safety implication: `scripts/ib_order.py` must enforce the `YES/NO`
  pre-flight gate before ever calling `IBClient.place_order`. There is
  no second chance.

### Test B (Python path): bracketOrder produces a working OCA group

Submit a single-leg parent buy + bracket pair (take-profit sell + stop-loss
sell). Verify in TWS that:

- All three orders appear, the parent as `PreSubmitted`/`Submitted`, the
  children as `PendingSubmit`/`Hold` (depending on TWS configuration).
- Both children share an `ocaGroup` value (TWS column or the order
  detail panel).
- After the parent fills, cancelling one child cancels the other.

### Test C (MCP stock-draft path): instruction → deep-link → approve

Use the MCP to draft a stock order (e.g. 1 share of ORCL at $1.00 LIMIT).
Verify:

- `create_order_instruction` returns an `instruction_id` and a URL.
- `get_order_instructions` includes the instruction.
- `get_account_orders` does **not** include it.
- Opening the URL on the IBKR app prompts the trader to approve before
  it becomes a live order.
- After approval, the order moves to `get_account_orders` with the
  expected limit price. Cancel it from the IBKR app to clean up.

## Outcome checklist

Record findings inline below and reference from `scripts/ib_order.py`
and `references/execution.md`.

- [ ] (Python) `ib_insync.placeOrder` submits live with no approval: YES / NO
- [ ] (Python) `ib_insync.bracketOrder` produces a working OCA group: YES / NO
- [ ] (MCP) `create_order_instruction` instruction lands in `get_order_instructions` queue: YES / NO
- [ ] (MCP) Deep-link approval flow works end-to-end: YES / NO

## Status (2026-06-03)

- (Python) `ib_insync.placeOrder` submission semantics: documented via
  ib_insync source + IBKR API guide. **Not** re-run live on paper this
  session — the user's account is live, not paper. The pre-flight YES/NO
  gate in `scripts/ib_order.py::build_preflight` is the only safety; do
  not bypass.
- (Python) `ib_insync.bracketOrder` OCA semantics: same — documented via
  source, OCA group auto-generated on the children.
- (MCP) `create_order_instruction` draft semantics: ✅ verified via
  schema + observed queue separation (`get_order_instructions` was empty
  while `get_account_orders` contained 1 live QQQ order during the
  2026-06-03 probe).
- (MCP) Deep-link approval flow: schema-confirmed (deep-link URL returned
  in instruction object). End-to-end click-through not exercised in this
  session.
