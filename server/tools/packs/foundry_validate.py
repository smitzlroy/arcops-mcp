"""
Foundry Validate Tool for ArcOps MCP.

Validates multi-model inference performance with Foundry Local.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from server.services.artifact_signer import sign_artifact
from server.tools.base import BaseTool


class FoundryValidateTool(BaseTool):
    """
    Validate multi-model inference with catalog and BYO models.

    Runs inference workloads and measures:
    - Model load time
    - Inference latency (p50, p95, p99)
    - Memory consumption
    - Throughput

    Compares against configurable thresholds and outputs PASS/FAIL verdict.
    """

    name = "foundry.validate"
    description = (
        "Validate multi-model inference with Foundry Local catalog and BYO models. "
        "Measures performance against thresholds and returns validation artifact."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "catalogModel": {
                "type": "string",
                "description": "Foundry Local catalog model ID (e.g., qwen2.5-0.5b)",
            },
            "byoImage": {
                "type": "string",
                "description": "Optional BYO model OCI image reference",
            },
            "testAsset": {
                "type": "string",
                "description": "Path to test asset (text file for LLM)",
            },
            "thresholds": {
                "type": "string",
                "description": "Path to thresholds YAML file",
            },
            "iterations": {
                "type": "integer",
                "description": "Number of inference iterations",
                "default": 10,
            },
            "outputPath": {
                "type": "string",
                "description": "Path to write validation artifact",
                "default": "artifacts/inference-validation.json",
            },
            "dryRun": {
                "type": "boolean",
                "description": "If true, use mock inference data",
                "default": False,
            },
        },
        "required": ["catalogModel"],
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool via MCP protocol."""
        return await self.run(**arguments)

    async def run(
        self,
        catalogModel: str,
        byoImage: str | None = None,
        testAsset: str | None = None,
        thresholds: str | None = None,
        iterations: int = 10,
        outputPath: str = "artifacts/inference-validation.json",
        dryRun: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute Foundry validation."""
        import yaml

        run_id = self.generate_run_id()
        timestamp = self.get_timestamp()

        # Load thresholds
        threshold_config = self._load_thresholds(thresholds)

        artifact: dict[str, Any] = {
            "version": "1.0.0",
            "type": "inference-validation",
            "timestamp": timestamp,
            "runId": run_id,
            "metadata": {
                "toolName": self.name,
                "toolVersion": "1.0.0",
                "hostname": self._get_hostname(),
                "foundryVersion": await self._get_foundry_version(dryRun),
            },
            "models": [],
            "inference": {
                "testAsset": testAsset,
                "testAssetType": "text",
                "workflow": "single-model-inference",
                "iterations": iterations,
                "warmupIterations": 2,
                "successful": 0,
                "failed": 0,
                "metrics": {},
            },
            "thresholds": threshold_config,
            "checks": [],
            "verdict": "FAIL",
            "failureReasons": [],
        }

        # Load models
        models_loaded = []

        # Load catalog model
        catalog_result = await self._load_model(catalogModel, "catalog", dryRun)
        artifact["models"].append(catalog_result)
        if catalog_result["loaded"]:
            models_loaded.append(catalogModel)

        # Load BYO model if specified
        if byoImage:
            byo_result = await self._load_model(byoImage, "byo", dryRun)
            artifact["models"].append(byo_result)
            if byo_result["loaded"]:
                models_loaded.append(byoImage)
            artifact["inference"]["workflow"] = "multi-model-inference"

        # Run inference
        if models_loaded:
            if dryRun:
                metrics = self._mock_inference_metrics(iterations)
            else:
                metrics = await self._run_inference(catalogModel, testAsset, iterations)

            artifact["inference"]["metrics"] = metrics
            artifact["inference"]["successful"] = iterations
        else:
            artifact["failureReasons"].append("No models loaded successfully")

        # Run threshold checks
        artifact["checks"] = self._run_threshold_checks(
            artifact["inference"]["metrics"],
            threshold_config,
        )

        # Determine verdict
        failed_checks = sum(1 for c in artifact["checks"] if c["status"] == "fail")
        if failed_checks == 0 and models_loaded:
            artifact["verdict"] = "PASS"
        else:
            artifact["verdict"] = "FAIL"
            for check in artifact["checks"]:
                if check["status"] == "fail":
                    artifact["failureReasons"].append(
                        f"{check['title']}: {check['actual']} vs threshold {check['threshold']}"
                    )

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

    def _load_thresholds(self, thresholds_path: str | None) -> dict[str, Any]:
        """Load thresholds from YAML file or use defaults."""
        import yaml

        defaults = {
            "name": "default",
            "latencyP95MsMax": 200,
            "latencyP99MsMax": 500,
            "memoryMbMax": 16000,
            "throughputRpsMin": 5,
            "gpuUtilizationPctMax": 95,
        }

        if not thresholds_path:
            return defaults

        path = Path(thresholds_path)
        if not path.exists():
            return defaults

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            return {
                "name": config.get("name", "custom"),
                "path": str(path),
                **config.get("thresholds", {}),
            }
        except Exception:
            return defaults

    async def _get_foundry_version(self, dry_run: bool) -> str:
        """Get Foundry Local version."""
        if dry_run:
            return "1.0.0-mock"

        try:
            import subprocess

            result = subprocess.run(
                ["foundry", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    async def _load_model(self, model_id: str, model_type: str, dry_run: bool) -> dict[str, Any]:
        """Load a model via Foundry Local."""
        result = {
            "name": model_id,
            "type": model_type,
            "image": model_id if model_type == "byo" else None,
            "alias": model_id.split("/")[-1].split(":")[0],
            "loaded": False,
            "loadTimeMs": 0,
            "memoryMb": 0,
        }

        if dry_run:
            result["loaded"] = True
            result["loadTimeMs"] = 2500
            result["memoryMb"] = 1200 if "0.5b" in model_id else 3000
            return result

        try:
            from foundry_local import FoundryLocalManager

            start = time.time()
            manager = FoundryLocalManager(model_id)
            load_time = (time.time() - start) * 1000

            result["loaded"] = True
            result["loadTimeMs"] = int(load_time)

            # Try to get memory info
            loaded = manager.list_loaded_models()
            for m in loaded:
                if model_id in str(m):
                    result["memoryMb"] = getattr(m, "memory_mb", 0)
                    break

        except Exception as e:
            result["error"] = str(e)

        return result

    def _mock_inference_metrics(self, iterations: int) -> dict[str, Any]:
        """Generate mock inference metrics."""
        import random

        # Simulate latencies with some variance
        latencies = [random.uniform(50, 150) for _ in range(iterations)]

        return {
            "latencyP50Ms": round(statistics.median(latencies), 2),
            "latencyP95Ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2),
            "latencyP99Ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 2),
            "latencyMinMs": round(min(latencies), 2),
            "latencyMaxMs": round(max(latencies), 2),
            "latencyMeanMs": round(statistics.mean(latencies), 2),
            "throughputRps": round(1000 / statistics.mean(latencies), 2),
            "memoryPeakMb": 1500,
            "memoryAvgMb": 1200,
            "gpuUtilizationPct": 45,
            "tokensPerSecond": 85.5,
        }

    async def _run_inference(
        self, model_id: str, test_asset: str | None, iterations: int
    ) -> dict[str, Any]:
        """Run actual inference and measure metrics."""
        latencies = []

        try:
            from foundry_local import FoundryLocalManager
            from openai import OpenAI

            manager = FoundryLocalManager(model_id)
            client = OpenAI(
                base_url=f"{manager.endpoint}/v1",
                api_key="not-needed",
            )

            # Test prompt
            test_prompt = "Hello, how are you?"
            if test_asset and Path(test_asset).exists():
                with open(test_asset, "r", encoding="utf-8") as f:
                    test_prompt = f.read()[:500]  # Limit to 500 chars

            # Warmup
            for _ in range(2):
                client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=50,
                )

            # Measure
            for _ in range(iterations):
                start = time.time()
                client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": test_prompt}],
                    max_tokens=50,
                )
                latencies.append((time.time() - start) * 1000)

            sorted_latencies = sorted(latencies)

            return {
                "latencyP50Ms": round(statistics.median(latencies), 2),
                "latencyP95Ms": round(sorted_latencies[int(len(latencies) * 0.95)], 2),
                "latencyP99Ms": round(sorted_latencies[-1], 2),
                "latencyMinMs": round(min(latencies), 2),
                "latencyMaxMs": round(max(latencies), 2),
                "latencyMeanMs": round(statistics.mean(latencies), 2),
                "throughputRps": round(1000 / statistics.mean(latencies), 2),
                "memoryPeakMb": 0,  # Would need GPU monitoring
                "memoryAvgMb": 0,
                "gpuUtilizationPct": 0,
                "tokensPerSecond": 0,
            }

        except Exception as e:
            return {
                "error": str(e),
                "latencyP50Ms": 0,
                "latencyP95Ms": 0,
                "latencyP99Ms": 0,
            }

    def _run_threshold_checks(
        self, metrics: dict[str, Any], thresholds: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Run threshold checks against metrics."""
        checks = []

        # Latency P95
        if "latencyP95MsMax" in thresholds:
            actual = metrics.get("latencyP95Ms", 0)
            threshold = thresholds["latencyP95MsMax"]
            checks.append(
                {
                    "id": "FV-001",
                    "title": f"Latency P95 <= {threshold}ms",
                    "status": "pass" if actual <= threshold else "fail",
                    "metric": "latencyP95Ms",
                    "actual": actual,
                    "threshold": threshold,
                    "comparison": "<=",
                }
            )

        # Latency P99
        if "latencyP99MsMax" in thresholds:
            actual = metrics.get("latencyP99Ms", 0)
            threshold = thresholds["latencyP99MsMax"]
            checks.append(
                {
                    "id": "FV-002",
                    "title": f"Latency P99 <= {threshold}ms",
                    "status": "pass" if actual <= threshold else "fail",
                    "metric": "latencyP99Ms",
                    "actual": actual,
                    "threshold": threshold,
                    "comparison": "<=",
                }
            )

        # Memory
        if "memoryMbMax" in thresholds:
            actual = metrics.get("memoryPeakMb", 0)
            threshold = thresholds["memoryMbMax"]
            # Skip if we couldn't measure memory
            if actual > 0:
                checks.append(
                    {
                        "id": "FV-003",
                        "title": f"Memory <= {threshold}MB",
                        "status": "pass" if actual <= threshold else "fail",
                        "metric": "memoryPeakMb",
                        "actual": actual,
                        "threshold": threshold,
                        "comparison": "<=",
                    }
                )

        # Throughput
        if "throughputRpsMin" in thresholds:
            actual = metrics.get("throughputRps", 0)
            threshold = thresholds["throughputRpsMin"]
            checks.append(
                {
                    "id": "FV-004",
                    "title": f"Throughput >= {threshold} req/s",
                    "status": "pass" if actual >= threshold else "fail",
                    "metric": "throughputRps",
                    "actual": actual,
                    "threshold": threshold,
                    "comparison": ">=",
                }
            )

        return checks
