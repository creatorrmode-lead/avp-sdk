# Security Model

> **Status:** Mode 1 (SDK / Developer Mode) is shipped today (SDK 0.7.x). Mode 2
> (AVP-Managed Gateway) and Mode 3 (Customer-Hosted Gateway) are roadmap items
> planned for v0.8+ — not yet shipped. This document describes both current
> capability and target architecture.

AgentVeil separates advisory trust, runtime decisioning, and production
enforcement. The SDK helps integrations request decisions and preserve signed
evidence, but where credentials live determines whether AVP can technically
prevent bypass.

## SDK / Developer Mode

**Status:** shipped (SDK 0.7.x — Mode 1).

Use SDK mode for integration, demos, pilots, and applications where the host
application already controls the action path.

SDK mode supports:

- `integration_preflight()` setup and signed-read readiness checks;
- DelegationReceipt issuance and offline verification;
- Runtime Gate calls with action, resource, environment, and receipt context;
- human approval orchestration;
- signed receipts and proof packets for audit and review.

SDK mode is not full enforcement if the agent process still holds direct
provider credentials or can call the risky tool outside `controlled_action(...)`.
In that setup, AVP can evaluate, record, and prove the controlled path, but the
application owner must still remove or block bypass paths.

## Gateway Enforcement Mode

**Status:** roadmap / planned (Mode 2, Phase 3 — v0.8+). Not yet shipped.

Use gateway enforcement when risky actions must be technically constrained.

In this model:

- risky provider credentials are not held by the agent;
- the agent sends the requested action to an execution boundary;
- the boundary checks Runtime Gate, DelegationReceipt, and HumanApprovalReceipt
  when approval is required;
- the boundary validates the requested action, resource, environment, and
  parameters against the allowed execution contract;
- the boundary executes only when checks pass and fails closed otherwise;
- the boundary emits or stores signed execution evidence.

This is the stronger production model because the agent cannot bypass AVP by
using the provider credential directly.

## Customer-Hosted Gateway

**Status:** roadmap / planned (Mode 3, Phase 3). Reference architecture for
enterprise customers; implementation alongside Mode 2.

Some customers need secrets to stay inside their own infrastructure. A
customer-hosted gateway uses the same enforcement model, but the customer runs
the execution boundary and keeps provider credentials in their environment.

The security requirement is the same: the risky credential must be reachable
only by the boundary that performs AVP checks, not by the agent runtime.

## Receipts And Proof Strength

Signed receipts are tamper-evident evidence of the path that produced them.
They are strongest when emitted by the component that actually controls
execution.

- SDK mode receipts prove what happened on the SDK-controlled path.
- Gateway enforcement receipts prove that an execution boundary checked AVP
  control evidence before executing.
- Re-serializing signed receipt JSON can change bytes; keep raw signed receipt
  text when offline proof matters.

## Minimum Production Guidance

- Use `integration_preflight()` before Runtime Gate calls.
- Issue DelegationReceipts from the principal or workflow owner, not from the
  acting agent.
- Route production/destructive/financial tools through a boundary that owns the
  risky credential.
- Treat direct provider credentials inside the agent runtime as a bypass risk.
- Store DelegationReceipts, Runtime Gate audit IDs, approval receipts, execution
  receipts, and proof packets for later review.

Full production enforcement requires routing risky tools through an AVP-managed
or customer-hosted execution boundary. **Modes 2 and 3 are roadmap (Phase 3) —
plan accordingly during pilot scoping.**
