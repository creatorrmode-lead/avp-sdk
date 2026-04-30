"""Typed SDK result objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional


ControlledActionStatus = Literal["executed", "approval_required", "blocked"]
IntegrationPreflightStatus = Literal[
    "ready",
    "api_unreachable",
    "api_degraded",
    "unregistered",
    "signature_invalid",
    "unverified_or_forbidden",
    "agent_suspended",
    "agent_revoked",
    "agent_migrated",
    "nonce_replay",
    "rate_limited",
    "backend_or_config_unavailable",
    "unexpected_response",
]


@dataclass(frozen=True)
class ControlledActionOutcome:
    """Result returned by AVPAgent.controlled_action.

    The object exposes typed attributes for IDEs and static tooling. It also
    supports light dict-style access for ergonomic migration from examples.
    """

    status: ControlledActionStatus
    decision: Optional[dict[str, Any]] = None
    receipt_jcs: Optional[str] = None
    receipt: Optional[dict[str, Any]] = None
    approval: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    audit_id: Optional[str] = None
    approval_id: Optional[str] = None

    def __getitem__(self, key: str) -> Any:
        if not hasattr(self, key):
            raise KeyError(key)
        value = getattr(self, key)
        if value is None:
            raise KeyError(key)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        if not hasattr(self, key):
            return default
        value = getattr(self, key)
        return default if value is None else value

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"status": self.status}
        for key in (
            "decision",
            "receipt_jcs",
            "receipt",
            "approval",
            "reason",
            "audit_id",
            "approval_id",
        ):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data


@dataclass(frozen=True)
class ProofPacket:
    """Explicit-input proof bundle for a controlled-action workflow."""

    agent_did: str
    base_url: str
    sdk_version: str
    generated_at: str
    delegation_receipt: dict[str, Any]
    outcome_status: ControlledActionStatus
    audit_id: Optional[str] = None
    decision_receipt_jcs: Optional[str] = None
    decision_receipt: Optional[dict[str, Any]] = None
    execution_receipt_jcs: Optional[str] = None
    execution_receipt: Optional[dict[str, Any]] = None
    approval: Optional[dict[str, Any]] = None
    approval_receipt_jcs: Optional[str] = None
    approval_receipt: Optional[dict[str, Any]] = None
    remediation_case: Optional[dict[str, Any]] = None
    remediation_refs: Optional[list[dict[str, Any]]] = None

    def __getitem__(self, key: str) -> Any:
        if not hasattr(self, key):
            raise KeyError(key)
        value = getattr(self, key)
        if value is None:
            raise KeyError(key)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        if not hasattr(self, key):
            return default
        value = getattr(self, key)
        return default if value is None else value

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key in (
            "agent_did",
            "base_url",
            "sdk_version",
            "generated_at",
            "delegation_receipt",
            "outcome_status",
            "audit_id",
            "decision_receipt_jcs",
            "decision_receipt",
            "execution_receipt_jcs",
            "execution_receipt",
            "approval",
            "approval_receipt_jcs",
            "approval_receipt",
            "remediation_case",
            "remediation_refs",
        ):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data


@dataclass(frozen=True)
class IntegrationPreflightReport:
    """Safety-preserving readiness check before first integration."""

    ready: bool
    status: IntegrationPreflightStatus
    next_action: str
    did: str
    base_url: str
    local_identity_ok: bool = True
    api_reachable: bool = False
    registered: Optional[bool] = None
    verified: Optional[bool] = None
    agent_status: Optional[str] = None
    successor_did: Optional[str] = None
    signed_request_ok: bool = False
    status_code: Optional[int] = None
    detail: Optional[str] = None
    retry_after: Optional[int] = None

    def __getitem__(self, key: str) -> Any:
        if not hasattr(self, key):
            raise KeyError(key)
        value = getattr(self, key)
        if value is None:
            raise KeyError(key)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        if not hasattr(self, key):
            return default
        value = getattr(self, key)
        return default if value is None else value

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key in (
            "ready",
            "status",
            "next_action",
            "did",
            "base_url",
            "local_identity_ok",
            "api_reachable",
            "registered",
            "verified",
            "agent_status",
            "successor_did",
            "signed_request_ok",
            "status_code",
            "detail",
            "retry_after",
        ):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data


__all__ = [
    "ControlledActionOutcome",
    "ControlledActionStatus",
    "IntegrationPreflightReport",
    "IntegrationPreflightStatus",
    "ProofPacket",
]
