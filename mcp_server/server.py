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
    instructions="Trust & reputation layer for AI agents. Use these tools to register agents, check reputation scores, submit peer attestations, and discover agents by capability.",
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
    """Check the reputation score of an AI agent by their DID.

    Args:
        did: Agent's decentralized identifier (e.g. did:key:z6Mk...)

    Returns:
        Reputation score (0-1), confidence, and interpretation.
    """
    try:
        agent = _get_agent()
        result = agent.get_reputation(did)
        return json.dumps(result, indent=2)
    except AVPNotFoundError:
        return json.dumps({"error": f"Agent {did} not found"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_agent_info(did: str) -> str:
    """Get public information about an AI agent.

    Args:
        did: Agent's DID (did:key:z6Mk...)

    Returns:
        Agent details: display name, verification status, capabilities.
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
    """Search for AI agents by capability, provider, or minimum reputation.

    Args:
        capability: Filter by capability (e.g. "code_review", "translation")
        provider: Filter by LLM provider (e.g. "anthropic", "openai")
        min_reputation: Minimum reputation score (0.0-1.0)
        limit: Max results (1-100, default 10)

    Returns:
        List of matching agents with their capabilities and scores.
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
def verify_audit_chain() -> str:
    """Verify the integrity of AVP's immutable audit chain.

    Returns:
        Whether the chain is valid, number of entries, and latest hash.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get("/v1/audit/verify")
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_protocol_stats() -> str:
    """Get current AVP protocol statistics.

    Returns:
        Total agents, attestations, verified agents, escrows, and cards.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get("/v1/stats")
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_attestations_received(did: str) -> str:
    """Get all attestations (peer reviews) received by an agent.

    Args:
        did: Agent's DID

    Returns:
        List of attestations with outcome, weight, and context.
    """
    try:
        import httpx
        with httpx.Client(base_url=BASE_URL, timeout=15) as c:
            r = c.get(f"/v1/attestations/to/{did}")
            return json.dumps(r.json(), indent=2)
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_audit_trail(did: str, limit: int = 20) -> str:
    """Get the audit trail for an agent — all recorded actions.

    Args:
        did: Agent's DID
        limit: Max entries (1-100, default 20)

    Returns:
        Chronological list of audit events (register, attest, transfer, etc.)
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
    """Register a new AI agent on Agent Veil Protocol.
    Generates Ed25519 keys, creates a W3C DID, and registers on the network.

    Args:
        display_name: Human-readable name for the agent

    Returns:
        Agent DID and registration details.
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

    Args:
        to_did: DID of the agent being rated
        outcome: Rating — "positive", "negative", or "neutral"
        weight: Confidence weight (0.0-1.0, higher = more confident)
        context: Interaction type (e.g. "code_review", "task_completion")

    Returns:
        Attestation details including cryptographic signature.
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
        return json.dumps({"error": f"Rate limited: {e}"})
    except Exception as e:
        return _err(e)


@mcp.tool()
def publish_agent_card(
    capabilities: str,
    provider: str = "",
    endpoint_url: str = "",
) -> str:
    """Publish or update your agent's capability card for discovery.

    Args:
        capabilities: Comma-separated list (e.g. "code_review,security_audit,testing")
        provider: LLM provider (e.g. "anthropic", "openai", "google")
        endpoint_url: URL where this agent can be reached

    Returns:
        Published card details.
    """
    caps = [c.strip() for c in capabilities.split(",") if c.strip()]
    if not caps:
        return json.dumps({"error": "At least one capability is required"})

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

    Returns:
        Your agent's DID, registration status, and saved location.
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
    """Information about Agent Veil Protocol."""
    return json.dumps({
        "name": "Agent Veil Protocol (AVP)",
        "version": "0.1.0",
        "api": f"{BASE_URL}/docs",
        "explorer": f"{BASE_URL}/#explorer",
        "sdk": "pip install agentveil",
        "github": "https://github.com/creatorrmode-lead/avp-sdk",
        "features": [
            "W3C DID Identity (Ed25519)",
            "EigenTrust Reputation Algorithm",
            "Signed Peer-to-Peer Attestations",
            "Agent Cards (capability discovery)",
            "GitHub OAuth Verification",
            "IPFS-Anchored Audit Trail",
            "Escrow with Dispute Resolution",
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
