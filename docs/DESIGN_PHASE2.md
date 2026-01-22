# Phase 2 Design: Tool Integration Architecture

This document defines how Phase 2 tools integrate into the ArcOps MCP server.

**Tools in Scope:**
1. Support.AksArc (`Test-SupportAksArcKnownIssues`)
2. AzLocalTSGTool (TSG search)
3. az aksarc get-logs (log collection)

---

## Design Principles

1. **Thin Wrappers Only** - Expose existing tool functionality as-is, no added behavior
2. **Consistent Findings Contract** - Normalize output to `findings.schema.json` where applicable
3. **No Auto-Remediation** - Always return diagnostics; user decides next action
4. **Respect Tool Design** - Each tool already has a purpose; we just make it accessible via MCP

---

## Tool 1: Support.AksArc Wrapper

### MCP Tool Definition

```yaml
name: aksarc.support.diagnose
description: >
  Run Test-SupportAksArcKnownIssues to check for common AKS Arc issues.
  Returns diagnostic results. Does not auto-remediate.

input_schema:
  type: object
  properties:
    dryRun:
      type: boolean
      default: false
      description: Return fixture data without running actual checks
```

### What It Does

Calls `Test-SupportAksArcKnownIssues` and returns the results. That's it.

The tool already checks:
- Failover Cluster Service responsiveness
- MOC Cloud/Node/Host Agent status
- MOC version validation
- Expired certificates
- Gallery images stuck in deleting
- VMs stuck in pending state
- VMMS responsiveness

### Execution

```powershell
Import-Module Support.AksArc
Test-SupportAksArcKnownIssues | ConvertTo-Json -Depth 10
```

### Output Mapping

Transform PowerShell output to findings schema, preserving all original data in `evidence`.

### File Structure

```
server/tools/
  aksarc_support_tool.py
tests/
  test_aksarc_support.py
  fixtures/
    aksarc_support_sample.json
```

---

## Tool 2: AzLocalTSGTool Integration

### MCP Tool Definition

```yaml
name: azlocal.tsg.search
description: >
  Search Azure Local troubleshooting guides using AzLocalTSGTool.
  The module handles GitHub indexing and local caching.

input_schema:
  type: object
  required: [query]
  properties:
    query:
      type: string
      description: Error message, symptom, or keyword to search
```

### What It Does

Calls your existing `Search-AzLocalTSG` cmdlet. The module already handles:
- GitHub content indexing
- Local caching
- Relevance ranking

### Execution

```powershell
Import-Module AzLocalTSGTool
Search-AzLocalTSG -Query "certificate expired" | ConvertTo-Json -Depth 10
```

### Output

Return the module's native output directly. No transformation needed.

### File Structure

```
server/tools/
  azlocal_tsg_tool.py
tests/
  test_tsg_tool.py
  fixtures/
    tsg_search_sample.json
```

---

## Tool 3: AKS Arc Log Collection

### MCP Tool Definition

```yaml
name: aksarc.logs.collect
description: >
  Collect diagnostic logs from AKS Arc cluster using az aksarc get-logs.

input_schema:
  type: object
  properties:
    ip:
      type: string
      description: Node IP address (for single node collection)
    kubeconfig:
      type: string
      description: Path to kubeconfig (for all nodes)
    credentialsDir:
      type: string
      description: Path to SSH keys
    outDir:
      type: string
      default: ./logs
      description: Output directory
```

### What It Does

Calls `az aksarc get-logs` with the provided parameters. Returns the path to collected logs.

### Execution

```bash
az aksarc get-logs --ip 192.168.200.25 --credentials-dir ./.ssh --out-dir ./logs
```

### Output

Return command result: success/failure, output path, any errors.

### File Structure

```
server/tools/
  aksarc_logs_tool.py
tests/
  test_aksarc_logs.py
```

---

## Implementation Order

1. **aksarc_support_tool.py** - Wraps `Test-SupportAksArcKnownIssues`
2. **azlocal_tsg_tool.py** - Wraps `Search-AzLocalTSG`
3. **aksarc_logs_tool.py** - Wraps `az aksarc get-logs`

Each tool follows the same pattern as `arc_connectivity_check.py`:
- Inherit from `BaseTool`
- Check for module/CLI availability
- Execute and return results
- Support `dryRun` with fixture data for testing
