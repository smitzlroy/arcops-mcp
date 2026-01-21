"""
Azure Local Environment Checker Wrapper Tool.

Wraps and normalizes outputs from the Azure Local Environment Checker.
References: docs/SOURCES.md#azure-local-environment-checker
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from server.tools.base import BaseTool

logger = logging.getLogger(__name__)


class AzLocalEnvCheckWrapTool(BaseTool):
    """
    Tool to wrap and normalize Azure Local Environment Checker outputs.

    Runs the checker via subprocess if present; otherwise simulates from fixtures.
    """

    name = "azlocal.envcheck.wrap"
    description = (
        "Wrap and normalize Azure Local Environment Checker outputs. "
        "Runs the checker via subprocess if present, otherwise uses fixtures for simulation."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["quick", "full"],
                "default": "quick",
            },
            "timeoutSec": {"type": "integer", "default": 300},
            "rawOutput": {"type": "boolean", "default": False},
            "checkerPath": {"type": "string"},
            "dryRun": {"type": "boolean", "default": False},
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the environment checker and normalize results."""
        mode = arguments.get("mode", "quick")
        timeout_sec = arguments.get("timeoutSec", 300)
        raw_output = arguments.get("rawOutput", False)
        checker_path = arguments.get("checkerPath") or os.environ.get("ENVCHECKER_PATH")
        dry_run = arguments.get("dryRun", False)

        run_id = self.generate_run_id()
        findings = self.create_findings_base(
            target="host",
            run_id=run_id,
            tool_name=self.name,
            mode=mode,
        )

        start_time = time.time()

        if dry_run or not checker_path or not Path(checker_path).exists():
            # Use fixture data for simulation
            logger.info("Using fixture data (dry_run=%s, checker_path=%s)", dry_run, checker_path)
            raw_result = await self._load_fixture()
            findings["metadata"]["simulated"] = True
        else:
            # Execute the actual Environment Checker
            logger.info("Executing Environment Checker at %s", checker_path)
            raw_result = await self._run_checker(checker_path, mode, timeout_sec)
            findings["metadata"]["simulated"] = False

        # Parse and normalize the results
        await self._normalize_results(findings, raw_result, raw_output)

        duration_ms = int((time.time() - start_time) * 1000)
        findings["metadata"]["totalDurationMs"] = duration_ms

        return findings

    async def _load_fixture(self) -> dict[str, Any]:
        """Load fixture data for simulation."""
        fixture_path = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "envcheck_sample.json"

        if fixture_path.exists():
            with open(fixture_path, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]

        # Return minimal fixture if file doesn't exist
        return {
            "checks": [
                {
                    "name": "Connectivity",
                    "status": "Passed",
                    "details": "All connectivity checks passed",
                },
                {
                    "name": "DNS",
                    "status": "Passed",
                    "details": "DNS resolution working correctly",
                },
                {
                    "name": "TLS",
                    "status": "Passed",
                    "details": "TLS certificates valid",
                },
                {
                    "name": "NTP",
                    "status": "Warning",
                    "details": "Time sync drift detected: 2.5 seconds",
                },
            ]
        }

    async def _run_checker(
        self, checker_path: str, mode: str, timeout_sec: int
    ) -> dict[str, Any]:
        """Run the actual Environment Checker subprocess."""
        cmd = [checker_path]
        if mode == "full":
            cmd.append("--full")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_sec,
            )

            if process.returncode != 0:
                logger.warning(
                    "Checker returned non-zero: %d, stderr: %s",
                    process.returncode,
                    stderr.decode(),
                )

            # Try to parse as JSON, fall back to raw text
            try:
                return json.loads(stdout.decode())  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                return {"raw": stdout.decode(), "stderr": stderr.decode()}

        except asyncio.TimeoutError:
            logger.error("Checker timed out after %d seconds", timeout_sec)
            return {"error": f"Timeout after {timeout_sec} seconds"}
        except Exception as e:
            logger.exception("Failed to run checker")
            return {"error": str(e)}

    async def _normalize_results(
        self,
        findings: dict[str, Any],
        raw_result: dict[str, Any],
        include_raw: bool,
    ) -> None:
        """Normalize checker results into findings format."""
        if include_raw:
            findings["metadata"]["rawOutput"] = raw_result

        if "error" in raw_result:
            self.add_check(
                findings,
                check_id="azlocal.envcheck.execution",
                title="Environment Checker Execution",
                severity="high",
                status="fail",
                evidence={"error": raw_result["error"]},
                hint="Ensure the Environment Checker is installed and accessible",
                sources=[
                    self.get_source_ref(
                        "azure-local-environment-checker",
                        "Azure Local Environment Checker",
                    )
                ],
            )
            return

        # Process checks from raw result
        checks = raw_result.get("checks", [])
        for check in checks:
            name = check.get("name", "Unknown")
            status_raw = check.get("status", "Unknown").lower()
            details = check.get("details", "")

            # Map status
            status_map = {
                "passed": "pass",
                "pass": "pass",
                "failed": "fail",
                "fail": "fail",
                "warning": "warn",
                "warn": "warn",
                "skipped": "skipped",
            }
            status = status_map.get(status_raw, "warn")

            # Determine severity based on check type
            severity = self._get_severity(name, status)

            # Generate check ID
            check_id = f"azlocal.{name.lower().replace(' ', '_')}"

            self.add_check(
                findings,
                check_id=check_id,
                title=f"Azure Local - {name}",
                severity=severity,
                status=status,
                evidence={"details": details, "rawStatus": check.get("status")},
                hint=self._get_hint(name, status),
                sources=[
                    self.get_source_ref(
                        "azure-local-environment-checker",
                        "Azure Local Environment Checker",
                    )
                ],
            )

    def _get_severity(self, check_name: str, status: str) -> str:
        """Determine severity based on check type and status."""
        high_priority_checks = ["connectivity", "dns", "tls", "authentication"]
        medium_priority_checks = ["ntp", "time", "proxy"]

        name_lower = check_name.lower()

        if status == "fail":
            if any(hp in name_lower for hp in high_priority_checks):
                return "high"
            return "medium"
        elif status == "warn":
            if any(hp in name_lower for hp in high_priority_checks):
                return "medium"
            return "low"
        return "low"

    def _get_hint(self, check_name: str, status: str) -> str | None:
        """Generate remediation hint based on check type and status."""
        if status == "pass":
            return None

        hints = {
            "connectivity": "Verify network connectivity and firewall rules. Check docs/SOURCES.md#arc-required-endpoints",
            "dns": "Verify DNS resolution for required endpoints. Check DNS server configuration.",
            "tls": "Verify TLS certificates and CA trust chain. Corporate proxies may require custom CA.",
            "ntp": "Synchronize system time with a reliable NTP server. Time drift can cause authentication failures.",
            "authentication": "Verify Azure AD credentials and permissions. Check service principal configuration.",
            "proxy": "Verify HTTP(S)_PROXY environment variables and proxy authentication.",
        }

        name_lower = check_name.lower()
        for key, hint in hints.items():
            if key in name_lower:
                return hint

        return "Review check details and consult docs/SOURCES.md for guidance."
