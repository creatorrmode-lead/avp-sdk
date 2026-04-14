"""
AWS Bedrock + Agent Veil Protocol — trust-gated agent delegation.

Shows how to:
    1. Register two agents on AVP (orchestrator + worker)
    2. Define AVP reputation tools for Bedrock Converse API
    3. Let Claude check trust before delegating a task
    4. Log interaction result as an attestation

Prerequisites:
    pip install agentveil boto3
    AWS credentials configured (aws configure / IAM role / env vars)

Usage:
    python examples/aws_bedrock.py
    AVP_URL=http://localhost:8000 python examples/aws_bedrock.py
"""

import json
import os

import boto3
from agentveil import AVPAgent

AVP_URL = os.environ.get("AVP_URL", "https://agentveil.dev")
BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL", "us.anthropic.claude-sonnet-4-20250514-v1:0")
BEDROCK_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# --- AVP tool definitions for Bedrock Converse ---

TOOLS = [
    {
        "toolSpec": {
            "name": "check_reputation",
            "description": "Check an AVP agent's trust score before delegating work. Returns score (0-1), confidence, tier, and risk level.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "did": {
                            "type": "string",
                            "description": "The agent's DID (did:key:z6Mk...)",
                        }
                    },
                    "required": ["did"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "can_trust",
            "description": "Quick yes/no check: is this agent trusted enough for the task? Uses AVP trust-check endpoint.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "did": {
                            "type": "string",
                            "description": "The agent's DID to check",
                        },
                        "min_tier": {
                            "type": "string",
                            "description": "Minimum required tier: newcomer, basic, trusted, elite",
                            "default": "basic",
                        },
                    },
                    "required": ["did"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "log_attestation",
            "description": "Record the outcome of a delegated task as a trust attestation on AVP.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "to_did": {
                            "type": "string",
                            "description": "DID of the agent being rated",
                        },
                        "outcome": {
                            "type": "string",
                            "enum": ["positive", "negative"],
                            "description": "Was the task completed well?",
                        },
                        "context": {
                            "type": "string",
                            "description": "Short description of what was delegated",
                        },
                    },
                    "required": ["to_did", "outcome", "context"],
                }
            },
        }
    },
]


def handle_tool(name: str, args: dict, orchestrator: AVPAgent) -> str:
    """Execute an AVP tool call and return result as string."""
    if name == "check_reputation":
        rep = orchestrator.get_reputation(args["did"])
        return json.dumps(rep, indent=2)

    elif name == "can_trust":
        rep = orchestrator.get_reputation(args["did"])
        tier_order = ["newcomer", "basic", "trusted", "elite"]
        min_tier = args.get("min_tier", "basic")
        agent_tier = rep.get("tier", "newcomer")
        trusted = tier_order.index(agent_tier) >= tier_order.index(min_tier)
        return json.dumps({"trusted": trusted, "tier": agent_tier, "score": rep.get("score")})

    elif name == "log_attestation":
        orchestrator.attest(
            to_did=args["to_did"],
            outcome=args["outcome"],
            weight=0.8,
            context=args["context"],
        )
        return json.dumps({"status": "recorded", "outcome": args["outcome"]})

    return json.dumps({"error": f"Unknown tool: {name}"})


def converse_with_tools(client, messages: list, system: str, orchestrator: AVPAgent) -> str:
    """Run Bedrock Converse loop with AVP tool use."""
    while True:
        response = client.converse(
            modelId=BEDROCK_MODEL,
            system=[{"text": system}],
            messages=messages,
            toolConfig={"tools": TOOLS},
        )

        # Collect assistant output
        assistant_content = response["output"]["message"]["content"]
        messages.append({"role": "assistant", "content": assistant_content})

        # Check if model wants to use tools
        stop = response["stopReason"]
        if stop != "tool_use":
            # Extract final text
            for block in assistant_content:
                if "text" in block:
                    return block["text"]
            return ""

        # Process tool calls
        tool_results = []
        for block in assistant_content:
            if "toolUse" in block:
                tu = block["toolUse"]
                print(f"  [tool] {tu['name']}({json.dumps(tu['input'])})")
                result = handle_tool(tu["name"], tu["input"], orchestrator)
                print(f"  [result] {result[:120]}...")
                tool_results.append({
                    "toolResult": {
                        "toolUseId": tu["toolUseId"],
                        "content": [{"text": result}],
                    }
                })

        messages.append({"role": "user", "content": tool_results})


def main():
    print("=" * 60)
    print("  AWS Bedrock + AVP: Trust-Gated Delegation")
    print("=" * 60)

    # === Step 1: Register agents ===
    print("\n[1/4] Registering agents on AVP...")
    orchestrator = AVPAgent.create(AVP_URL, name="bedrock_orchestrator", save=False)
    orchestrator.register(
        display_name="Bedrock Orchestrator",
        capabilities=["orchestration", "delegation"],
        provider="anthropic",
    )

    worker = AVPAgent.create(AVP_URL, name="bedrock_worker", save=False)
    worker.register(
        display_name="Bedrock Worker",
        capabilities=["code_review", "testing"],
        provider="anthropic",
    )

    print(f"  Orchestrator: {orchestrator.did[:40]}...")
    print(f"  Worker:       {worker.did[:40]}...")

    # === Step 2: Check trust via Bedrock ===
    print("\n[2/4] Asking Claude to check worker trust via AVP tools...")
    bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

    system = (
        "You are an orchestrator agent. Before delegating tasks, "
        "always check the worker's reputation using the provided tools. "
        "If the agent is not trusted enough, refuse to delegate."
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        f"I need to delegate a code review task to agent {worker.did}. "
                        "First check their reputation. Then verify they meet at least "
                        "'newcomer' tier. If trusted, the task is approved — log a "
                        "positive attestation with context 'code_review_delegation'."
                    )
                }
            ],
        }
    ]

    print("\n--- Claude Converse (with AVP tools) ---")
    result = converse_with_tools(bedrock, messages, system, orchestrator)
    print(f"\n--- Response ---\n{result}")

    # === Step 3: Verify reputation updated ===
    print("\n[3/4] Checking updated reputation...")
    rep = orchestrator.get_reputation(worker.did)
    print(f"  Worker score: {rep['score']:.3f}, confidence: {rep['confidence']:.3f}")

    # === Step 4: Cleanup ===
    print("\n[4/4] Done. Agents created with save=False (in-memory only).")
    print("  No cleanup needed — keys not persisted to disk.")
    print("=" * 60)


if __name__ == "__main__":
    main()
