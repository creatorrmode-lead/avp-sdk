"""
Claude MCP Server for Agent Veil Protocol.

Runs as an MCP (Model Context Protocol) server that Claude Desktop/Code
can connect to. Exposes AVP reputation tools as MCP tools.

Usage:
    python -m agentveil.tools.claude_mcp

Config for claude_desktop_config.json:
    {
      "mcpServers": {
        "agentveil": {
          "command": "python",
          "args": ["-m", "agentveil.tools.claude_mcp"],
          "env": {
            "AVP_BASE_URL": "https://agentveil.dev",
            "AVP_AGENT_NAME": "claude_agent"
          }
        }
      }
    }
"""

from __future__ import annotations

import json
import logging
import os
import sys

from agentveil.agent import AVPAgent

log = logging.getLogger("agentveil.tools.claude_mcp")

try:
    from mcp.server import Server
    from mcp.server.stdio import run_server
    from mcp.types import Tool, TextContent
except ImportError:
    raise ImportError(
        "mcp is required for AVP Claude MCP server. "
        "Install with: pip install mcp"
    )

# Configuration from environment
AVP_BASE_URL = os.environ.get("AVP_BASE_URL", "https://agentveil.dev")
AVP_AGENT_NAME = os.environ.get("AVP_AGENT_NAME", "claude_agent")

# Agent cache
_agent: AVPAgent | None = None


def _get_agent() -> AVPAgent:
    """Get or create a cached AVPAgent instance."""
    global _agent
    if _agent is None:
        try:
            _agent = AVPAgent.load(AVP_BASE_URL, name=AVP_AGENT_NAME)
        except Exception:
            _agent = AVPAgent.create(AVP_BASE_URL, name=AVP_AGENT_NAME)
            _agent.register()
    return _agent


# --- MCP Server setup ---

server = Server("agentveil")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available AVP tools."""
    return [
        Tool(
            name="check_avp_reputation",
            description=(
                "Check an AI agent's reputation on Agent Veil Protocol. "
                "Provide a DID (did:key:z6Mk...) to get trust score (0-1), "
                "confidence level, and whether they are trustworthy."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "did": {
                        "type": "string",
                        "description": "The DID (did:key:z6Mk...) of the agent to check",
                    },
                },
                "required": ["did"],
            },
        ),
        Tool(
            name="should_delegate_to_agent",
            description=(
                "Decide whether to delegate a task to an AI agent based on their "
                "AVP reputation. Returns a delegation decision with reasoning."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "did": {
                        "type": "string",
                        "description": "The DID of the agent to evaluate",
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum reputation score (0.0-1.0) to approve delegation",
                        "default": 0.5,
                    },
                },
                "required": ["did"],
            },
        ),
        Tool(
            name="log_avp_interaction",
            description=(
                "Log an interaction result with another AI agent on AVP. "
                "Record positive, negative, or neutral outcomes as signed attestations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "did": {
                        "type": "string",
                        "description": "The DID of the agent you interacted with",
                    },
                    "outcome": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"],
                        "description": "Interaction outcome",
                        "default": "positive",
                    },
                    "context": {
                        "type": "string",
                        "description": "Context of the interaction (e.g. 'code_review')",
                        "default": "claude_task",
                    },
                },
                "required": ["did"],
            },
        ),
        Tool(
            name="search_avp_agents",
            description=(
                "Search for AI agents on Agent Veil Protocol by capability or provider. "
                "Returns a list of agents with their DIDs, capabilities, and reputation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {
                        "type": "string",
                        "description": "Filter by capability (e.g. 'code_review', 'research')",
                    },
                    "provider": {
                        "type": "string",
                        "description": "Filter by LLM provider (e.g. 'anthropic', 'openai')",
                    },
                    "min_reputation": {
                        "type": "number",
                        "description": "Minimum reputation score (0.0-1.0)",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "check_avp_reputation":
            agent = _get_agent()
            did = arguments["did"]
            rep = agent.get_reputation(did)
            result = json.dumps({
                "did": did,
                "score": rep.get("score", 0.0),
                "confidence": rep.get("confidence", 0.0),
                "interpretation": rep.get("interpretation", "unknown"),
                "total_attestations": rep.get("total_attestations", 0),
            }, indent=2)

        elif name == "should_delegate_to_agent":
            agent = _get_agent()
            did = arguments["did"]
            min_score = arguments.get("min_score", 0.5)
            rep = agent.get_reputation(did)
            score = rep.get("score", 0.0)
            confidence = rep.get("confidence", 0.0)
            interpretation = rep.get("interpretation", "unknown")

            should_delegate = score >= min_score and confidence > 0.1
            reason = (
                f"Score {score:.2f} >= {min_score:.2f} threshold, "
                f"confidence {confidence:.2f}, rated '{interpretation}'"
                if should_delegate
                else f"Score {score:.2f} < {min_score:.2f} threshold "
                f"or low confidence ({confidence:.2f})"
            )

            result = json.dumps({
                "delegate": should_delegate,
                "did": did,
                "score": score,
                "confidence": confidence,
                "min_score": min_score,
                "reason": reason,
            }, indent=2)

        elif name == "log_avp_interaction":
            agent = _get_agent()
            did = arguments["did"]
            outcome = arguments.get("outcome", "positive")
            context = arguments.get("context", "claude_task")
            att = agent.attest(
                to_did=did,
                outcome=outcome,
                weight=0.8,
                context=context,
            )
            result = json.dumps({
                "status": "recorded",
                "to_did": did,
                "outcome": att.get("outcome", outcome),
                "weight": att.get("weight", 0.8),
                "context": context,
            }, indent=2)

        elif name == "search_avp_agents":
            agent = _get_agent()
            agents = agent.search_agents(
                capability=arguments.get("capability"),
                provider=arguments.get("provider"),
                min_reputation=arguments.get("min_reputation"),
            )
            result = json.dumps(agents, indent=2)

        else:
            result = f"Unknown tool: {name}"

        return [TextContent(type="text", text=result)]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    """Run the MCP server over stdio."""
    async with run_server(server, read_stream=sys.stdin, write_stream=sys.stdout):
        pass


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
