"""
ArcOps Chat - Simplified chat interface using Foundry Local.

This version calls CLI commands directly instead of the MCP server.
"""

import subprocess
import json
import httpx
from pathlib import Path


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_environment",
            "description": "Check if the environment is ready for Azure Local. Validates hardware, OS, networking.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_connectivity", 
            "description": "Test network connectivity to Azure endpoints.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_cluster",
            "description": "Validate AKS Arc cluster configuration.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

SYSTEM = """You help users diagnose Azure Local and AKS Arc deployments.
Use check_environment, check_connectivity, or validate_cluster when asked about status.
Explain results simply and suggest fixes for issues."""


def run_cli(cmd: str) -> dict:
    """Run a CLI command and return parsed JSON output."""
    out_dir = Path("./agent_results")
    out_dir.mkdir(exist_ok=True)
    
    full_cmd = f"python -m cli {cmd} --dry-run --out {out_dir}"
    try:
        result = subprocess.run(
            full_cmd, shell=True, capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        # Find the latest JSON file
        json_files = sorted(out_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if json_files:
            return json.loads(json_files[0].read_text())
        return {"output": result.stdout, "error": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def call_tool(name: str) -> str:
    """Execute a tool and return formatted results."""
    cmd_map = {
        "check_environment": "envcheck",
        "check_connectivity": "egress", 
        "validate_cluster": "validate"
    }
    cmd = cmd_map.get(name)
    if not cmd:
        return f"Unknown tool: {name}"
    
    result = run_cli(cmd)
    
    # Format for display
    if "checks" in result:
        summary = result.get("summary", {})
        lines = [
            f"Target: {result.get('target', 'unknown')}",
            f"Results: {summary.get('pass', 0)} pass, {summary.get('fail', 0)} fail, {summary.get('warn', 0)} warnings",
            ""
        ]
        for check in result.get("checks", [])[:10]:  # Show first 10
            status_icon = {"pass": "✅", "fail": "❌", "warn": "⚠️"}.get(check["status"], "•")
            lines.append(f"{status_icon} {check['name']}: {check.get('message', '')}")
        return "\n".join(lines)
    
    return json.dumps(result, indent=2)


def chat_with_foundry(messages: list, foundry_url: str = "http://localhost:5272") -> dict:
    """Send messages to Foundry Local."""
    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{foundry_url}/v1/chat/completions",
            json={
                "model": "phi-4-mini",
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto"
            }
        )
        return resp.json()


def main():
    print("\n" + "=" * 50)
    print("  ArcOps Chat")
    print("  Natural language diagnostics for Azure Local")
    print("=" * 50)
    print("\nExamples:")
    print("  • Is my environment ready for Azure Local?")
    print("  • Check connectivity to Azure")
    print("  • Validate my cluster")
    print("\nType 'quit' to exit\n")
    
    messages = [{"role": "system", "content": SYSTEM}]
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not user_input or user_input.lower() in ("quit", "exit"):
            break
        
        messages.append({"role": "user", "content": user_input})
        
        try:
            result = chat_with_foundry(messages)
            choice = result["choices"][0]
            msg = choice["message"]
            
            # Handle tool calls
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    print(f"\n🔧 Running {tool_name}...")
                    tool_result = call_tool(tool_name)
                    print(f"\n{tool_result}")
                    
                    messages.append(msg)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_result
                    })
                
                # Get explanation
                result = chat_with_foundry([m for m in messages if m["role"] != "tool"] + 
                                          [{"role": "user", "content": f"Explain these results: {tool_result}"}])
                final = result["choices"][0]["message"]["content"]
                print(f"\nAssistant: {final}\n")
            else:
                print(f"\nAssistant: {msg['content']}\n")
                messages.append(msg)
                
        except httpx.ConnectError:
            print("\n❌ Foundry Local not running.")
            print("   Start it with: foundry model run phi-4-mini\n")
        except Exception as e:
            print(f"\nError: {e}\n")
    
    print("Goodbye!")


if __name__ == "__main__":
    main()
