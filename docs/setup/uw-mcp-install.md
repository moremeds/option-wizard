# Installing the Unusual Whales MCP server

The option-wizard skill expects the UW remote HTTP MCP to be available in
Claude Code. Two ways to wire it.

## Prerequisites

- Active UW subscription with API access at https://unusualwhales.com/pricing?product=api
- API token from your UW account
- Token stored locally, never committed:

```bash
# .env (gitignored)
UW_API_KEY=<your token>
```

`.env.example` ships as the template.

## Endpoint

The authenticated MCP endpoint per UW's OpenAPI spec is:

```
https://api.unusualwhales.com/api/mcp
```

Auth is `Authorization: Bearer <API_TOKEN>`. Verified locally: `initialize`
returns `serverInfo: unusual-whales-public-api v1.0.0` and `tools/list` returns
real tool definitions.

## Option A — user-scope (recommended)

Registers the server globally for your Claude Code user account. Works in
every project, no env-var dance, no per-project config to maintain.

```bash
set -a; source .env; set +a
claude mcp add --transport http --scope user unusual-whales \
  https://api.unusualwhales.com/api/mcp \
  --header "Authorization: Bearer $UW_API_KEY"
```

Verify:

```bash
claude mcp list | grep unusual-whales
# unusual-whales: https://api.unusualwhales.com/api/mcp (HTTP) - ✓ Connected
```

The token is written into `~/.claude.json` (local, not synced). Restart Claude
Code to pick up the new server in the active session.

## Option B — project-scope (for repo cloners)

`/.mcp.json.example` ships as the template. Copy it locally and source your
`.env` before launching `claude` so `${UW_API_KEY}` resolves:

```bash
cp .mcp.json.example .mcp.json     # local copy is gitignored
set -a; source .env; set +a
claude
```

`.mcp.json` is gitignored so the live config (which may end up holding the
literal token) never leaks. If you'd rather skip the env-var dance, replace
`${UW_API_KEY}` in your local `.mcp.json` with the literal token — same risk
profile as `.env`, both stay local.

## Verify in-session

In a Claude Code session, ask: *"list available MCP tools for unusual whales"*.
The list should include the `mcp__unusual-whales__*` tools.

If they don't appear:
- `claude mcp list | grep unusual-whales` should show `✓ Connected`. If it
  shows `Pending approval`, run `claude` in the project dir and approve.
- Confirm the token by curl:
  ```bash
  curl -sS -X POST \
    -H "Authorization: Bearer $UW_API_KEY" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"p","version":"0"}}}' \
    https://api.unusualwhales.com/api/mcp
  ```
  A working token returns a JSON-RPC result with `serverInfo`. A 401 means the
  token is bad or expired.
- Confirm the REST path still works as a separate sanity check:
  ```bash
  set -a; source .env; set +a
  .venv/bin/pytest tests/integration/test_uw_smoke.py -v
  ```
