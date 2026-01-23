"""
Clean Chat Service - Simple, reliable chat with MCP tool execution.

Design principles:
1. Sync operations where possible
2. Clear tool execution flow
3. Proper error handling
4. LLM makes all decisions (no keyword hacks)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from server.tools import (
    AksArcValidateTool,
    AksArcLogsTool,
    AksArcSupportTool,
    ArcConnectivityCheckTool,
    ArcGatewayEgressCheckTool,
    AzLocalEnvCheckWrapTool,
    AzLocalTsgTool,
    DiagnosticsBundleTool,
    ArcOpsEducationalTool,
)

logger = logging.getLogger(__name__)


# System prompt that teaches the LLM when to use each tool
SYSTEM_PROMPT = """You are ArcOps Assistant, a diagnostic AI for Azure Local and AKS Arc environments.

AVAILABLE TOOLS:
1. arc.connectivity.check - Check network connectivity to 52+ Azure endpoints (DNS, TLS, firewall)
2. arc.gateway.egress - Check TLS/Proxy/FQDN reachability for Arc gateway endpoints
3. azlocal.envcheck - Run Azure Local Environment Checker for host validation
4. azlocal.tsg.search - Search troubleshooting guides for ANY error message or symptom
5. aks.arc.validate - Validate AKS Arc cluster configuration (extensions, CNI, versions)
6. aksarc.support.diagnose - Detect known AKS Arc issues (MOC, certs, VMMS)
7. aksarc.logs.collect - Collect diagnostic logs from AKS Arc cluster nodes
8. arcops.diagnostics.bundle - Create support bundle with evidence files
9. arcops.explain - Get educational content about Azure Local/AKS Arc topics

WHEN TO USE TOOLS:
- Connectivity/firewall/proxy issues → arc.connectivity.check
- Gateway/egress/proxy problems → arc.gateway.egress
- Host validation/environment check → azlocal.envcheck  
- ANY error message or failure → azlocal.tsg.search (use exact error text)
- Cluster health/extensions → aks.arc.validate
- Known AKS Arc issues → aksarc.support.diagnose
- Collect logs for support → aksarc.logs.collect
- Create support bundle → arcops.diagnostics.bundle
- Learn about a topic → arcops.explain

TSG SEARCH RESPONSE FORMAT:
When azlocal.tsg.search returns results, present them clearly:
1. State you found relevant troubleshooting guide(s)
2. For the TOP match:
   - Show the TSG title
   - Provide the GitHub link from "Url" field
   - List ALL fix steps from "FixSteps" array
   - Format Code steps as PowerShell code blocks
3. Mention additional relevant matches with titles and links
4. Always include GitHub URLs

IMPORTANT:
- ALWAYS use azlocal.tsg.search when user mentions ANY error, failure, or problem
- Pass exact error message to the tool's query parameter
- ALWAYS use tools to gather real diagnostic information
- Do NOT make up results or error codes
- Present ACTUAL data returned (URLs, steps, code)
- If tool fails, explain error and suggest alternatives
- Be thorough with fix steps, not just summaries
"""


# MCP Tool Registry - maps tool names to implementations
TOOL_REGISTRY = {
    # Connectivity & Network Tools
    "arc.connectivity.check": ArcConnectivityCheckTool(),
    "arc.gateway.egress": ArcGatewayEgressCheckTool(),
    # Azure Local Environment Tools
    "azlocal.envcheck": AzLocalEnvCheckWrapTool(),
    "azlocal.tsg.search": AzLocalTsgTool(),
    # AKS Arc Tools
    "aks.arc.validate": AksArcValidateTool(),
    "aksarc.support.diagnose": AksArcSupportTool(),
    "aksarc.logs.collect": AksArcLogsTool(),
    # Utility Tools
    "arcops.diagnostics.bundle": DiagnosticsBundleTool(),
    "arcops.explain": ArcOpsEducationalTool(),
}


def get_tools_schema() -> list[dict]:
    """Generate OpenAI-compatible tools schema from registry."""
    tools = []
    for name, tool in TOOL_REGISTRY.items():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
        )
    return tools


async def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute an MCP tool and return the result."""
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return {"error": f"Unknown tool: {name}"}

    try:
        logger.info(f"Executing tool: {name} with args: {arguments}")
        result = await tool.execute(arguments)
        logger.info(f"Tool {name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return {"error": str(e), "tool": name}


class ChatService:
    """
    Simple chat service that uses Foundry Local for LLM and executes MCP tools.
    """

    def __init__(self, endpoint: str, model: str):
        """
        Initialize the chat service.

        Args:
            endpoint: Foundry Local endpoint (e.g., http://127.0.0.1:52621/v1)
            model: Model alias (e.g., phi-4-mini)
        """
        # Normalize endpoint - remove trailing /v1 if present since OpenAI client adds it
        base_url = endpoint.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]

        self.client = OpenAI(
            base_url=f"{base_url}/v1", api_key="foundry-local"  # Foundry doesn't require a real key
        )
        self.model = model
        self.tools_schema = get_tools_schema()
        self.conversation_history: list[dict] = []

    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation_history = []

    async def chat(self, user_message: str, dry_run: bool = False) -> dict[str, Any]:
        """
        Process a user message and return the assistant's response.

        This method:
        1. Sends the message to Foundry with available tools
        2. If the LLM requests tools, executes them
        3. Sends tool results back to LLM for final response

        Args:
            user_message: The user's input
            dry_run: If True, tools will use fixture data

        Returns:
            Dictionary with response, tool_calls, and metadata
        """
        # Build messages array
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})

        # Track what tools were called
        tools_executed = []

        try:
            # First call to LLM with tools
            logger.info(f"Sending message to {self.model}: {user_message[:100]}...")
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, tools=self.tools_schema, tool_choice="auto"
            )

            assistant_message = response.choices[0].message

            # Check if LLM wants to call tools
            if assistant_message.tool_calls:
                logger.info(f"LLM requested {len(assistant_message.tool_calls)} tool(s)")

                # Add assistant message with tool calls to history
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in assistant_message.tool_calls
                        ],
                    }
                )

                # Execute each tool
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Note: dryRun is only added if explicitly requested via API
                    # The tool schemas no longer expose dryRun to prevent LLM misuse
                    if dry_run:
                        tool_args["dryRun"] = True

                    # Execute the tool
                    tool_result = await execute_tool(tool_name, tool_args)
                    tools_executed.append(
                        {
                            "name": tool_name,
                            "arguments": tool_args,
                            "result_summary": self._summarize_result(tool_result),
                        }
                    )

                    # Add tool result to messages
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result),
                        }
                    )

                # Second call to LLM with tool results
                logger.info("Sending tool results back to LLM...")
                final_response = self.client.chat.completions.create(
                    model=self.model, messages=messages
                )
                final_content = final_response.choices[0].message.content
            else:
                # No tools needed, use direct response
                final_content = assistant_message.content

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": final_content})

            return {
                "success": True,
                "response": final_content,
                "tools_executed": tools_executed,
                "model": self.model,
            }

        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"I encountered an error: {e}",
                "tools_executed": tools_executed,
            }

    def _summarize_result(self, result: dict) -> str:
        """Create a brief summary of a tool result."""
        if "error" in result:
            return f"Error: {result['error']}"
        if "summary" in result:
            summary = result["summary"]
            return f"Pass: {summary.get('pass', 0)}, Fail: {summary.get('fail', 0)}, Warn: {summary.get('warn', 0)}"
        if "resultCount" in result:
            return f"Found {result['resultCount']} results"
        if "success" in result:
            return "Success" if result["success"] else "Failed"
        return "Completed"
