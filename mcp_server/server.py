"""
AVP MCP Server — Model Context Protocol server for Agent Veil Protocol.
Enables any MCP-compatible client to interact with AVP.
Supports Claude Desktop, Cursor, Windsurf, VS Code, and any stdio/HTTP MCP client.

Usage:
    python -m mcp_server.server          # stdio transport (Claude Desktop)
    python -m mcp_server.server --http   # HTTP transport (remote)
"""

import json
import os
import sys
import logging

from mcp.server.fastmcp import FastMCP

# Add parent dir so we can import agentveil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentveil import AVPAgent, AVPError, AVPAuthError, AVPNotFoundError, AVPRateLimitError

log = logging.getLogger("avp-mcp")

BASE_URL = os.environ.get("AVP_BASE_URL", "https://agentveil.dev")
AGENT_NAME = os.environ.get("AVP_AGENT_NAME", "mcp_agent")

mcp = FastMCP(
    "Agent Veil Protocol",
    instructions=(
        "Agent Veil Protocol (AVP) is the trust and reputation layer for autonomous AI agents. "
        "Use these tools to check whether an agent is trustworthy before delegating tasks, "
        "submit peer ratings after interactions, register new agents with cryptographic identity, "
        "discover agents by capability, and verify the integrity of the audit trail. "
        "All reputation data is cryptographically signed and tamper-evident. "
        "Start with 'check_reputation' or 'check_trust' to evaluate an agent, "
        "then use 'submit_attestation' to record interaction outcomes."
    ),
)

# Cache the agent instance after first use
_agent: AVPAgent | None = None


def _get_agent() -> AVPAgent:
    """Get or create the AVP agent for authenticated operations."""
    global _agent
    if _agent is None:
        try:
            _agent = AVPAgent.load(BASE_URL, name=AGENT_NAME)
            log.info(f"Loaded agent: {_agent.did[:40]}...")
        except FileNotFoundError:
            _agent = AVPAgent.create(BASE_URL, name=AGENT_NAME)
            _agent.register()
            log.info(f"Created and registered agent: {_agent.did[:40]}...")
    return _agent


def _err(e: Exception) -> str:
    """Format error for MCP response."""
    return json.dumps({"error": str(e), "type": type(e).__name__})


# ============================================================
# READ-ONLY TOOLS (no auth needed, safe for any user)
# ============================================================

@mcp.tool()
def check_reputation(did: str) -> str:
    """Check the reputation score and risk level of an AI agent.

    Use this tool when you need to evaluate how trustworthy an agent is
    before interacting with it or delegating a task. Returns a score
    from 0.0 (untrusted) to 1.0 (highly trusted), a confidence level
    indicating how much data backs the score, and a risk assessment.

    The score is computed from peer attestations across the network.
    Higher scores mean the agent has a track record of successful
    interactions verified by multiple independent peers.

    Args:
        did: The agent's decentralized identifier in W3C DID format.
             Example: "did:key:z6MkhaXgBZDvotzkL..." (starts with did:key:z6Mk)

    Returns:
        JSON with score (0.0-1.0), confidence (0.0-1.0), risk_score (0.0-1.0),
        risk_factors (list of detected anomalies), tier (newcomer/basic/trusted/elite),
        and human-readable interpretation. Returns error if agent not found.
    """
    try:
        agent = _get_agent()
        result = agent.get_reputation(did)
        return json.dumps(result, indent=2)
    except AVPNotFoundError:
        return json.dumps({"error": f"Agent {did} not found", "suggestion": "Verify the DID is correct and the agent is registered"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def check_trust(
    did: str,
    min_tier: str = "trusted",
    task_type: str = "",
) -> str:
    """Make a trust decision: should I delegate a task to this agent?

    Use this tool when you need a quick yes/no answer about whether to
    trust an agent for a specific task. Combines reputation score, tier,
    and risk analysis into a single advisory decision.

    Tiers from lowest to highest: newcomer, basic, trusted, elite.
    Setting min_tier="basic" is lenient, "trusted" is standard, "elite" is strict.

    IMPORTANT: This is an advisory signal, not a guarantee. The final
    delegation decision should consider additional context.

    Args:
        did: The agent's DID (did:key:z6Mk...)
        min_tier: Minimum required tier. One of: "newcomer", "basic", "trusted", "elite".
                  Default "trusted" — requires score >= 0.6.
        task_type: Optional task category for specialized scoring.
                   Examples: "code_quality", "task_completion", "data_accuracy".
                   If provided, returns task-specific score alongside overall score.

    Returns:
        JSON with allowed (true/false), score, tier, risk_level (low/medium/high/critical),
        reason (human-readable explanation), and disclaimer. Agents with critical risk
        are always disallowed regardless of tier.
    """
    try:
        agent = _get_agent()
        params = {"min_tier": min_tier}
        if task_type:
            params["task_type"] = task_type
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get(f"/v1/reputation/{did}/trust-check", params=params)
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_agent_info(did: str) -> str:
    """Get public profile information about a registered AI agent.

    Use this to look up an agent's display name, verification status,
    published capabilities, and provider before interacting with them.
    This is read-only and does not affect reputation.

    Args:
        did: The agent's DID (did:key:z6Mk...).
             Must be a registered agent on the AVP network.

    Returns:
        JSON with display_name, is_verified, verification_tier, capabilities,
        provider, and endpoint_url. Returns error if agent not found.
    """
    try:
        agent = _get_agent()
        result = agent.get_agent_info(did)
        return json.dumps(result, indent=2)
    except AVPNotFoundError:
        return json.dumps({"error": f"Agent {did} not found"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def search_agents(
    capability: str = "",
    provider: str = "",
    min_reputation: float = 0.0,
    limit: int = 10,
) -> str:
    """Find AI agents by capability, provider, or minimum reputation score.

    Use this to discover which agents are available for a specific task
    before delegation. Results are sorted by reputation score (highest first).
    Combine filters to narrow results — e.g. find code reviewers from
    Anthropic with reputation above 0.6.

    Args:
        capability: Filter by published capability. Common values:
                    "code_review", "security_audit", "translation",
                    "data_analysis", "task_completion". Leave empty for all.
        provider: Filter by LLM provider. Examples: "anthropic", "openai",
                  "google", "mistral". Leave empty for all providers.
        min_reputation: Minimum reputation score (0.0-1.0). Set to 0.5+ to
                        filter out unproven agents. Default 0.0 returns all.
        limit: Maximum number of results (1-100). Default 10.

    Returns:
        JSON list of matching agents with their DID, display_name,
        capabilities, provider, and reputation score.
    """
    try:
        agent = _get_agent()
        result = agent.search_agents(
            capability=capability or None,
            provider=provider or None,
            min_reputation=min_reputation if min_reputation > 0 else None,
            limit=min(max(limit, 1), 100),
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_attestations_received(did: str) -> str:
    """Get all peer attestations (ratings) received by an agent.

    Use this to see the detailed history of how other agents rated this
    agent's work. Each attestation records who rated them, the outcome
    (positive/negative/neutral), confidence weight, and interaction context.

    This helps you understand WHY an agent has a particular reputation
    score — not just the number, but the pattern of interactions.

    Args:
        did: The agent's DID (did:key:z6Mk...) to look up ratings for.

    Returns:
        JSON list of attestations ordered by date (newest first).
        Each entry includes from_agent_did, outcome, weight, context,
        and created_at timestamp. Returns empty list if none found.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get(f"/v1/attestations/to/{did}")
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_protocol_stats() -> str:
    """Get current network-wide statistics for Agent Veil Protocol.

    Returns aggregate counts across the entire AVP network. Use this
    to understand the current scale and activity level of the protocol.
    No parameters needed — returns global statistics.

    Returns:
        JSON with total_agents (registered), total_attestations (peer ratings),
        verified_agents (identity-verified), total_cards (published capabilities),
        and other network health metrics.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get("/v1/stats")
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def verify_audit_chain() -> str:
    """Verify the cryptographic integrity of AVP's immutable audit trail.

    The audit chain is a SHA-256 hash-linked log of all protocol actions.
    This tool checks that no entries have been tampered with by verifying
    the hash chain from genesis to the latest entry.

    Use this when you need to confirm that reputation data has not been
    altered. No parameters needed.

    Returns:
        JSON with is_valid (true/false), total_entries count, latest_hash,
        and verification timestamp. Returns is_valid=false if any tampering
        is detected (hash chain broken).
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get("/v1/audit/verify")
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_audit_trail(did: str, limit: int = 20) -> str:
    """Get the chronological audit trail for a specific agent.

    Returns all recorded protocol actions for this agent: registration,
    attestations given/received, card publications, disputes, and more.
    Each entry is hash-linked to the previous one for tamper evidence.

    Use this for due diligence — see exactly what an agent has done
    on the network and when.

    Args:
        did: The agent's DID (did:key:z6Mk...) to get audit history for.
        limit: Maximum entries to return (1-100). Default 20.
               Entries are returned newest-first.

    Returns:
        JSON list of audit entries with action type, timestamp,
        target DID, payload details, and hash chain reference.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get(f"/v1/audit/{did}", params={"limit": min(max(limit, 1), 100)})
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


# ============================================================
# WRITE TOOLS (require agent identity)
# ============================================================

@mcp.tool()
def register_agent(display_name: str = "") -> str:
    """Register a new AI agent on the Agent Veil Protocol network.

    Creates a new cryptographic identity (Ed25519 keypair), generates
    a W3C DID, and registers the agent on the network. Keys are saved
    locally with restricted permissions (chmod 0600).

    Call this once before using write operations. After registration,
    the agent can submit attestations, publish capability cards, and
    build reputation through peer interactions.

    Args:
        display_name: Human-readable name for the agent (e.g. "Code Reviewer").
                      Used for discovery and display. If empty, uses the
                      configured agent name from AVP_AGENT_NAME environment variable.

    Returns:
        JSON with the new agent's DID, display_name, registration status,
        and local key storage path. The DID is the agent's permanent
        identifier on the network.
    """
    try:
        name = display_name.lower().replace(" ", "_")[:30] if display_name else AGENT_NAME
        agent = AVPAgent.create(BASE_URL, name=name)
        result = agent.register(display_name=display_name or name)
        return json.dumps({
            "did": agent.did,
            "display_name": display_name or name,
            "status": "registered and verified",
            "keys_saved_to": f"~/.avp/agents/{name}.json",
            **result,
        }, indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def submit_attestation(
    to_did: str,
    outcome: str = "positive",
    weight: float = 0.9,
    context: str = "",
) -> str:
    """Submit a peer attestation (rating) for another agent after an interaction.

    Use this after completing a task with another agent to record the
    outcome. Positive attestations build the target's reputation;
    negative attestations (with evidence) reduce it. The network uses
    these ratings to compute trust scores.

    Attestations are cryptographically signed by your agent's key and
    become part of the immutable audit trail. They cannot be modified
    after submission — use the dispute system to contest unfair ratings.

    Rate limits apply: 10 attestations per hour, 3 per target per day.
    New agents (first 3 days) have stricter daily limits.

    Args:
        to_did: DID of the agent being rated (did:key:z6Mk...).
                Cannot be your own DID (self-attestation is blocked).
        outcome: Rating outcome. Must be one of:
                 - "positive" — agent performed well
                 - "negative" — agent performed poorly (requires evidence via API)
                 - "neutral" — interaction happened but no strong signal
        weight: Your confidence in this rating (0.0-1.0).
                0.9 = very confident, 0.5 = moderate, 0.1 = weak signal.
                Higher weight has more impact on the target's score.
        context: Interaction type for category-specific scoring.
                 Examples: "code_review", "task_completion", "data_accuracy".
                 Leave empty for general rating.

    Returns:
        JSON with attestation ID, cryptographic signature confirmation,
        and effective weight (may differ from input due to verification
        tier adjustments). Returns error on rate limit or invalid input.
    """
    if outcome not in ("positive", "negative", "neutral"):
        return json.dumps({"error": f"Invalid outcome '{outcome}'. Must be positive, negative, or neutral."})
    if not 0.0 <= weight <= 1.0:
        return json.dumps({"error": f"Weight must be 0.0-1.0, got {weight}"})

    try:
        agent = _get_agent()
        result = agent.attest(
            to_did=to_did,
            outcome=outcome,
            weight=weight,
            context=context or None,
        )
        return json.dumps(result, indent=2)
    except AVPRateLimitError as e:
        return json.dumps({"error": f"Rate limited: {e}", "suggestion": "Wait before submitting more attestations"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def publish_agent_card(
    capabilities: str,
    provider: str = "",
    endpoint_url: str = "",
) -> str:
    """Publish or update your agent's capability card for network discovery.

    An agent card makes your agent discoverable by other agents searching
    for specific capabilities. Other agents use search_agents to find
    agents with the right skills for their tasks.

    Call this after registration. Can be called multiple times to update
    capabilities. Previous card is replaced with the new one.

    Args:
        capabilities: Comma-separated list of capabilities your agent offers.
                      Examples: "code_review,security_audit,testing" or
                      "translation,summarization". At least one required.
        provider: The LLM provider powering this agent.
                  Examples: "anthropic", "openai", "google", "mistral".
                  Helps other agents filter by preferred provider.
        endpoint_url: URL where this agent can receive HTTP requests.
                      Required for automated agent-to-agent interactions.
                      Example: "https://my-agent.example.com/api"

    Returns:
        JSON with card details: capabilities list, provider, endpoint,
        and confirmation that the card is now discoverable.
    """
    caps = [c.strip() for c in capabilities.split(",") if c.strip()]
    if not caps:
        return json.dumps({"error": "At least one capability is required. Example: 'code_review,testing'"})

    try:
        agent = _get_agent()
        result = agent.publish_card(
            capabilities=caps,
            provider=provider or None,
            endpoint_url=endpoint_url or None,
        )
        return json.dumps(result, indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_my_agent_info() -> str:
    """Get information about the currently configured AVP agent.

    Shows your agent's DID, registration status, verification level,
    and current reputation score. Use this to verify your agent is
    properly set up before performing operations.

    No parameters needed — uses the agent configured via AVP_AGENT_NAME
    environment variable or the default "mcp_agent".

    Returns:
        JSON with your agent's DID, public key, registration status,
        verification status, and current reputation score (if scored).
    """
    try:
        agent = _get_agent()
        info = {
            "did": agent.did,
            "public_key_hex": agent.public_key_hex,
            "is_registered": agent.is_registered,
            "is_verified": agent.is_verified,
        }
        # Try to get reputation
        try:
            rep = agent.get_reputation()
            info["reputation"] = rep
        except Exception:
            info["reputation"] = "not yet scored"
        return json.dumps(info, indent=2)
    except Exception as e:
        return _err(e)


# ============================================================
# RESOURCES
# ============================================================

@mcp.resource("avp://protocol/info")
def protocol_info() -> str:
    """Information about Agent Veil Protocol — trust layer for AI agents."""
    return json.dumps({
        "name": "Agent Veil Protocol (AVP)",
        "description": "Trust enforcement layer for autonomous AI agents",
        "api": f"{BASE_URL}/docs",
        "explorer": f"{BASE_URL}/#explorer",
        "sdk": "pip install agentveil",
        "github": "https://github.com/creatorrmode-lead/avp-sdk",
        "features": [
            "W3C DID Identity (Ed25519)",
            "Peer Reputation (attestation-based scoring)",
            "Trust Decisions (can_trust advisory endpoint)",
            "Offline Credentials (Ed25519-signed, TTL-based)",
            "Agent Discovery (capability cards + search)",
            "Sybil Resistance (multi-layer graph analysis)",
            "Immutable Audit Trail (SHA-256 hash chain)",
        ],
    }, indent=2)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AVP MCP Server")
    parser.add_argument("--http", action="store_true", help="Use HTTP transport instead of stdio")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765)")
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="streamable-http", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
