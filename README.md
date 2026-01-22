# ArcOps MCP

[![MCP](https://img.shields.io/badge/MCP-2025--06--18-blue)](https://modelcontextprotocol.io)
[![Foundry Local](https://img.shields.io/badge/Foundry%20Local-compatible-green)](https://github.com/microsoft/foundry-local)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **AI-powered diagnostic assistant for Azure Local and AKS Arc** — powered by Model Context Protocol (MCP) and Foundry Local.

ArcOps MCP provides a conversational interface for troubleshooting Azure Local and AKS Arc deployments. Ask questions in natural language and get diagnostic insights from official Microsoft tools.

## ✨ Features

- **🤖 AI Chat Interface** — Natural language troubleshooting powered by Foundry Local SLMs
- **🔧 MCP Tool Integration** — Standardized tool protocol for AI agents
- **📊 Real Diagnostics** — Wraps official Microsoft tools (no fake data)
- **🔍 TSG Search** — Search Azure Local troubleshooting guides via [AzLocalTSGTool](https://github.com/smitzlroy/azlocaltsgtool)
- **📦 Offline Capable** — Local AI models run entirely on your machine

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ArcOps Assistant                         │
│                     (React Chat Interface)                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP/SSE
┌─────────────────────────▼───────────────────────────────────────┐
│                     ArcOps MCP Server                           │
│                      (FastAPI + MCP)                            │
├─────────────────────────────────────────────────────────────────┤
│  🔧 MCP Tools                    │  🤖 AI Integration           │
│  ├── arc.connectivity.check      │  └── Foundry Local SDK       │
│  ├── aks.arc.validate            │      └── Qwen 2.5 / Phi-4    │
│  ├── azlocal.tsg.search          │                              │
│  └── arcops.diagnostics.bundle   │                              │
└─────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                    Microsoft Tools                              │
│  ├── AzStackHci.EnvironmentChecker (PowerShell)                │
│  ├── AzLocalTSGTool (PowerShell)                                │
│  ├── Azure CLI (az connectedk8s, az k8s-extension)             │
│  └── kubectl                                                    │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Windows 10/11 or Windows Server 2019+
- Python 3.11+
- [Foundry Local](https://github.com/microsoft/foundry-local) (for AI chat)
- Node.js 18+ (for UI development)

### Installation

```powershell
# Clone the repository
git clone https://github.com/smitzlroy/arcops-mcp
cd arcops-mcp

# Create virtual environment and install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Install optional PowerShell modules for real diagnostics
Install-Module -Name AzStackHci.EnvironmentChecker -Force
Install-Module -Name AzLocalTSGTool -Force
```

### Start the Server

```powershell
# Start MCP server
python -m cli server --port 8080

# In a new terminal, start Foundry Local with a model
foundry model run qwen2.5-1.5b

# In a new terminal, start the UI
cd ui
npm install
npm run dev
```

Open **http://localhost:5173** and start chatting!

## 💬 Usage Examples

### Chat with the Assistant

Try asking:
- "Check connectivity to Azure"
- "Validate my AKS Arc cluster"
- "I'm getting error 0x80004005"
- "Search for cluster validation issues"

### CLI Commands

```powershell
# Run connectivity check
python -m cli envcheck --out ./results

# Validate cluster
python -m cli validate --cluster my-cluster --resource-group my-rg

# Create diagnostic bundle
python -m cli bundle --in ./results --out ./artifacts
```

### Direct API Access

```bash
# Check server health
curl http://localhost:8080/health

# Run connectivity check
curl http://localhost:8080/api/connectivity/check?mode=quick

# List available MCP tools
curl -X POST http://localhost:8080/mcp/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## 🔧 MCP Tools

All diagnostic tools are exposed via the [Model Context Protocol](https://modelcontextprotocol.io):

| Tool | Description | Backend |
|------|-------------|---------|
| `arc.connectivity.check` | Azure endpoint connectivity validation | `AzStackHci.EnvironmentChecker` |
| `aks.arc.validate` | AKS Arc cluster health checks | `az connectedk8s` + `kubectl` |
| `azlocal.tsg.search` | Search troubleshooting guides | `AzLocalTSGTool` |
| `aksarc.support.diagnose` | Known issue detection | `Support.AksArc` |
| `arcops.diagnostics.bundle` | Create support bundles | Local packaging |

### MCP Integration

```python
# Example: Using MCP tools programmatically
from server.main import TOOL_REGISTRY

# Get a tool
tsg_tool = TOOL_REGISTRY["azlocal.tsg.search"]

# Execute it
result = await tsg_tool.execute({
    "query": "cluster validation failed",
    "dryRun": False
})
```

## 🤖 AI Models

ArcOps uses [Foundry Local](https://github.com/microsoft/foundry-local) to run AI models locally:

| Model | Size | Recommended | Tool Calling |
|-------|------|-------------|--------------|
| `qwen2.5-1.5b` | 1.25 GB | ✅ Best for tools | ✅ |
| `qwen2.5-7b` | 5.5 GB | ✅ Excellent | ✅ |
| `phi-4-mini` | 3.6 GB | ✅ Good balance | ✅ |
| `qwen2.5-0.5b` | 520 MB | ⚠️ Limited | ✅ (with assist) |

**Recommended:** Use `qwen2.5-1.5b` or larger for reliable tool selection.

## 📁 Project Structure

```
arcops-mcp/
├── cli/                    # Command-line interface
│   ├── __main__.py         # CLI entry point
├── server/
│   ├── main.py             # FastAPI + MCP server
│   ├── api_routes.py       # REST + Chat endpoints
│   └── tools/              # MCP tool implementations
│       ├── arc_connectivity_check.py
│       ├── aks_arc_validate.py
│       ├── azlocal_tsg_tool.py
│       └── diagnostics_bundle.py
├── ui/                     # React/Vite web interface
│   └── src/components/
│       ├── ChatPanel.tsx   # Main chat interface
│       └── LiveToolVisualization.tsx
├── schemas/                # JSON schemas
└── tests/                  # Test suite
```

## 🔒 Privacy & Security

- **All AI runs locally** — No data sent to external APIs
- **Foundry Local** uses on-device SLMs
- **No telemetry** — Your data stays on your machine
- **Dry-run mode** for safe testing without real operations

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design
- [Tool Registry](docs/TOOL_REGISTRY.md) — All MCP tools
- [Privacy & Security](docs/PRIVACY_SECURITY.md) — Data handling
- [Sources](docs/SOURCES.md) — Microsoft documentation links

## 🧪 Development

```powershell
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --cov=server --cov=cli

# Format code
black server/ cli/ tests/
isort server/ cli/ tests/

# Type check
mypy server/ cli/

# Build UI
cd ui && npm run build
```

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines and submit PRs.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

**Built with** ❤️ **for Azure Local and AKS Arc operators**

*Powered by [Model Context Protocol](https://modelcontextprotocol.io) and [Foundry Local](https://github.com/microsoft/foundry-local)*
