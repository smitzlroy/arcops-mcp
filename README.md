# ArcOps MCP

[![MCP](https://img.shields.io/badge/MCP-2025--06--18-blue)](https://modelcontextprotocol.io)
[![Foundry Local](https://img.shields.io/badge/Foundry%20Local-compatible-green)](https://github.com/microsoft/foundry-local)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **AI-powered diagnostic assistant for Azure Local and AKS Arc** — powered by Model Context Protocol (MCP) and local AI models.

ArcOps MCP provides a conversational interface for troubleshooting Azure Local and AKS Arc deployments. Ask questions in natural language and get diagnostic insights from official Microsoft tools.

## 🏗️ Architecture

![ArcOps MCP Architecture](diagrams/architecture.svg)

**[View Interactive Diagram →](diagrams/arcops-architecture-horizontal.html)** *(open locally for animations)*

## ✨ Features

- **🤖 AI Chat Interface** — Natural language troubleshooting powered by local SLMs
- **🔧 MCP Tool Integration** — Standardized Model Context Protocol for AI agents
- **📊 Real Diagnostics** — Wraps official Microsoft tools (no fake data)
- **🔍 TSG Search** — Search 149 Azure Local troubleshooting guides via [AzLocalTSGTool](https://github.com/smitzlroy/azlocaltsgtool)
- **📦 Offline Capable** — All AI models run entirely on your machine

## 🚀 Quick Start

### Prerequisites

- Windows 10/11 or Windows Server 2019+
- Python 3.11+
- [Foundry Local](https://github.com/microsoft/foundry-local) (for AI chat)
- Node.js 18+ (for UI)

### Installation

```powershell
# Clone the repository
git clone https://github.com/smitzlroy/arcops-mcp
cd arcops-mcp

# Create virtual environment and install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Install PowerShell modules for diagnostics
Install-Module -Name AzStackHci.EnvironmentChecker -Force
Install-Module -Name AzLocalTSGTool -Force
Install-Module -Name Support.AksArc -Force
```

### Start the Server

```powershell
# Start MCP server
python -m cli server --port 8080

# Start Foundry Local with a model
foundry model run qwen2.5-0.5b

# Start the UI
cd ui && npm install && npm run dev
```

Open **http://localhost:5173** and start chatting!

## 💬 Usage Examples

Try asking:
- *"Check connectivity to Azure"*
- *"Validate my AKS Arc cluster"*
- *"I'm getting error 0x80004005"*
- *"Search for cluster validation issues"*

## 🔧 MCP Tools

| Tool | Description | Backend |
|------|-------------|---------|
| `arc.connectivity.check` | Azure endpoint connectivity (52+ endpoints) | `AzStackHci.EnvironmentChecker` |
| `arc.gateway.egress.check` | Arc Gateway TLS/Proxy validation | `AzStackHci.EnvironmentChecker` |
| `azlocal.envcheck` | Full environment validation | `AzStackHci.EnvironmentChecker` |
| `azlocal.tsg.search` | Search 149 troubleshooting guides | `AzLocalTSGTool` |
| `aks.arc.validate` | AKS Arc cluster health checks | `az connectedk8s` + `kubectl` |
| `aksarc.support.diagnose` | Known issue detection | `Support.AksArc` |
| `aksarc.logs.collect` | Log collection for support | `Support.AksArc` |
| `arcops.diagnostics.bundle` | Create support bundles | Local packaging |
| `azlocal.educational` | Azure Local concepts & learning | Built-in |

## 🤖 Supported Models

ArcOps works with any OpenAI-compatible API. Recommended local models via [Foundry Local](https://github.com/microsoft/foundry-local):

| Model | Size | Tool Calling |
|-------|------|--------------|
| `qwen2.5-0.5b` | 520 MB | ✅ Excellent |
| `qwen2.5-1.5b` | 1.25 GB | ✅ Excellent |
| `phi-4-mini` | 3.6 GB | ✅ Good |

## 🔒 Privacy & Security

- **All AI runs locally** — No data sent to external APIs
- **No telemetry** — Your data stays on your machine
- **Dry-run mode** — Safe testing without real operations

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design details
- [Tool Registry](docs/TOOL_REGISTRY.md) — All MCP tools
- [Privacy & Security](docs/PRIVACY_SECURITY.md) — Data handling

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

**Built with** ❤️ **for Azure Local and AKS Arc operators**

*Powered by [Model Context Protocol](https://modelcontextprotocol.io) and [Foundry Local](https://github.com/microsoft/foundry-local)*
