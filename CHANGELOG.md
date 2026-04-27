# Changelog

All notable changes to the `agentveil` SDK.

## [0.6.2] — 2026-04-27

### Added — DelegationReceipt primitive
- New `agentveil.delegation` module shipping a minimal AVP runtime-
  control primitive: a W3C Verifiable Credential v2.0 receipt that
  records who authorized which agent to act, within what scope, and
  for how long.
- `issue_delegation()` signs a receipt with the principal's Ed25519
  `did:key`. Scope predicates supported in v1: `max_spend`
  (ISO 4217 currency + amount) and `allowed_category` (string value).
  Validity is bounded by `validFrom` / `validUntil`. Receipts are
  canonicalized with RFC 8785 JCS before signing.
- `verify_delegation()` performs offline verification: structure
  checks, expiration window, scope-predicate validation,
  `eddsa-jcs-2022` Data Integrity Proof. No network calls, no
  AVP backend dependency.
- Standalone reference verifier (~180 lines, only `pynacl` /
  `base58` / `jcs` dependencies, no `agentveil` SDK import) at
  `examples/delegation/verify.py` — auditors can read and run it
  without trusting the SDK.
- JSON-LD context pinned at `https://agentveil.dev/contexts/delegation/v1.jsonld`.

### Schema stability
- `DelegationReceipt` v1 wire format is intended to be stable. Future
  extensions add new optional predicates rather than alter existing
  ones — anything else would invalidate already-signed receipts.

### Not changed
- All existing reputation, attestation, registration, MCP, and
  webhook-alert surfaces are untouched.

## [0.6.1] — 2026-04-23

### Added (B3 — negative attestation DX)
- `AVPAgent.attest()` now raises `AVPValidationError` client-side when
  `outcome="negative"` is passed without both `context` and a valid SHA-256
  `evidence_hash` (64 lowercase hex chars). Mirrors the server-side
  requirement in `app/api/v1/attestations.py` so callers fail fast with a
  clear message instead of chasing a 400 from the server.
- Same validation added to `AVPMockAgent.attest()` so mock-mode code paths
  surface the issue before hitting a real backend.
- Docstring updated to mark `context` and `evidence_hash` as REQUIRED for
  negative outcomes.

### Added (B9 partial — explainability for starter floor)
- `ReputationResponse` and `TrustCheckResponse` now expose explicit
  `raw_score`, `display_score`, `floor_applied: bool`, `floor_reason` fields.
- `TrustCheckResponse.reason` includes a human-readable `[starter floor
  applied …]` suffix when applicable.
- `docs/PROTOCOL.md` now has a "Starter Floor Semantics" section.

### Known limitation
- `raw_score` is `null` whenever the starter floor is applied. The backend
  currently stores only the gated score, so the pre-floor signal is not
  recoverable after the fact. `floor_applied = true` is the truthful signal;
  `raw_score` exposure requires a DB migration tracked separately.

### Not changed
- Reputation computation, decision logic, `allowed` / `tier` / `risk_level`
  semantics, and the single source-of-truth (`get_latest_score`).

## [0.6.0] — 2026-04-23

### Changed (behavior change — not backward compatible)
- `register()` no longer blocks on onboarding completion. Onboarding runs
  server-side in the background after `/verify`; the call returns as soon as
  the agent is verified. Prior versions implicitly waited up to ~30s for an
  LLM-driven onboarding challenge and auto-answered it.
- `register()` return dict now includes `onboarding_pending: bool` so callers
  can branch without polling.

### Added
- `auto_answer_onboarding_challenge(max_wait=30.0)` — explicit, opt-in helper
  that reproduces the pre-v0.6.0 behavior (poll challenge, auto-submit a stock
  answer). Returns the challenge result dict or `None`.
- `wait_for_onboarding(timeout=60.0, poll_interval=2.0)` — explicit helper that
  blocks until onboarding reaches a terminal state (`completed` / `failed` /
  `not_started`). Raises `TimeoutError` on timeout.
- Structured `challenge_expired` handling: backend now returns `409` with
  `fresh_challenge` / `fresh_pow_challenge` / `fresh_pow_difficulty` in the
  error body so clients can retry `/verify` without a new `/register` call.

### Deprecated
- `_auto_handle_onboarding_challenge()` — retained as an internal alias for
  one release. New code must use `auto_answer_onboarding_challenge()`.

### Migration
- If you relied on the implicit onboarding wait inside `register()`, add an
  explicit call to `agent.auto_answer_onboarding_challenge()` and/or
  `agent.wait_for_onboarding()` after `register()`.
- If you only care about registration being verified, no code change is
  needed — `register()` now just returns faster.

### Onboarding state semantics (explicit)
`GET /v1/onboarding/{did}` — exact states returned:
- Unknown DID → HTTP 404 "Agent not found".
- Agent exists but `/verify` has not run yet (post-register, pre-verify) →
  200 with `status="not_started"`. Synthetic response (no session row yet).
- Agent verified, no card published, session waiting → 200 with
  `status="pending"` (session row created at verify; pipeline idle).
- Agent verified, card present, background pipeline running → 200 with
  `status="in_progress"` + `current_stage`.
- Terminal states → `status="completed"` or `status="failed"`.

The `not_started` window is narrow (between `/register` and `/verify`) but
real. Clients must treat `status` — not HTTP code — as the source of truth
for onboarding lifecycle.

### Performance note
Latency numbers observed in local validation (register ~0.2s, 5 agents
sequential ~1.4s total) were measured with `POW_DIFFICULTY_BITS=18` — the
documented **development override**. Production default remains **28 bits**;
real client-side PoW solve adds 10-150s on single-threaded CPUs depending
on hardware. What v0.6.0 fixes is the **hidden onboarding-wait block**, not
PoW latency. The two are independent; PoW ergonomics are tracked separately.

## [0.5.8] — 2026-04-22

### Changed
- README: replaced Glama MCP Directory image badge with a plain text link.
  The badge rendered the current Glama quality score ("not tested") which
  looked weak on the PyPI package page. The directory listing is still
  linked, just without the score card image.

### Notes
- No runtime, API, or behavior changes. Pure README/package-metadata update.

## [0.5.7] — 2026-04-17

### Fixed
- `_auto_handle_challenge` no longer blocks the event loop when called from an
  async context. Polling work is now offloaded to a daemon thread
  (`avp-challenge-{name}`); sync callers behave exactly as before.

> Note: versions 0.5.3–0.5.6 were published to PyPI without changelog entries.
> See git history for what changed in those releases.

## [0.5.2] — 2026-04-09

### Added
- `can_trust()` method — advisory trust decision (score + tier + risk + explanation)
- Connects to `GET /v1/reputation/{did}/trust-check` endpoint

## [0.5.1] — 2026-04-09

### Fixed
- Decorator 409 handling — verify actual state from server before retry
- 3 critical SDK bugs: credential field mismatch, version sync, async blocking

### Changed
- Documentation updates for accuracy

## [0.5.0] — 2026-04-08

### Added
- Webhook alerts: `set_alert()`, `alert_url` param in `@avp_tracked`, `AVP_ALERT_URL` env var
- Auto-subscribe to score drop alerts via environment variable

## [0.4.2] — 2026-04-07

### Added
- Hermes Agent skill for agentskills.io
- Jobs Layer demo (`examples/jobs_demo.py`)
- Author metadata, SECURITY.md, expanded keywords

## [0.4.0] — 2026-04-06

### Added
- Onboarding feedback warnings when capabilities missing
- Hermes integration (MCP + skill)

## [0.3.9] — 2026-04-05

### Added
- Auto-challenge in `register()` flow
- `private_key_hex` property for key export
- `save=False` mode with key security warning

## [0.3.8] — 2026-04-04

### Added
- Encrypted key storage (Fernet + machine-derived key)
- HTTP TLS warning when connecting to non-HTTPS endpoints

## [0.3.6] — 2026-04-03

### Added
- `attest_batch()` — submit up to 50 attestations at once
- `get_reputation_bulk()` — query up to 100 agents at once

## [0.3.3] — 2026-04-01

### Added
- One-step registration with auto card creation
- Onboarding challenge support

## [0.3.0] — 2026-03-28

### Added
- Verifiable credentials with Ed25519 signatures and dynamic TTL
- Reputation tracks (per-category scoring)
- Reputation velocity (1d/7d/30d trend)
- Mock mode (`AVPAgent.create(mock=True)`)
- 6 framework integrations: CrewAI, LangGraph, AutoGen, OpenAI, Paperclip, Claude MCP
- MCP server with 11 tools

## [0.2.0] — 2026-03-22

### Added
- `@avp_tracked` decorator for zero-config integration
- Renamed package from `avp-sdk` to `agentveil`

## [0.1.1] — 2026-03-19

### Added
- Initial release: DID identity, attestations, reputation queries
