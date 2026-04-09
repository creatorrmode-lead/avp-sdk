"""End-to-end tests using mock agents — full lifecycle without a server."""

import pytest

from agentveil.mock import AVPMockAgent


class TestFullLifecycle:
    """Complete agent lifecycle: create → register → card → attest → reputation."""

    def test_single_agent_lifecycle(self):
        agent = AVPMockAgent.create(name="lifecycle")
        assert not agent.is_registered

        # Register
        reg = agent.register()
        assert agent.is_registered
        assert agent.is_verified
        assert reg["did"] == agent.did

        # Publish card
        card = agent.publish_card(
            capabilities=["code_review", "testing"],
            provider="anthropic",
        )
        assert "code_review" in card["capabilities"]

        # Check reputation
        rep = agent.get_reputation()
        assert rep["score"] > 0

        # Health
        h = agent.health()
        assert h["status"] == "ok"

    def test_two_agent_interaction(self):
        alice = AVPMockAgent.create(name="alice")
        bob = AVPMockAgent.create(name="bob")
        alice.register()
        bob.register()

        # Alice publishes card
        alice.publish_card(capabilities=["research"], provider="anthropic")

        # Bob searches for research agents
        results = bob.search_agents(capability="research")
        assert len(results) >= 1

        # Bob checks Alice's reputation
        rep = bob.get_reputation(alice.did)
        assert rep["did"] == alice.did

        # Bob attests positively about Alice
        att = bob.attest(alice.did, outcome="positive", weight=0.9, context="research")
        assert att["outcome"] == "positive"
        assert att["to_did"] == alice.did

        # Alice checks her reputation tracks
        tracks = alice.get_reputation_tracks()
        assert "code_quality" in tracks["tracks"]

        # Alice checks velocity
        vel = alice.get_reputation_velocity()
        assert vel["trend"] == "improving"

    def test_reputation_changes_over_multiple_attestations(self):
        agent = AVPMockAgent.create(name="scorer")
        peer = AVPMockAgent.create(name="peer")
        agent.register()
        peer.register()

        scores = []
        for i in range(5):
            agent.attest(peer.did, outcome="positive", weight=1.0)
            scores.append(agent.get_reputation()["score"])

        # Score should increase monotonically with positive attestations
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]

    def test_negative_attestations_decrease_reputation(self):
        agent = AVPMockAgent.create(name="critic")
        peer = AVPMockAgent.create(name="target")
        agent.register()

        rep_before = agent.get_reputation()["score"]
        for _ in range(3):
            agent.attest(peer.did, outcome="negative", weight=1.0)
        rep_after = agent.get_reputation()["score"]

        assert rep_after < rep_before

    def test_credential_flow(self):
        agent = AVPMockAgent.create(name="cred_test")
        agent.register()

        # Get credential
        cred = agent.get_reputation_credential(risk_level="medium")
        assert cred["did"] == agent.did
        assert cred["risk_level"] == "medium"
        assert "signature" in cred
        assert "signer_did" in cred
        assert cred["expires_at"] > cred["issued_at"]

    def test_agent_info(self):
        agent = AVPMockAgent.create(name="info_test")
        agent.register()

        info = agent.get_agent_info()
        assert info["did"] == agent.did
        assert info["status"] == "active"

        # Can query other agents too
        other_info = agent.get_agent_info("did:key:z6MkOther")
        assert other_info["did"] == "did:key:z6MkOther"
