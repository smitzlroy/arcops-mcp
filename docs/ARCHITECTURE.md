# Architecture

## Overview

ArcOps MCP Bridge is designed as a modular, contracts-first system that wraps existing Microsoft tools and normalizes their outputs into a standard Findings JSON format.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ArcOps MCP Bridge                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   CLI        │    │  MCP Server  │    │     UI       │          │
│  │  (Typer)     │    │  (FastAPI)   │    │ (React/Vite) │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             │                                       │
│                    ┌────────┴────────┐                              │
│                    │  Tool Registry  │                              │
│                    └────────┬────────┘                              │
│                             │                                       │
│         ┌───────────────────┼───────────────────┐                   │
│         │                   │                   │                   │
│   ┌─────┴─────┐      ┌─────┴─────┐      ┌─────┴─────┐              │
│   │ EnvCheck  │      │  Egress   │      │   AKS     │              │
│   │   Wrap    │      │  Check    │      │ Validate  │              │
│   └─────┬─────┘      └─────┬─────┘      └─────┬─────┘              │
│         │                  │                  │                     │
│         └──────────────────┼──────────────────┘                     │
│                            │                                        │
│                   ┌────────┴────────┐                               │
│                   │    Findings     │                               │
│                   │     Schema      │                               │
│                   └─────────────────┘                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │           External Systems              │
        ├─────────────────────────────────────────┤
        │  • Azure Local Environment Checker      │
        │  • kubectl / Kubernetes API             │
        │  • Azure Arc Endpoints                  │
        │  • Corporate Proxies & CAs              │
        └─────────────────────────────────────────┘
```

## Data Flow

### 1. Tool Invocation Flow

```
User/Agent → CLI/Server → Tool Registry → Specific Tool → Findings JSON
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ External Checkers   │
                                    │ (Environment Check, │
                                    │  kubectl, etc.)     │
                                    └─────────────────────┘
```

### 2. Evidence Pack Creation Flow

```
Multiple Tool Runs → findings/*.json → Bundle Tool → bundle.zip
                                           │
                                           ├── findings.json (combined)
                                           ├── sha256sum.txt
                                           └── logs/ (optional)
```

## Component Details

### MCP Server (server/main.py)

- **Framework**: FastAPI with async support
- **Transport**: HTTP/JSON (MCP-over-HTTP)
- **Port**: 8080 (configurable)
- **Endpoints**:
  - `GET /mcp/manifest` - Tool discovery
  - `POST /mcp/tools/{name}` - Tool invocation
  - `GET /mcp/tools/{name}/schema` - Input/output schemas

### Tool Registry

Maps tool names to implementations:

| Tool Name | Implementation | Purpose |
|-----------|---------------|---------|
| `azlocal.envcheck.wrap` | `AzLocalEnvCheckWrapTool` | Wrap Environment Checker |
| `arc.gateway.egress.check` | `ArcGatewayEgressCheckTool` | Endpoint reachability |
| `aks.arc.validate` | `AksArcValidateTool` | Cluster validation |
| `arcops.diagnostics.bundle` | `DiagnosticsBundleTool` | Evidence pack creation |

### Findings Schema (schemas/findings.schema.json)

All tools output conforming JSON:

```json
{
  "version": "0.1.0",
  "target": "host|cluster|gateway|bundle",
  "timestamp": "ISO8601",
  "runId": "unique-id",
  "checks": [
    {
      "id": "tool.check.name",
      "title": "Human-readable title",
      "severity": "high|medium|low",
      "status": "pass|fail|warn|skipped",
      "evidence": {},
      "hint": "Remediation hint",
      "sources": [{"type": "doc", "label": "...", "url": "..."}]
    }
  ],
  "summary": {
    "total": 10,
    "pass": 8,
    "fail": 1,
    "warn": 1,
    "skipped": 0
  }
}
```

## Configuration

### Endpoint Configuration (server/config/endpoints.yaml)

```yaml
endpoints:
  - fqdn: management.azure.com
    port: 443
    tls: true
    required: true
    category: azure-arc
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `ENVCHECKER_PATH` | Path to Environment Checker executable |
| `KUBECONFIG` | Kubernetes config path |
| `HTTP_PROXY` | HTTP proxy URL |
| `HTTPS_PROXY` | HTTPS proxy URL |
| `NO_PROXY` | Proxy bypass list |

## Security Considerations

1. **No Secrets in Code**: All credentials via environment/config
2. **Offline First**: No egress without explicit action
3. **Audit Trail**: All runs produce evidence packs
4. **Source References**: All checks cite official docs

## Extensibility

### Adding a New Tool

1. Create tool class in `server/tools/`
2. Inherit from `BaseTool`
3. Implement `execute()` method
4. Register in `TOOL_REGISTRY` (server/main.py)
5. Add to MCP manifest
6. Write tests

### Adding a New Check

1. Add check logic to existing tool
2. Use `add_check()` helper
3. Reference `docs/SOURCES.md`
4. Add fixture and test
