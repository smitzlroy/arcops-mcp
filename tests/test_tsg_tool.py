"""Tests for Azure Local TSG Search Tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.tools.azlocal_tsg_tool import AzLocalTsgTool


@pytest.fixture
def tool():
    """Create tool instance."""
    return AzLocalTsgTool()


@pytest.fixture
def sample_fixture():
    """Load sample fixture data."""
    fixture_path = Path(__file__).parent / "fixtures" / "tsg_search_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestAzLocalTsgTool:
    """Tests for AzLocalTsgTool."""

    def test_tool_metadata(self, tool):
        """Test tool has correct metadata."""
        assert tool.name == "azlocal.tsg.search"
        assert "AzLocalTSGTool" in tool.description
        assert "query" in tool.input_schema["required"]

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self, tool):
        """Test that empty query returns error."""
        result = await tool.execute({"query": ""})

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_dry_run_returns_results(self, tool):
        """Test dry run returns valid results structure."""
        result = await tool.execute({"query": "connectivity", "dryRun": True})

        assert result["success"] is True
        assert "results" in result
        assert result["dryRun"] is True
        assert result["resultCount"] >= 0

    @pytest.mark.asyncio
    async def test_dry_run_loads_fixture(self, tool, sample_fixture):
        """Test dry run loads fixture data correctly."""
        result = await tool.execute({"query": "certificate", "dryRun": True})

        assert result["success"] is True
        assert result["resultCount"] == len(sample_fixture["results"])

    @pytest.mark.asyncio
    async def test_dry_run_results_have_expected_fields(self, tool):
        """Test dry run results have expected structure."""
        result = await tool.execute({"query": "test", "dryRun": True})

        assert result["success"] is True
        if result["results"]:
            first_result = result["results"][0]
            assert "title" in first_result
            assert "category" in first_result
            assert "url" in first_result

    def test_check_module_installed_mock(self, tool):
        """Test module detection with mocked subprocess."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"Name": "AzLocalTSGTool", "Version": "0.3.2", "Path": "C:\\Modules\\AzLocalTSGTool"}
        )

        with patch("subprocess.run", return_value=mock_result):
            info = tool._check_module_installed()

        assert info["installed"] is True
        assert info["name"] == "AzLocalTSGTool"

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
    async def test_module_not_installed_returns_error(self, tool):
        """Test that missing module returns appropriate error."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = await tool.execute({"query": "test", "dryRun": False})

        assert result["success"] is False
        assert "AzLocalTSGTool module not installed" in result["error"]
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_query_preserved_in_response(self, tool):
        """Test that query is preserved in response."""
        result = await tool.execute({"query": "certificate expired", "dryRun": True})

        assert result["query"] == "certificate expired"

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, tool):
        """Test progress callback is invoked during dry run."""
        callbacks = []

        async def capture_callback(data):
            callbacks.append(data)

        await tool.execute({"query": "test", "dryRun": True}, progress_callback=capture_callback)

        assert len(callbacks) > 0
        types = [c["type"] for c in callbacks]
        assert "status" in types
        assert "complete" in types

    @pytest.mark.asyncio
    async def test_successful_search_mock(self, tool, sample_fixture):
        """Test successful search with mocked subprocess."""
        # Mock module check
        module_mock = MagicMock()
        module_mock.returncode = 0
        module_mock.stdout = json.dumps(
            {"Name": "AzLocalTSGTool", "Version": "0.3.2", "Path": "C:\\Modules"}
        )

        # Mock search result
        search_mock = MagicMock()
        search_mock.returncode = 0
        search_mock.stdout = json.dumps(sample_fixture["results"])

        def run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list) and len(cmd) > 2:
                cmd_str = cmd[-1] if isinstance(cmd[-1], str) else ""
                if "Get-Module" in cmd_str:
                    return module_mock
                elif "Search-AzLocalTSG" in cmd_str:
                    return search_mock
            return module_mock

        with patch("subprocess.run", side_effect=run_side_effect):
            result = await tool.execute({"query": "connectivity", "dryRun": False})

        assert result["success"] is True
        assert result["resultCount"] == len(sample_fixture["results"])
