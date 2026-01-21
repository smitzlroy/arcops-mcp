# ArcOps MCP Bridge

> MCP-powered operations bridge for Azure Local + AKS Arc

[![CI](https://github.com/smitzlroy/arcops-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/smitzlroy/arcops-mcp/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

ArcOps MCP is a sovereign-safe, contracts-first operations bridge that exposes deterministic, auditable tools for Azure Local and AKS enabled by Azure Arc. It wraps and normalizes outputs from existing checkers (Azure Local Environment Checker, Supportability TSG scripts) into a versioned Findings JSON contract.

### Key Features

- **MCP Server**: HTTP-based MCP transport exposing tools via REST API
- **4 Core Tools**:
  - `azlocal.envcheck.wrap` - Wrap Azure Local Environment Checker
  - `arc.gateway.egress.check` - TLS/Proxy/FQDN reachability checks
  - `aks.arc.validate` - Cluster invariant validation
  - `arcops.diagnostics.bundle` - Evidence pack creation
- **Contracts First**: All outputs conform to `schemas/findings.schema.json`
- **Sovereign Safe**: No background egress; offline by default
- **CLI & UI**: Full CLI for automation + React-based report viewer

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (for UI)

### Installation

```bash
# Clone the repository
git clone https://github.com/smitzlroy/arcops-mcp
cd arcops-mcp

# Install Python dependencies
pip install -e ".[dev]"

# Install UI dependencies
cd ui && npm ci && cd ..
```

### Run CLI (Offline/Dry-Run)

```bash
# Environment check
python -m cli envcheck --mode full --dry-run --out ./artifacts

# Egress connectivity check
python -m cli egress --cfg server/config/endpoints.yaml --dry-run --out ./artifacts

# AKS Arc validation
python -m cli validate --dry-run --out ./artifacts

# Create diagnostics bundle
python -m cli bundle --in ./artifacts --out ./artifacts
```

### Start MCP Server

```bash
# Start the server
python -m cli server --port 8080

# Or directly with uvicorn
uvicorn server.main:app --reload --port 8080
```

### Start UI

```bash
cd ui
npm run dev
# Open http://localhost:5173
```

## Project Structure

```
arcops-mcp/
├── server/                 # FastAPI MCP server
│   ├── main.py            # MCP dispatcher + tool registry
│   ├── mcp_manifest.json  # MCP manifest
│   ├── tools/             # Tool implementations
│   └── config/            # Configuration files
├── cli/                   # Typer CLI
├── schemas/               # JSON schemas
│   └── findings.schema.json
├── ui/                    # React + Vite + Tailwind UI
├── tests/                 # Pytest tests
│   └── fixtures/          # Test fixtures
├── docs/                  # Documentation
└── .github/workflows/     # CI/CD
```

## API Reference

### MCP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server info |
| `/health` | GET | Health check |
| `/mcp/manifest` | GET | MCP manifest with tools |
| `/mcp/tools` | GET | List available tools |
| `/mcp/tools/{name}` | POST | Invoke a tool |
| `/mcp/tools/{name}/schema` | GET | Get tool schema |

### Tool Invocation Example

```bash
curl -X POST http://localhost:8080/mcp/tools/azlocal.envcheck.wrap \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"mode": "quick", "dryRun": true}}'
```

## Configuration

### Endpoint Configuration

Edit `server/config/endpoints.yaml` to customize endpoints for your environment:

```yaml
endpoints:
  - fqdn: management.azure.com
    port: 443
    tls: true
    required: true
    category: azure-arc
    description: Azure Resource Manager
```

### Proxy Configuration

Set environment variables:

```bash
export HTTP_PROXY=http://proxy.contoso.com:8080
export HTTPS_PROXY=http://proxy.contoso.com:8080
export NO_PROXY=localhost,127.0.0.1,.contoso.com
```

## Development

### Setup Development Environment

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v

# Run linting
black server/ cli/ tests/
isort server/ cli/ tests/
mypy server/ cli/
pylint server/ cli/
```

### Adding a New Rule

1. Add the check logic in the appropriate tool under `server/tools/`
2. Add a source reference to `docs/SOURCES.md`
3. Add a fixture under `tests/fixtures/`
4. Add a unit test
5. Ensure schema compliance

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=server --cov=cli --cov-report=html

# Specific test file
pytest tests/test_findings_schema.py -v
```

## Documentation

- [SOP.md](docs/SOP.md) - Standard Operating Procedures
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Architecture & Design
- [PRIVACY_SECURITY.md](docs/PRIVACY_SECURITY.md) - Security Guidelines
- [SOURCES.md](docs/SOURCES.md) - External References

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit changes (conventional commits: `feat:`, `fix:`, `docs:`)
4. Push and open a PR

All contributions must:
- Pass CI (lint, type check, tests)
- Include tests for new functionality
- Reference sources in `docs/SOURCES.md`
