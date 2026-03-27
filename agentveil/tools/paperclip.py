"""
Paperclip integration for Agent Veil Protocol.

Provides AVP trust tools as Paperclip plugin-compatible functions that agents
in a Paperclip company can use to check reputation, verify delegation targets,
log interaction results, and evaluate agent teams.

Paperclip is an open-source orchestration platform for zero-human companies.
It coordinates multiple AI agents with org charts, budgets, and heartbeat
scheduling — but has no built-in trust or reputation layer. AVP fills this gap.

Usage as standalone functions:
    from agentveil.tools.paperclip import (
        avp_check_reputation,
        avp_should_delegate,
        avp_log_interaction,
        avp_evaluate_team,
        avp_heartbeat_report,
        configure,
    )

    configure(base_url="https://agentveil.dev", agent_name="paperclip_ceo")
    result = avp_check_reputation(did="did:key:z6Mk...")

Usage as Paperclip plugin tool definitions:
    from agentveil.tools.paperclip import avp_plugin_tools

    tools = avp_plugin_tools()
    # Register tools with Paperclip plugin SDK
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from agentveil.agent import AVPAgent

log = logging.getLogger("agentveil.tools.paperclip")

# Module-level agent cache
_agents: dict[str, AVPAgent] = {}

AVP_BASE_URL = "https://agentveil.dev"
AVP_AGENT_NAME = "paperclip_agent"


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


# --- Core tool functions ---


def avp_check_reputation(did: str) -> str:
    """Check an AI agent's reputation on Agent Veil Protocol.

    Paperclip agents have no built-in reputation system. This tool queries
    AVP to get trust scores before delegating work to other agents.

    Args:
        did: The DID (did:key:z6Mk...) of the agent to check.

    Returns:
        JSON string with score, confidence, interpretation, and attestation count.
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


def avp_should_delegate(did: str, min_score: float = 0.5) -> str:
    """Decide whether to delegate a task to an agent based on AVP reputation.

    In Paperclip, the CEO agent delegates tasks to subordinates without
    verifying their reliability. This tool adds a trust gate — check an
    agent's reputation before assigning work.

    Args:
        did: The DID of the agent to evaluate.
        min_score: Minimum reputation score (0.0-1.0) to approve delegation.

    Returns:
        JSON string with delegation decision and reasoning.
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


def avp_log_interaction(
    did: str, outcome: str = "positive", context: str = "paperclip_task"
) -> str:
    """Log an interaction result with another agent as a signed attestation.

    After a Paperclip heartbeat completes, agents can record whether their
    collaborators performed well. This builds reputation over time and
    enables trust-based delegation in future heartbeats.

    Args:
        did: The DID of the agent you interacted with.
        outcome: Interaction outcome: 'positive', 'negative', or 'neutral'.
        context: Context of the interaction (e.g. 'code_review', 'content_writing').

    Returns:
        JSON string confirming the attestation was recorded.
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


# --- Paperclip-specific tools ---


def avp_evaluate_team(dids: list[str]) -> str:
    """Evaluate trust scores for an entire Paperclip agent team.

    Paperclip companies have org charts with multiple agents. This tool
    batch-checks reputation for all agents in a team, identifies the
    weakest link, and provides an overall team trust assessment.

    Args:
        dids: List of DIDs for all agents in the company/team.

    Returns:
        JSON string with per-agent scores and team summary.
    """
    try:
        agent = _get_agent()
        results = []
        total_score = 0.0
        lowest_score = 1.0
        lowest_agent = ""

        for did in dids:
            try:
                rep = agent.get_reputation(did)
                score = rep.get("score", 0.0)
                confidence = rep.get("confidence", 0.0)
                results.append({
                    "did": did,
                    "score": score,
                    "confidence": confidence,
                    "interpretation": rep.get("interpretation", "unknown"),
                })
                total_score += score
                if score < lowest_score:
                    lowest_score = score
                    lowest_agent = did
            except Exception as e:
                results.append({
                    "did": did,
                    "score": 0.0,
                    "confidence": 0.0,
                    "interpretation": "unknown",
                    "error": str(e),
                })

        team_avg = total_score / len(dids) if dids else 0.0

        return json.dumps({
            "team_size": len(dids),
            "average_score": round(team_avg, 3),
            "lowest_score": round(lowest_score, 3),
            "lowest_agent": lowest_agent,
            "agents": results,
        }, indent=2)
    except Exception as e:
        return f"Error evaluating team: {e}"


def avp_heartbeat_report(
    agent_did: str,
    peers_evaluated: Optional[list[dict]] = None,
) -> str:
    """Generate a trust report for a Paperclip heartbeat cycle.

    Call this at the end of each heartbeat to produce a trust summary.
    Optionally include peer evaluations from this heartbeat to automatically
    submit attestations.

    Args:
        agent_did: DID of the agent running this heartbeat.
        peers_evaluated: Optional list of dicts with keys:
            - did: peer agent DID
            - outcome: 'positive', 'negative', or 'neutral'
            - context: interaction context string

    Returns:
        JSON string with self-reputation, peer attestation results, and velocity.
    """
    try:
        agent = _get_agent()

        # Get own reputation and velocity
        own_rep = agent.get_reputation(agent_did)
        try:
            velocity = agent.get_reputation_velocity(agent_did)
        except Exception:
            velocity = {}

        report = {
            "agent_did": agent_did,
            "own_reputation": {
                "score": own_rep.get("score", 0.0),
                "confidence": own_rep.get("confidence", 0.0),
                "interpretation": own_rep.get("interpretation", "unknown"),
            },
            "velocity": {
                "trend": velocity.get("trend", "unknown"),
                "alert": velocity.get("alert", False),
                "alert_reason": velocity.get("alert_reason", ""),
            },
            "peer_attestations": [],
        }

        # Submit attestations for peers evaluated in this heartbeat
        if peers_evaluated:
            for peer in peers_evaluated:
                try:
                    result = agent.attest(
                        to_did=peer["did"],
                        outcome=peer.get("outcome", "positive"),
                        weight=0.8,
                        context=peer.get("context", "paperclip_heartbeat"),
                    )
                    report["peer_attestations"].append({
                        "did": peer["did"],
                        "outcome": peer.get("outcome", "positive"),
                        "status": "recorded",
                    })
                except Exception as e:
                    report["peer_attestations"].append({
                        "did": peer["did"],
                        "outcome": peer.get("outcome", "positive"),
                        "status": f"error: {e}",
                    })

        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Error generating heartbeat report: {e}"


# --- Paperclip Plugin tool definitions ---


def avp_plugin_tools() -> list[dict]:
    """Return Paperclip plugin-compatible tool definitions for AVP.

    These definitions follow the Paperclip Plugin SDK format.
    Register them in your plugin's tool manifest.

    Returns:
        List of tool definition dicts.
    """
    return [
        {
            "name": "avp_check_reputation",
            "description": (
                "Check an AI agent's trust score on Agent Veil Protocol. "
                "Returns score (0-1), confidence, and interpretation. "
                "Use before delegating tasks to verify agent reliability."
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
            "handler": "avp_check_reputation",
        },
        {
            "name": "avp_should_delegate",
            "description": (
                "Decide whether to delegate a task to an agent based on their "
                "AVP reputation. Returns yes/no decision with reasoning."
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
                        "description": "Minimum reputation score (0.0-1.0)",
                        "default": 0.5,
                    },
                },
                "required": ["did"],
            },
            "handler": "avp_should_delegate",
        },
        {
            "name": "avp_log_interaction",
            "description": (
                "Log an interaction with another agent as a signed attestation. "
                "Record positive, negative, or neutral outcomes after task completion."
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
                        "description": "Context (e.g. 'code_review', 'content_writing')",
                    },
                },
                "required": ["did"],
            },
            "handler": "avp_log_interaction",
        },
        {
            "name": "avp_evaluate_team",
            "description": (
                "Batch-check trust scores for all agents in a Paperclip company. "
                "Returns per-agent scores, team average, and weakest link."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of agent DIDs to evaluate",
                    },
                },
                "required": ["dids"],
            },
            "handler": "avp_evaluate_team",
        },
        {
            "name": "avp_heartbeat_report",
            "description": (
                "Generate a trust report at the end of a Paperclip heartbeat cycle. "
                "Includes own reputation, velocity trend, and optional peer attestations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_did": {
                        "type": "string",
                        "description": "DID of the agent running this heartbeat",
                    },
                    "peers_evaluated": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "did": {"type": "string"},
                                "outcome": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                                "context": {"type": "string"},
                            },
                            "required": ["did"],
                        },
                        "description": "Optional peer evaluations from this heartbeat",
                    },
                },
                "required": ["agent_did"],
            },
            "handler": "avp_heartbeat_report",
        },
    ]


def handle_avp_tool_call(function_name: str, arguments: dict) -> str:
    """Execute an AVP tool call by name. Used by Paperclip plugin handler.

    Args:
        function_name: Tool name from avp_plugin_tools().
        arguments: Parsed arguments dict.

    Returns:
        JSON string with the result.
    """
    handlers = {
        "avp_check_reputation": lambda args: avp_check_reputation(args["did"]),
        "avp_should_delegate": lambda args: avp_should_delegate(
            args["did"], args.get("min_score", 0.5)
        ),
        "avp_log_interaction": lambda args: avp_log_interaction(
            args["did"],
            args.get("outcome", "positive"),
            args.get("context", "paperclip_task"),
        ),
        "avp_evaluate_team": lambda args: avp_evaluate_team(args["dids"]),
        "avp_heartbeat_report": lambda args: avp_heartbeat_report(
            args["agent_did"],
            args.get("peers_evaluated"),
        ),
    }

    handler = handlers.get(function_name)
    if handler:
        try:
            return handler(arguments)
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": f"Unknown function: {function_name}"})
