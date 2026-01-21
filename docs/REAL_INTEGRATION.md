# ArcOps MCP - REAL Azure Integration

## What's Now Real

This MCP server now provides **actual Azure integration** instead of demo/mock data.

### MCP Server APIs

| Endpoint | Description | Real Data |
|----------|-------------|-----------|
| `GET /api/status` | Azure CLI authentication status | ✅ Real |
| `GET /api/clusters` | List all AKS Arc connected clusters | ✅ Real (15 clusters) |
| `GET /api/cluster/{name}/validate?resource_group={rg}` | Validate specific cluster | ✅ Real |
| `GET /api/cluster/{name}/extensions?resource_group={rg}` | List cluster extensions | ✅ Real |
| `GET /api/subscriptions` | List Azure subscriptions | ✅ Real |
| `POST /mcp/tools/{name}` | MCP tool invocation | ⚠️ Mixed (see below) |

### MCP Tools Status

| Tool | Status | Notes |
|------|--------|-------|
| `azlocal.envcheck.wrap` | ⚠️ Simulated | Uses fixtures, needs real Environment Checker |
| `arc.gateway.egress.check` | ⚠️ Simulated | Uses mock endpoints, needs real 50+ endpoints |
| `aks.arc.validate` | ✅ Real via API | Uses /api/cluster/{name}/validate |
| `arcops.diagnostics.bundle` | ⚠️ Placeholder | Stub implementation |

## Your Real Clusters

Found **15 AKS Arc clusters** in subscription "AdaptiveCloudLab":

| Cluster | Resource Group | Status | K8s | Nodes |
|---------|----------------|--------|-----|-------|
| nyc-kms | NewYorkCity | Connected | 1.31.5 | 2 |
| nyc-lgcapp | ACX-AKS-LGCAPP-VAL | Connected | 1.31.5 | 5 |
| va-hackathon | ACX-Hackathon | Connected | 1.31.5 | 2 |
| ca-mario | California | Connected | 1.32.6 | 3 |
| **Halliburton-demo** | Orlando | **Offline** | 1.32.6 | 2 |
| **akslondon** | aksdeploytool-canbremoved | Connected | 1.31.10 | 3 |
| AKSARC-GPU | DattaRajpure-AKSARC | Connected | 1.32.6 | 2 |
| mobile-mario | ACX-MobileAzL | Connected | 1.31.10 | 2 |
| mobile-vi | ACX-MobileAzL | Connected | 1.32.6 | 2 |
| ca-vi | ACX-VideoIndexer | Connected | 1.32.6 | 3 |
| portland-vi | ACX-VIdeoIndexer-SCUS | Connected | 1.32.6 | 1 |
| cluster-l3 | aio-advanced-networking-b25 | Connected | 1.33.1+k3s1 | 1 |
| cluster-l2 | aio-advanced-networking-b25 | Connected | 1.33.1+k3s1 | 1 |
| K3s-Bel | JianY-demo | Connected | 1.33.6+k3s1 | 1 |
| sydney-rag | Sydney | Connected | 1.30.4 | 9 |

## Running the Services

### 1. Start MCP Server

```bash
cd c:\AI\arcops-mcp
python -m uvicorn server.main:app --host 127.0.0.1 --port 8001
```

### 2. Start UI

```bash
cd c:\AI\arcops-mcp\ui
npm run dev
```

### 3. Access

- **UI Dashboard**: http://localhost:5173
- **API Docs**: http://127.0.0.1:8001/docs

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React UI      │────▶│  MCP Server     │────▶│  Azure CLI      │
│  localhost:5173 │     │  :8001          │     │  az commands    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Azure ARM      │
                        │  connectedk8s   │
                        │  k8s-extension  │
                        └─────────────────┘
```

## What Still Needs Work

1. **Environment Checker Integration** - Wire to actual `AzStackHCI_Environment_Checker`
2. **Egress Check Endpoints** - Add real 50+ Microsoft/Azure endpoints
3. **kubectl Integration** - Real cluster probing for in-depth validation
4. **Diagnostic Bundle** - Actually collect logs, configs, metrics

## Where Would This Run?

This runs on a **jump box / management server** that has:
- Azure CLI installed and authenticated (`az login`)
- Network access to Azure ARM APIs
- (Optionally) kubectl and kubeconfig for deeper cluster inspection
- Python 3.10+ for the MCP server

The MCP server acts as a bridge between:
- **Human operators** (via UI, Chat, CLI)
- **AI agents** (via MCP protocol)
- **Azure infrastructure** (via az CLI, kubectl, APIs)
