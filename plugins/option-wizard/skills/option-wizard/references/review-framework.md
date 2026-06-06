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
| **Weekly review** | 7 calendar days back from invocation date | Micro-feedback loop: did this week's calls hold up? Did I follow them? | Per-call scorecard + discipline 4-quadrant + side-by-side markout table. No pattern aggregation (sample too small). |
| **Monthly review** | 30 calendar days back | Pattern detection: am I systematically wrong on a call type / ticker / regime? Where is execution leaking edge? | Everything from weekly + pattern analysis (hit rate by call type / ticker / regime) + action items proposing skill rule changes |

CLI:

```bash
.venv/bin/python -m scripts.retrospective --window weekly
.venv/bin/python -m scripts.retrospective --window monthly
.venv/bin/python -m scripts.retrospective --window monthly --no-writeback --no-pitfall-drafts
```

Default behavior writes verdicts back to source archive files and emits
pitfall draft candidates. Flags opt out.

## Layer 1 — Call extraction + markout

A "call" is one falsifiable claim extracted from an archived analysis.
The framework recognizes three types.

### Three call types

| Type | Encoded as | Direction signal | Truth source |
|---|---|---|---|
| **Directional** | Stock or index expected to move up/down/range over horizon | +1 bullish / −1 bearish / 0 range | TV historical spot |
| **Vol regime** | IV is RICH / CHEAP relative to RV | −1 RICH (expects vol compression) / +1 CHEAP (expects vol expansion) | UW IV rank time series + UW realized vol |
| **Structure** | Listed-options structure recommended (bull put spread, CSP, collar, …) | Implicit from structure's natural delta; encoded as expected sign of normalized P/L | Mark-to-market of the hypothetical structure on TV spot path; if trader entered, actual position mark |

**FCN / AQ / DQ structure recommendations are filtered out** at the
extraction stage — they live in PB workflows.

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
TV spot path using either:

- **Phase 1** (current): Black-Scholes-Merton mark with TV historical
  spot + UW IV at analysis date held flat (crude — flagged as
  `mark_source = "model"`)
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

## Layer 2 — Trade markout

For every actual fill within the window (IB executions + any secondary
broker trades documented in `private/trader-profile.md`):

| Trade type | `entry_basis` | `mark_T` source | Normalization denominator |
|---|---|---|---|
| Stock outright | `entry_fill × abs(qty)` | TV historical spot × qty | `entry_basis` |
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

## Layer 3 — Discipline scorecard (4-quadrant)

For each call, the framework checks whether the trader executed a
matching trade within **1-3 trading days** of the analysis date. A
match requires:

- Same ticker
- Same direction signal (long stock or long delta → matches bullish
  call; short stock or short delta → matches bearish call)
- For structure calls: structure type matches (CSP recommendation +
  trader sold a put on same ticker within 3 days → match; CSP
  recommendation + trader bought a call instead → no match)

| | Call CORRECT | Call WRONG |
|---|---|---|
| **Trader followed** | ✅ system + discipline both right | ⚠️ system wrong, not trader's fault |
| **Trader ignored** | ❌ discipline gap — trader missed a right call | ✅ trader's instinct saved them |

The framework reports the 4 counts + an `avg_markout` per quadrant.
If `avg_markout(ignored_correct) > avg_markout(followed_correct)`, the
trader is systematically filtering OUT the better calls — a discipline
failure mode worth flagging in action items.

## The key output — side-by-side markout table

This is the single most important table in the 复盘 output. It tells
the trader where edge is being created vs leaked:

| Horizon | Avg call markout | Avg trade markout | Δ (call − trade) | n_calls | n_trades |
|---|---|---|---|---|---|
| T+1d | … | … | … | … | … |
| T+5d | … | … | … | … | … |
| T+10d | … | … | … | … | … |
| T+21d | … | … | … | … | … |
| T+45d | … | … | … | … | … |

Diagnostic rules:

- **Δ > 0 systematically** → Analysis is right but trades aren't
  capturing it. Look for: structure mismatch (analysis says CSP, trade
  is a long call), timing lag (trader enters 5+ days after analysis,
  missing the move), undersizing (correct structure but token-size
  position).
- **Δ < 0 systematically** → Trader's live decisions outperform the
  case-prepared analysis. The analysis framework needs improvement;
  trader instinct is the better signal. Investigate which analyses were
  ignored profitably and capture the pattern.
- **Both call and trade markout < 0** → System-wide problem. Either the
  market regime has shifted away from the analytical model's
  assumptions, or there's a structural error in the analysis pipeline.

The same comparison runs per-ticker and per-regime in the monthly
review so the diagnosis can point at where the edge / leak concentrates.

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

Every archive file under `references/ticker/private/` has an empty
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

## Phase 1 limitations (current)

1. **Option marks for trade markout** use BSM with TV historical spot +
   UW IV held flat at analysis date. This is a known approximation —
   accurate for ATM, less so for OTM tails or near-expiry contracts.
   `mark_source = "model"` is reported on every mark so the trader sees
   when to discount. IB `get_price_history` for option contracts is
   Phase 2; macmini DB is Phase 3.
2. **Directional verdict threshold** is fixed ±2% noise band, not
   vol-adjusted. Replace with ±0.5σ once N ≥ 50 directional calls.
3. **Call extraction** uses YAML frontmatter + first-paragraph keyword
   heuristics. Manually-edited analyses without standard frontmatter
   are skipped with a log line. Phase 2 may add LLM-assisted extraction
   for non-standard archives.
4. **Match window for discipline scorecard** is fixed at 3 trading
   days. Some trader workflows (FCN counter-offer negotiation) have
   longer natural gaps; 复盘 doesn't capture those (correctly — FCN is
   out of scope).

## How to invoke

Pure functions (consistent with other skill modules — `python -c`):

```bash
.venv/bin/python -c '
from scripts.retrospective import (
    extract_calls, compute_call_markout, compute_trade_markout,
    aggregate_markout, render_report,
)
# orchestrator code here, with pre-fetched spot/iv/trade data
'
```

Orchestrator CLI (convenience entrypoint that fetches data via existing
`_clients/` and runs the full pipeline):

```bash
# Weekly review, write back verdicts to archive Outcome sections, emit pitfall drafts
.venv/bin/python -m scripts.retrospective --window weekly

# Monthly review with pattern analysis, no email
.venv/bin/python -m scripts.retrospective --window monthly --no-email

# Exploratory run — no archive edits, no drafts
.venv/bin/python -m scripts.retrospective --window monthly --no-writeback --no-pitfall-drafts
```

The CLI is the second skill orchestrator-script (after
`manage_positions`). The same convention applies: argparse entrypoint,
talks to `_clients/` for live data, calls pure functions for compute,
writes output + optional email.
