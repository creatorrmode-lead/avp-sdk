"""
AVP authentication helpers.
Builds signed Authorization headers for API requests.
"""

import hashlib
import secrets
import time

from nacl.signing import SigningKey


def build_auth_header(
    private_key: bytes,
    did: str,
    method: str,
    path: str,
    body: bytes = b"",
) -> dict[str, str]:
    """
    Build AVP-Sig Authorization header.

    Signs: {method}:{path}:{timestamp}:{nonce}:{body_sha256}
    Returns dict with Authorization header ready for httpx.

    Args:
        private_key: Ed25519 private key (32 bytes)
        did: Agent's DID (did:key:z6Mk...)
        method: HTTP method (GET, POST, etc.)
        path: URL path (/v1/attestations)
        body: Request body bytes
    """
    ts = int(time.time())
    nonce = secrets.token_hex(16)
    body_hash = hashlib.sha256(body).hexdigest()

    message = f"{method}:{path}:{ts}:{nonce}:{body_hash}"
    signing_key = SigningKey(private_key)
    signed = signing_key.sign(message.encode())
    sig_hex = signed.signature.hex()

    return {
        "Authorization": f'AVP-Sig did="{did}",ts="{ts}",nonce="{nonce}",sig="{sig_hex}"',
        "Content-Type": "application/json",
    }
