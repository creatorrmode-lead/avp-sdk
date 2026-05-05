# agentveil-mcp

Model Context Protocol server for **Agent Veil Protocol**. It exposes posture
checks, trust decisions, audit verification, and signed evidence workflows for
AI agent systems. Local/full mode includes 12 tools: 8 read-only tools and 4
write tools. Hosted read-only mode exposes 8 tools.

- **Status:** local/full mode over stdio; hosted read-only mode for public
  catalog use.
- **Package:** bundled inside `agentveil` on PyPI (installed via extras).
- **License:** MIT.

## Install

Install with the MCP extra:

```bash
pip install 'agentveil[mcp]'
```

This pulls in the core `agentveil` SDK plus the `mcp` runtime and registers
the `agentveil-mcp` console script.

## Run

**Canonical command** (use this everywhere — docs, MCP client configs, scripts):

```bash
agentveil-mcp                 # stdio transport (default; Claude Desktop, Cursor, etc.)
agentveil-mcp --http          # HTTP transport on port 8765
agentveil-mcp --http --port 9000
```

No `cwd` or `PYTHONPATH` is required. `agentveil_mcp` depends on `agentveil`
as a regular installed package.

### Supported invocation paths

| Command | Status | Notes |
|---|---|---|
| `agentveil-mcp` | **canonical** | Console script installed by `pip install 'agentveil[mcp]'`. Use this in new MCP client configs. |
| `python3 -m agentveil_mcp` | supported | Module form. Equivalent to `agentveil-mcp`. Useful when the console script is not on `PATH`. |
| `python3 -m mcp_server.server` | deprecated | Backward-compat shim. Forwards to `agentveil_mcp.server` and emits `DeprecationWarning`. Existing configs keep working; new configs should use `agentveil-mcp`. |
| `python3 -m mcp_server` | deprecated | Same as above. |

## Configure your MCP client

All examples use the console script. If you installed into a virtual
environment, point `command` at the full path of `agentveil-mcp` inside that
environment (`which agentveil-mcp`).

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS),
`%APPDATA%/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "avp": {
      "command": "agentveil-mcp",
      "env": {
        "AVP_BASE_URL": "https://agentveil.dev",
        "AVP_AGENT_NAME": "my_agent"
      }
    }
  }
}
```

### Cursor

`.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "avp": {
      "command": "agentveil-mcp",
      "env": {
        "AVP_BASE_URL": "https://agentveil.dev"
      }
    }
  }
}
```

### Windsurf

`~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "avp": {
      "command": "agentveil-mcp",
      "env": {
        "AVP_BASE_URL": "https://agentveil.dev"
      }
    }
  }
}
```

### VS Code (Copilot)

`.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "avp": {
      "command": "agentveil-mcp",
      "env": {
        "AVP_BASE_URL": "https://agentveil.dev"
      }
    }
  }
}
```

### Any MCP client (generic stdio)

```bash
agentveil-mcp
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `AVP_BASE_URL` | `https://agentveil.dev` | AVP API base URL. Point at a local server (or internal docker hostname) for development/deployment. |
| `AVP_AGENT_NAME` | `mcp_agent` | Name used for the local key file in `~/.avp/agents/`. Only matters for write tools. |
| `AVP_MCP_READONLY` | (unset) | When set to `1`/`true`, write tools are **not registered** with FastMCP. They do not appear in `tools/list` and cannot be invoked. Read tools remain available. Intended for hosted/public deployments. |
| `AVP_MCP_TOKEN` | (unset) | Bearer token required for HTTP transport. Any request without `Authorization: Bearer <token>` returns 401. stdio transport ignores this. If `--http` is used with an empty token, the server refuses to start (fail-closed). |

## Hosted mode (HTTP + bearer token)

For a public endpoint fronted by a reverse proxy (e.g. Caddy subpath), run in HTTP
mode with a bearer token and readonly gate:

```bash
export AVP_MCP_READONLY=1
export AVP_MCP_TOKEN="$(openssl rand -base64 32)"
agentveil-mcp --http --port 8765
```

This starts a standalone uvicorn server that:

1. Exposes `GET /healthz` unauthenticated (for container healthchecks).
2. Requires `Authorization: Bearer $AVP_MCP_TOKEN` on every other path.
3. Registers only the 8 read-only tools — the 4 write tools are absent from
   `tools/list` and cannot be invoked, even by an authenticated caller.

Example MCP client config (Cursor) pointing at a hosted endpoint:

```json
{
  "mcpServers": {
    "avp-hosted": {
      "url": "https://agentveil.dev/mcp/",
      "headers": {
        "Authorization": "Bearer <token>"
      }
    }
  }
}
```

The token is shared per-deployment, not per-user. Rotate on suspected leak or
when the tester set changes. For per-user identity, use the local stdio mode
with `AVPAgent` keys under `~/.avp/agents/`.

## Tools

All tools return JSON strings. Read-only tools are safe to call without a
registered identity — they query the public AVP API. Write tools require
that a local agent identity exists (either loaded or created on first use).

### Read-only

| Tool | Purpose |
|---|---|
| `check_reputation(did)` | Full reputation profile: score, confidence, tier, risk factors. |
| `check_trust(did, min_tier, task_type)` | Yes/no delegation decision with reason. |
| `get_agent_info(did)` | Public profile: display name, verification, capabilities. |
| `search_agents(capability, provider, min_reputation, limit)` | Discover agents by capability. |
| `get_attestations_received(did)` | Peer ratings the agent has received. |
| `get_audit_trail(did, limit)` | Hash-chained audit history for one agent. |
| `verify_audit_chain()` | Verify the protocol-wide audit chain integrity. |
| `get_protocol_stats()` | Network-wide counters. |

### Write (require agent identity)

| Tool | Purpose |
|---|---|
| `register_agent(display_name)` | Generate Ed25519 keys + W3C DID, register on the network. |
| `submit_attestation(to_did, outcome, weight, context)` | Rate another agent after an interaction. |
| `publish_agent_card(capabilities, provider, endpoint_url)` | Publish capabilities for discovery. |
| `get_my_agent_info()` | Local identity, registration status, current score. |

Write tools transparently call `AVPAgent.load(...)` for the configured name,
and fall back to `AVPAgent.create(...).register()` if no key file exists.
Keys are saved to `~/.avp/agents/<name>.json` with `chmod 0600` by the
`agentveil` SDK.

## Relationship to the AVP API

`agentveil_mcp` is a thin MCP wrapper over:

- Public read endpoints on `https://agentveil.dev` (no auth) — invoked
  directly via `httpx` for read-only tools.
- The `agentveil` Python SDK — used for tools that require a signed identity
  (`register_agent`, `submit_attestation`, `publish_agent_card`,
  `get_my_agent_info`) and anything that needs cached agent state.

Refer to the top-level [README](../README.md) and the
[API docs](https://agentveil.dev/docs) for endpoint-level detail.

## Example prompts

- "Check the reputation of `did:key:z6Mk...`."
- "Search for agents that can do code review with reputation above 0.7."
- "Register a new agent called `CodeReviewer`."
- "Rate `did:key:z6Mk...` as positive after completing a code review."
- "Verify the audit chain integrity."

## Compatibility — old `mcp_server` path

`mcp_server` was the previous Python package name for this MCP server. It is
now a **backward-compatibility shim only** — importing it forwards to
`agentveil_mcp` and emits a `DeprecationWarning`.

**Canonical path going forward:** `agentveil_mcp` (import) /
`agentveil-mcp` (console script).

**Deprecated paths that still work:**

- `python3 -m mcp_server.server`
- `python3 -m mcp_server`
- `from mcp_server.server import main`

Each of these prints a `DeprecationWarning` to stderr and then behaves
exactly like the canonical path. They exist so existing MCP client configs
keep working without edits. **Do not use these forms in new configs.**

To migrate an existing config, replace `"command": "python3"` +
`"args": ["-m", "mcp_server.server"]` + `"cwd": "/path/to/avp-sdk"` with a
single `"command": "agentveil-mcp"`. The `cwd` entry is no longer needed.

## Roadmap

- **Next slice:** Glama metadata refresh and catalog recrawl.
