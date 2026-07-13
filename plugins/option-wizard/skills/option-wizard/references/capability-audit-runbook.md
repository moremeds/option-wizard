# Capability-audit runbook — 复跑验证流程

**Trigger:** "run capability audit" / "审计这个 skill 的能力" / quarterly (first
weekend of Jan/Apr/Jul/Oct), or after any major framework change (new doctrine,
new workflow, scoring change). First executed 2026-07-13; that audit's outputs
are the baseline every future run compares against.

**Question it answers:** is the co-pilot's analysis quality improving, measured
against realized market data — not against its own opinion of itself.

**Separation from 复盘:** W6 复盘 grades individual calls on a weekly/monthly
cadence. This audit grades **the system**: scoring-band calibration, corpus-wide
bias, depth-rubric trend, data-source utilization, and whether prior audit
action items landed. It reads 复盘 output; it never replaces it. Hard rule #9
(archive vs broker source separation) applies here exactly as in 复盘.

---

## Phase 1 — Call extraction (archive → calls.json)

Read every analysis doc in `references/private/{ticker,market,review}/` (add
`archive/` subtree for the quarterly run). Extract **every falsifiable call**
into `private/audits/<YYYY-MM-DD>/calls.json`:

```json
{"id": "t01", "source_file": "...", "as_of_date": "YYYY-MM-DD",
 "ticker": "NVDA", "direction": "bullish|bearish|neutral|range|vol_up|vol_down",
 "spot_at_call": 0.0, "horizon_days": 21, "structure_recommended": "...",
 "thesis_oneliner": "...", "regime_claim": "...", "prior_verdict": null}
```

Rules learned 2026-07-13:
- The audit schema is deliberately broader than the production `calls:`
  frontmatter (`retrospective.Call` = call_type + numeric direction −1/0/+1).
  Fixed mapping when scoring: `bullish`→directional +1, `bearish`→directional
  −1, `range`/`neutral`→directional 0, `vol_up`/`vol_down`→vol_regime ±1.
- Multi-ticker macro calls: emit one row per ticker, but **never** let VIX
  inherit an equity direction label (VIX is mechanically inverse — tag it
  `vol_up`/`vol_down` or exclude).
- Synthetic data is excluded and said so: check whether any JSONL log is test
  fixtures before counting it as usage (the 749-row `entry-timing-log.jsonl`
  was a parametric sweep, not real decisions).
- Completeness beats precision: a dated directional sentence with a testable
  implication is a call even without a 决策块.

## Phase 2 — Price truth + markout computation

1. Pull daily closes for every extracted ticker, call-window start → last full
   trading day. Source ladder: `XenonClient.daily_closes` (programmatic, once
   the 2026-07-13 regime-engine plan lands) → UW MCP close-price series →
   massive MCP → TV reader. (TV stays canonical for LIVE spot per hard rule
   #2; historical grading uses broker/vendor daily bars.) Failed fetches stay
   failed with what was tried (2026-07-13: RUT failed all available paths —
   recorded, not faked).
2. **Cross-validation gate (mandatory):** reproduce ≥2 archived 复盘-computed
   markouts from the fresh series before trusting it. Standing baselines
   (tolerance ±0.01pp on each return): **t01** NVDA as-of 2026-06-03 →
   T+1 +1.82%, T+5 −6.67%, T+10 −4.70%; **t04** TSLA as-of 2026-06-04 →
   T+1 −1.24% (both archived in `private/audits/2026-07-13/markouts.json`
   with their source files). Later audits may add newer baselines but never
   drop these two. If they don't reproduce, stop and diagnose the price
   source before quoting any aggregate.
3. Compute per call: T+1/T+5/T+10/T+21 returns, verdict per the **current**
   scoring rules in `scripts/retrospective.py` (σ-scaled once landed; the
   2026-07-13 audit used the then-current ±2% and proved it miscalibrated),
   plus σ-context = move ÷ (daily σ × √h).
4. Reuse/adapt `docs/audits/2026-07-13-capability/scripts/compute_markouts.py`
   — do not rewrite from scratch.
5. Outputs: `private/audits/<date>/{prices,markouts}.json`.

## Phase 3 — Scorecard + calibration check

Report, with counts:
- Hit rate overall and by: direction, month, single-name vs index/macro, and
  (once regime tags exist) by regime state at call time.
- **Band calibration table:** per ticker, the verdict band expressed in σ-units
  at T+5. Any ticker where the band is <0.25σ or >0.6σ → scoring-rule action
  item.
- **T+1 vs T+21 verdict flip rate** (2026-07-13 baseline: 50% — any verdict
  quoted at a shorter horizon than the call's own is noise).
- Cross-check computed verdicts vs archived `prior_verdict`; disagreements are
  either horizon mismatches (fine, note them) or data conflicts (stop, debug).
- Unscoreable calls stay unscoreable with the reason class (no historical IV
  rank, fetch failure, not-a-ticker).

## Phase 4 — Depth rubric (analysis quality trend)

Score each substantive doc 0–2 on the seven dimensions (baseline scores in the
2026-07-13 audit):
a) layer coverage · b) competing hypotheses · c) regime characterized with
measured values vs adjectives · d) falsifiability (levels + dates) ·
e) provenance/timestamps · f) scenario & sizing logic · g) follow-through
(did anything later read this doc).

Deliverable: median by month vs prior audit — is the corpus getting deeper or
just longer? Plus the recurring-weakness list with quotes, checked against the
prior audit's list: which weaknesses closed, which persist (a weakness that
survives two audits becomes a pitfall/doctrine candidate).

## Phase 5 — Utilization + flywheel health

- Data-source utilization delta vs prior audit: endpoints newly adopted,
  still-unused high-value ones (baseline list: 2026-07-13 audit §1.6).
- Flywheel throughput: pitfall drafts pending in `_drafts/` and their age;
  prior audit's action items — landed or stalled (verify via `git log`, the
  monthly skill audit's technique)?
- Automation health: `grep -c "Traceback" ~/.config/option-wizard/daily.log`
  since last audit; CI status; grading cadence actually happening?
- `regime:` frontmatter coverage: count archives dated after the regime-log's
  first line that lack `regime:` frontmatter — the convention (SKILL.md
  archive conventions) decays unless someone counts.

## Phase 6 — Write-up + comparison

Write `docs/audits/<YYYY-MM-DD>-capability-audit.md` in the same structure as
the 2026-07-13 baseline (findings → roadmap), opening with a **delta table vs
the previous audit**: hit rate, flip rate, band-calibration violations, depth
median, utilization count, flywheel backlog. Scripts → 
`docs/audits/<date>-capability/scripts/` with README; data → 
`private/audits/<date>/` (verify gitignore: `git check-ignore private/audits/<date>/calls.json`).

## Hard gates (non-negotiable, all inherited from SKILL.md hard rules)

1. Every price traces to a real API response; failed fetch ≠ estimated value.
2. Phase 2 cross-validation gate passes before any aggregate is quoted.
3. Personal NLV/cash never appears in the tracked audit doc.
4. Verdicts only at horizons the data supports — no extrapolation past the
   last trading day (`horizon_incomplete` instead).
5. The audit doc states its own gaps (what was unscoreable and why) — an audit
   that claims full coverage is presumptively wrong.

## Orchestration note

The 2026-07-13 baseline ran as three parallel subagents (extraction+rubric /
utilization+regime / markout) with the orchestrator synthesizing — ~30 min
wall-clock. Single-session sequential works too; Phases 1→2→3 are strictly
ordered, 4 and 5 are independent of 2–3 and can run anytime.
