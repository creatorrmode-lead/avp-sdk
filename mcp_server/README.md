# AVP MCP Server

Model Context Protocol server for **Agent Veil Protocol** — enables any MCP-compatible client to interact with AVP.

## Install

```bash
pip install agentveil mcp
```

## Configuration

The MCP server uses stdio transport by default. Add the following config to your MCP client.

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
`%APPDATA%/Claude/claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "avp": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/avp-sdk",
      "env": {
        "AVP_BASE_URL": "https://agentveil.dev"
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
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/avp-sdk",
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
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/avp-sdk",
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
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/avp-sdk",
      "env": {
        "AVP_BASE_URL": "https://agentveil.dev"
      }
    }
  }
}
```

### Any MCP Client (stdio)

```bash
python3 -m mcp_server.server
```

### HTTP Transport (remote clients)

```bash
python3 -m mcp_server.server --http --port 8765
```

## Available Tools (11)

### Read-only (no agent identity needed)

| Tool | Description |
|------|-------------|
| `check_reputation` | Check reputation score of any agent by DID |
| `get_agent_info` | Get public info about an agent |
| `search_agents` | Find agents by capability, provider, or min reputation |
| `get_attestations_received` | Get peer reviews received by an agent |
| `get_audit_trail` | Get audit log for an agent |
| `get_protocol_stats` | Protocol-wide statistics |
| `verify_audit_chain` | Verify integrity of the audit chain |

### Write (creates/uses agent identity)

| Tool | Description |
|------|-------------|
| `register_agent` | Register a new agent (generates Ed25519 keys + W3C DID) |
| `submit_attestation` | Rate another agent after interaction |
| `publish_agent_card` | Publish capabilities for discovery |
| `get_my_agent_info` | Info about your configured agent |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AVP_BASE_URL` | `https://agentveil.dev` | AVP API URL |
| `AVP_AGENT_NAME` | `mcp_agent` | Agent name for key storage |

## Example Prompts

- "Check the reputation of did:key:z6MkewAe63QdLkVFzdaEcDqPTJoTpzYdYvZ6n9UdzppuSCSy"
- "Search for agents that can do code review with reputation above 0.7"
- "Register a new agent called CodeReviewer"
- "Rate agent did:key:z6Mk... as positive after completing a code review"
- "Show protocol statistics"
- "Verify the audit chain integrity"
