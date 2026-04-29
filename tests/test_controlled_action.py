"""Tests for high-level controlled action orchestration."""

from unittest.mock import patch

from nacl.signing import SigningKey

from agentveil.agent import AVPAgent
from agentveil.results import ControlledActionOutcome


def _make_agent() -> AVPAgent:
    sk = SigningKey.generate()
    return AVPAgent("http://localhost:8000", bytes(sk), name="controlled-test", timeout=1.0)


def test_controlled_action_allow_executes_and_preserves_receipt_jcs():
    agent = _make_agent()
    decision = {
        "audit_id": "urn:uuid:11111111-1111-1111-1111-111111111111",
        "decision": "ALLOW",
        "reason": "read_action",
    }
    receipt_jcs = '{"receipt_id":"urn:uuid:22222222-2222-2222-2222-222222222222","status":"SUCCESS"}'

    with patch.object(agent, "runtime_evaluate", return_value=decision) as eval_mock, \
         patch.object(agent, "execute", return_value=receipt_jcs) as execute_mock:
        result = agent.controlled_action(
            action="infra.resource.inspect",
            resource="resource:1",
            environment="development",
            delegation_receipt={"id": "urn:uuid:receipt"},
            params={"resource_id": "resource:1"},
        )

    eval_mock.assert_called_once()
    execute_mock.assert_called_once_with(
        audit_id=decision["audit_id"],
        action="infra.resource.inspect",
        resource="resource:1",
        environment="development",
        params={"resource_id": "resource:1"},
    )
    assert isinstance(result, ControlledActionOutcome)
    assert result.status == "executed"
    assert result.receipt_jcs == receipt_jcs
    assert result.receipt["status"] == "SUCCESS"
    assert result["status"] == "executed"


def test_controlled_action_waiting_creates_approval_without_executing():
    agent = _make_agent()
    decision = {
        "audit_id": "urn:uuid:11111111-1111-1111-1111-111111111111",
        "decision": "WAITING_FOR_HUMAN_APPROVAL",
        "reason": "destructive_production_action",
    }
    approval = {"id": "urn:uuid:approval", "status": "PENDING"}
    delegation_receipt = {"id": "urn:uuid:receipt"}

    with patch.object(agent, "runtime_evaluate", return_value=decision), \
         patch.object(agent, "create_approval", return_value=approval) as approval_mock, \
         patch.object(agent, "execute") as execute_mock:
        result = agent.controlled_action(
            action="infra.volume.delete",
            resource="volume:vol-1",
            environment="production",
            delegation_receipt=delegation_receipt,
            params={"resource_id": "vol-1"},
            approval_expires_in_seconds=900,
        )

    approval_mock.assert_called_once_with(
        audit_id=decision["audit_id"],
        delegation_receipt=delegation_receipt,
        expires_in_seconds=900,
    )
    execute_mock.assert_not_called()
    assert isinstance(result, ControlledActionOutcome)
    assert result.status == "approval_required"
    assert result.approval == approval


def test_controlled_action_blocked_does_not_create_approval_or_execute():
    agent = _make_agent()
    decision = {
        "audit_id": "urn:uuid:11111111-1111-1111-1111-111111111111",
        "decision": "BLOCK",
        "reason": "governance_recent_disputes",
    }

    with patch.object(agent, "runtime_evaluate", return_value=decision), \
         patch.object(agent, "create_approval") as approval_mock, \
         patch.object(agent, "execute") as execute_mock:
        result = agent.controlled_action(
            action="infra.volume.delete",
            resource="volume:vol-1",
            environment="production",
            delegation_receipt={"id": "urn:uuid:receipt"},
            params={"resource_id": "vol-1"},
        )

    approval_mock.assert_not_called()
    execute_mock.assert_not_called()
    assert isinstance(result, ControlledActionOutcome)
    assert result.status == "blocked"
    assert result.decision == decision
    assert result.reason == "governance_recent_disputes"


def test_controlled_action_unknown_decision_fails_closed():
    agent = _make_agent()
    decision = {
        "audit_id": "urn:uuid:11111111-1111-1111-1111-111111111111",
        "decision": "MFA_REQUIRED",
        "reason": "future_gate_state",
    }

    with patch.object(agent, "runtime_evaluate", return_value=decision), \
         patch.object(agent, "create_approval") as approval_mock, \
         patch.object(agent, "execute") as execute_mock:
        result = agent.controlled_action(
            action="infra.volume.delete",
            resource="volume:vol-1",
            environment="production",
            delegation_receipt={"id": "urn:uuid:receipt"},
            params={"resource_id": "vol-1"},
        )

    approval_mock.assert_not_called()
    execute_mock.assert_not_called()
    assert result.status == "blocked"
    assert result.reason == "future_gate_state"


def test_execute_after_approval_executes_with_approval_id():
    agent = _make_agent()
    receipt_jcs = '{"receipt_id":"urn:uuid:22222222-2222-2222-2222-222222222222","status":"SUCCESS"}'

    with patch.object(agent, "execute", return_value=receipt_jcs) as execute_mock:
        result = agent.execute_after_approval(
            audit_id="urn:uuid:11111111-1111-1111-1111-111111111111",
            approval_id="urn:uuid:approval",
            action="infra.volume.delete",
            resource="volume:vol-1",
            environment="production",
            params={"resource_id": "vol-1"},
        )

    execute_mock.assert_called_once_with(
        audit_id="urn:uuid:11111111-1111-1111-1111-111111111111",
        action="infra.volume.delete",
        resource="volume:vol-1",
        environment="production",
        params={"resource_id": "vol-1"},
        approval_id="urn:uuid:approval",
    )
    assert isinstance(result, ControlledActionOutcome)
    assert result.status == "executed"
    assert result.approval_id == "urn:uuid:approval"
    assert result.receipt["status"] == "SUCCESS"
