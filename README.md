# ArcOps MCP

An operations bridge for Azure Local and AKS Arc that wraps existing diagnostic tools and exposes them through the Model Context Protocol (MCP).

[![CI](https://github.com/smitzlroy/arcops-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/smitzlroy/arcops-mcp/actions/workflows/ci.yml)

## What is this?

This project takes the various diagnostic and validation tools used with Azure Local and AKS Arc (Environment Checker, TSG scripts, connectivity tests) and wraps them in a consistent HTTP API. Everything outputs normalized JSON that follows a single schema, making it easier to automate, integrate, and build tooling around.

The server runs locally and doesn't phone home. Designed for air-gapped and sovereign environments.

## Quick start (Chat UI)

The easiest way to use this is through the chat interface powered by [Foundry Local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/):

```bash
# Install Foundry Local (one-time)
winget install Microsoft.FoundryLocal

# Install dependencies
pip install -e .

# Start chatting
chat.bat
```

Then just ask questions like:
- "Is my environment ready for Azure Local?"
- "Check connectivity to Azure"
- "Validate my cluster"

## Tools

| Tool | What it does |
|------|--------------|
| `azlocal.envcheck.wrap` | Runs Azure Local Environment Checker and normalizes the output |
| `arc.gateway.egress.check` | Tests connectivity to required Azure endpoints (handles proxies, TLS) |
| `aks.arc.validate` | Validates AKS Arc cluster config (extensions, CNI, versions) |
| `arcops.diagnostics.bundle` | Packages findings into a ZIP with checksums |

## Getting started

**Requirements:** Python 3.11+, Node 20+ (optional, for the UI)

```bash
git clone https://github.com/smitzlroy/arcops-mcp
cd arcops-mcp
pip install -e ".[dev]"
```

## Usage

### CLI

```bash
# Run environment checks (dry-run mode for testing)
python -m cli envcheck --dry-run --out ./results

# Test egress connectivity
python -m cli egress --dry-run --out ./results

# Validate AKS Arc cluster
python -m cli validate --dry-run --out ./results

# Bundle everything into a ZIP
python -m cli bundle --in ./results --out ./results
```

### HTTP Server

```bash
python -m cli server --port 8080
```

Then call tools via HTTP:

```bash
curl -X POST http://localhost:8080/mcp/tools/azlocal.envcheck.wrap \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"mode": "quick", "dryRun": true}}'
```

### Web UI

There's a simple React app for viewing results:

```bash
cd ui && npm ci && npm run dev
```

Open http://localhost:5173 and drag-drop a findings JSON file.

## Configuration

Endpoints are defined in `server/config/endpoints.yaml`. Add or remove entries as needed for your environment.

For proxied environments:

```bash
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1,.internal.local
```

## Project layout

```
server/          FastAPI app and tool implementations
cli/             Command-line interface
schemas/         JSON schema for findings output
ui/              React viewer for results
tests/           Test suite
docs/            Additional documentation
```

## Development

```bash
pip install -e ".[dev]"
pre-commit install
pytest tests/ -v
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design details and [docs/SOURCES.md](docs/SOURCES.md) for external references.

## License

MIT
