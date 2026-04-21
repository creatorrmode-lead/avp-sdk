"""
DEPRECATED: `mcp_server` has been renamed to `agentveil_mcp`.

This package is kept as a compatibility shim so existing MCP client configs
using `python -m mcp_server.server` or `python -m mcp_server` continue to work.
New code should import from `agentveil_mcp` and new configs should use the
`agentveil-mcp` console script.
"""
import warnings

warnings.warn(
    "The 'mcp_server' package is deprecated and will be removed in a future "
    "release. Use 'agentveil_mcp' (or the 'agentveil-mcp' console script) instead.",
    DeprecationWarning,
    stacklevel=2,
)
