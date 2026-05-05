# AVP Roadmap

## Current — Public SDK 0.7.5 + Production API

- [x] Public Python SDK 0.7.5 on PyPI: `pip install agentveil`
- [x] Production API for reputation, trust checks, credentials, cards, audit verification, and latest public IPFS anchors
- [x] W3C DID identity (`did:key`, Ed25519)
- [x] AVP-Sig request signing for authenticated protocol calls
- [x] Reputation and advisory trust checks for agent systems
- [x] AVP JSON and W3C reputation credentials with offline verification
- [x] Runtime proof helpers and signed evidence verification
- [x] MCP server: 12 tools in local/full mode, with 8 read-only tools available in hosted mode
- [x] Framework examples for CrewAI, LangGraph, AutoGen, OpenAI, Claude MCP, and Paperclip
- [x] AVPProvider merged into Microsoft Agent Governance Toolkit (PR #1010)

## Guided Pilot

- [x] Runtime Gate decision flow for controlled-action workflows
- [x] Human approval and execution receipt proof model
- [x] Proof packet verification for signed runtime evidence
- [ ] Wider self-service rollout for controlled-action workflows
- [ ] Operator-facing documentation for guided production adoption

## Planned

- [ ] Public agent reputation dashboard
- [ ] Expanded hosted MCP catalog metadata and recrawl
- [ ] Self-hosting documentation for approved deployments
- [ ] Formal protocol specification v1.0
- [ ] Key rotation documentation

## Research / Future

- [ ] Runtime proof and offline verification publication
- [ ] ERC-8004 bridge exploration
- [ ] Federation between AVP nodes
