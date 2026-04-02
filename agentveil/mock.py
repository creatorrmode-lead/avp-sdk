"""
AVPMockAgent — offline mock for testing and demos.

Works without a running AVP server. All crypto (keys, DIDs, signing)
is real — only HTTP calls are mocked with realistic responses.

Usage:
    from agentveil import AVPAgent
    agent = AVPAgent.create(mock=True)
    agent.register()                     # instant, no server
    rep = agent.get_reputation()         # returns mock data
    agent.attest("did:key:z6Mk...", outcome="positive")
"""

import time
import uuid
import hashlib
import logging
from typing import Optional

from nacl.signing import SigningKey

from agentveil.agent import AVPAgent, _public_key_to_did

log = logging.getLogger("agentveil.mock")


class AVPMockAgent(AVPAgent):
    """
    Mock AVP agent that works without a server.

    All methods return realistic data. Keys and DIDs are real Ed25519.
    Use for testing, demos, and CI pipelines.
    """

    def __init__(self, private_key: bytes, name: str = "agent"):
        # Initialize with a dummy base_url — never used
        super().__init__(
            base_url="mock://localhost",
            private_key=private_key,
            name=name,
            timeout=0,
        )
        self._mock_attestations = []
        self._mock_reputation = 0.75

    @classmethod
    def create(cls, name: str = "agent", **kwargs) -> "AVPMockAgent":
        """Create a mock agent with fresh keys. No disk writes."""
        signing_key = SigningKey.generate()
        agent = cls(bytes(signing_key), name=name)
        log.info(f"Created mock agent: {agent.did[:40]}...")
        return agent

    def save(self) -> str:
        """No-op — mock agents don't write to disk."""
        return "/dev/null"

    # === Registration (mock) ===

    def register(
        self,
        display_name: Optional[str] = None,
        capabilities: Optional[list[str]] = None,
        endpoint_url: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> dict:
        self._is_registered = True
        self._is_verified = True
        log.info(f"Mock registered: {self._did[:40]}...")
        return {
            "did": self._did,
            "agent_address": f"0xMOCK{self._public_key.hex()[:8]}",
            "challenge": "mock-challenge",
        }

    # === Agent Cards (mock) ===

    def publish_card(
        self,
        capabilities: list[str],
        provider: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ) -> dict:
        return {
            "card_id": f"mock-card-{uuid.uuid4().hex[:8]}",
            "did": self._did,
            "capabilities": capabilities,
            "provider": provider,
            "endpoint_url": endpoint_url,
        }

    def search_agents(
        self,
        capability: Optional[str] = None,
        provider: Optional[str] = None,
        min_reputation: Optional[float] = None,
        limit: int = 20,
    ) -> list[dict]:
        # Generate two fake peer agents
        peer1_key = SigningKey.generate()
        peer2_key = SigningKey.generate()
        peer1_did = _public_key_to_did(bytes(peer1_key.verify_key))
        peer2_did = _public_key_to_did(bytes(peer2_key.verify_key))

        return [
            {
                "did": peer1_did,
                "display_name": "MockAgent-Alpha",
                "capabilities": [capability or "general"],
                "provider": provider or "anthropic",
                "reputation_score": 0.85,
            },
            {
                "did": peer2_did,
                "display_name": "MockAgent-Beta",
                "capabilities": [capability or "general"],
                "provider": provider or "openai",
                "reputation_score": 0.72,
            },
        ]

    # === Attestations (mock) ===

    def attest(
        self,
        to_did: str,
        outcome: str = "positive",
        weight: float = 1.0,
        context: Optional[str] = None,
        evidence_hash: Optional[str] = None,
    ) -> dict:
        if outcome not in ("positive", "negative", "neutral"):
            from agentveil.exceptions import AVPValidationError
            raise AVPValidationError(f"Invalid outcome: {outcome}", 400, "")
        if not 0.0 <= weight <= 1.0:
            from agentveil.exceptions import AVPValidationError
            raise AVPValidationError(f"Weight must be 0.0-1.0, got {weight}", 400, "")

        att_id = f"mock-att-{uuid.uuid4().hex[:8]}"
        self._mock_attestations.append({
            "id": att_id,
            "from_did": self._did,
            "to_did": to_did,
            "outcome": outcome,
            "weight": weight,
            "context": context,
        })

        # Adjust mock reputation based on attestation
        if outcome == "positive":
            self._mock_reputation = min(1.0, self._mock_reputation + 0.02 * weight)
        elif outcome == "negative":
            self._mock_reputation = max(0.0, self._mock_reputation - 0.05 * weight)

        return {
            "attestation_id": att_id,
            "from_did": self._did,
            "to_did": to_did,
            "outcome": outcome,
            "weight": weight,
            "ipfs_cid": f"QmMOCK{uuid.uuid4().hex[:16]}",
        }

    # === Reputation (mock) ===

    def get_reputation(self, did: Optional[str] = None) -> dict:
        score = self._mock_reputation
        confidence = min(0.9, 0.1 + len(self._mock_attestations) * 0.15)
        if score >= 0.8:
            interpretation = "excellent"
        elif score >= 0.6:
            interpretation = "good"
        elif score >= 0.4:
            interpretation = "neutral"
        else:
            interpretation = "poor"
        return {
            "did": did or self._did,
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "interpretation": interpretation,
            "total_attestations": len(self._mock_attestations),
        }

    def get_reputation_tracks(self, did: Optional[str] = None) -> dict:
        base = self._mock_reputation
        return {
            "did": did or self._did,
            "tracks": {
                "code_quality": {"score": round(base + 0.05, 4), "confidence": 0.6},
                "task_completion": {"score": round(base, 4), "confidence": 0.5},
                "data_accuracy": {"score": round(base - 0.03, 4), "confidence": 0.4},
                "negotiation": {"score": round(base + 0.02, 4), "confidence": 0.3},
                "general": {"score": round(base, 4), "confidence": 0.5},
            },
        }

    def get_reputation_velocity(self, did: Optional[str] = None) -> dict:
        return {
            "did": did or self._did,
            "current_score": round(self._mock_reputation, 4),
            "velocity": {"1d": 0.02, "7d": 0.05, "30d": 0.08},
            "trend": "improving",
            "alert": False,
            "alert_reason": None,
        }

    def get_reputation_credential(
        self, did: Optional[str] = None, risk_level: str = "medium"
    ) -> dict:
        if risk_level == "critical":
            from agentveil.exceptions import AVPValidationError
            raise AVPValidationError("Critical risk: use get_reputation() instead", 400, "")

        ttl_map = {"low": 3600, "medium": 900, "high": 300}
        ttl = ttl_map.get(risk_level, 900)
        now = int(time.time())

        target_did = did or self._did
        payload = f"{target_did}:{self._mock_reputation}:{now}"
        signing_key = SigningKey(self._private_key)
        sig = signing_key.sign(payload.encode()).signature.hex()

        return {
            "did": target_did,
            "score": round(self._mock_reputation, 4),
            "issued_at": now,
            "expires_at": now + ttl,
            "issuer_did": self._did,
            "signature_hex": sig,
            "ipfs_cid": f"QmMOCK{uuid.uuid4().hex[:16]}",
            "risk_level": risk_level,
        }

    # === Agent Info (mock) ===

    def get_agent_info(self, did: Optional[str] = None) -> dict:
        return {
            "did": did or self._did,
            "display_name": self._name,
            "registered_at": "2026-01-01T00:00:00Z",
            "verification_tier": "did",
            "status": "active",
        }

    # === Health (mock) ===

    def health(self) -> dict:
        return {"status": "ok", "mode": "mock", "version": "0.3.0"}

    def __repr__(self) -> str:
        status = "verified" if self._is_verified else "registered" if self._is_registered else "new"
        return f"AVPMockAgent(name={self._name!r}, did={self._did[:30]}..., status={status})"
