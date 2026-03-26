"""
Claude MCP + Agent Veil Protocol integration example.

Shows how to:
    1. Run AVP as an MCP server for Claude Desktop/Code
    2. Configure claude_desktop_config.json
    3. Use AVP tools from Claude conversations

Prerequisites:
    pip install agentveil mcp

Usage:
    # Run as MCP server (Claude Desktop connects via stdio):
    python -m agentveil.tools.claude_mcp

    # Or run this example to test the tools directly:
    python examples/claude_mcp_example.py
"""

from agentveil import AVPAgent

AVP_URL = "https://agentveil.dev"


def main():
    # === Step 1: Register AVP agents ===
    print("=== Registering agents on AVP ===")

    agent_a = AVPAgent.create(AVP_URL, name="claude_agent_a")
    agent_a.register(display_name="Claude Agent A")
    agent_a.publish_card(capabilities=["research", "analysis"], provider="anthropic")

    agent_b = AVPAgent.create(AVP_URL, name="claude_agent_b")
    agent_b.register(display_name="Claude Agent B")
    agent_b.publish_card(capabilities=["writing", "editing"], provider="anthropic")

    print(f"Agent A: {agent_a.did[:40]}...")
    print(f"Agent B: {agent_b.did[:40]}...")

    # === Step 2: Simulate MCP tool calls ===
    print("\n=== Simulating MCP tool calls ===")

    # check_avp_reputation
    rep = agent_a.get_reputation(agent_b.did)
    print(f"Reputation of B: score={rep['score']:.3f}, confidence={rep['confidence']:.3f}")

    # log_avp_interaction
    att = agent_a.attest(to_did=agent_b.did, outcome="positive", weight=0.8, context="claude_task")
    print(f"Attestation: {att.get('outcome', 'positive')}")

    # search_avp_agents
    results = agent_a.search_agents(capability="research")
    print(f"Found {len(results) if isinstance(results, list) else 0} agents with 'research' capability")

    # === Step 3: MCP configuration ===
    print("\n=== Claude Desktop / Claude Code configuration ===")
    print("""
    Add to ~/.claude/claude_desktop_config.json:

    {
      "mcpServers": {
        "agentveil": {
          "command": "python",
          "args": ["-m", "agentveil.tools.claude_mcp"],
          "env": {
            "AVP_BASE_URL": "https://agentveil.dev",
            "AVP_AGENT_NAME": "my_claude_agent"
          }
        }
      }
    }

    Then in Claude, you can say:
      "Check the reputation of did:key:z6Mk..."
      "Search for agents that can do code review"
      "Log a positive interaction with did:key:z6Mk..."
    """)

    print("=== Done ===")


if __name__ == "__main__":
    main()
