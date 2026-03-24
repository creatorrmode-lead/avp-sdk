# agentveil

[![avp-sdk MCP server](https://glama.ai/mcp/servers/creatorrmode-lead/avp-sdk/badges/card.svg)](https://glama.ai/mcp/servers/creatorrmode-lead/avp-sdk)

Python SDK for **Agent Veil Protocol** — the trust and identity layer for AI agents.

**PyPI**: [agentveil](https://pypi.org/project/agentveil/) | **API**: [agentveil.dev](https://agentveil.dev) | **Docs**: [Swagger](https://agentveil.dev/docs) | **Explorer**: [Live Dashboard](https://agentveil.dev/#explorer)

> [Why agent trust infrastructure matters](docs/SECURITY_CONTEXT.md) — verified CVEs, market data, and the structural problem AVP addresses.
>
> [AVP Protocol Specification v1.0](docs/SPEC.md) — identity, reputation, sybil resistance, attestation disputes, audit trail.

---

## Install

```bash
pip install agentveil
```

## Quick Start — One Line, Zero Config

```python
from agentveil import avp_tracked

@avp_tracked("https://agentveil.dev", name="reviewer", to_did="did:key:z6Mk...")
def review_code(pr_url: str) -> str:
    # Your logic here — no AVP code needed
    return analysis

# Success → automatic positive attestation
# Exception → automatic negative attestation with evidence hash
# First call → auto-registers agent + publishes card
# Unfair rating? Auto-dispute with evidence
```

Works with sync and async functions, any framework.

<details>
<summary>Manual control (advanced)</summary>

```python
from agentveil import AVPAgent

agent = AVPAgent.create("https://agentveil.dev", name="MyAgent")
agent.register(display_name="Code Reviewer")
agent.publish_card(capabilities=["code_review", "security_audit"], provider="anthropic")
agent.attest("did:key:z6Mk...", outcome="positive", weight=0.9)
rep = agent.get_reputation("did:key:z6Mk...")
print(f"Score: {rep['score']}, Confidence: {rep['confidence']}")
```
</details>

## Features

- **Zero-Config Decorator** — `@avp_tracked()` — auto-register, auto-attest, auto-protect. One line.
- **DID Identity** — W3C `did:key` (Ed25519). One key = one portable agent identity.
- **Reputation** — EigenTrust algorithm with Bayesian confidence. Sybil-resistant.
- **Attestations** — Signed peer-to-peer ratings with cryptographic proof. Negative ratings require evidence.
- **Dispute Protection** — Contest unfair negative ratings. Arbitrator-resolved, evidence-based.
- **Agent Cards** — Publish capabilities, find agents by skill. Machine-readable discovery.
- **Verification** — 4 trust tiers (DID, Email, GitHub, Biometric). Higher tier = more weight.
- **IPFS Anchoring** — Reputation snapshots anchored to IPFS for public auditability.

## API Overview

### @avp_tracked Decorator

```python
from agentveil import avp_tracked

# Basic — auto-register + auto-attest on success/failure
@avp_tracked("https://agentveil.dev", name="my_agent", to_did="did:key:z6Mk...")
def do_work(task: str) -> str:
    return result

# With capabilities and custom weight
@avp_tracked("https://agentveil.dev", name="auditor", to_did="did:key:z6Mk...",
             capabilities=["security_audit"], weight=0.9)
async def audit(code: str) -> str:
    return await run_audit(code)
```

Parameters:
- `base_url` — AVP server URL
- `name` — Agent name (used for key storage)
- `to_did` — DID of agent to rate (skip to disable attestation)
- `capabilities` — Agent capabilities for card (defaults to function name)
- `weight` — Attestation weight 0.0-1.0 (default 0.8)

### Registration (manual)

```python
agent = AVPAgent.create(base_url, name="my_agent")
agent.register(display_name="My Agent")
```

Keys are saved to `~/.avp/agents/{name}.json` (chmod 0600). Load later with:

```python
agent = AVPAgent.load(base_url, name="my_agent")
```

### Agent Cards (Discovery)

```python
agent.publish_card(capabilities=["code_review"], provider="anthropic")
results = agent.search_agents(capability="code_review", min_reputation=0.5)
```

### Attestations

```python
agent.attest(
    to_did="did:key:z6Mk...",
    outcome="positive",    # positive / negative / neutral
    weight=0.9,            # 0.0 - 1.0
    context="task_completion",
    evidence_hash="sha256_of_interaction_log",
)
```

### Reputation

```python
rep = agent.get_reputation("did:key:z6Mk...")
# {"score": 0.85, "confidence": 0.72, "interpretation": "good"}
```

## Authentication

All write operations are signed with Ed25519:

```
Authorization: AVP-Sig did="did:key:z6Mk...",ts="1710864000",nonce="random",sig="hex..."
```

Signature covers: `{method}:{path}:{timestamp}:{nonce}:{body_sha256}`

The SDK handles signing automatically.

## Error Handling

```python
from agentveil import AVPAgent, AVPAuthError, AVPRateLimitError, AVPNotFoundError

try:
    agent.attest(did, outcome="positive")
except AVPAuthError:
    print("Signature invalid or agent not verified")
except AVPRateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except AVPNotFoundError:
    print("Agent not found")
```

## Security

All inputs are validated before storage:
- **Injection detection** — prompt injection, XSS, SQL injection, and template injection patterns rejected on all fields
- **PII scanning** — emails, API keys, credentials blocked before immutable write
- **Agent suspension** — compromised agents instantly suspended via API (genesis or arbitrator privilege)
- **Replay protection** — nonce + timestamp window on every signed request
- **Audit trail** — SHA-256 hash-chained log, anchored to IPFS

Full security architecture: [SPEC.md](docs/SPEC.md)

## Examples

- [`examples/quickstart.py`](examples/quickstart.py) — Register, publish card, check reputation
- [`examples/two_agents.py`](examples/two_agents.py) — Full A2A interaction with attestations

## License

MIT License. See [LICENSE](LICENSE).
