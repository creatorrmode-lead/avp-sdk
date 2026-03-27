"""
Paperclip + Agent Veil Protocol integration example.

Shows how to:
    1. Register Paperclip company agents on AVP
    2. Use AVP trust tools within Paperclip heartbeat cycles
    3. Evaluate team reputation before task delegation
    4. Generate heartbeat trust reports with peer attestations
    5. Detect reputation degradation via velocity tracking

Paperclip has no built-in trust layer. AVP adds:
    - Cryptographic identity (DID) for each agent
    - EigenTrust reputation scoring
    - Signed attestations between agents
    - Team-level trust evaluation
    - Reputation velocity alerts

Prerequisites:
    pip install agentveil

Usage:
    python examples/paperclip_example.py
"""

from agentveil import AVPAgent
from agentveil.tools.paperclip import (
    avp_check_reputation,
    avp_should_delegate,
    avp_log_interaction,
    avp_evaluate_team,
    avp_heartbeat_report,
    configure,
)

AVP_URL = "https://agentveil.dev"


def main():
    configure(base_url=AVP_URL, agent_name="paperclip_ceo")

    # === Step 1: Register a Paperclip company's agents on AVP ===
    print("=== Registering Paperclip company agents on AVP ===")

    ceo = AVPAgent.create(AVP_URL, name="paperclip_ceo")
    ceo.register(display_name="Paperclip CEO Agent")
    ceo.publish_card(capabilities=["strategy", "delegation", "coordination"], provider="anthropic")

    engineer = AVPAgent.create(AVP_URL, name="paperclip_engineer")
    engineer.register(display_name="Paperclip Engineer Agent")
    engineer.publish_card(capabilities=["code_review", "implementation", "testing"], provider="anthropic")

    writer = AVPAgent.create(AVP_URL, name="paperclip_writer")
    writer.register(display_name="Paperclip Content Writer")
    writer.publish_card(capabilities=["content_writing", "editing", "research"], provider="anthropic")

    print(f"CEO:      {ceo.did[:40]}...")
    print(f"Engineer: {engineer.did[:40]}...")
    print(f"Writer:   {writer.did[:40]}...")

    # === Step 2: CEO checks reputation before delegating ===
    print("\n=== CEO checks engineer reputation before delegation ===")
    rep_result = avp_check_reputation(did=engineer.did)
    print(f"Engineer reputation: {rep_result}")

    # === Step 3: Delegation decision ===
    print("\n=== Delegation decision ===")
    del_result = avp_should_delegate(did=engineer.did, min_score=0.3)
    print(f"Should delegate: {del_result}")

    # === Step 4: Evaluate entire team ===
    print("\n=== Team evaluation ===")
    team_result = avp_evaluate_team(dids=[ceo.did, engineer.did, writer.did])
    print(f"Team report: {team_result}")

    # === Step 5: Simulate heartbeat — agents work and rate each other ===
    print("\n=== Simulating heartbeat cycle ===")

    # CEO rates engineer and writer after they complete tasks
    print("CEO attesting engineer (positive)...")
    avp_log_interaction(did=engineer.did, outcome="positive", context="code_implementation")

    print("CEO attesting writer (positive)...")
    avp_log_interaction(did=writer.did, outcome="positive", context="content_creation")

    # Engineer rates writer for collaboration
    configure(agent_name="paperclip_engineer")
    print("Engineer attesting writer (positive)...")
    avp_log_interaction(did=writer.did, outcome="positive", context="documentation_review")

    # === Step 6: Generate heartbeat trust report ===
    print("\n=== Heartbeat trust report ===")
    configure(agent_name="paperclip_ceo")
    report = avp_heartbeat_report(
        agent_did=ceo.did,
        peers_evaluated=[
            {"did": engineer.did, "outcome": "positive", "context": "sprint_completion"},
            {"did": writer.did, "outcome": "positive", "context": "content_delivery"},
        ],
    )
    print(f"Report: {report}")

    # === Step 7: Check updated reputations ===
    print("\n=== Updated reputations after heartbeat ===")
    for name, agent in [("CEO", ceo), ("Engineer", engineer), ("Writer", writer)]:
        rep = ceo.get_reputation(agent.did)
        print(f"{name}: score={rep['score']:.3f}, confidence={rep['confidence']:.3f}")

    # === Step 8: Paperclip plugin integration example ===
    print("\n=== Paperclip Plugin setup ===")
    print("""
    # To use AVP as a Paperclip plugin:
    #
    # 1. In your plugin's index.ts:
    #
    #    import { avp_plugin_tools } from 'agentveil/tools/paperclip';
    #    const tools = avp_plugin_tools();
    #    plugin.registerTools(tools);
    #
    # 2. In your SKILLS.md, add:
    #
    #    ## Trust Verification
    #    Before delegating any task, use avp_check_reputation to verify
    #    the target agent's trust score. Only delegate if score >= 0.5.
    #
    #    After each heartbeat, use avp_heartbeat_report to log peer
    #    evaluations and track reputation velocity.
    #
    # 3. Agents will automatically have access to AVP tools
    #    alongside their standard Paperclip tools.
    """)

    print("=== Done ===")


if __name__ == "__main__":
    main()
