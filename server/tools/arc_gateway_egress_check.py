"""
Arc Gateway Egress Check Tool.

Checks TLS/Proxy/FQDN reachability for Azure Arc gateway endpoints.
References: docs/SOURCES.md#arc-required-endpoints
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

from server.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ArcGatewayEgressCheckTool(BaseTool):
    """
    Tool to check TLS/Proxy/FQDN reachability for Azure Arc gateway endpoints.

    Supports corporate CA trust and HTTP(S)_PROXY.
    """

    name = "arc.gateway.egress.check"
    description = (
        "Check TLS/Proxy/FQDN reachability for Azure Arc gateway endpoints. "
        "Supports corporate CA trust and HTTP(S)_PROXY."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "configPath": {
                "type": "string",
                "default": "server/config/endpoints.yaml",
            },
            "categories": {"type": "array", "items": {"type": "string"}},
            "requiredOnly": {"type": "boolean", "default": False},
            "timeoutSec": {"type": "integer", "default": 10},
            "dryRun": {"type": "boolean", "default": False},
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute egress checks against configured endpoints."""
        config_path = arguments.get("configPath", "server/config/endpoints.yaml")
        categories = arguments.get("categories")
        required_only = arguments.get("requiredOnly", False)
        timeout_sec = arguments.get("timeoutSec", 10)
        dry_run = arguments.get("dryRun", False)

        run_id = self.generate_run_id()
        findings = self.create_findings_base(
            target="gateway",
            run_id=run_id,
            tool_name=self.name,
        )

        # Load endpoint configuration
        endpoints = await self._load_endpoints(config_path, categories, required_only)

        if not endpoints:
            self.add_check(
                findings,
                check_id="arc.gateway.config",
                title="Endpoint Configuration",
                severity="high",
                status="fail",
                evidence={"configPath": config_path},
                hint=f"No endpoints found in {config_path}. Verify configuration file exists.",
            )
            return findings

        findings["metadata"]["endpointCount"] = len(endpoints)
        findings["metadata"]["dryRun"] = dry_run

        # Get proxy configuration
        proxy_config = self._get_proxy_config()
        if proxy_config:
            findings["metadata"]["proxyConfigured"] = True

        # Check each endpoint
        if dry_run:
            await self._check_endpoints_dry_run(findings, endpoints)
        else:
            await self._check_endpoints(findings, endpoints, timeout_sec, proxy_config)

        return findings

    async def _load_endpoints(
        self,
        config_path: str,
        categories: list[str] | None,
        required_only: bool,
    ) -> list[dict[str, Any]]:
        """Load and filter endpoints from configuration."""
        path = Path(config_path)

        if not path.exists():
            # Try relative to package root
            path = Path(__file__).parent.parent.parent / config_path

        if not path.exists():
            logger.warning("Endpoints config not found: %s", config_path)
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error("Failed to load endpoints config: %s", e)
            return []

        endpoints = config.get("endpoints", [])

        # Filter by category
        if categories:
            endpoints = [e for e in endpoints if e.get("category") in categories]

        # Filter required only
        if required_only:
            endpoints = [e for e in endpoints if e.get("required", False)]

        return endpoints

    def _get_proxy_config(self) -> dict[str, str] | None:
        """Get proxy configuration from environment."""
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

        if http_proxy or https_proxy:
            return {
                "http": http_proxy or "",
                "https": https_proxy or "",
            }
        return None

    async def _check_endpoints_dry_run(
        self,
        findings: dict[str, Any],
        endpoints: list[dict[str, Any]],
    ) -> None:
        """Simulate endpoint checks using fixture data."""
        fixture_path = (
            Path(__file__).parent.parent.parent / "tests" / "fixtures" / "egress_ok.json"
        )

        fixture_data: dict[str, Any] = {}
        if fixture_path.exists():
            with open(fixture_path, "r", encoding="utf-8") as f:
                fixture_data = json.load(f)

        for endpoint in endpoints:
            fqdn = endpoint.get("fqdn", "unknown")
            port = endpoint.get("port", 443)
            tls = endpoint.get("tls", True)
            required = endpoint.get("required", False)
            category = endpoint.get("category", "unknown")

            # Check if we have fixture data for this endpoint
            fixture_status = fixture_data.get(fqdn, {}).get("status", "pass")
            fixture_latency = fixture_data.get(fqdn, {}).get("latency_ms", 50)

            check_id = f"arc.gateway.{category}.{fqdn.replace('.', '_').replace('*', 'wildcard')}"

            self.add_check(
                findings,
                check_id=check_id,
                title=f"Egress Check: {fqdn}:{port}",
                severity="high" if required else "medium",
                status=fixture_status,
                evidence={
                    "fqdn": fqdn,
                    "port": port,
                    "tls": tls,
                    "required": required,
                    "category": category,
                    "latency_ms": fixture_latency,
                    "simulated": True,
                },
                hint=self._get_egress_hint(fqdn, category) if fixture_status != "pass" else None,
                sources=[
                    self.get_source_ref("arc-required-endpoints", f"Arc Required Endpoints - {category}")
                ],
                duration_ms=fixture_latency,
            )

    async def _check_endpoints(
        self,
        findings: dict[str, Any],
        endpoints: list[dict[str, Any]],
        timeout_sec: int,
        proxy_config: dict[str, str] | None,
    ) -> None:
        """Check actual endpoint connectivity."""
        # Create HTTP client with optional proxy
        transport_kwargs: dict[str, Any] = {}
        if proxy_config:
            transport_kwargs["proxy"] = proxy_config.get("https") or proxy_config.get("http")

        async with httpx.AsyncClient(
            timeout=timeout_sec,
            follow_redirects=True,
            verify=True,
        ) as client:
            tasks = [
                self._check_single_endpoint(client, endpoint, findings, timeout_sec)
                for endpoint in endpoints
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_single_endpoint(
        self,
        client: httpx.AsyncClient,
        endpoint: dict[str, Any],
        findings: dict[str, Any],
        timeout_sec: int,
    ) -> None:
        """Check a single endpoint's reachability and TLS."""
        fqdn = endpoint.get("fqdn", "unknown")
        port = endpoint.get("port", 443)
        tls = endpoint.get("tls", True)
        required = endpoint.get("required", False)
        category = endpoint.get("category", "unknown")
        description = endpoint.get("description", "")

        # Skip wildcard endpoints (can't test directly)
        if "*" in fqdn:
            check_id = f"arc.gateway.{category}.{fqdn.replace('.', '_').replace('*', 'wildcard')}"
            self.add_check(
                findings,
                check_id=check_id,
                title=f"Egress Check: {fqdn}:{port}",
                severity="low",
                status="skipped",
                evidence={
                    "fqdn": fqdn,
                    "port": port,
                    "reason": "Wildcard endpoint - cannot test directly",
                },
                hint="Wildcard endpoints require testing with specific subdomains",
            )
            return

        start_time = time.time()
        status = "pass"
        evidence: dict[str, Any] = {
            "fqdn": fqdn,
            "port": port,
            "tls": tls,
            "required": required,
            "category": category,
            "description": description,
        }
        hint: str | None = None

        try:
            # Build URL
            scheme = "https" if tls else "http"
            url = f"{scheme}://{fqdn}:{port}/"

            # Make request
            response = await client.get(url, timeout=timeout_sec)
            evidence["status_code"] = response.status_code
            evidence["reachable"] = True

            # Check TLS chain if applicable
            if tls:
                evidence["tls_verified"] = True

            # Any response is considered success for reachability
            if response.status_code >= 500:
                status = "warn"
                hint = f"Endpoint returned server error: {response.status_code}"

        except httpx.ConnectTimeout:
            status = "fail"
            evidence["error"] = "Connection timeout"
            evidence["reachable"] = False
            hint = self._get_egress_hint(fqdn, category)

        except httpx.ConnectError as e:
            status = "fail"
            evidence["error"] = f"Connection failed: {str(e)}"
            evidence["reachable"] = False
            hint = self._get_egress_hint(fqdn, category)

        except ssl.SSLError as e:
            status = "fail"
            evidence["error"] = f"TLS error: {str(e)}"
            evidence["tls_verified"] = False
            hint = "TLS certificate validation failed. Check CA trust chain and corporate proxy configuration."

        except Exception as e:
            status = "fail"
            evidence["error"] = str(e)
            hint = self._get_egress_hint(fqdn, category)

        duration_ms = int((time.time() - start_time) * 1000)
        evidence["latency_ms"] = duration_ms

        check_id = f"arc.gateway.{category}.{fqdn.replace('.', '_')}"
        self.add_check(
            findings,
            check_id=check_id,
            title=f"Egress Check: {fqdn}:{port}",
            severity="high" if required else "medium",
            status=status,
            evidence=evidence,
            hint=hint,
            sources=[
                self.get_source_ref("arc-required-endpoints", f"Arc Required Endpoints - {category}")
            ],
            duration_ms=duration_ms,
        )

    def _get_egress_hint(self, fqdn: str, category: str) -> str:
        """Get remediation hint for egress failures."""
        hints = {
            "azure-arc": (
                f"Cannot reach {fqdn}. Verify firewall rules allow outbound HTTPS to Azure Arc endpoints. "
                "See docs/SOURCES.md#arc-required-endpoints"
            ),
            "aks-arc": (
                f"Cannot reach {fqdn}. Verify firewall rules allow access to container registry endpoints. "
                "See docs/SOURCES.md#aks-arc-requirements"
            ),
            "monitoring": (
                f"Cannot reach {fqdn}. This is optional for telemetry. "
                "Enable if Azure Monitor integration is required."
            ),
        }
        return hints.get(
            category,
            f"Cannot reach {fqdn}. Verify network connectivity and firewall rules.",
        )
