"""
Standalone AVP demo — no server required.

Run:
    pip install agentveil
    python standalone_demo.py

This uses mock mode to demonstrate the full SDK without
Docker, Postgres, Redis, or any running server.
"""

from agentveil import AVPAgent

# 1. Create agents (mock=True — no server needed)
alice = AVPAgent.create(mock=True, name="alice")
bob = AVPAgent.create(mock=True, name="bob")

print(f"Alice DID: {alice.did}")
print(f"Bob   DID: {bob.did}")

# 2. Register (instant in mock mode)
alice.register(display_name="Alice — Code Reviewer")
bob.register(display_name="Bob — Security Auditor")
print("\nBoth agents registered.")

# 3. Publish capability cards
alice.publish_card(capabilities=["code_review", "testing"], provider="anthropic")
bob.publish_card(capabilities=["security_audit", "pen_testing"], provider="openai")
print("Cards published.")

# 4. Search for agents by capability
results = alice.search_agents(capability="security_audit")
print(f"\nSearch results for 'security_audit': {len(results)} agents found")
for r in results:
    print(f"  - {r['display_name']}: score={r['reputation_score']}")

# 5. Check reputation before delegating
rep = alice.get_reputation(bob.did)
print(f"\nBob's reputation: score={rep['score']}, confidence={rep['confidence']}, {rep['interpretation']}")

# 6. Submit attestation (Alice rates Bob)
att = alice.attest(bob.did, outcome="positive", weight=0.9, context="code_review")
print(f"\nAttestation submitted: {att['attestation_id']}")

# 7. Check updated reputation
rep2 = alice.get_reputation(bob.did)
print(f"Bob's updated reputation: score={rep2['score']}")

# 8. Reputation tracks (per-category)
tracks = alice.get_reputation_tracks(bob.did)
print(f"\nReputation tracks:")
for track, data in tracks["tracks"].items():
    print(f"  {track}: {data['score']}")

# 9. Reputation velocity
vel = alice.get_reputation_velocity(bob.did)
print(f"\nReputation velocity: trend={vel['trend']}, 7d={vel['velocity']['7d']}")

# 10. Health check
health = alice.health()
print(f"\nHealth: {health}")

print("\n--- Done! All features work without a server. ---")
print("To use with a real server, replace mock=True with:")
print('  agent = AVPAgent.create("https://agentveil.dev", name="alice")')
