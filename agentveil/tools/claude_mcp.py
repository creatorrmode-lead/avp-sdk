"""
Claude MCP Server for Agent Veil Protocol.

Runs as an MCP (Model Context Protocol) server that Claude Desktop/Code
can connect to. Exposes AVP reputation tools as MCP tools.

Usage:
    python -m agentveil.tools.claude_mcp

Config for claude_desktop_config.json:
    {
      "mcpServers": {
        "agentveil": {
          "command": "python",
          "args": ["-m", "agentveil.tools.claude_mcp"],
          "env": {
            "AVP_BASE_URL": "https://agentveil.dev",
            "AVP_AGENT_NAME": "claude_agent"
          }
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
import os
import sys

from agentveil.agent import AVPAgent

log = logging.getLogger("agentveil.tools.claude_mcp")

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "mcp is required for AVP Claude MCP server. "
        "Install with: pip install mcp"
    )

# Configuration from environment
AVP_BASE_URL = os.environ.get("AVP_BASE_URL", "https://agentveil.dev")
AVP_AGENT_NAME = os.environ.get("AVP_AGENT_NAME", "claude_agent")

# Agent cache
_agent: AVPAgent | None = None


def _get_agent() -> AVPAgent:
    """Get or create a cached AVPAgent instance."""
    global _agent
    if _agent is None:
        try:
            _agent = AVPAgent.load(AVP_BASE_URL, name=AVP_AGENT_NAME)
        except Exception:
            _agent = AVPAgent.create(AVP_BASE_URL, name=AVP_AGENT_NAME)
            _agent.register()
    return _agent


# --- MCP Server ---

mcp = FastMCP("agentveil")


@mcp.tool()
async def check_avp_reputation(did: str) -> str:
    """Check an AI agent's reputation on Agent Veil Protocol.

    Returns trust score (0-1), confidence level, and interpretation.
    Use this to verify an agent before delegating work.

    Args:
        did: The DID (did:key:z6Mk...) of the agent to check.
    """
    try:
        agent = _get_agent()
        rep = agent.get_reputation(did)
        return json.dumps({
            "did": did,
            "score": rep.get("score", 0.0),
            "confidence": rep.get("confidence", 0.0),
            "interpretation": rep.get("interpretation", "unknown"),
            "total_attestations": rep.get("total_attestations", 0),
        }, indent=2)
    except Exception as e:
        return f"Error checking reputation: {e}"


@mcp.tool()
async def should_delegate_to_agent(did: str, min_score: float = 0.5) -> str:
    """Decide whether to delegate a task to an AI agent based on their AVP reputation.

    Returns a delegation decision with the agent's score and reasoning.

    Args:
        did: The DID of the agent to evaluate.
        min_score: Minimum reputation score (0.0-1.0) to approve delegation.
    """
    try:
        agent = _get_agent()
        rep = agent.get_reputation(did)
        score = rep.get("score", 0.0)
        confidence = rep.get("confidence", 0.0)
        interpretation = rep.get("interpretation", "unknown")

        should_delegate = score >= min_score and confidence > 0.1
        reason = (
            f"Score {score:.2f} >= {min_score:.2f} threshold, "
            f"confidence {confidence:.2f}, rated '{interpretation}'"
            if should_delegate
            else f"Score {score:.2f} < {min_score:.2f} threshold "
            f"or low confidence ({confidence:.2f})"
        )

        return json.dumps({
            "delegate": should_delegate,
            "did": did,
            "score": score,
            "confidence": confidence,
            "min_score": min_score,
            "reason": reason,
        }, indent=2)
    except Exception as e:
        return f"Error evaluating agent: {e}"


@mcp.tool()
async def log_avp_interaction(
    did: str, outcome: str = "positive", context: str = "claude_task"
) -> str:
    """Log an interaction result with another AI agent on Agent Veil Protocol.

    Record positive, negative, or neutral outcomes as signed attestations.
    This builds the agent's reputation over time.

    Args:
        did: The DID of the agent you interacted with.
        outcome: Interaction outcome: 'positive', 'negative', or 'neutral'.
        context: Context of the interaction (e.g. 'code_review', 'research').
    """
    try:
        agent = _get_agent()
        result = agent.attest(
            to_did=did,
            outcome=outcome,
            weight=0.8,
            context=context,
        )
        return json.dumps({
            "status": "recorded",
            "to_did": did,
            "outcome": result.get("outcome", outcome),
            "weight": result.get("weight", 0.8),
            "context": context,
        }, indent=2)
    except Exception as e:
        return f"Error logging interaction: {e}"


@mcp.tool()
async def search_avp_agents(
    capability: str = "", provider: str = "", min_reputation: float = 0.0
) -> str:
    """Search for AI agents on Agent Veil Protocol by capability or provider.

    Returns a list of agents with their DIDs, capabilities, and reputation scores.

    Args:
        capability: Filter by capability (e.g. 'code_review', 'research').
        provider: Filter by LLM provider (e.g. 'anthropic', 'openai').
        min_reputation: Minimum reputation score (0.0-1.0).
    """
    try:
        agent = _get_agent()
        results = agent.search_agents(
            capability=capability or None,
            provider=provider or None,
            min_reputation=min_reputation or None,
        )
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error searching agents: {e}"


def main():
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
