# ArcOps MCP Architecture

> Technical architecture for the Edge AI Readiness & Trust Platform

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONSUMERS                                       │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────┤
│  Foundry Local  │   VS Code /     │      CLI        │    CI/CD Pipeline    │
│     Agents      │    Copilot      │   (arcops)      │     (GitOps)         │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬───────────┘
         │                 │                 │                   │
         └─────────────────┴────────┬────────┴───────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MCP SERVER (FastAPI)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Tool Router                                  │   │
│  │   /mcp/tools/list    /mcp/tools/call    /api/tools/{name}/run       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐  │
│  │                           TOOL REGISTRY                              │  │
│  ├──────────────────┬─────────────┴───────────┬─────────────────────────┤  │
│  │                  │                         │                         │  │
│  │  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────┐ │  │
│  │  │  READINESS PACKS     │  │  EXISTING TOOLS      │  │  SHARED    │ │  │
│  │  │  (new)               │  │  (preserved)         │  │  SERVICES  │ │  │
│  │  ├──────────────────────┤  ├──────────────────────┤  ├────────────┤ │  │
│  │  │ • supply_chain.gate  │  │ • arc.connectivity   │  │ • Artifact │ │  │
│  │  │ • network.safety     │  │ • arc.gateway.egress │  │   Signer   │ │  │
│  │  │ • network.render     │  │ • azlocal.envcheck   │  │ • Policy   │ │  │
│  │  │ • gpu.check          │  │ • azlocal.tsg.search │  │   Engine   │ │  │
│  │  │ • foundry.validate   │  │ • aks.arc.validate   │  │ • Cache    │ │  │
│  │  │                      │  │ • aksarc.support     │  │   Manager  │ │  │
│  │  │                      │  │ • aksarc.logs        │  │            │ │  │
│  │  │                      │  │ • diagnostics.bundle │  │            │ │  │
│  │  │                      │  │ • azlocal.learn      │  │            │ │  │
│  │  └──────────────────────┘  └──────────────────────┘  └────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ARTIFACTS                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ approval.json   │  │ safety-report   │  │ gpu-readiness.json          │  │
│  │ (supply-chain)  │  │ .json           │  │ inference-validation.json   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ OCI Registry    │  │ Kubernetes      │  │ Foundry Local               │  │
│  │ (BYO models)    │  │ (AKS Arc)       │  │ (AI inference)              │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. MCP Server

The core FastAPI server exposes tools via MCP-compliant endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /mcp/tools/list` | List all available tools with schemas |
| `POST /mcp/tools/call` | Execute a tool by name |
| `GET /api/tools` | REST API tool listing |
| `POST /api/tools/{name}/run` | REST API tool execution |
| `GET /health` | Health check |

**Key Design Decisions:**
- All tools return structured JSON artifacts
- Tools are stateless and idempotent
- Errors return structured error responses, not exceptions

### 2. Tool Registry

Tools are organized into two categories:

#### Readiness Packs (New)

| Tool | MCP Name | Input | Output |
|------|----------|-------|--------|
| Supply-Chain Gate | `supply_chain.gate` | image, pubKey, policy | ApprovalArtifact |
| Network Safety Check | `network.safety` | policy | SafetyReport |
| Network Render | `network.render` | policy, outputDir | ManifestPaths |
| GPU Check | `gpu.check` | nodeSelector? | GpuReadiness |
| Foundry Validate | `foundry.validate` | catalogModel, byoImage, thresholds | InferenceValidation |

#### Existing Tools (Preserved)

| Tool | MCP Name | Purpose |
|------|----------|---------|
| Connectivity Check | `arc.connectivity.check` | Azure endpoint connectivity |
| Gateway Egress | `arc.gateway.egress.check` | Arc Gateway TLS/Proxy |
| Environment Check | `azlocal.envcheck` | Full environment validation |
| TSG Search | `azlocal.tsg.search` | Troubleshooting guide search |
| AKS Arc Validate | `aks.arc.validate` | Cluster health checks |
| Support Diagnose | `aksarc.support.diagnose` | Known issue detection |
| Log Collection | `aksarc.logs.collect` | Support log collection |
| Diagnostics Bundle | `arcops.diagnostics.bundle` | Create support bundles |
| Educational | `azlocal.educational` | Learning resources |

### 3. Shared Services

#### Artifact Signer
Signs output artifacts with SHA-256 hash for integrity verification:
```python
{
    "artifactHash": "sha256:abc123...",
    "signedAt": "2026-01-23T12:00:00Z",
    "signer": "arcops-mcp"
}
```

#### Policy Engine
Evaluates policies from YAML files against check results:
```yaml
# policies/supply-chain.yaml
rules:
  - name: require-signature
    condition: signatureValidated == true
    verdict: GREEN
    else: RED
  - name: no-critical-cves
    condition: sbom.vulnerabilities.critical == 0
    verdict: GREEN
    else: AMBER
```

#### Cache Manager
Manages offline caches for:
- Vulnerability database (CVE data)
- SBOM components
- Policy bundles

### 4. Artifact Schemas

All artifacts follow a consistent structure:

```json
{
    "version": "1.0.0",
    "type": "approval|safety-report|gpu-readiness|inference-validation",
    "timestamp": "ISO-8601",
    "runId": "unique-id",
    "metadata": {
        "toolName": "string",
        "toolVersion": "string",
        "hostname": "string"
    },
    "result": { /* type-specific payload */ },
    "verdict": "GREEN|AMBER|RED|PASS|FAIL",
    "artifactHash": "sha256:..."
}
```

## Data Flow

### Pack A: Supply-Chain Gate

```
User/Agent                 MCP Server              External
    │                          │                      │
    │  supply_chain.gate       │                      │
    │  (image, pubKey, policy) │                      │
    │─────────────────────────>│                      │
    │                          │  Pull image manifest │
    │                          │─────────────────────>│ OCI Registry
    │                          │<─────────────────────│
    │                          │                      │
    │                          │  Verify signature    │
    │                          │  (cosign/notary)     │
    │                          │                      │
    │                          │  Parse/generate SBOM │
    │                          │  Scan vulnerabilities│
    │                          │  (offline cache)     │
    │                          │                      │
    │                          │  Evaluate policy     │
    │                          │                      │
    │    ApprovalArtifact      │                      │
    │<─────────────────────────│                      │
    │    (GREEN/AMBER/RED)     │                      │
```

### Pack B: Network Safety

```
User/Agent                 MCP Server              Kubernetes
    │                          │                      │
    │  network.safety          │                      │
    │  (policy.yaml)           │                      │
    │─────────────────────────>│                      │
    │                          │                      │
    │                          │  Parse policy        │
    │                          │  Validate rules      │
    │                          │  Check for violations│
    │                          │                      │
    │    SafetyReport          │                      │
    │<─────────────────────────│                      │
    │                          │                      │
    │  network.render          │                      │
    │  (policy.yaml, outDir)   │                      │
    │─────────────────────────>│                      │
    │                          │                      │
    │                          │  Generate Gateway API│
    │                          │  Generate Istio      │
    │                          │  Write to outDir     │
    │                          │                      │
    │    ManifestPaths         │                      │
    │<─────────────────────────│                      │
    │                          │                      │
    │  kubectl apply -f ...    │                      │
    │────────────────────────────────────────────────>│
```

### Pack C: GPU & Foundry Validation

```
User/Agent                 MCP Server              Foundry Local
    │                          │                      │
    │  gpu.check               │                      │
    │─────────────────────────>│                      │
    │                          │  Check nvidia-smi    │
    │                          │  Check drivers       │
    │                          │  Check MIG config    │
    │    GpuReadiness          │                      │
    │<─────────────────────────│                      │
    │                          │                      │
    │  foundry.validate        │                      │
    │  (catalogModel, byoImage)│                      │
    │─────────────────────────>│                      │
    │                          │  Load catalog model  │
    │                          │─────────────────────>│
    │                          │  Load BYO model      │
    │                          │─────────────────────>│
    │                          │  Run inference       │
    │                          │  Measure metrics     │
    │                          │  Compare thresholds  │
    │    InferenceValidation   │                      │
    │<─────────────────────────│                      │
    │    (PASS/FAIL)           │                      │
```

## Directory Structure

```
arcops-mcp/
├── server/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── mcp_server.py           # MCP protocol handler
│   ├── api_routes.py           # REST API routes
│   ├── tools/
│   │   ├── __init__.py         # Tool registry
│   │   ├── base.py             # Base tool class
│   │   ├── # ... existing tools ...
│   │   └── packs/              # NEW: Readiness packs
│   │       ├── __init__.py
│   │       ├── supply_chain_gate.py
│   │       ├── network_safety.py
│   │       ├── gpu_check.py
│   │       └── foundry_validate.py
│   ├── services/               # NEW: Shared services
│   │   ├── __init__.py
│   │   ├── artifact_signer.py
│   │   ├── policy_engine.py
│   │   └── cache_manager.py
│   └── schemas/                # NEW: Pydantic models
│       ├── __init__.py
│       ├── artifacts.py
│       └── policies.py
├── cli/
│   ├── __init__.py
│   ├── __main__.py
│   └── commands/               # NEW: CLI commands
│       ├── __init__.py
│       ├── supply_chain.py
│       ├── network.py
│       ├── gpu.py
│       └── foundry.py
├── schemas/                    # JSON schemas
│   ├── findings.schema.json    # Existing
│   ├── approval.schema.json    # NEW
│   ├── safety-report.schema.json
│   ├── gpu-readiness.schema.json
│   └── inference-validation.schema.json
├── policies/                   # NEW: Policy templates
│   ├── supply-chain-default.yaml
│   ├── network-sovereign.yaml
│   └── inference-thresholds.yaml
├── tests/
│   ├── # ... existing tests ...
│   └── test_packs/             # NEW: Pack tests
│       ├── test_supply_chain.py
│       ├── test_network_safety.py
│       ├── test_gpu_check.py
│       └── test_foundry_validate.py
├── artifacts/                  # Output artifacts
├── docs/
│   ├── ARCHITECTURE.md         # This file
│   ├── VISION.md
│   ├── SPEC.md
│   └── # ... existing docs ...
└── ui/                         # Evidence viewer UI
```

## Security Considerations

### Authentication
- MCP server runs locally (127.0.0.1)
- No authentication required for local access
- Optional API key for remote access

### Secrets Handling
- Private keys never logged
- Keys read from files or K8s secrets
- Attestations stored alongside artifacts

### Artifact Integrity
- All artifacts include SHA-256 hash
- Optional signing with cosign-compatible keys
- Tamper detection at consumption time

## Connectivity Modes

| Mode | Description | Behavior |
|------|-------------|----------|
| **Air-gapped** | No internet | All checks use local caches |
| **Restricted** | Proxy only | Optional cache refresh via proxy |
| **Connected** | Full internet | Real-time enrichment available |

Configuration via environment:
```bash
ARCOPS_CONNECTIVITY_MODE=air-gapped|restricted|connected
ARCOPS_PROXY_URL=http://proxy.local:8080
ARCOPS_CACHE_DIR=/var/cache/arcops
```

## Integration Points

### Helm Integration
```yaml
# values.yaml
model:
  image: "oci://registry.local/models/yolo:1.0"
  approvalArtifact: "artifacts/approval.json"

# templates/deployment.yaml
{{- $approval := .Files.Get .Values.model.approvalArtifact | fromJson -}}
{{- if ne $approval.verdict "GREEN" -}}
{{ fail (printf "Model not approved: %s" $approval.verdict) }}
{{- end -}}
```

### GitOps Integration
```yaml
# .github/workflows/deploy.yaml
- name: Gate Model
  run: |
    arcops supply-chain gate \
      --image ${{ inputs.model_image }} \
      --pubkey keys/org.pub \
      --policy policies/supply-chain.yaml \
      --out artifacts/approval.json
    
    if [ "$(jq -r .verdict artifacts/approval.json)" != "GREEN" ]; then
      echo "Model not approved"
      exit 1
    fi
```

---

*This architecture supports the mission of making sovereign AI deployments predictable, auditable, and safe.*
