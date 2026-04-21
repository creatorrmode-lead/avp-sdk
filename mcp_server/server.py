"""
DEPRECATED: `mcp_server.server` has been renamed to `agentveil_mcp.server`.

This module is a compatibility shim. All names are re-exported from
`agentveil_mcp.server`. Importing this module emits a DeprecationWarning.

Existing MCP client configs using `python -m mcp_server.server` continue
to work but should migrate to the `agentveil-mcp` console script or
`python -m agentveil_mcp`.
"""
import warnings

warnings.warn(
    "Importing 'mcp_server.server' is deprecated. Use 'agentveil_mcp.server' "
    "or the 'agentveil-mcp' console script instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agentveil_mcp.server import *  # noqa: F401,F403
from agentveil_mcp.server import main, mcp  # noqa: F401

if __name__ == "__main__":
    main()
