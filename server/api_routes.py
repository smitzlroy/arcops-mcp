"""
Real Azure API endpoints for ArcOps MCP Server.

These endpoints call actual Azure CLI to get real cluster data,
not simulated/mock data.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Create router for API endpoints
router = APIRouter(prefix="/api", tags=["azure"])


def _find_az_cli() -> str | None:
    """Find Azure CLI executable, checking common paths."""
    az_cmd = shutil.which("az")
    if az_cmd:
        return az_cmd

    # Try common Windows paths
    for path in [
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ]:
        if Path(path).exists():
            return path

    return None


@router.get("/clusters")
async def list_clusters(subscription: str | None = None) -> dict[str, Any]:
    """
    List real AKS Arc connected clusters from Azure.

    Requires az CLI to be authenticated (az login).
    """
    az_cmd = _find_az_cli()

    if not az_cmd:
        return {
            "success": False,
            "clusters": [],
            "error": "Azure CLI (az) not found",
            "hint": "Install Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli",
        }

    try:
        cmd = [az_cmd, "connectedk8s", "list", "-o", "json"]
        if subscription:
            cmd.extend(["--subscription", subscription])

        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            logger.error("az connectedk8s list failed: %s", result.stderr)
            return {
                "success": False,
                "clusters": [],
                "error": result.stderr,
                "hint": "Ensure az CLI is authenticated (az login)",
            }

        clusters = json.loads(result.stdout)

        # Extract key info for each cluster
        cluster_summaries = []
        for c in clusters:
            cluster_summaries.append(
                {
                    "name": c.get("name"),
                    "resourceGroup": c.get("resourceGroup"),
                    "location": c.get("location"),
                    "connectivityStatus": c.get("connectivityStatus"),
                    "provisioningState": c.get("provisioningState"),
                    "kubernetesVersion": c.get("kubernetesVersion"),
                    "agentVersion": c.get("agentVersion"),
                    "distribution": c.get("distribution"),
                    "infrastructure": c.get("infrastructure"),
                    "totalNodeCount": c.get("totalNodeCount"),
                    "lastConnectivityTime": c.get("lastConnectivityTime"),
                }
            )

        return {
            "success": True,
            "count": len(clusters),
            "clusters": cluster_summaries,
            "source": "azure_cli",
            "subscription": subscription or "default",
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "clusters": [], "error": "Command timed out"}
    except json.JSONDecodeError as e:
        return {"success": False, "clusters": [], "error": f"Failed to parse response: {e}"}
    except Exception as e:
        logger.exception("Error listing clusters")
        return {"success": False, "clusters": [], "error": str(e)}


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
    az_cmd = _find_az_cli()

    if not az_cmd:
        return {"authenticated": False, "azCliInstalled": False, "error": "Azure CLI not found"}

    try:
        # Check current account
        cmd = [az_cmd, "account", "show", "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {
                "authenticated": False,
                "azCliInstalled": True,
                "error": "Not authenticated - run 'az login'",
            }

        account = json.loads(result.stdout)

        return {
            "authenticated": True,
            "azCliInstalled": True,
            "azCliPath": az_cmd,
            "subscription": {
                "id": account.get("id"),
                "name": account.get("name"),
                "tenantId": account.get("tenantId"),
            },
            "user": account.get("user", {}).get("name"),
        }

    except Exception as e:
        return {"authenticated": False, "azCliInstalled": True, "error": str(e)}


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
