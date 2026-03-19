"""
AVPAgent — main SDK class for interacting with Agent Veil Protocol.

Handles key management, authentication, registration, attestations,
reputation queries, payments, and escrow.

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

from avp_sdk.auth import build_auth_header
from avp_sdk.exceptions import (
    AVPError,
    AVPAuthError,
    AVPNotFoundError,
    AVPRateLimitError,
    AVPInsufficientFundsError,
    AVPValidationError,
    AVPServerError,
)

log = logging.getLogger("avp_sdk")

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
    for all AVP operations: registration, attestation, reputation,
    payments, and escrow.
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
    def create(cls, base_url: str, name: str = "agent", save: bool = True) -> "AVPAgent":
        """
        Create a new agent with fresh Ed25519 keys.

        Args:
            base_url: AVP server URL (e.g. "https://avp.example.com")
            name: Agent name (used for local key storage)
            save: Save keys to ~/.avp/agents/{name}.json
        """
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
            if "Insufficient" in str(detail):
                raise AVPInsufficientFundsError(f"Insufficient funds: {detail}", 400, detail)
            raise AVPValidationError(f"Validation error: {detail}", 400, detail)
        elif response.status_code >= 500:
            raise AVPServerError(f"Server error: {detail}", response.status_code, detail)
        else:
            raise AVPError(f"Unexpected error ({response.status_code}): {detail}", response.status_code, detail)

    # === Registration ===

    def register(self, display_name: Optional[str] = None) -> dict:
        """
        Register agent on AVP and verify key ownership.
        Does both steps (register + verify) in one call.

        Args:
            display_name: Optional human-readable name

        Returns:
            dict with 'did' and 'agnet_address'
        """
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            # Step 1: Register
            r = c.post("/v1/agents/register", json={
                "public_key_hex": self.public_key_hex,
                "display_name": display_name or self._name,
            })
            data = self._handle_response(r)
            challenge = data["challenge"]

            # Step 2: Sign challenge and verify
            signing_key = SigningKey(self._private_key)
            signed = signing_key.sign(challenge.encode())
            sig_hex = signed.signature.hex()

            r = c.post("/v1/agents/verify", json={
                "did": self._did,
                "challenge": challenge,
                "signature_hex": sig_hex,
            })
            self._handle_response(r)

        self._is_registered = True
        self._is_verified = True
        self.save()
        log.info(f"Registered and verified: {self._did[:40]}...")
        return data

    # === Agent Cards ===

    def publish_card(
        self,
        capabilities: list[str],
        provider: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ) -> dict:
        """
        Publish or update agent's capability card.

        Args:
            capabilities: List of capabilities (e.g. ["code_review", "testing"])
            provider: LLM provider (e.g. "anthropic", "openai")
            endpoint_url: URL where this agent can be reached
        """
        body_data = {"capabilities": capabilities}
        if provider:
            body_data["provider"] = provider
        if endpoint_url:
            body_data["endpoint_url"] = endpoint_url

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
    ) -> dict:
        """
        Submit an attestation about another agent.

        Args:
            to_did: DID of agent being rated
            outcome: "positive", "negative", or "neutral"
            weight: Confidence weight (0.0 to 1.0)
            context: Interaction type (e.g. "task_completion")
            evidence_hash: SHA256 of interaction log

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

    def get_agent_info(self, did: Optional[str] = None) -> dict:
        """Get public info about an agent."""
        target = did or self._did
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/agents/{target}")
            return self._handle_response(r)

    # === Payments ===

    def get_balance(self, did: Optional[str] = None) -> dict:
        """Get agent's balance (internal + Agnet)."""
        target = did or self._did
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/payments/balance/{target}")
            return self._handle_response(r)

    def transfer(self, to_did: str, amount_nagn: int, memo: Optional[str] = None) -> dict:
        """
        Transfer funds to another agent.

        Args:
            to_did: Recipient DID
            amount_nagn: Amount in nAGN (1 AGN = 1,000,000 nAGN)
            memo: Optional memo
        """
        body_data = {"to_agent_did": to_did, "amount_nagn": amount_nagn}
        if memo:
            body_data["memo"] = memo

        body = json.dumps(body_data).encode()
        headers = self._auth_headers("POST", "/v1/payments/transfer", body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/payments/transfer", content=body, headers=headers)
            return self._handle_response(r)

    # === Escrow ===

    def create_escrow(
        self,
        payee_did: str,
        amount_nagn: int,
        ttl_hours: int = 24,
        memo: Optional[str] = None,
    ) -> dict:
        """
        Create an escrow — hold funds until interaction completes.

        Args:
            payee_did: Agent who will receive funds on success
            amount_nagn: Amount to hold
            ttl_hours: Hours before auto-refund (1-168)
            memo: Optional memo
        """
        body_data = {
            "payee_did": payee_did,
            "amount_nagn": amount_nagn,
            "ttl_hours": ttl_hours,
        }
        if memo:
            body_data["memo"] = memo

        body = json.dumps(body_data).encode()
        headers = self._auth_headers("POST", "/v1/payments/escrow", body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/payments/escrow", content=body, headers=headers)
            return self._handle_response(r)

    def release_escrow(self, escrow_id: str) -> dict:
        """Release escrow — send funds to payee. Only payee can call this."""
        body_data = {"escrow_id": escrow_id, "action": "release"}
        body = json.dumps(body_data).encode()
        headers = self._auth_headers("POST", "/v1/payments/escrow/resolve", body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/payments/escrow/resolve", content=body, headers=headers)
            return self._handle_response(r)

    def refund_escrow(self, escrow_id: str) -> dict:
        """Refund escrow — return funds to payer. Only payer can call this."""
        body_data = {"escrow_id": escrow_id, "action": "refund"}
        body = json.dumps(body_data).encode()
        headers = self._auth_headers("POST", "/v1/payments/escrow/resolve", body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/payments/escrow/resolve", content=body, headers=headers)
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
