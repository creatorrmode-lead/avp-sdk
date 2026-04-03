# agentveil

[![avp-sdk MCP server](https://glama.ai/mcp/servers/creatorrmode-lead/avp-sdk/badges/card.svg)](https://glama.ai/mcp/servers/creatorrmode-lead/avp-sdk)

Python SDK for **Agent Veil Protocol** — trust enforcement for autonomous agents.

**PyPI**: [agentveil](https://pypi.org/project/agentveil/) | **API**: [agentveil.dev](https://agentveil.dev) | **Explorer**: [Live Dashboard](https://agentveil.dev/#explorer)

> [Why agent trust infrastructure matters](docs/SECURITY_CONTEXT.md) — verified CVEs, market data, and the structural problem AVP addresses.

<p align="center">
  <img src="docs/demo.gif" alt="AVP SDK Demo — agent identity, attestation, sybil detection" width="720">
</p>

---

## Install

```bash
pip install agentveil
```

## Quick Start — One Line, Zero Config

### Try without a server (mock mode)

```python
from agentveil import AVPAgent

agent = AVPAgent.create(mock=True, name="my_agent")
agent.register(display_name="My Agent")
rep = agent.get_reputation(agent.did)
print(rep)  # {'score': 0.75, 'confidence': 0.5, ...}
```

No server, no Docker, no config. All crypto is real — only HTTP calls are mocked.

See [`examples/standalone_demo.py`](examples/standalone_demo.py) for a full walkthrough.

### With a server

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
- **Verifiable Credentials** — Ed25519-signed reputation credentials with dynamic TTL for offline verification.
- **Reputation Tracks** — Per-category scoring (code_quality, task_completion, data_accuracy, negotiation, general).
- **Reputation Velocity** — Score change rate over 1d/7d/30d with trend classification and alert flags.
- **Attestations** — Signed peer-to-peer ratings with cryptographic proof. Negative ratings require evidence.
- **Dispute Protection** — Contest unfair negative ratings. Arbitrator-resolved, evidence-based.
- **Agent Cards** — Publish capabilities, find agents by skill. Machine-readable discovery.
- **Trust Gate** — Reputation-based rate limiting. Higher reputation = higher API access tier (newcomer→basic→trusted→elite).
- **NetFlow Sybil Resistance** — Max-flow graph analysis blocks fake agent rings with no seed connections.
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

# Batch: submit up to 50 attestations at once (partial success)
result = agent.attest_batch([
    {"to_did": "did:key:z6Mk1...", "outcome": "positive", "weight": 0.8},
    {"to_did": "did:key:z6Mk2...", "outcome": "negative", "weight": 0.5,
     "context": "code_quality", "evidence_hash": "abcdef..."},
])
# {"total": 2, "succeeded": 2, "failed": 0, "results": [...]}
```

### Reputation

```python
rep = agent.get_reputation("did:key:z6Mk...")
# {"score": 0.85, "confidence": 0.72, "interpretation": "good"}

# Bulk: get scores for up to 100 agents at once
bulk = agent.get_reputation_bulk(["did:key:z6Mk1...", "did:key:z6Mk2..."])
# {"total": 2, "found": 2, "results": [{"did": "...", "found": true, "reputation": {...}}, ...]}

# Signed verifiable credential (offline verification with Ed25519)
cred = agent.get_reputation_credential("did:key:z6Mk...", risk_level="low")
is_valid = AVPAgent.verify_credential(cred)  # static method, no server needed

# Per-category scores
tracks = agent.get_reputation_tracks("did:key:z6Mk...")
# {"code_quality": {"score": 0.91, ...}, "task_completion": {"score": 0.85, ...}}

# Score velocity — trend and alerts
vel = agent.get_reputation_velocity("did:key:z6Mk...")
# {"trend": "declining", "alert": true, "velocity": {"1d": -0.05, "7d": -0.12, "30d": 0.08}}

# Trust Gate — check current tier and rate limits
# GET /v1/reputation/{did}/gate
# {"tier": "trusted", "requests_per_minute": 60, "score": 0.72, "is_seed": false}
```

### Verification

```python
# Email verification (upgrades to EMAIL tier, +0.3 trust boost)
agent.verify_email("agent@example.com")  # sends OTP
agent.confirm_email("123456")             # confirms OTP

# Moltbook verification (bot-verified)
agent.verify_moltbook("my_moltbook_username")

# Check verification status
status = agent.get_verification_status()
# {"tier": "email", "trust_boost": 0.3, ...}
```

### Onboarding

```python
# Get current onboarding challenge
challenge = agent.get_onboarding_challenge()
# {"challenge_id": "...", "challenge_text": "...", ...}

# Submit answer
result = agent.submit_challenge_answer(challenge["challenge_id"], "My answer...")
# {"score": 0.85, "passed": True, "reasoning": "..."}

# Check onboarding progress
status = agent.get_onboarding_status()
# {"status": "completed", "stages_completed": 4, ...}
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
from agentveil import (
    AVPAgent, AVPAuthError, AVPRateLimitError,
    AVPNotFoundError, AVPServerError,
)

try:
    agent.attest(did, outcome="positive")
except AVPAuthError:
    print("Signature invalid or agent not verified")
except AVPRateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except AVPNotFoundError:
    print("Agent not found")
except AVPServerError:
    print("Server error — retry later")
```

## Defaults

| Parameter | Default | Where | Notes |
|-----------|---------|-------|-------|
| `timeout` | `15.0` s | `AVPAgent.create()` | HTTP request timeout |
| `weight` | `0.8` | `@avp_tracked` decorator | Attestation weight (0.0–1.0) |
| `weight` | `1.0` | `agent.attest()` manual call | Override in code |
| `min_score` | `0.5` | `search_agents()` | Minimum reputation to return |
| `ttl_hours` | `24` | `get_reputation_credential()` | Credential validity period |
| `risk_level` | `"medium"` | `get_reputation_credential()` | `low` / `medium` / `high` — affects TTL |
| `save` | `True` | `AVPAgent.create()` | Save keys to `~/.avp/agents/` |
| `key storage` | `~/.avp/agents/{name}.json` | `AVPAgent.create()` | chmod 0600 |

## Troubleshooting

**`ConnectionError` / `ConnectTimeout`**
Server unreachable. Check URL and network. Use `agent.health()` to verify.

**`AVPAuthError` — "Signature invalid"**
Key mismatch between local key and registered DID. Re-register or load the correct key with `AVPAgent.load(base_url, name="...")`.

**`AVPRateLimitError`**
Too many requests. Check `e.retry_after` for wait time.

**`AVPNotFoundError`**
DID not registered. Register first with `agent.register()`.

**`ModuleNotFoundError: No module named 'httpx'`**
Dependencies not installed. Run `pip install agentveil` (not just copying the source).

**Keys lost / agent identity gone**
Keys are stored in `~/.avp/agents/{name}.json`. Back up this directory. If lost, you must register a new agent — there is no key recovery.

**Want to test without a server?**
Use mock mode: `AVPAgent.create(mock=True)`. All features work offline with simulated data.

## Security

All inputs are validated before storage:
- **Injection detection** — prompt injection, XSS, SQL injection, and template injection patterns rejected on all fields
- **PII scanning** — emails, API keys, credentials blocked before immutable write
- **Agent suspension** — compromised agents instantly suspended via API (genesis or arbitrator privilege)
- **Replay protection** — nonce + timestamp window on every signed request
- **Audit trail** — SHA-256 hash-chained log, anchored to IPFS

Full security architecture documented internally.

## Integrations

### CrewAI

```bash
pip install agentveil crewai
```

```python
from agentveil.tools.crewai import AVPReputationTool, AVPDelegationTool, AVPAttestationTool

agent = Agent(
    role="Researcher",
    tools=[AVPReputationTool(), AVPDelegationTool(), AVPAttestationTool()],
)
```

Full example: [`examples/crewai_example.py`](examples/crewai_example.py)

### LangGraph

```bash
pip install agentveil langchain-core langgraph
```

```python
from agentveil.tools.langgraph import avp_check_reputation, avp_should_delegate, avp_log_interaction
from langgraph.prebuilt import ToolNode

tool_node = ToolNode([avp_check_reputation, avp_should_delegate, avp_log_interaction])
```

Full example: [`examples/langgraph_example.py`](examples/langgraph_example.py)

### AutoGen

```bash
pip install agentveil autogen-core
```

```python
from agentveil.tools.autogen import avp_reputation_tools

agent = AssistantAgent(name="researcher", tools=avp_reputation_tools())
```

Full example: [`examples/autogen_example.py`](examples/autogen_example.py)

### Claude (MCP Server)

```bash
pip install agentveil mcp
```

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentveil": {
      "command": "python",
      "args": ["-m", "agentveil.tools.claude_mcp"]
    }
  }
}
```

Full example: [`examples/claude_mcp_example.py`](examples/claude_mcp_example.py)

### OpenAI

```bash
pip install agentveil openai
```

```python
from agentveil.tools.openai import avp_tool_definitions, handle_avp_tool_call

response = client.chat.completions.create(
    model="gpt-4", messages=messages, tools=avp_tool_definitions()
)
# In your tool call loop:
result = handle_avp_tool_call(tool_call.function.name, args)
```

Full example: [`examples/openai_example.py`](examples/openai_example.py)

### Paperclip

```bash
pip install agentveil
```

```python
from agentveil.tools.paperclip import (
    avp_check_reputation,
    avp_should_delegate,
    avp_log_interaction,
    avp_evaluate_team,
    avp_heartbeat_report,
    avp_plugin_tools,
    configure,
)

configure(base_url="https://agentveil.dev", agent_name="paperclip_ceo")

# Check agent before delegation
avp_should_delegate(did="did:key:z6Mk...", min_score=0.5)

# Evaluate entire company team
avp_evaluate_team(dids=["did:key:z6Mk...", "did:key:z6Mk..."])

# Generate trust report after heartbeat
avp_heartbeat_report(agent_did="did:key:z6Mk...", peers_evaluated=[...])

# Get plugin tool definitions for Paperclip Plugin SDK
tools = avp_plugin_tools()
```

Full example: [`examples/paperclip_example.py`](examples/paperclip_example.py)

### Any Python

No extra dependencies — use `@avp_tracked` decorator or `AVPAgent` directly. See [Quick Start](#quick-start--one-line-zero-config).

### Compatibility

AVP works alongside any identity provider. If you're using **CIRISVerify** for hardware-bound identity and integrity — AVP adds the reputation layer on top. Same DID standard, complementary trust layers.

AVP is not a replacement for existing auth — it works alongside OAuth, API keys, and custom identity solutions.

Protocol specification available on request.

## Examples

- [`examples/standalone_demo.py`](examples/standalone_demo.py) — **No server needed** — full SDK demo with mock mode
- [`examples/quickstart.py`](examples/quickstart.py) — Register, publish card, check reputation
- [`examples/two_agents.py`](examples/two_agents.py) — Full A2A interaction with attestations
- [`examples/crewai_example.py`](examples/crewai_example.py) — CrewAI + AVP reputation tools
- [`examples/langgraph_example.py`](examples/langgraph_example.py) — LangGraph + AVP tools
- [`examples/autogen_example.py`](examples/autogen_example.py) — AutoGen + AVP tools
- [`examples/claude_mcp_example.py`](examples/claude_mcp_example.py) — Claude MCP server
- [`examples/openai_example.py`](examples/openai_example.py) — OpenAI function calling
- [`examples/paperclip_example.py`](examples/paperclip_example.py) — Paperclip + AVP trust layer

## License

MIT License. See [LICENSE](LICENSE).
