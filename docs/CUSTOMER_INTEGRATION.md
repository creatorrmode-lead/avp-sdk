# Customer Integration Guide

This guide is for integrating AVP into a real controlled-action workflow. It is not a demo path and does not bypass runtime safety.

For a first guided customer rollout, use
`docs/PILOT_READINESS_CHECKLIST.md` before running a controlled action.

## What AVP Controls

AVP keeps the reputation stack and adds runtime enforcement:

```text
Identity -> Cards/Reputation/Attestations -> Delegation
-> Runtime Gate -> Governance -> Human Approval
-> Signed Execution Receipt -> Remediation
```

Use `can_trust()` before selecting an agent. Use `controlled_action()` before the agent performs a concrete action.

## Secrets

Client-side:

- Store the agent Ed25519 private key locally.
- `AVPAgent.save(passphrase=...)` encrypts the key.
- Never send private keys, API keys, cloud tokens, or raw private logs to AVP.

Operator/backend:

- `ADMIN_TOKEN` provisions trusted operator agents.
- `CREDENTIAL_SIGNING_KEY_HEX` signs reputation credentials.
- `EXECUTION_RECEIPT_SIGNING_KEY_HEX` signs execution receipts.
- `HUMAN_APPROVAL_SIGNING_KEY_HEX` signs approval receipts.

If execution or human approval signing keys are missing, the backend fails closed with `503` before state changes.

## Setup Checklist

Before the first controlled action:

1. Create or load the local agent identity.
2. Register and verify the agent DID with the AVP API.
3. Obtain a DelegationReceipt for the intended action scope.
4. Call `controlled_action(...)`.
5. Store `receipt_jcs` if the action executes.
6. If approval is required, route approval to the principal and resume with `execute_after_approval(...)`.
7. If blocked, surface the reason and do not execute the action.

Creating a local DID/key is not enough by itself. The production API must know and verify that DID before signed runtime requests can succeed.

## Integration Preflight

Run preflight before the first controlled action:

```python
report = agent.integration_preflight()

if not report.ready:
    print(report.status)
    print(report.next_action)
```

Preflight checks API reachability, public DID registration status, verification status when visible, and one safe signed read request. It does not call Runtime Gate, approve actions, or execute actions.

## DelegationReceipt Source

A DelegationReceipt is issued by the principal or workflow owner that authorizes the agent to request a bounded action. It should name the agent DID, the allowed action/resource/environment scope, and the validity window.

Use `can_trust()` before selecting an agent, then issue or obtain a DelegationReceipt for the selected agent before calling `controlled_action(...)`. Reputation helps selection; delegation authorizes the runtime action.

## First Controlled Action

Use `examples/first_controlled_action.py` as the customer template. By default
it only loads identity and runs preflight. It calls `controlled_action(...)`
only when `AVP_RUN_CONTROLLED_ACTION=1` and a DelegationReceipt is supplied via
`AVP_DELEGATION_RECEIPT_FILE` or `AVP_DELEGATION_RECEIPT_JSON`.

```python
from agentveil import AVPAgent, ControlledActionOutcome

agent = AVPAgent.load("https://agentveil.dev", name="customer-agent", passphrase="...")

result: ControlledActionOutcome = agent.controlled_action(
    action="infra.resource.inspect",
    resource="resource:vol-123",
    environment="development",
    params={"resource_id": "vol-123"},
    delegation_receipt=delegation_receipt,
)

if result.status == "executed":
    receipt_jcs = result.receipt_jcs      # exact signed proof artifact
    receipt = result.receipt              # parsed convenience view
elif result.status == "approval_required":
    approval_id = result.approval["id"]
elif result.status == "blocked":
    reason = result.reason
```

`controlled_action()` never auto-approves. If approval is required, the principal must approve the request with their own DID.

Production applications should also catch SDK exceptions around
`controlled_action(...)`, especially `AVPRateLimitError`, `AVPValidationError`,
and `AVPServerError`. The first-action template shows one minimal handling
pattern.

The first-action template intentionally does not generate a DelegationReceipt
for you. In production, the principal or workflow owner issues it after
selecting the agent and defining the allowed action scope. Put that signed
receipt in `AVP_DELEGATION_RECEIPT_FILE` or `AVP_DELEGATION_RECEIPT_JSON`.

## Approval Resume Path

```python
receipt_result = agent.execute_after_approval(
    audit_id=runtime_audit_id,
    approval_id=approval_id,
    action="infra.volume.delete",
    resource="volume:vol-123",
    environment="production",
    params={"resource_id": "vol-123"},
)

receipt_jcs = receipt_result.receipt_jcs
```

## Low-Level API Wrappers

Use these when your application wants to own orchestration:

- `runtime_evaluate(...)`
- `get_runtime_decision(audit_id)`
- `execute(...)`
- `get_execution_receipt(receipt_id)`
- `create_approval(...)`
- `get_approval(approval_id)`
- `approve(approval_id)`
- `deny(approval_id, reason=None)`
- `create_governance_policy(...)`
- `activate_governance_policy(policy_id)`
- `create_governance_risk_event(...)`
- `create_remediation_case(...)`
- `list_remediation_cases(...)`
- `get_remediation_case(case_id)`
- `add_remediation_evidence(...)`

`execute()`, `get_execution_receipt()`, `approve()`, and `deny()` return exact signed JSON text. Keep that string for offline proof.

## Error Map

- `401`: missing/invalid signature, nonce replay, expired timestamp, or unregistered agent.
- `403`: agent not verified, suspended, revoked, or not allowed for the requested role.
- `404`: missing or foreign private resource. AVP intentionally hides existence for private objects.
- `409`: valid request but unsafe/currently impossible state, such as `approval_required`, `approval_not_approved`, `approval_expired`, or `capability_not_executable_in_mvp`.
- `422`: schema validation error.
- `429`: Trust Gate or global rate limit. Respect `retry_after`.
- `503`: backend dependency unavailable or missing signing key. Do not retry aggressively.

Runtime `BLOCK` is not an HTTP error. It is a safety decision returned by Runtime Gate or Governance.

## Proof Retention Checklist

For a security/compliance review, retain:

- DelegationReceipt
- Runtime Gate `audit_id`
- raw signed execution receipt (`receipt_jcs`)
- signed approval receipt, if used
- remediation case and evidence hashes, if contested

Also retain when available:

- agent DID and public key
- governance `policy_version` and `policy_context_hash`
- `/v1/audit/verify` result for audit-chain integrity

Signed execution and approval receipts are immutable proof artifacts. Remediation can reference them, but cannot rewrite them.
