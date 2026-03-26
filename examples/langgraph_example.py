"""
LangGraph + Agent Veil Protocol integration example.

Shows how to:
    1. Use AVP reputation tools in a LangGraph workflow
    2. Check reputation before delegating tasks
    3. Log interaction results as attestations
    4. Build a ToolNode with AVP tools

Prerequisites:
    pip install agentveil langchain-core langgraph

Usage:
    python examples/langgraph_example.py
"""

from agentveil import AVPAgent
from agentveil.tools.langgraph import (
    avp_check_reputation,
    avp_should_delegate,
    avp_log_interaction,
    configure,
)

AVP_URL = "https://agentveil.dev"


def main():
    # === Step 1: Configure AVP tools ===
    configure(base_url=AVP_URL, agent_name="langgraph_researcher")

    # === Step 2: Register AVP agents ===
    print("=== Registering agents on AVP ===")

    researcher = AVPAgent.create(AVP_URL, name="langgraph_researcher")
    researcher.register(display_name="LangGraph Researcher")
    researcher.publish_card(capabilities=["research", "analysis"], provider="openai")

    writer = AVPAgent.create(AVP_URL, name="langgraph_writer")
    writer.register(display_name="LangGraph Writer")
    writer.publish_card(capabilities=["writing", "editing"], provider="anthropic")

    print(f"Researcher: {researcher.did[:40]}...")
    print(f"Writer:     {writer.did[:40]}...")

    # === Step 3: Use tools directly ===
    print("\n=== Checking writer reputation ===")
    rep_result = avp_check_reputation.invoke({"did": writer.did})
    print(f"Reputation: {rep_result}")

    print("\n=== Delegation decision ===")
    del_result = avp_should_delegate.invoke({"did": writer.did, "min_score": 0.3})
    print(f"Decision: {del_result}")

    print("\n=== Logging interaction ===")
    att_result = avp_log_interaction.invoke({
        "did": writer.did,
        "outcome": "positive",
        "context": "research_task",
    })
    print(f"Attestation: {att_result}")

    # === Step 4: Check updated reputation ===
    print("\n=== Updated reputation ===")
    rep = researcher.get_reputation(writer.did)
    print(f"Writer: score={rep['score']:.3f}, confidence={rep['confidence']:.3f}")

    # === Step 5: LangGraph workflow setup (requires LLM API key) ===
    print("\n=== LangGraph workflow setup (requires OPENAI_API_KEY) ===")
    print("""
    # To run with actual LangGraph:
    #
    # from langgraph.prebuilt import ToolNode
    # from langgraph.graph import StateGraph, MessagesState
    #
    # tools = [avp_check_reputation, avp_should_delegate, avp_log_interaction]
    # tool_node = ToolNode(tools)
    #
    # workflow = StateGraph(MessagesState)
    # workflow.add_node("tools", tool_node)
    # # ... add LLM node, edges, etc.
    # graph = workflow.compile()
    """)

    print("=== Done ===")


if __name__ == "__main__":
    main()
