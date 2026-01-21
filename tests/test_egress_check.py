"""
Tests for the Arc Gateway Egress Check tool.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.tools.arc_gateway_egress_check import ArcGatewayEgressCheckTool


@pytest.fixture
def tool() -> ArcGatewayEgressCheckTool:
    """Create a tool instance for testing."""
    return ArcGatewayEgressCheckTool()


@pytest.fixture
def egress_fixture() -> dict:
    """Load the egress fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "egress_ok.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestArcGatewayEgressCheckTool:
    """Tests for ArcGatewayEgressCheckTool."""

    @pytest.mark.asyncio
    async def test_execute_dry_run(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test execution in dry run mode."""
        result = await tool.execute({"dryRun": True})

        assert result is not None
        assert result["version"] == "0.1.0"
        assert result["target"] == "gateway"
        assert "checks" in result
        assert "summary" in result
        assert result["metadata"]["dryRun"] is True

    @pytest.mark.asyncio
    async def test_findings_structure(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test that findings conform to expected structure."""
        result = await tool.execute({"dryRun": True})

        # Check required fields
        assert "version" in result
        assert "target" in result
        assert "timestamp" in result
        assert "runId" in result
        assert "checks" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_checks_have_required_fields(self, tool: ArcGatewayEgressCheckTool) -> None:
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
    async def test_check_ids_follow_convention(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test that check IDs follow naming convention."""
        result = await tool.execute({"dryRun": True})

        for check in result["checks"]:
            # IDs should start with arc.gateway
            assert check["id"].startswith("arc.gateway.")

    @pytest.mark.asyncio
    async def test_evidence_contains_endpoint_info(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test that evidence contains endpoint information."""
        result = await tool.execute({"dryRun": True})

        for check in result["checks"]:
            if "evidence" in check:
                evidence = check["evidence"]
                # Should have FQDN and port info
                assert "fqdn" in evidence
                assert "port" in evidence

    @pytest.mark.asyncio
    async def test_category_filter(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test filtering by category."""
        result = await tool.execute({
            "dryRun": True,
            "categories": ["azure-arc"],
        })

        for check in result["checks"]:
            if "evidence" in check:
                # All checks should be from azure-arc category
                assert check["evidence"].get("category") == "azure-arc"

    @pytest.mark.asyncio
    async def test_required_only_filter(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test filtering for required endpoints only."""
        result = await tool.execute({
            "dryRun": True,
            "requiredOnly": True,
        })

        for check in result["checks"]:
            if "evidence" in check:
                # All checks should be for required endpoints
                assert check["evidence"].get("required", False) is True

    @pytest.mark.asyncio
    async def test_endpoint_count_in_metadata(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test that endpoint count is in metadata."""
        result = await tool.execute({"dryRun": True})

        assert "endpointCount" in result["metadata"]
        assert result["metadata"]["endpointCount"] > 0

    def test_tool_metadata(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test tool has correct metadata."""
        assert tool.name == "arc.gateway.egress.check"
        assert tool.description is not None
        assert len(tool.description) > 0
        assert tool.input_schema is not None

    @pytest.mark.asyncio
    async def test_missing_config_returns_failure(self, tool: ArcGatewayEgressCheckTool) -> None:
        """Test that missing config file returns appropriate failure."""
        result = await tool.execute({
            "dryRun": False,
            "configPath": "/nonexistent/path/endpoints.yaml",
        })

        # Should have a config check failure
        config_check = next(
            (c for c in result["checks"] if "config" in c["id"]),
            None
        )
        assert config_check is not None
        assert config_check["status"] == "fail"
