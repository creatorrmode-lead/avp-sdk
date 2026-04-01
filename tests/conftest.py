"""Shared fixtures for AVP SDK tests."""

import pytest
from nacl.signing import SigningKey

from agentveil.agent import AVPAgent, _public_key_to_did
from agentveil.mock import AVPMockAgent


@pytest.fixture
def signing_key():
    """Fresh Ed25519 signing key."""
    return SigningKey.generate()


@pytest.fixture
def private_key(signing_key):
    """Raw 32-byte private key."""
    return bytes(signing_key)


@pytest.fixture
def public_key(signing_key):
    """Raw 32-byte public key."""
    return bytes(signing_key.verify_key)


@pytest.fixture
def did(public_key):
    """DID derived from public key."""
    return _public_key_to_did(public_key)


@pytest.fixture
def mock_agent():
    """Ready-to-use mock agent (registered)."""
    agent = AVPMockAgent.create(name="test_agent")
    agent.register()
    return agent


@pytest.fixture
def mock_agent_pair():
    """Two registered mock agents for interaction tests."""
    a = AVPMockAgent.create(name="agent_a")
    b = AVPMockAgent.create(name="agent_b")
    a.register()
    b.register()
    return a, b
