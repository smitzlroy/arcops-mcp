"""
Tests for findings schema validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


@pytest.fixture
def schema() -> dict:
    """Load the findings schema."""
    schema_path = Path(__file__).parent.parent / "schemas" / "findings.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_findings() -> dict:
    """Load sample findings fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "findings_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestFindingsSchema:
    """Tests for findings schema validation."""

    def test_schema_is_valid_json_schema(self, schema: dict) -> None:
        """Test that the schema is a valid JSON Schema."""
        # Should not raise
        jsonschema.Draft7Validator.check_schema(schema)

    def test_schema_has_required_metadata(self, schema: dict) -> None:
        """Test that schema has required metadata fields."""
        assert "$schema" in schema
        assert "$id" in schema
        assert "title" in schema
        assert "version" in schema

    def test_sample_findings_valid(self, schema: dict, sample_findings: dict) -> None:
        """Test that sample findings validate against schema."""
        # Should not raise
        jsonschema.validate(sample_findings, schema)

    def test_minimal_valid_findings(self, schema: dict) -> None:
        """Test minimal valid findings structure."""
        minimal = {
            "version": "0.1.0",
            "target": "host",
            "timestamp": "2025-01-21T10:00:00Z",
            "checks": [],
        }
        # Should not raise
        jsonschema.validate(minimal, schema)

    def test_findings_with_all_optional_fields(self, schema: dict) -> None:
        """Test findings with all optional fields."""
        full = {
            "version": "0.1.0",
            "target": "cluster",
            "timestamp": "2025-01-21T10:00:00Z",
            "runId": "test-run-123",
            "metadata": {
                "toolName": "test-tool",
                "toolVersion": "1.0.0",
                "hostname": "test-host",
                "mode": "full",
            },
            "checks": [
                {
                    "id": "test.check.1",
                    "title": "Test Check",
                    "severity": "high",
                    "status": "pass",
                    "description": "A test check",
                    "evidence": {"key": "value"},
                    "hint": "Test hint",
                    "sources": [
                        {"type": "doc", "label": "Test Doc", "url": "https://example.com"}
                    ],
                    "duration_ms": 100,
                }
            ],
            "summary": {
                "total": 1,
                "pass": 1,
                "fail": 0,
                "warn": 0,
                "skipped": 0,
            },
        }
        # Should not raise
        jsonschema.validate(full, schema)

    def test_invalid_target_rejected(self, schema: dict) -> None:
        """Test that invalid target values are rejected."""
        invalid = {
            "version": "0.1.0",
            "target": "invalid_target",  # Not in enum
            "timestamp": "2025-01-21T10:00:00Z",
            "checks": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

    def test_invalid_severity_rejected(self, schema: dict) -> None:
        """Test that invalid severity values are rejected."""
        invalid = {
            "version": "0.1.0",
            "target": "host",
            "timestamp": "2025-01-21T10:00:00Z",
            "checks": [
                {
                    "id": "test.check",
                    "title": "Test",
                    "severity": "critical",  # Not in enum
                    "status": "pass",
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

    def test_invalid_status_rejected(self, schema: dict) -> None:
        """Test that invalid status values are rejected."""
        invalid = {
            "version": "0.1.0",
            "target": "host",
            "timestamp": "2025-01-21T10:00:00Z",
            "checks": [
                {
                    "id": "test.check",
                    "title": "Test",
                    "severity": "high",
                    "status": "error",  # Not in enum
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

    def test_missing_required_fields_rejected(self, schema: dict) -> None:
        """Test that missing required fields are rejected."""
        # Missing version
        invalid = {
            "target": "host",
            "timestamp": "2025-01-21T10:00:00Z",
            "checks": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

        # Missing checks array
        invalid = {
            "version": "0.1.0",
            "target": "host",
            "timestamp": "2025-01-21T10:00:00Z",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

    def test_check_id_pattern(self, schema: dict) -> None:
        """Test that check ID must match pattern."""
        # Valid IDs
        valid = {
            "version": "0.1.0",
            "target": "host",
            "timestamp": "2025-01-21T10:00:00Z",
            "checks": [
                {"id": "test.check.1", "title": "Test", "severity": "low", "status": "pass"},
                {"id": "arc-gateway_test", "title": "Test", "severity": "low", "status": "pass"},
            ],
        }
        jsonschema.validate(valid, schema)

    def test_source_type_enum(self, schema: dict) -> None:
        """Test that source type must be valid enum."""
        invalid = {
            "version": "0.1.0",
            "target": "host",
            "timestamp": "2025-01-21T10:00:00Z",
            "checks": [
                {
                    "id": "test.check",
                    "title": "Test",
                    "severity": "low",
                    "status": "pass",
                    "sources": [
                        {"type": "invalid_type", "label": "Test"}
                    ],
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

    def test_version_pattern(self, schema: dict) -> None:
        """Test that version must match semver pattern."""
        invalid = {
            "version": "1.0",  # Missing patch version
            "target": "host",
            "timestamp": "2025-01-21T10:00:00Z",
            "checks": [],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)

    def test_all_target_types(self, schema: dict) -> None:
        """Test all valid target types."""
        valid_targets = ["cluster", "host", "site", "gateway", "bundle"]

        for target in valid_targets:
            findings = {
                "version": "0.1.0",
                "target": target,
                "timestamp": "2025-01-21T10:00:00Z",
                "checks": [],
            }
            # Should not raise
            jsonschema.validate(findings, schema)

    def test_all_status_types(self, schema: dict) -> None:
        """Test all valid status types."""
        valid_statuses = ["pass", "fail", "warn", "skipped"]

        for status in valid_statuses:
            findings = {
                "version": "0.1.0",
                "target": "host",
                "timestamp": "2025-01-21T10:00:00Z",
                "checks": [
                    {
                        "id": f"test.{status}",
                        "title": f"Test {status}",
                        "severity": "low",
                        "status": status,
                    }
                ],
            }
            # Should not raise
            jsonschema.validate(findings, schema)
