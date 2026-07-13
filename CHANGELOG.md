# Changelog

All notable changes to option-wizard are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
pre-1.0 semver (minor = feature, patch = fix).

## [0.3.0] — 2026-07-13

### Added
- Decision doctrine v1 + review-loop upgrades U1–U6 (#30): aggression
  tiers (PROBE→EXCEPTIONAL, 5% NLV loss cap), competing hypotheses,
  crowding check, ≥2-structure comparison, 决策块 block.
- Pitfall 06: crowding-check × catalyst escalation — falling IV rank into
  a known binary must not downgrade a fired crowding flag (#31).
- Pitfall 07: index pre-market/overnight live-first gate — pull IB ES
  future + VIX index first; UW futures/tide are RTH-frozen (#33).
- Daily-scan failure alerting: unhandled scan errors now email the
  traceback (bypassing `--no-email`) and exit 1 instead of dying silently.
- CI runs pytest + ruff on every PR; repo-wide ruff clean-up (0 lint
  errors); `uv.lock` now tracked; `AGENTS.md` synced with hard rules 9–10.

### Changed
- Audit uses a quantity-conservation bucket check instead of the fixed
  $20 strike-width threshold (#29).
- Doc-coherence sweep: unified the 7-workflow count and the 7 AQ/DQ
  refusal red lines (R0–R6) across `SKILL.md`/`references`; xenon
  documented as the primary account-state / live-greeks source (IB MCP
  demoted to fallback).

## [0.2.0] — 2026-06-23

### Added
- **Open Knowledge Format (OKF) v0.1 alignment** of the `references/`
  knowledge base: OKF-standard YAML frontmatter on every framework, runbook,
  pitfall, and case study; reserved `references/index.md` (bundle root),
  `references/OKF.md` (conformance spec), and `references/log.md` (change
  history); per-directory `pitfalls/index.md` + `ticker/index.md`.
- **`scripts/case_studies.py`** — `find_case_studies()` parses the
  `Trade Case Study` frontmatter and ranks prior cases by ticker / structure
  (ticker hit `100` > structure overlap `10`). CLI:
  `python -m scripts.case_studies --ticker ORCL [--structure fcn] [--json]`.
  Reuses `retrospective.parse_archive_frontmatter` — no new dependency.
- `tests/test_case_studies.py` — 8 tests (hermetic `tmp_path` + real bundle).
- **xenon read-only Query API migration** (#27): broker + market-data
  acquisition (IB+Futu account state, live mid / L2 depth, live greeks /
  IV) moved to xenon; IB MCP demoted to fallback.
- **Macro-hedge empirical convexity framework** + regime gates (#24).
- **Workflow 2b — index premium selling**: CSP + RUT diagonal +
  entry-timing (#22).

### Changed
- Type vocabulary adds `Framework` / `Runbook` / `Reference` producer
  extensions alongside `Trading Pitfall` / `Trade Case Study` (kept
  byte-identical to the upstream trade-skills bundle for paste-compatibility).
- `SKILL.md` router: bundle entry-point pointer; the pattern-match row now
  points at the programmatic finder; fixed the add-a-pitfall row (it pointed
  at the now-stubbed README and called the index "empty").
- Directory `README.md` files slimmed to one-line GitHub stubs; canonical
  navigation moved to each directory's `index.md`.

## [0.1.0] — 2026-06-03

### Added
- Initial pre-release scaffold: the option-wizard skill (frameworks,
  runbooks, pitfalls, scripts, tests) and the fundamental-analysis skill.
