# option-wizard

Personal Claude Code skill: FCN private-bank quote defense, single-name option income recommendations, SPX macro hedge sizing, and Interactive Brokers order execution with defined-risk guardrails.

## Install

```bash
ln -s ~/projects/option-wizard/plugins/option-wizard/skills/option-wizard \
      ~/.claude/skills/option-wizard
```

## Use

In Claude Code: mention a ticker in a trading context, paste a PB FCN quote, or ask to review positions. See `plugins/option-wizard/skills/option-wizard/SKILL.md` for triggers.

## Layout

- `plugins/option-wizard/skills/option-wizard/SKILL.md` — skill entry
- `plugins/option-wizard/skills/option-wizard/scripts/` — Python helpers
- `plugins/option-wizard/skills/option-wizard/references/` — domain reference docs
- `docs/specs/` — design specification
- `docs/plans/` — implementation plan
- `tests/` — pytest suite

## Spec

See `docs/specs/2026-06-03-option-wizard-design.md`.
