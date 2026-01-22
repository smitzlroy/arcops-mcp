"""
AKS Arc Validate Tool.

Validates AKS Arc cluster invariants: extension presence/health, CNI mode, version pins.
References: docs/SOURCES.md#aks-arc-validation
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from server.tools.base import BaseTool

logger = logging.getLogger(__name__)


class AksArcValidateTool(BaseTool):
    """
    Tool to validate AKS Arc cluster invariants.

    Returns 'skipped' if kubeconfig is unavailable.
    """

    name = "aks.arc.validate"
    description = (
        "Validate AKS Arc cluster invariants: extension presence/health, CNI mode, version pins. "
        "Returns 'skipped' if kubeconfig is unavailable."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "kubeconfig": {"type": "string"},
            "context": {"type": "string"},
            "checks": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["extensions", "cni", "versions", "flux", "all"],
                },
                "default": ["all"],
            },
            "dryRun": {"type": "boolean", "default": False},
        },
    }

    # Expected Arc extensions
    EXPECTED_EXTENSIONS = [
        "microsoft.azuremonitor.containers",
        "microsoft.arc.containerstorage",
        "microsoft.flux",
        "microsoft.azure.policy",
    ]

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute AKS Arc validation checks."""
        kubeconfig = arguments.get("kubeconfig") or os.environ.get(
            "KUBECONFIG", str(Path.home() / ".kube" / "config")
        )
        context = arguments.get("context")
        checks = arguments.get("checks", ["all"])
        dry_run = arguments.get("dryRun", False)

        run_id = self.generate_run_id()
        findings = self.create_findings_base(
            target="cluster",
            run_id=run_id,
            tool_name=self.name,
        )

        # Check if kubeconfig exists
        kubeconfig_path = Path(kubeconfig)
        if not kubeconfig_path.exists() and not dry_run:
            self.add_check(
                findings,
                check_id="aks.arc.kubeconfig",
                title="Kubernetes Configuration",
                severity="high",
                status="skipped",
                evidence={
                    "kubeconfigPath": str(kubeconfig_path),
                    "exists": False,
                },
                hint=(
                    f"Kubeconfig not found at {kubeconfig_path}. "
                    "Set KUBECONFIG environment variable or provide --kubeconfig path. "
                    "This check will be skipped until kubeconfig is available."
                ),
                sources=[self.get_source_ref("aks-arc-validation", "AKS Arc Validation")],
            )
            return findings

        findings["metadata"]["kubeconfig"] = str(kubeconfig_path)
        findings["metadata"]["context"] = context
        findings["metadata"]["dryRun"] = dry_run

        # Resolve which checks to run
        if "all" in checks:
            checks = ["extensions", "cni", "versions", "flux"]

        # Get cluster data (mock or real)
        if dry_run:
            cluster_data = await self._load_fixture()
        else:
            cluster_data = await self._get_cluster_data(kubeconfig_path, context)

        # Run requested checks
        for check in checks:
            if check == "extensions":
                await self._check_extensions(findings, cluster_data)
            elif check == "cni":
                await self._check_cni(findings, cluster_data)
            elif check == "versions":
                await self._check_versions(findings, cluster_data)
            elif check == "flux":
                await self._check_flux(findings, cluster_data)

        return findings

    async def _load_fixture(self) -> dict[str, Any]:
        """Load fixture data for simulation."""
        fixture_path = (
            Path(__file__).parent.parent.parent / "tests" / "fixtures" / "findings_sample.json"
        )

        if fixture_path.exists():
            with open(fixture_path, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]

        # Return mock cluster data
        return {
            "extensions": [
                {
                    "name": "microsoft.azuremonitor.containers",
                    "status": "Installed",
                    "healthy": True,
                },
                {"name": "microsoft.flux", "status": "Installed", "healthy": True},
                {"name": "microsoft.azure.policy", "status": "Installed", "healthy": False},
            ],
            "cni": {
                "plugin": "azure",
                "mode": "overlay",
                "podCidr": "10.244.0.0/16",
            },
            "versions": {
                "kubernetes": "1.28.5",
                "arcAgent": "1.15.0",
                "helmOperator": "1.4.2",
            },
            "flux": {
                "installed": True,
                "version": "2.2.0",
                "gitRepositories": 2,
                "kustomizations": 3,
                "reconciled": True,
            },
        }

    async def _get_cluster_data(self, kubeconfig: Path, context: str | None) -> dict[str, Any]:
        """
        Get REAL cluster data via kubectl and Azure CLI.

        Uses kubectl for cluster-internal data (CNI, versions) and
        Azure CLI for Arc-specific data (extensions, connected clusters).

        Returns dict with: extensions, cni, versions, flux
        """
        cluster_data: dict[str, Any] = {
            "extensions": [],
            "cni": {},
            "versions": {},
            "flux": {},
        }

        # Build kubectl base command with kubeconfig
        kubectl_base = ["kubectl", f"--kubeconfig={kubeconfig}"]
        if context:
            kubectl_base.extend(["--context", context])

        # 1. Get Kubernetes version
        try:
            cmd = kubectl_base + ["version", "-o", "json"]
            logger.info("Running: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                version_data = json.loads(result.stdout)
                server_version = version_data.get("serverVersion", {})
                cluster_data["versions"]["kubernetes"] = server_version.get(
                    "gitVersion", "unknown"
                ).lstrip("v")
            else:
                logger.warning("kubectl version failed: %s", result.stderr)
                cluster_data["versions"]["kubernetes"] = "unknown"
        except Exception as e:
            logger.error("Failed to get kubernetes version: %s", e)
            cluster_data["versions"]["kubernetes"] = "error"

        # 2. Get CNI configuration from kube-system pods
        try:
            cmd = kubectl_base + ["get", "pods", "-n", "kube-system", "-o", "json"]
            logger.info("Running: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                pods_data = json.loads(result.stdout)
                cni_plugin = "unknown"

                for pod in pods_data.get("items", []):
                    pod_name = pod.get("metadata", {}).get("name", "")
                    if "azure-cni" in pod_name or "azure-ip" in pod_name:
                        cni_plugin = "azure"
                        break
                    elif "calico" in pod_name:
                        cni_plugin = "calico"
                        break
                    elif "flannel" in pod_name:
                        cni_plugin = "flannel"
                        break
                    elif "cilium" in pod_name:
                        cni_plugin = "cilium"
                        break

                cluster_data["cni"]["plugin"] = cni_plugin
        except Exception as e:
            logger.error("Failed to detect CNI: %s", e)
            cluster_data["cni"]["plugin"] = "error"

        # 3. Get Arc agent info from azure-arc namespace
        try:
            cmd = kubectl_base + ["get", "pods", "-n", "azure-arc", "-o", "json"]
            logger.info("Running: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                pods_data = json.loads(result.stdout)
                for pod in pods_data.get("items", []):
                    containers = pod.get("spec", {}).get("containers", [])
                    for container in containers:
                        if "arc" in container.get("name", "").lower():
                            image = container.get("image", "")
                            # Extract version from image tag
                            if ":" in image:
                                version = image.split(":")[-1]
                                cluster_data["versions"]["arcAgent"] = version
                                break
            else:
                logger.warning("No azure-arc namespace or pods: %s", result.stderr)
        except Exception as e:
            logger.error("Failed to get Arc agent version: %s", e)

        # 4. Try to get connected cluster info from Azure CLI
        try:
            # First try to get cluster name from azure-arc configmap
            cmd = kubectl_base + [
                "get",
                "configmap",
                "azure-clusterconfig",
                "-n",
                "azure-arc",
                "-o",
                "json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            cluster_name = None
            resource_group = None

            if result.returncode == 0:
                config_data = json.loads(result.stdout)
                data = config_data.get("data", {})
                cluster_name = data.get("AZURE_RESOURCE_NAME")
                resource_group = data.get("AZURE_RESOURCE_GROUP")

            # Get extensions if we have cluster info
            if cluster_name and resource_group:
                extensions = await self._get_cluster_extensions(cluster_name, resource_group)
                for ext in extensions:
                    ext_info = {
                        "name": ext.get("extensionType", ext.get("name", "unknown")),
                        "status": ext.get("provisioningState", "Unknown"),
                        "healthy": ext.get("provisioningState") == "Succeeded",
                        "version": ext.get("version"),
                    }
                    cluster_data["extensions"].append(ext_info)
        except Exception as e:
            logger.error("Failed to get extensions from Azure: %s", e)

        # 5. Check for Flux GitOps
        try:
            cmd = kubectl_base + ["get", "pods", "-n", "flux-system", "-o", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                pods_data = json.loads(result.stdout)
                flux_pods = pods_data.get("items", [])

                cluster_data["flux"]["installed"] = len(flux_pods) > 0

                # Get Flux version from source-controller
                for pod in flux_pods:
                    if "source-controller" in pod.get("metadata", {}).get("name", ""):
                        containers = pod.get("spec", {}).get("containers", [])
                        for container in containers:
                            image = container.get("image", "")
                            if ":" in image:
                                cluster_data["flux"]["version"] = image.split(":")[-1]
                                break

                # Count GitRepositories
                cmd_repos = kubectl_base + ["get", "gitrepositories", "-A", "--no-headers"]
                result_repos = subprocess.run(cmd_repos, capture_output=True, text=True, timeout=30)
                if result_repos.returncode == 0:
                    repos = [line for line in result_repos.stdout.strip().split("\n") if line]
                    cluster_data["flux"]["gitRepositories"] = len(repos)

                # Count Kustomizations
                cmd_kust = kubectl_base + ["get", "kustomizations", "-A", "--no-headers"]
                result_kust = subprocess.run(cmd_kust, capture_output=True, text=True, timeout=30)
                if result_kust.returncode == 0:
                    kusts = [line for line in result_kust.stdout.strip().split("\n") if line]
                    cluster_data["flux"]["kustomizations"] = len(kusts)

                # Check reconciliation status (simplified - check if all pods are Running)
                all_running = all(
                    pod.get("status", {}).get("phase") == "Running" for pod in flux_pods
                )
                cluster_data["flux"]["reconciled"] = all_running
            else:
                cluster_data["flux"]["installed"] = False
        except Exception as e:
            logger.error("Failed to check Flux status: %s", e)
            cluster_data["flux"]["installed"] = False

        logger.info(
            "Collected real cluster data: extensions=%d, cni=%s, k8s=%s, flux=%s",
            len(cluster_data["extensions"]),
            cluster_data["cni"].get("plugin", "unknown"),
            cluster_data["versions"].get("kubernetes", "unknown"),
            cluster_data["flux"].get("installed", False),
        )

        return cluster_data

    async def _list_connected_clusters(
        self, subscription: str | None = None
    ) -> list[dict[str, Any]]:
        """
        List REAL AKS Arc connected clusters from Azure.

        Uses az connectedk8s list to get actual cluster inventory.
        """
        try:
            cmd = ["az", "connectedk8s", "list", "-o", "json"]
            if subscription:
                cmd.extend(["--subscription", subscription])

            logger.info("Running: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                logger.error("az connectedk8s list failed: %s", result.stderr)
                return []

            clusters = json.loads(result.stdout)
            logger.info("Found %d connected clusters", len(clusters))
            return clusters

        except subprocess.TimeoutExpired:
            logger.error("az connectedk8s list timed out")
            return []
        except json.JSONDecodeError as e:
            logger.error("Failed to parse az output: %s", e)
            return []
        except Exception as e:
            logger.error("Error listing clusters: %s", e)
            return []

    async def _get_cluster_extensions(
        self, cluster_name: str, resource_group: str
    ) -> list[dict[str, Any]]:
        """Get extensions installed on a specific cluster."""
        try:
            cmd = [
                "az",
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                logger.warning("Failed to get extensions for %s: %s", cluster_name, result.stderr)
                return []

            return json.loads(result.stdout)

        except Exception as e:
            logger.error("Error getting extensions for %s: %s", cluster_name, e)
            return []

    async def _check_extensions(
        self, findings: dict[str, Any], cluster_data: dict[str, Any]
    ) -> None:
        """Check Arc extension presence and health."""
        start_time = time.time()
        extensions = cluster_data.get("extensions", [])
        extension_names = {ext.get("name") for ext in extensions}

        # Check for expected extensions
        for expected in self.EXPECTED_EXTENSIONS:
            check_id = f"aks.arc.extension.{expected.replace('.', '_')}"

            if expected not in extension_names:
                self.add_check(
                    findings,
                    check_id=check_id,
                    title=f"Arc Extension: {expected}",
                    severity="medium",
                    status="warn",
                    evidence={
                        "extension": expected,
                        "installed": False,
                    },
                    hint=f"Extension {expected} is not installed. Install via Azure Portal or CLI.",
                    sources=[self.get_source_ref("arc-extensions", "Arc Extensions")],
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            else:
                # Find extension details
                ext_data = next((e for e in extensions if e.get("name") == expected), {})
                healthy = ext_data.get("healthy", True)

                self.add_check(
                    findings,
                    check_id=check_id,
                    title=f"Arc Extension: {expected}",
                    severity="medium" if not healthy else "low",
                    status="pass" if healthy else "warn",
                    evidence={
                        "extension": expected,
                        "installed": True,
                        "status": ext_data.get("status"),
                        "healthy": healthy,
                    },
                    hint=(
                        f"Extension {expected} is unhealthy. Check extension logs."
                        if not healthy
                        else None
                    ),
                    sources=[self.get_source_ref("arc-extensions", "Arc Extensions")],
                    duration_ms=int((time.time() - start_time) * 1000),
                )

    async def _check_cni(self, findings: dict[str, Any], cluster_data: dict[str, Any]) -> None:
        """Check CNI configuration."""
        start_time = time.time()
        cni = cluster_data.get("cni", {})

        plugin = cni.get("plugin", "unknown")
        mode = cni.get("mode", "unknown")
        pod_cidr = cni.get("podCidr")

        # Validate CNI settings
        status = "pass"
        hint = None

        if plugin not in ["azure", "calico", "flannel"]:
            status = "warn"
            hint = f"CNI plugin '{plugin}' may not be fully supported. Recommended: azure, calico, flannel."

        self.add_check(
            findings,
            check_id="aks.arc.cni.config",
            title="CNI Configuration",
            severity="medium",
            status=status,
            evidence={
                "plugin": plugin,
                "mode": mode,
                "podCidr": pod_cidr,
            },
            hint=hint,
            sources=[self.get_source_ref("aks-arc-networking", "AKS Arc Networking")],
            duration_ms=int((time.time() - start_time) * 1000),
        )

    async def _check_versions(self, findings: dict[str, Any], cluster_data: dict[str, Any]) -> None:
        """Check version compatibility."""
        start_time = time.time()
        versions = cluster_data.get("versions", {})

        k8s_version = versions.get("kubernetes", "unknown")
        arc_version = versions.get("arcAgent", "unknown")

        # Simple version checks
        status = "pass"
        hint = None

        # Check Kubernetes version (simplified)
        if k8s_version.startswith("1.2"):
            major_minor = k8s_version.rsplit(".", 1)[0]
            minor = int(major_minor.split(".")[1]) if "." in major_minor else 0
            if minor < 26:
                status = "warn"
                hint = f"Kubernetes {k8s_version} is outdated. Consider upgrading to 1.28+."

        self.add_check(
            findings,
            check_id="aks.arc.versions",
            title="Version Compatibility",
            severity="medium",
            status=status,
            evidence=versions,
            hint=hint,
            sources=[self.get_source_ref("aks-arc-versions", "AKS Arc Supported Versions")],
            duration_ms=int((time.time() - start_time) * 1000),
        )

    async def _check_flux(self, findings: dict[str, Any], cluster_data: dict[str, Any]) -> None:
        """Check Flux GitOps configuration."""
        start_time = time.time()
        flux = cluster_data.get("flux", {})

        installed = flux.get("installed", False)
        reconciled = flux.get("reconciled", False)

        if not installed:
            self.add_check(
                findings,
                check_id="aks.arc.flux",
                title="Flux GitOps",
                severity="low",
                status="skipped",
                evidence={"installed": False},
                hint="Flux is not installed. Install if GitOps is required.",
                sources=[self.get_source_ref("arc-gitops", "Arc GitOps with Flux")],
                duration_ms=int((time.time() - start_time) * 1000),
            )
            return

        status = "pass" if reconciled else "warn"
        hint = None if reconciled else "Flux sources are not reconciled. Check Flux logs."

        self.add_check(
            findings,
            check_id="aks.arc.flux",
            title="Flux GitOps",
            severity="medium",
            status=status,
            evidence={
                "installed": installed,
                "version": flux.get("version"),
                "gitRepositories": flux.get("gitRepositories"),
                "kustomizations": flux.get("kustomizations"),
                "reconciled": reconciled,
            },
            hint=hint,
            sources=[self.get_source_ref("arc-gitops", "Arc GitOps with Flux")],
            duration_ms=int((time.time() - start_time) * 1000),
        )
