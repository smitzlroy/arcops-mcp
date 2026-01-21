"""
Base tool class for ArcOps MCP tools.

All tools inherit from this base class to ensure consistent interface.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


class BaseTool(ABC):
    """Abstract base class for MCP tools."""

    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}

    def generate_run_id(self) -> str:
        """Generate a unique run ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{timestamp}-{short_uuid}"

    def get_timestamp(self) -> str:
        """Get current ISO 8601 timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def create_findings_base(
        self,
        target: str,
        run_id: str | None = None,
        tool_name: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        """Create base findings structure."""
        import socket

        return {
            "version": "0.1.0",
            "target": target,
            "timestamp": self.get_timestamp(),
            "runId": run_id or self.generate_run_id(),
            "metadata": {
                "toolName": tool_name or self.name,
                "toolVersion": "0.1.0",
                "hostname": socket.gethostname(),
                "mode": mode,
            },
            "checks": [],
            "summary": {
                "total": 0,
                "pass": 0,
                "fail": 0,
                "warn": 0,
                "skipped": 0,
            },
        }

    def add_check(
        self,
        findings: dict[str, Any],
        check_id: str,
        title: str,
        severity: str,
        status: str,
        evidence: dict[str, Any] | None = None,
        hint: str | None = None,
        sources: list[dict[str, str]] | None = None,
        description: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Add a check result to findings."""
        check: dict[str, Any] = {
            "id": check_id,
            "title": title,
            "severity": severity,
            "status": status,
        }

        if description:
            check["description"] = description
        if evidence:
            check["evidence"] = evidence
        if hint:
            check["hint"] = hint
        if sources:
            check["sources"] = sources
        if duration_ms is not None:
            check["duration_ms"] = duration_ms

        findings["checks"].append(check)

        # Update summary
        findings["summary"]["total"] += 1
        if status in findings["summary"]:
            findings["summary"][status] += 1

    def get_source_ref(self, anchor: str, label: str, source_type: str = "doc") -> dict[str, str]:
        """
        Get a source reference pointing to docs/SOURCES.md.

        All external references should go through SOURCES.md to avoid
        hardcoding internal URLs in the codebase.
        """
        return {
            "type": source_type,
            "label": label,
            "url": f"docs/SOURCES.md#{anchor}",
        }

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the tool with given arguments.

        Args:
            arguments: Tool-specific arguments

        Returns:
            Findings JSON conforming to schemas/findings.schema.json
        """
        raise NotImplementedError
