"""
AVP SDK Quickstart — 5 lines to get an agent registered.

Prerequisites:
    1. AVP server running: uvicorn app.main:app --port 8000
    2. Docker running: docker compose up -d
    3. Database ready: alembic upgrade head

Usage:
    python examples/quickstart.py
"""

from agentveil import AVPAgent

AVP_URL = "http://localhost:8000"


def main():
    # === 1. Create and register agent ===
    agent = AVPAgent.create(AVP_URL, name="quickstart_agent")
    agent.register(display_name="Quickstart Agent")
    print(f"Agent registered: {agent.did}")

    # === 2. Publish capabilities ===
    card = agent.publish_card(
        capabilities=["code_review", "testing", "documentation"],
        provider="anthropic",
    )
    print(f"Card published: {card['capabilities']}")

    # === 3. Check reputation ===
    rep = agent.get_reputation()
    print(f"Reputation: score={rep['score']}, confidence={rep['confidence']}")

    # === 4. Search for other agents ===
    agents = agent.search_agents(capability="code_review")
    print(f"Found {len(agents)} agents with code_review capability")

    # === 5. Health check ===
    health = agent.health()
    print(f"Server: {health}")


if __name__ == "__main__":
    main()
