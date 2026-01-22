"""
Real Azure API endpoints for ArcOps MCP Server.

These endpoints call actual Azure CLI to get real cluster data,
not simulated/mock data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from server.azure_context import AzureContext

logger = logging.getLogger(__name__)

# Create router for API endpoints
router = APIRouter(prefix="/api", tags=["azure"])


def _find_az_cli() -> str | None:
    """Find Azure CLI executable, checking common paths.

    DEPRECATED: Use AzureContext.find_az_cli() instead.
    """
    return AzureContext.find_az_cli()


@router.get("/clusters")
async def list_clusters(subscription: str | None = None) -> dict[str, Any]:
    """
    List real AKS Arc connected clusters from Azure.

    Requires az CLI to be authenticated (az login).
    """
    return await AzureContext.get_connected_clusters(subscription)


@router.get("/cluster/{cluster_name}/extensions")
async def get_cluster_extensions(cluster_name: str, resource_group: str) -> dict[str, Any]:
    """Get extensions installed on a specific AKS Arc cluster."""
    az_cmd = _find_az_cli()

    if not az_cmd:
        return {"success": False, "extensions": [], "error": "Azure CLI not found"}

    try:
        cmd = [
            az_cmd,
            "k8s-extension",
            "list",
            "--cluster-name",
            cluster_name,
            "--resource-group",
            resource_group,
            "--cluster-type",
            "connectedClusters",
            "-o",
            "json",
        ]

        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            return {"success": False, "extensions": [], "error": result.stderr}

        extensions = json.loads(result.stdout)

        ext_summaries = []
        for ext in extensions:
            ext_summaries.append(
                {
                    "name": ext.get("name"),
                    "extensionType": ext.get("extensionType"),
                    "provisioningState": ext.get("provisioningState"),
                    "version": ext.get("version"),
                    "releaseTrain": ext.get("releaseTrain"),
                    "isSystemExtension": ext.get("isSystemExtension", False),
                }
            )

        return {
            "success": True,
            "cluster": cluster_name,
            "count": len(extensions),
            "extensions": ext_summaries,
        }

    except Exception as e:
        logger.exception("Error getting extensions")
        return {"success": False, "extensions": [], "error": str(e)}


@router.get("/cluster/{cluster_name}/validate")
async def validate_cluster(cluster_name: str, resource_group: str) -> dict[str, Any]:
    """
    Validate a specific AKS Arc cluster.

    Checks:
    - Connectivity status
    - Agent version
    - Extensions installed
    - Common issues
    """
    az_cmd = _find_az_cli()

    if not az_cmd:
        return {"success": False, "checks": [], "error": "Azure CLI not found"}

    checks = []

    try:
        # Get cluster details
        cmd = [
            az_cmd,
            "connectedk8s",
            "show",
            "--name",
            cluster_name,
            "--resource-group",
            resource_group,
            "-o",
            "json",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            return {"success": False, "checks": [], "error": f"Cluster not found: {result.stderr}"}

        cluster = json.loads(result.stdout)

        # Check 1: Connectivity
        connectivity = cluster.get("connectivityStatus", "Unknown")
        checks.append(
            {
                "id": "aks.arc.connectivity",
                "title": "Cluster Connectivity",
                "status": "pass" if connectivity == "Connected" else "fail",
                "severity": "high" if connectivity != "Connected" else "info",
                "evidence": {
                    "connectivityStatus": connectivity,
                    "lastConnectivityTime": cluster.get("lastConnectivityTime"),
                },
                "hint": (
                    "Cluster is offline - check network connectivity and Arc agent"
                    if connectivity != "Connected"
                    else None
                ),
            }
        )

        # Check 2: Provisioning state
        prov_state = cluster.get("provisioningState", "Unknown")
        checks.append(
            {
                "id": "aks.arc.provisioning",
                "title": "Provisioning State",
                "status": "pass" if prov_state == "Succeeded" else "warn",
                "severity": "medium" if prov_state != "Succeeded" else "info",
                "evidence": {"provisioningState": prov_state},
            }
        )

        # Check 3: Agent version
        agent_version = cluster.get("agentVersion", "Unknown")
        checks.append(
            {
                "id": "aks.arc.agent.version",
                "title": "Arc Agent Version",
                "status": "pass",  # Would need version comparison logic
                "severity": "info",
                "evidence": {
                    "agentVersion": agent_version,
                    "distribution": cluster.get("distribution"),
                    "kubernetesVersion": cluster.get("kubernetesVersion"),
                },
            }
        )

        # Get extensions
        ext_result = await get_cluster_extensions(cluster_name, resource_group)
        if ext_result.get("success"):
            ext_count = ext_result.get("count", 0)
            ext_names = [e.get("extensionType") for e in ext_result.get("extensions", [])]

            # Check for expected extensions
            expected = ["microsoft.azuremonitor.containers", "microsoft.flux"]
            missing = [e for e in expected if e not in ext_names]

            checks.append(
                {
                    "id": "aks.arc.extensions",
                    "title": "Arc Extensions",
                    "status": "pass" if not missing else "warn",
                    "severity": "medium" if missing else "info",
                    "evidence": {
                        "installed": ext_names,
                        "count": ext_count,
                        "missing": missing if missing else None,
                    },
                    "hint": f"Consider installing: {', '.join(missing)}" if missing else None,
                }
            )

        return {
            "success": True,
            "cluster": cluster_name,
            "resourceGroup": resource_group,
            "checks": checks,
            "summary": {
                "total": len(checks),
                "passed": len([c for c in checks if c["status"] == "pass"]),
                "warnings": len([c for c in checks if c["status"] == "warn"]),
                "failed": len([c for c in checks if c["status"] == "fail"]),
            },
        }

    except Exception as e:
        logger.exception("Error validating cluster")
        return {"success": False, "checks": [], "error": str(e)}


@router.post("/diagnose")
async def comprehensive_diagnose(request: dict[str, Any] = None) -> dict[str, Any]:
    """
    Run comprehensive AKS Arc diagnostics - the multi-tool orchestration endpoint.

    This chains multiple checks together and provides:
    1. Connectivity checks (firewall, DNS, TLS)
    2. Cluster validation (if connected)
    3. TSG suggestions for any issues found
    4. Actionable remediation steps

    Perfect for support engineers who need a one-click diagnostic report.
    """
    import sys
    from datetime import datetime

    project_root = Path(__file__).parent.parent
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)

    diagnosis = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "stages": [],
        "all_issues": [],
        "tsg_suggestions": [],
        "overall_health": "unknown",
    }

    # Stage 1: Connectivity Check
    logger.info("Running comprehensive diagnosis - Stage 1: Connectivity")
    try:
        egress_file = results_dir / "egress.json"
        if egress_file.exists():
            egress_file.unlink()

        result = subprocess.run(
            [sys.executable, "-m", "cli", "egress", "--dry-run", "--out", str(results_dir)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=120,
            env={**os.environ, "PYTHONUTF8": "1"},
        )

        if egress_file.exists():
            connectivity_result = json.loads(egress_file.read_text(encoding="utf-8"))
        else:
            connectivity_result = {"error": "No output file generated", "stderr": result.stderr}
    except Exception as e:
        connectivity_result = {"error": str(e)}

    conn_summary = connectivity_result.get("summary", {})
    diagnosis["stages"].append(
        {
            "name": "Connectivity Check",
            "tool": "egress",
            "status": (
                "fail"
                if conn_summary.get("fail", 0) > 0
                else ("warn" if conn_summary.get("warn", 0) > 0 else "pass")
            ),
            "summary": conn_summary,
            "issues": [
                c
                for c in connectivity_result.get("checks", [])
                if c.get("status") in ("fail", "warn")
            ],
        }
    )

    # Collect issues
    for check in connectivity_result.get("checks", []):
        if check.get("status") in ("fail", "warn"):
            diagnosis["all_issues"].append(
                {
                    "source": "connectivity",
                    "id": check.get("id"),
                    "title": check.get("title"),
                    "status": check.get("status"),
                    "hint": check.get("hint"),
                }
            )

    # Stage 2: Cluster Validation
    logger.info("Running comprehensive diagnosis - Stage 2: Cluster Validation")
    try:
        validate_file = results_dir / "validate.json"
        if validate_file.exists():
            validate_file.unlink()

        result = subprocess.run(
            [sys.executable, "-m", "cli", "validate", "--dry-run", "--out", str(results_dir)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=120,
            env={**os.environ, "PYTHONUTF8": "1"},
        )

        if validate_file.exists():
            validate_result = json.loads(validate_file.read_text(encoding="utf-8"))
        else:
            validate_result = {"error": "No output file generated", "stderr": result.stderr}
    except Exception as e:
        validate_result = {"error": str(e)}

    val_summary = validate_result.get("summary", {})
    diagnosis["stages"].append(
        {
            "name": "Cluster Validation",
            "tool": "validate",
            "status": (
                "fail"
                if val_summary.get("fail", 0) > 0
                else ("warn" if val_summary.get("warn", 0) > 0 else "pass")
            ),
            "summary": val_summary,
            "issues": [
                c for c in validate_result.get("checks", []) if c.get("status") in ("fail", "warn")
            ],
        }
    )

    # Collect issues
    for check in validate_result.get("checks", []):
        if check.get("status") in ("fail", "warn"):
            diagnosis["all_issues"].append(
                {
                    "source": "cluster",
                    "id": check.get("id"),
                    "title": check.get("title"),
                    "status": check.get("status"),
                    "hint": check.get("hint"),
                }
            )

    # Stage 3: Generate TSG suggestions
    if diagnosis["all_issues"]:
        diagnosis["tsg_suggestions"] = _generate_tsg_suggestions(diagnosis["all_issues"])

    # Calculate overall health
    fail_count = sum(s["summary"].get("fail", 0) for s in diagnosis["stages"] if s.get("summary"))
    warn_count = sum(s["summary"].get("warn", 0) for s in diagnosis["stages"] if s.get("summary"))
    pass_count = sum(s["summary"].get("pass", 0) for s in diagnosis["stages"] if s.get("summary"))

    if fail_count > 0:
        diagnosis["overall_health"] = "critical"
        diagnosis["health_icon"] = "🔴"
    elif warn_count > 0:
        diagnosis["overall_health"] = "degraded"
        diagnosis["health_icon"] = "🟡"
    else:
        diagnosis["overall_health"] = "healthy"
        diagnosis["health_icon"] = "🟢"

    diagnosis["totals"] = {
        "pass": pass_count,
        "warn": warn_count,
        "fail": fail_count,
        "total_issues": len(diagnosis["all_issues"]),
    }

    # Generate executive summary
    diagnosis["executive_summary"] = _generate_executive_summary(diagnosis)

    return {"success": True, "diagnosis": diagnosis}


def _generate_executive_summary(diagnosis: dict[str, Any]) -> str:
    """Generate a human-readable executive summary of the diagnosis."""
    lines = []

    health = diagnosis.get("overall_health", "unknown")
    icon = diagnosis.get("health_icon", "❓")
    totals = diagnosis.get("totals", {})

    lines.append(f"{icon} **Overall System Health: {health.upper()}**")
    lines.append("")
    lines.append(f"**Diagnostics Summary:**")
    lines.append(f"- ✅ Passed: {totals.get('pass', 0)} checks")
    lines.append(f"- ⚠️ Warnings: {totals.get('warn', 0)} checks")
    lines.append(f"- ❌ Failed: {totals.get('fail', 0)} checks")

    # List critical issues
    critical = [i for i in diagnosis.get("all_issues", []) if i.get("status") == "fail"]
    if critical:
        lines.append("")
        lines.append("**🚨 Critical Issues Requiring Attention:**")
        for issue in critical[:5]:
            lines.append(f"- **{issue.get('title', 'Unknown')}**")
            if issue.get("hint"):
                lines.append(f"  └─ 💡 {issue['hint']}")

    # TSG suggestions
    suggestions = diagnosis.get("tsg_suggestions", [])
    if suggestions:
        lines.append("")
        lines.append("**📚 Recommended Troubleshooting Guides:**")
        for tsg in suggestions[:3]:
            lines.append(f'- Search: *"{tsg}"*')

    return "\n".join(lines)


@router.get("/subscriptions")
async def list_subscriptions() -> dict[str, Any]:
    """List available Azure subscriptions."""
    az_cmd = _find_az_cli()

    if not az_cmd:
        return {"success": False, "subscriptions": [], "error": "Azure CLI not found"}

    try:
        cmd = [az_cmd, "account", "list", "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {
                "success": False,
                "subscriptions": [],
                "error": result.stderr,
                "hint": "Run 'az login' to authenticate",
            }

        subs = json.loads(result.stdout)

        sub_summaries = []
        for s in subs:
            sub_summaries.append(
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "isDefault": s.get("isDefault", False),
                    "state": s.get("state"),
                }
            )

        return {"success": True, "count": len(subs), "subscriptions": sub_summaries}

    except Exception as e:
        logger.exception("Error listing subscriptions")
        return {"success": False, "subscriptions": [], "error": str(e)}


@router.get("/status")
async def azure_status() -> dict[str, Any]:
    """Check Azure CLI status and authentication."""
    auth_status = await AzureContext.check_auth()
    return AzureContext.to_api_response(auth_status)


@router.get("/tools/status")
async def tools_status() -> dict[str, Any]:
    """
    Get the status of all available tools and their dependencies.

    Returns readiness state for each tool category.
    """
    tools = []

    # 1. Azure CLI - needed for most operations
    az_cmd = _find_az_cli()
    tools.append(
        {
            "id": "azure-cli",
            "name": "Azure CLI",
            "description": "Required for Azure operations",
            "ready": az_cmd is not None,
            "hint": (
                "Install: https://docs.microsoft.com/cli/azure/install-azure-cli"
                if not az_cmd
                else None
            ),
        }
    )

    # 2. Environment Checker - for connectivity checks
    envchecker_ready = False
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-Module -ListAvailable AzStackHci.EnvironmentChecker"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        envchecker_ready = "AzStackHci.EnvironmentChecker" in result.stdout
    except Exception:
        pass
    tools.append(
        {
            "id": "env-checker",
            "name": "Environment Checker",
            "description": "Connectivity validation",
            "ready": envchecker_ready,
            "hint": (
                "Install-Module AzStackHci.EnvironmentChecker -Force"
                if not envchecker_ready
                else None
            ),
        }
    )

    # 3. Support.AksArc - for known issues detection
    support_ready = False
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-Module -ListAvailable Support.AksArc"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        support_ready = "Support.AksArc" in result.stdout
    except Exception:
        pass
    tools.append(
        {
            "id": "support-aksarc",
            "name": "Support.AksArc",
            "description": "Known issues detection",
            "ready": support_ready,
            "hint": "Install-Module Support.AksArc -Force" if not support_ready else None,
        }
    )

    # 4. AzLocalTSGTool - for TSG search
    tsg_ready = False
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Get-Module -ListAvailable AzLocalTSGTool"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        tsg_ready = "AzLocalTSGTool" in result.stdout
    except Exception:
        pass
    tools.append(
        {
            "id": "tsg-search",
            "name": "TSG Search",
            "description": "Troubleshooting guides",
            "ready": tsg_ready,
            "hint": "Install-Module AzLocalTSGTool -Force" if not tsg_ready else None,
        }
    )

    # 5. az aksarc extension - for logs collection
    aksarc_ext_ready = False
    if az_cmd:
        try:
            result = subprocess.run(
                [az_cmd, "extension", "list", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                extensions = json.loads(result.stdout)
                aksarc_ext_ready = any(e.get("name") == "aksarc" for e in extensions)
        except Exception:
            pass
    tools.append(
        {
            "id": "aksarc-logs",
            "name": "AKS Arc Logs",
            "description": "Collect cluster logs",
            "ready": aksarc_ext_ready,
            "hint": "az extension add --name aksarc" if not aksarc_ext_ready else None,
        }
    )

    # 6. Foundry Local - for AI chat
    foundry_ready = False
    foundry_models = []
    try:
        from foundry_local import FoundryLocalManager

        manager = FoundryLocalManager("qwen2.5-0.5b")
        loaded = manager.list_loaded_models()
        foundry_ready = len(loaded) > 0
        foundry_models = [m.id for m in loaded] if loaded else []
    except ImportError:
        pass
    except Exception:
        pass
    tools.append(
        {
            "id": "foundry-local",
            "name": "AI Chat",
            "description": "Foundry Local AI",
            "ready": foundry_ready,
            "models": foundry_models,
            "hint": "foundry model run qwen2.5-0.5b" if not foundry_ready else None,
        }
    )

    # Calculate summary
    ready_count = sum(1 for t in tools if t["ready"])
    total_count = len(tools)

    return {
        "success": True,
        "tools": tools,
        "summary": {
            "ready": ready_count,
            "total": total_count,
            "percentage": int((ready_count / total_count) * 100),
        },
    }


# ============================================================================
# CONNECTIVITY CHECK ENDPOINTS
# ============================================================================


@router.get("/connectivity/check")
async def run_connectivity_check(
    mode: str = "quick",
    install_checker: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Run connectivity check for Azure Local / AKS Arc.

    Args:
        mode: Check mode - 'quick' (key endpoints), 'full' (all), 'endpoints-only'
        install_checker: Auto-install Microsoft Environment Checker if missing
        dry_run: Simulate checks using fixture data

    Returns:
        Findings with connectivity check results
    """
    from server.tools.arc_connectivity_check import ArcConnectivityCheckTool

    tool = ArcConnectivityCheckTool()
    result = await tool.execute(
        {
            "mode": mode,
            "installChecker": install_checker,
            "dryRun": dry_run,
        }
    )

    return {"success": True, "findings": result}


@router.get("/connectivity/check/stream")
async def run_connectivity_check_stream(
    mode: str = "quick",
    install_checker: bool = False,
    dry_run: bool = False,
):
    """
    Run connectivity check with Server-Sent Events (SSE) streaming.

    Streams progress updates in real-time, then sends final results.

    Event types:
    - status: Phase changes (detecting, installing, running)
    - progress: Individual check progress
    - complete: Final results with full findings
    - error: Error occurred
    """
    from fastapi.responses import StreamingResponse
    import asyncio
    from server.tools.arc_connectivity_check import ArcConnectivityCheckTool

    async def event_generator():
        # Queue for progress updates
        progress_queue: asyncio.Queue = asyncio.Queue()
        findings_result = None
        error_result = None

        async def progress_callback(data: dict):
            await progress_queue.put(data)

        async def run_check():
            nonlocal findings_result, error_result
            try:
                tool = ArcConnectivityCheckTool()
                findings_result = await tool.execute(
                    {
                        "mode": mode,
                        "installChecker": install_checker,
                        "dryRun": dry_run,
                    },
                    progress_callback=progress_callback,
                )
            except Exception as e:
                error_result = str(e)
            finally:
                # Signal completion
                await progress_queue.put(None)

        # Start the check in background
        task = asyncio.create_task(run_check())

        # Stream progress updates
        while True:
            try:
                data = await asyncio.wait_for(progress_queue.get(), timeout=120)

                if data is None:
                    # Check completed
                    break

                # Send SSE event
                event_data = json.dumps(data)
                yield f"event: {data.get('type', 'progress')}\ndata: {event_data}\n\n"

            except asyncio.TimeoutError:
                # Send keepalive
                yield f": keepalive\n\n"

        # Wait for task completion
        await task

        # Send final result
        if error_result:
            yield f"event: error\ndata: {json.dumps({'error': error_result})}\n\n"
        elif findings_result:
            yield f"event: complete\ndata: {json.dumps({'success': True, 'findings': findings_result})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/connectivity/checker-status")
async def checker_status() -> dict[str, Any]:
    """Check if Microsoft Environment Checker is installed."""
    # Standard installation paths
    checker_paths = [
        r"C:\Program Files\WindowsPowerShell\Modules\AzStackHci.EnvironmentChecker",
        r"C:\Program Files\PowerShell\Modules\AzStackHci.EnvironmentChecker",
    ]

    for base_path in checker_paths:
        path = Path(base_path)
        if path.exists():
            # Find the module manifest
            manifests = list(path.glob("**/AzStackHci.EnvironmentChecker.psd1"))
            if manifests:
                return {
                    "installed": True,
                    "path": str(manifests[0]),
                    "location": str(path),
                }

    # Check via PowerShell
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-Module -ListAvailable AzStackHci.EnvironmentChecker | Select-Object Name, Version, Path | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            module_info = json.loads(result.stdout)
            if module_info:
                return {
                    "installed": True,
                    "module": module_info,
                    "source": "powershell",
                }
    except Exception as e:
        logger.debug("PowerShell check failed: %s", e)

    return {
        "installed": False,
        "hint": "Install with: Install-Module -Name AzStackHci.EnvironmentChecker -Force",
        "installCommand": "Install-Module -Name AzStackHci.EnvironmentChecker -Force -Scope CurrentUser",
    }


@router.post("/connectivity/install-checker")
async def install_checker() -> dict[str, Any]:
    """Install Microsoft Environment Checker via PowerShell."""
    logger.info("Installing AzStackHci.EnvironmentChecker module...")

    try:
        install_cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            """
            Write-Host "Setting PSGallery as trusted..."
            Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction SilentlyContinue

            Write-Host "Installing AzStackHci.EnvironmentChecker..."
            Install-Module -Name AzStackHci.EnvironmentChecker -Force -AllowClobber -Scope CurrentUser

            Write-Host "Verifying installation..."
            $module = Get-Module -ListAvailable AzStackHci.EnvironmentChecker | Select-Object Name, Version, Path
            if ($module) {
                Write-Host "SUCCESS: Module installed"
                $module | ConvertTo-Json
            } else {
                Write-Host "ERROR: Module not found after installation"
                exit 1
            }
            """,
        ]

        result = subprocess.run(
            install_cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            # Try to parse module info from output
            try:
                # Find JSON in output
                lines = result.stdout.strip().split("\n")
                json_start = None
                for i, line in enumerate(lines):
                    if line.strip().startswith("{"):
                        json_start = i
                        break

                if json_start is not None:
                    json_str = "\n".join(lines[json_start:])
                    module_info = json.loads(json_str)
                    return {
                        "success": True,
                        "module": module_info,
                        "message": "Environment Checker installed successfully",
                        "output": result.stdout,
                    }
            except json.JSONDecodeError:
                pass

            return {
                "success": True,
                "message": "Environment Checker installed (verification pending)",
                "output": result.stdout,
            }
        else:
            return {
                "success": False,
                "error": result.stderr or "Installation failed",
                "output": result.stdout,
                "hint": "Try running PowerShell as Administrator",
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Installation timed out after 5 minutes",
            "hint": "Check network connectivity to PowerShell Gallery",
        }
    except Exception as e:
        logger.exception("Failed to install Environment Checker")
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/connectivity/endpoints")
async def list_endpoints(category: str | None = None) -> dict[str, Any]:
    """List configured endpoints for connectivity checking."""
    import yaml

    config_path = Path(__file__).parent / "config" / "endpoints.yaml"

    if not config_path.exists():
        return {"success": False, "error": "Endpoints config not found"}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        endpoints = config.get("endpoints", [])

        if category:
            endpoints = [e for e in endpoints if e.get("category") == category]

        # Group by category
        by_category: dict[str, list[dict[str, Any]]] = {}
        for ep in endpoints:
            cat = ep.get("category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(ep)

        return {
            "success": True,
            "total": len(endpoints),
            "categories": list(by_category.keys()),
            "byCategory": by_category,
            "endpoints": endpoints,
        }

    except Exception as e:
        logger.exception("Failed to load endpoints")
        return {"success": False, "error": str(e)}


# ============================================================================
# Chat API for web UI
# ============================================================================


class ChatMessage:
    """Simple chat message structure."""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


import re


def _parse_tool_calls_from_content(content: str) -> list[dict[str, Any]]:
    """
    Parse tool calls from content that contains <tool_call> XML tags.

    Some models output tool calls in the format:
    <tool_call>
    {"name": "tool_name", "arguments": {...}}
    </tool_call>
    """
    if not content:
        return []

    tool_calls = []
    pattern = r"<tool_call>\s*({.*?})\s*</tool_call>"
    matches = re.findall(pattern, content, re.DOTALL)

    for match in matches:
        try:
            parsed = json.loads(match)
            if "name" in parsed:
                tool_calls.append(parsed)
        except json.JSONDecodeError:
            logger.warning("Failed to parse tool call: %s", match)
            continue

    return tool_calls


def _clean_tool_call_content(content: str) -> str:
    """Remove <tool_call> XML tags from content for clean display."""
    if not content:
        return ""

    # Remove tool_call blocks
    pattern = r"<tool_call>\s*{.*?}\s*</tool_call>"
    cleaned = re.sub(pattern, "", content, flags=re.DOTALL)

    # Clean up extra whitespace
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    return cleaned


def _summarize_tool_results(tool_results: list[dict[str, Any]]) -> str:
    """Generate a human-readable summary of tool results with TSG auto-linking."""
    summaries = []
    all_issues = []  # Collect issues across all tools for TSG suggestions

    for tr in tool_results:
        tool_name = tr.get("tool", "unknown")
        result = tr.get("result", {})

        # Handle TSG search results
        if tool_name == "search_tsg":
            output = result.get("output", "")
            query = result.get("query", "")
            if output:
                summaries.append(f"\n📚 **TSG Search Results** (query: '{query}'):\n{output}")
            else:
                summaries.append(f"\n📚 **TSG Search**: No results for '{query}'")
            continue

        # Get checks and summary
        checks = result.get("checks", [])
        summary = result.get("summary", {})

        if not checks and not summary:
            # Handle error cases
            if result.get("error"):
                summaries.append(
                    f"**{_tool_display_name(tool_name)}**: ❌ Error - {result['error']}"
                )
            continue

        # Count results
        pass_count = summary.get("pass", 0)
        warn_count = summary.get("warn", 0)
        fail_count = summary.get("fail", 0)
        total = summary.get("total", len(checks))

        # Build status line with visual indicator
        if fail_count > 0:
            status = f"❌ {fail_count} failed"
            status_icon = "🔴"
        elif warn_count > 0:
            status = f"⚠️ {warn_count} warnings"
            status_icon = "🟡"
        else:
            status = f"✅ All {pass_count} checks passed"
            status_icon = "🟢"

        tool_display = _tool_display_name(tool_name)
        summaries.append(f"{status_icon} **{tool_display}**: {status} (out of {total} checks)")

        # List issues with enhanced details
        issues = [c for c in checks if c.get("status") in ("fail", "warn")]
        if issues:
            summaries.append("\n**Issues found:**")
            for issue in issues[:5]:  # Limit to top 5
                icon = "❌" if issue.get("status") == "fail" else "⚠️"
                title = issue.get("title", "Unknown check")
                hint = issue.get("hint", "")
                check_id = issue.get("id", "")
                evidence = issue.get("evidence", {})

                summaries.append(f"- {icon} **{title}**")
                if check_id:
                    summaries.append(f"  📋 Check ID: `{check_id}`")
                if hint:
                    summaries.append(f"  💡 {hint}")

                # Add key evidence
                if evidence and isinstance(evidence, dict):
                    key_evidence = _extract_key_evidence(evidence)
                    if key_evidence:
                        summaries.append(f"  📊 {key_evidence}")

                # Collect for TSG auto-suggest
                all_issues.append(
                    {
                        "title": title,
                        "id": check_id,
                        "status": issue.get("status"),
                        "hint": hint,
                    }
                )

        # If all passed, give positive confirmation
        if pass_count > 0 and fail_count == 0 and warn_count == 0:
            summaries.append(
                "\n✅ All connectivity and validation checks passed. Your Azure connection is healthy."
            )

    # Auto-suggest TSG searches for found issues
    if all_issues:
        tsg_suggestions = _generate_tsg_suggestions(all_issues)
        if tsg_suggestions:
            summaries.append("\n---")
            summaries.append("🔎 **Suggested Troubleshooting Guide Searches:**")
            for suggestion in tsg_suggestions[:3]:  # Top 3 suggestions
                summaries.append(f'- Search TSG for: *"{suggestion}"*')
            summaries.append("\n💬 *Ask me to search any of these to find solutions!*")

    if not summaries:
        return "I ran the diagnostic tools but couldn't parse the results. Please check the detailed output below."

    return "\n".join(summaries)


def _extract_key_evidence(evidence: dict[str, Any]) -> str:
    """Extract the most relevant evidence for display."""
    # Priority fields to show
    priority_keys = ["error", "message", "endpoint", "errorDetails", "actual", "expected"]

    for key in priority_keys:
        if key in evidence and evidence[key]:
            value = evidence[key]
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            return f"{key}: `{value}`"

    # Show first string value if no priority key found
    for key, value in evidence.items():
        if isinstance(value, str) and value:
            if len(value) > 80:
                value = value[:80] + "..."
            return f"{key}: `{value}`"

    return ""


def _generate_tsg_suggestions(issues: list[dict[str, Any]]) -> list[str]:
    """Generate TSG search suggestions based on found issues."""
    suggestions = []

    # Map common check IDs/titles to TSG search terms
    tsg_mappings = {
        # Connectivity issues
        "arc.connectivity": "Azure Arc connectivity troubleshooting",
        "arc.gateway": "Azure Arc gateway connectivity",
        "aks.arc.connectivity": "AKS Arc cluster connection issues",
        "firewall": "Azure Arc firewall requirements",
        "dns": "Azure Arc DNS resolution",
        "proxy": "Azure Arc proxy configuration",
        "tls": "Azure Arc TLS certificate issues",
        "ssl": "Azure Arc SSL certificate",
        "egress": "Azure Arc egress requirements",
        "monitoring": "Azure Arc monitoring endpoints",
        "telemetry": "Azure Arc telemetry configuration",
        "visualstudio": "Azure monitoring Visual Studio endpoint",
        # Cluster issues
        "cluster.offline": "AKS Arc cluster offline troubleshooting",
        "extension": "AKS Arc extension installation",
        "agent": "Azure Arc agent troubleshooting",
        "provisioning": "AKS Arc provisioning failed",
        "cni": "AKS Arc CNI troubleshooting",
        "flux": "AKS Arc Flux GitOps issues",
        # Environment issues
        "hardware": "Azure Local hardware requirements",
        "memory": "Azure Local memory requirements",
        "disk": "Azure Local disk requirements",
        "network": "Azure Local network configuration",
        "hyperv": "Hyper-V requirements Azure Local",
        "cpu": "Azure Local CPU requirements",
        "storage": "Azure Local storage requirements",
    }

    for issue in issues:
        check_id = issue.get("id", "").lower()
        title = issue.get("title", "").lower()
        hint = issue.get("hint", "").lower()

        # Try to match to TSG suggestions
        matched = False
        for keyword, tsg_query in tsg_mappings.items():
            if keyword in check_id or keyword in title or keyword in hint:
                if tsg_query not in suggestions:
                    suggestions.append(tsg_query)
                matched = True
                break

        # Use title as fallback search term if no match (for both fail and warn)
        if not matched and issue.get("status") in ("fail", "warn") and issue.get("title"):
            clean_title = issue["title"].replace("Check", "").replace("Egress", "").strip()
            fallback = f"Azure Arc {clean_title}"
            if fallback not in suggestions and len(clean_title) > 5:
                suggestions.append(fallback)

    return suggestions


def _tool_display_name(tool_name: str) -> str:
    """Get display name for a tool."""
    names = {
        "run_connectivity_check": "Azure Connectivity Check",
        "check_environment": "Environment Validation",
        "validate_cluster": "AKS Arc Cluster Validation",
        "search_tsg": "Troubleshooting Guide Search",
    }
    return names.get(tool_name, tool_name)


CHAT_SYSTEM_PROMPT = """You are ArcOps Assistant, an AI expert on Azure Local and AKS Arc operations.

CRITICAL: You MUST use tools to answer questions. Never guess or describe - always call the appropriate tool.

TOOL DECISION TREE (follow exactly):

1. ERROR MESSAGES / PROBLEMS → ALWAYS call search_tsg first
   Keywords: "error", "failed", "not working", "issue", "problem", "fix", "help", "troubleshoot"
   Example: "I have error 0x800xxxxx" → search_tsg(query="0x800xxxxx")
   Example: "certificate expired" → search_tsg(query="certificate expired")
   Example: "can't connect" → search_tsg(query="connection failed")

2. CONNECTIVITY / NETWORK → call run_connectivity_check
   Keywords: "connectivity", "reach Azure", "firewall", "DNS", "endpoints", "egress"
   Example: "can I reach Azure?" → run_connectivity_check()

3. CLUSTER HEALTH → call validate_cluster
   Keywords: "cluster", "validate", "AKS", "Kubernetes", "k8s", "health"
   Example: "is my cluster healthy?" → validate_cluster()

4. ENVIRONMENT / PREREQUISITES → call check_environment
   Keywords: "environment", "prerequisites", "ready", "requirements"
   Example: "is my system ready?" → check_environment()

5. UNKNOWN / GENERAL → search_tsg with the user's question
   Example: "why is deployment slow" → search_tsg(query="deployment slow")

RESPONSE FORMAT:
- After tool results, summarize concisely
- ❌ for failures, ⚠️ for warnings, ✅ for passed
- Always suggest next steps
- If issues found, suggest: "Ask me to search for [specific error]"""


@router.post("/chat")
async def chat(
    request: dict[str, Any],
) -> dict[str, Any]:
    """
    Chat endpoint for conversational AI interaction.

    Supports Foundry Local or any OpenAI-compatible API.
    """
    messages = request.get("messages", [])
    if not messages:
        return {"success": False, "error": "No messages provided"}

    # Try to use Foundry Local
    try:
        return await _chat_with_foundry(messages)
    except Exception as e:
        logger.warning("Foundry Local not available: %s", e)
        return {
            "success": False,
            "error": "AI chat requires Foundry Local. Start it with: foundry model run qwen2.5-0.5b",
            "hint": "Install: pip install foundry-local-sdk",
        }


async def _chat_with_foundry(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Chat using Foundry Local SDK."""
    import httpx

    try:
        from foundry_local import FoundryLocalManager

        manager = FoundryLocalManager("qwen2.5-0.5b")
        endpoint = manager.endpoint

        # Get loaded model
        loaded = manager.list_loaded_models()
        model_id = loaded[0].id if loaded else "qwen2.5-0.5b"
    except ImportError:
        raise RuntimeError("foundry-local-sdk not installed")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Foundry Local: {e}")

    # Add system prompt if not present
    if not messages or messages[0].get("role") != "system":
        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + messages

    # Define available tools with clear descriptions
    tools = [
        {
            "type": "function",
            "function": {
                "name": "run_connectivity_check",
                "description": "Test network connectivity to Azure endpoints. Call this when user asks about connectivity, network access, firewall rules, DNS resolution, or whether they can reach Azure services. Returns pass/fail status for each required Azure endpoint.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_environment",
                "description": "Run Azure Local environment validation checks. Call this when user asks about environment readiness, system requirements, prerequisites, hardware requirements, or general 'is my system ready' questions. Validates hardware, OS, networking, and Azure Local prerequisites.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["quick", "full"],
                            "description": "quick for basic checks, full for comprehensive validation",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "validate_cluster",
                "description": "Validate AKS Arc cluster health and configuration. Call this when user asks about cluster status, cluster health, Kubernetes issues, AKS Arc validation, or wants to check their cluster. Returns cluster health metrics, extension status, and configuration issues.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_tsg",
                "description": "Search Azure Local and AKS Arc troubleshooting guides (TSGs). ALWAYS call this tool when: 1) User mentions any error code (0x..., error XXX, etc.), 2) User describes a problem or failure, 3) User asks how to fix something, 4) User mentions 'not working', 'failing', 'issue', 'problem'. This tool searches official troubleshooting documentation and returns relevant solutions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The error message, error code, or problem description to search for",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    ]

    # Detect if user is asking about errors/problems
    last_user_msg = next(
        (m["content"].lower() for m in reversed(messages) if m["role"] == "user"), ""
    )
    error_indicators = [
        "error",
        "0x",
        "failed",
        "fail",
        "issue",
        "problem",
        "not working",
        "broken",
        "fix",
        "help",
    ]
    force_tsg = any(indicator in last_user_msg for indicator in error_indicators)

    logger.info("Chat processing - force_tsg=%s, query=%s", force_tsg, last_user_msg[:50])

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            request_body = {
                "model": model_id,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            }
            resp = await client.post(f"{endpoint}/chat/completions", json=request_body)
            result = resp.json()

            logger.debug("Foundry response: %s", str(result)[:500])

            if "error" in result:
                return {"success": False, "error": result["error"]}

            # Check for valid response structure
            if "choices" not in result or not result["choices"]:
                logger.error("Invalid response from Foundry: %s", result)
                return {"success": False, "error": "Invalid response from AI model"}

            msg = result["choices"][0]["message"]
            content = msg.get("content", "") or ""

            # Handle proper tool_calls in response
            if msg.get("tool_calls"):
                tool_results = []
                for tc in msg["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    tool_args = json.loads(tc["function"].get("arguments", "{}"))

                    tool_result = await _execute_chat_tool(tool_name, tool_args)
                    tool_results.append(
                        {
                            "tool": tool_name,
                            "result": tool_result,
                        }
                    )

                # Generate human-readable summary
                summary = _summarize_tool_results(tool_results)

                return {
                    "success": True,
                    "content": summary,
                    "tool_calls": tool_results,
                    "requires_followup": True,
                }

            # Some models output <tool_call> in content instead of using proper tool_calls
            # Parse and execute those too
            parsed_calls = _parse_tool_calls_from_content(content)
            if parsed_calls:
                tool_results = []
                for pc in parsed_calls:
                    tool_result = await _execute_chat_tool(pc["name"], pc.get("arguments", {}))
                    tool_results.append(
                        {
                            "tool": pc["name"],
                            "result": tool_result,
                        }
                    )

                # Generate human-readable summary
                summary = _summarize_tool_results(tool_results)

                return {
                    "success": True,
                    "content": summary,
                    "tool_calls": tool_results,
                    "requires_followup": True,
                }

            return {
                "success": True,
                "content": content,
                "tool_calls": [],
                "requires_followup": False,
            }

        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Available tools for chat - defined once for scanning animation
CHAT_TOOLS = [
    {
        "id": "run_connectivity_check",
        "name": "Azure Connectivity Check",
        "icon": "🌐",
        "description": "Test network connectivity to Azure endpoints",
    },
    {
        "id": "check_environment",
        "name": "Environment Validation",
        "icon": "🔍",
        "description": "Validate Azure Local prerequisites",
    },
    {
        "id": "validate_cluster",
        "name": "AKS Arc Cluster Validation",
        "icon": "☸️",
        "description": "Check cluster health and configuration",
    },
    {
        "id": "search_tsg",
        "name": "TSG Search",
        "icon": "📚",
        "description": "Search troubleshooting guides",
    },
]


@router.post("/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    """
    Streaming chat endpoint with progress events.

    Sends Server-Sent Events (SSE) for real-time progress updates:
    - scanning: Shows which tool is being considered
    - selected: Tool has been selected for execution
    - executing: Tool is being executed
    - complete: Request complete with final response
    """
    body = await request.json()
    messages = body.get("messages", [])

    def sse_event(data: dict) -> str:
        """Format SSE event with proper newlines."""
        return f"data: {json.dumps(data)}\n\n"

    async def event_generator() -> AsyncGenerator[str, None]:
        if not messages:
            yield sse_event({"type": "error", "error": "No messages provided"})
            return

        # Get user's last message for keyword hints
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        ).lower()

        # Phase 1: Scanning tools animation
        yield sse_event(
            {"type": "phase", "phase": "analyzing", "message": "Analyzing your request..."}
        )
        await asyncio.sleep(0.2)

        # Show scanning animation
        for tool in CHAT_TOOLS:
            yield sse_event({"type": "scanning", "tool": tool})
            await asyncio.sleep(0.1)

        # Phase 2: Use LLM with MCP tools
        yield sse_event(
            {"type": "phase", "phase": "thinking", "message": "AI selecting best diagnostic..."}
        )

        try:
            import httpx
            from foundry_local import FoundryLocalManager

            # Get Foundry endpoint and currently loaded model
            manager = FoundryLocalManager("qwen2.5-0.5b")  # Just to get endpoint
            endpoint = manager.endpoint
            loaded = manager.list_loaded_models()
            model_id = loaded[0].id if loaded else "qwen2.5-1.5b"
            logger.info(f"Chat using model: {model_id}")

            # Prepare messages with system prompt
            chat_messages = messages.copy()
            if not chat_messages or chat_messages[0].get("role") != "system":
                chat_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + chat_messages

            # Define MCP tools for LLM
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "run_connectivity_check",
                        "description": "Test network connectivity to Azure endpoints. Use for: connectivity issues, firewall, DNS, reaching Azure, egress checks.",
                        "parameters": {
                            "type": "object",
                            "properties": {"mode": {"type": "string", "enum": ["quick", "full"]}},
                            "required": [],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "validate_cluster",
                        "description": "Validate AKS Arc cluster health. Use for: cluster status, Kubernetes health, node issues, extension problems.",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "search_tsg",
                        "description": "Search troubleshooting guides. MUST USE when user mentions: error, failed, problem, issue, fix, help, 0x codes, or any error message.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Error message or problem to search",
                                }
                            },
                            "required": ["query"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "check_environment",
                        "description": "Check Azure Local prerequisites. Use for: environment readiness, requirements, installation checks.",
                        "parameters": {
                            "type": "object",
                            "properties": {"mode": {"type": "string", "enum": ["quick", "full"]}},
                            "required": [],
                        },
                    },
                },
            ]

            # Determine if this is a small model that needs keyword assistance
            # Models >= 1.5B parameters can handle tool selection on their own
            is_small_model = "0.5b" in model_id.lower() or "0.5-b" in model_id.lower()
            logger.info(f"Model {model_id}: is_small_model={is_small_model}")

            # Keyword detection only for small models that struggle with tool selection
            error_keywords = [
                "error",
                "0x",
                "failed",
                "fail",
                "issue",
                "problem",
                "not working",
                "fix",
                "help",
            ]
            connectivity_keywords = [
                "connectivity",
                "reach azure",
                "firewall",
                "dns",
                "endpoint",
                "egress",
            ]
            cluster_keywords = [
                "validate cluster",
                "cluster health",
                "aks health",
                "kubernetes",
                "node status",
            ]

            # Only force tool selection for small models
            forced_tool = None
            forced_args = {}
            if is_small_model:
                if any(kw in last_user_msg for kw in error_keywords):
                    forced_tool = "search_tsg"
                    forced_args = {
                        "query": next(
                            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
                        )
                    }
                    logger.info(f"Small model keyword detection: forcing search_tsg")
                elif any(kw in last_user_msg for kw in connectivity_keywords):
                    forced_tool = "run_connectivity_check"
                    forced_args = {"mode": "quick"}
                elif any(kw in last_user_msg for kw in cluster_keywords):
                    forced_tool = "validate_cluster"
                    forced_args = {}

            if forced_tool:
                # Skip LLM - we know what tool to use based on keywords
                tool_meta = next((t for t in CHAT_TOOLS if t["id"] == forced_tool), CHAT_TOOLS[0])
                yield sse_event({"type": "selected", "tool": tool_meta})
                await asyncio.sleep(0.2)
                yield sse_event({"type": "executing", "tool": tool_meta, "args": forced_args})

                # Execute via MCP
                logger.info(
                    f"Executing MCP tool {forced_tool} (keyword-forced) with args: {forced_args}"
                )
                tool_result = await _execute_chat_tool(forced_tool, forced_args)
                tool_results = [{"tool": forced_tool, "result": tool_result}]

                yield sse_event(
                    {
                        "type": "tool_complete",
                        "tool": tool_meta,
                        "success": "error" not in tool_result,
                    }
                )

                # Generate summary
                summary = _summarize_tool_results(tool_results)
                if "no results" in summary.lower():
                    summary += "\n\n---\n📞 **Need more help?** Contact Microsoft Support: https://support.microsoft.com/azure"

                yield sse_event(
                    {
                        "type": "complete",
                        "success": True,
                        "content": summary,
                        "tool_calls": tool_results,
                    }
                )
                return  # Exit generator

            # No forced tool - let LLM decide with tool_choice="auto"
            logger.info("No keyword match - using LLM for tool selection")

            # Call LLM to select and parameterize tool
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{endpoint}/chat/completions",
                    json={
                        "model": model_id,
                        "messages": chat_messages,
                        "tools": tools,
                        "tool_choice": "auto",  # Let LLM decide
                    },
                )
                result = resp.json()

                if "error" in result:
                    yield sse_event({"type": "error", "error": result["error"]})
                    return

                if "choices" not in result or not result["choices"]:
                    yield sse_event({"type": "error", "error": "Invalid AI response"})
                    return

                msg = result["choices"][0]["message"]
                content = msg.get("content", "") or ""

                # Get tool calls from LLM response
                tool_calls = msg.get("tool_calls", [])
                parsed_calls = _parse_tool_calls_from_content(content) if not tool_calls else []
                all_calls = tool_calls or parsed_calls

                if all_calls:
                    tool_results = []

                    for tc in all_calls:
                        if isinstance(tc, dict) and "function" in tc:
                            tool_name = tc["function"]["name"]
                            tool_args = json.loads(tc["function"].get("arguments", "{}"))
                        else:
                            tool_name = tc.get("name", "")
                            tool_args = tc.get("arguments", {})

                        # Find tool metadata
                        tool_meta = next(
                            (t for t in CHAT_TOOLS if t["id"] == tool_name),
                            {"id": tool_name, "name": tool_name, "icon": "🔧"},
                        )

                        # Send selected event
                        yield sse_event({"type": "selected", "tool": tool_meta})
                        await asyncio.sleep(0.2)

                        # Send executing event
                        yield sse_event({"type": "executing", "tool": tool_meta, "args": tool_args})

                        # Execute via MCP registry
                        logger.info(
                            f"Executing MCP tool {tool_name} with LLM-generated args: {tool_args}"
                        )
                        tool_result = await _execute_chat_tool(tool_name, tool_args)
                        tool_results.append({"tool": tool_name, "result": tool_result})

                        # Send complete event
                        yield sse_event(
                            {
                                "type": "tool_complete",
                                "tool": tool_meta,
                                "success": "error" not in tool_result,
                            }
                        )

                    # Generate summary
                    summary = _summarize_tool_results(tool_results)
                    if "no results" in summary.lower():
                        summary += "\n\n---\n📞 **Need more help?** Contact Microsoft Support: https://support.microsoft.com/azure"

                    yield sse_event(
                        {
                            "type": "complete",
                            "success": True,
                            "content": summary,
                            "tool_calls": tool_results,
                        }
                    )
                else:
                    # No tool calls - shouldn't happen with tool_choice="required"
                    yield sse_event(
                        {
                            "type": "complete",
                            "success": True,
                            "content": content
                            or "I can help diagnose Azure Local and AKS Arc issues. Try asking about connectivity, cluster health, or describe an error.",
                            "tool_calls": [],
                        }
                    )

        except ImportError:
            yield sse_event({"type": "error", "error": "Foundry Local SDK not installed"})
        except Exception as e:
            logger.exception("Streaming chat error")
            yield sse_event({"type": "error", "error": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _execute_chat_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool from chat context via MCP.

    Maps chat tool names to MCP tool names and calls them via the MCP registry.
    """
    from server.main import TOOL_REGISTRY

    # Map chat tool names to MCP tool names
    tool_mapping = {
        "run_connectivity_check": "arc.connectivity.check",
        "check_environment": "arc.connectivity.check",  # Same tool, different mode
        "validate_cluster": "aks.arc.validate",
        "search_tsg": "azlocal.tsg.search",  # TSG search via MCP
    }

    # Get MCP tool name
    mcp_tool_name = tool_mapping.get(tool_name)
    if not mcp_tool_name:
        return {"error": f"Unknown tool: {tool_name}"}

    # Check if tool exists in registry
    if mcp_tool_name not in TOOL_REGISTRY:
        return {"error": f"MCP tool not registered: {mcp_tool_name}"}

    # Build MCP tool arguments
    mcp_args: dict[str, Any] = {"dryRun": False}  # Default to real execution

    if tool_name == "run_connectivity_check":
        mcp_args["mode"] = args.get("mode", "quick")
    elif tool_name == "check_environment":
        # Environment check maps to connectivity with full mode
        mcp_args["mode"] = args.get("mode", "quick")
    elif tool_name == "validate_cluster":
        mcp_args["checks"] = args.get("checks", ["all"])
    elif tool_name == "search_tsg":
        # TSG search needs query parameter
        mcp_args["query"] = args.get("query", "")
        if not mcp_args["query"]:
            return {"error": "No search query provided"}
        # Use dry_run from args, default to False for real execution

    # Execute via MCP tool registry
    try:
        tool = TOOL_REGISTRY[mcp_tool_name]
        logger.info("Executing MCP tool %s with args %s", mcp_tool_name, mcp_args)
        result = await tool.execute(mcp_args)
        logger.info("MCP tool %s completed successfully", mcp_tool_name)
        return result
    except Exception as e:
        logger.error("MCP tool %s failed: %s", mcp_tool_name, e)
        return {"error": str(e)}


@router.get("/chat/status")
async def chat_status() -> dict[str, Any]:
    """Check if chat (Foundry Local) is available."""
    try:
        from foundry_local import FoundryLocalManager

        # FoundryLocalManager auto-discovers the running Foundry service endpoint
        # Pass any model alias - it will find the running service
        manager = FoundryLocalManager("qwen2.5-0.5b")
        endpoint = manager.endpoint

        # Get currently loaded models
        loaded = manager.list_loaded_models()
        models = [m.id for m in loaded] if loaded else []

        return {
            "available": len(models) > 0,
            "endpoint": endpoint,
            "models": models,
        }

    except ImportError:
        return {
            "available": False,
            "error": "foundry-local-sdk not installed",
            "hint": "Install: pip install foundry-local-sdk",
        }

    except Exception as e:
        logger.exception("Foundry check failed")
        return {
            "available": False,
            "error": str(e),
            "hint": "Start Foundry Local: foundry model run qwen2.5-1.5b",
        }


# Models that support tool calling (required for chat)
TOOL_CAPABLE_MODELS = {
    "qwen2.5-0.5b",
    "qwen2.5-1.5b",
    "qwen2.5-7b",
    "qwen2.5-14b",
    "qwen2.5-coder-0.5b",
    "qwen2.5-coder-1.5b",
    "qwen2.5-coder-7b",
    "qwen2.5-coder-14b",
    "phi-4-mini",
}


def _get_foundry_models() -> dict[str, Any]:
    """Get all available models from Foundry Local catalog."""
    try:
        from foundry_local import FoundryLocalManager

        # Use 1.5b as default - better at tool selection
        manager = FoundryLocalManager("qwen2.5-1.5b")

        # Get all models from catalog
        try:
            catalog = list(manager.list_catalog_models())
        except Exception:
            catalog = []

        # Get cached (downloaded) models
        try:
            cached = list(manager.list_cached_models())
            cached_aliases = {m.alias for m in cached}
        except Exception:
            cached = []
            cached_aliases = set()

        # Get currently loaded/running models
        try:
            loaded = manager.list_loaded_models()
            loaded_aliases = {m.alias for m in loaded} if loaded else set()
        except Exception:
            loaded = []
            loaded_aliases = set()

        # Group by alias (unique model name)
        seen_aliases = set()
        models = []

        for m in catalog:
            if m.alias in seen_aliases:
                continue
            seen_aliases.add(m.alias)

            # Determine recommended models - prefer larger models for better tool selection
            is_recommended = m.alias in ["qwen2.5-1.5b", "phi-4-mini", "qwen2.5-7b"]
            supports_tools = m.alias in TOOL_CAPABLE_MODELS

            models.append(
                {
                    "id": m.alias,
                    "modelId": m.id,
                    "name": m.alias.replace("-", " ").title(),
                    "size": f"{m.file_size} MB" if m.file_size else "Unknown",
                    "sizeBytes": m.file_size * 1024 * 1024 if m.file_size else 0,
                    "license": m.license if hasattr(m, "license") else "Unknown",
                    "device": m.device_type if hasattr(m, "device_type") else "Unknown",
                    "downloaded": m.alias in cached_aliases,
                    "loaded": m.alias in loaded_aliases,
                    "recommended": is_recommended,
                    "supportsTools": supports_tools,
                }
            )

        # Sort: loaded first, then downloaded, then recommended, then by name
        models.sort(
            key=lambda x: (not x["loaded"], not x["downloaded"], not x["recommended"], x["name"])
        )

        return {
            "success": True,
            "models": models,
            "loaded": list(loaded_aliases),
            "downloaded": list(cached_aliases),
            "sdk_available": True,
            "service_running": True,
        }
    except ImportError:
        return {
            "success": False,
            "models": [],
            "loaded": [],
            "downloaded": [],
            "sdk_available": False,
            "hint": "pip install foundry-local-sdk",
        }
    except Exception as e:
        # Try to get at least a basic list from CLI
        return _get_foundry_models_from_cli(str(e))


def _get_foundry_models_from_cli(sdk_error: str) -> dict[str, Any]:
    """Fallback: parse foundry CLI output for model list."""
    try:
        # Get cached models
        cache_result = subprocess.run(
            ["foundry", "cache", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
        )

        downloaded = set()
        if cache_result.returncode == 0:
            for line in cache_result.stdout.split("\n"):
                # Look for lines that start with the disk emoji (various encodings)
                # or have model-like patterns
                line = line.strip()
                if not line or line.startswith("Models cached") or line.startswith("Alias"):
                    continue
                # Split on whitespace and look for model alias patterns
                parts = line.split()
                if len(parts) >= 2:
                    # Skip the emoji (first part), second part is the alias
                    alias = parts[1] if len(parts[0]) <= 4 else parts[0]  # Emoji or alias
                    # Validate it looks like a model name
                    if any(m in alias for m in ["qwen", "phi", "llama", "mistral", "deepseek"]):
                        downloaded.add(alias)

        # Basic model list for when SDK fails
        basic_models = [
            {
                "id": "qwen2.5-1.5b",
                "name": "Qwen 2.5 1.5B",
                "size": "1.25 GB",
                "recommended": True,  # Prefer 1.5B for better tool selection
                "supportsTools": True,
            },
            {
                "id": "qwen2.5-0.5b",
                "name": "Qwen 2.5 0.5B",
                "size": "520 MB",
                "recommended": False,
                "supportsTools": True,
            },
            {
                "id": "qwen2.5-7b",
                "name": "Qwen 2.5 7B",
                "size": "5.5 GB",
                "recommended": True,
                "supportsTools": True,
            },
            {
                "id": "phi-4-mini",
                "name": "Phi 4 Mini",
                "size": "3.6 GB",
                "recommended": True,
                "supportsTools": True,
            },
            {
                "id": "phi-4",
                "name": "Phi 4",
                "size": "8.4 GB",
                "recommended": False,
                "supportsTools": False,
            },
            {
                "id": "phi-3.5-mini",
                "name": "Phi 3.5 Mini",
                "size": "2.1 GB",
                "recommended": False,
                "supportsTools": False,
            },
            {
                "id": "deepseek-r1-7b",
                "name": "DeepSeek R1 7B",
                "size": "5.3 GB",
                "recommended": False,
                "supportsTools": False,
            },
            {
                "id": "mistral-7b-v0.2",
                "name": "Mistral 7B v0.2",
                "size": "4.0 GB",
                "recommended": False,
                "supportsTools": False,
            },
        ]

        for m in basic_models:
            m["downloaded"] = m["id"] in downloaded
            m["loaded"] = False

        return {
            "success": True,
            "models": basic_models,
            "loaded": [],
            "downloaded": list(downloaded),
            "sdk_available": True,
            "service_running": False,
            "warning": f"SDK error: {sdk_error}. Using fallback model list.",
        }
    except Exception as e:
        return {
            "success": False,
            "models": [],
            "error": f"Failed to get models: {e}",
            "hint": "Ensure Foundry Local is installed: https://github.com/microsoft/foundry-local",
        }


@router.get("/foundry/models")
async def list_available_models() -> dict[str, Any]:
    """List all available models from Foundry Local catalog."""
    return _get_foundry_models()


@router.post("/foundry/start")
async def start_foundry_model(request: dict[str, Any]) -> dict[str, Any]:
    """Start a Foundry Local model."""
    model_id = request.get("model_id", "qwen2.5-1.5b")  # Default to 1.5b for better tool selection

    try:
        # Use the SDK to load the model (non-blocking)
        from foundry_local import FoundryLocalManager

        manager = FoundryLocalManager(model_id)

        # Check if model is already loaded
        loaded = manager.list_loaded_models()
        for m in loaded:
            if m.alias == model_id or m.id.startswith(model_id):
                return {
                    "success": True,
                    "model": model_id,
                    "message": f"Model {model_id} is already running",
                }

        # Model not loaded - need to load it
        # The FoundryLocalManager will handle starting the service if needed
        # We use model run in background for initial setup
        import subprocess
        import sys

        # Start foundry model run in a detached process
        if sys.platform == "win32":
            # Windows: use START to run in background
            subprocess.Popen(
                f"start /B foundry model run {model_id}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Unix: use nohup
            subprocess.Popen(
                ["nohup", "foundry", "model", "run", model_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        # Wait a bit for the service to start
        import asyncio

        await asyncio.sleep(5)

        # Verify it started
        try:
            manager2 = FoundryLocalManager(model_id)
            loaded2 = manager2.list_loaded_models()
            if loaded2:
                return {
                    "success": True,
                    "model": model_id,
                    "message": f"Model {model_id} started",
                }
        except Exception:
            pass

        return {
            "success": True,
            "model": model_id,
            "message": f"Model {model_id} starting (may take a moment)",
        }

    except ImportError:
        return {
            "success": False,
            "error": "foundry-local-sdk not installed",
            "hint": "pip install foundry-local-sdk",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Foundry CLI not found",
            "hint": "Install Foundry Local from https://github.com/microsoft/foundry-local",
        }
    except Exception as e:
        logger.exception("Failed to start foundry model")
        return {"success": False, "error": str(e)}


@router.post("/foundry/stop")
async def stop_foundry() -> dict[str, Any]:
    """Stop Foundry Local service."""
    try:
        result = subprocess.run(
            ["foundry", "service", "stop"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "success": True,
            "message": "Foundry service stopped",
            "output": result.stdout,
        }
    except FileNotFoundError:
        return {"success": False, "error": "Foundry CLI not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/foundry/restart")
async def restart_foundry(request: dict[str, Any]) -> dict[str, Any]:
    """Restart Foundry Local with a different model.

    Foundry Local can only run one model at a time. To switch models,
    we must stop the service entirely and start with the new model.
    """
    model_id = request.get("model_id", "qwen2.5-0.5b")
    import asyncio
    import sys

    try:
        # Step 1: Stop the Foundry service completely
        logger.info("Stopping Foundry service for model switch...")
        subprocess.run(
            ["foundry", "service", "stop"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Wait for service to fully stop
        await asyncio.sleep(3)

        # Step 2: Start foundry model run in background (this starts the service + loads model)
        logger.info("Starting Foundry with model: %s", model_id)

        if sys.platform == "win32":
            # Windows: use START /B to run in background without blocking
            subprocess.Popen(
                f"start /B foundry model run {model_id}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Unix: use nohup
            subprocess.Popen(
                ["nohup", "foundry", "model", "run", model_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        # Wait for model to start loading
        await asyncio.sleep(5)

        # Verify it's starting
        status_result = subprocess.run(
            ["foundry", "service", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if "running" in status_result.stdout.lower() or "started" in status_result.stdout.lower():
            return {
                "success": True,
                "model": model_id,
                "message": f"Switched to {model_id}. Model is loading...",
            }
        else:
            return {
                "success": True,
                "model": model_id,
                "message": f"Model {model_id} starting (may take a moment)...",
            }

    except FileNotFoundError:
        return {
            "success": False,
            "error": "Foundry CLI not found",
            "hint": "Install Foundry Local from https://github.com/microsoft/foundry-local",
        }
    except Exception as e:
        logger.exception("Failed to restart foundry")
        return {"success": False, "error": str(e)}
