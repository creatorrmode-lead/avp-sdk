"""
LangGraph integration for Agent Veil Protocol.

Provides AVP tools as LangChain-compatible tools for LangGraph agent workflows.

Usage:
    from agentveil.tools.langgraph import avp_check_reputation, avp_should_delegate, avp_log_interaction

    from langgraph.prebuilt import ToolNode
    tool_node = ToolNode([avp_check_reputation, avp_should_delegate, avp_log_interaction])
"""

from __future__ import annotations

import json
import logging

from agentveil.agent import AVPAgent

log = logging.getLogger("agentveil.tools.langgraph")

try:
    from langchain_core.tools import tool
except ImportError:
    raise ImportError(
        "langchain-core is required for AVP LangGraph tools. "
        "Install with: pip install langchain-core langgraph"
    )

# Module-level agent cache
_agents: dict[str, AVPAgent] = {}

AVP_BASE_URL = "https://agentveil.dev"
AVP_AGENT_NAME = "langgraph_agent"


def _get_agent(base_url: str = AVP_BASE_URL, name: str = AVP_AGENT_NAME) -> AVPAgent:
    """Get or create a cached AVPAgent instance."""
    key = f"{base_url}:{name}"
    if key not in _agents:
        try:
            _agents[key] = AVPAgent.load(base_url, name=name)
        except Exception:
            _agents[key] = AVPAgent.create(base_url, name=name)
            _agents[key].register()
    return _agents[key]


def configure(base_url: str = AVP_BASE_URL, agent_name: str = AVP_AGENT_NAME) -> None:
    """Configure default AVP URL and agent name for all tools."""
    global AVP_BASE_URL, AVP_AGENT_NAME
    AVP_BASE_URL = base_url
    AVP_AGENT_NAME = agent_name


@tool
def avp_check_reputation(did: str) -> str:
    """Check an AI agent's reputation on Agent Veil Protocol.

    Use this to verify an agent's trustworthiness before delegating work.
    Returns trust score (0-1), confidence level, and interpretation.

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


@tool
def avp_should_delegate(did: str, min_score: float = 0.5) -> str:
    """Decide whether to delegate a task to an AI agent based on their AVP reputation.

    Returns a yes/no decision with the agent's score and reasoning.

    Args:
        did: The DID (did:key:z6Mk...) of the agent to evaluate.
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


@tool
def avp_log_interaction(did: str, outcome: str = "positive", context: str = "langgraph_task") -> str:
    """Log an interaction result with another AI agent on Agent Veil Protocol.

    After working with an agent, record the outcome as a signed attestation.
    This builds the agent's reputation over time.

    Args:
        did: The DID (did:key:z6Mk...) of the agent you interacted with.
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
