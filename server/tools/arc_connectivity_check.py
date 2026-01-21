"""
Arc Connectivity Check Tool - Unified connectivity validation.

Consolidates environment checking and egress testing into one seamless tool.
Supports auto-installation of the official Microsoft Environment Checker.

References: docs/SOURCES.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import socket
import ssl
import subprocess
import time
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
from typing import Any, Callable, Coroutine

import httpx
import yaml

from server.tools.base import BaseTool

logger = logging.getLogger(__name__)

# Type alias for async progress callback
ProgressCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class ArcConnectivityCheckTool(BaseTool):
    """
    Unified connectivity check for Azure Local and AKS Arc.

    Modes:
    - quick: Key endpoints only (fast, ~10 checks)
    - full: All endpoints + host checks (~50+ checks)
    - endpoints-only: Just FQDN reachability (no host checks)

    Features:
    - Auto-detects Microsoft Environment Checker
    - Falls back to native Python checks if not installed
    - Offers to install Environment Checker if missing
    """

    name = "arc.connectivity.check"
    description = (
        "Unified connectivity check for Azure Local and AKS Arc. "
        "Tests DNS, TLS, and endpoint reachability. "
        "Auto-installs Microsoft Environment Checker if needed."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["quick", "full", "endpoints-only"],
                "default": "quick",
                "description": "Check mode: quick (key endpoints), full (all checks), endpoints-only (just URLs)",
            },
            "installChecker": {
                "type": "boolean",
                "default": False,
                "description": "Auto-install Microsoft Environment Checker if not present",
            },
            "checkerPath": {
                "type": "string",
                "description": "Path to Environment Checker (auto-detected if not specified)",
            },
            "configPath": {
                "type": "string",
                "default": "server/config/endpoints.yaml",
                "description": "Path to endpoints configuration",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter endpoints by category (azure-arc, aks-arc, monitoring)",
            },
            "timeoutSec": {
                "type": "integer",
                "default": 10,
                "description": "Timeout for each endpoint check",
            },
            "dryRun": {
                "type": "boolean",
                "default": False,
                "description": "Simulate checks using fixture data",
            },
        },
    }

    # Official Environment Checker paths
    CHECKER_PATHS = [
        r"C:\Program Files\WindowsPowerShell\Modules\AzStackHci.EnvironmentChecker\AzStackHci.EnvironmentChecker.psd1",
        r"C:\Program Files\PowerShell\Modules\AzStackHci.EnvironmentChecker\AzStackHci.EnvironmentChecker.psd1",
    ]

    # Key endpoints for quick mode
    KEY_ENDPOINTS = [
        "management.azure.com",
        "login.microsoftonline.com",
        "mcr.microsoft.com",
        "gbl.his.arc.azure.com",
    ]

    async def execute(
        self,
        arguments: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Execute connectivity checks.

        Args:
            arguments: Tool arguments
            progress_callback: Optional async callback for streaming progress updates.
                              Called with dict containing 'type', 'message', etc.
        """
        mode = arguments.get("mode", "quick")
        install_checker = arguments.get("installChecker", False)
        checker_path = arguments.get("checkerPath")
        config_path = arguments.get("configPath", "server/config/endpoints.yaml")
        categories = arguments.get("categories")
        timeout_sec = arguments.get("timeoutSec", 10)
        dry_run = arguments.get("dryRun", False)

        run_id = self.generate_run_id()
        findings = self.create_findings_base(
            target="connectivity",
            run_id=run_id,
            tool_name=self.name,
            mode=mode,
        )

        start_time = time.time()

        # Step 1: Check for Environment Checker
        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Detecting Microsoft Environment Checker...",
                    "phase": "detect",
                }
            )

        checker_info = await self._detect_environment_checker(checker_path)
        findings["metadata"]["environmentChecker"] = checker_info

        # Step 2: Install if requested and not present
        if install_checker and not checker_info["installed"]:
            if progress_callback:
                await progress_callback(
                    {
                        "type": "status",
                        "message": "Installing Microsoft Environment Checker...",
                        "phase": "install",
                    }
                )
            install_result = await self._install_environment_checker()
            findings["metadata"]["installAttempt"] = install_result
            if install_result["success"]:
                checker_info = await self._detect_environment_checker()
                findings["metadata"]["environmentChecker"] = checker_info

        # Step 3: Load endpoints
        endpoints = await self._load_endpoints(config_path, categories, mode)
        findings["metadata"]["endpointCount"] = len(endpoints)

        # Step 4: Run checks - ONLY use official Microsoft Environment Checker
        # We do not reinvent what Microsoft already provides
        if dry_run:
            await self._run_dry_run_checks(findings, endpoints, mode)
        elif checker_info["installed"]:
            # Use official Environment Checker (this is the ONLY real check path)
            await self._run_environment_checker(
                findings, checker_info["path"], mode, progress_callback
            )
        else:
            # Environment Checker not installed - cannot run checks
            self.add_check(
                findings,
                check_id="arc.connectivity.checker.required",
                title="Microsoft Environment Checker Required",
                severity="high",
                status="fail",
                evidence={
                    "installed": False,
                    "searchedPaths": self.CHECKER_PATHS,
                },
                hint=(
                    "Microsoft Environment Checker is required for connectivity checks. "
                    "Install with: Install-Module -Name AzStackHci.EnvironmentChecker -Force "
                    "Or use the 'Install Now' button in the UI."
                ),
                sources=[
                    self.get_source_ref("azure-local-environment-checker", "Environment Checker")
                ],
            )

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        findings["metadata"]["totalDurationMs"] = duration_ms

        return findings

    async def _detect_environment_checker(self, custom_path: str | None = None) -> dict[str, Any]:
        """Detect if Microsoft Environment Checker is installed."""
        # Check custom path first
        if custom_path and Path(custom_path).exists():
            return {
                "installed": True,
                "path": custom_path,
                "source": "custom",
            }

        # Check environment variable
        env_path = os.environ.get("ENVCHECKER_PATH")
        if env_path and Path(env_path).exists():
            return {
                "installed": True,
                "path": env_path,
                "source": "environment",
            }

        # Check standard paths
        for path in self.CHECKER_PATHS:
            if Path(path).exists():
                return {
                    "installed": True,
                    "path": path,
                    "source": "standard",
                }

        # Check if PowerShell module is available
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "Get-Module -ListAvailable AzStackHci.EnvironmentChecker | Select-Object -ExpandProperty Path",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return {
                    "installed": True,
                    "path": result.stdout.strip(),
                    "source": "powershell-module",
                }
        except Exception as e:
            logger.debug("PowerShell module check failed: %s", e)

        return {
            "installed": False,
            "path": None,
            "source": None,
            "hint": "Install with: Install-Module -Name AzStackHci.EnvironmentChecker -Force",
        }

    async def _install_environment_checker(self) -> dict[str, Any]:
        """Install Microsoft Environment Checker via PowerShell."""
        logger.info("Attempting to install AzStackHci.EnvironmentChecker module...")

        try:
            # Install the module
            install_cmd = [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                """
                Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction SilentlyContinue
                Install-Module -Name AzStackHci.EnvironmentChecker -Force -AllowClobber -Scope CurrentUser
                Get-Module -ListAvailable AzStackHci.EnvironmentChecker | Select-Object Name, Version, Path | ConvertTo-Json
                """,
            ]

            result = subprocess.run(
                install_cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for install
            )

            if result.returncode == 0:
                try:
                    module_info = json.loads(result.stdout.strip())
                    return {
                        "success": True,
                        "module": module_info,
                        "message": "Environment Checker installed successfully",
                    }
                except json.JSONDecodeError:
                    return {
                        "success": True,
                        "message": "Module installed (could not parse details)",
                        "stdout": result.stdout[:500],
                    }
            else:
                return {
                    "success": False,
                    "error": result.stderr[:500],
                    "hint": "Try running PowerShell as Administrator",
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Installation timed out after 5 minutes",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def _load_endpoints(
        self,
        config_path: str,
        categories: list[str] | None,
        mode: str,
    ) -> list[dict[str, Any]]:
        """Load endpoints from configuration."""
        path = Path(config_path)
        if not path.exists():
            path = Path(__file__).parent.parent.parent / config_path

        if not path.exists():
            logger.warning("Endpoints config not found: %s", config_path)
            # Return default key endpoints
            return [
                {"fqdn": ep, "port": 443, "tls": True, "required": True, "category": "azure-arc"}
                for ep in self.KEY_ENDPOINTS
            ]

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error("Failed to load endpoints: %s", e)
            return []

        endpoints = config.get("endpoints", [])

        # Filter by category
        if categories:
            endpoints = [e for e in endpoints if e.get("category") in categories]

        # Filter by mode
        if mode == "quick":
            # Only key endpoints for quick mode
            endpoints = [
                e for e in endpoints if e.get("fqdn") in self.KEY_ENDPOINTS or e.get("required")
            ]
        elif mode == "endpoints-only":
            # All endpoints, no host checks
            pass
        # mode == "full" uses all endpoints

        return endpoints

    async def _run_environment_checker(
        self,
        findings: dict[str, Any],
        checker_path: str,
        mode: str,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Run the official Microsoft Environment Checker.

        Args:
            findings: Findings dict to populate
            checker_path: Path to the Environment Checker module
            mode: Check mode (quick/full)
            progress_callback: Optional async callback for streaming progress updates
        """
        logger.info("Running Microsoft Environment Checker...")

        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Starting Microsoft Environment Checker...",
                    "phase": "init",
                }
            )

        try:
            # Build PowerShell command to run the checker
            # For streaming, we use verbose output on stderr
            # For non-streaming, we suppress all extra output to get clean JSON
            if progress_callback:
                ps_cmd = f"""
                $VerbosePreference = 'Continue'
                Import-Module '{checker_path}' -Force -Verbose 4>&2
                Write-Host "Starting connectivity validation..." -ForegroundColor Cyan 2>&1
                $results = Invoke-AzStackHciConnectivityValidation -PassThru 4>&2 *>&2
                Write-Host "Serializing results..." -ForegroundColor Cyan 2>&1
                $results | ConvertTo-Json -Depth 10
                """
            else:
                # Non-streaming: silence all output except JSON, compress for size
                ps_cmd = f"""
                $VerbosePreference = 'SilentlyContinue'
                $WarningPreference = 'SilentlyContinue'
                $ErrorActionPreference = 'SilentlyContinue'
                Import-Module '{checker_path}' -Force 3>$null 4>$null
                $results = Invoke-AzStackHciConnectivityValidation -PassThru 3>$null 4>$null
                $results | ConvertTo-Json -Depth 10 -Compress
                """

            # Run with streaming if callback provided
            if progress_callback:
                # Use Popen for streaming
                process = subprocess.Popen(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )

                stdout_lines: list[str] = []
                stderr_lines: list[str] = []
                check_count = 0

                # Thread-safe queue for stderr
                stderr_queue: Queue[str | None] = Queue()

                def read_stderr() -> None:
                    if process.stderr:
                        for line in process.stderr:
                            stderr_queue.put(line)
                    stderr_queue.put(None)  # Signal done

                stderr_thread = Thread(target=read_stderr)
                stderr_thread.start()

                # Process stderr in async loop
                while True:
                    try:
                        line = stderr_queue.get_nowait()
                        if line is None:
                            break
                        line = line.strip()
                        stderr_lines.append(line)

                        # Parse progress from verbose output
                        if "VERBOSE:" in line:
                            msg = line.replace("VERBOSE:", "").strip()
                            check_count += 1
                            await progress_callback(
                                {
                                    "type": "progress",
                                    "message": msg,
                                    "checksProcessed": check_count,
                                }
                            )
                        elif "Testing" in line or "Checking" in line:
                            await progress_callback(
                                {
                                    "type": "progress",
                                    "message": line,
                                    "checksProcessed": check_count,
                                }
                            )
                    except Empty:
                        await asyncio.sleep(0.1)
                        if process.poll() is not None:
                            # Process finished, drain remaining
                            while True:
                                try:
                                    remaining = stderr_queue.get_nowait()
                                    if remaining is None:
                                        break
                                    stderr_lines.append(remaining.strip())
                                except Empty:
                                    break
                            break

                stderr_thread.join(timeout=5)
                stdout_data = process.stdout.read() if process.stdout else ""
                process.wait(timeout=30)

                return_code = process.returncode

                await progress_callback(
                    {"type": "status", "message": "Processing results...", "phase": "parsing"}
                )
            else:
                # Non-streaming mode
                result = subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                stdout_data = result.stdout
                return_code = result.returncode

            if return_code == 0:
                try:
                    checker_results = json.loads(stdout_data)
                    await self._parse_checker_results(findings, checker_results)
                    findings["metadata"]["checkerExecuted"] = True

                    if progress_callback:
                        await progress_callback(
                            {
                                "type": "complete",
                                "message": f"Completed {len(findings.get('checks', []))} checks",
                                "totalChecks": len(findings.get("checks", [])),
                            }
                        )
                except json.JSONDecodeError:
                    # Checker ran but output wasn't JSON
                    self.add_check(
                        findings,
                        check_id="arc.connectivity.checker.parse",
                        title="Environment Checker Output",
                        severity="low",
                        status="warn",
                        evidence={
                            "rawOutput": stdout_data[:1000],
                            "parseError": "Could not parse JSON output",
                        },
                        hint="Checker executed but output format was unexpected",
                    )
            else:
                self.add_check(
                    findings,
                    check_id="arc.connectivity.checker.error",
                    title="Environment Checker Execution",
                    severity="medium",
                    status="fail",
                    evidence={
                        "returnCode": return_code,
                    },
                    hint="Environment Checker failed to execute.",
                )

        except subprocess.TimeoutExpired:
            self.add_check(
                findings,
                check_id="arc.connectivity.checker.timeout",
                title="Environment Checker Timeout",
                severity="medium",
                status="fail",
                evidence={"timeout": 300},
                hint="Checker timed out. Try running with fewer endpoints or check network connectivity.",
            )
        except Exception as e:
            logger.exception("Environment Checker failed")
            self.add_check(
                findings,
                check_id="arc.connectivity.checker.exception",
                title="Environment Checker Error",
                severity="medium",
                status="fail",
                evidence={"error": str(e)},
            )

    async def _parse_checker_results(
        self,
        findings: dict[str, Any],
        checker_results: list[dict[str, Any]] | dict[str, Any],
    ) -> None:
        """Parse Environment Checker results into findings format."""
        # Handle both list and dict formats
        if isinstance(checker_results, dict):
            checker_results = [checker_results]

        for item in checker_results:
            name = item.get("Name", item.get("TargetResourceName", "Unknown"))

            # Get status - check multiple locations and handle int/string
            additional_data = item.get("AdditionalData", {})
            status_raw = additional_data.get("Status", item.get("Status", "Unknown"))

            # Handle integer Status enum values (from JSON serialization)
            # 0 = SUCCESS, 1 = WARNING, 2 = FAILURE (common enum pattern)
            if isinstance(status_raw, int):
                status_raw = {0: "SUCCESS", 1: "WARNING", 2: "FAILURE"}.get(status_raw, "Unknown")

            description = item.get("Description", item.get("Title", ""))
            details = additional_data if isinstance(additional_data, dict) else str(additional_data)

            # Map status - handle various formats from Environment Checker
            status_map = {
                "SUCCESS": "pass",
                "Succeeded": "pass",
                "Passed": "pass",
                "pass": "pass",
                "FAILURE": "fail",
                "Failed": "fail",
                "fail": "fail",
                "WARNING": "warn",
                "Warning": "warn",
                "warn": "warn",
            }
            status = status_map.get(
                str(status_raw).upper() if isinstance(status_raw, str) else str(status_raw), "warn"
            )

            # Determine severity from the item's Severity field or based on type
            item_severity = item.get("Severity", 1)
            if isinstance(item_severity, int):
                severity = {0: "low", 1: "medium", 2: "high"}.get(item_severity, "medium")
            elif "connectivity" in name.lower() or "dns" in name.lower():
                severity = "high"
            else:
                severity = "medium"

            check_id = (
                f"arc.connectivity.envchecker.{name.lower().replace(' ', '_').replace('.', '_')}"
            )

            # Extract hint from details
            hint = None
            if status != "pass" and isinstance(details, dict):
                hint = details.get("ExceptionMessage") or details.get("Detail", "")[:200]

            self.add_check(
                findings,
                check_id=check_id,
                title=f"{name}",
                severity=severity,
                status=status,
                evidence={
                    "originalStatus": status_raw,
                    "description": description,
                    "targetResource": item.get("TargetResourceName", ""),
                    "latencyMs": (
                        details.get("LatencyInMs", "") if isinstance(details, dict) else ""
                    ),
                },
                hint=hint,
                sources=[
                    self.get_source_ref("azure-local-environment-checker", "Environment Checker")
                ],
            )

    # NOTE: Removed _run_endpoint_checks and _check_endpoint methods
    # We do NOT reinvent what Microsoft already provides with the Environment Checker
    # All connectivity validation is done through the official Invoke-AzStackHciConnectivityValidation cmdlet

    async def _check_tls(self, fqdn: str, port: int) -> dict[str, Any]:
        """Check TLS certificate validity."""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((fqdn, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=fqdn) as ssock:
                    cert = ssock.getpeercert()
                    return {
                        "valid": True,
                        "subject": dict(x[0] for x in cert.get("subject", [])),
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "notAfter": cert.get("notAfter"),
                        "notBefore": cert.get("notBefore"),
                    }
        except ssl.SSLError as e:
            return {"valid": False, "error": str(e)}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    async def _run_dry_run_checks(
        self,
        findings: dict[str, Any],
        endpoints: list[dict[str, Any]],
        mode: str,
    ) -> None:
        """Run simulated checks using fixture data."""
        logger.info("Running dry-run simulation...")
        findings["metadata"]["simulated"] = True

        # Load fixture data
        fixture_path = (
            Path(__file__).parent.parent.parent / "tests" / "fixtures" / "connectivity_sample.json"
        )

        fixture_data: dict[str, Any] = {}
        if fixture_path.exists():
            with open(fixture_path, "r", encoding="utf-8") as f:
                fixture_data = json.load(f)

        # Add simulated checker status check
        self.add_check(
            findings,
            check_id="arc.connectivity.checker.status",
            title="Environment Checker Status",
            severity="low",
            status="pass",
            evidence={
                "installed": True,
                "version": "2.0.0",
                "simulated": True,
            },
        )

        # Add simulated endpoint checks
        for endpoint in endpoints:
            fqdn = endpoint.get("fqdn", "unknown")
            if "*" in fqdn:
                continue

            port = endpoint.get("port", 443)
            required = endpoint.get("required", False)
            category = endpoint.get("category", "unknown")
            description = endpoint.get("description", "")

            fixture_ep = fixture_data.get(fqdn, {})
            status = fixture_ep.get("status", "pass")
            latency = fixture_ep.get("latency_ms", 45)

            check_id = f"arc.connectivity.{category}.{fqdn.replace('.', '_')}"

            self.add_check(
                findings,
                check_id=check_id,
                title=f"{description or fqdn}",
                severity="high" if required else "medium",
                status=status,
                evidence={
                    "fqdn": fqdn,
                    "port": port,
                    "reachable": status == "pass",
                    "latencyMs": latency,
                    "simulated": True,
                },
                duration_ms=latency,
            )


# Export for easy importing
__all__ = ["ArcConnectivityCheckTool"]
