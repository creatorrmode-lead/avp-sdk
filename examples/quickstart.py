"""
AgentVeil SDK quickstart — no server required.

Run:
    pip install agentveil
    python examples/quickstart.py
"""

from agentveil import AVPAgent


def main():
    agent = AVPAgent.create(mock=True, name="quickstart-agent")
    agent.register(display_name="Quickstart Agent")
    agent.publish_card(
        capabilities=["code_review", "testing", "documentation"],
        provider="demo",
    )

    rep = agent.get_reputation()
    print(f"did={agent.did}")
    print(f"score={rep['score']}")
    print(f"interpretation={rep['interpretation']}")

    results = agent.search_agents(capability="code_review")
    print(f"matching_agents={len(results)}")

    # Self-attestation is only used here because this is a mock smoke test.
    attestation = agent.attest(
        to_did=agent.did,
        outcome="positive",
        weight=0.8,
        context="quickstart",
    )
    print(f"attestation={attestation['outcome']}")


if __name__ == "__main__":
    main()
