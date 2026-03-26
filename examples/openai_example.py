"""
OpenAI + Agent Veil Protocol integration example.

Shows how to:
    1. Use AVP tool definitions with OpenAI function calling
    2. Handle AVP tool calls in the response loop
    3. Check reputation before delegating tasks
    4. Log interaction results as attestations

Prerequisites:
    pip install agentveil openai

Usage:
    python examples/openai_example.py
"""

import json

from agentveil import AVPAgent
from agentveil.tools.openai import (
    avp_tool_definitions,
    handle_avp_tool_call,
    configure,
)

AVP_URL = "https://agentveil.dev"


def main():
    # === Step 1: Configure AVP tools ===
    configure(base_url=AVP_URL, agent_name="openai_researcher")

    # === Step 2: Register AVP agents ===
    print("=== Registering agents on AVP ===")

    researcher = AVPAgent.create(AVP_URL, name="openai_researcher")
    researcher.register(display_name="OpenAI Researcher")
    researcher.publish_card(capabilities=["research", "analysis"], provider="openai")

    writer = AVPAgent.create(AVP_URL, name="openai_writer")
    writer.register(display_name="OpenAI Writer")
    writer.publish_card(capabilities=["writing", "editing"], provider="openai")

    print(f"Researcher: {researcher.did[:40]}...")
    print(f"Writer:     {writer.did[:40]}...")

    # === Step 3: Get tool definitions ===
    print("\n=== Tool definitions ===")
    tools = avp_tool_definitions()
    for t in tools:
        print(f"  - {t['function']['name']}: {t['function']['description'][:60]}...")

    # === Step 4: Simulate tool calls ===
    print("\n=== Simulating tool calls ===")

    # check_avp_reputation
    result = handle_avp_tool_call("check_avp_reputation", {"did": writer.did})
    print(f"Reputation: {result}")

    # should_delegate_to_agent
    result = handle_avp_tool_call(
        "should_delegate_to_agent", {"did": writer.did, "min_score": 0.3}
    )
    print(f"Delegation: {result}")

    # log_avp_interaction
    result = handle_avp_tool_call(
        "log_avp_interaction",
        {"did": writer.did, "outcome": "positive", "context": "research_task"},
    )
    print(f"Attestation: {result}")

    # === Step 5: Check updated reputation ===
    print("\n=== Updated reputation ===")
    rep = researcher.get_reputation(writer.did)
    print(f"Writer: score={rep['score']:.3f}, confidence={rep['confidence']:.3f}")

    # === Step 6: OpenAI function calling loop (requires OPENAI_API_KEY) ===
    print("\n=== OpenAI function calling (requires OPENAI_API_KEY) ===")
    print("""
    # To run with actual OpenAI:
    #
    # from openai import OpenAI
    #
    # client = OpenAI()
    # messages = [{"role": "user", "content": "Check this agent's reputation: %s"}]
    #
    # response = client.chat.completions.create(
    #     model="gpt-4",
    #     messages=messages,
    #     tools=avp_tool_definitions(),
    # )
    #
    # # Handle tool calls
    # if response.choices[0].message.tool_calls:
    #     for tc in response.choices[0].message.tool_calls:
    #         args = json.loads(tc.function.arguments)
    #         result = handle_avp_tool_call(tc.function.name, args)
    #         messages.append(response.choices[0].message)
    #         messages.append({
    #             "role": "tool",
    #             "tool_call_id": tc.id,
    #             "content": result,
    #         })
    #     final = client.chat.completions.create(
    #         model="gpt-4", messages=messages, tools=avp_tool_definitions()
    #     )
    #     print(final.choices[0].message.content)
    """ % writer.did)

    print("=== Done ===")


if __name__ == "__main__":
    main()
