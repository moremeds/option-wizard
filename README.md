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
cd ~/projects/option-wizard

# Symlink the skill into your Claude Code skills dir
ln -s "$PWD/plugins/option-wizard/skills/option-wizard" \
      ~/.claude/skills/option-wizard

# (Optional) Customize the trader profile — see next section
cp docs/setup/trader-profile.md.example private/trader-profile.md
$EDITOR private/trader-profile.md
```

## Customize for your trading style

The skill ships with universal hard rules (defined-risk only, source
discipline, freshness gate, layer-coverage table). Anything that varies
by trader — broker setup, language preference, macro hedge budget,
response style — lives in a **gitignored** local profile that
`CLAUDE.md` `@`-includes when present.

```bash
mkdir -p private/
cp docs/setup/trader-profile.md.example private/trader-profile.md
$EDITOR private/trader-profile.md
```

What goes in the profile:

- Your trader style (mega-cap tech / income / macro overlay / etc.)
- Primary + secondary brokers and how to pull positions
- Language and tone preferences
- Macro hedge budget (default 1.5% NLV)
- Watchlists, blackout dates, prohibited strategies

The file is **never committed** — `private/` is in `.gitignore`. Your
NLV, positions, and any personalization stay on your machine. The
skill runs fine without it using the defaults in `CLAUDE.md`.

## Available Skills

### Option Wizard (`option-wizard`)

Personal options-trading assistant covering income structure picks, structured-product (FCN/ELN) defense, macro hedge sizing, and live IB execution. Triggers on Chinese or English prompts naming a ticker in a trading context or pasting a PB quote — see `plugins/option-wizard/skills/option-wizard/SKILL.md`.

| Skill | Description |
|---|---|
| [option-wizard](plugins/option-wizard/skills/option-wizard/) | Options trading knowledge base — 8-layer analysis runbook + regime × structure matrix + UW/TV/IB orchestration + FCN counter-offer email generation + defined-risk audit. Lazy-loaded. |

## Data sources

- **xenon Query API** (read-only, personal instance) — **primary** for account state (IB *and* Futu: `/portfolio`, `/futu/portfolio`, `/orders`, `/blotter`), live mid/NBBO/L2 liquidity (`/market-depth`), and live per-contract greeks/IV (`/options/greeks`). No client-side BSM — greeks always come from a live broker quote.
- **Unusual Whales** REST + MCP — vol surface, GEX by strike/expiry, max pain, dark pool, IV/skew, and analytical-mode chain mid/IV/greeks (required, see `docs/setup/uw-mcp-install.md`)
- **TradingView desktop app** via [`opencli`](https://github.com/jackwener/opencli) — chart state, news, quote, **the only source for price + technicals** per SKILL.md hard rule #2 (required for L3 of any ticker analysis)
- **Interactive Brokers Gateway** via `ib_insync` — order submission always routes here; also the fallback for account state / live greeks / spot when xenon is unreachable.

The invariant (from `CLAUDE.md` §"Data source order"): **xenon** = state + live mid/liquidity + live greeks; **UW** = options-analytics aggregates + analytical-mode greeks; **TV** = spot/technicals; **ib_insync** = execution + fallback greeks.

Private-bank structured-product quotes (Accumulator/Decumulator, "AQ"/"DQ") are evaluated separately via `references/aq-dq-framework.md` — 7 refusal red lines, fair-value breakdown with provenance, and a bilingual counter-offer email; never routed through IB.

## Position analysis: bring your own broker connector

The position-review workflow (`scripts.manage_positions`,
`scripts.defined_risk_audit`, 21-DTE scan, concentration / Greeks rollup)
is **broker-agnostic in implementation** but requires user-provided
connectors to actually pull positions. **The skill does not ship with
any broker auto-discovery** — you must wire up whatever brokers you use:

- **Interactive Brokers** — primary pull is the xenon Query API
  (`XenonClient.ib_portfolio()`); if you don't run xenon, fall back to
  the Anthropic IBKR MCP connector, which calls `get_account_summary`,
  `get_account_positions`, `get_account_orders`, `get_account_trades`.
  Configure the connector in your Claude Code MCP settings (or via
  claude.ai's MCP marketplace).
- **Futu (Moo Moo)** — primary pull is the xenon Query API
  (`XenonClient.futu_portfolio()`); if you don't run xenon, fall back to
  the OpenD daemon + futu-api Python wrapper, or a third-party CLI (e.g.,
  [`portfolio-analyser`](https://github.com/moremeds/portfolio-analyser)
  for the `ft --range 1y --rerun` JSON export; `--rerun` bypasses the
  ISO-week trade cache so a review never silently reads stale fills).
  Document your chosen pull command in `private/trader-profile.md`.
- **Tastytrade / Schwab / E*TRADE / IBKR Web API / Robinhood / etc.** —
  not built in. Bring your own CLI, MCP server, or Python wrapper that
  outputs positions in a JSON-translatable form, and reference the pull
  command from `private/trader-profile.md`.

For every secondary broker, your pull output must be **translatable to
the IB-shape positions dict** (`contract_description` / `position` /
`market_price` per row). The skill's audit + scan scripts run on that
shape — they don't care which broker it came from.

If no broker is configured, the position-review workflow can't run.
The other workflows (single-ticker analysis, index/macro analysis, FCN
evaluation) only need UW + TV and are unaffected.

## License

MIT
