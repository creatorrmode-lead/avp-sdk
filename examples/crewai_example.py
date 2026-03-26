"""
CrewAI + Agent Veil Protocol integration example.

Shows how to:
    1. Give CrewAI agents AVP reputation tools
    2. Check reputation before delegating tasks
    3. Log interaction results as attestations
    4. Wrap agent functions with @avp_tracked

Prerequisites:
    pip install agentveil crewai

Usage:
    python examples/crewai_example.py
"""

from agentveil import AVPAgent
from agentveil.tools.crewai import AVPReputationTool, AVPDelegationTool, AVPAttestationTool

AVP_URL = "https://agentveil.dev"


def main():
    # === Step 1: Register AVP agents ===
    print("=== Registering agents on AVP ===")

    researcher = AVPAgent.create(AVP_URL, name="crewai_researcher")
    researcher.register(display_name="CrewAI Researcher")
    researcher.publish_card(capabilities=["research", "analysis"], provider="openai")

    writer = AVPAgent.create(AVP_URL, name="crewai_writer")
    writer.register(display_name="CrewAI Writer")
    writer.publish_card(capabilities=["writing", "editing"], provider="anthropic")

    reviewer = AVPAgent.create(AVP_URL, name="crewai_reviewer")
    reviewer.register(display_name="CrewAI Reviewer")
    reviewer.publish_card(capabilities=["code_review", "quality_assurance"], provider="openai")

    print(f"Researcher: {researcher.did[:40]}...")
    print(f"Writer:     {writer.did[:40]}...")
    print(f"Reviewer:   {reviewer.did[:40]}...")

    # === Step 2: Create AVP tools ===
    print("\n=== Creating AVP tools ===")

    rep_tool = AVPReputationTool(base_url=AVP_URL, agent_name="crewai_researcher")
    del_tool = AVPDelegationTool(base_url=AVP_URL, agent_name="crewai_researcher")
    att_tool = AVPAttestationTool(base_url=AVP_URL, agent_name="crewai_researcher")

    print("Tools ready: check_avp_reputation, should_delegate_to_agent, log_avp_interaction")

    # === Step 3: Check reputation before delegation ===
    print("\n=== Checking writer reputation ===")
    rep_result = rep_tool._run(did=writer.did)
    print(f"Reputation: {rep_result}")

    # === Step 4: Decide on delegation ===
    print("\n=== Delegation decision ===")
    del_result = del_tool._run(did=writer.did, min_score=0.3)
    print(f"Decision: {del_result}")

    # === Step 5: Log interaction after task ===
    print("\n=== Logging interactions ===")

    # Researcher attests writer (positive)
    att_result = att_tool._run(did=writer.did, outcome="positive", context="research_task")
    print(f"Researcher -> Writer: {att_result}")

    # Writer attests reviewer (positive)
    att_tool_writer = AVPAttestationTool(base_url=AVP_URL, agent_name="crewai_writer")
    att_result2 = att_tool_writer._run(did=reviewer.did, outcome="positive", context="editing_task")
    print(f"Writer -> Reviewer: {att_result2}")

    # === Step 6: Check updated reputations ===
    print("\n=== Updated reputations ===")
    for name, agent in [("Researcher", researcher), ("Writer", writer), ("Reviewer", reviewer)]:
        rep = researcher.get_reputation(agent.did)
        print(f"{name}: score={rep['score']:.3f}, confidence={rep['confidence']:.3f}")

    # === Step 7: Use with CrewAI Crew (requires LLM API key) ===
    print("\n=== CrewAI Crew setup (requires OPENAI_API_KEY) ===")
    print("""
    # To run with actual CrewAI agents:
    #
    # from crewai import Agent, Task, Crew
    #
    # researcher_agent = Agent(
    #     role="Research Analyst",
    #     goal="Find and verify information",
    #     backstory="Expert researcher with reputation awareness",
    #     tools=[
    #         AVPReputationTool(base_url=AVP_URL),
    #         AVPDelegationTool(base_url=AVP_URL),
    #         AVPAttestationTool(base_url=AVP_URL),
    #     ],
    # )
    #
    # task = Task(
    #     description="Research AI agent trust and check collaborator reputation",
    #     expected_output="Research report with trust verification",
    #     agent=researcher_agent,
    # )
    #
    # crew = Crew(agents=[researcher_agent], tasks=[task])
    # result = crew.kickoff()
    """)

    print("=== Done ===")


if __name__ == "__main__":
    main()
