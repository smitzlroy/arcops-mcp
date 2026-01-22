# ArcOps MCP - Tool Registry

This document catalogs all known tools, modules, scripts, and diagnostic capabilities for Azure Local and AKS Arc that can be exposed through the MCP server.

**Purpose**: Define what operations the MCP server should support, organized by category and value to AI agents.

**Last Updated**: 2026-01-22

---

## Registry Overview

| Category | Count | Priority |
|----------|-------|----------|
| Validation & Readiness | 6 | HIGH |
| Diagnostics & Logs | 5 | HIGH |
| Troubleshooting Guides (TSG) | 14 | HIGH |
| Operations & Management | 8 | MEDIUM |
| Monitoring & Health | 4 | MEDIUM |
| Education & Docs | 2 | LOW |

---

## 1. VALIDATION & READINESS TOOLS

### 1.1 Azure Local Environment Checker
| Attribute | Value |
|-----------|-------|
| **Name** | AzStackHci.EnvironmentChecker |
| **Type** | PowerShell Module |
| **Source** | [PowerShell Gallery](https://www.powershellgallery.com/packages/AzStackHci.EnvironmentChecker) |
| **Documentation** | [MS Learn](https://learn.microsoft.com/en-us/azure/azure-local/manage/use-environment-checker) |
| **MCP Status** | ✅ IMPLEMENTED |

**Validators Included:**
- `Invoke-AzStackHciConnectivityValidation` - Network/firewall endpoint reachability
- `Invoke-AzStackHciHardwareValidation` - Hardware requirements check
- `Invoke-AzStackHciActiveDirectoryValidation` - AD preparation check
- `Invoke-AzStackHciNetworkValidation` - IP range and network infrastructure
- `Invoke-AzStackHciArcIntegrationValidation` - Arc onboarding prerequisites

**Key Parameters:**
- `-PassThru` - Returns structured objects (ideal for MCP)
- `-Service "Arc For Servers"` - Filter by service
- `-Proxy http://proxy:8080` - Proxy support
- `-PsSession $session` - Remote execution

---

### 1.2 AKS Arc Diagnostic Checker
| Attribute | Value |
|-----------|-------|
| **Name** | diagnostics-checker (on control plane VM) |
| **Type** | Script + Binary |
| **Source** | Built into AKS Arc control plane VMs |
| **Documentation** | [MS Learn](https://learn.microsoft.com/en-us/azure/aks/aksarc/aks-arc-diagnostic-checker) |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Checks Performed:**
- `cloud-agent-connectivity-test` - MOC cloud agent FQDN resolution and reachability
- `gateway-icmp-ping-test` - Gateway reachability from control plane VM
- `http-connectivity-required-url-test` - Required Azure URLs accessible

**Prerequisites:**
- SSH access to control plane VM
- Logical network name
- Requires running script on Azure Local node

---

### 1.3 AKS Arc Support Tool
| Attribute | Value |
|-----------|-------|
| **Name** | Support.AksArc |
| **Type** | PowerShell Module |
| **Source** | [PowerShell Gallery](https://www.powershellgallery.com/packages/Support.AksArc) |
| **Documentation** | [MS Learn](https://learn.microsoft.com/en-us/azure/aks/aksarc/support-module) |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Key Cmdlets:**
- `Test-SupportAksArcKnownIssues` - Diagnostic health checks for common issues
- `Invoke-SupportAksArcRemediation` - Auto-fix known issues
- `Invoke-SupportAksArcRemediation_EnableWindowsNodepool` - Enable Windows node pools
- `Invoke-SupportAksArcRemediation_DisableWindowsNodepool` - Disable Windows node pools

**Checks Performed:**
- Failover Cluster Service responsiveness
- MOC Cloud/Node/Host Agent status
- MOC version validation
- Expired certificates
- Gallery images stuck in deleting
- VMs stuck in pending state
- Virtual Machine Management Service responsiveness

---

## 2. DIAGNOSTICS & LOG COLLECTION

### 2.1 Azure Local On-Demand Log Collection
| Attribute | Value |
|-----------|-------|
| **Name** | Send-DiagnosticData |
| **Type** | PowerShell Cmdlet |
| **Source** | Built-in (Azure Local 2311.2+) |
| **Documentation** | [MS Learn](https://learn.microsoft.com/en-us/azure/azure-local/manage/collect-logs) |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Capabilities:**
- Collect and send logs to Microsoft (Kusto database)
- Save logs to SMB share
- Send supplementary logs
- Send logs for specific roles only
- Requires `AzureEdgeTelemetryAndDiagnostics` extension

---

### 2.2 AKS Arc Log Collection
| Attribute | Value |
|-----------|-------|
| **Name** | az aksarc get-logs / Get-AzAksArcLog |
| **Type** | Azure CLI / PowerShell |
| **Source** | az aksarc extension |
| **Documentation** | [MS Learn](https://learn.microsoft.com/en-us/azure/aks/aksarc/get-on-demand-logs) |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Usage:**
```powershell
# By IP (single node)
az aksarc get-logs --ip 192.168.200.25 --credentials-dir ./.ssh --out-dir ./logs

# By kubeconfig (all nodes)
az aksarc get-logs --kubeconfig ./.kube/config --credentials-dir ./.ssh --out-dir ./logs
```

**Prerequisites:**
- SSH key from cluster creation
- Network access to cluster nodes

---

### 2.3 Get Kubelet Logs
| Attribute | Value |
|-----------|-------|
| **Name** | kubectl logs |
| **Type** | kubectl |
| **Documentation** | [MS Learn](https://learn.microsoft.com/en-us/azure/aks/aksarc/get-kubelet-logs) |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

---

## 3. TROUBLESHOOTING GUIDES (TSG)

### 3.1 AzLocalTSGTool
| Attribute | Value |
|-----------|-------|
| **Name** | AzLocalTSGTool |
| **Type** | PowerShell Module |
| **Source** | [PowerShell Gallery](https://www.powershellgallery.com/packages/AzLocalTSGTool) |
| **GitHub** | [smitzlroy/azlocaltsgtool](https://github.com/smitzlroy/azlocaltsgtool) |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Purpose:** Search known issues and fixes from GitHub supportability content.

---

### 3.2 AzureLocal-Supportability Repository
| Attribute | Value |
|-----------|-------|
| **Name** | AzureLocal-Supportability TSG Collection |
| **Type** | GitHub Repository |
| **Source** | [Azure/AzureLocal-Supportability](https://github.com/Azure/AzureLocal-Supportability) |
| **MCP Status** | 🔲 NOT IMPLEMENTED (via AzLocalTSGTool) |

**TSG Categories:**
| Category | Path | Description |
|----------|------|-------------|
| Deployment | `/TSG/Deployment` | Prerequisites, AD, Software Download, OS install, Registration, Arc extensions |
| Update | `/TSG/Update` | Health Check, Sideloading, Azure Update Manager, PowerShell updates |
| Upgrade | `/TSG/Upgrade` | Upgrade from 22H2 to 23H2 |
| LCM | `/TSG/LCM` | Lifecycle Manager issues |
| Lifecycle | `/TSG/Lifecycle` | Add Server, Repair Server operations |
| Arc VMs | `/TSG/ArcVMs` | VM lifecycle, licensing, extensions, networking, storage |
| Security | `/TSG/Security` | WDAC, BitLocker, Secret Rotation, Syslog, Defender |
| Networking | `/TSG/Networking` | Arc Gateway, Outbound Connectivity, TOR Configuration |
| Monitoring | `/TSG/Monitoring` | Insights, Metrics, Alerts |
| AVD | `/TSG/AVD` | Azure Virtual Desktop on Azure Local |
| AKS | `/TSG/AKS` | AKS Arc Deployment, Networking, Update |
| Storage | `/TSG/Storage` | Storage issues |
| Environment Validator | `/TSG/EnvironmentValidator` | Validation during deploy, update, scaleout, upgrade |
| Arc Registration | `/TSG/ArcRegistration` | Arc registration issues |

---

## 4. OPERATIONS & MANAGEMENT (Azure CLI)

### 4.1 Connected Kubernetes (az connectedk8s)
| Attribute | Value |
|-----------|-------|
| **Name** | az connectedk8s |
| **Type** | Azure CLI Extension |
| **MCP Status** | ⚠️ PARTIAL (list, show) |

**Key Commands:**
| Command | MCP Value | Description |
|---------|-----------|-------------|
| `az connectedk8s list` | HIGH | List all connected clusters |
| `az connectedk8s show` | HIGH | Get cluster details |
| `az connectedk8s connect` | MEDIUM | Connect a cluster to Arc |
| `az connectedk8s delete` | LOW | Remove Arc connection |
| `az connectedk8s enable-features` | MEDIUM | Enable features like custom-locations |
| `az connectedk8s troubleshoot` | HIGH | Diagnostic checks |

---

### 4.2 Kubernetes Extensions (az k8s-extension)
| Attribute | Value |
|-----------|-------|
| **Name** | az k8s-extension |
| **Type** | Azure CLI Extension |
| **MCP Status** | ⚠️ PARTIAL (list) |

**Key Commands:**
| Command | MCP Value | Description |
|---------|-----------|-------------|
| `az k8s-extension list` | HIGH | List installed extensions |
| `az k8s-extension show` | HIGH | Get extension details |
| `az k8s-extension create` | MEDIUM | Install an extension |
| `az k8s-extension update` | MEDIUM | Update extension config |
| `az k8s-extension delete` | LOW | Remove extension |

---

### 4.3 Kubernetes Configuration / GitOps (az k8s-configuration)
| Attribute | Value |
|-----------|-------|
| **Name** | az k8s-configuration flux |
| **Type** | Azure CLI Extension |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Key Commands:**
| Command | MCP Value | Description |
|---------|-----------|-------------|
| `az k8s-configuration flux list` | HIGH | List Flux configurations |
| `az k8s-configuration flux show` | HIGH | Get Flux config details |
| `az k8s-configuration flux create` | MEDIUM | Create GitOps config |
| `az k8s-configuration flux kustomization list` | MEDIUM | List kustomizations |

---

### 4.4 Custom Locations (az customlocation)
| Attribute | Value |
|-----------|-------|
| **Name** | az customlocation |
| **Type** | Azure CLI Extension |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Key Commands:**
| Command | MCP Value | Description |
|---------|-----------|-------------|
| `az customlocation list` | HIGH | List custom locations |
| `az customlocation show` | HIGH | Get details |
| `az customlocation create` | MEDIUM | Create custom location |

---

### 4.5 Azure Local (az stack-hci)
| Attribute | Value |
|-----------|-------|
| **Name** | az stack-hci |
| **Type** | Azure CLI Extension |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Key Commands:**
| Command | MCP Value | Description |
|---------|-----------|-------------|
| `az stack-hci cluster list` | HIGH | List Azure Local clusters |
| `az stack-hci cluster show` | HIGH | Get cluster details |
| `az stack-hci arc-setting show` | HIGH | Get Arc settings |
| `az stack-hci extension list` | HIGH | List extensions |

---

### 4.6 Azure Local VMs (az stack-hci-vm)
| Attribute | Value |
|-----------|-------|
| **Name** | az stack-hci-vm |
| **Type** | Azure CLI Extension |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Key Commands:**
| Command | MCP Value | Description |
|---------|-----------|-------------|
| `az stack-hci-vm list` | HIGH | List Arc VMs |
| `az stack-hci-vm show` | HIGH | Get VM details |
| `az stack-hci-vm start/stop/restart` | MEDIUM | VM power operations |

---

## 5. MONITORING & HEALTH

### 5.1 Azure Monitor Integration
| Attribute | Value |
|-----------|-------|
| **Name** | Insights extension |
| **Type** | Arc Extension |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Capabilities:**
- Container Insights for AKS Arc
- VM Insights for Arc VMs
- Azure Local Insights

---

### 5.2 Health Service
| Attribute | Value |
|-----------|-------|
| **Name** | Get-HealthFault |
| **Type** | PowerShell Cmdlet |
| **MCP Status** | 🔲 NOT IMPLEMENTED |

**Checks:**
- Cluster health faults
- Storage health
- Network health

---

## 6. IMPLEMENTATION PRIORITY

### Phase 1 (Current)
- [x] Environment Checker (Connectivity validation)
- [x] Basic cluster listing (az connectedk8s list)
- [x] Extension listing (az k8s-extension list)

### Phase 2 (Next)
- [ ] AKS Arc Support Tool (Test-SupportAksArcKnownIssues)
- [ ] AzLocalTSGTool integration
- [ ] Log collection (az aksarc get-logs)

### Phase 3 (Future)
- [ ] AKS Arc Diagnostic Checker
- [ ] Custom locations
- [ ] GitOps/Flux management
- [ ] VM operations

---

## 7. TOOL INTERFACE PATTERNS

### Pattern A: PowerShell Module Wrapper
```python
async def execute_powershell_tool(module: str, cmdlet: str, params: dict) -> dict:
    """Wrap a PowerShell cmdlet as an MCP tool."""
    cmd = f"Import-Module {module}; {cmdlet} {format_params(params)} | ConvertTo-Json -Depth 10"
    result = subprocess.run(["powershell", "-Command", cmd], capture_output=True)
    return json.loads(result.stdout)
```

### Pattern B: Azure CLI Wrapper
```python
async def execute_az_tool(command: list[str]) -> dict:
    """Wrap an Azure CLI command as an MCP tool."""
    cmd = ["az"] + command + ["-o", "json"]
    result = subprocess.run(cmd, capture_output=True)
    return json.loads(result.stdout)
```

### Pattern C: TSG Search
```python
async def search_tsg(query: str, category: str = None) -> list[dict]:
    """Search troubleshooting guides for relevant solutions."""
    # Use AzLocalTSGTool or direct GitHub API
    pass
```

---

## 8. REFERENCES

- [Azure Local Documentation](https://learn.microsoft.com/en-us/azure/azure-local/)
- [AKS Arc Documentation](https://learn.microsoft.com/en-us/azure/aks/aksarc/)
- [Azure Arc Documentation](https://learn.microsoft.com/en-us/azure/azure-arc/)
- [AzureLocal-Supportability GitHub](https://github.com/Azure/AzureLocal-Supportability)
- [AzLocalTSGTool](https://www.powershellgallery.com/packages/AzLocalTSGTool)
