"""
ArcOps Chat - Simple chat interface for Azure Local diagnostics.

Uses Foundry Local for AI and runs diagnostic tools locally.
"""

import subprocess
import json
import sys
from pathlib import Path

try:
    from foundry_local import FoundryLocalManager

    HAS_SDK = True
except ImportError:
    HAS_SDK = False
    import httpx


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def run_diagnostic(tool_name: str) -> dict:
    """Run a diagnostic tool and return results."""
    cmd_map = {
        "check_environment": "envcheck",
        "check_connectivity": "egress",
        "validate_cluster": "validate",
    }

    cmd = cmd_map.get(tool_name)
    if not cmd:
        return {"error": f"Unknown tool: {tool_name}"}

    out_dir = PROJECT_ROOT / "results"
    out_dir.mkdir(exist_ok=True)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "cli", cmd, "--dry-run", "--out", str(out_dir)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )

        # Find latest output file
        json_files = sorted(out_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if json_files:
            return json.loads(json_files[0].read_text())
        return {"stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def format_results(data: dict) -> str:
    """Format diagnostic results for display."""
    if "error" in data:
        return f"Error: {data['error']}"

    if "checks" not in data:
        return json.dumps(data, indent=2)

    summary = data.get("summary", {})
    lines = [
        f"Target: {data.get('target', 'local')}",
        f"Results: {summary.get('pass', 0)} passed, {summary.get('fail', 0)} failed, {summary.get('warn', 0)} warnings",
        "",
    ]

    for check in data.get("checks", [])[:15]:
        icon = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}.get(check.get("status"), "•")
        name = check.get("name", "Unknown")
        msg = check.get("message", "")
        lines.append(f"  {icon} {name}")
        if msg and check.get("status") != "pass":
            lines.append(f"     {msg}")

    return "\n".join(lines)


def chat_loop_with_sdk():
    """Chat using Foundry Local SDK (handles service automatically)."""
    print("Initializing Foundry Local...")

    try:
        manager = FoundryLocalManager("qwen2.5-0.5b")
        endpoint = manager.endpoint
        
        # Get the actual model ID that's loaded
        loaded = manager.list_loaded_models()
        if loaded:
            model_id = loaded[0].id  # It's an object, not a dict
        else:
            model_id = "qwen2.5-0.5b"
            
        print(f"Using endpoint: {endpoint}")
        print(f"Model: {model_id}")
    except Exception as e:
        print(f"Failed to initialize Foundry Local: {e}")
        print("\nTry running: foundry model run qwen2.5-0.5b")
        return

    import httpx

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        messages.append({"role": "user", "content": user_input})
        response = call_model(endpoint, messages, model_id)

        if response:
            print(f"\nAssistant: {response}")
            messages.append({"role": "assistant", "content": response})


def call_model(endpoint: str, messages: list, model_id: str = "qwen2.5-0.5b") -> str:
    """Call the model and handle tool execution."""
    import httpx

    tools = [
        {
            "type": "function",
            "function": {
                "name": "check_environment",
                "description": "Check if the system is ready for Azure Local deployment",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_connectivity",
                "description": "Test network connectivity to required Azure endpoints",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "validate_cluster",
                "description": "Validate AKS Arc cluster configuration",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{endpoint}/chat/completions",
                json={
                    "model": model_id,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                },
            )
            result = resp.json()

            if "error" in result:
                return f"Model error: {result['error']}"

            msg = result["choices"][0]["message"]

            # Handle tool calls
            if msg.get("tool_calls"):
                tool_outputs = []
                for tc in msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    print(f"\n🔧 Running {tool_name}...")

                    data = run_diagnostic(tool_name)
                    formatted = format_results(data)
                    print(formatted)
                    tool_outputs.append(formatted)

                # Get summary from model
                summary_messages = messages + [
                    {
                        "role": "assistant",
                        "content": f"I ran the diagnostics. Here are the results:\n\n{chr(10).join(tool_outputs)}",
                    },
                    {
                        "role": "user",
                        "content": "Please summarize these results and explain any issues found.",
                    },
                ]

                resp = client.post(
                    f"{endpoint}/chat/completions",
                    json={"model": model_id, "messages": summary_messages},
                )
                return resp.json()["choices"][0]["message"]["content"]

            return msg.get("content", "")

    except httpx.ConnectError:
        return "Cannot connect to Foundry Local. Run: foundry model run qwen2.5-0.5b"
    except Exception as e:
        return f"Error: {e}"


def chat_loop_simple():
    """Simple chat without SDK (requires manual service start)."""
    import httpx

    # Try to find the endpoint
    endpoint = "http://localhost:5272"

    print(f"Connecting to Foundry Local at {endpoint}...")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        messages.append({"role": "user", "content": user_input})
        response = call_model(endpoint, messages)

        if response:
            print(f"\nAssistant: {response}")
            messages.append({"role": "assistant", "content": response})


SYSTEM_PROMPT = """You are ArcOps Assistant. You help users check if their systems are ready for Azure Local and AKS Arc.

When users ask about their environment, connectivity, or cluster status, use the appropriate diagnostic tool:
- check_environment: For hardware, OS, and prerequisite validation
- check_connectivity: For network/firewall/proxy connectivity to Azure
- validate_cluster: For AKS Arc cluster configuration

Explain results in simple terms. If there are failures, explain what they mean and how to fix them."""


def main():
    print()
    print("=" * 50)
    print("  ArcOps Chat")
    print("  Azure Local & AKS Arc Diagnostics")
    print("=" * 50)
    print()
    print("Ask me things like:")
    print("  • Is my system ready for Azure Local?")
    print("  • Check if I can reach Azure")
    print("  • Validate my cluster setup")
    print()
    print("Type 'quit' to exit")
    print()

    if HAS_SDK:
        chat_loop_with_sdk()
    else:
        chat_loop_simple()

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
