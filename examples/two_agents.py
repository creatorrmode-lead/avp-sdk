"""
Two agents interact: discover, attest, check advisory reputation.

Shows the local two-agent flow:
    1. Both agents register
    2. Agent A searches for Agent B by capability
    3. Agents interact (simulated)
    4. Agent A attests Agent B positively
    5. Both check advisory reputation

Usage:
    python examples/two_agents.py
"""

from agentveil import AVPAgent

AVP_URL = "http://localhost:8000"


def main():
    # === Setup: Register both agents ===
    print("=== Registering agents ===")
    agent_a = AVPAgent.create(AVP_URL, name="customer_agent")
    agent_a.register(display_name="Supply Chain Customer")
    agent_a.publish_card(capabilities=["procurement", "supply_chain"], provider="anthropic")

    agent_b = AVPAgent.create(AVP_URL, name="agent_b_router")
    agent_b.register(display_name="Logistics Router")
    agent_b.publish_card(capabilities=["logistics", "routing", "optimization"], provider="openai")

    print(f"Agent A: {agent_a.did[:40]}...")
    print(f"Agent B: {agent_b.did[:40]}...")

    # === Agent A searches for logistics agent ===
    print("\n=== Searching for logistics agents ===")
    results = agent_a.search_agents(capability="logistics")
    print(f"Found {len(results)} logistics agents")

    # === Check Agent B's reputation before hiring ===
    print("\n=== Checking reputation ===")
    rep = agent_a.get_reputation(agent_b.did)
    print(f"Agent B reputation: score={rep['score']}, confidence={rep['confidence']}")
    print(f"Interpretation: {rep['interpretation']}")

    # === Agent A attests Agent B after interaction ===
    print("\n=== Submitting attestation ===")
    att = agent_a.attest(
        agent_b.did,
        outcome="positive",
        weight=0.9,
        context="logistics_task",
    )
    print(f"Attestation submitted: {att['outcome']}, weight={att['weight']}")

    # === Check reputations after attestation ===
    print("\n=== Updated reputations ===")
    rep_b = agent_a.get_reputation(agent_b.did)
    print(f"Agent B: score={rep_b['score']:.3f}, confidence={rep_b['confidence']:.3f}")

    rep_a = agent_b.get_reputation(agent_a.did)
    print(f"Agent A: score={rep_a['score']:.3f}, confidence={rep_a['confidence']:.3f}")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
