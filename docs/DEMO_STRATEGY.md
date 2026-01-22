# ArcOps MCP Demo Strategy

## Executive Summary

ArcOps MCP is a **Model Context Protocol server** that bridges Azure Local / AKS Arc operations with AI-powered assistants. It showcases two key value propositions:

1. **For AKS Arc Team**: Unified diagnostics with actionable remediation guidance
2. **For Foundry Local / Edge AI Team**: A real-world MCP implementation demonstrating enterprise-grade tool orchestration

---

## 🎯 AKS Arc Team - Pre-empting Feedback

### What We Have Today ✅

| Tool | What It Does | Demo Value |
|------|-------------|------------|
| **Connectivity Check** | Tests 52 endpoints (Azure Arc, AKS Arc, Azure Local, monitoring, certificates, etc.) | High - immediate visual feedback on network readiness |
| **Cluster Validation** | Checks extensions, CNI mode, version pins, Flux status | Medium - requires actual cluster |
| **TSG Search** | Searches Azure Local troubleshooting guides by keyword | Medium - great for error messages |
| **Support.AksArc** | Wraps Test-SupportAksArcKnownIssues for common issues | High - reuses existing PS module |
| **Diagnostics Bundle** | Creates evidence packs with findings + logs + SHA256 manifest | High - support workflow ready |

### What They'll Want Next 🔮

Based on common PM/support team feedback patterns:

#### 1. **Real-Time Cluster Metrics** (Priority: High)
- Current pod health / restart counts
- Node resource utilization (CPU/memory pressure)
- PVC binding status
- *Demo potential: Show live cluster health dashboard*

#### 2. **Log Correlation** (Priority: High)
- Collect logs from Arc agents, AKS extensions, kubelet
- Correlate timestamps with failures
- *This is partially in `aksarc.logs.collect` but needs UI integration*

#### 3. **Known Issue Matching** (Priority: Medium)
- When a check fails, auto-suggest matching known issues
- Link to TSG or KB articles
- *Already have TSG search - need to wire it into failure hints*

#### 4. **Remediation Playbooks** (Priority: Medium-High)
- Beyond hints: actual step-by-step remediation scripts
- "Fix it" button for safe remediations
- *Careful: They'll ask about auto-remediation (high risk)*

#### 5. **Multi-Cluster View** (Priority: Medium)
- Compare checks across multiple AKS Arc clusters
- Fleet health dashboard
- *Currently single-cluster focused*

### Specific Demo Scenarios for AKS Arc PM/Support

```
Scenario 1: "New cluster won't connect to Azure"
→ Run connectivity check → Shows which endpoints are blocked
→ Click on failure → See TSG suggestion
→ See remediation hint (e.g., "Add proxy exception for *.azure.com")

Scenario 2: "Extension install keeps failing"  
→ Run cluster validation → Shows extension health
→ Shows version compatibility issues
→ Suggests rollback or update path

Scenario 3: "Customer needs support case evidence"
→ Run all diagnostics
→ Create bundle → Single ZIP with findings + logs
→ SHA256 manifest for tamper-evidence
```

### Pre-empting Tough Questions

| Question | Answer |
|----------|--------|
| "Does this replace Environment Checker?" | No - we wrap and normalize it. Same engine, better UX. |
| "Can it auto-remediate?" | Not yet. Design principle: diagnose, don't mutate without consent. |
| "Does it work air-gapped?" | Yes - Foundry Local is the AI, runs 100% on-prem. |
| "How does this integrate with Azure Support?" | Bundle output is support-case-ready (findings.json + sha256). |
| "What about confidentiality?" | All runs locally. No data leaves the machine unless you choose to upload. |

---

## 🚀 Edge AI / Foundry Local Team - How to WOW Them

### Current State: "Good"
- MCP server running on HTTP transport
- 7 registered tools with JSON Schema input/output
- AI chat with function calling using local model (Qwen 2.5 0.5B)
- Visual tool execution in React UI

### What Would Make It "Great" 🌟

#### 1. **Full MCP Protocol Compliance** ✨ (Priority: Critical)

Your current implementation uses FastAPI HTTP but not the official MCP transport protocol. To truly WOW them:

```diff
Current:  POST /mcp/tools/{name}  (custom HTTP)
Official: JSON-RPC 2.0 over HTTP/SSE or stdio

Current:  GET /mcp/manifest
Official: tools/list + resources/list + prompts/list
```

**Action**: Add an MCP-compliant endpoint layer alongside current REST API:
- `tools/list` → List all available tools
- `tools/call` → Invoke a tool with JSON-RPC wrapper
- `notifications/tools/list_changed` → Notify clients of tool changes

#### 2. **Multi-Tool Orchestration Demo** 🔗 (Priority: High)

Show the AI chaining multiple tools to solve a problem:

```
User: "My Arc connection is failing, help me troubleshoot"

AI Thinking:
1. Run connectivity check (find blocked endpoints)
2. Search TSG for the specific error
3. Run cluster validation (check extension health)
4. Create diagnostic bundle (for support case)

→ Returns unified summary with all findings
```

*This is what makes MCP powerful - not just one tool, but intelligent tool composition.*

#### 3. **Streaming Progress with SSE** 📡 (Priority: Medium-High)

Currently progress is polled. Official MCP uses Server-Sent Events:

```javascript
// Current: Poll for results
const response = await fetch('/api/chat', { method: 'POST', body: ... });

// WOW: Stream progress in real-time
const eventSource = new EventSource('/api/chat/stream');
eventSource.onmessage = (event) => {
  // Update UI as each tool completes
};
```

#### 4. **Resource Protocol** 📦 (Priority: Medium)

MCP supports Resources (files, docs, structured data) alongside Tools:

```json
{
  "resources": [
    { "uri": "arcops://clusters", "name": "Connected Clusters" },
    { "uri": "arcops://findings/latest", "name": "Latest Diagnostics" },
    { "uri": "arcops://tsg/index", "name": "TSG Knowledge Base" }
  ]
}
```

*This lets the AI "browse" your data, not just call tools.*

#### 5. **Prompt Templates** 📝 (Priority: Medium)

MCP supports pre-built prompts that guide the AI:

```json
{
  "prompts": [
    {
      "name": "troubleshoot_connectivity",
      "description": "Diagnose Azure connectivity issues",
      "arguments": [{ "name": "symptoms", "required": true }]
    }
  ]
}
```

*Reduces model complexity - Foundry Local team will love this for smaller models.*

### Demo Script for Foundry Local PM

```
1. Show: "Here's a real-world MCP server for IT ops"
   → Open http://localhost:5174
   → Show tool registry with 7 tools

2. Ask: "Check my connectivity to Azure"
   → AI automatically calls run_connectivity_check
   → Shows 52 URL checks with pass/warn/fail
   → Animation shows "MCP Server executing tools..."

3. Ask: "I'm getting error X, what should I do?"
   → AI calls tsg_search with the error
   → Returns relevant troubleshooting guides

4. Ask: "Create a support bundle for Microsoft"
   → AI calls diagnostics_bundle
   → Creates ZIP with SHA256 manifest

5. Highlight: "All of this runs 100% locally"
   → Foundry Local = on-device AI
   → MCP server = local tool bridge
   → No cloud dependency for core function
```

### The "WOW" Pitch for Foundry Local Team

> "We've built a production-ready MCP implementation that:
> 
> 1. **Proves function calling works** with Foundry Local models
> 2. **Demonstrates real enterprise value** (not a toy demo)
> 3. **Shows multi-tool orchestration** in a single conversation
> 4. **Runs 100% air-gapped** for edge/defense scenarios
> 5. **Can be template** for other IT operations tools
>
> We'd love your help to:
> - Improve small model function calling accuracy
> - Add streaming support (SSE transport)
> - Explore larger models for complex reasoning"

---

## 🏗️ Architecture Assessment

### Question 1: Is This Microsoft Engineering Standard?

#### ✅ What's Good

| Aspect | Assessment |
|--------|------------|
| **FastAPI + Pydantic** | Industry standard for Python APIs |
| **JSON Schema for inputs** | Matches MCP spec exactly |
| **Async tool execution** | Correct for I/O-bound operations |
| **Structured findings output** | Well-designed, reusable schema |
| **Tool registry pattern** | Clean, extensible design |

#### ⚠️ Gaps to Address

| Gap | Impact | Fix Effort |
|-----|--------|------------|
| Not using official `mcp` Python SDK | Low - HTTP works fine | Medium |
| No JSON-RPC 2.0 wrapper | Clients expect it | Low |
| No SSE streaming for progress | UX degraded | Medium |
| No capability negotiation | Not protocol-compliant | Low |

#### Recommendation

Your implementation is **pragmatically correct** but not **spec-compliant**. For a demo, this is fine. For shipping as a reference implementation, add:

```python
# Add MCP SDK support
from mcp import Server
from mcp.server.fastmcp import FastMCP

mcp_server = FastMCP("arcops")

@mcp_server.tool()
def connectivity_check(...):
    ...
```

### Question 2: Is Tool Registration Consistent?

#### Current Pattern ✅

```python
# server/main.py
TOOL_REGISTRY: dict[str, Any] = {
    "arc.connectivity.check": ArcConnectivityCheckTool(),
    "aks.arc.validate": AksArcValidateTool(),
    "aksarc.support.diagnose": AksArcSupportTool(),
    # ... etc
}
```

**Pros:**
- All tools inherit from `BaseTool`
- Consistent `execute()` method signature
- Uniform input/output schema pattern
- Easy to add new tools

**Adding a New Tool:**
```python
# 1. Create server/tools/my_new_tool.py
class MyNewTool(BaseTool):
    name = "my.new.tool"
    description = "Does something useful"
    input_schema = { ... }
    
    async def execute(self, arguments, progress_callback=None):
        # Do work
        return findings

# 2. Register in server/main.py
from server.tools.my_new_tool import MyNewTool
TOOL_REGISTRY["my.new.tool"] = MyNewTool()

# 3. Add to mcp_manifest.json (for discovery)
```

#### Improvement Opportunities

1. **Auto-discovery**: Scan `server/tools/` directory automatically
2. **Plugin system**: Load tools from external packages
3. **Hot-reload**: Add/remove tools without restart

```python
# Future: Auto-discovery pattern
import importlib
import pkgutil
import server.tools

for _, module_name, _ in pkgutil.iter_modules(server.tools.__path__):
    module = importlib.import_module(f"server.tools.{module_name}")
    for cls in module.__dict__.values():
        if isinstance(cls, type) and issubclass(cls, BaseTool) and cls != BaseTool:
            tool = cls()
            TOOL_REGISTRY[tool.name] = tool
```

---

## 📋 Pre-Demo Checklist

### For AKS Arc Team Demo
- [ ] Connectivity check shows 52 endpoints with clear pass/warn/fail
- [ ] At least one warning (simulated or real) to show remediation hints
- [ ] TSG search returns relevant results for common error messages
- [ ] Bundle creation produces valid ZIP with SHA256 manifest
- [ ] UI shows tool execution animation clearly

### For Foundry Local Team Demo
- [ ] Model downloads and loads successfully
- [ ] Chat understands function calling (uses tools, not just text)
- [ ] Multi-turn conversation maintains context
- [ ] Tool results are summarized in human-readable format
- [ ] Show dry-run mode works (no cluster needed)

### For Both
- [ ] Server starts cleanly (`python -m cli server`)
- [ ] UI builds and runs (`npm run dev` in ui/)
- [ ] No visible errors in console
- [ ] Model selection dropdown works
- [ ] Prepare 2-3 scripted questions that showcase capabilities

---

## 🎬 30-Second Elevator Pitch

> "ArcOps Assistant is an **AI-powered troubleshooting bridge** for Azure Local and AKS Arc.
> 
> It uses **Foundry Local** (on-device AI) with **MCP** (Model Context Protocol) to let you ask natural language questions like 'check my connectivity' or 'why is my cluster failing' and get actionable diagnostics.
> 
> **For AKS Arc**: Unified diagnostics that wrap existing tools into a single, support-case-ready experience.
> 
> **For Edge AI**: A production-quality MCP implementation proving local AI can orchestrate real enterprise tools.
> 
> All of it runs **100% locally** - no cloud required for core function."
