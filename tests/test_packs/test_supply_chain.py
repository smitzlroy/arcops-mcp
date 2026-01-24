"""
Tests for Supply Chain Gate Tool.

Tests signature verification, SBOM analysis, and policy evaluation
for BYO model approval workflow.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from server.tools.packs.supply_chain_gate import SupplyChainGateTool
from server.services.policy_engine import PolicyEngine, PolicyResult


@pytest.fixture
def tool():
    """Create tool instance."""
    return SupplyChainGateTool()


@pytest.fixture
def policy_path(tmp_path):
    """Create test policy file."""
    policy = {
        "name": "test-policy",
        "version": "1.0",
        "rules": [
            {
                "name": "require-signature",
                "description": "Signature must be validated",
                "condition": "signature.validated == true",
                "verdict": "GREEN",
                "failVerdict": "RED",
            },
            {
                "name": "no-critical-cves",
                "description": "No critical CVEs",
                "condition": "sbom.vulnerabilities.critical == 0",
                "verdict": "GREEN",
                "failVerdict": "RED",
            },
        ],
    }

    policy_file = tmp_path / "test-policy.yaml"
    import yaml

    with open(policy_file, "w") as f:
        yaml.dump(policy, f)

    return str(policy_file)


@pytest.fixture
def output_path(tmp_path):
    """Create temp output path."""
    return str(tmp_path / "approval.json")


class TestSupplyChainGateTool:
    """Test suite for SupplyChainGateTool."""

    @pytest.mark.asyncio
    async def test_tool_metadata(self, tool):
        """Test tool has correct metadata."""
        assert tool.name == "supply_chain.gate"
        assert "signature" in tool.description.lower()
        assert "image" in tool.input_schema["properties"]
        assert "policy" in tool.input_schema["properties"]

    @pytest.mark.asyncio
    async def test_dry_run_with_valid_signature(self, tool, policy_path, output_path):
        """Test dry run with valid signature produces GREEN verdict."""
        result = await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        assert result["version"] == "1.0.0"
        assert result["type"] == "approval"
        assert result["verdict"] == "GREEN"
        assert result["signature"]["validated"] is True
        assert "artifactHash" in result
        assert result["artifactHash"].startswith("sha256:")

    @pytest.mark.asyncio
    async def test_dry_run_without_signature(self, tool, policy_path, output_path):
        """Test dry run without signature produces RED verdict."""
        result = await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey=None,  # No key
            outputPath=output_path,
            dryRun=True,
        )

        assert result["verdict"] == "RED"
        assert result["signature"]["validated"] is False

    @pytest.mark.asyncio
    async def test_artifact_written_to_file(self, tool, policy_path, output_path):
        """Test artifact is written to output file."""
        await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        assert Path(output_path).exists()

        with open(output_path, "r") as f:
            saved = json.load(f)

        assert saved["type"] == "approval"
        assert "verdict" in saved

    @pytest.mark.asyncio
    async def test_image_reference_normalization(self, tool, policy_path, output_path):
        """Test OCI image reference normalization."""
        result = await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        # OCI prefix should be stripped
        assert not result["image"]["reference"].startswith("oci://")
        assert "registry.local" in result["image"]["reference"]

    @pytest.mark.asyncio
    async def test_tag_extraction(self, tool, policy_path, output_path):
        """Test tag extraction from image reference."""
        result = await tool.run(
            image="oci://registry.local/models/test:v2.1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        assert result["image"]["tag"] == "v2.1.0"

    @pytest.mark.asyncio
    async def test_sbom_vulnerabilities_in_result(self, tool, policy_path, output_path):
        """Test SBOM vulnerabilities are included in result."""
        result = await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        assert "sbom" in result
        assert "vulnerabilities" in result["sbom"]
        vulns = result["sbom"]["vulnerabilities"]
        assert "critical" in vulns
        assert "high" in vulns
        assert "medium" in vulns
        assert "low" in vulns

    @pytest.mark.asyncio
    async def test_policy_evaluation_in_result(self, tool, policy_path, output_path):
        """Test policy evaluation results are included."""
        result = await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        assert "policy" in result
        assert result["policy"]["name"] == "test-policy"
        assert result["policy"]["rulesEvaluated"] == 2
        assert result["policy"]["rulesPassed"] >= 0

    @pytest.mark.asyncio
    async def test_reasons_populated(self, tool, policy_path, output_path):
        """Test reasons array is populated."""
        result = await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        assert "reasons" in result
        assert len(result["reasons"]) > 0
        assert any("signature" in r.lower() or "Signature" in r for r in result["reasons"])

    @pytest.mark.asyncio
    async def test_run_id_generated(self, tool, policy_path, output_path):
        """Test unique run ID is generated."""
        result1 = await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        result2 = await tool.run(
            image="oci://registry.local/models/test:1.0",
            policy=policy_path,
            pubKey="keys/test.pub",
            outputPath=output_path,
            dryRun=True,
        )

        assert result1["runId"] != result2["runId"]


class TestPolicyEngine:
    """Test suite for PolicyEngine."""

    def test_load_policy_from_dict(self):
        """Test loading policy from dictionary."""
        engine = PolicyEngine()
        engine.load_policy_from_dict(
            {
                "name": "test",
                "version": "1.0",
                "rules": [],
            }
        )

        assert engine.policy["name"] == "test"

    def test_evaluate_simple_condition(self):
        """Test evaluating simple equality condition."""
        engine = PolicyEngine()
        engine.load_policy_from_dict(
            {
                "name": "test",
                "version": "1.0",
                "rules": [
                    {
                        "name": "check-validated",
                        "condition": "signature.validated == true",
                        "verdict": "GREEN",
                        "failVerdict": "RED",
                    },
                ],
            }
        )

        result = engine.evaluate({"signature": {"validated": True}})

        assert result.verdict == "GREEN"
        assert result.rules_passed == 1
        assert result.rules_failed == 0

    def test_evaluate_numeric_condition(self):
        """Test evaluating numeric comparison condition."""
        engine = PolicyEngine()
        engine.load_policy_from_dict(
            {
                "name": "test",
                "version": "1.0",
                "rules": [
                    {
                        "name": "max-vulns",
                        "condition": "sbom.vulnerabilities.critical <= 0",
                        "verdict": "GREEN",
                        "failVerdict": "RED",
                    },
                ],
            }
        )

        # Should pass with 0 critical vulns
        result = engine.evaluate({"sbom": {"vulnerabilities": {"critical": 0}}})
        assert result.verdict == "GREEN"

        # Should fail with 1 critical vuln
        result = engine.evaluate({"sbom": {"vulnerabilities": {"critical": 1}}})
        assert result.verdict == "RED"

    def test_evaluate_missing_field_fails(self):
        """Test that missing fields cause rule to fail."""
        engine = PolicyEngine()
        engine.load_policy_from_dict(
            {
                "name": "test",
                "version": "1.0",
                "rules": [
                    {
                        "name": "check-field",
                        "condition": "missing.field == true",
                        "verdict": "GREEN",
                        "failVerdict": "RED",
                    },
                ],
            }
        )

        result = engine.evaluate({})
        assert result.verdict == "RED"

    def test_worst_verdict_wins(self):
        """Test that worst verdict is used as final verdict."""
        engine = PolicyEngine()
        engine.load_policy_from_dict(
            {
                "name": "test",
                "version": "1.0",
                "rules": [
                    {
                        "name": "rule1",
                        "condition": "field1 == true",
                        "verdict": "GREEN",
                        "failVerdict": "AMBER",
                    },
                    {
                        "name": "rule2",
                        "condition": "field2 == true",
                        "verdict": "GREEN",
                        "failVerdict": "RED",
                    },
                ],
            }
        )

        # Both fail - RED should win over AMBER
        result = engine.evaluate({"field1": False, "field2": False})
        assert result.verdict == "RED"

    def test_failures_list_populated(self):
        """Test that failures list is populated on rule failures."""
        engine = PolicyEngine()
        engine.load_policy_from_dict(
            {
                "name": "test",
                "version": "1.0",
                "rules": [
                    {
                        "name": "failing-rule",
                        "description": "This rule fails",
                        "condition": "value == true",
                        "verdict": "GREEN",
                        "failVerdict": "RED",
                    },
                ],
            }
        )

        result = engine.evaluate({"value": False})

        assert len(result.failures) == 1
        assert result.failures[0]["rule"] == "failing-rule"
