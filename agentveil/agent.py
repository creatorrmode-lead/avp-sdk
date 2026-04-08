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

        # Warn if using unencrypted HTTP for non-localhost connections
        if self._base_url.startswith("http://") and "localhost" not in self._base_url and "127.0.0.1" not in self._base_url:
            log.warning(
                "Using HTTP without TLS. Signatures and keys may be intercepted. "
                "Use https:// in production."
            )

        # Derive public key and DID
        signing_key = SigningKey(private_key)
        self._public_key = bytes(signing_key.verify_key)
        self._did = _public_key_to_did(self._public_key)
        self._is_registered = False
        self._is_verified = False
        self._saved_to_disk = False

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
        else:
            log.warning(
                f"Agent {agent.did[:30]}... created with save=False. "
                f"Private key exists only in memory — if the process crashes before "
                f"register() or save(), this agent is lost. Use agent.private_key_hex "
                f"to back up, or agent.save() to persist."
            )
        log.info(f"Created new agent: {agent.did[:40]}...")
        return agent

    @classmethod
    def load(cls, base_url: str, name: str = "agent", passphrase: Optional[str] = None) -> "AVPAgent":
        """
        Load agent from saved keys.

        Args:
            base_url: AVP server URL
            name: Agent name (matches saved file)
            passphrase: Required if the saved file was encrypted with a passphrase

        Raises:
            FileNotFoundError: If no saved agent with this name
            ValueError: If file is encrypted but no passphrase provided
        """
        path = os.path.join(AGENTS_DIR, f"{name}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No saved agent '{name}' at {path}")

        with open(path) as f:
            data = json.load(f)

        if data.get("encrypted"):
            if not passphrase:
                raise ValueError(
                    f"Agent '{name}' is encrypted. Provide passphrase to load."
                )
            from nacl.pwhash import argon2id
            from nacl.secret import SecretBox

            salt = bytes.fromhex(data["encryption_salt"])
            key = argon2id.kdf(
                SecretBox.KEY_SIZE,
                passphrase.encode(),
                salt,
                opslimit=argon2id.OPSLIMIT_MODERATE,
                memlimit=argon2id.MEMLIMIT_MODERATE,
            )
            box = SecretBox(key)
            encrypted = bytes.fromhex(data["private_key_encrypted"])
            private_key = bytes(box.decrypt(encrypted))
        else:
            private_key = bytes.fromhex(data["private_key_hex"])

        agent = cls(base_url, private_key, name=name)
        agent._is_registered = data.get("registered", False)
        agent._is_verified = data.get("verified", False)
        agent._saved_to_disk = True
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
    def private_key_hex(self) -> str:
        """Agent's private key as hex string. Use to back up key for later recovery via from_private_key()."""
        return self._private_key.hex()

    @property
    def is_registered(self) -> bool:
        return self._is_registered

    @property
    def is_verified(self) -> bool:
        return self._is_verified

    # === Key management ===

    def save(self, passphrase: Optional[str] = None) -> str:
        """
        Save agent keys to disk. Returns file path.

        Args:
            passphrase: If provided, encrypts the private key using NaCl SecretBox
                        with a key derived from the passphrase via scrypt.
                        If None, private key is stored as plaintext hex (0o600 permissions).
        """
        os.makedirs(AGENTS_DIR, exist_ok=True)
        path = os.path.join(AGENTS_DIR, f"{self._name}.json")

        data = {
            "name": self._name,
            "did": self._did,
            "public_key_hex": self._public_key.hex(),
            "registered": self._is_registered,
            "verified": self._is_verified,
            "base_url": self._base_url,
        }

        if passphrase:
            from nacl.pwhash import argon2id
            from nacl.secret import SecretBox
            from nacl.utils import random as nacl_random

            salt = nacl_random(argon2id.SALTBYTES)
            key = argon2id.kdf(
                SecretBox.KEY_SIZE,
                passphrase.encode(),
                salt,
                opslimit=argon2id.OPSLIMIT_MODERATE,
                memlimit=argon2id.MEMLIMIT_MODERATE,
            )
            box = SecretBox(key)
            encrypted = box.encrypt(self._private_key)
            data["private_key_encrypted"] = encrypted.hex()
            data["encryption_salt"] = salt.hex()
            data["encrypted"] = True
        else:
            data["private_key_hex"] = self._private_key.hex()
            data["encrypted"] = False
            log.warning(
                "Saving private key unencrypted. Use save(passphrase='...') for encrypted storage."
            )

        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(path, 0o600)  # Owner read/write only
        self._saved_to_disk = True
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

        onboarding_started = verify_data.get("onboarding_started", False)
        next_step = verify_data.get("next_step", "")

        if onboarding_started or "Onboarding started" in next_step:
            log.info(f"Registered, verified, card published, onboarding started: {self._did[:40]}...")
            self._auto_handle_onboarding_challenge()
        else:
            log.warning(
                f"Registered and verified but onboarding NOT started: "
                f"no capabilities were provided. Call agent.publish_card("
                f"capabilities=[...], provider='...') to start onboarding. "
                f"Server response: {next_step}"
            )

        return data

    def _auto_handle_onboarding_challenge(self, max_wait: float = 30.0) -> None:
        """
        Poll for an onboarding challenge and auto-submit an answer.
        Best-effort, non-fatal: if anything fails, registration still succeeds.
        Challenge generation involves LLM call and may take 5-15s after Stage 1.
        """
        import time

        # Initial delay: Stage 1 runs fast but LLM challenge generation takes 5-10s
        time.sleep(3.0)

        deadline = time.monotonic() + max_wait

        try:
            challenge = None
            while time.monotonic() < deadline:
                challenge = self.get_onboarding_challenge()
                if challenge and challenge.get("status") == "awaiting_response":
                    break
                time.sleep(2.0)

            if not challenge or challenge.get("status") != "awaiting_response":
                log.debug("Auto-challenge: no active challenge found, skipping")
                return

            challenge_id = challenge.get("challenge_id", "")
            challenge_text = challenge.get("challenge_text", "")

            if not challenge_id or not challenge_text:
                return

            answer = (
                f"Responding to challenge: {challenge_text[:200]}\n\n"
                f"I am an AI agent with capabilities in this domain. "
                f"This is an automated response from the AVP SDK register() flow. "
                f"My capabilities are registered in my agent card."
            )

            result = self.submit_challenge_answer(challenge_id, answer)
            log.info(
                f"Auto-challenge: score={result.get('score', '?')}, "
                f"passed={result.get('passed', '?')}"
            )
        except Exception as e:
            log.debug(f"Auto-challenge handling skipped: {e}")

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

    def attest_batch(self, attestations: list[dict]) -> dict:
        """
        Submit multiple attestations in a single request (up to 50).

        Each attestation is validated independently — partial success is possible.

        Args:
            attestations: List of dicts, each with:
                - to_did (str): Target agent DID
                - outcome (str): "positive", "negative", or "neutral"
                - weight (float): 0.0-1.0 (default 1.0)
                - context (str, optional): Interaction type
                - evidence_hash (str, optional): SHA256 of evidence
                - is_private (bool, optional): Default False
                - interaction_id (str, optional): UUID

        Returns:
            dict with total, succeeded, failed, results
        """
        if not attestations or len(attestations) > 50:
            raise AVPValidationError("Batch must contain 1-50 attestations")

        signing_key = SigningKey(self._private_key)
        items = []

        for att in attestations:
            to_did = att["to_did"]
            outcome = att.get("outcome", "positive")
            weight = att.get("weight", 1.0)
            context = att.get("context")
            evidence_hash = att.get("evidence_hash")

            if outcome not in ("positive", "negative", "neutral"):
                raise AVPValidationError(f"Invalid outcome: {outcome}")
            if not 0.0 <= weight <= 1.0:
                raise AVPValidationError(f"Weight must be 0.0-1.0, got {weight}")

            # Sign each attestation
            attest_payload = json.dumps({
                "to": to_did,
                "outcome": outcome,
                "weight": weight,
                "context": context or "",
                "evidence_hash": evidence_hash or "",
            }, sort_keys=True, separators=(",", ":")).encode()
            signed = signing_key.sign(attest_payload)

            item = {
                "to_agent_did": to_did,
                "outcome": outcome,
                "weight": weight,
                "signature": signed.signature.hex(),
            }
            if context:
                item["context"] = context
            if evidence_hash:
                item["evidence_hash"] = evidence_hash
            if att.get("is_private"):
                item["is_private"] = True
            if att.get("interaction_id"):
                item["interaction_id"] = att["interaction_id"]
            items.append(item)

        body = json.dumps({"attestations": items}).encode()
        headers = self._auth_headers("POST", "/v1/attestations/batch", body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/attestations/batch", content=body, headers=headers)
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

    def get_reputation_bulk(self, dids: list[str]) -> dict:
        """
        Get reputation scores for multiple agents in one request (up to 100).

        Args:
            dids: List of agent DIDs

        Returns:
            dict with total, found, results (list of {did, found, reputation, error})
        """
        if not dids or len(dids) > 100:
            raise AVPValidationError("Bulk query requires 1-100 DIDs")

        dids_param = ",".join(dids)
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get("/v1/reputation/bulk", params={"dids": dids_param})
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

    # ── Alert Webhooks ──────────────────────────────────────────────────

    def set_alert(
        self,
        webhook_url: str,
        threshold: float = 0.5,
    ) -> dict:
        """
        Subscribe to score drop alerts.

        When this agent's score falls below threshold, AVP POSTs to webhook_url.
        Upserts: if (agent, url) already exists, updates threshold.

        Args:
            webhook_url: HTTPS endpoint (Discord, Teams, PagerDuty, Zapier, custom)
            threshold: Score threshold (default 0.5, range 0.0-1.0)

        Returns:
            dict with alert subscription details
        """
        body = json.dumps({
            "webhook_url": webhook_url,
            "threshold": threshold,
        }).encode()
        headers = self._auth_headers("POST", "/v1/alerts", body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post("/v1/alerts", content=body, headers=headers)
            return self._handle_response(r)

    def remove_alert(self, alert_id: str) -> None:
        """Remove an alert subscription by ID."""
        path = f"/v1/alerts/{alert_id}"
        headers = self._auth_headers("DELETE", path, b"")

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.delete(path, headers=headers)
            if r.status_code != 204:
                self._handle_response(r)

    def list_alerts(self) -> list[dict]:
        """List all alert subscriptions for this agent."""
        headers = self._auth_headers("GET", "/v1/alerts", b"")

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get("/v1/alerts", headers=headers)
            return self._handle_response(r)

    # ── Reputation Credentials ────────────────────────────────────────

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

    # === Onboarding / Challenge ===

    def get_onboarding_challenge(self) -> Optional[dict]:
        """
        Get the current onboarding challenge for this agent.

        Returns:
            Challenge dict with challenge_id, challenge_text, challenge_type,
            target_capability, deadline, status. None if no challenge exists.
        """
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/onboarding/{self._did}/challenge")
            if r.status_code == 404:
                return None
            return self._handle_response(r)

    def submit_challenge_answer(self, challenge_id: str, answer: str) -> dict:
        """
        Submit an answer to the onboarding challenge.

        Args:
            challenge_id: The challenge_id from get_onboarding_challenge()
            answer: The agent's answer (10-5000 chars)

        Returns:
            dict with challenge_id, score, passed, reasoning, pipeline_status
        """
        body_data = {"challenge_id": challenge_id, "answer": answer}
        body = json.dumps(body_data).encode()
        path = f"/v1/onboarding/{self._did}/challenge"
        headers = self._auth_headers("POST", path, body)

        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.post(path, content=body, headers=headers)
            return self._handle_response(r)

    def get_onboarding_status(self) -> dict:
        """Get current onboarding status for this agent."""
        with httpx.Client(base_url=self._base_url, timeout=self._timeout) as c:
            r = c.get(f"/v1/onboarding/{self._did}")
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
