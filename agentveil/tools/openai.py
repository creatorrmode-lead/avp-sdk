"""
OpenAI integration for Agent Veil Protocol.

Provides AVP tool definitions and handlers for OpenAI function calling.

Usage:
    from agentveil.tools.openai import avp_tool_definitions, handle_avp_tool_call, configure

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=avp_tool_definitions(),
    )
"""

from __future__ import annotations

import json
import logging

from agentveil.agent import AVPAgent

log = logging.getLogger("agentveil.tools.openai")

# Module-level agent cache
_agents: dict[str, AVPAgent] = {}

AVP_BASE_URL = "https://agentveil.dev"
AVP_AGENT_NAME = "openai_agent"


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


def avp_tool_definitions() -> list[dict]:
    """Return OpenAI-compatible tool definitions for AVP functions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "check_avp_reputation",
                "description": (
                    "Check an AI agent's reputation on Agent Veil Protocol. "
                    "Returns trust score (0-1), confidence level, and interpretation."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "did": {
                            "type": "string",
                            "description": "The DID (did:key:z6Mk...) of the agent to check",
                        },
                    },
                    "required": ["did"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "should_delegate_to_agent",
                "description": (
                    "Decide whether to delegate a task to an AI agent based on their "
                    "AVP reputation. Returns yes/no with reasoning."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "did": {
                            "type": "string",
                            "description": "The DID of the agent to evaluate",
                        },
                        "min_score": {
                            "type": "number",
                            "description": "Minimum reputation score (0.0-1.0) to approve delegation",
                            "default": 0.5,
                        },
                    },
                    "required": ["did"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "log_avp_interaction",
                "description": (
                    "Log an interaction result with another AI agent on AVP. "
                    "Record positive, negative, or neutral outcomes as signed attestations."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "did": {
                            "type": "string",
                            "description": "The DID of the agent you interacted with",
                        },
                        "outcome": {
                            "type": "string",
                            "enum": ["positive", "negative", "neutral"],
                            "description": "Interaction outcome",
                        },
                        "context": {
                            "type": "string",
                            "description": "Context of the interaction (e.g. 'code_review')",
                        },
                    },
                    "required": ["did"],
                },
            },
        },
    ]


def handle_avp_tool_call(function_name: str, arguments: dict) -> str:
    """
    Execute an AVP tool call and return the result as a JSON string.

    Use this in your OpenAI function calling loop to handle AVP tool calls.

    Args:
        function_name: The function name from tool_call.function.name
        arguments: The parsed arguments from tool_call.function.arguments

    Returns:
        JSON string with the result
    """
    try:
        agent = _get_agent()

        if function_name == "check_avp_reputation":
            did = arguments["did"]
            rep = agent.get_reputation(did)
            return json.dumps({
                "did": did,
                "score": rep.get("score", 0.0),
                "confidence": rep.get("confidence", 0.0),
                "interpretation": rep.get("interpretation", "unknown"),
                "total_attestations": rep.get("total_attestations", 0),
            }, indent=2)

        elif function_name == "should_delegate_to_agent":
            did = arguments["did"]
            min_score = arguments.get("min_score", 0.5)
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

        elif function_name == "log_avp_interaction":
            did = arguments["did"]
            outcome = arguments.get("outcome", "positive")
            context = arguments.get("context", "openai_task")
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

        else:
            return json.dumps({"error": f"Unknown function: {function_name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})
