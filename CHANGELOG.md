# Changelog

All notable changes to the `agentveil` SDK.

## [0.5.2] — 2026-04-09

### Added
- `can_trust()` method — advisory trust decision (score + tier + risk + explanation)
- Connects to `GET /v1/reputation/{did}/trust-check` endpoint

## [0.5.1] — 2026-04-09

### Fixed
- Decorator 409 handling — verify actual state from server before retry
- 3 critical SDK bugs: credential field mismatch, version sync, async blocking

### Changed
- Honest documentation: clarified Zero-Config and IPFS claims

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
