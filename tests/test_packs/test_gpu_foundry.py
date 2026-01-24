"""
Tests for GPU Check and Foundry Validate Tools.

Tests GPU hardware detection and inference validation.
"""

import json
import pytest
from pathlib import Path

import yaml

from server.tools.packs.gpu_check import GpuCheckTool
from server.tools.packs.foundry_validate import FoundryValidateTool


@pytest.fixture
def gpu_tool():
    """Create GpuCheckTool instance."""
    return GpuCheckTool()


@pytest.fixture
def foundry_tool():
    """Create FoundryValidateTool instance."""
    return FoundryValidateTool()


@pytest.fixture
def thresholds_path(tmp_path):
    """Create thresholds YAML file."""
    thresholds = {
        "name": "test-thresholds",
        "thresholds": {
            "latencyP95MsMax": 200,
            "latencyP99MsMax": 500,
            "memoryMbMax": 16000,
            "throughputRpsMin": 5,
        },
    }

    thresholds_file = tmp_path / "thresholds.yaml"
    with open(thresholds_file, "w") as f:
        yaml.dump(thresholds, f)

    return str(thresholds_file)


@pytest.fixture
def strict_thresholds_path(tmp_path):
    """Create strict thresholds that will fail."""
    thresholds = {
        "name": "strict-thresholds",
        "thresholds": {
            "latencyP95MsMax": 10,  # Very strict - will fail
            "throughputRpsMin": 1000,  # Very strict - will fail
        },
    }

    thresholds_file = tmp_path / "strict-thresholds.yaml"
    with open(thresholds_file, "w") as f:
        yaml.dump(thresholds, f)

    return str(thresholds_file)


@pytest.fixture
def output_path(tmp_path):
    """Create temp output path."""
    return str(tmp_path / "output.json")


class TestGpuCheckTool:
    """Test suite for GpuCheckTool."""

    @pytest.mark.asyncio
    async def test_tool_metadata(self, gpu_tool):
        """Test tool has correct metadata."""
        assert gpu_tool.name == "gpu.check"
        assert "GPU" in gpu_tool.description or "gpu" in gpu_tool.description.lower()
        assert "outputPath" in gpu_tool.input_schema["properties"]

    @pytest.mark.asyncio
    async def test_dry_run_returns_mock_gpu(self, gpu_tool, output_path):
        """Test dry run returns mock GPU data."""
        result = await gpu_tool.run(
            outputPath=output_path,
            dryRun=True,
        )

        assert result["version"] == "1.0.0"
        assert result["type"] == "gpu-readiness"
        assert result["verdict"] == "READY"
        assert len(result["gpus"]) == 1
        assert "artifactHash" in result

    @pytest.mark.asyncio
    async def test_mock_gpu_has_expected_fields(self, gpu_tool, output_path):
        """Test mock GPU data has all expected fields."""
        result = await gpu_tool.run(
            outputPath=output_path,
            dryRun=True,
        )

        gpu = result["gpus"][0]

        assert "index" in gpu
        assert "name" in gpu
        assert "uuid" in gpu
        assert "memory" in gpu
        assert "totalMb" in gpu["memory"]
        assert "freeMb" in gpu["memory"]
        assert "driver" in gpu
        assert "healthy" in gpu

    @pytest.mark.asyncio
    async def test_summary_calculated(self, gpu_tool, output_path):
        """Test summary is calculated correctly."""
        result = await gpu_tool.run(
            outputPath=output_path,
            dryRun=True,
        )

        summary = result["summary"]

        assert summary["totalGpus"] == len(result["gpus"])
        assert summary["healthyGpus"] <= summary["totalGpus"]
        assert "totalMemoryMb" in summary
        assert "driverVersion" in summary

    @pytest.mark.asyncio
    async def test_readiness_checks_run(self, gpu_tool, output_path):
        """Test readiness checks are executed."""
        result = await gpu_tool.run(
            outputPath=output_path,
            dryRun=True,
        )

        assert "checks" in result
        assert len(result["checks"]) > 0

        # Check for expected check IDs
        check_ids = [c["id"] for c in result["checks"]]
        assert "GPU-001" in check_ids  # GPU presence check

    @pytest.mark.asyncio
    async def test_artifact_written_to_file(self, gpu_tool, output_path):
        """Test artifact is written to output file."""
        await gpu_tool.run(
            outputPath=output_path,
            dryRun=True,
        )

        assert Path(output_path).exists()

        with open(output_path, "r") as f:
            saved = json.load(f)

        assert saved["type"] == "gpu-readiness"

    @pytest.mark.asyncio
    async def test_verdict_ready_when_healthy(self, gpu_tool, output_path):
        """Test verdict is READY when GPU is healthy."""
        result = await gpu_tool.run(
            outputPath=output_path,
            dryRun=True,
        )

        assert result["verdict"] == "READY"
        assert result["gpus"][0]["healthy"] is True


class TestFoundryValidateTool:
    """Test suite for FoundryValidateTool."""

    @pytest.mark.asyncio
    async def test_tool_metadata(self, foundry_tool):
        """Test tool has correct metadata."""
        assert foundry_tool.name == "foundry.validate"
        assert "inference" in foundry_tool.description.lower()
        assert "catalogModel" in foundry_tool.input_schema["properties"]

    @pytest.mark.asyncio
    async def test_dry_run_with_catalog_model(self, foundry_tool, thresholds_path, output_path):
        """Test dry run with catalog model."""
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            thresholds=thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )

        assert result["version"] == "1.0.0"
        assert result["type"] == "inference-validation"
        assert result["verdict"] == "PASS"
        assert "artifactHash" in result

    @pytest.mark.asyncio
    async def test_model_info_captured(self, foundry_tool, thresholds_path, output_path):
        """Test model information is captured."""
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            thresholds=thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )

        assert len(result["models"]) >= 1

        model = result["models"][0]
        assert model["name"] == "qwen2.5-0.5b"
        assert model["type"] == "catalog"
        assert model["loaded"] is True

    @pytest.mark.asyncio
    async def test_byo_model_included(self, foundry_tool, thresholds_path, output_path):
        """Test BYO model is included when specified."""
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            byoImage="oci://registry.local/models/custom:1.0",
            thresholds=thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )

        assert len(result["models"]) == 2

        byo_model = next(m for m in result["models"] if m["type"] == "byo")
        assert byo_model["name"] == "oci://registry.local/models/custom:1.0"

    @pytest.mark.asyncio
    async def test_metrics_calculated(self, foundry_tool, thresholds_path, output_path):
        """Test inference metrics are calculated."""
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            thresholds=thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )

        metrics = result["inference"]["metrics"]

        assert "latencyP50Ms" in metrics
        assert "latencyP95Ms" in metrics
        assert "latencyP99Ms" in metrics
        assert "throughputRps" in metrics
        assert metrics["latencyP95Ms"] > 0

    @pytest.mark.asyncio
    async def test_threshold_checks_run(self, foundry_tool, thresholds_path, output_path):
        """Test threshold checks are executed."""
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            thresholds=thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )

        assert "checks" in result
        assert len(result["checks"]) > 0

        # All checks should pass with reasonable thresholds
        for check in result["checks"]:
            assert check["status"] in ["pass", "fail", "skip"]

    @pytest.mark.asyncio
    async def test_strict_thresholds_cause_failure(
        self, foundry_tool, strict_thresholds_path, output_path
    ):
        """Test that strict thresholds cause FAIL verdict."""
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            thresholds=strict_thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )

        assert result["verdict"] == "FAIL"
        assert len(result["failureReasons"]) > 0

    @pytest.mark.asyncio
    async def test_default_thresholds_used(self, foundry_tool, output_path):
        """Test default thresholds are used when not specified."""
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            thresholds=None,
            outputPath=output_path,
            dryRun=True,
        )

        assert result["thresholds"]["name"] == "default"
        assert "latencyP95MsMax" in result["thresholds"]

    @pytest.mark.asyncio
    async def test_artifact_written_to_file(self, foundry_tool, thresholds_path, output_path):
        """Test artifact is written to output file."""
        await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            thresholds=thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )

        assert Path(output_path).exists()

        with open(output_path, "r") as f:
            saved = json.load(f)

        assert saved["type"] == "inference-validation"

    @pytest.mark.asyncio
    async def test_workflow_type_set(self, foundry_tool, thresholds_path, output_path):
        """Test workflow type is set correctly."""
        # Single model
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            thresholds=thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )
        assert result["inference"]["workflow"] == "single-model-inference"

        # Multi model
        result = await foundry_tool.run(
            catalogModel="qwen2.5-0.5b",
            byoImage="oci://registry.local/models/custom:1.0",
            thresholds=thresholds_path,
            outputPath=output_path,
            dryRun=True,
        )
        assert result["inference"]["workflow"] == "multi-model-inference"
