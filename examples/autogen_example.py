"""
AutoGen + Agent Veil Protocol integration example.

Shows how to:
    1. Give AutoGen agents AVP reputation tools
    2. Check reputation before delegating tasks
    3. Log interaction results as attestations
    4. Use FunctionTool wrappers with AutoGen agents

Prerequisites:
    pip install agentveil autogen-core

Usage:
    python examples/autogen_example.py
"""

from agentveil import AVPAgent
from agentveil.tools.autogen import (
    check_avp_reputation,
    should_delegate_to_agent,
    log_avp_interaction,
    avp_reputation_tools,
    configure,
)

AVP_URL = "https://agentveil.dev"


def main():
    # === Step 1: Configure AVP tools ===
    configure(base_url=AVP_URL, agent_name="autogen_researcher")

    # === Step 2: Register AVP agents ===
    print("=== Registering agents on AVP ===")

    researcher = AVPAgent.create(AVP_URL, name="autogen_researcher")
    researcher.register(display_name="AutoGen Researcher")
    researcher.publish_card(capabilities=["research", "analysis"], provider="openai")

    writer = AVPAgent.create(AVP_URL, name="autogen_writer")
    writer.register(display_name="AutoGen Writer")
    writer.publish_card(capabilities=["writing", "editing"], provider="openai")

    print(f"Researcher: {researcher.did[:40]}...")
    print(f"Writer:     {writer.did[:40]}...")

    # === Step 3: Use functions directly ===
    print("\n=== Checking writer reputation ===")
    rep_result = check_avp_reputation(did=writer.did)
    print(f"Reputation: {rep_result}")

    print("\n=== Delegation decision ===")
    del_result = should_delegate_to_agent(did=writer.did, min_score=0.3)
    print(f"Decision: {del_result}")

    print("\n=== Logging interaction ===")
    att_result = log_avp_interaction(
        did=writer.did, outcome="positive", context="research_task"
    )
    print(f"Attestation: {att_result}")

    # === Step 4: Check updated reputation ===
    print("\n=== Updated reputation ===")
    rep = researcher.get_reputation(writer.did)
    print(f"Writer: score={rep['score']:.3f}, confidence={rep['confidence']:.3f}")

    # === Step 5: Get FunctionTool instances ===
    print("\n=== FunctionTool instances ===")
    tools = avp_reputation_tools()
    for t in tools:
        print(f"  - {t.name}: {t.description[:60]}...")

    # === Step 6: AutoGen agent setup (requires LLM API key) ===
    print("\n=== AutoGen agent setup (requires OPENAI_API_KEY) ===")
    print("""
    # To run with actual AutoGen agents:
    #
    # from autogen_ext.models.openai import OpenAIChatCompletionClient
    # from autogen_agentchat.agents import AssistantAgent
    #
    # model = OpenAIChatCompletionClient(model="gpt-4")
    # tools = avp_reputation_tools()
    #
    # agent = AssistantAgent(
    #     name="researcher",
    #     model_client=model,
    #     tools=tools,
    #     system_message="You are a researcher with reputation awareness.",
    # )
    """)

    print("=== Done ===")


if __name__ == "__main__":
    main()
