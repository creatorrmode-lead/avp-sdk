# AVP Protocol Specification v0.1

## Overview

AVP is a trust enforcement layer for autonomous agents.
It combines cryptographic identity, peer reputation,
and admission decisions.

## Agent Identity

Every agent has a W3C DID (did:key) based on Ed25519.

DID format: did:key:z{base58(multicodec_prefix + public_key)}
Multicodec prefix for Ed25519: 0xED01

Keys stored locally: ~/.avp/agents/{name}.json (chmod 0600)

## Authentication

All write operations are signed:

Authorization: AVP-Sig did="...", ts="...", nonce="...", sig="..."

Signature covers: {METHOD}:{PATH}:{timestamp}:{nonce}:{sha256(body)}

This prevents replay attacks and request tampering.

## Attestations

Structure:
- from_did: attesting agent
- to_did: attested agent
- outcome: positive | negative | neutral
- weight: 0.0 - 1.0
- context: task category
- evidence_hash: sha256 of interaction log (required for negative)
- signature: Ed25519 signature of attestation payload

## Agent Cards

Machine-readable capability declarations:
- did: agent identifier
- display_name: human readable name
- capabilities: list of skill tags
- provider: underlying model provider
- endpoint: optional HTTP endpoint

## Reputation

Reputation scores are computed server-side using
peer attestations as input. Scores range from 0.0 to 1.0.
Per-category tracks are supported.

## Verifiable Credentials

Reputation credentials are Ed25519-signed JWTs.
Offline verification: AVPAgent.verify_credential(cred)
does not require server access.

## What This Spec Covers

This document covers the public protocol interface:
identity format, authentication scheme, attestation
structure, and credential format.

Internal reputation algorithms, sybil detection logic,
and dispute resolution mechanisms are proprietary
implementations not covered by this specification.
