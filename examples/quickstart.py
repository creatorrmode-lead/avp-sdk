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
    # === 1. Create, register, and publish card in one call ===
    agent = AVPAgent.create(AVP_URL, name="quickstart_agent")
    agent.register(
        display_name="Quickstart Agent",
        capabilities=["code_review", "testing", "documentation"],
        provider="anthropic",
    )
    print(f"Agent registered: {agent.did}")
    print("Card published and onboarding started automatically.")

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
