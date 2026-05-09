# MCP Proxy Operations

## Downstream Lifecycle

The MCP proxy starts each configured downstream MCP server as a child process and
applies platform-specific cleanup controls:

| Platform | Ungraceful Proxy Termination Behavior |
| --- | --- |
| Linux | The downstream child receives `SIGTERM` through `prctl(PR_SET_PDEATHSIG)` if the proxy process exits before normal cleanup. The downstream also runs in its own process group for graceful shutdown. |
| Windows | The downstream process is assigned to a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`; the kernel terminates the job when the proxy process exits. |
| macOS | Graceful proxy shutdown terminates the downstream process group. If the proxy is force-killed, downstream may remain running; run the proxy under `launchd` or another supervisor when ungraceful-termination cleanup is required. |

## Downstream Response Timeout

The proxy waits up to `downstream.response_timeout_seconds` for a forwarded
JSON-RPC request to receive a matching downstream response. The default is 30
seconds.

Example:

```json
{
  "downstream": {
    "name": "github-mcp",
    "command": "github-mcp-server",
    "args": [],
    "response_timeout_seconds": 30
  }
}
```

On timeout, the proxy returns a sanitized JSON-RPC error to the client and keeps
the downstream process running so later requests can continue.
