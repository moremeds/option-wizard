# TSLA — 2026-06-03 (runbook trace)

**Date:** 2026-06-03
**Setup:** Range-bound TSLA at $423.74, 49 days from 7/22 ER, trader has zero
TSLA exposure but existing book (QQQ/SPY/GLD CSPs) is 59% margin-utilized.
Used as the canonical end-to-end trace of `references/analysis-runbook.md`
during the v0.1.0 acceptance run. Trade pre-flight was generated and the
trader replied "no it is a test" — order aborted per SKILL.md hard rule #3.

## Data snapshot

| Metric | Value | Source |
|---|---|---|
| Spot | $423.74 (2026-06-02 close) | UW |
| 200DMA (extrapolated) | ~$410-415 | UW SMA (last available 2026-04-17 = $398.87) |
| RSI(14) | 53.59 | UW |
| ATM IV (7/10) | 0.451 | UW chain |
| 21d RV | ~0.40 (computed from 4h candles) | UW + compute |
| **VRP** | **+0.046** | derived |
| Vol label | **NEUTRAL** (edge of RICH) | `scripts.vrp` |
| Net dealer gamma | +281K (slight positive) | UW GEX-by-ticker |
| 7/10 put wall | $400 (oi_cluster on put_gex) | `compute_levels_per_expiry` |
| 7/10 call wall | $440 (oi_cluster on call_gex) | `compute_levels_per_expiry` |
| Per-front-week call wall (6/05) | $430-440 | `compute_levels_per_expiry` |
| Gamma flip (per-expiry 7/10) | spot in long-gamma zone | derived |
| **IV term structure** | **Contango** (7/10 0.451 → 8/21 0.482) | UW chains × 4 expiries |
| 25Δ skew (7/10) | +0.035 (calls richer than puts) | UW chain |
| Next earnings | 2026-07-22 (49 days) | UW flow alert metadata |
| Account: cash / NLV | $38,178 / $66,333 | IB |
| Account: avail / init margin | $21,426 / $44,906 (59% util) | IB |

## Per-layer execution trace

| Layer | Data source | Result |
|---|---|---|
| 0 — Account | IB `get_account_summary` + `get_positions` | 0 TSLA; 59% margin utilized; defined-risk only |
| 1 — Vol/dealer regime | UW GEX, max pain, VRP compute | NEUTRAL vol, slight + gamma, walls per-expiry |
| 2 — Term + skew | UW chains × 4 expiries | Contango (no catalyst inside window); +0.035 skew |
| 3 — Price action | UW SMA200 + RSI14 + 4h candles | +2-3% above 200DMA = mild bull; RSI 53 = neutral; range $397-445 |
| 4 — Tape | UW flow alerts + flow per expiry + dark pool | Bullish call chase front; $6.7M Nov put hedges back; 5/29 $431 dark pool blocks underwater |
| 5 — Catalyst clock | derived | ER 7/22; trade expiry 7/10 (12-day buffer); 21 DTE review 6/19 |
| 6 — Structure pick | strategies matrix | NEUTRAL × mild-bull → bull put spread; 4-signal veto: 0/4 fire |
| 7 — Pre-flight + YES/NO | IB live (markets closed → UW prices as proxy) | Pre-flight emitted; trader: NO; aborted |

## Recommended structure (per runbook output)

```
TSLA 2026-07-10 expiry (37 DTE)
SELL 1× 7/10 400P @ $13.27 (UW last)
BUY  1× 7/10 390P @ ~$10.43 (interpolated)
─────────────────────────────────────
Width:        $10
Net credit:   ~$2.80
Max loss:     $720
Max gain:     $280 (28% width return)
Breakeven:    $397.20 (-6.3%)
Margin (IB):  ~$720 (defined risk)
Qty:          1 contract (3.4% of AvailableFunds)
```

## Decision

**Trader: NO (test).** Order aborted; no fill, no positions modified.

## What the runbook caught that a single-pass analysis would miss

1. **Per-expiry call wall divergence.** Aggregated GEX across all expiries
   surfaced $640 as call wall (long-tail noise). Per-expiry on 6/05 surfaced
   $430-440 (real tactical resistance). Trader called this out — `gex_levels`
   was extended with `oi_cluster` definition + `compute_levels_per_expiry`
   to make per-expiry the default for tactical reads.

2. **Term structure contango as catalyst-clearance signal.** 7/10 IV (0.451)
   < 8/21 IV (0.482) confirms no catalyst is being front-loaded into the
   trade window — strengthens the entry beyond just VRP edge.

3. **Inverted equity skew (+0.035).** Calls richer than puts is unusual for
   equity. Not a green light on its own but rules out "puts structurally bid
   on crash fear" — meaning the spread's short-put leg isn't selling into
   structural demand.

4. **Account-state constraint as size cap.** With 59% margin utilized on
   existing book, the size came down from 2 contracts to 1 even though risk
   math could support more. The runbook's Layer 0 gates this.

## What was blocked / extrapolated

- **TV news + chart-state**: opencli `tradingview` plugin was registered but
  commands rejected access declarations (opencli version was 1.7.22, plugin
  needed ≥1.8.0). Fixed in same session: upgraded opencli to 1.8.2, re-synced
  the plugin cache from source. After fix: TV commands callable. Then a
  second-order block surfaced — see "TV-enabled re-analysis (delta)" below.
- **IB market data on 7/10 puts**: returned all zeros (likely after-hours +
  L1 option subscription not active). Used UW chain `last_price` from 6/02
  close as the pricing proxy. Real entry would need fresh quote.
- **200DMA**: UW returned data up to 2026-04-17 only. Extrapolated forward
  by ~$1/week trend — reported as approximate.
- **TSLA's prior ER absorption** (4/22): not verifiable without TV news.
  4-signal bullish veto signal #1 marked unknown rather than fabricated.

## TV-enabled re-analysis (delta, same-day follow-up)

After the initial analysis, the TV reader was brought fully online and the
TV-blocked layers (3 and 6) were re-run. Two extra blocks surfaced and got
fixed in sequence:

1. **Port 9222 collision** — `chrome-devtools-mcp` (loaded as an MCP server
   in this Claude Code session) already binds 9222. Every `opencli
   tradingview launch` attempt against the default port fails silently
   because the port is taken; the launch returns `ready: false` and no
   subsequent data command can connect. Fix: launch with `--port 9224` and
   set `OPENCLI_CDP_ENDPOINT=http://127.0.0.1:9224` for the data commands.
   Persisted in `~/.zshrc` AND `~/.zshenv` (the latter so non-interactive
   shells — e.g. tool-spawned subprocesses — also pick it up).

2. **Stale `TradingView --help` process** — a manual `TradingView --help`
   probe earlier in the session left a detached binary process running.
   macOS `open -a TradingView` then quietly skipped re-spawning (it
   considers the app "already running" regardless of argv), so the new
   `--remote-debugging-port` flag was never applied. The plugin's
   `osascript ... quit` (polite quit) didn't catch the detached process.
   Fix: `pkill -KILL -f "TradingView"` before relaunch. Worth a PR upstream
   to make `launch.js` use hard-kill rather than osascript quit when a
   detached binary instance is detected.

With TV online, the **4-signal bullish veto check** populated properly:

| # | Signal | Before TV | After TV |
|---|---|---|---|
| 1 | Post-ER absorbed gap-up | Unknown | Still unknown (no recent gap-event news) |
| 2 | 3+ independent channel checks of demand strength | Unknown | **✅ Fires** — 6 sources (Reuters ×2, Invezz, GuruFocus, TradingView, Zacks) all confirming May Chinese EV sales +39.4% and EU recovery |
| 3 | Validated thematic re-rate | No evidence | ⚠ Partial — Fremont→Optimus pivot + Reuters self-driving piece, mixed with speculative SpaceX-valuation narrative |
| 4 | Term structure inversion | NOT firing (contango) | NOT firing |

**Count: 2 firm + 1 partial of 4. Threshold for veto is ≥3. No veto.**

Plus:
- **Chart-state**: `Ul01ifAY` layout open but symbol/interval both empty —
  TV is up but TSLA isn't the current focus. No active conviction signal
  from the terminal layout.
- **Spot intraday**: TV realtime quote at 2026-06-03 07:44 UTC shows
  $423.74 +1.89% — pre-market is bid into the open, not gapping down. The
  short put is not facing immediate gamma stress at entry.

**Structure recommendation unchanged** (bull put spread 400/390, 1 contract)
but **conviction floor raised**. The principled upgrade path with veto
signals firing 2.5/4 is: stay at 1 contract for risk discipline given the
existing book's margin utilization, OR scale to 2 contracts on stronger
direction conviction. Either is defensible — the runbook gates *size*, not
the structure itself.

**Decision still NO** (test mode). No position opened in either round.

## Bugs surfaced and fixed during this trace

| Bug | Fix |
|---|---|
| `gex_levels.compute_levels` aggregates across all expiries → misleading "wall" | Added `compute_levels_per_expiry`; per-expiry is now the trader-facing default |
| `_call_wall` only supports `net_neg_gex` definition → returns None for upside-skewed names | Added `call_wall_definition='oi_cluster'` to surface concentrated call_gex peaks |
| TV plugin commands all rejected by opencli | Upgraded opencli 1.7.22 → 1.8.2; re-synced plugin cache from source; commands now callable |
