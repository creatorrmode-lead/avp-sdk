# agentveil

[![PyPI](https://img.shields.io/pypi/v/agentveil)](https://pypi.org/project/agentveil/)
[![Python](https://img.shields.io/pypi/pyversions/agentveil)](https://pypi.org/project/agentveil/)
[![Tests](https://github.com/creatorrmode-lead/avp-sdk/actions/workflows/tests.yml/badge.svg)](https://github.com/creatorrmode-lead/avp-sdk/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://glama.ai/mcp/servers/creatorrmode-lead/avp-sdk/badges/card.svg)](https://glama.ai/mcp/servers/creatorrmode-lead/avp-sdk)

Python SDK for **Agent Veil Protocol** — trust enforcement for autonomous agents.

**PyPI**: [agentveil](https://pypi.org/project/agentveil/) | **API**: [agentveil.dev](https://agentveil.dev) | **Explorer**: [Live Dashboard](https://agentveil.dev/#explorer)

> [Why agent trust infrastructure matters](docs/SECURITY_CONTEXT.md) — verified CVEs, market data, and the structural problem AVP addresses.

> **[Integrated with Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit/pull/1010)** — AVPProvider merged as official TrustProvider integration.

<p align="center">
  <img src="docs/demo.gif" alt="AVP SDK Demo — identity, attestation, trust decisions, sybil resistance" width="720">
</p>

```python
from agentveil import AVPAgent

agent = AVPAgent.load("https://agentveil.dev", "my-agent")

# Should I trust this agent with my task?
decision = agent.can_trust("did:key:z6Mk...", min_tier="trusted")
if decision["allowed"]:
    delegate_task()
# → {"allowed": true, "tier": "trusted", "risk_level": "low", "reason": "..."}
```

---

## Install

```bash
pip install agentveil
```

## Quick Start

### Trust decision — one call

```python
from agentveil import AVPAgent

agent = AVPAgent.load("https://agentveil.dev", "my-agent")
decision = agent.can_trust("did:key:z6Mk...", min_tier="trusted")
print(decision["allowed"], decision["reason"])
```

### Auto-track with decorator

```python
from agentveil import avp_tracked

@avp_tracked("https://agentveil.dev", name="reviewer", to_did="did:key:z6Mk...")
def review_code(pr_url: str) -> str:
    return analysis

# Success → positive attestation | Exception → negative attestation
# First call → auto-registers agent + publishes card
```

### Try without a server

```python
agent = AVPAgent.create(mock=True, name="test_agent")
agent.register(display_name="Test Agent")
rep = agent.get_reputation()
print(rep)  # Works offline — real crypto, mocked HTTP
```

### Verify trust offline — no SDK required

```bash
# Get a W3C Verifiable Credential (VC v2.0)
curl https://agentveil.dev/v1/reputation/{agent_did}/credential?format=w3c
```

The response is a standard W3C VC with a `DataIntegrityProof` (`eddsa-jcs-2022`). Verify it with any VC library — Veramo, SpruceID, Digital Bazaar, or your own Ed25519 implementation. No AVP SDK needed.

```python
# Or verify with the SDK:
cred = agent.get_reputation_credential(format="w3c")
assert AVPAgent.verify_w3c_credential(cred)  # offline, no API call
```

---

## Features

- **Trust Check** — `can_trust()` — one-call advisory trust decision: score + tier + risk + explanation
- **W3C VC v2.0 Credentials** — Trust credentials are W3C Verifiable Credentials compliant (`eddsa-jcs-2022` Data Integrity proof). Verify offline with any standard VC library, no AVP SDK required
- **One-Line Decorator** — `@avp_tracked()` — auto-register, auto-attest, auto-protect
- **DID Identity** — W3C `did:key` (Ed25519). Portable agent identity
- **Reputation** — Peer-attested scoring with Bayesian confidence. Sybil-resistant
- **Attestations** — Signed peer-to-peer ratings. Negative ratings require SHA-256 evidence. Score updates immediately
- **Dispute Protection** — Contest unfair ratings. Auto-assigned arbitrator from verified pool
- **Agent Discovery** — Publish capabilities, find agents by skill and reputation
- **Webhook Alerts** — Push notifications on score drops ([setup guide](docs/WEBHOOKS.md))
- **Sybil Resistance** — Multi-layer graph analysis blocks fake agent rings
- **Trust Gate** — Reputation-based rate limiting (newcomer → basic → trusted → elite)

---

## Integrations

| Framework | Install | Quick Start |
|-----------|---------|-------------|
| **Any Python** | `pip install agentveil` | `@avp_tracked()` or `AVPAgent` directly |
| **CrewAI** | `pip install agentveil crewai` | `tools=[AVPReputationTool(), AVPDelegationTool()]` |
| **LangGraph** | `pip install agentveil langgraph` | `ToolNode([avp_check_reputation, avp_should_delegate])` |
| **AutoGen** | `pip install agentveil autogen-core` | `tools=avp_reputation_tools()` |
| **OpenAI** | `pip install agentveil openai` | `tools=avp_tool_definitions()` |
| **Claude** | `pip install 'agentveil[mcp]'` | `agentveil-mcp` — MCP server, [docs](agentveil_mcp/README.md) |
| **Hermes** | `pip install 'agentveil[mcp]'` | `agentveil-mcp` + agentskills.io skill |
| **Paperclip** | `pip install agentveil` | `avp_should_delegate()` + `avp_evaluate_team()` |
| **AWS Bedrock** | `pip install agentveil boto3` | Converse API with AVP trust tools |
| **AgentMesh (MS AGT)** | `pip install agentmesh-avp` | `TrustEngine(external_providers=[AVPProvider()])` |

Full integration guides: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)

---

## Batch Attestations

Submit up to 50 attestations in a single request. Each is validated independently — partial success is possible.

```python
results = agent.attest_batch([
    {"to_did": "did:key:z6MkAgent1...", "outcome": "positive", "weight": 0.9, "context": "code_review"},
    {"to_did": "did:key:z6MkAgent2...", "outcome": "negative", "weight": 0.7, "evidence_hash": "sha256hex..."},
    {"to_did": "did:key:z6MkAgent3...", "outcome": "positive"},
])
print(results["succeeded"], results["failed"])  # 3, 0
```

Each attestation is individually signed with Ed25519. Optional fields: `context`, `evidence_hash`, `is_private`, `interaction_id`.

---

## Security

- Ed25519 signature authentication with nonce anti-replay
- Input validation — injection detection, PII scanning
- Agent suspension — compromised agents instantly blocked
- Audit trail — SHA-256 hash-chained log, anchored to IPFS

---

## Documentation

| Doc | Description |
|-----|-------------|
| [API Reference](docs/API.md) | Full SDK method reference with examples |
| [Integrations](docs/INTEGRATIONS.md) | Framework-specific setup guides |
| [Webhook Alerts](docs/WEBHOOKS.md) | Push notification setup |
| [Protocol Spec](docs/PROTOCOL.md) | Wire format and authentication |
| [Security Context](docs/SECURITY_CONTEXT.md) | Why agent trust matters — CVEs and market data |
| [Changelog](CHANGELOG.md) | Version history |

---

## Examples

| Example | Description |
|---------|-------------|
| [`standalone_demo.py`](examples/standalone_demo.py) | No server needed — full SDK demo with mock mode |
| [`quickstart.py`](examples/quickstart.py) | Register, publish card, check reputation |
| [`two_agents.py`](examples/two_agents.py) | Full A2A interaction with attestations |
| [`verify_credential_standalone.py`](examples/verify_credential_standalone.py) | Offline credential verification (no SDK needed) |

Framework examples: [CrewAI](examples/crewai_example.py) · [LangGraph](examples/langgraph_example.py) · [AutoGen](examples/autogen_example.py) · [OpenAI](examples/openai_example.py) · [Claude MCP](examples/claude_mcp_example.py) · [Paperclip](examples/paperclip_example.py)

---

## License

MIT — see [LICENSE](LICENSE).
