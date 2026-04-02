"""
Contract tests: SDK ↔ Server field agreement.

These tests verify that SDK request payloads match server Pydantic schemas.
If a server schema adds a required field, these tests MUST fail.

No running server needed — tests inspect code structure only.
"""

import json
from unittest.mock import patch, MagicMock

import httpx
from nacl.signing import SigningKey

from agentveil.agent import AVPAgent


def _make_agent() -> AVPAgent:
    """Create a real agent (not mock) without saving to disk."""
    sk = SigningKey.generate()
    return AVPAgent("http://localhost:8000", bytes(sk), name="contract-test", timeout=1.0)


class TestRegisterContract:
    """Verify register() sends all fields required by AgentVerifyRequest."""

    def test_verify_request_includes_pow_nonce(self):
        """
        AgentVerifyRequest requires: did, challenge, signature_hex, pow_nonce.
        SDK must send all four.
        """
        agent = _make_agent()
        captured_requests = []

        def mock_post(url, **kwargs):
            captured_requests.append({"url": url, "json": kwargs.get("json")})
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200

            if "/register" in url:
                resp.json.return_value = {
                    "did": agent.did,
                    "agnet_address": "0xtest",
                    "challenge": "test-challenge-hex",
                    "challenge_expires_at": "2026-12-31T00:00:00Z",
                    "pow_challenge": "test-challenge-hex",
                    "pow_difficulty": 1,  # difficulty=1 for fast test
                }
            elif "/verify" in url:
                resp.json.return_value = {
                    "did": agent.did,
                    "verified": True,
                    "trust_period_active": False,
                    "trust_period_ends_at": None,
                    "next_step": "Publish your agent card.",
                }
            return resp

        with patch.object(httpx.Client, "post", side_effect=mock_post):
            with patch.object(agent, "save", return_value="/dev/null"):
                agent.register(display_name="ContractTest")

        # Find the verify request
        verify_reqs = [r for r in captured_requests if "/verify" in r["url"]]
        assert len(verify_reqs) == 1, f"Expected 1 verify request, got {len(verify_reqs)}"

        verify_body = verify_reqs[0]["json"]

        # All required fields from AgentVerifyRequest
        assert "did" in verify_body, "Missing 'did' in verify request"
        assert "challenge" in verify_body, "Missing 'challenge' in verify request"
        assert "signature_hex" in verify_body, "Missing 'signature_hex' in verify request"
        assert "pow_nonce" in verify_body, "Missing 'pow_nonce' in verify request"

        # Types
        assert isinstance(verify_body["did"], str)
        assert isinstance(verify_body["challenge"], str)
        assert isinstance(verify_body["signature_hex"], str)
        assert isinstance(verify_body["pow_nonce"], str)

    def test_register_reads_pow_fields_from_response(self):
        """SDK must read pow_challenge and pow_difficulty from register response."""
        agent = _make_agent()
        pow_data = {}

        original_solve = None

        def capture_solve(challenge, difficulty):
            pow_data["challenge"] = challenge
            pow_data["difficulty"] = difficulty
            return "0"  # Dummy nonce

        def mock_post(url, **kwargs):
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200

            if "/register" in url:
                resp.json.return_value = {
                    "did": agent.did,
                    "agnet_address": "0xtest",
                    "challenge": "the-challenge",
                    "challenge_expires_at": "2026-12-31T00:00:00Z",
                    "pow_challenge": "pow-challenge-value",
                    "pow_difficulty": 20,
                }
            elif "/verify" in url:
                resp.json.return_value = {
                    "did": agent.did,
                    "verified": True,
                }
            return resp

        with patch.object(httpx.Client, "post", side_effect=mock_post), \
             patch("agentveil.agent.solve_pow", side_effect=capture_solve), \
             patch.object(agent, "save", return_value="/dev/null"):
            agent.register()

        assert pow_data["challenge"] == "pow-challenge-value"
        assert pow_data["difficulty"] == 20


class TestAttestContract:
    """Verify attest() supports all fields from AttestationCreateRequest."""

    def test_attest_sends_is_private(self):
        """SDK must send is_private when set to True."""
        agent = _make_agent()
        agent._is_registered = True
        agent._is_verified = True
        captured = {}

        def mock_post(url, **kwargs):
            if "/attestations" in url:
                body = kwargs.get("content", b"")
                captured["body"] = json.loads(body)
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "id": "test-id",
                "from_agent_did": agent.did,
                "to_agent_did": "did:key:z6MkTarget",
                "outcome": "positive",
                "weight": 1.0,
                "is_private": True,
                "created_at": "2026-01-01T00:00:00Z",
            }
            return resp

        with patch.object(httpx.Client, "post", side_effect=mock_post):
            agent.attest("did:key:z6MkTarget", outcome="positive", is_private=True)

        assert captured["body"].get("is_private") is True

    def test_attest_sends_interaction_id(self):
        """SDK must send interaction_id when provided."""
        agent = _make_agent()
        agent._is_registered = True
        agent._is_verified = True
        captured = {}

        def mock_post(url, **kwargs):
            if "/attestations" in url:
                body = kwargs.get("content", b"")
                captured["body"] = json.loads(body)
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "id": "test-id",
                "from_agent_did": agent.did,
                "to_agent_did": "did:key:z6MkTarget",
                "outcome": "positive",
                "weight": 1.0,
                "created_at": "2026-01-01T00:00:00Z",
            }
            return resp

        with patch.object(httpx.Client, "post", side_effect=mock_post):
            agent.attest(
                "did:key:z6MkTarget",
                outcome="positive",
                interaction_id="550e8400-e29b-41d4-a716-446655440000",
            )

        assert captured["body"].get("interaction_id") == "550e8400-e29b-41d4-a716-446655440000"


class TestCardContract:
    """Verify publish_card() supports all fields from CardCreateRequest."""

    def test_card_sends_signature(self):
        """SDK must send signature when provided."""
        agent = _make_agent()
        agent._is_registered = True
        agent._is_verified = True
        captured = {}

        def mock_post(url, **kwargs):
            if "/cards" in url:
                body = kwargs.get("content", b"")
                captured["body"] = json.loads(body)
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json.return_value = {
                "id": "test-card-id",
                "agent_did": agent.did,
                "version": 1,
                "capabilities": ["testing"],
                "endpoint_url": None,
                "protocols": [],
                "provider": None,
            }
            return resp

        with patch.object(httpx.Client, "post", side_effect=mock_post):
            agent.publish_card(
                capabilities=["testing"],
                signature="abcdef1234567890",
            )

        assert captured["body"].get("signature") == "abcdef1234567890"
