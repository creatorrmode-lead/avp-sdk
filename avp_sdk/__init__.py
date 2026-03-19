"""
AVP SDK — Python client for Agent Veil Protocol.

Usage:
    from avp_sdk import AVPAgent

    agent = AVPAgent.create("https://avp.example.com", name="MyAgent")
    agent.register()
    agent.publish_card(capabilities=["code_review", "testing"], provider="anthropic")

    rep = agent.get_reputation(other_agent_did)
    agent.attest(other_agent_did, outcome="positive", weight=0.9)
"""

from avp_sdk.agent import AVPAgent
from avp_sdk.exceptions import (
    AVPError,
    AVPAuthError,
    AVPNotFoundError,
    AVPRateLimitError,
    AVPInsufficientFundsError,
    AVPValidationError,
)

__version__ = "0.1.0"

__all__ = [
    "AVPAgent",
    "AVPError",
    "AVPAuthError",
    "AVPNotFoundError",
    "AVPRateLimitError",
    "AVPInsufficientFundsError",
    "AVPValidationError",
]
