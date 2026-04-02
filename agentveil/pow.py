"""
Proof-of-Work solver for AVP anti-sybil registration.

Mirrors server verification logic: find a nonce such that
SHA-256(challenge + nonce) has at least `difficulty` leading zero bits.
"""

import hashlib


def solve_pow(challenge: str, difficulty: int) -> str:
    """
    Solve PoW puzzle by brute-forcing nonces.

    Finds the smallest integer nonce such that
    SHA-256(challenge + str(nonce)) has at least `difficulty` leading zero bits.

    Args:
        challenge: The challenge string from server registration response.
        difficulty: Number of required leading zero bits.

    Returns:
        The nonce as a string.
    """
    full_bytes = difficulty // 8
    remaining_bits = difficulty % 8
    mask = (0xFF >> remaining_bits) ^ 0xFF if remaining_bits else 0

    nonce = 0
    while True:
        nonce_str = str(nonce)
        digest = hashlib.sha256((challenge + nonce_str).encode()).digest()

        valid = True
        for i in range(full_bytes):
            if digest[i] != 0:
                valid = False
                break

        if valid and remaining_bits > 0 and (digest[full_bytes] & mask) != 0:
            valid = False

        if valid:
            return nonce_str
        nonce += 1
