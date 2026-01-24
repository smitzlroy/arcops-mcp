"""
Network Safety Tool for ArcOps MCP.

Validates and generates Gateway API + Istio network policies with
deny-by-default posture for sovereign/edge deployments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from server.services.artifact_signer import sign_artifact
from server.tools.base import BaseTool


# Safety check definitions
SAFETY_CHECKS = [
    {
        "id": "NS-001",
        "title": "No wildcard egress (0.0.0.0/0)",
        "category": "egress",
        "severity": "critical",
        "check": lambda ns: "0.0.0.0/0" not in ns.get("egress", {}).get("allowedCidrs", []),
        "remediation": "Remove 0.0.0.0/0 from allowedCidrs and specify explicit CIDR ranges",
    },
    {
        "id": "NS-002",
        "title": "TLS required for public ingress",
        "category": "tls",
        "severity": "high",
        "check": lambda ns: ns.get("ingress", {}).get("tlsRequired", True),
        "remediation": "Set tlsRequired: true for all ingress hosts",
    },
    {
        "id": "NS-003",
        "title": "TLS secret specified when TLS required",
        "category": "tls",
        "severity": "high",
        "check": lambda ns: not ns.get("ingress", {}).get("tlsRequired", False)
        or ns.get("ingress", {}).get("tlsSecret"),
        "remediation": "Specify tlsSecret when tlsRequired is true",
    },
    {
        "id": "NS-004",
        "title": "Egress mode is deny-by-default",
        "category": "egress",
        "severity": "high",
        "check": lambda ns: ns.get("egress", {}).get("mode") == "deny-by-default",
        "remediation": "Set egress.mode to 'deny-by-default'",
    },
    {
        "id": "NS-005",
        "title": "No wildcard hosts in ingress",
        "category": "ingress",
        "severity": "medium",
        "check": lambda ns: not any("*" in h for h in ns.get("ingress", {}).get("hosts", [])),
        "remediation": "Replace wildcard hosts with specific hostnames",
    },
    {
        "id": "NS-006",
        "title": "Rate limiting configured",
        "category": "ingress",
        "severity": "low",
        "check": lambda ns: ns.get("ingress", {}).get("rateLimit") is not None,
        "remediation": "Consider adding rate limiting for production workloads",
    },
]


class NetworkSafetyTool(BaseTool):
    """
    Validate network policy against security requirements.

    Checks for common security issues:
    - Wildcard egress
    - Missing TLS
    - Overly permissive ingress
    - Missing deny-by-default posture

    Outputs a safety report with PASS/FAIL/WARN verdict.
    """

    name = "network.safety"
    description = (
        "Validate network policy YAML against security requirements. "
        "Returns a safety report with violations and remediation guidance."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "policy": {
                "type": "string",
                "description": "Path to network policy YAML file",
            },
            "outputPath": {
                "type": "string",
                "description": "Path to write safety report",
                "default": "artifacts/safety-report.json",
            },
        },
        "required": ["policy"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool via MCP protocol."""
        return await self.run(**arguments)

    async def run(
        self,
        policy: str,
        outputPath: str = "artifacts/safety-report.json",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute network safety validation."""
        run_id = self.generate_run_id()
        timestamp = self.get_timestamp()

        # Load policy
        policy_path = Path(policy)
        if not policy_path.exists():
            return self._error_artifact(run_id, timestamp, f"Policy file not found: {policy}")

        with open(policy_path, "r", encoding="utf-8") as f:
            policy_data = yaml.safe_load(f)

        # Initialize artifact
        artifact: dict[str, Any] = {
            "version": "1.0.0",
            "type": "safety-report",
            "timestamp": timestamp,
            "runId": run_id,
            "metadata": {
                "toolName": self.name,
                "toolVersion": "1.0.0",
                "hostname": self._get_hostname(),
            },
            "policy": {
                "name": policy_data.get("name", "unknown"),
                "path": policy,
                "version": policy_data.get("version", "1.0"),
                "namespaces": len(policy_data.get("namespaces", [])),
            },
            "checks": [],
            "summary": {
                "total": 0,
                "pass": 0,
                "fail": 0,
                "warn": 0,
                "skip": 0,
                "bySeverity": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                },
            },
            "verdict": "PASS",
        }

        # Run checks for each namespace
        all_checks: list[dict[str, Any]] = []

        # Global checks
        global_config = policy_data.get("global", {})
        all_checks.extend(self._run_global_checks(global_config))

        # Per-namespace checks
        for ns in policy_data.get("namespaces", []):
            ns_name = ns.get("name", "unknown")
            all_checks.extend(self._run_namespace_checks(ns, ns_name))

        artifact["checks"] = all_checks

        # Compute summary
        summary = artifact["summary"]
        for check in all_checks:
            summary["total"] += 1
            status = check["status"]
            summary[status] = summary.get(status, 0) + 1

            if check["status"] == "fail":
                severity = check["severity"]
                summary["bySeverity"][severity] = summary["bySeverity"].get(severity, 0) + 1

        # Determine verdict
        if summary["bySeverity"]["critical"] > 0:
            artifact["verdict"] = "FAIL"
        elif summary["bySeverity"]["high"] > 0:
            artifact["verdict"] = "FAIL"
        elif summary["fail"] > 0:
            artifact["verdict"] = "WARN"
        else:
            artifact["verdict"] = "PASS"

        # Sign artifact
        artifact = sign_artifact(artifact)

        # Write to output
        output_path = Path(outputPath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2)

        return artifact

    def _run_global_checks(self, global_config: dict[str, Any]) -> list[dict[str, Any]]:
        """Run global policy checks."""
        checks = []

        # Check TLS minimum version
        tls_version = global_config.get("tlsMinVersion", "1.2")
        checks.append(
            {
                "id": "NS-G01",
                "category": "global",
                "severity": "high",
                "status": "pass" if tls_version >= "1.2" else "fail",
                "title": "TLS minimum version >= 1.2",
                "description": f"TLS minimum version is {tls_version}",
                "remediation": "Set global.tlsMinVersion to 1.2 or higher",
            }
        )

        # Check deny-by-default
        deny_default = global_config.get("denyByDefault", False)
        checks.append(
            {
                "id": "NS-G02",
                "category": "global",
                "severity": "high",
                "status": "pass" if deny_default else "warn",
                "title": "Global deny-by-default enabled",
                "description": f"denyByDefault is {'enabled' if deny_default else 'disabled'}",
                "remediation": "Set global.denyByDefault to true",
            }
        )

        return checks

    def _run_namespace_checks(
        self, ns_config: dict[str, Any], ns_name: str
    ) -> list[dict[str, Any]]:
        """Run per-namespace checks."""
        checks = []

        for check_def in SAFETY_CHECKS:
            try:
                passed = check_def["check"](ns_config)
                checks.append(
                    {
                        "id": check_def["id"],
                        "category": check_def["category"],
                        "severity": check_def["severity"],
                        "status": "pass" if passed else "fail",
                        "title": check_def["title"],
                        "namespace": ns_name,
                        "remediation": check_def["remediation"] if not passed else None,
                    }
                )
            except Exception as e:
                checks.append(
                    {
                        "id": check_def["id"],
                        "category": check_def["category"],
                        "severity": check_def["severity"],
                        "status": "skip",
                        "title": check_def["title"],
                        "namespace": ns_name,
                        "description": f"Check skipped: {str(e)}",
                    }
                )

        return checks

    def _get_hostname(self) -> str:
        """Get current hostname."""
        import socket

        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    def _error_artifact(self, run_id: str, timestamp: str, error: str) -> dict[str, Any]:
        """Create error artifact."""
        artifact = {
            "version": "1.0.0",
            "type": "safety-report",
            "timestamp": timestamp,
            "runId": run_id,
            "error": error,
            "verdict": "FAIL",
            "checks": [],
            "summary": {"total": 0, "pass": 0, "fail": 0, "warn": 0},
        }
        return sign_artifact(artifact)


class NetworkRenderTool(BaseTool):
    """
    Render Gateway API and Istio manifests from network policy.

    Generates:
    - Gateway API Gateway and HTTPRoute resources
    - Istio ServiceEntry and VirtualService for egress

    All generated manifests follow deny-by-default principles.
    """

    name = "network.render"
    description = (
        "Generate Gateway API ingress and Istio egress manifests from network policy. "
        "Returns paths to generated manifests."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "policy": {
                "type": "string",
                "description": "Path to network policy YAML file",
            },
            "outputDir": {
                "type": "string",
                "description": "Directory to write manifests",
                "default": "manifests/network",
            },
        },
        "required": ["policy"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool via MCP protocol."""
        return await self.run(**arguments)

    async def run(
        self,
        policy: str,
        outputDir: str = "manifests/network",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate network manifests from policy."""
        # Load policy
        policy_path = Path(policy)
        if not policy_path.exists():
            return {"error": f"Policy file not found: {policy}"}

        with open(policy_path, "r", encoding="utf-8") as f:
            policy_data = yaml.safe_load(f)

        output_dir = Path(outputDir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ingress_manifests: list[str] = []
        egress_manifests: list[str] = []

        # Generate ingress manifests
        ingress_dir = output_dir / "ingress"
        ingress_dir.mkdir(exist_ok=True)

        # Generate Gateway
        gateway = self._generate_gateway(policy_data)
        gateway_path = ingress_dir / "gateway.yaml"
        with open(gateway_path, "w", encoding="utf-8") as f:
            yaml.dump(gateway, f, default_flow_style=False)
        ingress_manifests.append(str(gateway_path))

        # Generate HTTPRoutes per namespace
        for ns in policy_data.get("namespaces", []):
            ns_name = ns.get("name", "default")
            if "ingress" in ns:
                route = self._generate_httproute(ns, policy_data)
                route_path = ingress_dir / f"{ns_name}-route.yaml"
                with open(route_path, "w", encoding="utf-8") as f:
                    yaml.dump(route, f, default_flow_style=False)
                ingress_manifests.append(str(route_path))

        # Generate egress manifests
        egress_dir = output_dir / "egress"
        egress_dir.mkdir(exist_ok=True)

        for ns in policy_data.get("namespaces", []):
            ns_name = ns.get("name", "default")
            egress_config = ns.get("egress", {})

            if egress_config.get("mode") == "deny-by-default":
                # Generate ServiceEntries for allowed destinations
                for idx, sni in enumerate(egress_config.get("allowedSNI", [])):
                    se = self._generate_service_entry(ns_name, sni, idx)
                    se_path = egress_dir / f"{ns_name}-egress-{idx}.yaml"
                    with open(se_path, "w", encoding="utf-8") as f:
                        yaml.dump(se, f, default_flow_style=False)
                    egress_manifests.append(str(se_path))

        return {
            "ingressManifests": ingress_manifests,
            "egressManifests": egress_manifests,
            "outputDir": str(output_dir),
        }

    def _generate_gateway(self, policy_data: dict[str, Any]) -> dict[str, Any]:
        """Generate Gateway API Gateway resource."""
        global_config = policy_data.get("global", {})
        tls_min = global_config.get("tlsMinVersion", "1.2")

        return {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "Gateway",
            "metadata": {
                "name": "edge-gateway",
                "namespace": "istio-system",
            },
            "spec": {
                "gatewayClassName": "istio",
                "listeners": [
                    {
                        "name": "https",
                        "port": 443,
                        "protocol": "HTTPS",
                        "tls": {
                            "mode": "Terminate",
                            "options": {
                                "minVersion": f"TLS{tls_min.replace('.', '')}",
                            },
                        },
                        "allowedRoutes": {
                            "namespaces": {"from": "Selector"},
                        },
                    },
                ],
            },
        }

    def _generate_httproute(
        self, ns_config: dict[str, Any], policy_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate Gateway API HTTPRoute resource."""
        ns_name = ns_config.get("name", "default")
        ingress = ns_config.get("ingress", {})
        hosts = ingress.get("hosts", [])

        route = {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "HTTPRoute",
            "metadata": {
                "name": f"{ns_name}-route",
                "namespace": ns_name,
            },
            "spec": {
                "parentRefs": [
                    {
                        "name": "edge-gateway",
                        "namespace": "istio-system",
                    },
                ],
                "hostnames": hosts,
                "rules": [
                    {
                        "matches": [
                            {"path": {"type": "PathPrefix", "value": "/"}},
                        ],
                        "backendRefs": [
                            {
                                "name": f"{ns_name}-svc",
                                "port": 8080,
                            },
                        ],
                    },
                ],
            },
        }

        return route

    def _generate_service_entry(self, ns_name: str, sni: str, idx: int) -> dict[str, Any]:
        """Generate Istio ServiceEntry for allowed egress."""
        return {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "ServiceEntry",
            "metadata": {
                "name": f"{ns_name}-egress-{idx}",
                "namespace": "istio-system",
            },
            "spec": {
                "hosts": [sni],
                "ports": [
                    {"number": 443, "name": "https", "protocol": "HTTPS"},
                ],
                "resolution": "DNS",
                "location": "MESH_EXTERNAL",
                "exportTo": [ns_name],
            },
        }
