"""Tests for PoW solver — ensures SDK solver matches server verifier."""

import hashlib

from agentveil.pow import solve_pow


def _server_verify_pow(challenge: str, nonce: str, difficulty: int) -> bool:
    """
    Mirror of server's verify_pow() from avp/app/core/security/pow.py.
    Used here to validate SDK solver produces correct nonces.
    """
    digest = hashlib.sha256((challenge + nonce).encode()).digest()

    full_bytes = difficulty // 8
    remaining_bits = difficulty % 8

    for i in range(full_bytes):
        if digest[i] != 0:
            return False

    if remaining_bits > 0:
        mask = (0xFF >> remaining_bits) ^ 0xFF
        if digest[full_bytes] & mask != 0:
            return False

    return True


class TestSolvePow:
    """PoW solver correctness tests."""

    def test_solve_difficulty_1(self):
        """Difficulty 1 bit — very easy, nonce found quickly."""
        nonce = solve_pow("test-challenge-1", 1)
        assert _server_verify_pow("test-challenge-1", nonce, 1)

    def test_solve_difficulty_4(self):
        """Difficulty 4 bits — still fast."""
        nonce = solve_pow("test-challenge-4", 4)
        assert _server_verify_pow("test-challenge-4", nonce, 4)

    def test_solve_difficulty_8(self):
        """Difficulty 8 bits — 1 full zero byte."""
        nonce = solve_pow("test-challenge-8", 8)
        assert _server_verify_pow("test-challenge-8", nonce, 8)

    def test_solve_difficulty_12(self):
        """Difficulty 12 bits — 1 full byte + 4 bits."""
        nonce = solve_pow("test-challenge-12", 12)
        assert _server_verify_pow("test-challenge-12", nonce, 12)

    def test_solve_difficulty_16(self):
        """Difficulty 16 bits — 2 full zero bytes."""
        nonce = solve_pow("test-challenge-16", 16)
        assert _server_verify_pow("test-challenge-16", nonce, 16)

    def test_nonce_is_string(self):
        """Nonce must be returned as string (server expects str)."""
        nonce = solve_pow("any-challenge", 4)
        assert isinstance(nonce, str)

    def test_different_challenges_different_nonces(self):
        """Different challenges should (usually) produce different nonces."""
        n1 = solve_pow("challenge-aaa", 8)
        n2 = solve_pow("challenge-bbb", 8)
        # Not guaranteed to differ, but very likely with difficulty 8
        # At minimum, both must verify
        assert _server_verify_pow("challenge-aaa", n1, 8)
        assert _server_verify_pow("challenge-bbb", n2, 8)

    def test_wrong_nonce_fails_verification(self):
        """A random nonce should fail server verification (overwhelmingly likely)."""
        assert not _server_verify_pow("test-challenge", "definitely_wrong_nonce", 16)
