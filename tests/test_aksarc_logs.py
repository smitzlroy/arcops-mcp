"""Tests for AKS Arc Log Collection Tool."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.tools.aksarc_logs_tool import AksArcLogsTool


@pytest.fixture
def tool():
    """Create tool instance."""
    return AksArcLogsTool()


class TestAksArcLogsTool:
    """Tests for AksArcLogsTool."""

    def test_tool_metadata(self, tool):
        """Test tool has correct metadata."""
        assert tool.name == "aksarc.logs.collect"
        assert "get-logs" in tool.description
        assert "ip" in tool.input_schema["properties"]
        assert "kubeconfig" in tool.input_schema["properties"]

    @pytest.mark.asyncio
    async def test_missing_target_returns_error(self, tool):
        """Test that missing ip and kubeconfig returns error."""
        result = await tool.execute({})

        assert result["success"] is False
        assert "ip" in result["error"] or "kubeconfig" in result["error"]

    @pytest.mark.asyncio
    async def test_dry_run_with_ip(self, tool):
        """Test dry run with IP address."""
        result = await tool.execute(
            {
                "ip": "192.168.1.100",
                "dryRun": True,
            }
        )

        assert result["dryRun"] is True
        assert result["target"]["ip"] == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_dry_run_with_kubeconfig(self, tool):
        """Test dry run with kubeconfig path."""
        result = await tool.execute(
            {
                "kubeconfig": "/path/to/kubeconfig",
                "dryRun": True,
            }
        )

        assert result["dryRun"] is True
        assert result["target"]["kubeconfig"] == "/path/to/kubeconfig"

    @pytest.mark.asyncio
    async def test_dry_run_checks_credentials_dir(self, tool, tmp_path):
        """Test dry run validates credentials directory."""
        creds_dir = tmp_path / "creds"
        creds_dir.mkdir()
        # Create a fake key file
        (creds_dir / "id_rsa").write_text("fake key")

        result = await tool.execute(
            {
                "ip": "192.168.1.100",
                "credentialsDir": str(creds_dir),
                "dryRun": True,
            }
        )

        assert result["dryRun"] is True
        # Should have a pass check for SSH keys
        key_check = next((c for c in result.get("checks", []) if c["check"] == "SSH keys"), None)
        assert key_check is not None
        assert key_check["status"] == "pass"

    @pytest.mark.asyncio
    async def test_dry_run_missing_credentials_warns(self, tool, tmp_path):
        """Test dry run warns when credentials directory has no keys."""
        creds_dir = tmp_path / "empty_creds"
        creds_dir.mkdir()

        result = await tool.execute(
            {
                "ip": "192.168.1.100",
                "credentialsDir": str(creds_dir),
                "dryRun": True,
            }
        )

        key_check = next((c for c in result.get("checks", []) if c["check"] == "SSH keys"), None)
        assert key_check is not None
        assert key_check["status"] == "warn"

    @pytest.mark.asyncio
    async def test_dry_run_nonexistent_credentials_fails(self, tool):
        """Test dry run fails when credentials directory doesn't exist."""
        result = await tool.execute(
            {
                "ip": "192.168.1.100",
                "credentialsDir": "/nonexistent/path",
                "dryRun": True,
            }
        )

        issues = result.get("issues", [])
        creds_issue = next((i for i in issues if i["check"] == "credentials directory"), None)
        assert creds_issue is not None
        assert creds_issue["status"] == "fail"

    def test_check_az_aksarc_available_mock(self, tool):
        """Test CLI detection with mocked subprocess."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"version": "1.0.0"})

        with patch("shutil.which", return_value="/usr/bin/az"):
            with patch("subprocess.run", return_value=mock_result):
                info = tool._check_az_aksarc_available()

        assert info["available"] is True
        assert info["azCli"] is True

    def test_check_az_aksarc_not_available(self, tool):
        """Test CLI detection when az not found."""
        with patch("shutil.which", return_value=None):
            with patch.object(Path, "exists", return_value=False):
                info = tool._check_az_aksarc_available()

        assert info["available"] is False
        assert "hint" in info

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, tool):
        """Test progress callback is invoked during dry run."""
        callbacks = []

        async def capture_callback(data):
            callbacks.append(data)

        await tool.execute(
            {"ip": "192.168.1.100", "dryRun": True}, progress_callback=capture_callback
        )

        assert len(callbacks) > 0
        types = [c["type"] for c in callbacks]
        assert "status" in types
        assert "complete" in types

    @pytest.mark.asyncio
    async def test_default_out_dir(self, tool):
        """Test default output directory is used."""
        result = await tool.execute(
            {
                "ip": "192.168.1.100",
                "dryRun": True,
            }
        )

        assert result["outDir"] == "./logs"

    @pytest.mark.asyncio
    async def test_custom_out_dir(self, tool):
        """Test custom output directory is preserved."""
        result = await tool.execute(
            {
                "ip": "192.168.1.100",
                "outDir": "/custom/logs",
                "dryRun": True,
            }
        )

        assert result["outDir"] == "/custom/logs"
