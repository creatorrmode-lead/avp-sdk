"""
CrewAI integration for Agent Veil Protocol.

Provides AVPReputationTool — a CrewAI-compatible tool that lets agents
check reputation, decide on delegation, and log interaction results.

Usage:
    from agentveil.tools.crewai import AVPReputationTool

    tool = AVPReputationTool(base_url="https://agentveil.dev")
    researcher = Agent(role="Researcher", tools=[tool])
"""

from __future__ import annotations

import json
import logging
from typing import Type

from pydantic import BaseModel, Field

from agentveil.agent import AVPAgent

log = logging.getLogger("agentveil.tools.crewai")

try:
    from crewai.tools import BaseTool
except ImportError:
    raise ImportError(
        "crewai is required for AVP CrewAI tools. Install with: pip install crewai"
    )


# --- Input Schemas ---

class CheckReputationInput(BaseModel):
    """Input for checking an agent's reputation."""
    did: str = Field(..., description="The DID (did:key:z6Mk...) of the agent to check.")


class ShouldDelegateInput(BaseModel):
    """Input for deciding whether to delegate to an agent."""
    did: str = Field(..., description="The DID of the agent to evaluate.")
    min_score: float = Field(
        default=0.5,
        description="Minimum reputation score (0.0-1.0) to approve delegation.",
    )


class LogInteractionInput(BaseModel):
    """Input for logging an interaction result as an attestation."""
    did: str = Field(..., description="The DID of the agent you interacted with.")
    outcome: str = Field(
        default="positive",
        description="Interaction outcome: 'positive', 'negative', or 'neutral'.",
    )
    context: str = Field(
        default="crewai_task",
        description="Context of the interaction (e.g. 'code_review', 'research').",
    )


# --- Tools ---

class AVPReputationTool(BaseTool):
    """Check an agent's reputation score on Agent Veil Protocol.

    Returns the agent's trust score, confidence level, and interpretation.
    Use this before delegating tasks to unknown agents.
    """

    name: str = "check_avp_reputation"
    description: str = (
        "Check an AI agent's reputation on Agent Veil Protocol. "
        "Provide a DID (did:key:z6Mk...) to get the agent's trust score (0-1), "
        "confidence level, and whether they are trustworthy. "
        "Use this to verify an agent before delegating work."
    )
    args_schema: Type[BaseModel] = CheckReputationInput

    base_url: str = "https://agentveil.dev"
    agent_name: str = "crewai_agent"
    _agent: AVPAgent | None = None

    class Config:
        arbitrary_types_allowed = True

    def _get_agent(self) -> AVPAgent:
        if self._agent is None:
            try:
                self._agent = AVPAgent.load(self.base_url, name=self.agent_name)
            except Exception:
                self._agent = AVPAgent.create(self.base_url, name=self.agent_name)
                self._agent.register()
        return self._agent

    def _run(self, did: str) -> str:
        try:
            agent = self._get_agent()
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


class AVPDelegationTool(BaseTool):
    """Decide whether to delegate a task to an agent based on their reputation.

    Returns a clear yes/no decision with the agent's score and reasoning.
    """

    name: str = "should_delegate_to_agent"
    description: str = (
        "Decide whether to delegate a task to an AI agent based on their "
        "Agent Veil Protocol reputation. Provide the agent's DID and a minimum "
        "acceptable score (default 0.5). Returns a delegation decision with reasoning."
    )
    args_schema: Type[BaseModel] = ShouldDelegateInput

    base_url: str = "https://agentveil.dev"
    agent_name: str = "crewai_agent"
    _agent: AVPAgent | None = None

    class Config:
        arbitrary_types_allowed = True

    def _get_agent(self) -> AVPAgent:
        if self._agent is None:
            try:
                self._agent = AVPAgent.load(self.base_url, name=self.agent_name)
            except Exception:
                self._agent = AVPAgent.create(self.base_url, name=self.agent_name)
                self._agent.register()
        return self._agent

    def _run(self, did: str, min_score: float = 0.5) -> str:
        try:
            agent = self._get_agent()
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


class AVPAttestationTool(BaseTool):
    """Log an interaction result as a signed attestation on Agent Veil Protocol.

    Use this after completing a task with another agent to record
    whether the interaction was positive, negative, or neutral.
    """

    name: str = "log_avp_interaction"
    description: str = (
        "Log an interaction result with another AI agent on Agent Veil Protocol. "
        "After working with an agent, record whether the outcome was "
        "'positive', 'negative', or 'neutral'. This builds the agent's reputation."
    )
    args_schema: Type[BaseModel] = LogInteractionInput

    base_url: str = "https://agentveil.dev"
    agent_name: str = "crewai_agent"
    _agent: AVPAgent | None = None

    class Config:
        arbitrary_types_allowed = True

    def _get_agent(self) -> AVPAgent:
        if self._agent is None:
            try:
                self._agent = AVPAgent.load(self.base_url, name=self.agent_name)
            except Exception:
                self._agent = AVPAgent.create(self.base_url, name=self.agent_name)
                self._agent.register()
        return self._agent

    def _run(self, did: str, outcome: str = "positive", context: str = "crewai_task") -> str:
        try:
            agent = self._get_agent()
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
