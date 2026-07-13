# Capability audit — 2026-07-13

**Question answered:** how far is this co-pilot from its maximum level at (1) regime
understanding, (2) result quality, (3) decision-useful depth — measured empirically, not
by opinion.

**Method:** three-agent campaign. (a) Full read of the private analysis archive (~49 docs):
extracted 52 falsifiable calls (`private/audits/2026-07-13/calls.json`) and scored every
substantive doc on a 7-dimension depth rubric. (b) Markout validation: real daily closes
(UW `get_ticker_close_prices`, cross-validated to the basis point against two archived 复盘
verdicts) joined against all calls → `private/audits/2026-07-13/markouts.json`.
(c) Data-source utilization sweep + live regime-snapshot demo. Scripts:
`2026-07-13-capability/scripts/`. Operational gaps are separate: `2026-07-13-gap-audit.md`.

---

## 1. Empirical findings

### 1.1 Markout scorecard (99 scored rows from 51 calls, 2026-06-03 → 2026-07-08)

| Slice | RIGHT | WRONG | NEUTRAL | Hit rate |
|---|---|---|---|---|
| Overall | 39 | 37 | 23 | **51.3%** |
| June | 22 | 26 | 15 | 45.8% |
| July | 17 | 11 | 8 | 60.7% (shorter elapsed horizons — suggestive only) |
| Index/macro | 29 | 19 | 18 | 60.4% |
| Single-name | 10 | 18 | 5 | 35.7% |
| bullish / bearish / range / neutral | — | — | — | 46.2% / 55.6% / 52.6% / 50.0% |

Unscoreable: 19 vol-regime calls (no historical IV-rank source exists — UW serves
snapshots only), RUT (all three fetch paths failed, documented), 6 vol calls proxy-scored
via realized vol (5/6 confirmed).

### 1.2 The ruler is broken — the framework cannot measure its own edge

The fixed ±2% verdict band, expressed in each ticker's realized σ at T+5:

| Band ≈ | Tickers | Effect |
|---|---|---|
| 0.08–0.21σ (far too tight) | VIX 0.08, MU 0.11, INTC 0.15, AMD/SOXX 0.17, SMH 0.21 | range calls fail almost by construction |
| 0.26–0.43σ (reasonable) | TSLA, NET, ADBE, NVDA, GS, GOOGL, LLY, QQQ/NDX | — |
| 0.66–0.99σ (too loose) | IWM 0.66, SPY 0.80, SPX 0.82, DIA 0.99 | range calls pass almost by construction |

The index-vs-single-name hit-rate gap (60.4% vs 35.7%) is therefore largely a scoring
artifact, and 4 of the 5 "worst misses" are VIX-under-a-range-framing band mismatches.
**Conclusion: current measured hit rates say more about the band than about call quality.**
The review-framework defers σ-scaling until N ≥ 50; this audit is the evidence to skip
that gate — the miscalibration is provable today.

### 1.3 Short-window markout is a coin flip

16 of 32 calls with both horizons available flip verdict between T+1 and T+21 (50%).
Grading must be horizon-matched to the call's own `horizon_days`; T+1 verdicts are noise
(confirms the archived NVDA case: T+1 +1.82% → T+5 −6.67%).

### 1.4 The prediction loop rarely closes

Before this audit, only ~6 of 52 calls carried a real grade; most Outcome sections are
"to be filled" or UNKNOWN placeholders. The corpus predicts prolifically and grades
sparsely. Additionally `entry-timing-log.jsonl` (749 records) is **synthetic parametric
sweep fixtures, not real usage** — the N ≥ 10 entry-timing calibration path has zero real
observations.

### 1.5 Depth rubric — June → July quality jump is real

7-dimension scoring across ~47 docs: provenance and regime characterization consistently
strong (2/2); competing-hypotheses and follow-through weak in June, climbing in July
(doctrine v1 visibly working — 07-02/07-03 docs score 12–13/14 vs June median ~9-10).

Five recurring decision-changing weaknesses (evidence in agent report; examples abridged):
1. **Stale load-bearing numbers presented as current** — June L3 fed UW indicator series
   6 weeks stale ("today estimated"); 4× mid-doc corrections on decision-critical values
   (VRP +14 → +3.7 flips sell-vs-buy-premium).
2. **Falling IV rank read as "not priced = safe," overriding a fired crowding check** —
   TSLA delivery: crowded long + falling IV into a known binary → −7.5% sell-the-news.
   Produced a wrong actionable lean before pitfall 06 codified it.
3. **Write-once-read-never** (see 1.4).
4. **Advice treadmill on concentration** — same single-name/beta-delta breach re-flagged
   in every review; remedy repeatedly unexecuted or late (one hedge executed 5× over the
   1.5% NLV budget cap, one day late; one conflict flagged 6/22 "self-healed by luck").
5. **Fragile single-source inputs carried into conclusions** — MU spot arrived as $1,064
   (vendor fallback bug, real ~$120); KRW/JPY mixing produced a phantom −$1.06M month and
   a false 83%-concentration alarm; frozen weekend feeds presented as live (→ pitfall 07).

Three strengths to preserve: provenance/honest-gap discipline; July's structured
competing-hypotheses habit; a self-auditing retrospective that git-verifies whether its
own improvement items actually shipped.

### 1.6 Data-source utilization — the co-pilot fights with one hand

- **UW:** trading pipeline uses 10 REST endpoints (IV/RV/skew/term/max-pain/GEX/greeks/
  dark-pool prints). Entirely unused: market tide (intraday reversal detection),
  per-expiry GEX (`get_greek_exposure_by_strike_expiry` — the all-expiry aggregate
  produces artifacts like a "12600 call wall"), flow alerts, dark-pool volume-price
  clusters, insider activity, short-interest/days-to-cover, seasonality, macro event
  calendar, options/stock screeners (~40+ tools).
- **xenon:** 12/19 endpoints wrapped; unused: `/attribution` (would replace hand-rolled
  markout math), `/orders/quote` (cheap conId quote refresh), `/contract/qualify`,
  `/ws-ticket` (the only streaming path — everything today is snapshot-poll).
- **FRED:** HY OAS wired; IG OAS + DGS10 documented in the docstring, zero call sites.
- **TV:** screener + alert fire-log capabilities unused.
- **No daily regime snapshot is ever persisted** — regime is re-derived ad hoc per
  analysis and discarded, so regime-conditioned learning (which regimes my calls work in)
  is structurally impossible today. This also makes the 19 vol calls permanently
  ungradeable: UW has no IV-rank history, so the only fix is archiving it yourself daily.

---

## 2. Roadmap to maximum level

Ordered by expected lift per unit effort; each item names the capability it unlocks.

### R1 — `regime_snapshot.py` daily archive (understand the regime) — HIGHEST LEVERAGE
Persist a daily JSONL regime state vector after the existing cron scan: SPX/QQQ/VIX
(+VIX9D/VVIX ratio), IV-rank cross-section over a fixed watchlist, term-structure state,
**per-expiry** GEX flip/walls, market-tide EOD summary, HY OAS + IG OAS + DGS10, yield
curve, event clock (next 14d), index-vs-single-name IV dispersion. ~1 new script + 2
client methods (`get_greek_exposure_by_strike_expiry`, tide). Unlocks: regime-conditioned
复盘, vol-call grading, dispersion signals, event-aware sizing. Without the archive,
"understand the regime better" stays unanswerable — you cannot condition on what you
never recorded.

### R2 — Fix the ruler (quality): σ-scaled, horizon-matched verdicts NOW
Replace ±2% with 0.5σ·√h per ticker (trailing 20d σ — the audit's σ table is the spec);
grade only at the call's own horizon. Small change in `retrospective.py`; evidence in
§1.2–1.3 justifies skipping the N ≥ 50 gate. Until this lands, every hit-rate number the
system produces is untrustworthy.

### R3 — Close the loop automatically (quality)
Wire retrospective's live fetchers (prices via UW closes — this audit's fetch path is the
prototype) + auto-grade weekly; add `regime:` frontmatter to every decision block from
that day's R1 snapshot. 46/52 ungraded calls is the single biggest feedback hole.

### R4 — Structural guards for the two proven reasoning failures (quality)
(a) Crowding × catalyst: falling IV rank into a known binary may never downgrade a fired
crowding flag (codify the TSLA −7.5% shape as a hard check, not prose). (b) Input
validation: cross-vendor spot sanity band (TV vs UW vs massive — catches the next MU
$1,064) + currency-normalization assert (catches the next KRW phantom).

### R5 — Escalating ledger (depth: kill the advice treadmill)
An action item resurfaced N≥3 times unexecuted becomes a forced decision block: execute
or retire-with-reason. Hedge-budget check moves pre-trade (currently retroactive only).

### R6 — Positioning/flow layer + candidate generation (depth)
Add to the single-name runbook: flow alerts, dark-pool volume-price clusters, insider
cluster, short-interest/DTC before any premium-sell. Add a weekly screener pass (UW
options screener / TV screener) so the co-pilot proposes candidates instead of only
responding to trader-named tickers.

### R7 — Real entry-timing calibration data (depth)
Start logging real gate evaluations at every actual entry decision (the current 749-line
log is synthetic fixtures); revisit thresholds at N ≥ 10 real observations, then build
the deferred backtest harness.

---

*Data: `private/audits/2026-07-13/{calls,prices,markouts}.json` (gitignored). Scripts:
`docs/audits/2026-07-13-capability/scripts/`. Price series cross-validated to the basis
point against two independently-computed archived verdicts. No fabricated values; all
gaps (RUT fetch, FRED proxy block, SPX skew empty) recorded as gaps.*
