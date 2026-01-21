# ArcOps MCP

A Model Context Protocol (MCP) server that wraps official Microsoft diagnostic tools for Azure Local and AKS Arc. Provides a unified interface for pre-deployment validation, connectivity testing, and cluster health checks.

## Overview

ArcOps MCP does not reinvent diagnostic tooling. Instead, it wraps existing Microsoft tools—primarily the [Azure Stack HCI Environment Checker](https://learn.microsoft.com/azure-stack/hci/manage/use-environment-checker) and Azure CLI—and exposes them through a standardized API with consistent JSON output.

**What it wraps:**
- `Invoke-AzStackHciConnectivityValidation` - Official Microsoft connectivity validation
- `az connectedk8s` / `az k8s-extension` - Azure CLI for AKS Arc cluster management
- `kubectl` - Kubernetes cluster inspection

**What it provides:**
- MCP-compatible tool interface for AI agents
- REST API for automation and integration
- Web UI for interactive diagnostics
- CLI for scripted checks
- Normalized findings schema across all tools

## Requirements

- Windows 10/11 or Windows Server 2019+
- Python 3.11+
- PowerShell 5.1+ (for Environment Checker)
- Azure CLI (for cluster operations)
- Node.js 18+ (for UI development)

## Installation

```powershell
git clone https://github.com/smitzlroy/arcops-mcp
cd arcops-mcp
pip install -e ".[dev]"
```

For the Microsoft Environment Checker (optional but recommended):
```powershell
Install-Module -Name AzStackHci.EnvironmentChecker -Force
```

## Quick Start

### Start the Server

```powershell
python -m cli server --port 8080
```

The server exposes:
- MCP endpoints at `/mcp/tools/*`
- REST API at `/api/*`
- Health check at `/health`

### Run the Web UI

```powershell
cd ui
npm install
npm run dev
```

Open http://localhost:5173 to access the diagnostic dashboard.

### CLI Usage

```powershell
# Run connectivity check (uses Microsoft Environment Checker)
python -m cli envcheck --out ./results

# Validate an AKS Arc cluster
python -m cli validate --cluster my-cluster --resource-group my-rg

# Create a diagnostic bundle for support
python -m cli bundle --in ./results --out ./artifacts
```

## API Reference

### Connectivity Check

```bash
GET /api/connectivity/check?mode=quick
```

Runs the Microsoft Environment Checker and returns results in normalized format.

**Parameters:**
- `mode`: `quick` (key endpoints) or `full` (all checks)
- `install_checker`: `true` to auto-install Environment Checker if missing

**Response:**
```json
{
  "success": true,
  "findings": {
    "version": "1.0.0",
    "target": "connectivity",
    "timestamp": "2026-01-21T22:00:00Z",
    "checks": [...],
    "summary": {
      "total": 94,
      "pass": 92,
      "fail": 2,
      "warn": 0
    }
  }
}
```

### Cluster Validation

```bash
GET /api/cluster/{name}/validate?resource_group={rg}
```

Validates an AKS Arc cluster's health, extensions, and connectivity status.

### List Clusters

```bash
GET /api/clusters
```

Returns all AKS Arc connected clusters in the current subscription.

## MCP Integration

The server implements the Model Context Protocol for AI agent integration:

```bash
# List available tools
GET /mcp/tools

# Invoke a tool
POST /mcp/tools/arc.connectivity.check
Content-Type: application/json

{"mode": "quick"}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `arc.connectivity.check` | Run connectivity validation using Microsoft Environment Checker |
| `aks.arc.validate` | Validate AKS Arc cluster configuration and health |
| `arcops.diagnostics.bundle` | Create diagnostic bundle for support |

## Findings Schema

All tools output a normalized JSON format defined in `schemas/findings.schema.json`:

```json
{
  "version": "1.0.0",
  "target": "connectivity",
  "timestamp": "2026-01-21T22:00:00Z",
  "runId": "20260121-220000-abc123",
  "checks": [
    {
      "id": "arc.connectivity.envchecker.azure_arc_services",
      "title": "Azure Arc Services",
      "status": "pass",
      "severity": "high",
      "evidence": {...}
    }
  ],
  "summary": {
    "total": 94,
    "pass": 92,
    "fail": 2,
    "warn": 0,
    "skipped": 0
  }
}
```

## Project Structure

```
arcops-mcp/
├── cli/                 # Command-line interface
├── server/
│   ├── main.py          # FastAPI application
│   ├── api_routes.py    # REST API endpoints
│   ├── tools/           # MCP tool implementations
│   └── config/          # Endpoint configurations
├── ui/                  # React/Vite web interface
├── schemas/             # JSON schemas
├── tests/               # Test suite
└── docs/                # Documentation
```

## Development

```powershell
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Format code
black server/ cli/ tests/
isort server/ cli/ tests/

# Type check
mypy server/ cli/
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and component overview
- [Sources](docs/SOURCES.md) - External references and Microsoft documentation links
- [Privacy & Security](docs/PRIVACY_SECURITY.md) - Data handling and security considerations

## License

MIT
