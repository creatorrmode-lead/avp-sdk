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
from datetime import datetime, timedelta, timezone
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
        """
        Initialize mock agent with a private key.

        Uses a dummy base_url since no real HTTP calls are made.
        Reputation starts at 0.75 with an empty attestation list.

        Args:
            private_key: Ed25519 private key bytes
            name: Agent name for identification
        """
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
        """
        Mock registration — instantly marks agent as registered and verified.

        No HTTP call or Proof-of-Work is performed. Always succeeds.

        Args:
            display_name: Optional human-readable name (ignored in mock)
            capabilities: Agent capabilities (ignored in mock)
            endpoint_url: URL where this agent can be reached (ignored in mock)
            provider: LLM provider (ignored in mock)

        Returns:
            dict with 'did', 'agent_address', and 'challenge'
        """
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
        """
        Mock publish — returns a fake card without contacting the server.

        Args:
            capabilities: List of capabilities (e.g. ["code_review", "testing"])
            provider: LLM provider (e.g. "anthropic", "openai")
            endpoint_url: URL where this agent can be reached

        Returns:
            dict with 'card_id', 'did', 'capabilities', 'provider', 'endpoint_url'
        """
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
        """
        Mock search — returns two fake peer agents with realistic data.

        Args:
            capability: Filter by capability name
            provider: Filter by LLM provider
            min_reputation: Minimum reputation score (unused in mock)
            limit: Max results to return (unused in mock, always returns 2)

        Returns:
            list of dicts, each with 'did', 'display_name', 'capabilities',
            'provider', and 'reputation_score'
        """
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
        """
        Mock attestation — records locally and adjusts mock reputation.

        Validates outcome and weight, stores the attestation in memory,
        and adjusts the mock reputation score accordingly.

        Args:
            to_did: DID of agent being rated
            outcome: "positive", "negative", or "neutral"
            weight: Attestation weight (0.0 to 1.0)
            context: Optional context description
            evidence_hash: Optional hash of supporting evidence

        Returns:
            dict with 'attestation_id', 'from_did', 'to_did', 'outcome',
            'weight', and 'ipfs_cid'

        Raises:
            AVPValidationError: If outcome is invalid or weight out of range
        """
        from agentveil.exceptions import AVPValidationError

        if outcome not in ("positive", "negative", "neutral"):
            raise AVPValidationError(f"Invalid outcome: {outcome}", 400, "")
        if not 0.0 <= weight <= 1.0:
            raise AVPValidationError(f"Weight must be 0.0-1.0, got {weight}", 400, "")
        # B3: mirror server + live SDK validation for negative attestations.
        if outcome == "negative":
            missing = []
            if not context:
                missing.append("context")
            if not evidence_hash:
                missing.append("evidence_hash")
            if missing:
                raise AVPValidationError(
                    f"Negative attestations require {' and '.join(missing)}. "
                    f"Pass context and evidence_hash (sha256 hex of the interaction log).",
                    400, "",
                )
            import re as _re
            if not _re.match(r"^[a-f0-9]{64}$", evidence_hash):
                raise AVPValidationError(
                    "evidence_hash must be lowercase SHA-256 hex (64 chars).",
                    400, "",
                )

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

    def attest_batch(self, attestations: list[dict]) -> dict:
        """
        Mock batch attestation — submits multiple attestations in one call.

        Each attestation dict should contain 'to_did' and optionally
        'outcome', 'weight', 'context', 'evidence_hash'.

        Args:
            attestations: List of 1-50 attestation dicts

        Returns:
            dict with 'total', 'succeeded', 'failed', and 'results'

        Raises:
            AVPValidationError: If batch is empty or exceeds 50 items
        """
        if not attestations or len(attestations) > 50:
            from agentveil.exceptions import AVPValidationError
            raise AVPValidationError("Batch must contain 1-50 attestations", 400, "")

        results = []
        succeeded = 0
        for idx, att in enumerate(attestations):
            single = self.attest(
                to_did=att["to_did"],
                outcome=att.get("outcome", "positive"),
                weight=att.get("weight", 1.0),
                context=att.get("context"),
                evidence_hash=att.get("evidence_hash"),
            )
            results.append({"index": idx, "success": True, "attestation": single})
            succeeded += 1

        return {
            "total": len(attestations),
            "succeeded": succeeded,
            "failed": 0,
            "results": results,
        }

    # === Reputation (mock) ===

    def get_reputation(self, did: Optional[str] = None) -> dict:
        """
        Mock reputation query — returns locally tracked mock score.

        Confidence increases with each attestation submitted.

        Args:
            did: DID of agent to query (defaults to self)

        Returns:
            dict with 'did', 'score', 'confidence', 'interpretation',
            and 'total_attestations'
        """
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

    def get_reputation_bulk(self, dids: list[str]) -> dict:
        """
        Mock bulk reputation query — returns mock scores for multiple DIDs.

        Args:
            dids: List of 1-100 DIDs to query

        Returns:
            dict with 'total', 'found', and 'results' (each with 'did',
            'found', 'reputation')

        Raises:
            AVPValidationError: If list is empty or exceeds 100 items
        """
        if not dids or len(dids) > 100:
            from agentveil.exceptions import AVPValidationError
            raise AVPValidationError("Bulk query requires 1-100 DIDs", 400, "")

        results = []
        for d in dids:
            rep = self.get_reputation(d)
            results.append({"did": d, "found": True, "reputation": rep})

        return {
            "total": len(dids),
            "found": len(dids),
            "results": results,
        }

    def get_reputation_tracks(self, did: Optional[str] = None) -> dict:
        """
        Mock reputation by track — returns per-category mock scores.

        Tracks: code_quality, task_completion, data_accuracy, negotiation, general.
        Each track is derived from the base mock reputation with small offsets.

        Args:
            did: DID of agent to query (defaults to self)

        Returns:
            dict with 'did' and 'tracks' mapping track names to
            {'score': float, 'confidence': float}
        """
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
        """
        Mock reputation velocity — returns fake trend data.

        Always returns "improving" trend with no alerts.

        Args:
            did: DID of agent to query (defaults to self)

        Returns:
            dict with 'did', 'current_score', 'velocity' (1d/7d/30d),
            'trend', 'alert', and 'alert_reason'
        """
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
        """
        Mock signed reputation credential — returns a verifiable credential.

        Produces a real Ed25519 signature over the credential payload.
        TTL varies by risk_level: low=1h, medium=15m, high=5m.

        Args:
            did: DID of agent to credential (defaults to self)
            risk_level: "low", "medium", or "high" (affects TTL)

        Returns:
            dict with 'did', 'score', 'confidence', 'issued_at', 'expires_at',
            'signer_did', 'signature', 'ipfs_cid', 'risk_level'

        Raises:
            AVPValidationError: If risk_level is "critical"
        """
        if risk_level == "critical":
            from agentveil.exceptions import AVPValidationError
            raise AVPValidationError("Critical risk: use get_reputation() instead", 400, "")

        ttl_map = {"low": 3600, "medium": 900, "high": 300}
        ttl = ttl_map.get(risk_level, 900)
        now = int(time.time())

        target_did = did or self._did
        now_dt = datetime.now(timezone.utc)
        issued_str = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        expires_str = (now_dt + timedelta(seconds=ttl)).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = f"{target_did}:{self._mock_reputation}:{now}"
        signing_key = SigningKey(self._private_key)
        sig = signing_key.sign(payload.encode()).signature.hex()

        return {
            "did": target_did,
            "score": round(self._mock_reputation, 4),
            "confidence": 0.5,
            "issued_at": issued_str,
            "expires_at": expires_str,
            "signer_did": self._did,
            "signature": sig,
            "ipfs_cid": f"QmMOCK{uuid.uuid4().hex[:16]}",
            "risk_level": risk_level,
        }

    # === Verification (mock) ===

    def verify_email(self, email: str) -> dict:
        """
        Mock email verification — always succeeds immediately.

        Args:
            email: Email address to verify (ignored in mock)

        Returns:
            dict with 'message' and 'expires_in'
        """
        return {"message": "Verification email sent", "expires_in": 600}

    def confirm_email(self, otp: str) -> dict:
        """
        Mock email confirmation — always succeeds regardless of OTP.

        Args:
            otp: One-time password from verification email (ignored in mock)

        Returns:
            dict with 'verified', 'tier', and 'trust_boost'
        """
        return {"verified": True, "tier": "email", "trust_boost": 0.3}

    def verify_moltbook(self, moltbook_username: str) -> dict:
        """
        DEPRECATED — Moltbook is a legacy / compatibility surface.

        Mirrors :meth:`AVPAgent.verify_moltbook`: the call still succeeds,
        but a real Moltbook verification grants NONE-equivalent trust
        (0.1x). Use ``verify_email`` or GitHub verification instead.

        Args:
            moltbook_username: Moltbook username to verify (ignored in mock)

        Returns:
            dict with 'message' and 'status'
        """
        import warnings

        warnings.warn(
            "AVPMockAgent.verify_moltbook is deprecated: Moltbook is a legacy "
            "compatibility surface and grants NONE-equivalent trust (0.1x).",
            DeprecationWarning,
            stacklevel=2,
        )
        return {"message": "Moltbook verification requested", "status": "pending"}

    def get_verification_status(self, did: Optional[str] = None) -> dict:
        """
        Mock verification status — always returns DID-only tier.

        Args:
            did: DID to check (defaults to self)

        Returns:
            dict with 'did', 'tier', 'trust_boost', and 'verified_at'
        """
        return {
            "did": did or self._did,
            "tier": "did",
            "trust_boost": 0.0,
            "verified_at": None,
        }

    # === Onboarding (mock) ===

    def get_onboarding_challenge(self) -> Optional[dict]:
        """
        Mock onboarding challenge — returns a fake capability description challenge.

        Returns:
            dict with 'challenge_id', 'challenge_text', 'challenge_type',
            'target_capability', 'deadline', and 'status'
        """
        return {
            "challenge_id": f"mock-challenge-{uuid.uuid4().hex[:8]}",
            "challenge_text": "Describe your primary capability in 2-3 sentences.",
            "challenge_type": "capability_description",
            "target_capability": "general",
            "deadline": "2099-01-01T00:00:00Z",
            "status": "pending",
        }

    def submit_challenge_answer(self, challenge_id: str, answer: str) -> dict:
        """
        Mock challenge submission — always passes with a high score.

        Args:
            challenge_id: ID of the challenge to answer
            answer: Challenge response text (ignored in mock)

        Returns:
            dict with 'challenge_id', 'score', 'passed', 'reasoning',
            and 'pipeline_status'
        """
        return {
            "challenge_id": challenge_id,
            "score": 0.85,
            "passed": True,
            "reasoning": "Mock evaluation: answer meets requirements",
            "pipeline_status": "completed",
        }

    def get_onboarding_status(self) -> dict:
        """
        Mock onboarding status — reflects verification state.

        Returns:
            dict with 'did', 'status', 'stages_completed', and 'stages_total'
        """
        return {
            "did": self._did,
            "status": "completed" if self._is_verified else "pending",
            "stages_completed": 4 if self._is_verified else 0,
            "stages_total": 4,
        }

    # === Agent Info (mock) ===

    def get_agent_info(self, did: Optional[str] = None) -> dict:
        """
        Mock agent info — returns basic agent metadata.

        Args:
            did: DID of agent to query (defaults to self)

        Returns:
            dict with 'did', 'display_name', 'registered_at',
            'verification_tier', and 'status'
        """
        return {
            "did": did or self._did,
            "display_name": self._name,
            "registered_at": "2026-01-01T00:00:00Z",
            "verification_tier": "did",
            "status": "active",
        }

    # === Health (mock) ===

    def health(self) -> dict:
        """
        Mock health check — always returns ok.

        Returns:
            dict with 'status', 'mode', and 'version'
        """
        return {"status": "ok", "mode": "mock", "version": "0.7.10"}

    def __repr__(self) -> str:
        status = "verified" if self._is_verified else "registered" if self._is_registered else "new"
        return f"AVPMockAgent(name={self._name!r}, did={self._did[:30]}..., status={status})"
