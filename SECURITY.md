# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.5.x   | :white_check_mark: |
| < 0.5   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in `agentveil`, please report it responsibly.

**Email:** ob@agentveil.dev

Please include:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Any suggested fix (optional)

We will acknowledge receipt within **48 hours** and aim to provide an initial assessment within **5 business days**.

## Security Practices

- **Ed25519 signatures** on all authenticated requests
- **Nonce + timestamp** replay protection
- **Input validation** — injection detection on all fields (prompt injection, XSS, SQL injection)
- **PII scanning** — credentials and sensitive data blocked before storage
- **Audit trail** — SHA-256 hash-chained logs anchored to IPFS
- **Key storage** — local keys saved with `chmod 0600` permissions

## Cryptographic Identity

### DID Method: did:key

AVP uses `did:key` (W3C CCG, Ed25519) for agent identifiers. This is a **stateless, self-certifying** method: the DID is derived deterministically from the public key.

**By design, did:key does not support:**
- Key rotation (new key = new DID)
- DID deactivation/revocation at the protocol level
- Key recovery after loss

AVP provides an **application-layer** succession path on top of `did:key` — see DID Succession Protocol below.

**Implications for key compromise:** If an agent's private key is compromised, the attacker gains full control of that identity. AVP mitigates this server-side: agents can be suspended or revoked via the AVP registry, and webhook alerts notify operators of anomalous score drops. However, this protection is scoped to the AVP ecosystem.

**Recommendations:**
- Use encrypted key storage (`agent.save(passphrase="...")`) with Argon2id key derivation for production agents.
- For planned rotation, use the DID Succession Protocol (`POST /v1/agents/migrate`) to transfer reputation to a new keypair.
- For long-lived, high-value agents, consider `did:web` (supports rotation, revocation, key history) when AVP adds support.
- Store keys in hardware security modules (HSM) or secure enclaves where possible.
- Monitor reputation velocity alerts for early compromise detection.

### DID Succession Protocol

AVP supports application-layer key rotation via `POST /v1/agents/migrate`. The old key signs an endorsement of the new key, and reputation transfers to the new DID with a decay factor.

**Protocol:**
- Both old and new keys sign a canonical migration message (prefix `avp:migrate`, includes timestamps and DIDs).
- Signature freshness window: 300 seconds.
- Reputation decay: `new_score = old_score * 0.9`.
- Old DID is marked `SUCCEEDED` and cannot be used for authenticated requests afterward.
- Cooldown between migrations: 30 days per identity.

**What this addresses:** planned rotation (compliance, key hygiene, personnel change) and post-compromise migration when the old key is still under operator control.

**What this does NOT address:** recovery if the old private key is lost — succession requires both signatures. For that scenario, an agent must re-register and rebuild reputation from zero.

### Challenge-Response Authentication

- **Registration challenge:** 64 random hex chars (`secrets.token_hex(32)`), stored in Redis with 300-second TTL. Expired challenges auto-delete. One-time use — consumed on verification.
- **API request auth:** Ed25519 signature over `{method}:{path}:{timestamp}:{nonce}:{body_sha256}`. Timestamp window: 60 seconds. Nonces tracked in Redis with 120-second TTL (2x timestamp window for safety margin). Redis unavailable = fail closed (503).
- **Proof-of-Work:** Required on registration to prevent Sybil attacks. SHA-256 with configurable difficulty (default 24 leading zero bits).

### Credential Signing

Reputation credentials are signed by the server's Ed25519 key (configured via `CREDENTIAL_SIGNING_KEY_HEX`). Two formats available:
- **AVP format:** Custom JSON with hex-encoded signature. Verify with `AVPAgent.verify_credential()`.
- **W3C VC v2.0 format:** Standards-compliant Verifiable Credential with Data Integrity proof (`eddsa-jcs-2022`). Verify with any VC library or `AVPAgent.verify_w3c_credential()`.

Ephemeral signing keys are rejected in production (`CREDENTIAL_SIGNING_KEY_HEX` must be set).

## Disclosure Policy

We follow coordinated disclosure. Please do not open public issues for security vulnerabilities.
