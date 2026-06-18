# Review (复盘) Framework

Structured retrospective on the trader's recent analyses + actual trades.
Triggered by "复盘" / "weekly review" / "monthly review" / "review my
recent calls". The skill's sixth workflow (see `workflows-overview.md`).

## What this is

The skill produces a lot of analyses: per-ticker calls, vol-regime
labels, structure recommendations, refusal verdicts on PB quotes. The
trader also places trades, some matching the analyses and some not. Over
a week / a month, two questions accumulate:

1. **Were the analytical calls right?** Did spot / IV move the way the
   analysis predicted? Did the recommended structure print P/L?
2. **Did the trader's execution capture that edge?** When analysis was
   right, did the trader act on it? When analysis was wrong, did the
   trader's instinct override save the day?

The 复盘 framework answers both via **markout** — the standard
execution-quality metric measuring P/L at horizon T after each
decision, normalized so analyses and trades are directly comparable.

## Source separation (SKILL.md hard rule #9)

**Three independent layers, sourced strictly. Never cross-infer.**

| Layer | Source | What it measures |
|---|---|---|
| **A — Analysis quality** | `references/private/{ticker,market,review}/**/*.md` (archive only, recursive) | Directional verdict on past analyses: was the call right? Hit rate by call type / ticker. **Archive describes a proposed trade or analysis-only thesis — never a trade record.** |
| **B — Trade flow** | **xenon `/blotter` (IB + Futu fills) + `/portfolio` + `/futu/portfolio`** via `parse_xenon_blotter` — BOTH brokers, every review (IB MCP `get_account_trades` + Futu `portfolio-analyser` CLI = documented fallback) | Actual fills, execution markout, realized P&L, roll patterns. **Only legitimate source for "what was actually done."** |
| **C — Cross-cut advisory** | Trader / LLM judgment | Manual observations linking A ↔ B. **Judgment-only — no algorithmic scorecard, no `followed × correct` quadrant.** |

**Forbidden** (per hard rule #9):
- Inferring execution from an archive filename like `qqq-...-tp-close.md` — that's analysis, not a trade
- Auto-joining calls to trades by ticker + date proximity (the deleted `reconcile_calls_with_trades` / `discipline_quadrant`)
- Running 复盘 with only IB pulled — Futu is required every time

Layer A and Layer B aggregates are reported in **separate tables**, never side-by-side with a computed Δ. If the trader wants the "did execution capture the analysis edge?" question answered, that observation goes into Layer C as judgment, with explicit references back to the Layer A call and the Layer B trade — but stays advisory.

## What this is NOT

**FCN / AQ / DQ are out of scope.** PB structured products live on a
separate workflow (Workflows 4 + 5). Their P/L decomposition (path
truncation on KO, doubling-tail PV, observation cadence) doesn't fit the
horizon-markout shape, and their refusal verdicts already have their own
checklist accountability. The 复盘 framework only covers:

- Directional calls on individual stocks / indices
- Vol regime calls (RICH / NEUTRAL / CHEAP)
- Listed-options structure recommendations (CSP, covered call, spreads,
  collars, jade lizards, protective puts) and the resulting trades
- Stock outright trades

If a 复盘 sweep encounters an FCN/AQ/DQ archive file, it logs the file
and skips it — the trader audits PB deals through Workflow 4/5
post-mortems separately.

## Cadence: two distinct workflows

| Workflow | Window | Use case | Output emphasis |
|---|---|---|---|
| **Weekly review** | 7 calendar days back from invocation date | Micro-feedback loop: did this week's calls hold up? What position changes happened? | Layer A per-call scorecard + Layer B trade log + Layer C advisory observations. No pattern aggregation (sample too small). |
| **Monthly review** | 30 calendar days back | Pattern detection: systematic miss on a call type / ticker / regime? Roll cadence / execution drift? | Everything from weekly + Layer A pattern analysis (hit rate by call type / ticker / regime) + action items proposing skill rule changes |

CLI:

```bash
.venv/bin/python -m scripts.retrospective --window weekly
.venv/bin/python -m scripts.retrospective --window monthly
.venv/bin/python -m scripts.retrospective --window monthly --no-writeback --no-pitfall-drafts
```

Default behavior writes verdicts back to source archive files and emits
pitfall draft candidates. Flags opt out.

## Layer A — Analysis quality (archive only)

A "call" is one falsifiable claim extracted from an archived analysis.
The framework recognizes three types. **Source is `references/private/{ticker,market,review}/**/*.md` exclusively (recursive)** — archive presence never implies a trade happened.

### Three call types

| Type | Encoded as | Direction signal | Truth source |
|---|---|---|---|
| **Directional** | Stock or index expected to move up/down/range over horizon | +1 bullish / −1 bearish / 0 range | IB `get_price_history` daily close ¹ |
| **Vol regime** | IV is RICH / CHEAP relative to RV | −1 RICH (expects vol compression) / +1 CHEAP (expects vol expansion) | UW IV rank time series + UW realized vol |
| **Structure** | Listed-options structure recommended (bull put spread, CSP, collar, …) | Implicit from structure's natural delta; encoded as expected sign of normalized P/L | Mark-to-market of the hypothetical structure on the IB `get_price_history` daily-close path ¹; if trader entered, actual position mark |

**FCN / AQ / DQ structure recommendations are filtered out** at the
extraction stage — they live in PB workflows.

> ¹ **Markout-truth fetch path (read before quoting any spot).**
> `opencli tradingview` exposes only a live `quote` (current spot) — it has
> **no historical-bars command** — and its desktop CDP session is often
> unreachable in a headless review. So the markout truth series comes from
> **IB `get_price_history`** (`step=ONE_DAY`, `period=TWO_WEEKS` or
> `ONE_MONTH`, `outside_rth=false`). Resolve the `contract_id` first via
> `search_contracts` (`STK` for single names / ETFs, `IND` for indices;
> e.g. SPX = 416904 CBOE · QQQ = 320227571 NASDAQ · VIX = 13455763 CBOE).
> TV is a live-spot cross-check only when its CDP session is up — never the
> historical series. (Per SKILL.md hard rule #2, OHLCV historical: TV
> primary *when reachable*, IB `get_price_history` is the working fallback
> and the de-facto path for 复盘.)

### Markout horizons

Fixed grid: **T+1d, T+5d, T+10d, T+21d, T+45d** measured in trading
days from the analysis date. Rationale:

- T+1d catches overnight reversals
- T+5d ≈ one trading week
- T+10d aligns with typical short-vol theta decay window
- T+21d aligns with the 21-DTE management gate (hard rule #4) and
  monthly options cycle
- T+45d aligns with the standard 45-DTE expiry pick for sell-premium
  structures

If the trader closes a position before a horizon, that horizon's mark
uses the realized close P/L (markout truncates, doesn't extrapolate).

### Markout metric per call type

**Directional**:

```
markout_T = direction × (spot_T / spot_0 − 1)
```

Positive = call was correct. Reported as raw percent (e.g., `+0.024`
means +2.4 percentage points of correct signed move). Phase 2 may add
vol-adjusted variant (divide by `IV_0 × sqrt(T_days / 252)` to express
in σ units) — deferred until N ≥ 50 calls.

**Vol regime**:

```
iv_rank_markout_T = direction × (iv_rank_T − iv_rank_0)
rv_realized_markout = direction × (rv_realized_over_window − iv_0)
```

Where `direction` is −1 for RICH (call expected IV to come down) and +1
for CHEAP. `rv_realized_markout` is an auxiliary check — was IV
genuinely rich vs subsequent realized? Reported on horizons T+5/10/21
(IV rank doesn't move materially over T+1).

**Structure**:

```
markout_T = (mark_T − entry_basis) / max_loss
```

Where:

- `mark_T` is mark-to-market at horizon
- `entry_basis` is entry credit (for short premium) or debit (for long
  premium)
- `max_loss` is the structure's defined max loss (spread width −
  credit, or full debit for long premium)

For long stock holdings: `markout_T = (spot_T − entry) / entry`.
Reported as a fraction in `[-1.0, +∞)` for short premium and `[-1.0,
+∞)` for long premium, where `+1.0` means full max profit captured at
horizon.

If the trader did NOT enter the recommended structure, the structure
markout is **simulated**: mark the hypothetical structure on the actual
underlying daily-close path (IB `get_price_history`, footnote ¹) using
either:

- **Phase 1** (current): Black-Scholes-Merton mark with the IB
  `get_price_history` daily close + UW IV at analysis date held flat
  (crude — flagged as `mark_source = "model"`). Exception: if the
  structure's expiry falls inside the markout window, use terminal
  intrinsic at expiry (exact) instead of the BSM mark — e.g. an expired
  iron condor's terminal value is fully determined by the expiry-day close.
- **Phase 2**: IB `get_price_history` for the specific option contract
  if accessible (`mark_source = "ib_chain"`)
- **Phase 3**: macmini internal historical DB via dedicated MCP
  (`mark_source = "macmini_db"`)

Phase 1 is the only available path today — the script flags every
`mark_source = "model"` mark as a known approximation in the report so
trader can discount confidence.

### Verdict thresholds (qualitative for now)

**Directional**:

| Markout @ verdict horizon | Verdict |
|---|---|
| `> +0.02` | CORRECT |
| `−0.02 ≤ markout ≤ +0.02` | NEUTRAL (noise band) |
| `< −0.02` | WRONG |

Verdict horizon defaults to **T+21d** for directional calls. ±2% is a
qualitative noise band — roughly 2× SPX single-day median move. Phase 2
replaces with vol-adjusted ±0.5σ once N ≥ 50 calls have been logged.

**Vol regime**:

| IV rank Δ @ verdict horizon | Verdict |
|---|---|
| Same sign as direction, ≥ 5 pts | CORRECT |
| Within ±5 pts | NEUTRAL |
| Opposite sign, ≥ 5 pts | WRONG |

Verdict horizon defaults to **T+10d** for vol regime.

**Structure**:

| Normalized markout @ verdict horizon | Verdict |
|---|---|
| `> 0` (any positive) | CORRECT |
| `0` | NEUTRAL |
| `< 0` | WRONG |

Verdict horizon defaults to **T+21d** for structures. No noise band —
structure markout is already normalized by max loss.

These thresholds are intentionally generous early on. The point of
quallitative-first is to be lenient enough to learn from the data, not
to assert precision the sample size doesn't support. Tighten once data
accumulates.

## Layer B — Trade flow (broker only: IB + Futu)

**Both brokers required every review** (per `private/trader-profile.md`
"Position-review scope").

**PRIMARY — xenon `/blotter`** (IB + Futu fills, one read-only surface):
`XenonClient().blotter()` → `parse_xenon_blotter(blotter, window_start,
window_end) → list[Trade]`. The blotter carries no option strike/expiry/right
at the execution level, so `option_meta` is None (pre-enrich if needed).
Check freshness via the blotter `as_of` and the Futu `is_stale` flag on
`/futu/portfolio`.

**FALLBACK** (when xenon is unreachable) — pull each broker independently,
then call the matching parser:

- **IB**: `mcp__claude_ai_Interactive_Brokers_IBKR__get_account_trades period=DAYS_7|DAYS_30` → `parse_ib_trades(response, window_start, window_end) → list[Trade]`
- **Futu**: `cd ~/projects/portfolio-analyser && npx tsx src/cli.ts ft --range 1m --rerun` (writes JSON report under `reports/`) → `parse_futu_trades(report_json, window_start, window_end) → list[Trade]`. **`--rerun` is mandatory for every review.** The CLI caches trades by ISO week, so without it a freshly-*named* report can still carry a stale `trades.dateRange.to` (observed 2026-06-14: a report file stamped 06-12 whose trade data ended 06-08, silently dropping the entire week's Futu flow). Before trusting any pre-existing report, verify `trades.dateRange.to ≥ the last trading day at or before window_end`; `parse_futu_trades` raises `ValueError` on stale data as a backstop, but the orchestrator should pass `--rerun` so it never trips.

Tag `trade_sources=["IB", "Futu"]` (or whichever subset succeeded) on the `ReviewReport`. If a broker pull fails or returns empty, surface that as a **data gap in Layer B's output**, never silently drop. The `cross_cut_advisory` is computed only against the brokers actually pulled.

For every fill within the window:

| Trade type | `entry_basis` | `mark_T` source | Normalization denominator |
|---|---|---|---|
| Stock outright | `entry_fill × abs(qty)` | IB `get_price_history` daily close × qty ¹ | `entry_basis` |
| Long single option | `entry_fill × multiplier × abs(qty)` | option mid at T (chain or BSM) × qty | `entry_basis` |
| Short single option | `entry_credit × multiplier × abs(qty)` | `entry_credit − option_mid_T` × multiplier × abs(qty) | `multiplier × strike` (= margin proxy) |
| Defined-risk spread | sum of leg fills | sum of leg marks at T | `max_loss` (= spread_width − credit, for credit spreads; = debit, for debit spreads) |
| Collar / protective put overlay | sum of overlay leg fills (stock leg excluded) | sum of overlay leg marks at T | sum of overlay max-loss components |

**Multi-leg normalization**: the trade markout treats a multi-leg
position as a single trade keyed by the earliest leg's entry timestamp.
Legs entered within the same trading day are bundled; legs entered on
different days are separate trades (each with its own markout sweep).

**Mark source provenance**: each per-horizon mark carries
`mark_source ∈ {chain, model, realized_close}`. `realized_close` =
trader closed before the horizon; that horizon's mark = realized P/L,
remaining horizons report N/A. Reports surface the % of marks that came
from `chain` vs `model` so the trader knows how much to trust the
markout curve.

### Open multi-expiry term-curve snapshot

After trade-flow markouts complete, any ticker that still has **open**
positions across ≥2 expiries gets a current-time IV term-curve check.
This is the **same** check Workflow 3 (book review) runs in real-time
— here it's invoked retroactively as part of the 复盘 so a trader who
hasn't run a book review since the positions were opened still sees
the regime.

**Mechanics:**
- Pull `get_chains_for_expiry` for each held expiry (ATM ± 3 strikes
  is enough — full chain is wasteful here).
- Extract ATM IV per expiry via
  `scripts.term_curve.atm_iv_from_chain_rows(rows, spot)`.
- Label adjacent pairs via
  `scripts.term_curve.label_regime(atm_iv_by_expiry)` →
  list of `{from_expiry, to_expiry, iv_from, iv_to, basis, regime}`.
- Collapse with `scripts.term_curve.summarize_regime(pairs)` →
  one of `all_contango`, `all_inverted`, `all_flat`,
  `mixed_contango_inverted`, `mixed_with_flat`.

Surface the per-pair table + aggregate label under Layer B's
per-ticker block. **Skip** any ticker with only one held expiry (no
adjacent pair to label). Single-ticker IV rank / 52w percentile
**does not substitute** for this — same rule as Workflow 3.

**Why it lives in Layer B, not Layer A:** the check needs the
**actual held expiries**, which only the broker side knows. Archive
files document the proposed thesis but not what is currently open
across expiries. This is why the check sits in the Layer B pipeline
(step 3b in `workflows-overview.md` Workflow 6) rather than the
archive-driven Layer A.

**Why not auto-emit an action item:** the regime label is a signal,
not a directive. A ticker with `mixed_contango_inverted` may already
be intentionally structured that way (e.g., long the inverted expiry
as a vol-crush hedge against the contango short). Whether to roll
the inverted leg out is a trader-judgment decision and surfaces in
Layer C if the trader chooses to flag it.

## Layer C — Cross-cut (advisory, judgment-only)

**No algorithmic scorecard. No `followed × correct` quadrant. No automated reconciliation.** Per hard rule #9, the framework refuses to auto-join archive (Layer A) and broker (Layer B) data — those are independent streams answering separate questions.

What lives here:

- Manual observations the trader (or LLM in advisory mode) wants to flag, each labeled **"judgment-only"** in output
- Example: `"6/04 macro premarket bearish call → corresponding VIX hedge opened only on 6/05 after VIX 15→21 → execution lag of 1 trading day on hedge timing"`
  - References Layer A: `macro-2026-06-04-premarket-snapshot.md`
  - References Layer B: IB VIX AUG2026 20/30 call spread × 25 on 2026-06-05
  - **Not scored, not aggregated** — just surfaced for trader review

Schema (passed into `run_review(cross_cut_advisory=[...])`):

```python
[
  {
    "observation": "human-readable string",
    "layer_a_refs": ["macro-2026-06-04-premarket-snapshot.md", ...],
    "layer_b_refs": ["VIX AUG2026 20/30 call spread 2026-06-05", ...],
    "propose_action_item": True,  # if True, surfaces as a T-item
  },
  ...
]
```

**Why no scorecard?** A trade is its own decision — it doesn't "follow" or "ignore" an archive. The archive may have proposed something different from what was executed; the executed trade may have responded to fresh information not in the archive. Conflating the two streams produced false discipline metrics in early versions of this framework (see v0.3 changelog below).

## Per-layer aggregate outputs

Layer A and Layer B aggregates are reported **separately**:

**Layer A — Avg call markout (archive only)**

| Horizon | Avg call markout | n_calls |
|---|---|---|
| T+1d | … | … |
| T+5d | … | … |
| T+10d | … | … |
| T+21d | … | … |
| T+45d | … | … |

**Layer B — Avg trade markout (broker only, IB + Futu)**

| Horizon | Avg trade markout | n_trades |
|---|---|---|
| T+1d | … | … |
| T+5d | … | … |
| T+10d | … | … |
| T+21d | … | … |
| T+45d | … | … |

No "Δ (call − trade)" column — that comparison is judgment-only and lives in Layer C.

Per-ticker / per-regime breakdowns run inside each layer independently (monthly only).

## Pattern analysis (monthly only)

Weekly reviews skip this — sample too small. Monthly reviews aggregate:

| Breakdown | Computed |
|---|---|
| Hit rate by call type | `% CORRECT` for directional / vol regime / structure each |
| Hit rate by ticker | Tickers with ≥3 calls in window: per-ticker correct% |
| Hit rate by vol regime | Hit rate when analysis labeled RICH vs NEUTRAL vs CHEAP |
| Hit rate by data source | Hit rate when call rested primarily on UW signal vs TV chart vs IB account state |

Outliers (e.g., TSLA at 0% hit rate over 4 calls; CHEAP regime at 80%
hit rate vs RICH at 30%) get flagged in action items as candidates for
rule additions or pitfall promotion.

## Output structure (4 stages, mirrors book-review)

1. **Data pull**
   - Window dates + count of archive files scanned
   - IB trade pull result (count, date range) — note any pull failures
     as gaps
   - TV spot history pull result per ticker (count of horizons covered)
   - Option mark sources tally (`{chain: N, model: M, realized: K}`)
2. **Per-call scorecard table**
   - Columns: `ticker | date | type | direction | T+1 | T+5 | T+10 | T+21 | T+45 | verdict`
   - Sorted by date descending
3. **Side-by-side markout table** (the central deliverable)
4. **Discipline 4-quadrant** + per-quadrant avg markout
5. **Pattern analysis** (monthly only)
6. **Action items — END only, never mid-flow**

## Action items

Four groups, mirroring the book-review structure:

- **S1, S2, …** — Skill rules to add (e.g., "skill is wrong on TSLA 4/4
  times — add CLAUDE.md rule downweighting directional signals for TSLA
  during sustained negative dealer gamma")
- **P1, P2, …** — Candidate pitfalls (from WRONG calls — see next
  section)
- **T1, T2, …** — Trader-profile adjustments (e.g., "M7 buy-and-hold
  rule was overridden twice this month — confirm or strengthen the
  carve-out")
- **D1, D2, …** — Data quality flags (e.g., "37% of structure marks
  used BSM fallback — getting macmini DB online would tighten Layer 2
  fidelity")

Each line carries a one-line description + a trigger phrase ("S1 add",
"P1 promote", "T1 update", "D1 fix") so the trader picks fast. The
framework waits for the trader to pick — never auto-applies.

## Auto-writeback to archive Outcome section

Every archive file under `references/private/{ticker,market,review}/` has an empty
`## Outcome / Lesson` section (per SKILL.md §"Reporting & archive"). The
复盘 framework auto-fills these for any analysis it processed:

```markdown
## Outcome / Lesson

**Verdict (复盘 YYYY-MM-DD, monthly):** CORRECT
**Markout (raw % unless noted):**
- T+1d:  +0.4%
- T+5d:  +1.8%
- T+10d: +2.6%
- T+21d: +3.1%  ← verdict horizon
- T+45d: +4.2%
**Mark source:** chain (4/5) / model (1/5)
**Lesson:** (empty — trader fills in)
```

Idempotency: if the section already contains a `Verdict (复盘 <same date>,`
line, the framework skips it. If a newer 复盘 re-runs the same analysis
at a longer horizon, it appends a new block dated to that run.

Opt-out: `--no-writeback` flag suppresses all archive edits. Useful for
exploratory runs.

## Auto pitfall draft generation

For each call with `verdict = WRONG`, the framework writes a draft
pitfall to `references/pitfalls/_drafts/NN-slug.md` (gitignored — see
.gitignore). The draft has:

- Date / ticker / horizon / verdict
- Original call notes from the archive
- Truth data: what actually happened (spot/IV path)
- Empty "What went wrong" / "Rule going forward" sections

The trader reviews `_drafts/`, strips account-specific numbers, and
promotes selected drafts to numbered `references/pitfalls/NN-slug.md`
files (per the existing `_template.md` workflow). Drafts not promoted
stay in `_drafts/` as historical record; trader can periodically wipe
the dir.

Idempotency: drafts are keyed by `pitfall-<archive_filename_stem>.md`
in `_drafts/`. Re-running 复盘 over the same archive doesn't generate
duplicates.

Opt-out: `--no-pitfall-drafts` flag skips draft emission.

## Integration with existing skill components

- **Archive Outcome section** — SKILL.md §"Reporting & archive" already
  specifies an empty Outcome / Lesson block on every archive file
  "for audit fill-in". 复盘 is the structured fill-in mechanism.
- **Pitfall promotion path** — SKILL.md already documents "Lessons that
  generalize get promoted to `references/pitfalls/NN-slug.md`
  (account-stripped)". 复盘's `_drafts/` is the promotion staging area.
- **Re-invocation against same ticker** — SKILL.md §"Audit cadence"
  says "trader (or skill on re-invocation against same ticker)
  revisits each `private/` file at its named checkpoint". 复盘 is the
  executable version of this sentence — invoke it at any time and it
  visits every checkpoint that falls inside the window.

## Fixes from the first real run (v0.2)

The first 复盘 run against the trader's actual archive (2026-06-06)
surfaced four gaps. All four are now closed:

- **D1 — Closing trades excluded from markout.** A BTC trade with
  `realized_pnl != 0` has crystallized P/L; re-marking via BSM
  produces nonsense (the first run showed a fake +95% T+1d markout on
  a deep-ITM put closed near intrinsic). `compute_trade_markout` now
  short-circuits to `mark_source = "closing_trade_excluded"` on those
  trades. Opening trades unaffected.
- **D2 — Vol regime gets T+1d.** The original design skipped T+1d for
  vol_regime on the assumption that IV rank doesn't move materially
  overnight. The 2026-06-05 sell-off disproved this: TSLA IV rank
  jumped 16.57 → 33.07 in one session, confirming a CHEAP call from
  the day before. T+1d is now computed for vol_regime; T+45d stays
  skipped (IV rank mean-reverts by then and the signal is too noisy).
- **S1 — Multi-ticker macro archives supported.** Previously archives
  with comma-separated `ticker:` fields (e.g., `QQQ, SPY, IWM, DIA,
  VIX`) were skipped with `"multi-ticker — Phase 2"`. Now: one Call
  per ticker, all sharing the same `archive_path`. Multi-ticker
  archives force prose classification (skip the structure-list branch
  — book-review structures like `[csp, bull_put_spread, long_call]`
  apply to specific positions in the book, not every ticker
  uniformly).
- **S2 — `--validate-archive` CLI subcommand.** Scans the archive dir
  and reports per-file format issues: missing YAML frontmatter,
  missing required fields (`ticker` / `date` / `structures` / `tags`),
  unparseable date, missing `## Outcome / Lesson` section. Exits
  non-zero if any file has issues so it can be wired into CI.

## Architectural refactor (v0.3 — source separation)

The first real run (2026-06-06 weekly) exposed a deeper concept bug than the v0.2 D1-S2 fixes addressed: the framework was **conflating archive-derived "calls" with broker-derived "trades"** via `reconcile_calls_with_trades` and `discipline_quadrant`. SKILL.md hard rule #9 codifies the separation; the code now enforces it:

- **Deleted** (cross-stream joins): `reconcile_calls_with_trades`, `discipline_quadrant`, `DisciplineQuadrant`, `_trade_matches_call`, `DISCIPLINE_MATCH_WINDOW_DAYS`, the unified `aggregate_markout(calls, trades)`.
- **Split**: `aggregate_call_markout(call_markouts)` (Layer A only) + `aggregate_trade_markout(trade_markouts)` (Layer B only). Returned dicts contain no fields from the other layer.
- **Added** (broker integration): `parse_ib_trades(ib_response, window_start, window_end)` + `parse_futu_trades(futu_report_json, window_start, window_end)`. Both required every review.
- **Schema added**: `ReviewReport.trade_sources: list[str]` declares which brokers were pulled; `ReviewReport.cross_cut_advisory: list[dict]` carries Layer C judgment observations passed in by the caller.
- **Reconciliation tests removed**: `test_trade_matches_call_*`, `test_discipline_quadrant_classifies_each_call`, `test_reconcile_calls_with_trades_builds_full_map`. Replaced with `test_source_separation_no_reconcile_or_discipline_symbols_exported` as a regression guard.

**Frontmatter status semantics changed.** Archive `status:` field no longer carries broker-lifecycle meaning. The old `open | closed | executed` taxonomy implied trade state, which Layer A is forbidden to know. New values:

| Status | Meaning |
|---|---|
| `proposed` | Archive proposes a specific trade structure. Whether it was actually executed lives in Layer B (IB / Futu) — not here. |
| `analysis-only` | Diagnostic / thesis with no specific trade attached. Used for macro reads, vol-regime labels, pre-event setup notes. |
| `decision-pending` | Archive captures partial work; trader hasn't picked structure yet. |

Backward-compat: legacy archives with `status: open` / `closed` are read as `proposed` for extraction purposes. The framework does NOT use this field to infer Layer B information.

## Phase 1 limitations (current)

1. **Option marks for trade markout** use BSM with the IB `get_price_history`
   daily-close path (see footnote ¹ — TV opencli has no historical-bars
   command) + UW IV held flat at analysis date. This is a known approximation —
   accurate for ATM, less so for OTM tails or near-expiry contracts.
   `mark_source = "model"` is reported on every mark so the trader sees
   when to discount. IB `get_price_history` for option contracts is
   Phase 2; macmini DB is Phase 3.
2. **Directional verdict threshold** is fixed ±2% noise band, not
   vol-adjusted. Replace with ±0.5σ once N ≥ 50 directional calls.
3. **Closing-trade pairing not yet implemented.** D1 excludes closes
   from markout but doesn't pair them with their opens to attribute
   realized P/L to the original entry decision. Phase 2 would walk the
   trade list, match BTC/STC fills against earlier STO/BTO fills by
   (symbol, strike, expiry, right), and score the OPEN trade with
   final realized P/L.
4. **Open-trade detection is signal-based, not state-based.** D1 uses
   `realized_pnl != 0` as the open/close signal. This works for IB
   executions (the broker stamps realized P/L on closes) and Futu
   matched-pair closes (the parser attaches `pair.realizedPnl` to the
   close leg). Unmatched Futu legs land with `realized_pnl=None`,
   which is correct for opens but may miss isolated closes the matcher
   didn't pair.
5. **Layer C is purely opt-in.** The framework accepts `cross_cut_advisory`
   as caller input but does NOT generate observations itself. The trader
   (or LLM in advisory mode) writes them; the framework only renders +
   exposes them through action items. This is intentional under hard
   rule #9 — algorithmic A↔B joining is forbidden.

## How to invoke

Pure functions (consistent with other skill modules — `python -c`). Both brokers must be pulled per hard rule #9:

```bash
.venv/bin/python -c '
import json
from datetime import date
from pathlib import Path
from scripts.retrospective import (
    parse_ib_trades, parse_futu_trades,
    run_review, render_report,
)

# Layer B — pull BOTH brokers. PRIMARY: one xenon /blotter call (IB + Futu).
from scripts._clients.xenon import XenonClient
from scripts.retrospective import parse_xenon_blotter

window_start, window_end = date(2026, 5, 30), date(2026, 6, 6)
blotter = XenonClient().blotter()
trades = parse_xenon_blotter(blotter, window_start, window_end)

# FALLBACK (xenon unreachable): pull each broker and use the legacy parsers:
#   ib_response = {...}  # MCP get_account_trades period=DAYS_7
#   futu_report = json.load(open("/path/to/futu_report.json"))
#   trades = (parse_ib_trades(ib_response, window_start, window_end)
#             + parse_futu_trades(futu_report, window_start, window_end))

# Layer C — optional advisory observations (judgment-only).
advisory = [
    {"observation": "6/04 bearish call → hedge opened 6/05 = 1d lag",
     "layer_a_refs": ["macro-2026-06-04-premarket-snapshot.md"],
     "layer_b_refs": ["VIX AUG2026 20/30 call spread 2026-06-05"],
     "propose_action_item": False},
]

report = run_review(
    window="weekly", today=window_end,
    archive_dir=Path(".../private"),
    spot_history={...}, iv_rank_history={...},
    trades=trades, trade_sources=["IB", "Futu"],
    cross_cut_advisory=advisory,
    drafts_dir=Path(".../pitfalls/_drafts"),
)
print(render_report(report))
'
```

Orchestrator CLI (Phase 1 scaffold — data fetchers still need to be wired in by the trader):

```bash
# Weekly review, write back verdicts to archive Outcome sections, emit pitfall drafts
.venv/bin/python -m scripts.retrospective --window weekly

# Monthly review with pattern analysis
.venv/bin/python -m scripts.retrospective --window monthly

# Exploratory run — no archive edits, no drafts
.venv/bin/python -m scripts.retrospective --window monthly --no-writeback --no-pitfall-drafts

# Validate archive frontmatter / Outcome section format (S2).
# Exits non-zero on any issue → suitable for CI.
.venv/bin/python -m scripts.retrospective --validate-archive
```

The CLI is the second skill orchestrator-script (after
`manage_positions`). The same convention applies: argparse entrypoint,
talks to `_clients/` for live data, calls pure functions for compute,
writes output + optional email.
