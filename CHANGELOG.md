# Changelog

All notable changes to option-wizard are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
pre-1.0 semver (minor = feature, patch = fix).

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
