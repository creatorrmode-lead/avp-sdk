"""
agentveil-mcp — Model Context Protocol server for Agent Veil Protocol.
Enables any MCP-compatible client to interact with AVP.
Supports Claude Desktop, Cursor, Windsurf, VS Code, and any stdio/HTTP MCP client.

Usage:
    agentveil-mcp                 # stdio transport (Claude Desktop / Cursor)
    agentveil-mcp --http          # HTTP transport (remote)
    python -m agentveil_mcp       # equivalent to stdio transport
"""

import json
import os
import logging
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

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
def check_reputation(
    did: Annotated[str, Field(description="Agent's decentralized identifier in W3C DID format. Must start with 'did:key:z6Mk'. Example: 'did:key:z6MkhaXgBZDvotzkL...'")],
) -> str:
    """Get the full reputation profile of an agent: score, confidence, risk factors, and tier.

    Returns detailed numerical data for analysis and logging.
    Use this when you need the actual numbers (score, confidence, risk breakdown).

    NOT for yes/no delegation decisions — use check_trust instead (returns allowed: true/false).
    NOT for rating history — use get_attestations_received for individual peer reviews.

    Read-only. Does not modify any data or affect the target agent's score.

    Args:
        did: Agent's DID in W3C format. Must start with "did:key:z6Mk".

    Returns:
        JSON with score (0.0-1.0), confidence (0.0-1.0), risk_score (0.0-1.0),
        risk_factors (list), tier (newcomer/basic/trusted/elite), and interpretation.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get(f"/v1/reputation/{did}")
            if r.status_code == 404:
                return json.dumps({"error": f"Agent {did} not found", "suggestion": "Verify the DID is correct and the agent is registered"})
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def check_trust(
    did: Annotated[str, Field(description="Agent's DID to evaluate. Format: did:key:z6Mk...")],
    min_tier: Annotated[str, Field(description="Minimum required trust tier. One of: newcomer, basic, trusted, elite. Default: trusted")] = "trusted",
    task_type: Annotated[str, Field(description="Optional task category for specialized scoring. Examples: code_quality, task_completion, data_accuracy")] = "",
) -> str:
    """Quick yes/no delegation decision: is this agent trusted enough for my task?

    Returns allowed (true/false) with a human-readable reason. Use this when you
    only need a go/no-go answer before delegating work.

    NOT for detailed analysis — use check_reputation for full score breakdown.
    NOT for rating history — use get_attestations_received for peer reviews.

    Tiers from lowest to highest: newcomer, basic, trusted, elite.
    Advisory signal, not a guarantee.

    Read-only. Does not modify any data.

    Args:
        did: Agent's DID (did:key:z6Mk...).
        min_tier: Minimum required tier: "newcomer", "basic", "trusted", "elite". Default "trusted".
        task_type: Optional task category for specialized scoring.

    Returns:
        JSON with allowed (true/false), score, tier, risk_level, and reason.
    """
    try:
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
def get_agent_info(
    did: Annotated[str, Field(description="Agent's DID to look up. Format: did:key:z6Mk... Must be a registered agent")],
) -> str:
    """Get public profile information about a registered AI agent.

    Returns display name, verification status, capabilities, and provider.
    Use this when you already have a specific DID and need profile data.

    For trust assessment, use check_reputation or check_trust instead.
    For rating history, use get_attestations_received.
    To find agents by capability, use search_agents.

    Read-only — does not affect reputation or any stored data.

    Args:
        did: The agent's DID (did:key:z6Mk...).
             Must be a registered agent on the AVP network.

    Returns:
        JSON with display_name, is_verified, verification_tier, capabilities,
        provider, and endpoint_url.
        Returns {"error": "Agent not found"} if DID is not registered.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get(f"/v1/agents/{did}")
            if r.status_code == 404:
                return json.dumps({"error": f"Agent {did} not found"})
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def search_agents(
    capability: Annotated[str, Field(description="Filter by capability. Examples: code_review, security_audit, translation, data_analysis. Empty returns all")] = "",
    provider: Annotated[str, Field(description="Filter by LLM provider. Examples: anthropic, openai, google, mistral. Empty returns all")] = "",
    min_reputation: Annotated[float, Field(description="Minimum reputation score 0.0-1.0. Set 0.5+ to exclude unproven agents. Default: 0.0")] = 0.0,
    limit: Annotated[int, Field(description="Maximum results to return, 1-100. Default: 10")] = 10,
) -> str:
    """Find AI agents by capability, provider, or minimum reputation score.

    Use this to discover available agents for a task before delegation.
    Results are sorted by reputation score (highest first).
    Combine filters to narrow results.

    Use get_agent_info when you already have a specific DID.
    Use check_reputation or check_trust to evaluate a found agent.

    Read-only — does not modify any data.

    Args:
        capability: Filter by published capability. Examples:
                    "code_review", "security_audit", "translation". Empty for all.
        provider: Filter by LLM provider. Examples: "anthropic", "openai". Empty for all.
        min_reputation: Minimum reputation score (0.0-1.0). Default 0.0 returns all.
        limit: Maximum number of results (1-100). Default 10.

    Returns:
        JSON list of matching agents with DID, display_name, capabilities,
        provider, and reputation score. Returns empty list if no matches.
    """
    try:
        import httpx
        params = {"limit": min(max(limit, 1), 100)}
        if capability:
            params["capability"] = capability
        if provider:
            params["provider"] = provider
        if min_reputation > 0:
            params["min_reputation"] = min_reputation
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get("/v1/cards", params=params)
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_attestations_received(
    did: Annotated[str, Field(description="Agent's DID to look up ratings for. Format: did:key:z6Mk...")],
) -> str:
    """Get peer ratings (attestations) received by an agent — who rated them and how.

    Returns individual ratings from other agents: who gave them, positive/negative,
    weight, and context. Use this to understand the evidence behind a score.

    NOT for protocol-level events — use get_audit_trail for registration, disputes, transfers.
    NOT for the computed score — use check_reputation for the final number.

    Read-only. Does not affect reputation or stored data.

    Args:
        did: Agent's DID (did:key:z6Mk...) to look up ratings for.

    Returns:
        JSON list of attestations (newest first) with from_agent_did,
        outcome, weight, context, and created_at.
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
    """Get network-wide aggregate statistics: total agents, attestations, and verified identities.

    Call this to answer "how big is the AVP network?" or "is the service active?"
    before registering a new agent. Returns counts, not individual agent data.

    NOT for individual agents — use check_reputation for a specific agent's score,
    or search_agents to find agents by capability.

    Read-only. No authentication required. No parameters.

    Returns:
        JSON with total_agents, total_attestations, verified_agents,
        total_cards, and protocol version.
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

    Checks that no audit entries have been tampered with by verifying
    the SHA-256 hash chain from genesis to the latest entry.

    Use this before relying on audit data for compliance or dispute resolution.
    For an individual agent's audit history, use get_audit_trail instead.

    Read-only — no authentication required. Safe to call at any time.

    Returns:
        JSON with is_valid (true/false), total_entries count, latest_hash,
        and verification timestamp. is_valid=false means tampering detected.
        Returns {"error": "..."} on network errors.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get("/v1/audit/verify")
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_audit_trail(
    did: Annotated[str, Field(description="Agent's DID to get audit history for. Format: did:key:z6Mk...")],
    limit: Annotated[int, Field(description="Maximum entries to return, 1-100. Newest first. Default: 20")] = 20,
) -> str:
    """Get the tamper-evident audit trail: every protocol action by this agent.

    Returns hash-chained events: registration, card publications, disputes,
    job actions. Each entry links cryptographically to the previous one.
    Use this for compliance, due diligence, or dispute evidence.

    NOT for peer ratings — use get_attestations_received for who rated this agent.
    Use verify_audit_chain to check integrity of the entire chain.

    Read-only. Public data, no authentication required.

    Args:
        did: Agent's DID (did:key:z6Mk...) to get audit history for.
        limit: Maximum entries (1-100). Default 20. Newest first.

    Returns:
        JSON list of audit entries with action type, timestamp,
        target DID, payload, and hash chain reference.
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
def register_agent(
    display_name: Annotated[str, Field(description="Human-readable name for the agent. Example: 'Code Reviewer'. If empty, uses AVP_AGENT_NAME env var")] = "",
) -> str:
    """Register a new AI agent on the Agent Veil Protocol network.

    Creates a cryptographic identity (Ed25519 keypair), generates a W3C DID,
    and registers the agent. Keys are saved locally to ~/.avp/agents/
    with restricted permissions (chmod 0600).

    IMPORTANT: Registration is irreversible. The DID becomes the agent's
    permanent identifier. Keys cannot be regenerated for the same DID —
    keep the local key file safe.

    Call this once before using write operations (submit_attestation,
    publish_agent_card). Use get_my_agent_info to verify setup afterward.

    Side effects: creates local key file, registers agent on the network.

    Args:
        display_name: Human-readable name (e.g. "Code Reviewer").
                      If empty, uses AVP_AGENT_NAME environment variable.

    Returns:
        JSON with the new agent's DID, display_name, registration status,
        and local key storage path.
        Returns {"error": "..."} if registration fails (network error, name conflict).
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
    to_did: Annotated[str, Field(description="DID of the agent being rated. Format: did:key:z6Mk... Cannot be your own DID")],
    outcome: Annotated[str, Field(description="Rating: 'positive' (performed well), 'negative' (performed poorly), or 'neutral' (no strong signal)")] = "positive",
    weight: Annotated[float, Field(description="Confidence in this rating, 0.0-1.0. Higher = more impact on target's score. Default: 0.9")] = 0.9,
    context: Annotated[str, Field(description="Interaction type. Examples: code_review, task_completion, data_accuracy. Empty for general")] = "",
) -> str:
    """Submit a peer attestation (rating) for another agent after an interaction.

    Records your evaluation of another agent's performance. This is the
    primary mechanism for building reputation on the network.

    IMPORTANT: Attestations are cryptographically signed and immutable —
    they cannot be modified or deleted after submission. Use the dispute
    system to contest unfair ratings received.

    Side effects: permanently modifies the target agent's attestation
    history and may change their computed reputation score.

    Requires a registered agent identity (call register_agent first).
    Self-attestation (rating yourself) is blocked.

    Args:
        to_did: DID of the agent being rated (did:key:z6Mk...).
        outcome: Must be "positive", "negative", or "neutral".
        weight: Confidence (0.0-1.0). Default 0.9.
        context: Interaction type for category-specific scoring. Empty for general.

    Returns:
        JSON with attestation ID, signature confirmation, and effective weight.
        Returns {"error": "Rate limited"} if limits exceeded.
        Returns {"error": "..."} on invalid input or network errors.
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
    capabilities: Annotated[str, Field(description="Comma-separated capabilities. Examples: 'code_review,security_audit,testing'. At least one required")],
    provider: Annotated[str, Field(description="LLM provider name. Examples: anthropic, openai, google, mistral. Optional")] = "",
    endpoint_url: Annotated[str, Field(description="HTTP endpoint for agent-to-agent interactions. Example: 'https://my-agent.example.com/api'. Optional")] = "",
) -> str:
    """Publish or update your agent's capability card for network discovery.

    Makes your agent discoverable by other agents using search_agents.

    IMPORTANT: This operation is idempotent — calling it again replaces
    the previous card entirely. The card becomes publicly visible to all
    agents on the network immediately.

    Requires a registered agent identity (call register_agent first).
    Use search_agents afterward to verify your card is discoverable.
    Use get_my_agent_info to check your current registration status.

    Side effects: creates or replaces your public capability card.
    No effect on other agents' data.

    Args:
        capabilities: Comma-separated capabilities. At least one required.
                      Examples: "code_review,security_audit,testing".
        provider: LLM provider powering this agent. Helps discovery filtering.
        endpoint_url: URL for receiving HTTP requests from other agents.

    Returns:
        JSON with card details: capabilities list, provider, endpoint,
        and confirmation. Returns {"error": "..."} if not registered
        or on invalid input.
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
    """Get YOUR agent's DID, registration status, and reputation — the locally configured agent only.

    Call this to verify your own setup before calling submit_attestation or publish_agent_card.
    Returns private details (public key, registration state) not available through get_agent_info.

    NOT for looking up other agents — use get_agent_info(did) for any agent by DID,
    or check_reputation(did) for another agent's trust score.

    No parameters. Uses the agent configured via AVP_AGENT_NAME environment variable.

    Read-only. Does not modify any data.

    Returns:
        JSON with did, public_key_hex, is_registered, is_verified,
        and current reputation (or "not yet scored").
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
