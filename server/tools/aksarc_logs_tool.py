"""
AKS Arc Log Collection Tool - Wrapper for az aksarc get-logs.

Thin wrapper that exposes the az aksarc get-logs command via MCP.
Collects diagnostic logs from AKS Arc cluster nodes.

References:
- https://learn.microsoft.com/en-us/azure/aks/aksarc/get-on-demand-logs
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Coroutine

from server.tools.base import BaseTool

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class AksArcLogsTool(BaseTool):
    """
    Wrapper for az aksarc get-logs.

    Collects diagnostic logs from AKS Arc cluster nodes.
    Requires SSH credentials from cluster creation.
    """

    name = "aksarc.logs.collect"
    description = "Collect diagnostic logs from AKS Arc cluster using az aksarc get-logs."
    input_schema = {
        "type": "object",
        "properties": {
            "ip": {
                "type": "string",
                "description": "Node IP address for single node collection",
            },
            "kubeconfig": {
                "type": "string",
                "description": "Path to kubeconfig file for all-nodes collection",
            },
            "credentialsDir": {
                "type": "string",
                "description": "Path to directory containing SSH keys",
            },
            "outDir": {
                "type": "string",
                "default": "./logs",
                "description": "Output directory for collected logs",
            },
            "dryRun": {
                "type": "boolean",
                "default": False,
                "description": "Validate prerequisites without collecting logs",
            },
        },
    }

    async def execute(
        self,
        arguments: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Execute log collection."""
        ip = arguments.get("ip")
        kubeconfig = arguments.get("kubeconfig")
        credentials_dir = arguments.get("credentialsDir")
        out_dir = arguments.get("outDir", "./logs")
        dry_run = arguments.get("dryRun", False)

        start_time = time.time()

        # Validate inputs
        if not ip and not kubeconfig:
            return {
                "success": False,
                "error": "Either 'ip' or 'kubeconfig' is required",
                "hint": "Provide node IP for single node, or kubeconfig path for all nodes",
            }

        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Checking prerequisites...",
                    "phase": "detect",
                }
            )

        # Check if az aksarc extension is available
        cli_info = self._check_az_aksarc_available()

        if dry_run:
            return await self._run_dry_run(
                ip, kubeconfig, credentials_dir, out_dir, cli_info, progress_callback
            )

        if not cli_info["available"]:
            return {
                "success": False,
                "error": "az aksarc CLI extension not available",
                "hint": cli_info.get("hint", "Install Azure CLI and aksarc extension"),
                "cli": cli_info,
            }

        # Run actual log collection
        return await self._run_log_collection(
            ip, kubeconfig, credentials_dir, out_dir, start_time, progress_callback
        )

    def _check_az_aksarc_available(self) -> dict[str, Any]:
        """Check if az CLI with aksarc extension is available."""
        # Find az CLI
        az_cmd = shutil.which("az")
        if not az_cmd:
            # Check common Windows paths
            for path in [
                r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
                r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
            ]:
                if Path(path).exists():
                    az_cmd = path
                    break

        if not az_cmd:
            return {
                "available": False,
                "azCli": False,
                "hint": "Install Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli",
            }

        # Check if aksarc extension is installed
        try:
            result = subprocess.run(
                [az_cmd, "extension", "show", "--name", "aksarc", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                try:
                    ext_info = json.loads(result.stdout)
                    return {
                        "available": True,
                        "azCli": True,
                        "azPath": az_cmd,
                        "extensionVersion": ext_info.get("version"),
                    }
                except json.JSONDecodeError:
                    pass

            return {
                "available": False,
                "azCli": True,
                "azPath": az_cmd,
                "hint": "Install aksarc extension: az extension add --name aksarc",
            }

        except Exception as e:
            logger.debug("Failed to check aksarc extension: %s", e)
            return {
                "available": False,
                "azCli": True,
                "azPath": az_cmd,
                "error": str(e),
            }

    async def _run_log_collection(
        self,
        ip: str | None,
        kubeconfig: str | None,
        credentials_dir: str | None,
        out_dir: str,
        start_time: float,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Run az aksarc get-logs command."""
        az_cmd = shutil.which("az") or r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"

        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Collecting logs from cluster nodes...",
                    "phase": "collect",
                }
            )

        # Build command
        cmd = [az_cmd, "aksarc", "get-logs"]

        if ip:
            cmd.extend(["--ip", ip])
        elif kubeconfig:
            cmd.extend(["--kubeconfig", kubeconfig])

        if credentials_dir:
            cmd.extend(["--credentials-dir", credentials_dir])

        cmd.extend(["--out-dir", out_dir])

        logger.info("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes for log collection
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.returncode == 0:
                # Find the output file
                out_path = Path(out_dir)
                log_files = list(out_path.glob("*.tar.gz")) + list(out_path.glob("*.zip"))

                if progress_callback:
                    await progress_callback(
                        {
                            "type": "complete",
                            "message": "Log collection complete",
                        }
                    )

                return {
                    "success": True,
                    "outDir": out_dir,
                    "logFiles": [str(f) for f in log_files],
                    "stdout": result.stdout[:2000] if result.stdout else None,
                    "durationMs": duration_ms,
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr[:2000] if result.stderr else "Log collection failed",
                    "returnCode": result.returncode,
                    "durationMs": duration_ms,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Log collection timed out after 10 minutes",
                "hint": "Check network connectivity to cluster nodes",
            }
        except Exception as e:
            logger.exception("Unexpected error during log collection")
            return {
                "success": False,
                "error": str(e),
            }

    async def _run_dry_run(
        self,
        ip: str | None,
        kubeconfig: str | None,
        credentials_dir: str | None,
        out_dir: str,
        cli_info: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Validate prerequisites without collecting logs."""
        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Validating prerequisites (dry run)...",
                    "phase": "dry-run",
                }
            )

        issues = []
        warnings = []

        # Check CLI
        if not cli_info["available"]:
            issues.append(
                {
                    "check": "az aksarc extension",
                    "status": "fail",
                    "message": cli_info.get("hint", "Extension not available"),
                }
            )
        else:
            warnings.append(
                {
                    "check": "az aksarc extension",
                    "status": "pass",
                    "version": cli_info.get("extensionVersion"),
                }
            )

        # Check credentials directory
        if credentials_dir:
            creds_path = Path(credentials_dir)
            if not creds_path.exists():
                issues.append(
                    {
                        "check": "credentials directory",
                        "status": "fail",
                        "message": f"Directory not found: {credentials_dir}",
                    }
                )
            else:
                # Check for SSH keys
                key_files = list(creds_path.glob("*.pem")) + list(creds_path.glob("id_*"))
                if not key_files:
                    warnings.append(
                        {
                            "check": "SSH keys",
                            "status": "warn",
                            "message": "No SSH key files found in credentials directory",
                        }
                    )
                else:
                    warnings.append(
                        {
                            "check": "SSH keys",
                            "status": "pass",
                            "keyCount": len(key_files),
                        }
                    )

        # Check kubeconfig
        if kubeconfig:
            kube_path = Path(kubeconfig)
            if not kube_path.exists():
                issues.append(
                    {
                        "check": "kubeconfig",
                        "status": "fail",
                        "message": f"File not found: {kubeconfig}",
                    }
                )
            else:
                warnings.append(
                    {
                        "check": "kubeconfig",
                        "status": "pass",
                        "path": kubeconfig,
                    }
                )

        # Check output directory
        out_path = Path(out_dir)
        if not out_path.exists():
            warnings.append(
                {
                    "check": "output directory",
                    "status": "info",
                    "message": f"Directory will be created: {out_dir}",
                }
            )

        if progress_callback:
            await progress_callback(
                {
                    "type": "complete",
                    "message": f"Dry run complete: {len(issues)} issues, {len(warnings)} checks",
                }
            )

        return {
            "success": len(issues) == 0,
            "dryRun": True,
            "target": {"ip": ip, "kubeconfig": kubeconfig},
            "credentialsDir": credentials_dir,
            "outDir": out_dir,
            "issues": issues,
            "checks": warnings,
            "cli": cli_info,
            "hint": "Run without dryRun to collect logs" if len(issues) == 0 else None,
        }
