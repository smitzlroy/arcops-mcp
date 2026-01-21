"""
ArcOps Chat Agent - Natural language interface to Azure Local/AKS Arc diagnostics.

Uses Foundry Local for inference and calls ArcOps MCP tools.
"""

import json
import httpx
from typing import Optional


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_environment",
            "description": "Check if the environment is ready for Azure Local deployment. Validates hardware, OS, networking, and prerequisites.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["quick", "full"],
                        "description": "quick = basic checks, full = comprehensive validation"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_connectivity",
            "description": "Test network connectivity to required Azure endpoints. Checks if the system can reach Azure Arc, management APIs, and other required services.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_cluster",
            "description": "Validate an AKS Arc cluster configuration. Checks extensions, CNI settings, Kubernetes version, and Flux configuration.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_diagnostic_bundle",
            "description": "Create a diagnostic bundle with all check results. Packages findings into a ZIP file for support.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

SYSTEM_PROMPT = """You are ArcOps Assistant, helping users diagnose and validate Azure Local and AKS Arc deployments.

You have access to these diagnostic tools:
- check_environment: Validates hardware, OS, and prerequisites
- check_connectivity: Tests network access to required Azure endpoints  
- validate_cluster: Checks AKS Arc cluster configuration
- create_diagnostic_bundle: Packages results for support

When users ask about their environment or cluster status, use the appropriate tool.
Explain results in plain language and suggest fixes for any issues found.

Keep responses concise and helpful."""


class ArcOpsAgent:
    def __init__(self, foundry_port: int = 5272, mcp_port: int = 8080):
        self.foundry_url = f"http://localhost:{foundry_port}"
        self.mcp_url = f"http://localhost:{mcp_port}"
        self.model = "phi-4-mini"
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    def call_tool(self, name: str, args: dict) -> dict:
        """Call an MCP tool and return the result."""
        tool_map = {
            "check_environment": "azlocal.envcheck.wrap",
            "check_connectivity": "arc.gateway.egress.check",
            "validate_cluster": "aks.arc.validate",
            "create_diagnostic_bundle": "arcops.diagnostics.bundle"
        }
        
        mcp_tool = tool_map.get(name)
        if not mcp_tool:
            return {"error": f"Unknown tool: {name}"}
        
        # Map args
        mcp_args = {"dryRun": True}  # Default to dry-run for safety
        if name == "check_environment":
            mcp_args["mode"] = args.get("mode", "quick")
        
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{self.mcp_url}/mcp/tools/{mcp_tool}",
                    json={"arguments": mcp_args}
                )
                return resp.json()
        except httpx.ConnectError:
            return {"error": "MCP server not running. Start it with: python -m cli server"}
        except Exception as e:
            return {"error": str(e)}
    
    def chat(self, user_message: str) -> str:
        """Process a user message and return the response."""
        self.messages.append({"role": "user", "content": user_message})
        
        try:
            with httpx.Client(timeout=120) as client:
                # First call - may request tool use
                resp = client.post(
                    f"{self.foundry_url}/v1/chat/completions",
                    json={
                        "model": self.model,
                        "messages": self.messages,
                        "tools": TOOLS,
                        "tool_choice": "auto"
                    }
                )
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
                        
                        print(f"\n🔧 Running {tool_name}...")
                        result = self.call_tool(tool_name, tool_args)
                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "role": "tool",
                            "content": json.dumps(result, indent=2)
                        })
                    
                    # Add assistant message with tool calls
                    self.messages.append(message)
                    # Add tool results
                    self.messages.extend(tool_results)
                    
                    # Get final response
                    resp = client.post(
                        f"{self.foundry_url}/v1/chat/completions",
                        json={
                            "model": self.model,
                            "messages": self.messages
                        }
                    )
                    result = resp.json()
                    final_message = result["choices"][0]["message"]
                    self.messages.append(final_message)
                    return final_message["content"]
                else:
                    self.messages.append(message)
                    return message["content"]
                    
        except httpx.ConnectError:
            return "❌ Foundry Local not running.\n\nStart it with:\n  foundry model run phi-4-mini --port 5272"
        except Exception as e:
            return f"Error: {e}"
    
    def reset(self):
        """Clear conversation history."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]


def main():
    """Interactive chat loop."""
    print("=" * 60)
    print("  ArcOps Assistant")
    print("  Ask questions about your Azure Local / AKS Arc environment")
    print("=" * 60)
    print("\nCommands: /reset (clear history), /quit (exit)\n")
    
    agent = ArcOpsAgent()
    
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
        
        response = agent.chat(user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()
