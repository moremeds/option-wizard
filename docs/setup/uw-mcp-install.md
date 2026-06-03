# Installing the Unusual Whales MCP server

The option-wizard skill expects the UW remote HTTP MCP to be available in
Claude Code. This project wires it at the **project level** via `.mcp.json`
(checked into git, key via env interpolation) rather than at the user level
in `~/.claude.json` — anyone who clones the repo gets the MCP automatically
once their `.env` is populated.

## Prerequisites

- Active UW subscription with API access at https://unusualwhales.com/pricing?product=api
- API token from your UW account
- Token stored in the project's `.env` (gitignored), never committed:

```bash
# .env (gitignored)
UW_API_KEY=<your token>
```

`.env.example` ships as the template.

## How it works

`/.mcp.json` (committed) registers the server:

```json
{
  "mcpServers": {
    "unusual-whales": {
      "type": "http",
      "url": "https://unusualwhales.com/public-api/mcp",
      "headers": {
        "Authorization": "Bearer ${UW_API_KEY}"
      }
    }
  }
}
```

`${UW_API_KEY}` is interpolated by Claude Code from the shell environment when
the session starts. Make sure your shell exports it (most shell-aware tools
read `.env` automatically; if not, source it manually):

```bash
set -a; source .env; set +a
claude
```

Restart Claude Code after the first time you add the env var. UW tools
appear with the `mcp__unusual-whales__*` prefix.

## Verify

In a Claude Code session, ask: *"list available MCP tools for unusual whales"*.
The list should include `iv-rank`, `gex`, `skew`, etc.

If the tools do not appear:
- Check `.mcp.json` is valid JSON: `python -m json.tool .mcp.json`
- Check the env var is exported in the shell Claude Code was launched from: `echo $UW_API_KEY`
- Check the API key is active in the UW dashboard
- Run the live REST smoke as a parallel check:
  `set -a; source .env; set +a; .venv/bin/pytest tests/integration/test_uw_smoke.py -v`
