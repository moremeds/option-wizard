---
type: Changelog
title: option-wizard Knowledge Base — Change Log
description: Chronological history of the option-wizard reference bundle — frameworks, runbooks, pitfalls, and case studies added over time.
tags: [log, changelog, history]
timestamp: 2026-07-02T02:20:29Z
---

# Change Log

OKF reserved `log.md` — chronological history of this knowledge bundle, most recent first. Seeded from git history; append a dated entry whenever you add or materially revise a concept (see [`OKF.md`](OKF.md) conformance checklist). For the full commit-level history, `git log -- plugins/option-wizard/skills/option-wizard/references/`.

## 2026-07-03 — Pitfall 06 + crowding-check × catalyst escalation rule

TSLA Q2 delivery print (2026-07-02) beat consensus by 18% — and every
public bull estimate — yet the stock fell 7.5%, its worst day in a year
("buy the rumor, sell the news"). The same-day pre-print analysis had
already fired the crowding check (dealer gamma / price action / flow all
one-sided bullish), but a falling IV rank into the print was read as a
standalone "market isn't pricing risk" signal that overrode the crowding
flag instead of escalating it — the two questions (does the options
market charge event premium vs. will the crowd's one-sided position get
sold) got collapsed into one.

- Added [`pitfalls/06-crowded-into-catalyst-iv-rank-trap.md`](pitfalls/06-crowded-into-catalyst-iv-rank-trap.md).
- `decision-doctrine.md` §Crowding check gained a **mandatory escalation**
  sub-rule: crowding check fired + a scheduled binary catalyst inside the
  analysis window → IV-rank / term-structure trend can no longer override
  the crowding flag; requires a two-sided reaction scenario table
  (beat-and-held / beat-and-sold / miss) naming the crowding-driven
  downside case before the IV evidence feeds into the bull case.

## 2026-07-02 — Re-review fixes + 决策块 shadow trade

Re-reviewed PR #30 after the first live end-to-end test (TSLA, U1–U6
already merged into the branch) and found two doc-example bugs plus a
gap the trader flagged directly:

- **F1** — SKILL.md's and `retrospective.py`'s own `calls:` worked
  examples had an extra `|` (8 fields instead of 7); an archive copying
  the example verbatim got the call silently dropped to
  `skipped_archives` (caught it firsthand — yesterday's TSLA archive was
  written from this exact example and rejected by the real parser).
  Fixed both examples; added `test_skill_md_calls_example_parses_without_malformed_reasons`
  / `test_retrospective_module_calls_docstring_example_parses` in
  `tests/test_retrospective.py` so a future doc edit can't silently
  reintroduce either bug (parses the literal example string out of the
  source file and feeds it through `parse_structured_calls`).
- **F2** — the NVDA doc example paired `direction=-1` with
  `structure=bull_put_spread` (`STRUCTURE_DIRECTION` says `+1`) — copying
  it verbatim scores the call backwards. Swapped to `bear_call_spread`.
  Same regression test checks direction/structure consistency against
  `STRUCTURE_DIRECTION` for every entry in the doc example.
- **Shadow trade** — `decision-doctrine.md`'s 决策块 gained a **概率分布**
  (rough probability per competing hypothesis, Phase C) and **赔率**
  (gain vs max loss) field, plus a mandatory shadow-trade requirement:
  whenever 我的行动 is throttled below what 当前判断 supports (NO_TRADE,
  a margin-constraint gate, etc.), the block must still name the
  structure/strikes/expiry/tier the evidence would have justified. This
  closes the TSLA 2026-07-02 gap where dealer gamma / term structure /
  flow all read bullish but an account-margin constraint forced
  NO_TRADE — without the shadow trade, that underlying judgment never
  enters markout scoring. No `calls:` schema change needed — the shadow
  trade's direction is what the archived entry already carries, with
  `tier: NO_TRADE` recording that it wasn't acted on.

## 2026-07-02 — Review-loop upgrade (U1–U6)

Live-tested the day-old decision-doctrine (below) on NVDA + macro
analyses, then ran the first full June monthly 复盘 — surfacing six
distinct fix targets, closed in dependency order (U1 → U6):

- **U1** (`fix(retrospective)`, `9aee56f`) — four Layer-mechanics bugs
  the June run tripped: `write_back_outcome` / pitfall-draft filenames
  keyed by archive-stem only (multi-ticker archives lost all but the
  first call's verdict / collapsed WRONG drafts into one file);
  `parse_futu_trades` gained `min_lookback_days` (a `--range 1m` report
  sign-flipped June's realized P&L, −$9.9k vs the true +$9.7k, by
  dropping 39 cross-month pairs); `Trade.currency` + `realized_pnl_by_currency`
  (IB returns KRW `realized_pnl` unconverted, polluting a naive USD sum).
- **U2** (`feat(retrospective)`, `eeff01c`) — structured `calls:`
  frontmatter (`ticker|type|dir|structure|tier|crowding_flags|opposite_case_first`)
  takes precedence over prose keyword classification, carrying the
  decision-doctrine `tier` prose can't recover; `detect_pattern_anomalies`
  now reports `n_scored` alongside `n` and gates grouping thresholds on
  it (closes an overfitting trap: "TSLA 0% over 7 calls" meant 1 scored
  call and 6 still UNKNOWN); new by-tier hit-rate breakdown.
- **U3** (`feat(ledger)`, `8b57a0b`) — `scripts/ledger.py`: a JSONL
  decision ledger for action items that don't close the loop in-session
  (archived analyses found a "should roll down" call still open a week
  later, rescued only by a rally). Surfaces at the top of the daily
  `manage_positions` scan and 复盘's own report.
- **U4** (`fix(term-curve)`, `5f68d63`) — `atm_iv_from_chain_rows`
  auto-pivots the actual `get_chains_for_expiry` per-contract row shape
  (every live caller this session hand-wrote the same pivot first); new
  `atm_iv_by_expiry_from_term_structure` (one `iv_term_structure` call
  covers a ticker's full listed term structure, cheaper than a
  chain-pull per held expiry); VIX9D/VVIX IB contract ids documented
  (TV's exchange-prefix path fails for both).
- **U5** (`feat(retrospective)`, `b52fcc0`) — `save_review_report`
  auto-archives the rendered 复盘 report by default (a 2026-06-14 weekly
  review drove real code fixes but was never saved — permanently
  unrecoverable beyond the commit message); documents the two-pass
  monthly cadence (facts pass at month-start, T+21-matured verdict
  backfill pass ~3 weeks later — a monthly review run on the 1st can't
  score most of the month's directional calls regardless of data quality).
- **U6** (`feat(retrospective)`, `8ec191f`) — `flag_hedge_cost_outliers`:
  retroactive reverse cost-cap check on Layer B BUY option legs that
  read as long insurance, catching hedges placed manually (bypassing
  `build_macro_hedge`'s `max_annual_cost_pct` enforcement entirely —
  the mechanism behind a real ~8% NLV VIX call spread the 2026-07-01
  monthly skill audit found).

## 2026-07-02 — Decision doctrine

- Added [`decision-doctrine.md`](decision-doctrine.md): reasoning phases (competing hypotheses → disconfirmation → ≥2-structure comparison), aggression tiers with 9 alignment conditions (max loss hard-capped at **5% NLV at every tier**, per trader decision), mandatory contrarian crowding check, dynamic risk re-rating, 12-class missing-data taxonomy, adversarial QC checklist, and the 决策块 final decision block. Distilled from the trader's "ultimate market-structure agent" prompt; conflicts resolved in favor of hard rules #3 / #8 / #9 (fixed skeletons and 复盘 source separation stay).
- `SKILL.md`: new hard rule #10 (decision doctrine) + router row; `analysis-runbook.md` Layer 6 now runs doctrine phases C–F (hypotheses, crowding check, structure comparison, tier-based sizing) and closes with the 决策块.
- `review-framework.md`: four layer-mapped scoring dimensions (thesis / structure / process = Layer A, execution = Layer B, joins = Layer C judgment-only); pitfall promotion lifecycle (`OBSERVATION` → `CANDIDATE` → `ACTIVE` → `RETIRED`) with overfitting gate; removed the v0.2 "Discipline 4-quadrant" leftover from the output structure (contradicted hard rule #9).

## 2026-06-22 — OKF v0.1 alignment

- Adopted [Open Knowledge Format v0.1](OKF.md): added OKF-standard frontmatter (`type`, `title`, `description`, `tags`, `timestamp`) to every framework, runbook, pitfall, and case study, preserving each file's existing prose body.
- Added the reserved [`index.md`](index.md) bundle root, per-directory `index.md` indexes (with one-line `README.md` stubs), [`log.md`](log.md), and the [`OKF.md`](OKF.md) conformance & mapping document.
- Defined the option-wizard type vocabulary: `Framework` / `Runbook` / `Reference` extensions alongside upstream-identical `Trading Pitfall` / `Trade Case Study`.
- Pattern and `Trading Pitfall` / `Trade Case Study` types kept byte-identical to the upstream [trade-skills](https://github.com/himself65/trade-skills) bundle for paste-compatibility.

## Pre-OKF history (from git)

The bundle predates the OKF naming; these are the concept-level milestones reconstructed from git history.

- **2026-06-18** — `review-framework.md` / `workflows-overview.md` / `data-sources.md` updated (xenon Query API migration, freshness ladder).
- **2026-06-15** — `macro-hedge-convexity.md` empirical convexity framework + regime gates; pitfall 04 (ER range-structure strike staleness) + pitfall 05 (macro-print no post-event IV crush); `strategies.md` macro-hedge trigger heuristics.
- **2026-06-10** — `index-premium-selling.md` (Workflow 2b: CSP + RUT diagonal + entry timing); `aq-dq-framework.md`; pitfall 01 (VIX options track futures) + pitfall 03 (ratio backspreads not tail hedges).
- **2026-06-08** — `analysis-runbook.md` (8-layer ticker-analysis spine).
- **2026-06-06** — pitfall 02 (PB AQ implicit yield).
- **2026-06-05** — `ticker/aq-example-case.md` (AQ framework worked example).
- **2026-06-04** — `price-action-framework.md`.
- **2026-06-03** — Foundation: `strategies.md`, `gamma-framework.md`, `fcn-framework.md`, `execution.md`, `data-sources.md`, `ticker/orcl-2026-06-fcn.md`, pitfall/case-study templates.
