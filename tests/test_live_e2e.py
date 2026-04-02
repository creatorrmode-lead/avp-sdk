#!/usr/bin/env python3
"""
LIVE End-to-End Smoke Test — SDK → Production Server.

Tests the FULL agent lifecycle against a real running server:
  1. Health check
  2. Register agent (with PoW)
  3. Publish card
  4. Search agents
  5. Create second agent
  6. Agent B attests Agent A
  7. Check reputation
  8. Check reputation tracks
  9. Check reputation velocity
  10. Get agent info

Run:
    python tests/test_live_e2e.py                          # default: https://agentveil.dev
    python tests/test_live_e2e.py http://localhost:8000     # local server

This test creates REAL agents on the server. Use on staging/production
only when you want to verify the full flow works.
"""

import sys
import time
import traceback


def run_smoke_test(base_url: str) -> bool:
    """Run full E2E smoke test. Returns True if all steps pass."""

    from agentveil import AVPAgent

    steps_passed = 0
    steps_total = 10
    errors = []

    def step(num: int, name: str):
        print(f"\n  [{num}/{steps_total}] {name}...")

    def ok(detail: str = ""):
        nonlocal steps_passed
        steps_passed += 1
        suffix = f" — {detail}" if detail else ""
        print(f"       PASS{suffix}")

    def fail(error: str):
        errors.append(error)
        print(f"       FAIL — {error}")

    print(f"\n{'='*60}")
    print(f"  AVP SDK Live E2E Smoke Test")
    print(f"  Server: {base_url}")
    print(f"{'='*60}")

    # --- Step 1: Health ---
    step(1, "Health check")
    try:
        agent_a = AVPAgent.create(base_url, name=f"e2e_a_{int(time.time())}", save=False)
        health = agent_a.health()
        assert health.get("status") == "ok", f"Expected status=ok, got {health}"
        ok(f"status={health['status']}, db={health.get('database', '?')}")
    except Exception as e:
        fail(f"Health check failed: {e}")
        print("\n  ABORT — server unreachable. Fix server first.\n")
        return False

    # --- Step 2: Register Agent A (with PoW) ---
    step(2, "Register Agent A (register + PoW + verify)")
    try:
        t0 = time.time()
        reg_data = agent_a.register(display_name="E2E Smoke Agent A")
        elapsed = time.time() - t0
        assert agent_a.is_registered, "is_registered should be True"
        assert agent_a.is_verified, "is_verified should be True"
        assert "did" in reg_data, "Response missing 'did'"
        assert "agnet_address" in reg_data, "Response missing 'agnet_address'"
        ok(f"did={agent_a.did[:35]}... ({elapsed:.1f}s incl PoW)")
    except Exception as e:
        fail(f"Registration failed: {e}")
        traceback.print_exc()
        print("\n  ABORT — registration broken. This is the critical fix.\n")
        return False

    # --- Step 3: Publish Card ---
    step(3, "Publish Agent A card")
    try:
        card = agent_a.publish_card(
            capabilities=["e2e_test", "smoke_test"],
            provider="anthropic",
            endpoint_url="https://example.com/e2e",
        )
        assert "capabilities" in card, "Card response missing capabilities"
        ok(f"capabilities={card['capabilities']}")
    except Exception as e:
        fail(f"Card publish failed: {e}")
        traceback.print_exc()

    # --- Step 4: Search Agents ---
    step(4, "Search agents by capability")
    try:
        results = agent_a.search_agents(capability="e2e_test")
        # Should find at least the agent we just created
        assert isinstance(results, list), f"Expected list, got {type(results)}"
        ok(f"found {len(results)} agents")
    except Exception as e:
        fail(f"Search failed: {e}")
        traceback.print_exc()

    # --- Step 5: Register Agent B ---
    step(5, "Register Agent B")
    try:
        agent_b = AVPAgent.create(base_url, name=f"e2e_b_{int(time.time())}", save=False)
        t0 = time.time()
        agent_b.register(display_name="E2E Smoke Agent B")
        elapsed = time.time() - t0
        assert agent_b.is_verified, "Agent B should be verified"
        ok(f"did={agent_b.did[:35]}... ({elapsed:.1f}s)")
    except Exception as e:
        fail(f"Agent B registration failed: {e}")
        traceback.print_exc()

    # --- Step 6: Agent B attests Agent A ---
    step(6, "Agent B attests Agent A (positive)")
    try:
        agent_b.publish_card(capabilities=["e2e_test"], provider="openai")
        att = agent_b.attest(
            agent_a.did,
            outcome="positive",
            weight=0.8,
            context="e2e_smoke_test",
        )
        assert att["outcome"] == "positive", f"Expected positive, got {att['outcome']}"
        ok(f"outcome={att['outcome']}, weight={att['weight']}")
    except Exception as e:
        fail(f"Attestation failed: {e}")
        traceback.print_exc()

    # --- Step 7: Check Agent A reputation ---
    step(7, "Get Agent A reputation")
    try:
        rep = agent_a.get_reputation(agent_a.did)
        assert "score" in rep, "Missing score"
        assert "confidence" in rep, "Missing confidence"
        ok(f"score={rep['score']:.4f}, confidence={rep['confidence']:.4f}, interp={rep.get('interpretation', '?')}")
    except Exception as e:
        fail(f"Reputation check failed: {e}")
        traceback.print_exc()

    # --- Step 8: Check reputation tracks ---
    step(8, "Get Agent A reputation tracks")
    try:
        tracks = agent_a.get_reputation_tracks(agent_a.did)
        assert "tracks" in tracks, "Missing tracks"
        track_names = list(tracks["tracks"].keys())
        ok(f"tracks={track_names}")
    except Exception as e:
        fail(f"Reputation tracks failed: {e}")
        traceback.print_exc()

    # --- Step 9: Check reputation velocity ---
    step(9, "Get Agent A reputation velocity")
    try:
        vel = agent_a.get_reputation_velocity(agent_a.did)
        assert "current_score" in vel, "Missing current_score"
        assert "trend" in vel, "Missing trend"
        ok(f"score={vel['current_score']:.4f}, trend={vel['trend']}")
    except Exception as e:
        fail(f"Reputation velocity failed: {e}")
        traceback.print_exc()

    # --- Step 10: Get agent info ---
    step(10, "Get Agent A public info")
    try:
        info = agent_a.get_agent_info(agent_a.did)
        assert info["did"] == agent_a.did, "DID mismatch"
        assert info["status"] == "active", f"Expected active, got {info['status']}"
        ok(f"status={info['status']}, trust_period={info.get('trust_period_active', '?')}")
    except Exception as e:
        fail(f"Agent info failed: {e}")
        traceback.print_exc()

    # --- Summary ---
    print(f"\n{'='*60}")
    if steps_passed == steps_total:
        print(f"  ALL {steps_total} STEPS PASSED")
    else:
        print(f"  {steps_passed}/{steps_total} PASSED, {len(errors)} FAILED")
        for err in errors:
            print(f"    - {err}")
    print(f"{'='*60}\n")

    return steps_passed == steps_total


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://agentveil.dev"
    success = run_smoke_test(url)
    sys.exit(0 if success else 1)
