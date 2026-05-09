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

## Downstream Response Size And Framing

The proxy accepts downstream JSON-RPC responses as UTF-8 JSON objects on stdout,
including pretty-printed objects that span multiple lines. Each downstream
message is bounded to 1 MiB. If a downstream response exceeds that limit or is
not a JSON object, the proxy returns a sanitized downstream-unavailable error to
the client and does not include response content in logs or client output.

## Proxy Identity Storage

`agentveil-mcp-proxy init` encrypts the local proxy identity by default. In an
interactive shell it prompts for a passphrase and confirmation. In automated
setup, provide the passphrase with one of:

```bash
agentveil-mcp-proxy init --passphrase-file /run/secrets/avp-proxy-passphrase
AVP_PROXY_PASSPHRASE='...' agentveil-mcp-proxy init
```

`doctor`, `run`, and `reissue-grant` use the same passphrase sources. Plaintext
storage is available only through the explicit `--plaintext` opt-out on `init`;
the command prints a warning because the private key is then protected only by
local file permissions.

## Control Grant Lifecycle

The local control grant defaults to a 30-day TTL. `doctor` warns when the grant
expires within 7 days and fails when it has already expired.

To rotate the grant:

```bash
agentveil-mcp-proxy reissue-grant --passphrase-file /run/secrets/avp-proxy-passphrase
```

The command refuses to replace a still-valid grant with more than 24 hours
remaining unless `--force` is passed. For scheduled checks, `--auto` prints a
single structured status line.
