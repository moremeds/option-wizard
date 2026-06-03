# Install log

The skill is installed by symlinking it into the user's Claude skills
directory. This is a user-side action — run it once per machine:

```bash
ln -s /Users/chenxi/projects/option-wizard/plugins/option-wizard/skills/option-wizard \
      ~/.claude/skills/option-wizard
ls -l ~/.claude/skills/option-wizard
```

Expected: the symlink resolves to the project skill dir.

Then verify in Claude Code:

1. Open a new Claude Code session and ask: `list available skills`. The
   `option-wizard` skill should appear with the description from
   `SKILL.md` frontmatter.
2. Run the smoke prompt: `分析 ORCL FCN, PB 报 18% coupon, 75% strike, 6m 期限, 3m 观察`.
   The skill should orchestrate UW data fetch + fair_coupon analysis +
   8-item checklist output + bilingual counter-offer email.

If anything fails, record the failure below and fix before declaring
v1 acceptance.

## Install records

| Date | Machine | Result | Notes |
|------|---------|--------|-------|
| _yyyy-mm-dd_ | _hostname_ | _OK / FAIL_ | _what was observed_ |
