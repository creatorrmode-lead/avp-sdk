"""
AVPAgent — main SDK class for interacting with Agent Veil Protocol.

Handles key management, authentication, registration, attestations,
and reputation queries.

Usage:
    agent = AVPAgent.create("https://avp.example.com", name="MyAgent")
    agent.register()

    agent.attest("did:key:z6Mk...", outcome="positive", weight=0.8)
    rep = agent.get_reputation("did:key:z6Mk...")
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional

import httpx
from nacl.signing import SigningKey, VerifyKey

from agentveil.auth import build_auth_header
from agentveil.pow import solve_pow
from agentveil.exceptions import (
    AVPError,
    AVPAuthError,
    AVPNotFoundError,
    AVPRateLimitError,
    AVPValidationError,
    AVPServerError,
)

log = logging.getLogger("agentveil")

# Default storage for agent keys
AGENTS_DIR = os.path.expanduser("~/.avp/agents")

# Multicodec prefix for Ed25519 public key
ED25519_MULTICODEC = bytes([0xED, 0x01])


def _public_key_to_did(public_key: bytes) -> str:
    """Convert Ed25519 public key to did:key."""
    import base58
    multicodec_key = ED25519_MULTICODEC + public_key
    encoded = base58.b58encode(multicodec_key).decode("ascii")
    return f"did:key:z{encoded}"


class AVPAgent:
    """
    AI agent identity on Agent Veil Protocol.

    Manages Ed25519 keys, signs requests, and provides methods
    for all AVP operations: registration, attestation, and reputation.
    """

    def __init__(
        self,
        base_url: str,
        private_key: bytes,
        name: str = "agent",
        timeout: float = 15.0,
    ):
        """
        Initialize agent with existing private key.
        Use AVPAgent.create() or AVPAgent.load() instead of calling directly.
        """
        self._base_url = base_url.rstrip("/")
        self._private_key = private_key
        self._name = name
        self._timeout = timeout

        # Derive public key and DID
        signing_key = SigningKey(private_key)
        self._public_key = bytes(signing_key.verify_key)
        self._did = _public_key_to_did(self._public_key)
        self._is_registered = False
        self._is_verified = False

    # === Factory methods ===

    @classmethod
    def create(cls, base_url: str = "", name: str = "agent", save: bool = True, mock: bool = False) -> "AVPAgent":
        """
        Create a new agent with fresh Ed25519 keys.

        Args:
            base_url: AVP server URL (e.g. "https://agentveil.dev"). Not needed if mock=True.
            name: Agent name (used for local key storage)
            save: Save keys to ~/.avp/agents/{name}.json
            mock: If True, return a mock agent that works without a server
        """
        if mock:
            from agentveil.mock import AVPMockAgent
            return AVPMockAgent.create(name=name)

        if not base_url:
            raise ValueError("base_url is required (or use mock=True for offline mode)")

        signing_key = SigningKey.generate()
        private_key = bytes(signing_key)
        agent = cls(base_url, private_key, name=name)
        if save:
            agent.save()
        log.info(f"Created new agent: {agent.did[:40]}...")
        return agent

    @classmethod
    def load(cls, base_url: str, name: str = "agent") -> "AVPAgent":
        """
        Load agent from saved keys.

        Args:
            base_url: AVP server URL
            name: Agent name (matches saved file)

        Raises:
            FileNotFoundError: If no saved agent with this name
        """
        path = os.path.join(AGENTS_DIR, f"{name}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No saved agent '{name}' at {path}")

        with open(path) as f:
            data = json.load(f)

        private_key = bytes.fromhex(data["private_key_hex"])
        agent = cls(base_url, private_key, name=name)
        agent._is_registered = data.get("registered", False)
        agent._is_verified = data.get("verified", False)
        log.info(f"Loaded agent: {agent.did[:40]}...")
        return agent

    @classmethod
    def from_private_key(cls, base_url: str, private_key_hex: str, name: str = "agent") -> "AVPAgent":
        """Create agent from hex-encoded private key."""
        return cls(base_url, bytes.fromhex(private_key_hex), name=name)

    # === Properties ===

    @property
    def did(self) -> str:
        """Agent's DID (did:key:z6Mk...)."""
        return self._did

    @property
    def public_key_hex(self) -> str:
        """Agent's public key as hex string."""
        return self._public_key.hex()

    @property
    def is_registered(self) -> bool:
        return self._is_registered

    @property
    def is_verified(self) -> bool:
        return self._is_verified

    # === Key management ===

    def save(self) -> str:
        """Save agent keys to disk. Returns file path."""
        os.makedirs(AGENTS_DIR, exist_ok=True)
        path = os.path.join(AGENTS_DIR, f"{self._name}.json")
        with open(path, "w") as f:
            json.dump({
                "name": self._name,
                "did": self._did,
                "public_key_hex": self._public_key.hex(),
                "private_key_hex": self._private_key.hex(),
                "registered": self._is_registered,
                "verified": self._is_verified,
                "base_url": self._base_url,
            }, f, indent=2)
        os.chmod(path, 0o600)  # Owner read/write only
        return path

    # === HTTP helpers ===

    def _auth_headers(self, method: str, path: str, body: bytes = b"") -> dict:
        """Build authenticated headers for a request."""
        return build_auth_header(self._private_key, self._did, method, path, body)

    def _handle_response(self, response: httpx.Response) -> dict:
        """Parse response and raise appropriate exceptions."""
        if response.status_code == 200:
            return response.json()

        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text

        if response.status_code == 401:
            raise AVPAuthError(f"Authentication failed: {detail}", 401, detail)
        elif response.status_code == 403:
            raise AVPAuthError(f"Forbidden: {detail}", 403, detail)
        elif response.status_code == 404:
            raise AVPNotFoundError(f"Not found: {detail}", 404, detail)
        elif response.status_code == 409:
            raise AVPValidationError(f"Conflict: {detail}", 409, detail)
        elif response.status_code == 429:
            raise AVPRateLimitError(f"Rate limited: {detail}")
        elif response.status_code == 400:
            raise AVPValidationError(f"Validation error: {detail}", 400, detail)
        elif response.status_code >= 500:
            raise AVPServerError(f"Server error: {detail}", response.status_code, detail)
        else:
            raise AVPError(f"Unexpected error ({response.status_code}): {detail}", response.status_code, detail)

    # === Registration ===

    def register(
        self,
        display_name: Optional[str] = None,
        capabilities: Optional[list[str]] = None,
        endpoint_url: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> dict:
        """
        Register agent on AVP and verify key ownership.
        Does register + PoW + verify in one call.

        If capabilities are provided, the agent card is auto-created
        and the onboarding pipeline starts immediately after verification.

        Args:
            display_name: Optional human-readable name
            capabilities: Agent capabilities (e.g. ["code_review", "testing"])
            endpoint_url: URL where this agent can be reached
            provider: LLM provider (e.g. "anthropic", "openai")

        Returns:
            dict with 'did' and 'agnet_address'
        """
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            # Step 1: Register (with optional card data)
            body = {
                "public_key_hex": self.public_key_hex,
                "display_name": display_name or self._name,
            }
            if capabilities:
                body["capabilities"] = capabilities
            if endpoint_url:
                body["endpoint_url"] = endpoint_url
            if provider:
                body["provider"] = provider

            r = c.post("/v1/agents/register", json=body)
            data = self._handle_response(r)
            challenge = data["challenge"]

            # Step 2: Solve Proof-of-Work puzzle
            pow_challenge = data["pow_challenge"]
            pow_difficulty = data["pow_difficulty"]
            log.info(f"Solving PoW (difficulty={pow_difficulty} bits)...")
            pow_nonce = solve_pow(pow_challenge, pow_difficulty)
            log.info(f"PoW solved: nonce={pow_nonce}")

            # Step 3: Sign challenge and verify
            signing_key = SigningKey(self._private_key)
            signed = signing_key.sign(challenge.encode())
            sig_hex = signed.signature.hex()

            r = c.post("/v1/agents/verify", json={
                "did": self._did,
                "challenge": challenge,
                "signature_hex": sig_hex,
                "pow_nonce": pow_nonce,
            })
            verify_data = self._handle_response(r)

        self._is_registered = True
        self._is_verified = True
        self.save()

        next_step = verify_data.get("next_step", "")
        if "Onboarding started" in next_step:
            log.info(f"Registered, verified, card published, onboarding started: {self._did[:40]}...")
        else:
            log.info(f"Registered and verified: {self._did[:40]}...")

        return data

    # === Agent Cards ===

    def publish_card(
        self,
        capabilities: list[str],
        provider: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        signature: Optional[str] = None,
    ) -> dict:
        """
        Publish or update agent's capability card.

        Args:
            capabilities: List of capabilities (e.g. ["code_review", "testing"])
            provider: LLM provider (e.g. "anthropic", "openai")
            endpoint_url: URL where this agent can be reached
            signature: Optional card signature
        """
        body_data = {"capabilities": capabilities}
        if provider:
            body_data["provider"] = provider
        if endpoint_url:
            body_data["endpoint_url"] = endpoint_url
        if signature:
            body_data["signature"] = signature

        body = json.dumps(body_data).encode()
        headers = self._auth_headers("POST", "/v1/cards", body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/cards", content=body, headers=headers)
            return self._handle_response(r)

    def search_agents(
        self,
        capability: Optional[str] = None,
        provider: Optional[str] = None,
        min_reputation: Optional[float] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search for agents by capability, provider, or minimum reputation."""
        params = {"limit": limit}
        if capability:
            params["capability"] = capability
        if provider:
            params["provider"] = provider
        if min_reputation is not None:
            params["min_reputation"] = min_reputation

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get("/v1/cards", params=params)
            return self._handle_response(r)

    # === Attestations ===

    def attest(
        self,
        to_did: str,
        outcome: str = "positive",
        weight: float = 1.0,
        context: Optional[str] = None,
        evidence_hash: Optional[str] = None,
        is_private: bool = False,
        interaction_id: Optional[str] = None,
    ) -> dict:
        """
        Submit an attestation about another agent.

        Args:
            to_did: DID of agent being rated
            outcome: "positive", "negative", or "neutral"
            weight: Confidence weight (0.0 to 1.0)
            context: Interaction type (e.g. "task_completion")
            evidence_hash: SHA256 of interaction log
            is_private: If True, attestation is not publicly visible
            interaction_id: Optional UUID linking to a specific interaction

        Returns:
            Attestation details
        """
        if outcome not in ("positive", "negative", "neutral"):
            raise AVPValidationError(f"Invalid outcome: {outcome}. Must be positive/negative/neutral")
        if not 0.0 <= weight <= 1.0:
            raise AVPValidationError(f"Weight must be 0.0-1.0, got {weight}")

        # Build and sign attestation payload
        attest_payload = json.dumps({
            "to": to_did,
            "outcome": outcome,
            "weight": weight,
            "context": context or "",
            "evidence_hash": evidence_hash or "",
        }, sort_keys=True, separators=(",", ":")).encode()

        signing_key = SigningKey(self._private_key)
        signed = signing_key.sign(attest_payload)
        sig_hex = signed.signature.hex()

        body_data = {
            "to_agent_did": to_did,
            "outcome": outcome,
            "weight": weight,
            "signature": sig_hex,
        }
        if context:
            body_data["context"] = context
        if evidence_hash:
            body_data["evidence_hash"] = evidence_hash
        if is_private:
            body_data["is_private"] = True
        if interaction_id:
            body_data["interaction_id"] = interaction_id

        body = json.dumps(body_data).encode()
        headers = self._auth_headers("POST", "/v1/attestations", body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/attestations", content=body, headers=headers)
            return self._handle_response(r)

    # === Reputation ===

    def get_reputation(self, did: Optional[str] = None) -> dict:
        """
        Get reputation score for an agent.

        Args:
            did: Agent DID (defaults to self)

        Returns:
            dict with score, confidence, interpretation
        """
        target = did or self._did
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/reputation/{target}")
            return self._handle_response(r)

    def get_reputation_tracks(self, did: Optional[str] = None) -> dict:
        """
        Get specialized reputation scores by track (category).

        Returns per-track scores derived from the attestation `context` field:
        code_quality, task_completion, data_accuracy, negotiation, general.

        Args:
            did: Agent DID (defaults to self)

        Returns:
            dict with did and tracks: {track_name: {score, confidence, attestations}}
        """
        target = did or self._did
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/reputation/{target}/tracks")
            return self._handle_response(r)

    def get_reputation_velocity(self, did: Optional[str] = None) -> dict:
        """
        Get reputation velocity — rate of score change over time.

        Returns deltas over 1d, 7d, 30d windows with trend classification
        and alert flags for sudden drops.

        Args:
            did: Agent DID (defaults to self)

        Returns:
            dict with current_score, velocity, trend, alert, alert_reason
        """
        target = did or self._did
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/reputation/{target}/velocity")
            return self._handle_response(r)

    def get_reputation_credential(
        self,
        did: Optional[str] = None,
        risk_level: str = "medium",
    ) -> dict:
        """
        Get a signed reputation credential for offline verification.

        The credential is signed by the AVP server's Ed25519 key and contains
        the agent's score, confidence, and an expiration time based on risk_level.

        Args:
            did: Agent DID (defaults to self)
            risk_level: "low" (60min TTL), "medium" (15min), "high" (5min).
                        "critical" is rejected — use get_reputation() instead.

        Returns:
            dict with did, score, confidence, issued_at, expires_at,
            ipfs_cid, risk_level, signature, signer_did
        """
        if risk_level not in ("low", "medium", "high", "critical"):
            raise AVPValidationError(
                f"Invalid risk_level: {risk_level}. Must be low/medium/high/critical"
            )
        target = did or self._did
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(
                f"/v1/reputation/{target}/credential",
                params={"risk_level": risk_level},
            )
            return self._handle_response(r)

    @staticmethod
    def verify_credential(credential: dict) -> bool:
        """
        Verify a reputation credential offline — no API call needed.

        Checks:
        1. Ed25519 signature is valid (signer_did → public key → verify)
        2. Credential has not expired (expires_at > now)
        3. DID field is present and non-empty

        Args:
            credential: The credential dict from get_reputation_credential()

        Returns:
            True if the credential is valid and not expired
        """
        import base58
        from datetime import datetime, timezone

        try:
            # Check required fields
            for field in ("did", "score", "confidence", "issued_at", "expires_at",
                          "risk_level", "signature", "signer_did"):
                if field not in credential:
                    return False

            # Check not expired
            expires_at = datetime.strptime(
                credential["expires_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return False

            # Extract public key from signer_did
            signer_did = credential["signer_did"]
            if not signer_did.startswith("did:key:z"):
                return False
            decoded = base58.b58decode(signer_did[9:])
            if len(decoded) < 2 or decoded[0] != 0xED or decoded[1] != 0x01:
                return False
            public_key = decoded[2:]
            if len(public_key) != 32:
                return False

            # Reconstruct the signed payload
            payload = {
                k: v for k, v in credential.items()
                if k not in ("signature", "signer_did")
            }
            message = json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode()

            # Verify Ed25519 signature
            signature = bytes.fromhex(credential["signature"])
            verify_key = VerifyKey(public_key)
            verify_key.verify(message, signature)
            return True
        except Exception:
            return False

    def get_agent_info(self, did: Optional[str] = None) -> dict:
        """Get public info about an agent."""
        target = did or self._did
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/agents/{target}")
            return self._handle_response(r)

    # === Verification ===

    def verify_email(self, email: str) -> dict:
        """
        Start email verification. Sends OTP code to the given email.

        Args:
            email: Email address to verify

        Returns:
            dict with message and expires_in
        """
        body = json.dumps({"email": email}).encode()
        headers = self._auth_headers("POST", "/v1/verify/email", body)
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/verify/email", content=body, headers=headers)
            return self._handle_response(r)

    def confirm_email(self, otp: str) -> dict:
        """
        Confirm email OTP code. Upgrades to EMAIL tier (0.3x trust boost).

        Args:
            otp: 6-digit verification code from email

        Returns:
            dict with verified, tier, trust_boost
        """
        body = json.dumps({"otp": otp}).encode()
        headers = self._auth_headers("POST", "/v1/verify/email/confirm", body)
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/verify/email/confirm", content=body, headers=headers)
            return self._handle_response(r)

    def verify_moltbook(self, moltbook_username: str) -> dict:
        """
        Request Moltbook verification. Bot will check your profile and upgrade tier.

        Args:
            moltbook_username: Your Moltbook username

        Returns:
            dict with message and status
        """
        body = json.dumps({"moltbook_username": moltbook_username}).encode()
        headers = self._auth_headers("POST", "/v1/verify/moltbook", body)
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/verify/moltbook", content=body, headers=headers)
            return self._handle_response(r)

    def get_verification_status(self, did: Optional[str] = None) -> dict:
        """
        Check verification status for an agent.

        Args:
            did: Agent DID (defaults to self)

        Returns:
            dict with did, tier, trust_boost, verified_at
        """
        target = did or self._did
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/verify/status/{target}")
            return self._handle_response(r)

    # === Utility ===

    def health(self) -> dict:
        """Check AVP server health."""
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get("/v1/health")
            return self._handle_response(r)

    def __repr__(self) -> str:
        status = "verified" if self._is_verified else ("registered" if self._is_registered else "new")
        return f"AVPAgent(name={self._name}, did={self._did[:35]}..., status={status})"
