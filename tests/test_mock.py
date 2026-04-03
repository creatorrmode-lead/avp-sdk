"""Tests for AVPMockAgent — offline mock for testing and demos."""

import pytest

from agentveil.mock import AVPMockAgent
from agentveil.agent import AVPAgent
from agentveil.exceptions import AVPValidationError


class TestMockAgentCreation:
    """Mock agent factory and identity."""

    def test_create_returns_mock_agent(self):
        agent = AVPMockAgent.create(name="test")
        assert isinstance(agent, AVPMockAgent)

    def test_mock_is_avp_agent_subclass(self):
        agent = AVPMockAgent.create(name="test")
        assert isinstance(agent, AVPAgent)

    def test_mock_has_real_did(self):
        agent = AVPMockAgent.create(name="test")
        assert agent.did.startswith("did:key:z")

    def test_mock_different_dids(self):
        a = AVPMockAgent.create(name="a")
        b = AVPMockAgent.create(name="b")
        assert a.did != b.did

    def test_create_via_avp_agent_mock_flag(self):
        agent = AVPAgent.create(mock=True, name="test")
        assert isinstance(agent, AVPMockAgent)

    def test_save_is_noop(self):
        agent = AVPMockAgent.create(name="test")
        path = agent.save()
        assert path == "/dev/null"


class TestMockRegistration:
    """Registration without a server."""

    def test_register_sets_flags(self):
        agent = AVPMockAgent.create(name="test")
        assert not agent.is_registered
        agent.register()
        assert agent.is_registered
        assert agent.is_verified

    def test_register_returns_did(self):
        agent = AVPMockAgent.create(name="test")
        result = agent.register()
        assert result["did"] == agent.did
        assert "challenge" in result


class TestMockAttestation:
    """Attestation recording and validation."""

    def test_positive_attestation(self, mock_agent_pair):
        a, b = mock_agent_pair
        result = a.attest(b.did, outcome="positive", weight=0.8)
        assert result["outcome"] == "positive"
        assert result["from_did"] == a.did
        assert result["to_did"] == b.did
        assert "attestation_id" in result

    def test_negative_attestation(self, mock_agent_pair):
        a, b = mock_agent_pair
        result = a.attest(b.did, outcome="negative", weight=0.5)
        assert result["outcome"] == "negative"

    def test_neutral_attestation(self, mock_agent_pair):
        a, b = mock_agent_pair
        result = a.attest(b.did, outcome="neutral")
        assert result["outcome"] == "neutral"

    def test_invalid_outcome_raises(self, mock_agent):
        with pytest.raises(AVPValidationError, match="Invalid outcome"):
            mock_agent.attest("did:key:z6MkTest", outcome="bad")

    def test_weight_out_of_range_raises(self, mock_agent):
        with pytest.raises(AVPValidationError, match="Weight must be"):
            mock_agent.attest("did:key:z6MkTest", outcome="positive", weight=2.0)

    def test_attestation_updates_reputation(self, mock_agent_pair):
        a, b = mock_agent_pair
        rep_before = a.get_reputation()["score"]
        a.attest(b.did, outcome="positive", weight=1.0)
        rep_after = a.get_reputation()["score"]
        assert rep_after > rep_before

    def test_negative_attestation_decreases_reputation(self, mock_agent_pair):
        a, b = mock_agent_pair
        rep_before = a.get_reputation()["score"]
        a.attest(b.did, outcome="negative", weight=1.0)
        rep_after = a.get_reputation()["score"]
        assert rep_after < rep_before


class TestMockReputation:
    """Reputation queries."""

    def test_reputation_has_required_fields(self, mock_agent):
        rep = mock_agent.get_reputation()
        assert "did" in rep
        assert "score" in rep
        assert "confidence" in rep
        assert "interpretation" in rep
        assert "total_attestations" in rep

    def test_reputation_score_range(self, mock_agent):
        rep = mock_agent.get_reputation()
        assert 0.0 <= rep["score"] <= 1.0

    def test_reputation_confidence_grows_with_attestations(self, mock_agent_pair):
        a, b = mock_agent_pair
        conf_before = a.get_reputation()["confidence"]
        a.attest(b.did, outcome="positive")
        a.attest(b.did, outcome="positive")
        conf_after = a.get_reputation()["confidence"]
        assert conf_after > conf_before

    def test_reputation_for_specific_did(self, mock_agent):
        rep = mock_agent.get_reputation("did:key:z6MkSomebody")
        assert rep["did"] == "did:key:z6MkSomebody"


class TestMockReputationTracks:
    """Per-category reputation tracks."""

    def test_tracks_has_expected_categories(self, mock_agent):
        tracks = mock_agent.get_reputation_tracks()
        assert "tracks" in tracks
        expected = {"code_quality", "task_completion", "data_accuracy", "negotiation", "general"}
        assert set(tracks["tracks"].keys()) == expected

    def test_track_scores_are_numeric(self, mock_agent):
        tracks = mock_agent.get_reputation_tracks()
        for name, data in tracks["tracks"].items():
            assert isinstance(data["score"], (int, float))
            assert isinstance(data["confidence"], (int, float))


class TestMockReputationVelocity:
    """Reputation velocity and trends."""

    def test_velocity_has_required_fields(self, mock_agent):
        vel = mock_agent.get_reputation_velocity()
        assert "current_score" in vel
        assert "velocity" in vel
        assert "trend" in vel
        assert "alert" in vel

    def test_velocity_windows(self, mock_agent):
        vel = mock_agent.get_reputation_velocity()
        assert "1d" in vel["velocity"]
        assert "7d" in vel["velocity"]
        assert "30d" in vel["velocity"]


class TestMockCards:
    """Agent capability cards."""

    def test_publish_card(self, mock_agent):
        card = mock_agent.publish_card(
            capabilities=["code_review", "testing"],
            provider="anthropic",
        )
        assert card["capabilities"] == ["code_review", "testing"]
        assert card["provider"] == "anthropic"
        assert "card_id" in card

    def test_search_agents(self, mock_agent):
        results = mock_agent.search_agents(capability="research")
        assert len(results) == 2
        assert results[0]["capabilities"] == ["research"]
        assert results[0]["did"].startswith("did:key:z")


class TestMockCredential:
    """Reputation credentials."""

    def test_credential_has_signature(self, mock_agent):
        cred = mock_agent.get_reputation_credential()
        assert "signature_hex" in cred
        assert "score" in cred
        assert "risk_level" in cred

    def test_credential_risk_levels(self, mock_agent):
        for level in ("low", "medium", "high"):
            cred = mock_agent.get_reputation_credential(risk_level=level)
            assert cred["risk_level"] == level

    def test_credential_critical_raises(self, mock_agent):
        with pytest.raises(AVPValidationError):
            mock_agent.get_reputation_credential(risk_level="critical")


class TestMockUtilities:
    """Health check and agent info."""

    def test_health(self, mock_agent):
        h = mock_agent.health()
        assert h["status"] == "ok"
        assert h["mode"] == "mock"

    def test_agent_info(self, mock_agent):
        info = mock_agent.get_agent_info()
        assert info["did"] == mock_agent.did
        assert info["status"] == "active"

    def test_repr(self, mock_agent):
        r = repr(mock_agent)
        assert "AVPMockAgent" in r
        assert "verified" in r


class TestMockVerification:
    """Verification mock methods."""

    def test_verify_email_returns_dict(self, mock_agent):
        result = mock_agent.verify_email("test@example.com")
        assert "message" in result
        assert "expires_in" in result

    def test_confirm_email_returns_verified(self, mock_agent):
        result = mock_agent.confirm_email("123456")
        assert result["verified"] is True
        assert "tier" in result
        assert "trust_boost" in result

    def test_verify_moltbook_returns_status(self, mock_agent):
        result = mock_agent.verify_moltbook("testuser")
        assert "message" in result
        assert "status" in result

    def test_get_verification_status_self(self, mock_agent):
        status = mock_agent.get_verification_status()
        assert status["did"] == mock_agent.did
        assert "tier" in status

    def test_get_verification_status_other(self, mock_agent):
        status = mock_agent.get_verification_status("did:key:z6MkOther")
        assert status["did"] == "did:key:z6MkOther"


class TestMockOnboarding:
    """Onboarding challenge mock methods."""

    def test_get_onboarding_challenge(self, mock_agent):
        challenge = mock_agent.get_onboarding_challenge()
        assert challenge is not None
        assert "challenge_id" in challenge
        assert "challenge_text" in challenge
        assert "challenge_type" in challenge

    def test_submit_challenge_answer(self, mock_agent):
        result = mock_agent.submit_challenge_answer("test-id", "My answer here")
        assert "score" in result
        assert "passed" in result
        assert isinstance(result["passed"], bool)

    def test_get_onboarding_status_verified(self, mock_agent):
        status = mock_agent.get_onboarding_status()
        assert status["did"] == mock_agent.did
        assert status["status"] == "completed"
        assert status["stages_completed"] == 4

    def test_get_onboarding_status_new(self):
        agent = AVPMockAgent.create(name="new_agent")
        status = agent.get_onboarding_status()
        assert status["status"] == "pending"
        assert status["stages_completed"] == 0
