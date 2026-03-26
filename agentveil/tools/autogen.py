"""
AutoGen integration for Agent Veil Protocol.

Provides AVP functions wrapped as FunctionTool for Microsoft AutoGen agents.

Usage:
    from agentveil.tools.autogen import avp_reputation_tools, configure

    configure(base_url="https://agentveil.dev", agent_name="my_agent")
    tools = avp_reputation_tools()
    # Pass tools to AssistantAgent(tools=tools)
"""

from __future__ import annotations

import json
import logging
from typing import Annotated

from agentveil.agent import AVPAgent

log = logging.getLogger("agentveil.tools.autogen")

try:
    from autogen_core.tools import FunctionTool
except ImportError:
    raise ImportError(
        "autogen-core is required for AVP AutoGen tools. "
        "Install with: pip install autogen-core"
    )

# Module-level agent cache
_agents: dict[str, AVPAgent] = {}

AVP_BASE_URL = "https://agentveil.dev"
AVP_AGENT_NAME = "autogen_agent"


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


# --- Tool functions ---

def check_avp_reputation(
    did: Annotated[str, "The DID (did:key:z6Mk...) of the agent to check"],
) -> str:
    """Check an AI agent's reputation on Agent Veil Protocol.
    Returns trust score, confidence level, and interpretation."""
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


def should_delegate_to_agent(
    did: Annotated[str, "The DID of the agent to evaluate"],
    min_score: Annotated[float, "Minimum reputation score (0.0-1.0) to approve delegation"] = 0.5,
) -> str:
    """Decide whether to delegate a task to an agent based on their AVP reputation.
    Returns a delegation decision with reasoning."""
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


def log_avp_interaction(
    did: Annotated[str, "The DID of the agent you interacted with"],
    outcome: Annotated[str, "Interaction outcome: 'positive', 'negative', or 'neutral'"] = "positive",
    context: Annotated[str, "Context of the interaction (e.g. 'code_review')"] = "autogen_task",
) -> str:
    """Log an interaction result with another AI agent as a signed attestation on AVP.
    This builds the agent's reputation over time."""
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


# --- FunctionTool wrappers ---

def avp_reputation_tools() -> list:
    """Return a list of AVP FunctionTool instances for AutoGen agents."""
    return [
        FunctionTool(
            check_avp_reputation,
            description="Check an AI agent's reputation on Agent Veil Protocol. "
            "Provide a DID to get trust score, confidence, and interpretation.",
        ),
        FunctionTool(
            should_delegate_to_agent,
            description="Decide whether to delegate a task to an AI agent based on "
            "their AVP reputation. Returns yes/no with reasoning.",
        ),
        FunctionTool(
            log_avp_interaction,
            description="Log an interaction result with another AI agent on AVP. "
            "Record positive, negative, or neutral outcomes as signed attestations.",
        ),
    ]
