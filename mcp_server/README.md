# DEPRECATED — moved to `agentveil_mcp/`

The canonical AVP MCP server has been renamed to **`agentveil_mcp`**. See the
new README: [../agentveil_mcp/README.md](../agentveil_mcp/README.md).

## Migration

Old command (still works, emits `DeprecationWarning`):
```
python3 -m mcp_server.server
```

New canonical command (installed as a console script):
```
agentveil-mcp
```

Or equivalently:
```
python3 -m agentveil_mcp
```

### Update your MCP client config

Replace:
```json
{
  "command": "python3",
  "args": ["-m", "mcp_server.server"],
  "cwd": "/path/to/avp-sdk"
}
```

With:
```json
{
  "command": "agentveil-mcp"
}
```

The `cwd` entry is no longer needed because `agentveil-mcp` is an installed
console script and `agentveil_mcp` imports `agentveil` as a regular package
dependency.

## Compatibility window

The `mcp_server` package will continue to forward to `agentveil_mcp` for at
least one minor release. It will be removed in a future version.
