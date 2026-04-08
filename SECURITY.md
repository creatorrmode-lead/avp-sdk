# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| < 0.4   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in `agentveil`, please report it responsibly.

**Email:** security@agentveil.dev

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

## Disclosure Policy

We follow coordinated disclosure. Please do not open public issues for security vulnerabilities.
