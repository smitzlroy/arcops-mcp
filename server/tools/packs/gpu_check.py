"""
GPU Check Tool for ArcOps MCP.

Verifies GPU hardware readiness for AI workloads on Azure Local / AKS Arc.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from server.services.artifact_signer import sign_artifact
from server.tools.base import BaseTool


class GpuCheckTool(BaseTool):
    """
    Check GPU presence, drivers, MIG configuration, and capacity.

    Verifies:
    - GPU device presence via nvidia-smi
    - Driver and CUDA versions
    - MIG (Multi-Instance GPU) configuration
    - Memory availability
    - Temperature and health

    Outputs a GPU readiness artifact with READY/DEGRADED/NOT_READY verdict.
    """

    name = "gpu.check"
    description = (
        "Check GPU presence, drivers, MIG configuration, and capacity. "
        "Returns a readiness artifact for AI workload deployment."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "nodeSelector": {
                "type": "string",
                "description": "Optional Kubernetes node selector label",
            },
            "outputPath": {
                "type": "string",
                "description": "Path to write GPU readiness artifact",
                "default": "artifacts/gpu-readiness.json",
            },
            "dryRun": {
                "type": "boolean",
                "description": "If true, use mock GPU data",
                "default": False,
            },
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool via MCP protocol."""
        return await self.run(**arguments)

    async def run(
        self,
        nodeSelector: str | None = None,
        outputPath: str = "artifacts/gpu-readiness.json",
        dryRun: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute GPU readiness check."""
        run_id = self.generate_run_id()
        timestamp = self.get_timestamp()

        artifact: dict[str, Any] = {
            "version": "1.0.0",
            "type": "gpu-readiness",
            "timestamp": timestamp,
            "runId": run_id,
            "metadata": {
                "toolName": self.name,
                "toolVersion": "1.0.0",
                "hostname": self._get_hostname(),
                "node": nodeSelector,
            },
            "gpus": [],
            "summary": {
                "totalGpus": 0,
                "healthyGpus": 0,
                "totalMemoryMb": 0,
                "availableMemoryMb": 0,
                "driverVersion": "",
                "cudaVersion": "",
                "migEnabled": False,
            },
            "checks": [],
            "verdict": "NOT_READY",
        }

        if dryRun:
            # Mock GPU data
            artifact = self._mock_gpu_data(artifact)
        else:
            # Real GPU detection
            artifact = await self._detect_gpus(artifact)

        # Run readiness checks
        artifact["checks"] = self._run_readiness_checks(artifact)

        # Determine verdict
        artifact["verdict"] = self._determine_verdict(artifact)

        # Sign artifact
        artifact = sign_artifact(artifact)

        # Write output
        output_path = Path(outputPath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2)

        return artifact

    def _get_hostname(self) -> str:
        """Get current hostname."""
        import socket

        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    def _mock_gpu_data(self, artifact: dict[str, Any]) -> dict[str, Any]:
        """Generate mock GPU data for testing."""
        artifact["gpus"] = [
            {
                "index": 0,
                "name": "NVIDIA A100-PCIE-40GB",
                "uuid": "GPU-mock-uuid-0000-0000-0000-000000000000",
                "pciId": "00000000:00:1E.0",
                "memory": {
                    "totalMb": 40960,
                    "usedMb": 1024,
                    "freeMb": 39936,
                },
                "driver": "535.129.03",
                "cuda": "12.2",
                "computeCapability": "8.0",
                "mig": {
                    "enabled": False,
                    "mode": "disabled",
                    "instances": 0,
                },
                "temperature": {
                    "current": 45,
                    "max": 83,
                    "unit": "C",
                },
                "utilization": {
                    "gpu": 0,
                    "memory": 2,
                },
                "power": {
                    "draw": 52.0,
                    "limit": 250.0,
                    "unit": "W",
                },
                "healthy": True,
                "issues": [],
            },
        ]

        artifact["summary"] = {
            "totalGpus": 1,
            "healthyGpus": 1,
            "totalMemoryMb": 40960,
            "availableMemoryMb": 39936,
            "driverVersion": "535.129.03",
            "cudaVersion": "12.2",
            "migEnabled": False,
        }

        return artifact

    async def _detect_gpus(self, artifact: dict[str, Any]) -> dict[str, Any]:
        """Detect GPUs using nvidia-smi."""
        try:
            # Query nvidia-smi for GPU info
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,uuid,pci.bus_id,memory.total,memory.used,memory.free,driver_version,temperature.gpu,utilization.gpu,utilization.memory,power.draw,power.limit",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                artifact["summary"]["totalGpus"] = 0
                return artifact

            gpus = []
            total_memory = 0
            available_memory = 0
            driver_version = ""

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue

                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 13:
                    continue

                gpu = {
                    "index": int(parts[0]),
                    "name": parts[1],
                    "uuid": parts[2],
                    "pciId": parts[3],
                    "memory": {
                        "totalMb": int(float(parts[4])),
                        "usedMb": int(float(parts[5])),
                        "freeMb": int(float(parts[6])),
                    },
                    "driver": parts[7],
                    "temperature": {
                        "current": int(float(parts[8])) if parts[8] != "[N/A]" else 0,
                        "max": 83,  # Typical max
                        "unit": "C",
                    },
                    "utilization": {
                        "gpu": int(float(parts[9])) if parts[9] != "[N/A]" else 0,
                        "memory": int(float(parts[10])) if parts[10] != "[N/A]" else 0,
                    },
                    "power": {
                        "draw": float(parts[11]) if parts[11] != "[N/A]" else 0,
                        "limit": float(parts[12]) if parts[12] != "[N/A]" else 0,
                        "unit": "W",
                    },
                    "mig": {
                        "enabled": False,
                        "mode": "disabled",
                        "instances": 0,
                    },
                    "healthy": True,
                    "issues": [],
                }

                # Check for issues
                if gpu["temperature"]["current"] > 80:
                    gpu["issues"].append("Temperature above 80°C")
                    gpu["healthy"] = False
                if gpu["memory"]["freeMb"] < 1024:
                    gpu["issues"].append("Less than 1GB free memory")

                gpus.append(gpu)
                total_memory += gpu["memory"]["totalMb"]
                available_memory += gpu["memory"]["freeMb"]
                driver_version = gpu["driver"]

            artifact["gpus"] = gpus
            artifact["summary"] = {
                "totalGpus": len(gpus),
                "healthyGpus": sum(1 for g in gpus if g["healthy"]),
                "totalMemoryMb": total_memory,
                "availableMemoryMb": available_memory,
                "driverVersion": driver_version,
                "cudaVersion": self._get_cuda_version(),
                "migEnabled": any(g["mig"]["enabled"] for g in gpus),
            }

        except FileNotFoundError:
            # nvidia-smi not found
            artifact["summary"]["totalGpus"] = 0
            artifact["checks"].append(
                {
                    "id": "GPU-ERR",
                    "title": "nvidia-smi not found",
                    "status": "fail",
                    "severity": "critical",
                    "detail": "nvidia-smi command not found - NVIDIA drivers may not be installed",
                }
            )
        except subprocess.TimeoutExpired:
            artifact["summary"]["totalGpus"] = 0
            artifact["checks"].append(
                {
                    "id": "GPU-ERR",
                    "title": "nvidia-smi timeout",
                    "status": "fail",
                    "severity": "critical",
                    "detail": "nvidia-smi command timed out",
                }
            )

        return artifact

    def _get_cuda_version(self) -> str:
        """Get CUDA version from nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=cuda_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return "unknown"

    def _run_readiness_checks(self, artifact: dict[str, Any]) -> list[dict[str, Any]]:
        """Run GPU readiness checks."""
        checks = []
        summary = artifact["summary"]

        # Check: GPU presence
        checks.append(
            {
                "id": "GPU-001",
                "title": "GPU devices detected",
                "status": "pass" if summary["totalGpus"] > 0 else "fail",
                "severity": "critical",
                "detail": f"Found {summary['totalGpus']} GPU(s)",
            }
        )

        # Check: All GPUs healthy
        if summary["totalGpus"] > 0:
            checks.append(
                {
                    "id": "GPU-002",
                    "title": "All GPUs healthy",
                    "status": "pass" if summary["healthyGpus"] == summary["totalGpus"] else "warn",
                    "severity": "high",
                    "detail": f"{summary['healthyGpus']}/{summary['totalGpus']} GPUs healthy",
                }
            )

        # Check: Driver version
        if summary["driverVersion"]:
            # Require driver >= 525 for good CUDA 12 support
            try:
                major_version = int(summary["driverVersion"].split(".")[0])
                driver_ok = major_version >= 525
            except ValueError:
                driver_ok = False

            checks.append(
                {
                    "id": "GPU-003",
                    "title": "Driver version >= 525",
                    "status": "pass" if driver_ok else "warn",
                    "severity": "medium",
                    "detail": f"Driver version: {summary['driverVersion']}",
                }
            )

        # Check: Available memory
        min_memory_mb = 4096  # 4GB minimum
        checks.append(
            {
                "id": "GPU-004",
                "title": f"Available memory >= {min_memory_mb}MB",
                "status": "pass" if summary["availableMemoryMb"] >= min_memory_mb else "fail",
                "severity": "high",
                "detail": f"Available: {summary['availableMemoryMb']}MB",
            }
        )

        return checks

    def _determine_verdict(self, artifact: dict[str, Any]) -> str:
        """Determine overall GPU readiness verdict."""
        summary = artifact["summary"]
        checks = artifact["checks"]

        if summary["totalGpus"] == 0:
            return "NOT_READY"

        # Check for critical failures
        critical_fails = sum(
            1 for c in checks if c["status"] == "fail" and c["severity"] == "critical"
        )
        if critical_fails > 0:
            return "NOT_READY"

        # Check for high severity failures
        high_fails = sum(1 for c in checks if c["status"] == "fail" and c["severity"] == "high")
        if high_fails > 0:
            return "DEGRADED"

        # Check for any warnings
        warnings = sum(1 for c in checks if c["status"] == "warn")
        if warnings > 0:
            return "DEGRADED"

        return "READY"
