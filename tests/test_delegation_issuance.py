"""Tests for ergonomic SDK DelegationReceipt issuance."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from nacl.signing import SigningKey

from agentveil.agent import AVPAgent
from agentveil.delegation import verify_delegation


def _make_agent(name: str) -> AVPAgent:
    sk = SigningKey.generate()
    return AVPAgent("http://localhost:8000", bytes(sk), name=name, timeout=1.0)


def test_issue_delegation_receipt_verifies_with_correct_issuer_and_subject():
    principal = _make_agent("principal")
    agent = _make_agent("agent")

    receipt = principal.issue_delegation_receipt(
        agent_did=agent.did,
        allowed_categories=["infrastructure"],
        valid_for=timedelta(hours=1),
    )
    verified = verify_delegation(receipt)

    assert verified["issuer"] == principal.did
    assert verified["subject"] == agent.did
    assert verified["scope"] == [
        {"predicate": "allowed_category", "value": "infrastructure"}
    ]


def test_verify_delegation_receipt_helper_uses_existing_offline_verifier():
    principal = _make_agent("principal")
    agent = _make_agent("agent")
    receipt = principal.issue_delegation_receipt(
        agent_did=agent.did,
        allowed_categories=["data"],
        valid_for=timedelta(minutes=30),
    )

    verified = principal.verify_delegation_receipt(receipt)

    assert verified["valid"] is True
    assert verified["issuer"] == principal.did
    assert verified["subject"] == agent.did


def test_issue_delegation_receipt_encodes_multiple_categories_and_max_spend():
    principal = _make_agent("principal")
    agent = _make_agent("agent")

    receipt = principal.issue_delegation_receipt(
        agent_did=agent.did,
        allowed_categories=["infrastructure", "payments"],
        max_spend={"currency": "USD", "amount": 100},
        valid_for=timedelta(hours=2),
    )
    scope = verify_delegation(receipt)["scope"]

    assert scope == [
        {"predicate": "allowed_category", "value": "infrastructure"},
        {"predicate": "allowed_category", "value": "payments"},
        {"predicate": "max_spend", "currency": "USD", "amount": 100},
    ]


@pytest.mark.parametrize("valid_for", [timedelta(0), timedelta(seconds=-1)])
def test_issue_delegation_receipt_rejects_non_positive_valid_for(valid_for):
    principal = _make_agent("principal")
    agent = _make_agent("agent")

    with patch("agentveil.delegation.issue_delegation") as issue_mock:
        with pytest.raises(ValueError, match="valid_for must be a positive timedelta"):
            principal.issue_delegation_receipt(
                agent_did=agent.did,
                allowed_categories=["infrastructure"],
                valid_for=valid_for,
            )

    issue_mock.assert_not_called()


@pytest.mark.parametrize(
    "kwarg",
    ["allowed_actions", "allowed_resources", "allowed_environments"],
)
def test_issue_delegation_receipt_rejects_exact_scope_kwargs_before_signing(kwarg):
    principal = _make_agent("principal")
    agent = _make_agent("agent")

    with patch("agentveil.delegation.issue_delegation") as issue_mock:
        with pytest.raises(ValueError, match="unsupported exact-scope"):
            principal.issue_delegation_receipt(
                agent_did=agent.did,
                allowed_categories=["infrastructure"],
                valid_for=timedelta(hours=1),
                **{kwarg: ["infra.resource.inspect"]},
            )

    issue_mock.assert_not_called()


def test_generated_v1_receipt_works_in_mocked_controlled_action_flow():
    principal = _make_agent("principal")
    agent = _make_agent("agent")
    receipt = principal.issue_delegation_receipt(
        agent_did=agent.did,
        allowed_categories=["infrastructure"],
        valid_for=timedelta(hours=1),
    )
    raw_receipt = '{"receipt_id":"urn:uuid:receipt","status":"SUCCESS"}'

    def runtime_evaluate(**kwargs):
        scope = kwargs["delegation_receipt"]["credentialSubject"]["scope"]
        predicates = {entry["predicate"] for entry in scope}
        assert predicates == {"allowed_category"}
        return {
            "audit_id": "urn:uuid:audit",
            "decision": "ALLOW",
            "reason": "read_action",
        }

    with patch.object(agent, "runtime_evaluate", side_effect=runtime_evaluate), \
         patch.object(agent, "execute", return_value=raw_receipt) as execute_mock:
        result = agent.controlled_action(
            action="infra.resource.inspect",
            resource="resource:vol-123",
            environment="development",
            delegation_receipt=receipt,
            params={"resource_id": "vol-123"},
        )

    execute_mock.assert_called_once()
    assert result.status == "executed"
    assert result.receipt_jcs == raw_receipt
