"""
Tests for Network Safety Tool.

Tests policy validation and manifest generation for
Gateway API and Istio network policies.
"""

import json
import pytest
from pathlib import Path

import yaml

from server.tools.packs.network_safety import NetworkSafetyTool, NetworkRenderTool


@pytest.fixture
def safety_tool():
    """Create NetworkSafetyTool instance."""
    return NetworkSafetyTool()


@pytest.fixture
def render_tool():
    """Create NetworkRenderTool instance."""
    return NetworkRenderTool()


@pytest.fixture
def valid_policy_path(tmp_path):
    """Create valid network policy file."""
    policy = {
        "name": "test-network-policy",
        "version": "1.0",
        "global": {
            "tlsMinVersion": "1.2",
            "denyByDefault": True,
        },
        "namespaces": [
            {
                "name": "test-ns",
                "ingress": {
                    "hosts": ["api.test.local"],
                    "tlsRequired": True,
                    "tlsSecret": "test-tls",
                    "rateLimit": {
                        "requestsPerSecond": 100,
                    },
                },
                "egress": {
                    "mode": "deny-by-default",
                    "allowedCidrs": ["10.0.0.0/8"],
                    "allowedSNI": ["db.internal.local"],
                },
            },
        ],
    }

    policy_file = tmp_path / "network-policy.yaml"
    with open(policy_file, "w") as f:
        yaml.dump(policy, f)

    return str(policy_file)


@pytest.fixture
def unsafe_policy_path(tmp_path):
    """Create unsafe network policy with violations."""
    policy = {
        "name": "unsafe-policy",
        "version": "1.0",
        "global": {
            "tlsMinVersion": "1.0",  # Too old
            "denyByDefault": False,  # Not deny-by-default
        },
        "namespaces": [
            {
                "name": "unsafe-ns",
                "ingress": {
                    "hosts": ["*.wildcard.local"],  # Wildcard
                    "tlsRequired": False,  # No TLS
                },
                "egress": {
                    "mode": "allow-all",  # Not deny-by-default
                    "allowedCidrs": ["0.0.0.0/0"],  # Wildcard egress
                },
            },
        ],
    }

    policy_file = tmp_path / "unsafe-policy.yaml"
    with open(policy_file, "w") as f:
        yaml.dump(policy, f)

    return str(policy_file)


@pytest.fixture
def output_path(tmp_path):
    """Create temp output path."""
    return str(tmp_path / "safety-report.json")


@pytest.fixture
def manifests_dir(tmp_path):
    """Create temp manifests directory."""
    return str(tmp_path / "manifests")


class TestNetworkSafetyTool:
    """Test suite for NetworkSafetyTool."""

    @pytest.mark.asyncio
    async def test_tool_metadata(self, safety_tool):
        """Test tool has correct metadata."""
        assert safety_tool.name == "network.safety"
        assert "network" in safety_tool.description.lower()
        assert "policy" in safety_tool.input_schema["properties"]

    @pytest.mark.asyncio
    async def test_valid_policy_passes(self, safety_tool, valid_policy_path, output_path):
        """Test valid policy produces PASS verdict."""
        result = await safety_tool.run(
            policy=valid_policy_path,
            outputPath=output_path,
        )

        assert result["version"] == "1.0.0"
        assert result["type"] == "safety-report"
        assert result["verdict"] == "PASS"
        assert "artifactHash" in result

    @pytest.mark.asyncio
    async def test_unsafe_policy_fails(self, safety_tool, unsafe_policy_path, output_path):
        """Test unsafe policy produces FAIL verdict."""
        result = await safety_tool.run(
            policy=unsafe_policy_path,
            outputPath=output_path,
        )

        assert result["verdict"] == "FAIL"
        assert result["summary"]["fail"] > 0

    @pytest.mark.asyncio
    async def test_wildcard_egress_detected(self, safety_tool, unsafe_policy_path, output_path):
        """Test wildcard egress (0.0.0.0/0) is detected."""
        result = await safety_tool.run(
            policy=unsafe_policy_path,
            outputPath=output_path,
        )

        # Find the wildcard egress check
        wildcard_check = next((c for c in result["checks"] if c["id"] == "NS-001"), None)

        assert wildcard_check is not None
        assert wildcard_check["status"] == "fail"
        assert wildcard_check["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_missing_tls_detected(self, safety_tool, unsafe_policy_path, output_path):
        """Test missing TLS requirement is detected."""
        result = await safety_tool.run(
            policy=unsafe_policy_path,
            outputPath=output_path,
        )

        # Find TLS check
        tls_check = next((c for c in result["checks"] if c["id"] == "NS-002"), None)

        assert tls_check is not None
        assert tls_check["status"] == "fail"

    @pytest.mark.asyncio
    async def test_summary_counts_correct(self, safety_tool, valid_policy_path, output_path):
        """Test summary counts are calculated correctly."""
        result = await safety_tool.run(
            policy=valid_policy_path,
            outputPath=output_path,
        )

        summary = result["summary"]
        checks = result["checks"]

        # Verify counts match
        total_from_checks = len(checks)
        pass_count = sum(1 for c in checks if c["status"] == "pass")
        fail_count = sum(1 for c in checks if c["status"] == "fail")
        warn_count = sum(1 for c in checks if c["status"] == "warn")

        assert summary["total"] == total_from_checks
        assert summary["pass"] == pass_count
        assert summary["fail"] == fail_count
        assert summary["warn"] == warn_count

    @pytest.mark.asyncio
    async def test_artifact_written_to_file(self, safety_tool, valid_policy_path, output_path):
        """Test artifact is written to output file."""
        await safety_tool.run(
            policy=valid_policy_path,
            outputPath=output_path,
        )

        assert Path(output_path).exists()

        with open(output_path, "r") as f:
            saved = json.load(f)

        assert saved["type"] == "safety-report"

    @pytest.mark.asyncio
    async def test_missing_policy_file_error(self, safety_tool, output_path):
        """Test error when policy file doesn't exist."""
        result = await safety_tool.run(
            policy="/nonexistent/policy.yaml",
            outputPath=output_path,
        )

        assert result["verdict"] == "FAIL"
        assert "error" in result


class TestNetworkRenderTool:
    """Test suite for NetworkRenderTool."""

    @pytest.mark.asyncio
    async def test_tool_metadata(self, render_tool):
        """Test tool has correct metadata."""
        assert render_tool.name == "network.render"
        assert (
            "Gateway API" in render_tool.description
            or "manifest" in render_tool.description.lower()
        )

    @pytest.mark.asyncio
    async def test_generates_ingress_manifests(self, render_tool, valid_policy_path, manifests_dir):
        """Test ingress manifests are generated."""
        result = await render_tool.run(
            policy=valid_policy_path,
            outputDir=manifests_dir,
        )

        assert "ingressManifests" in result
        assert len(result["ingressManifests"]) > 0

        # Check files exist
        for manifest_path in result["ingressManifests"]:
            assert Path(manifest_path).exists()

    @pytest.mark.asyncio
    async def test_generates_egress_manifests(self, render_tool, valid_policy_path, manifests_dir):
        """Test egress manifests are generated."""
        result = await render_tool.run(
            policy=valid_policy_path,
            outputDir=manifests_dir,
        )

        assert "egressManifests" in result
        # Should have egress manifest for each allowedSNI
        assert len(result["egressManifests"]) > 0

    @pytest.mark.asyncio
    async def test_gateway_manifest_valid_yaml(self, render_tool, valid_policy_path, manifests_dir):
        """Test generated Gateway manifest is valid YAML."""
        result = await render_tool.run(
            policy=valid_policy_path,
            outputDir=manifests_dir,
        )

        # Find gateway manifest
        gateway_path = next((p for p in result["ingressManifests"] if "gateway" in p.lower()), None)

        assert gateway_path is not None

        with open(gateway_path, "r") as f:
            gateway = yaml.safe_load(f)

        assert gateway["apiVersion"] == "gateway.networking.k8s.io/v1"
        assert gateway["kind"] == "Gateway"
        assert "spec" in gateway

    @pytest.mark.asyncio
    async def test_httproute_manifest_valid_yaml(
        self, render_tool, valid_policy_path, manifests_dir
    ):
        """Test generated HTTPRoute manifest is valid YAML."""
        result = await render_tool.run(
            policy=valid_policy_path,
            outputDir=manifests_dir,
        )

        # Find HTTPRoute manifest by filename only (not full path)
        route_path = next(
            (p for p in result["ingressManifests"] 
             if Path(p).name.endswith("-route.yaml")),
            None
        )

        if route_path is None:
            pytest.skip("No HTTPRoute manifest generated")

        with open(route_path, "r") as f:
            route = yaml.safe_load(f)

        assert route["apiVersion"] == "gateway.networking.k8s.io/v1"
        assert route["kind"] == "HTTPRoute"
        assert "hostnames" in route["spec"]

    @pytest.mark.asyncio
    async def test_service_entry_manifest_valid_yaml(
        self, render_tool, valid_policy_path, manifests_dir
    ):
        """Test generated ServiceEntry manifest is valid YAML."""
        result = await render_tool.run(
            policy=valid_policy_path,
            outputDir=manifests_dir,
        )

        if not result["egressManifests"]:
            pytest.skip("No egress manifests generated")

        se_path = result["egressManifests"][0]

        with open(se_path, "r") as f:
            se = yaml.safe_load(f)

        assert se["apiVersion"] == "networking.istio.io/v1beta1"
        assert se["kind"] == "ServiceEntry"
        assert "hosts" in se["spec"]
