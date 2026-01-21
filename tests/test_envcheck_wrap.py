"""
Tests for the Azure Local Environment Checker wrapper tool.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.tools.azlocal_envcheck_wrap import AzLocalEnvCheckWrapTool


@pytest.fixture
def tool() -> AzLocalEnvCheckWrapTool:
    """Create a tool instance for testing."""
    return AzLocalEnvCheckWrapTool()


@pytest.fixture
def sample_fixture() -> dict:
    """Load the sample fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "envcheck_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestAzLocalEnvCheckWrapTool:
    """Tests for AzLocalEnvCheckWrapTool."""

    @pytest.mark.asyncio
    async def test_execute_dry_run(self, tool: AzLocalEnvCheckWrapTool) -> None:
        """Test execution in dry run mode."""
        result = await tool.execute({"dryRun": True, "mode": "quick"})

        assert result is not None
        assert result["version"] == "0.1.0"
        assert result["target"] == "host"
        assert "checks" in result
        assert "summary" in result
        assert result["metadata"]["simulated"] is True

    @pytest.mark.asyncio
    async def test_execute_full_mode(self, tool: AzLocalEnvCheckWrapTool) -> None:
        """Test execution in full mode."""
        result = await tool.execute({"dryRun": True, "mode": "full"})

        assert result["metadata"]["mode"] == "full"

    @pytest.mark.asyncio
    async def test_findings_structure(self, tool: AzLocalEnvCheckWrapTool) -> None:
        """Test that findings conform to expected structure."""
        result = await tool.execute({"dryRun": True})

        # Check required fields
        assert "version" in result
        assert "target" in result
        assert "timestamp" in result
        assert "runId" in result
        assert "checks" in result
        assert "summary" in result

        # Check summary structure
        summary = result["summary"]
        assert "total" in summary
        assert "pass" in summary
        assert "fail" in summary
        assert "warn" in summary
        assert "skipped" in summary

    @pytest.mark.asyncio
    async def test_checks_have_required_fields(self, tool: AzLocalEnvCheckWrapTool) -> None:
        """Test that all checks have required fields."""
        result = await tool.execute({"dryRun": True})

        for check in result["checks"]:
            assert "id" in check
            assert "title" in check
            assert "severity" in check
            assert "status" in check
            assert check["severity"] in ["high", "medium", "low"]
            assert check["status"] in ["pass", "fail", "warn", "skipped"]

    @pytest.mark.asyncio
    async def test_summary_counts_match_checks(self, tool: AzLocalEnvCheckWrapTool) -> None:
        """Test that summary counts match actual check counts."""
        result = await tool.execute({"dryRun": True})

        checks = result["checks"]
        summary = result["summary"]

        # Count actual statuses
        status_counts = {"pass": 0, "fail": 0, "warn": 0, "skipped": 0}
        for check in checks:
            status = check["status"]
            if status in status_counts:
                status_counts[status] += 1

        assert summary["total"] == len(checks)
        assert summary["pass"] == status_counts["pass"]
        assert summary["fail"] == status_counts["fail"]
        assert summary["warn"] == status_counts["warn"]
        assert summary["skipped"] == status_counts["skipped"]

    @pytest.mark.asyncio
    async def test_raw_output_included_when_requested(
        self, tool: AzLocalEnvCheckWrapTool
    ) -> None:
        """Test that raw output is included when requested."""
        result = await tool.execute({"dryRun": True, "rawOutput": True})

        assert "rawOutput" in result["metadata"]

    @pytest.mark.asyncio
    async def test_sources_reference_docs(self, tool: AzLocalEnvCheckWrapTool) -> None:
        """Test that sources reference docs/SOURCES.md."""
        result = await tool.execute({"dryRun": True})

        for check in result["checks"]:
            if "sources" in check:
                for source in check["sources"]:
                    assert "type" in source
                    assert "label" in source
                    # Sources should reference SOURCES.md
                    if "url" in source:
                        assert "SOURCES.md" in source["url"]

    def test_tool_metadata(self, tool: AzLocalEnvCheckWrapTool) -> None:
        """Test tool has correct metadata."""
        assert tool.name == "azlocal.envcheck.wrap"
        assert tool.description is not None
        assert len(tool.description) > 0
        assert tool.input_schema is not None
