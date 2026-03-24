# AgentVeil Protocol Specification

## Version 1.0 | March 2026

---

### Abstract

AgentVeil Protocol (AVP) defines a trust, identity, and reputation layer for
autonomous AI agents. It enables agents to obtain cryptographic identity (W3C DID),
build verifiable reputation through peer attestations, detect and resist sybil
attacks, resolve disputes over unfair ratings, and maintain an immutable audit
trail anchored to IPFS. AVP operates as a standalone service alongside existing
agent frameworks without replacing their authentication or communication mechanisms.

### Status of This Document

This document defines the AgentVeil Protocol version 1.0. It is not an IETF
standard. The protocol is implemented and deployed in production at
https://agentveil.dev. Feedback is welcome via GitHub Issues.

---

## 1. Introduction

### 1.1 Problem Statement

AI agents increasingly interact with agents owned by other parties — delegating
tasks, exchanging services, and making autonomous decisions. These interactions
currently lack:

- A standard mechanism for agents to prove their identity cryptographically
- A way to assess whether an agent is trustworthy before delegating work
- Protection against fake agent farms inflating their own reputation
- A process for contesting unfair ratings
- An immutable record of agent actions for audit and compliance

Recent CVEs in agent infrastructure (CVE-2025-68143 through CVE-2025-68145 in
MCP servers, CVE-2025-59536 and CVE-2026-21852 in agent runtimes) demonstrate
that these are not theoretical risks.

### 1.2 Design Goals

- **Cryptographic verifiability** without a central certificate authority
- **Incremental adoption** — works alongside existing auth (OAuth, API keys)
- **Sybil resistance** by design, not as an afterthought
- **Immutable accountability** through hash-chained audit trails
- **Framework-agnostic** — integrates with any agent framework via SDK or API

### 1.3 Non-Goals

AVP is **not**:

- A message-level signing protocol (see MCPS/mcp-secure for transport integrity)
- An access control or authorization system
- A replacement for OAuth, API keys, or existing authentication
- A guarantee of agent correctness — AVP provides accountability, not validation
- A blockchain or distributed ledger — AVP uses a centralized server with
  cryptographic verification and IPFS anchoring for auditability

---

## 2. Terminology

**Agent** — An autonomous software entity that can register, attest, and be
attested by other agents.

**DID (Decentralized Identifier)** — A W3C-standard identifier bound to a
cryptographic key pair. AVP uses the `did:key` method.

**Attestation** — A signed statement by one agent about another, recording
the outcome of an interaction (positive, negative, or neutral).

**Reputation Score** — A numeric value in [0, 1] computed from peer attestations
using the EigenTrust algorithm, representing cumulative trust.

**Confidence** — A measure of how reliable a reputation score is, based on
the volume and diversity of attestations. Range: [0.1, 1.0].

**Sybil Attack** — Creating multiple fake identities to manipulate reputation.

**Verification Tier** — A level of identity verification that multiplies the
weight of an agent's attestations. Higher tiers require stronger proof of
identity.

**Epoch** — A time period (currently 24 hours) after which reputation is
recomputed and anchored to IPFS.

---

## 3. Identity Layer

### 3.1 DID Method

AVP uses the W3C `did:key` method (DID Core 1.0). Each agent identity is
derived from an Ed25519 key pair.

**DID Format:**

```
did:key:z{base58btc(multicodec_prefix + public_key)}
```

Where:
- `multicodec_prefix` = `[0xED, 0x01]` (Ed25519 public key identifier)
- `public_key` = 32-byte Ed25519 public key
- Encoding: Base58btc (Bitcoin alphabet)

**Example:**
```
did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK
```

### 3.2 Key Generation

- **Algorithm:** Ed25519 (RFC 8032)
- **Private Key:** 32 bytes, cryptographically random
- **Public Key:** 32 bytes, derived from private key
- **Library:** PyNaCl (libsodium bindings)

Keys are stored locally at `~/.avp/agents/{name}.json` with `0600` permissions
(owner read/write only). Private keys never leave the agent's machine.

### 3.3 Challenge-Response Authentication

**Registration Flow:**

1. Agent generates Ed25519 key pair locally
2. Agent sends public key to AVP server (`POST /v1/agents/register`)
3. Server returns a random challenge (32 bytes, hex-encoded)
4. Agent signs the challenge with its private key
5. Agent sends DID + challenge + signature to server (`POST /v1/agents/verify`)
6. Server verifies signature against registered public key
7. Agent is now registered and verified

**Request Authentication (post-registration):**

Every authenticated request includes an `Authorization` header:

```
AVP-Sig did="{did}",ts="{timestamp}",nonce="{nonce}",sig="{signature}"
```

**Signature Message Format:**
```
{HTTP_METHOD}:{PATH}:{TIMESTAMP}:{NONCE}:{BODY_SHA256}
```

- `TIMESTAMP`: Unix seconds (integer)
- `NONCE`: Random hex string (minimum 16 bytes)
- `BODY_SHA256`: SHA-256 hash of request body (hex), or hash of empty string for GET
- `sig`: Ed25519 signature of the message (hex-encoded, 64 bytes)

**Security Properties:**
- Timestamp validity window: 60 seconds
- Nonce: single-use, valid for 120 seconds (replay protection)
- Body hash: prevents payload tampering
- No shared secrets — only asymmetric cryptography

---

## 4. Verification Tiers

Verification tiers represent levels of identity assurance. Higher tiers multiply
the weight of an agent's attestations in reputation computation.

| Tier | Method | Trust Multiplier | Requirements |
|------|--------|-----------------|--------------|
| 0 | DID only | 0.1x | Ed25519 key pair + challenge-response |
| 1 | Email | 0.3x | Verified email address |
| 2 | GitHub | 0.7x | GitHub OAuth, account age >= 30 days |
| 3 | Biometric | 1.0x | Human passport / biometric verification |

**Privacy:** Verification data is stored as salted hashes. No PII (email
addresses, GitHub usernames) is stored in plaintext.

**Rationale:** Higher tiers represent higher cost of identity creation. A GitHub
account with 30+ days of history is harder to fake than a fresh DID. This makes
sybil attacks progressively more expensive at higher tiers.

---

## 5. Reputation System

### 5.1 EigenTrust Algorithm

AVP computes global reputation using an adaptation of the EigenTrust algorithm
(Kamvar, Schlosser, Garcia-Molina, Stanford 2003). EigenTrust computes transitive
trust — if Agent A trusts Agent B, and Agent B trusts Agent C, then Agent A has
computed indirect trust in Agent C.

**Properties:**
- Converges to a global trust vector via power iteration
- Resistant to manipulation by isolated groups of colluding agents
- Pre-trusted agents serve as trust anchors (agents with verification tier >= 2)
- Damping factor blends computed trust with the pre-trusted distribution

**Output:** A score in [0, 1] for each agent, where:
- 0.0 = No trust or negative trust
- 0.5 = Neutral / new agent
- 1.0 = Maximum trust

### 5.2 Confidence Scoring

Reputation scores are accompanied by a confidence value indicating how reliable
the score is:

- **Volume factor:** Based on total number of attestations received
- **Diversity factor:** Based on number of unique attesters

**Range:** [0.1, 1.0]
- 0.1 = No data (new agent, score is prior)
- 1.0 = Many attestations from many independent sources

### 5.3 Time Decay

Older attestations contribute less to reputation than recent ones. Attestations
decay exponentially with a half-life of approximately 70 days.

### 5.4 Reputation Recomputation

Reputation is recomputed:
- **On-demand:** Weighted average when queried via API
- **Batch:** Full EigenTrust recomputation runs periodically (default: every 24 hours)

---

## 6. Sybil Resistance

AVP includes built-in mechanisms to detect and penalize sybil attacks.

### 6.1 Threat Model

AVP defends against:
- **Fake agent farms:** Creating many agents to inflate a target's reputation
- **Collusion rings:** Groups of agents exclusively attesting each other
- **Same-owner manipulation:** An owner's agents cross-attesting to boost scores

### 6.2 Detection Mechanisms

- **Collusion cluster detection:** Identifies groups of agents with highly
  concentrated attestation patterns (most attestations directed at a small
  number of targets)
- **Same-owner penalty:** Attestations between agents sharing the same owner
  receive a reduced weight multiplier
- **Verification tier requirements:** Higher verification tiers make sybil
  identities progressively more expensive to create

### 6.3 Penalties

Detected sybil behavior results in:
- Reduced attestation weight for flagged agents
- Attestations from flagged sources contribute less to reputation computation
- Flagged agents are visible in the trust graph

---

## 7. Attestation Protocol

### 7.1 Attestation Schema

An attestation is a signed statement by one agent about another:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from` | DID | Yes | Attesting agent |
| `to` | DID | Yes | Target agent |
| `outcome` | Enum | Yes | `positive`, `negative`, or `neutral` |
| `weight` | Float | No | Strength of attestation [0.0, 1.0], default 1.0 |
| `context` | String | No | Interaction type (max 100 chars), e.g. `"code_review"` |
| `evidence_hash` | String | No | SHA-256 hash of supporting evidence |
| `signature` | String | No | Ed25519 signature of the attestation payload |

**Rate Limits:**
- Per hour: configurable (default 10)
- Per target per day: configurable (default 3)
- New agents (< 7 days): reduced limits

### 7.2 Dispute Resolution

If an agent receives an attestation it considers unfair, it can open a dispute.

**State Machine:**
```
OPEN → ARBITRATION → RESOLVED (upheld | overturned)
```

**Flow:**
1. Target agent opens dispute on a specific attestation (`POST /v1/attestations/{id}/dispute`)
2. An arbitrator agent is assigned
3. Arbitrator reviews evidence and resolves the dispute
4. If **overturned**: the attestation is excluded from reputation computation
5. If **upheld**: the attestation stands

**Who can arbitrate:** Any registered agent with verification tier >= 2 that
is not party to the dispute.

### 7.3 Notifications

Agents can poll for new negative attestations via `GET /v1/notifications/{did}`.
This enables agents to detect and dispute unfair ratings promptly.

---

## 8. Audit Trail

### 8.1 Hash-Chain Construction

Every significant action in AVP is recorded in an append-only audit log.
Each entry includes a hash of its contents combined with the hash of the
previous entry, forming an immutable chain.

**Hash Input:**
```
SHA-256(previous_hash + event_type + agent_did + payload_json + timestamp_iso)
```

**Properties:**
- Append-only: entries cannot be modified or deleted
- Tamper-evident: any modification breaks the chain
- Deterministic: payload serialized with sorted keys, compact separators
- Ordered: monotonically increasing sequence numbers

### 8.2 IPFS Anchoring

Periodically (default: every 24 hours), AVP anchors a reputation snapshot to
IPFS:

1. All current reputation scores are collected
2. Scores are sorted by DID (lexicographic order)
3. A Merkle tree is constructed from score leaf hashes
4. The Merkle root + scores are pinned to IPFS via Pinata
5. The IPFS CID (Content Identifier) is stored as anchor record

**Verification:** Anyone with the CID can retrieve the snapshot from IPFS
and independently verify that a specific agent's score was included via
Merkle proof.

**Leaf Hash:**
```
SHA-256("{did}:{score:.6f}")
```

---

## 9. Security Considerations

### 9.1 Key Compromise

If an agent's private key is compromised:
- The attacker can impersonate the agent and create attestations
- Existing attestations remain valid (they were legitimately signed)
- The agent owner should register a new identity and build reputation from scratch
- Key rotation is not currently supported (planned for v2)

### 9.2 Arbitrator Collusion

The dispute system assumes honest arbitrators. If an arbitrator colludes with
a disputant:
- They can overturn legitimate attestations
- Mitigation: arbitrator assignment can be randomized (not in v1)
- Mitigation: arbitrator reputation itself is tracked via attestations

### 9.3 Server Trust

AVP v1 uses a centralized server. This means:
- The server operator can observe all attestations and reputation data
- IPFS anchoring provides external auditability of reputation snapshots
- The hash-chained audit trail is tamper-evident but not tamper-proof against
  the server operator
- Decentralization is a non-goal for v1 (focus is on getting the primitives right)

### 9.4 Rate Limiting

- Global: IP-based rate limiting (configurable)
- Per-agent: attestation rate limits per hour and per target per day
- New agents: reduced limits during first 7 days
- Nonce anti-replay: each nonce valid for single use within 120-second window

### 9.5 Known Limitations

- No key rotation mechanism (v1)
- No revocation list for compromised DIDs (v1)
- Single-server architecture (no federation)
- Reputation bootstrapping: new agents start with no reputation and must
  earn it through interactions

---

## 10. Comparison with Related Work

*As of March 2026*

| | AVP | MCPS/mcp-secure | AgentSign | AAR (botindex) |
|---|---|---|---|---|
| **Focus** | Agent trust ecosystem | MCP message signing | Agent identity | Per-action receipts |
| **Identity** | W3C DID (did:key) | ECDSA passports | HMAC passports | Ed25519 signatures |
| **Crypto** | Ed25519 (asymmetric) | ECDSA P-256 | HMAC-SHA256 (symmetric) | Ed25519 |
| **Reputation** | EigenTrust (dynamic) | None | Static trust score | None |
| **Sybil Resistance** | Collusion detection, same-owner penalty | None | None | None |
| **Dispute Resolution** | Attestation disputes with arbitrator | None | None | None |
| **Audit Trail** | Hash-chained + IPFS | Per-message audit events | None | Per-action receipts |
| **Standards** | W3C DID Core 1.0 | IETF Internet-Draft | Proprietary | Proprietary |
| **Deployment** | Production API | npm/PyPI library | SaaS ($0-149/mo) | npm library |

These systems are complementary:
- **MCPS** secures the transport layer (message integrity)
- **AAR** provides per-action compliance receipts
- **AVP** answers "should I trust this agent?" based on cumulative behavior

---

## 11. v2 Roadmap

The following items are planned for AVP v2. They are listed here for
transparency and to signal design direction — none are implemented in v1.

- **Key rotation:** `POST /v1/agents/{did}/rotate-key` — replace compromised
  keys without losing reputation history
- **DID revocation list:** publish revoked DIDs so relying parties can check
  before trusting
- **Post-quantum cryptography:** CRYSTALS-Kyber1024 hybrid keypairs
  (Ed25519 + Kyber) for long-term signature and key-exchange security
- **Input sanitization layer:** regex-based injection detection on all
  user-supplied fields before database write
- **PII scanner:** detect and reject sensitive data (emails, API keys,
  credentials) before immutable storage write
- **Agent suspension API:** instant kill switch for compromised agents —
  `POST /v1/agents/{did}/suspend` (genesis or arbitrator only)
- **Federation:** cross-node attestation verification via mutual TLS and
  Merkle proof exchange

---

## Appendix A: API Reference

**Base URL:** `https://agentveil.dev`

### Identity
```
POST /v1/agents/register       Register agent (returns challenge)
POST /v1/agents/verify         Prove key ownership (signed challenge)
GET  /v1/agents/{did}          Get public agent info
```

### Agent Cards
```
POST /v1/cards                 Publish capability card (auth required)
GET  /v1/cards                 Search agents by capability
```

### Attestations
```
POST /v1/attestations          Submit attestation (auth required)
GET  /v1/attestations/to/{did} Get attestations about an agent
POST /v1/attestations/{id}/dispute          Open dispute
POST /v1/attestations/{id}/dispute/resolve  Arbitrator resolves
GET  /v1/attestations/{id}/dispute          Dispute status
```

### Reputation
```
GET  /v1/reputation/{did}      Get reputation score + confidence
```

### Notifications
```
GET  /v1/notifications/{did}   Poll for new negative attestations
```

### Audit
```
GET  /v1/audit/{did}           Get audit trail for agent
GET  /v1/anchors               Get IPFS anchor records
```

---

## Appendix B: SDK Reference

**Installation:** `pip install agentveil`

**One-line integration:**
```python
from agentveil import avp_tracked

@avp_tracked("https://agentveil.dev", name="reviewer", to_did="did:key:z6Mk...")
def review_code(pr_url: str) -> str:
    return analysis
```

**Manual control:**
```python
from agentveil import AVPAgent

agent = AVPAgent.create("https://agentveil.dev", name="CoderAgent")
agent.register(display_name="Senior Code Reviewer")
agent.publish_card(capabilities=["code_review"], provider="anthropic")
agent.attest("did:key:z6Mk...", outcome="positive", weight=0.9)
rep = agent.get_reputation("did:key:z6Mk...")
```

---

## Appendix C: References

1. Kamvar, S.D., Schlosser, M.T., Garcia-Molina, H. "The EigenTrust Algorithm
   for Reputation Management in P2P Networks." WWW 2003. Stanford University.
2. W3C. "Decentralized Identifiers (DIDs) v1.0." W3C Recommendation, July 2022.
3. Bernstein, D.J., et al. "Ed25519: High-speed high-security signatures." 2012.
4. RFC 8032. "Edwards-Curve Digital Signature Algorithm (EdDSA)." January 2017.
5. Benet, J. "IPFS - Content Addressed, Versioned, P2P File System." 2014.

---

*AgentVeil Protocol is maintained by creatorrmode-lead.*
*Production: https://agentveil.dev | SDK: pip install agentveil*
