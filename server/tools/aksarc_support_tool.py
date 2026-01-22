"""
AKS Arc Support Tool - Wrapper for Test-SupportAksArcKnownIssues.

Thin wrapper that exposes the Support.AksArc PowerShell module via MCP.
Does not auto-remediate; returns diagnostic results for user review.

References:
- https://learn.microsoft.com/en-us/azure/aks/aksarc/support-module
- https://www.powershellgallery.com/packages/Support.AksArc
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Coroutine

from server.tools.base import BaseTool

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class AksArcSupportTool(BaseTool):
    """
    Wrapper for Test-SupportAksArcKnownIssues.

    Checks for common AKS Arc issues:
    - Failover Cluster Service responsiveness
    - MOC Cloud/Node/Host Agent status
    - MOC version validation
    - Expired certificates
    - Gallery images stuck in deleting
    - VMs stuck in pending state
    - VMMS responsiveness
    """

    name = "aksarc.support.diagnose"
    description = (
        "Run Test-SupportAksArcKnownIssues to check for common AKS Arc issues. "
        "Returns diagnostic results. Does not auto-remediate."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "dryRun": {
                "type": "boolean",
                "default": False,
                "description": "Return fixture data without running actual checks",
            },
        },
    }

    async def execute(
        self,
        arguments: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Execute AKS Arc known issues check."""
        dry_run = arguments.get("dryRun", False)

        run_id = self.generate_run_id()
        findings = self.create_findings_base(
            target="aksarc",
            run_id=run_id,
            tool_name=self.name,
            mode="dry-run" if dry_run else "live",
        )

        start_time = time.time()

        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Checking for Support.AksArc module...",
                    "phase": "detect",
                }
            )

        # Check if module is installed
        module_info = self._check_module_installed()
        findings["metadata"]["module"] = module_info

        if dry_run:
            await self._run_dry_run(findings, progress_callback)
        elif not module_info["installed"]:
            self.add_check(
                findings,
                check_id="aksarc.support.module.required",
                title="Support.AksArc Module Required",
                severity="high",
                status="fail",
                evidence={
                    "installed": False,
                    "moduleName": "Support.AksArc",
                },
                hint=(
                    "Install the Support.AksArc module from PowerShell Gallery: "
                    "Install-Module -Name Support.AksArc -Force"
                ),
            )
        else:
            await self._run_known_issues_check(findings, progress_callback)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        findings["metadata"]["totalDurationMs"] = duration_ms

        return findings

    def _check_module_installed(self) -> dict[str, Any]:
        """Check if Support.AksArc PowerShell module is installed."""
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "Get-Module -ListAvailable Support.AksArc | "
                    "Select-Object Name, Version, Path | ConvertTo-Json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    module_data = json.loads(result.stdout.strip())
                    # Handle single module vs array
                    if isinstance(module_data, list):
                        module_data = module_data[0]
                    return {
                        "installed": True,
                        "name": module_data.get("Name"),
                        "version": module_data.get("Version"),
                        "path": module_data.get("Path"),
                    }
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("Module check failed: %s", e)

        return {
            "installed": False,
            "hint": "Install-Module -Name Support.AksArc -Force",
        }

    async def _run_known_issues_check(
        self,
        findings: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Run Test-SupportAksArcKnownIssues and parse results."""
        logger.info("Running Test-SupportAksArcKnownIssues...")

        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Running Test-SupportAksArcKnownIssues...",
                    "phase": "execute",
                }
            )

        try:
            ps_cmd = """
            Import-Module Support.AksArc -Force
            $results = Test-SupportAksArcKnownIssues
            $results | ConvertTo-Json -Depth 10
            """

            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    check_results = json.loads(result.stdout.strip())
                    self._parse_results(findings, check_results)
                    findings["metadata"]["executed"] = True

                    if progress_callback:
                        await progress_callback(
                            {
                                "type": "complete",
                                "message": f"Completed {findings['summary']['total']} checks",
                                "totalChecks": findings["summary"]["total"],
                            }
                        )
                except json.JSONDecodeError:
                    # Module ran but output wasn't valid JSON
                    self.add_check(
                        findings,
                        check_id="aksarc.support.output.parse",
                        title="Support Module Output",
                        severity="medium",
                        status="warn",
                        evidence={
                            "rawOutput": result.stdout[:2000],
                            "parseError": "Could not parse JSON output",
                        },
                        hint="Module executed but output format was unexpected. Check manually.",
                    )
            else:
                self.add_check(
                    findings,
                    check_id="aksarc.support.execution.error",
                    title="Support Module Execution",
                    severity="high",
                    status="fail",
                    evidence={
                        "returnCode": result.returncode,
                        "stderr": result.stderr[:1000] if result.stderr else None,
                    },
                    hint="Test-SupportAksArcKnownIssues failed to execute.",
                )

        except subprocess.TimeoutExpired:
            self.add_check(
                findings,
                check_id="aksarc.support.timeout",
                title="Support Module Timeout",
                severity="high",
                status="fail",
                evidence={"timeoutSec": 300},
                hint="Check took too long. Verify cluster connectivity.",
            )
        except Exception as e:
            logger.exception("Unexpected error running Support.AksArc")
            self.add_check(
                findings,
                check_id="aksarc.support.error",
                title="Support Module Error",
                severity="high",
                status="fail",
                evidence={"error": str(e)},
            )

    def _parse_results(
        self,
        findings: dict[str, Any],
        check_results: list[dict[str, Any]] | dict[str, Any],
    ) -> None:
        """Parse Test-SupportAksArcKnownIssues output into findings schema."""
        # Handle single result vs array
        if isinstance(check_results, dict):
            check_results = [check_results]

        for item in check_results:
            # Map Support.AksArc output to our findings schema
            # The module returns objects with Name, Status, Details, etc.
            check_name = item.get("Name", item.get("CheckName", "unknown"))
            status_raw = item.get("Status", item.get("Result", "unknown"))
            details = item.get("Details", item.get("Message", ""))

            # Map status values
            status_map = {
                "Passed": "pass",
                "Pass": "pass",
                "OK": "pass",
                "Success": "pass",
                "Failed": "fail",
                "Fail": "fail",
                "Error": "fail",
                "Warning": "warn",
                "Warn": "warn",
                "Skipped": "skipped",
                "Skip": "skipped",
            }
            status = status_map.get(status_raw, "warn")

            # Determine severity based on check type
            severity = "medium"
            if "certificate" in check_name.lower():
                severity = "high"
            elif "agent" in check_name.lower():
                severity = "high"
            elif "cluster" in check_name.lower():
                severity = "high"

            # Build check ID from name
            check_id = f"aksarc.support.{check_name.lower().replace(' ', '-').replace('_', '-')}"

            self.add_check(
                findings,
                check_id=check_id,
                title=check_name,
                severity=severity,
                status=status,
                evidence={
                    "originalStatus": status_raw,
                    "details": details,
                    "raw": item,
                },
                hint=details if status == "fail" else None,
            )

    async def _run_dry_run(
        self,
        findings: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Return fixture data for testing."""
        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Loading fixture data (dry run)...",
                    "phase": "dry-run",
                }
            )

        # Load fixture if available
        fixture_path = (
            Path(__file__).parent.parent.parent
            / "tests"
            / "fixtures"
            / "aksarc_support_sample.json"
        )
        if fixture_path.exists():
            try:
                with open(fixture_path, "r", encoding="utf-8") as f:
                    fixture_data = json.load(f)
                self._parse_results(findings, fixture_data.get("results", []))
                findings["metadata"]["fixtureUsed"] = str(fixture_path)
            except Exception as e:
                logger.warning("Failed to load fixture: %s", e)
                self._add_sample_checks(findings)
        else:
            self._add_sample_checks(findings)

        if progress_callback:
            await progress_callback(
                {
                    "type": "complete",
                    "message": f"Dry run complete with {findings['summary']['total']} checks",
                    "totalChecks": findings["summary"]["total"],
                }
            )

    def _add_sample_checks(self, findings: dict[str, Any]) -> None:
        """Add sample checks for dry run when no fixture exists."""
        sample_checks = [
            {
                "id": "aksarc.support.failover-cluster-service",
                "title": "Failover Cluster Service",
                "severity": "high",
                "status": "pass",
            },
            {
                "id": "aksarc.support.moc-cloud-agent",
                "title": "MOC Cloud Agent Status",
                "severity": "high",
                "status": "pass",
            },
            {
                "id": "aksarc.support.moc-node-agent",
                "title": "MOC Node Agent Status",
                "severity": "high",
                "status": "pass",
            },
            {
                "id": "aksarc.support.moc-version",
                "title": "MOC Version Validation",
                "severity": "medium",
                "status": "pass",
            },
            {
                "id": "aksarc.support.certificates",
                "title": "Certificate Expiration Check",
                "severity": "high",
                "status": "pass",
            },
            {
                "id": "aksarc.support.vmms-responsive",
                "title": "VMMS Responsiveness",
                "severity": "high",
                "status": "pass",
            },
        ]

        for check in sample_checks:
            self.add_check(
                findings,
                check_id=check["id"],
                title=check["title"],
                severity=check["severity"],
                status=check["status"],
                evidence={"dryRun": True},
            )
