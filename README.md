# Option Wizard

> [!WARNING]
> This project is for educational and informational purposes only. Nothing here constitutes financial advice. Always do your own research and consult a qualified financial advisor before making investment decisions.

A personal Claude Code plugin marketplace housing one options-trading skill — FCN private-bank quote defense, single-name option income recommendations, SPX macro hedge sizing, and Interactive Brokers order execution with defined-risk guardrails. Layout follows the [`himself65/finance-skills`](https://github.com/himself65/finance-skills) convention.

## Quick Start

### Claude Code — Install the plugin

```bash
npx plugins add moremeds/option-wizard
```

### Claude Code — Install just the skill

```bash
npx skills add moremeds/option-wizard
```

### Other agents

```bash
npx skills add moremeds/option-wizard -a <agent-name>
```

### Local development install (from a clone)

```bash
git clone https://github.com/moremeds/option-wizard.git ~/projects/option-wizard
ln -s ~/projects/option-wizard/plugins/option-wizard/skills/option-wizard \
      ~/.claude/skills/option-wizard
```

## Available Skills

### Option Wizard (`option-wizard`)

Personal options-trading assistant covering income structure picks, structured-product (FCN/ELN) defense, macro hedge sizing, and live IB execution. Triggers on Chinese or English prompts naming a ticker in a trading context or pasting a PB quote — see `plugins/option-wizard/skills/option-wizard/SKILL.md`.

| Skill | Description |
|---|---|
| [option-wizard](plugins/option-wizard/skills/option-wizard/) | Options trading knowledge base — 8-layer analysis runbook + regime × structure matrix + UW/TV/IB orchestration + FCN counter-offer email generation + defined-risk audit. Lazy-loaded. |

## Data sources

- **Unusual Whales** REST + MCP — vol surface, GEX by strike/expiry, max pain, dark pool, IV/skew (required, see `docs/setup/uw-mcp-install.md`)
- **TradingView desktop app** via [`opencli`](https://github.com/jackwener/opencli) — chart state, news, quote (optional but recommended for the 4-signal bullish-conviction veto check)
- **Interactive Brokers Gateway** via `ib_insync` — positions, account, order submission (required for execution paths)

## License

MIT
