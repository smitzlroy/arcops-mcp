"""
ArcOps Chat Agent - Natural language interface to Azure Local/AKS Arc diagnostics.

Uses Foundry Local (or compatible OpenAI endpoint) for inference and calls ArcOps MCP tools.

Key features:
- Dynamically discovers tools from MCP server
- Builds system prompt from available tools
- Supports dry-run mode for testing
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents an MCP tool with its schema."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name.replace(".", "_"),  # OpenAI doesn't like dots in names
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class ArcOpsAgent:
    """
    Chat agent that discovers and uses MCP tools dynamically.

    Args:
        llm_url: URL of the LLM endpoint (Foundry Local or OpenAI-compatible)
        mcp_url: URL of the MCP server
        model: Model name to use for inference
        dry_run: If True, tools default to dry-run mode
    """

    def __init__(
        self,
        llm_url: str = "http://localhost:5272",
        mcp_url: str = "http://localhost:8080",
        model: str = "phi-4-mini",
        dry_run: bool = False,
    ):
        self.llm_url = llm_url
        self.mcp_url = mcp_url
        self.model = model
        self.dry_run = dry_run
        self.tools: list[MCPTool] = []
        self.messages: list[dict] = []
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Initialize the agent by discovering tools from MCP server.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Get tool definitions from MCP manifest
                resp = await client.get(f"{self.mcp_url}/mcp/manifest")
                if resp.status_code != 200:
                    logger.error("Failed to get MCP manifest: %s", resp.status_code)
                    return False

                manifest = resp.json()
                self.tools = []

                for tool_def in manifest.get("tools", []):
                    self.tools.append(
                        MCPTool(
                            name=tool_def["name"],
                            description=tool_def.get("description", ""),
                            input_schema=tool_def.get(
                                "inputSchema", {"type": "object", "properties": {}}
                            ),
                        )
                    )

                logger.info("Discovered %d tools from MCP server", len(self.tools))
                self._initialized = True

                # Build system prompt with discovered tools
                self._build_system_prompt()
                return True

        except httpx.ConnectError:
            logger.error("Cannot connect to MCP server at %s", self.mcp_url)
            return False
        except Exception as e:
            logger.exception("Error initializing agent: %s", e)
            return False

    def _build_system_prompt(self) -> None:
        """Build system prompt based on discovered tools."""
        tool_descriptions = "\n".join(f"- {tool.name}: {tool.description}" for tool in self.tools)

        self.system_prompt = f"""You are ArcOps Assistant, an expert in diagnosing and troubleshooting Azure Local and AKS Arc environments.

## Your Capabilities
You have access to these diagnostic tools:
{tool_descriptions}

## Guidelines
1. When users describe a problem, identify which tool(s) would help diagnose it
2. Run the appropriate tool to gather evidence
3. Explain results in plain language - be specific about what passed and what failed
4. For failures, provide clear remediation steps
5. If multiple issues exist, prioritize by severity (high -> medium -> low)

## Common Scenarios
- "My cluster is offline" -> Use aks.arc.validate to check connectivity and extensions
- "Can't reach Azure" -> Use arc.connectivity.check to test endpoints
- "Deployment failing" -> Use arc.connectivity.check then aks.arc.validate
- "Need a support bundle" -> Use arcops.diagnostics.bundle

Keep responses concise and actionable."""

        self.messages = [{"role": "system", "content": self.system_prompt}]

    def _openai_name_to_mcp(self, name: str) -> str:
        """Convert OpenAI-safe name back to MCP tool name."""
        return name.replace("_", ".")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Call an MCP tool and return the result.

        Args:
            name: OpenAI-format tool name (underscores)
            arguments: Tool arguments

        Returns:
            Tool result as dict
        """
        mcp_name = self._openai_name_to_mcp(name)

        # Apply dry_run if configured and not explicitly set
        if self.dry_run and "dryRun" not in arguments:
            arguments["dryRun"] = True

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.mcp_url}/mcp/tools/{mcp_name}",
                    json={"arguments": arguments},
                )

                if resp.status_code != 200:
                    return {"error": f"Tool call failed: {resp.status_code}", "details": resp.text}

                return resp.json()

        except httpx.ConnectError:
            return {"error": "MCP server not running", "hint": "Start with: python -m cli server"}
        except httpx.TimeoutException:
            return {"error": "Tool execution timed out"}
        except Exception as e:
            return {"error": str(e)}

    async def chat(self, user_message: str) -> str:
        """
        Process a user message and return the response.

        Args:
            user_message: The user's input

        Returns:
            Assistant's response
        """
        if not self._initialized:
            success = await self.initialize()
            if not success:
                return "Cannot connect to MCP server. Start it with: python -m cli server"

        self.messages.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                # Prepare tools in OpenAI format
                tools = [tool.to_openai_format() for tool in self.tools]

                # First call - may request tool use
                resp = await client.post(
                    f"{self.llm_url}/v1/chat/completions",
                    json={
                        "model": self.model,
                        "messages": self.messages,
                        "tools": tools,
                        "tool_choice": "auto",
                    },
                )

                if resp.status_code != 200:
                    return f"LLM error: {resp.status_code} - {resp.text}"

                result = resp.json()

                if "error" in result:
                    return f"Model error: {result['error']}"

                choice = result["choices"][0]
                message = choice["message"]

                # Check if model wants to call a tool
                if message.get("tool_calls"):
                    tool_results = []

                    for tool_call in message["tool_calls"]:
                        fn = tool_call["function"]
                        tool_name = fn["name"]
                        tool_args = json.loads(fn.get("arguments", "{}"))

                        logger.info("Calling tool: %s with args: %s", tool_name, tool_args)
                        print(f"\n[Tool] Running {self._openai_name_to_mcp(tool_name)}...")

                        result = await self.call_tool(tool_name, tool_args)

                        # Summarize result for context window efficiency
                        summary = self._summarize_tool_result(result)

                        tool_results.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "content": summary,
                            }
                        )

                    # Add assistant message with tool calls
                    self.messages.append(message)
                    # Add tool results
                    self.messages.extend(tool_results)

                    # Get final response
                    resp = await client.post(
                        f"{self.llm_url}/v1/chat/completions",
                        json={"model": self.model, "messages": self.messages},
                    )

                    result = resp.json()
                    final_message = result["choices"][0]["message"]
                    self.messages.append(final_message)
                    return final_message.get("content", "")
                else:
                    self.messages.append(message)
                    return message.get("content", "")

        except httpx.ConnectError:
            return "LLM service not available.\n\nIf using Foundry Local, start it with:\n  foundry model run phi-4-mini"
        except Exception as e:
            logger.exception("Error in chat")
            return f"Error: {e}"

    def _summarize_tool_result(self, result: dict[str, Any]) -> str:
        """
        Summarize tool result to reduce token usage.

        Args:
            result: Full tool result

        Returns:
            Summarized string representation
        """
        if "error" in result:
            return json.dumps({"error": result["error"], "hint": result.get("hint")})

        # Extract summary if available
        summary = result.get("summary", {})
        checks = result.get("checks", [])

        # Build concise summary
        output = {
            "target": result.get("target"),
            "summary": summary,
        }

        # Include only failed/warning checks with hints
        issues = [
            {
                "id": c.get("id"),
                "title": c.get("title"),
                "status": c.get("status"),
                "severity": c.get("severity"),
                "hint": c.get("hint"),
            }
            for c in checks
            if c.get("status") in ("fail", "warn")
        ]

        if issues:
            output["issues"] = issues

        # Include a sample of passed checks (first 3)
        passed = [c.get("title") for c in checks if c.get("status") == "pass"][:3]
        if passed:
            output["sample_passed"] = passed
            output["total_passed"] = len([c for c in checks if c.get("status") == "pass"])

        return json.dumps(output, indent=2)

    def reset(self) -> None:
        """Clear conversation history."""
        if self._initialized:
            self._build_system_prompt()
        else:
            self.messages = []


async def main_async():
    """Async interactive chat loop."""
    print("=" * 60)
    print("  ArcOps Assistant")
    print("  Ask questions about your Azure Local / AKS Arc environment")
    print("=" * 60)
    print("\nCommands: /reset (clear history), /quit (exit), /tools (list tools)\n")

    agent = ArcOpsAgent()

    # Initialize - discover tools
    print("Connecting to MCP server...")
    if not await agent.initialize():
        print("Warning: Could not connect to MCP server.")
        print("   Start it with: python -m cli server")
        print("   Continuing in limited mode...\n")
    else:
        print(f"Connected. {len(agent.tools)} tools available.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() == "/quit":
            print("Goodbye!")
            break

        if user_input.lower() == "/reset":
            agent.reset()
            print("Conversation reset.\n")
            continue

        if user_input.lower() == "/tools":
            print("\nAvailable tools:")
            for tool in agent.tools:
                print(f"  - {tool.name}: {tool.description[:60]}...")
            print()
            continue

        response = await agent.chat(user_input)
        print(f"\nAssistant: {response}\n")


def main():
    """Entry point - runs async main."""
    import asyncio

    asyncio.run(main_async())


if __name__ == "__main__":
    main()
