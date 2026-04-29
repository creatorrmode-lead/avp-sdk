# Customer Integration Guide

This guide is for integrating AVP into a real controlled-action workflow. It is not a demo path and does not bypass runtime safety.

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

## First Controlled Action

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

## Compliance Packet

For a security/compliance review, retain:

- agent DID and public key
- DelegationReceipt
- Runtime Gate decision and `audit_id`
- governance `policy_version` and `policy_context_hash`, when present
- signed approval receipt, when used
- signed execution receipt
- remediation case and evidence hashes, when contested
- `/v1/audit/verify` result for audit-chain integrity

Signed execution and approval receipts are immutable proof artifacts. Remediation can reference them, but cannot rewrite them.
