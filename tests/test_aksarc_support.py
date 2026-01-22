"""Tests for AKS Arc Support Tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.tools.aksarc_support_tool import AksArcSupportTool


@pytest.fixture
def tool():
    """Create tool instance."""
    return AksArcSupportTool()


@pytest.fixture
def sample_fixture():
    """Load sample fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "aksarc_support_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestAksArcSupportTool:
    """Tests for AksArcSupportTool."""

    def test_tool_metadata(self, tool):
        """Test tool has correct metadata."""
        assert tool.name == "aksarc.support.diagnose"
        assert "Test-SupportAksArcKnownIssues" in tool.description
        assert "dryRun" in tool.input_schema["properties"]

    @pytest.mark.asyncio
    async def test_dry_run_returns_findings(self, tool):
        """Test dry run returns valid findings structure."""
        result = await tool.execute({"dryRun": True})

        assert result["version"] == "0.1.0"
        assert result["target"] == "aksarc"
        assert "checks" in result
        assert "summary" in result
        assert result["metadata"]["mode"] == "dry-run"

    @pytest.mark.asyncio
    async def test_dry_run_loads_fixture(self, tool, sample_fixture):
        """Test dry run loads fixture data correctly."""
        result = await tool.execute({"dryRun": True})

        # Should have checks from fixture
        assert result["summary"]["total"] > 0

        # Check that fixture checks are parsed
        check_ids = [c["id"] for c in result["checks"]]
        assert any("failover" in cid.lower() for cid in check_ids)

    @pytest.mark.asyncio
    async def test_dry_run_all_checks_pass(self, tool):
        """Test dry run fixture shows all passing checks."""
        result = await tool.execute({"dryRun": True})

        # All fixture checks should pass
        assert result["summary"]["fail"] == 0
        assert result["summary"]["pass"] == result["summary"]["total"]

    def test_check_module_installed_mock(self, tool):
        """Test module detection with mocked subprocess."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"Name": "Support.AksArc", "Version": "1.0.0", "Path": "C:\\Modules\\Support.AksArc"}
        )

        with patch("subprocess.run", return_value=mock_result):
            info = tool._check_module_installed()

        assert info["installed"] is True
        assert info["name"] == "Support.AksArc"

    def test_check_module_not_installed(self, tool):
        """Test module detection when module is missing."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            info = tool._check_module_installed()

        assert info["installed"] is False
        assert "hint" in info

    @pytest.mark.asyncio
    async def test_module_not_installed_returns_failure(self, tool):
        """Test that missing module returns appropriate failure check."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = await tool.execute({"dryRun": False})

        # Should have a failure check about missing module
        assert result["summary"]["fail"] > 0
        check_ids = [c["id"] for c in result["checks"]]
        assert "aksarc.support.module.required" in check_ids

    def test_parse_results_single_item(self, tool):
        """Test parsing a single check result."""
        findings = tool.create_findings_base(target="aksarc", run_id="test")

        single_result = {"Name": "Test Check", "Status": "Passed", "Details": "All good"}

        tool._parse_results(findings, single_result)

        assert findings["summary"]["total"] == 1
        assert findings["summary"]["pass"] == 1

    def test_parse_results_multiple_items(self, tool, sample_fixture):
        """Test parsing multiple check results."""
        findings = tool.create_findings_base(target="aksarc", run_id="test")

        tool._parse_results(findings, sample_fixture["results"])

        assert findings["summary"]["total"] == len(sample_fixture["results"])

    def test_parse_results_failed_check(self, tool):
        """Test parsing a failed check result."""
        findings = tool.create_findings_base(target="aksarc", run_id="test")

        failed_result = {
            "Name": "Certificate Check",
            "Status": "Failed",
            "Details": "Certificate expired on 2025-01-01",
        }

        tool._parse_results(findings, failed_result)

        assert findings["summary"]["fail"] == 1
        # High severity checks should have hint populated
        check = findings["checks"][0]
        assert check["status"] == "fail"
        assert check["hint"] is not None

    def test_status_mapping(self, tool):
        """Test various status values are mapped correctly."""
        findings = tool.create_findings_base(target="aksarc", run_id="test")

        results = [
            {"Name": "Check1", "Status": "Passed"},
            {"Name": "Check2", "Status": "Pass"},
            {"Name": "Check3", "Status": "OK"},
            {"Name": "Check4", "Status": "Failed"},
            {"Name": "Check5", "Status": "Warning"},
            {"Name": "Check6", "Status": "Skipped"},
        ]

        tool._parse_results(findings, results)

        assert findings["summary"]["pass"] == 3
        assert findings["summary"]["fail"] == 1
        assert findings["summary"]["warn"] == 1
        assert findings["summary"]["skipped"] == 1

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, tool):
        """Test progress callback is invoked during dry run."""
        callbacks = []

        async def capture_callback(data):
            callbacks.append(data)

        await tool.execute({"dryRun": True}, progress_callback=capture_callback)

        assert len(callbacks) > 0
        # Should have status and complete messages
        types = [c["type"] for c in callbacks]
        assert "status" in types
        assert "complete" in types
