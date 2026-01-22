# ArcOps MCP Redesign Plan

## Current Problems

1. **Overly complex architecture** - Multiple layers (FastAPI, MCP SDK, Foundry Local) with poor integration
2. **Model management is broken** - Can't reliably list, download, or start models from UI
3. **SSE streaming issues** - Encoding errors, connection drops
4. **Tool selection unreliable** - Small models can't use tools properly; keyword hacks don't work
5. **No end-to-end testing** - Tools have never been validated with real dependencies

---

## Tool Audit Summary

| Tool | MCP ID | Dependencies | Status |
|------|--------|--------------|--------|
| Connectivity Check | `arc.connectivity.check` | AzStackHci.EnvironmentChecker PS module | ❓ Untested |
| Cluster Validation | `aks.arc.validate` | kubectl, az CLI, kubeconfig | ❓ Untested |
| Known Issues | `aksarc.support.diagnose` | Support.AksArc PS module | ❓ Untested |
| Log Collection | `aksarc.logs.collect` | az CLI + aksarc extension | ❓ Untested |
| TSG Search | `azlocal.tsg.search` | AzLocalTSGTool PS module | ❓ Untested |
| Bundle Creator | `arcops.diagnostics.bundle` | Python stdlib only | ✅ Should work |
| Educational | `arcops.explain` | None (embedded content) | ✅ Should work |

### Required Dependencies to Install

```powershell
# PowerShell modules
Install-Module -Name AzStackHci.EnvironmentChecker -Force -AllowClobber
Install-Module -Name Support.AksArc -Force -AllowClobber
Install-Module -Name AzLocalTSGTool -Force -AllowClobber

# Azure CLI extensions
az extension add --name aksarc

# CLI tools
winget install Kubernetes.kubectl
winget install Microsoft.AzureCLI
```

---

## Foundry Local Models Analysis

### Tool-Capable Models (Required for MCP)

Only these models support `tools` mode - critical for agentic use:

| Model | Size | Tools Support | Recommendation |
|-------|------|---------------|----------------|
| **qwen2.5-0.5b** | 0.52 GB | ✅ Yes | ⚠️ Too small, unreliable tool selection |
| **qwen2.5-1.5b** | 1.25 GB | ✅ Yes | ✅ **Minimum viable** - fast, decent |
| **qwen2.5-7b** | 4.73 GB | ✅ Yes | ✅ **Recommended** - good balance |
| **qwen2.5-14b** | 8.79 GB | ✅ Yes | 🔶 Large but excellent quality |
| **qwen2.5-coder-0.5b** | 0.52 GB | ✅ Yes | ⚠️ Too small |
| **qwen2.5-coder-1.5b** | 1.25 GB | ✅ Yes | ✅ Code-focused alternative |
| **qwen2.5-coder-7b** | 4.73 GB | ✅ Yes | ✅ Best for technical content |
| **qwen2.5-coder-14b** | 8.79 GB | ✅ Yes | 🔶 Premium code model |
| **phi-4-mini** | 3.60 GB | ✅ Yes | ✅ **Best overall** - Microsoft, great quality |

### Models WITHOUT Tool Support (DO NOT USE)

These models are chat-only and cannot call MCP tools:
- phi-4, phi-3.5-mini, phi-3-mini-* (chat only)
- mistral-7b-v0.2 (chat only)
- deepseek-r1-* (reasoning, no tools)
- phi-4-mini-reasoning (reasoning, no tools)
- gpt-oss-20b (chat only)

### Current Downloads
- ✅ phi-4 (8.37 GB) - Chat only, cannot use tools!
- ✅ qwen2.5-0.5b (0.52 GB) - Tools but too small
- ✅ qwen2.5-1.5b (1.25 GB) - Minimum viable

**Action: Download phi-4-mini (3.60 GB) - Best tool-capable model**

---

## New Architecture Design

### Principles

1. **Simplicity** - One clear path from UI → Backend → Foundry → MCP Tools
2. **Reliability** - Sync operations where possible, proper error handling
3. **Visibility** - Show exactly what's happening at each step
4. **LLM does the work** - No keyword hacks, no simulation unless explicitly requested

### Component Responsibilities

```
┌─────────────────────────────────────────────────────────────────┐
│  React UI (Vite)                                                 │
│  - Model selector (shows tool support, downloaded status)        │
│  - Chat interface with tool execution visualization              │
│  - Settings panel for dry-run mode                               │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP/JSON
┌───────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (port 8080)                                      │
│  Endpoints:                                                       │
│  - GET /api/models → List all Foundry models                      │
│  - POST /api/models/start → Start a model (sync, blocking)        │
│  - POST /api/models/stop → Stop current model                     │
│  - POST /api/chat → Chat with tool execution                      │
│  - GET /api/tools → List available MCP tools                      │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼ OpenAI-compatible API
┌───────────────────────────────────────────────────────────────────┐
│  Foundry Local (dynamic port)                                     │
│  - Runs selected model                                            │
│  - Provides /v1/chat/completions endpoint                         │
│  - Returns tool_calls when LLM decides to use tools               │
└───────────────────────────────────────────────────────────────────┘
                              │
                              ▼ tool_calls
┌───────────────────────────────────────────────────────────────────┐
│  MCP Tool Registry (Python classes)                               │
│  - Execute tool based on name/arguments from LLM                  │
│  - Return results to LLM for final response                       │
│  - All tools use real implementations (no simulation by default)  │
└───────────────────────────────────────────────────────────────────┘
```

### Chat Flow (Simplified)

```python
# 1. User sends message
user_message = "Check my connectivity to Azure"

# 2. Build messages with system prompt
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_message}
]

# 3. Send to Foundry with tools
response = foundry_client.chat.completions.create(
    model="phi-4-mini",
    messages=messages,
    tools=MCP_TOOLS_SCHEMA,  # All 7 tools
    tool_choice="auto"
)

# 4. If LLM returns tool_calls, execute them
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        result = execute_mcp_tool(tool_call.function.name, tool_call.function.arguments)
        messages.append({"role": "tool", "content": json.dumps(result), "tool_call_id": tool_call.id})
    
    # 5. Get final response with tool results
    final_response = foundry_client.chat.completions.create(
        model="phi-4-mini",
        messages=messages
    )
    return final_response.choices[0].message.content

# 6. Return direct response if no tools needed
return response.choices[0].message.content
```

### System Prompt (Critical for Tool Selection)

```
You are ArcOps Assistant, a diagnostic AI for Azure Local and AKS Arc environments.

AVAILABLE TOOLS:
1. arc.connectivity.check - Check network connectivity to 52+ Azure endpoints
2. aks.arc.validate - Validate AKS Arc cluster configuration  
3. aksarc.support.diagnose - Detect known AKS Arc issues
4. aksarc.logs.collect - Collect diagnostic logs from cluster nodes
5. azlocal.tsg.search - Search troubleshooting guides for errors
6. arcops.diagnostics.bundle - Create support bundle with evidence
7. arcops.explain - Get educational content about topics

WHEN TO USE TOOLS:
- User mentions connectivity, firewall, proxy, DNS → use arc.connectivity.check
- User mentions cluster health, validation, extensions → use aks.arc.validate
- User mentions error codes or error messages → use azlocal.tsg.search
- User asks about known issues or problems → use aksarc.support.diagnose
- User wants to collect logs → use aksarc.logs.collect
- User wants to learn about a topic → use arcops.explain

ALWAYS use tools to gather real information. Do not make up diagnostic results.
After running a tool, summarize the findings clearly for the user.
```

---

## Implementation Plan

### Phase 1: Dependencies & Testing (Day 1)

1. Install all PowerShell modules
2. Test each tool individually via CLI
3. Verify tool outputs match schema

### Phase 2: Clean Backend (Day 1-2)

1. Remove complex streaming code
2. Implement simple sync chat endpoint
3. Add proper model management endpoints
4. Create robust tool execution loop

### Phase 3: Simple UI (Day 2)

1. Model selector showing:
   - All available models
   - Downloaded status
   - Tool support indicator
   - Recommended badge
2. One-click download/start
3. Chat panel with tool execution display

### Phase 4: Testing & Polish (Day 3)

1. End-to-end test each tool
2. Verify LLM selects correct tools
3. Document common issues

---

## Files to Create/Modify

### New Files
- `server/chat_agent.py` - Clean chat implementation
- `server/model_manager.py` - Foundry model operations
- `server/tool_executor.py` - MCP tool execution

### Files to Simplify
- `server/api_routes.py` - Strip to essential endpoints
- `ui/src/components/ChatPanel.tsx` - Simplify model selector

### Files to Remove
- Complex SSE streaming code
- Keyword detection hacks
- Unused agent code

---

## Success Criteria

1. ✅ User can see ALL Foundry models with download/tool status
2. ✅ User can download and start models with progress feedback
3. ✅ Chat correctly routes to MCP tools based on LLM decision
4. ✅ All 7 tools execute with real dependencies
5. ✅ Clear error messages when dependencies missing
6. ✅ Recommended model (phi-4-mini) highlighted in UI
