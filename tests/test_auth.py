"""Tests for AVP authentication: signature generation and header format."""

import hashlib
import re
import time

from nacl.signing import SigningKey, VerifyKey

from agentveil.auth import build_auth_header
from agentveil.agent import _public_key_to_did


class TestBuildAuthHeader:
    """AVP-Sig authentication header construction."""

    def test_header_format(self, private_key, did):
        headers = build_auth_header(private_key, did, "POST", "/v1/attestations")
        auth = headers["Authorization"]
        assert auth.startswith("AVP-Sig ")
        assert f'did="{did}"' in auth
        assert 'ts="' in auth
        assert 'nonce="' in auth
        assert 'sig="' in auth

    def test_content_type_is_json(self, private_key, did):
        headers = build_auth_header(private_key, did, "GET", "/v1/health")
        assert headers["Content-Type"] == "application/json"

    def test_signature_is_valid_ed25519(self, private_key, did, public_key):
        body = b'{"test": true}'
        headers = build_auth_header(private_key, did, "POST", "/v1/test", body)
        auth = headers["Authorization"]

        # Extract components
        ts = re.search(r'ts="(\d+)"', auth).group(1)
        nonce = re.search(r'nonce="([^"]+)"', auth).group(1)
        sig_hex = re.search(r'sig="([^"]+)"', auth).group(1)

        # Reconstruct signed message
        body_hash = hashlib.sha256(body).hexdigest()
        message = f"POST:/v1/test:{ts}:{nonce}:{body_hash}"

        # Verify signature
        verify_key = VerifyKey(public_key)
        signature = bytes.fromhex(sig_hex)
        verify_key.verify(message.encode(), signature)  # raises if invalid

    def test_timestamp_is_current(self, private_key, did):
        before = int(time.time())
        headers = build_auth_header(private_key, did, "GET", "/v1/health")
        after = int(time.time())

        ts = int(re.search(r'ts="(\d+)"', headers["Authorization"]).group(1))
        assert before <= ts <= after

    def test_nonce_is_unique(self, private_key, did):
        h1 = build_auth_header(private_key, did, "GET", "/v1/health")
        h2 = build_auth_header(private_key, did, "GET", "/v1/health")
        nonce1 = re.search(r'nonce="([^"]+)"', h1["Authorization"]).group(1)
        nonce2 = re.search(r'nonce="([^"]+)"', h2["Authorization"]).group(1)
        assert nonce1 != nonce2

    def test_empty_body_uses_empty_hash(self, private_key, did):
        headers = build_auth_header(private_key, did, "GET", "/v1/health", b"")
        auth = headers["Authorization"]
        sig_hex = re.search(r'sig="([^"]+)"', auth).group(1)
        assert len(sig_hex) == 128  # Ed25519 signature = 64 bytes = 128 hex

    def test_different_bodies_produce_different_signatures(self, private_key, did):
        h1 = build_auth_header(private_key, did, "POST", "/v1/test", b'{"a":1}')
        h2 = build_auth_header(private_key, did, "POST", "/v1/test", b'{"a":2}')
        sig1 = re.search(r'sig="([^"]+)"', h1["Authorization"]).group(1)
        sig2 = re.search(r'sig="([^"]+)"', h2["Authorization"]).group(1)
        assert sig1 != sig2
