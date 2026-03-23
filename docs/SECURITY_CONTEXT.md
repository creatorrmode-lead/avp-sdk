# Why Agent Trust Infrastructure Matters

## The Problem in Numbers

- **88%** of organizations experienced confirmed or suspected security incidents
  involving AI agents in the past year
  *(Gravitee "State of AI Agent Security 2026", n=750 CIO/CTO/VP, Feb 2026)*

- Only **21.9%** treat AI agents as independent, identity-bearing entities.
  The rest share credentials between agents or merge them with existing
  service accounts
  *(Gravitee, Feb 2026)*

- Only **14.4%** of AI agents reached production with full security/IT approval
  *(Gravitee, Feb 2026)*

- Machine-to-human identity ratio in enterprise: **100:1** and growing
  *(Cloud Security Alliance, "State of Cloud and AI Security", March 2026)*

*Note: Gravitee has a commercial interest in agent security infrastructure.
Their survey data is cited as industry context, not as independent research.*


## Recent CVEs Demonstrating the Gap

### MCP Server Vulnerabilities (mcp-server-git)

| CVE | CVSS | Description |
|-----|------|-------------|
| CVE-2025-68143 | 6.5 Medium | Path traversal — `git_init` accepted arbitrary paths, creating repos anywhere on the filesystem |
| CVE-2025-68144 | 6.3 Medium | Argument injection — user-controlled args passed to git CLI without sanitization |
| CVE-2025-68145 | 6.4 Medium | Repository scoping bypass — `--repository` flag did not validate subsequent tool call paths |

All three fixed in mcp-server-git 2025.12.17. Published by GitHub via NVD.

### Agent Runtime Vulnerabilities (Claude Code)

| CVE | CVSS | Description |
|-----|------|-------------|
| CVE-2025-59536 | 8.7 High | Code injection — malicious project files executed before user accepted trust dialog. Fixed in v1.0.111 |
| CVE-2026-21852 | 5.3 Medium | API token exfiltration — modified config files redirected API calls to attacker endpoints before security prompts. Fixed in v2.0.65 |

*These CVEs are not an attack on Anthropic — they demonstrate that agent runtime
vulnerabilities are real even at the best organizations in the industry.*


## Agent Identity Attacks in the Wild

### Moltbook Incident (January 2026)

Moltbook, an AI agent social network, suffered an unsecured database
vulnerability discovered by Wiz Research:

- **Supabase API key** exposed in client-side JavaScript
- **1.5 million** API authentication tokens accessible without authentication
- **35,000** email addresses exposed
- Private messages between agents readable by anyone

The viral "secret language" post — where agents appeared to create an
encrypted communication protocol — turned out to be a human posting under
an agent's credentials, made possible by the platform's complete lack of
agent identity verification.

Meta Platforms acquired Moltbook on March 10, 2026.

*(Sources: 404 Media, Jan 31, 2026; Wiz Research disclosure)*


## The Structural Problem

These incidents share a root cause: **agents operate without verifiable
identity, reputation history, or accountability mechanisms.**

Current state of agent authentication:
- Agents authenticate with **static API keys** (long-lived, shared, easily stolen)
- No standard way to **verify an agent's track record** before delegating work
- No **sybil resistance** — anyone can create N fake agents
- No **dispute mechanism** when agent output is wrong or malicious
- No **immutable audit trail** for agent actions


## What AVP Addresses

| Attack Vector | AVP Mitigation |
|--------------|----------------|
| Agent impersonation | W3C DID (did:key) + Ed25519 challenge-response verification |
| Credential sharing | Per-agent cryptographic keypair, locally stored |
| Platform-wide agent hijacking | Per-agent Ed25519 keypair prevents impersonation even with leaked platform credentials |
| Sybil attacks (fake agent farms) | Collusion cluster detection, same-owner penalty |
| No accountability | Hash-chained audit trail (SHA-256) + IPFS anchoring |
| Blind delegation | EigenTrust reputation from peer attestations |
| Unfair ratings | Attestation dispute resolution with arbitrator |
| Static trust scores | Dynamic reputation via power iteration algorithm |


## References

1. Gravitee. "State of AI Agent Security 2026." February 4, 2026.
   Survey conducted by Opinion Matters, n=750 CIO/CTO/VP, US+UK.
2. Cloud Security Alliance. "State of Cloud and AI Security." March 2026.
3. NIST NVD. CVE-2025-68143, CVE-2025-68144, CVE-2025-68145 (mcp-server-git).
4. NIST NVD. CVE-2025-59536, CVE-2026-21852 (Claude Code, Anthropic).
5. 404 Media. Moltbook vulnerability disclosure. January 31, 2026.
6. Wiz Research. Moltbook database exposure analysis. January 2026.
