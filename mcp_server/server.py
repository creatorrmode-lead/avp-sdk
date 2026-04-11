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
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

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
def check_reputation(
    did: Annotated[str, Field(description="Agent's decentralized identifier in W3C DID format. Must start with 'did:key:z6Mk'. Example: 'did:key:z6MkhaXgBZDvotzkL...'")],
) -> str:
    """Check the reputation score and risk level of an AI agent.

    Use this BEFORE delegating a task to evaluate trustworthiness.
    For a quick yes/no trust decision, use check_trust instead.
    For detailed rating history, use get_attestations_received.

    The score is computed from peer attestations across the network.
    Higher scores mean a track record of successful interactions
    verified by multiple independent peers.

    Read-only — does not modify any data or affect the target agent's score.

    Args:
        did: The agent's decentralized identifier in W3C DID format.
             Must start with "did:key:z6Mk". Example: "did:key:z6MkhaXgBZDvotzkL..."

    Returns:
        JSON with score (0.0-1.0), confidence (0.0-1.0), risk_score (0.0-1.0),
        risk_factors (list of detected anomalies), tier (newcomer/basic/trusted/elite),
        and human-readable interpretation.
        Returns {"error": "Agent not found"} if DID is not registered.
        Returns {"error": "..."} on network or server errors.
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
    did: Annotated[str, Field(description="Agent's DID to evaluate. Format: did:key:z6Mk...")],
    min_tier: Annotated[str, Field(description="Minimum required trust tier. One of: newcomer, basic, trusted, elite. Default: trusted")] = "trusted",
    task_type: Annotated[str, Field(description="Optional task category for specialized scoring. Examples: code_quality, task_completion, data_accuracy")] = "",
) -> str:
    """Make a trust decision: should I delegate a task to this agent?

    Use this for a quick yes/no answer about whether to trust an agent.
    For detailed scores and risk factors, use check_reputation instead.
    For rating history, use get_attestations_received.

    Tiers from lowest to highest: newcomer, basic, trusted, elite.
    Agents with critical risk are always disallowed regardless of tier.

    Read-only — does not modify any data.

    IMPORTANT: This is an advisory signal, not a guarantee.

    Args:
        did: The agent's DID (did:key:z6Mk...)
        min_tier: Minimum required tier. One of: "newcomer", "basic", "trusted", "elite".
                  Default "trusted".
        task_type: Optional task category for specialized scoring.
                   Examples: "code_quality", "task_completion", "data_accuracy".

    Returns:
        JSON with allowed (true/false), score, tier, risk_level (low/medium/high/critical),
        reason (human-readable explanation), and disclaimer.
        Returns {"error": "..."} if DID not found or on network errors.
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
        agent = _get_agent()
        result = agent.get_agent_info(did)
        return json.dumps(result, indent=2)
    except AVPNotFoundError:
        return json.dumps({"error": f"Agent {did} not found"})
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
def get_attestations_received(
    did: Annotated[str, Field(description="Agent's DID to look up ratings for. Format: did:key:z6Mk...")],
) -> str:
    """Get all peer attestations (ratings) received by an agent.

    Shows the detailed history of how other agents rated this agent.
    Use this to understand WHY an agent has a particular score —
    not just the number, but the pattern of interactions.

    Use check_reputation for the computed trust score.
    Use check_trust for a simple yes/no delegation decision.

    Read-only — safe to call repeatedly. Does not affect the target
    agent's reputation or any stored data.

    Args:
        did: The agent's DID (did:key:z6Mk...) to look up ratings for.

    Returns:
        JSON list of attestations ordered by date (newest first).
        Each entry includes from_agent_did, outcome, weight, context,
        and created_at timestamp. Returns empty list if none found.
        Returns {"error": "..."} on network errors.
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

    Returns aggregate counts across the entire AVP network.
    No authentication required. No parameters needed.

    Use this to check network health or activity levels before registration.
    For individual agent data, use get_agent_info or check_reputation instead.

    Read-only — safe to call at any time without side effects.

    Returns:
        JSON with total_agents (registered), total_attestations (peer ratings),
        verified_agents (identity-verified), total_cards (published capabilities),
        and protocol version. Returns {"error": "..."} on network errors.
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
    """Get the chronological audit trail for a specific agent.

    Returns all recorded protocol actions: registration, attestations
    given/received, card publications, disputes, and more.
    Each entry is hash-linked to the previous one for tamper evidence.

    Use this for due diligence on a specific agent.
    Use verify_audit_chain to check integrity of the entire trail.
    No authentication required — audit data is public.

    Read-only — does not affect the agent or any stored data.

    Args:
        did: The agent's DID (did:key:z6Mk...) to get audit history for.
        limit: Maximum entries to return (1-100). Default 20. Newest first.

    Returns:
        JSON list of audit entries with action type, timestamp,
        target DID, payload details, and hash chain reference.
        Returns empty list if no entries found.
        Returns {"error": "..."} on network errors.
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
    """Get information about the currently configured AVP agent.

    Shows your own DID, registration status, verification level,
    and current reputation score. Use this to verify setup before
    calling write operations (submit_attestation, publish_agent_card).

    Unlike get_agent_info (which looks up any agent by DID), this
    returns your own agent's data including private registration details.

    No parameters — uses the agent configured via AVP_AGENT_NAME
    environment variable or the default "mcp_agent".

    Read-only — safe to call at any time without side effects.

    Returns:
        JSON with DID, public key, registration status, verification status,
        and current reputation score (or "not yet scored" if no attestations).
        Returns {"error": "..."} if agent configuration is missing or invalid.
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
