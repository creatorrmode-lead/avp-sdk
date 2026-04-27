"""
Regenerate sample delegation receipts for verify.py tests.

Test fixture only. Do not use the disposable keypair below for production
delegation. Re-run this script if the schema or signing helper changes:

  python examples/delegation/_generate_samples.py

Outputs three files in samples/:
  - valid.json     properly signed, in window
  - expired.json   properly signed, validUntil in the past
  - tampered.json  signed valid, scope altered after signing
"""

from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Fixed disposable fixture values, checked in for reproducible samples.
# Public and unsafe for production delegation.
PRINCIPAL_SEED_HEX = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
AGENT_SEED_HEX = "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100"

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(HERE, "samples")

# Import delegation.py directly (bypassing agentveil/__init__.py) so this
# fixture script runs in a minimal venv with just pynacl + base58 + jcs,
# without pulling httpx and the rest of the SDK.
import importlib.util  # noqa: E402

_DELEGATION_PATH = os.path.abspath(
    os.path.join(HERE, "..", "..", "agentveil", "delegation.py")
)
_spec = importlib.util.spec_from_file_location("agentveil_delegation", _DELEGATION_PATH)
_delegation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_delegation)
issue_delegation = _delegation.issue_delegation
_public_key_to_did = _delegation._public_key_to_did

from nacl.signing import SigningKey  # noqa: E402


def _did_for(seed_hex: str) -> str:
    sk = SigningKey(bytes.fromhex(seed_hex))
    return _public_key_to_did(bytes(sk.verify_key))


def _write(name: str, receipt: dict) -> None:
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    path = os.path.join(SAMPLES_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {path}")


def main() -> None:
    principal_seed = bytes.fromhex(PRINCIPAL_SEED_HEX)
    agent_did = _did_for(AGENT_SEED_HEX)

    scope = [
        {"predicate": "max_spend", "currency": "USD", "amount": 100},
        {"predicate": "allowed_category", "value": "office_supplies"},
    ]
    purpose = "Procure office supplies for Q2 onboarding kits"

    # --- valid: wide window so the sample stays valid for sample-doc demos ---
    valid_window_start = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
    valid = issue_delegation(
        principal_seed,
        agent_did=agent_did,
        scope=scope,
        purpose=purpose,
        valid_for=timedelta(days=400),
        valid_from=valid_window_start,
        receipt_id="urn:uuid:11111111-1111-4111-8111-111111111111",
    )
    _write("valid.json", valid)

    # --- expired: issued in the past, validUntil < now -----------------------
    past = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    expired = issue_delegation(
        principal_seed,
        agent_did=agent_did,
        scope=scope,
        purpose=purpose,
        valid_for=timedelta(days=1),
        valid_from=past,
        receipt_id="urn:uuid:22222222-2222-4222-8222-222222222222",
    )
    _write("expired.json", expired)

    # --- tampered: identical to `valid` except `credentialSubject.scope` was
    #     altered AFTER signing. Every other field (including `id`) is
    #     preserved so the sample demonstrates exactly one failure mode:
    #     scope tampering invalidates the signature.
    tampered = copy.deepcopy(valid)
    tampered["credentialSubject"]["scope"] = [
        {"predicate": "max_spend", "currency": "USD", "amount": 9999},
        {"predicate": "allowed_category", "value": "office_supplies"},
    ]
    _write("tampered.json", tampered)


if __name__ == "__main__":
    main()
