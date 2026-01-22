"""
ArcOps MCP Server - Official MCP SDK Implementation.

This module provides an MCP-compliant server using the official Python SDK.
It wraps existing tools while maintaining backward compatibility with the
REST API in main.py.

Transport options:
- SSE (Server-Sent Events) for web clients
- Stdio for CLI integration (e.g., Claude Desktop)
- Streamable HTTP for modern MCP clients
"""

from __future__ import annotations

import json
import logging
from typing import Any, Annotated

from mcp.server.fastmcp import FastMCP, Context
from pydantic import Field

# Import existing tool implementations
from server.tools.arc_connectivity_check import ArcConnectivityCheckTool
from server.tools.aks_arc_validate import AksArcValidateTool
from server.tools.aksarc_support_tool import AksArcSupportTool
from server.tools.aksarc_logs_tool import AksArcLogsTool
from server.tools.azlocal_tsg_tool import AzLocalTsgTool
from server.tools.diagnostics_bundle import DiagnosticsBundleTool
from server.tools.educational_tool import ArcOpsEducationalTool

logger = logging.getLogger(__name__)

# Initialize MCP server with official SDK
mcp = FastMCP(
    name="arcops-mcp",
    instructions="""
    ArcOps Assistant helps diagnose and troubleshoot Azure Local and AKS Arc environments.
    
    Available capabilities:
    - Check network connectivity to Azure endpoints (52+ URLs)
    - Validate AKS Arc cluster configuration and health
    - Search troubleshooting guides for error messages
    - Diagnose common AKS Arc issues
    - Collect logs for support cases
    - Create diagnostic bundles with evidence
    
    When users ask about connectivity, network, or firewall issues, use the connectivity_check tool.
    When users mention errors or problems, search the TSG guides first.
    For cluster health questions, use the validate_cluster tool.
    """,
    host="127.0.0.1",
    port=8000,  # MCP SDK default port (separate from FastAPI on 8080)
)

# Instantiate existing tool classes (reuse their logic)
_connectivity_tool = ArcConnectivityCheckTool()
_validate_tool = AksArcValidateTool()
_support_tool = AksArcSupportTool()
_logs_tool = AksArcLogsTool()
_tsg_tool = AzLocalTsgTool()
_bundle_tool = DiagnosticsBundleTool()
_educational_tool = ArcOpsEducationalTool()


# =============================================================================
# MCP SDK Tool Definitions
# =============================================================================


@mcp.tool(
    name="arc.connectivity.check",
    description="Check network connectivity to Azure endpoints for Arc and AKS Arc. Tests 52+ URLs for DNS, TLS, and reachability.",
)
async def connectivity_check(
    mode: Annotated[
        str,
        Field(
            description="Check mode: 'quick' (key endpoints), 'full' (all checks), or 'endpoints-only'"
        ),
    ] = "quick",
    categories: Annotated[
        list[str] | None,
        Field(description="Filter by category: azure-arc, aks-arc, azure-local, monitoring, etc."),
    ] = None,
    timeout_sec: Annotated[
        int, Field(description="Timeout for each endpoint check in seconds")
    ] = 10,
    dry_run: Annotated[bool, Field(description="Simulate checks using fixture data")] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Run connectivity checks for Azure Local and AKS Arc environments.

    Returns findings with pass/fail/warn status for each endpoint.
    """
    if ctx:
        await ctx.info("Starting connectivity check...")

    arguments = {
        "mode": mode,
        "categories": categories,
        "timeoutSec": timeout_sec,
        "dryRun": dry_run,
    }

    # Create progress callback that uses MCP context
    async def progress_callback(data: dict[str, Any]) -> None:
        if ctx and data.get("type") == "progress":
            await ctx.report_progress(
                data.get("current", 0),
                data.get("total", 100),
            )
        elif ctx and data.get("message"):
            await ctx.info(data["message"])

    result = await _connectivity_tool.execute(arguments, progress_callback=progress_callback)

    if ctx:
        summary = result.get("summary", {})
        await ctx.info(
            f"Completed: {summary.get('pass', 0)} pass, "
            f"{summary.get('fail', 0)} fail, {summary.get('warn', 0)} warn"
        )

    return result


@mcp.tool(
    name="aks.arc.validate",
    description="Validate AKS Arc cluster configuration, extensions, CNI mode, and version compatibility.",
)
async def validate_cluster(
    kubeconfig: Annotated[str | None, Field(description="Path to kubeconfig file")] = None,
    context: Annotated[str | None, Field(description="Kubernetes context to use")] = None,
    checks: Annotated[
        list[str] | None, Field(description="Checks to run: extensions, cni, versions, flux, all")
    ] = None,
    dry_run: Annotated[bool, Field(description="Simulate checks using fixture data")] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Validate an AKS Arc cluster's health and configuration.

    Checks:
    - Arc extension presence and health
    - CNI mode configuration
    - Version compatibility
    - Flux GitOps status
    """
    if ctx:
        await ctx.info("Validating AKS Arc cluster...")

    arguments = {
        "kubeconfig": kubeconfig,
        "context": context,
        "checks": checks or ["all"],
        "dryRun": dry_run,
    }

    result = await _validate_tool.execute(arguments)

    if ctx:
        summary = result.get("summary", {})
        await ctx.info(f"Validation complete: {summary.get('total', 0)} checks")

    return result


@mcp.tool(
    name="aksarc.support.diagnose",
    description="Run Test-SupportAksArcKnownIssues to check for common AKS Arc problems.",
)
async def diagnose_aksarc_issues(
    dry_run: Annotated[
        bool, Field(description="Return fixture data without running actual checks")
    ] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Diagnose common AKS Arc issues using the Support.AksArc PowerShell module.

    Checks for:
    - Failover Cluster Service responsiveness
    - MOC Cloud/Node/Host Agent status
    - MOC version validation
    - Expired certificates
    - Gallery images stuck in deleting
    - VMs stuck in pending state
    """
    if ctx:
        await ctx.info("Running AKS Arc known issues check...")

    async def progress_callback(data: dict[str, Any]) -> None:
        if ctx and data.get("message"):
            await ctx.info(data["message"])

    result = await _support_tool.execute({"dryRun": dry_run}, progress_callback=progress_callback)
    return result


@mcp.tool(
    name="aksarc.logs.collect",
    description="Collect logs from AKS Arc cluster nodes for troubleshooting.",
)
async def collect_logs(
    node_names: Annotated[
        list[str] | None, Field(description="Specific nodes to collect from")
    ] = None,
    log_types: Annotated[
        list[str] | None, Field(description="Log types: kubelet, arc-agent, extensions")
    ] = None,
    since_hours: Annotated[int, Field(description="Collect logs from the last N hours")] = 24,
    dry_run: Annotated[bool, Field(description="Simulate log collection")] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Collect diagnostic logs from AKS Arc cluster nodes.
    """
    if ctx:
        await ctx.info("Collecting AKS Arc logs...")

    arguments = {
        "nodeNames": node_names,
        "logTypes": log_types,
        "sinceHours": since_hours,
        "dryRun": dry_run,
    }

    async def progress_callback(data: dict[str, Any]) -> None:
        if ctx and data.get("message"):
            await ctx.info(data["message"])

    result = await _logs_tool.execute(arguments, progress_callback=progress_callback)
    return result


@mcp.tool(
    name="azlocal.tsg.search",
    description="Search Azure Local troubleshooting guides by keyword, error message, or symptom.",
)
async def search_tsg(
    query: Annotated[str, Field(description="Error message, symptom, or keyword to search")],
    dry_run: Annotated[
        bool, Field(description="Return fixture data without actual search")
    ] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Search Azure Local troubleshooting guides.

    The underlying AzLocalTSGTool module handles GitHub content indexing and local caching.
    """
    if ctx:
        await ctx.info(f"Searching TSG for: {query}")

    async def progress_callback(data: dict[str, Any]) -> None:
        if ctx and data.get("message"):
            await ctx.info(data["message"])

    result = await _tsg_tool.execute(
        {"query": query, "dryRun": dry_run}, progress_callback=progress_callback
    )

    if ctx:
        results_count = len(result.get("results", []))
        await ctx.info(f"Found {results_count} matching guides")

    return result


@mcp.tool(
    name="arcops.diagnostics.bundle",
    description="Create a diagnostic bundle ZIP with findings, logs, and SHA256 manifest for support cases.",
)
async def create_bundle(
    input_dir: Annotated[
        str, Field(description="Directory containing findings JSON files")
    ] = "./results",
    output_dir: Annotated[str, Field(description="Directory to write bundle ZIP")] = "./artifacts",
    include_logs: Annotated[bool, Field(description="Include collected logs in bundle")] = True,
    dry_run: Annotated[bool, Field(description="Simulate bundle creation")] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Create a diagnostic bundle for Microsoft support cases.

    Bundle includes:
    - findings.json (combined diagnostics)
    - sha256sum.txt (tamper-evidence manifest)
    - logs/ (optional log files)
    """
    if ctx:
        await ctx.info("Creating diagnostic bundle...")

    arguments = {
        "inputDir": input_dir,
        "outputDir": output_dir,
        "includeLogs": include_logs,
        "dryRun": dry_run,
    }

    async def progress_callback(data: dict[str, Any]) -> None:
        if ctx and data.get("message"):
            await ctx.info(data["message"])

    result = await _bundle_tool.execute(arguments, progress_callback=progress_callback)

    if ctx and result.get("bundlePath"):
        await ctx.info(f"Bundle created: {result['bundlePath']}")

    return result


@mcp.tool(
    name="arcops.explain",
    description="Get educational content about Azure Local, AKS Arc, and Arc operations concepts.",
)
async def explain_topic(
    topic: Annotated[
        str,
        Field(
            description="Topic to explain: connectivity, extensions, cni, flux, troubleshooting, etc."
        ),
    ],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Get educational explanations about Azure Local and AKS Arc concepts.

    Topics include:
    - connectivity: Network requirements and firewall rules
    - extensions: Arc extension architecture
    - cni: Container network interface modes
    - flux: GitOps with Flux
    - troubleshooting: General debug approach
    """
    if ctx:
        await ctx.info(f"Explaining: {topic}")

    result = await _educational_tool.execute({"topic": topic})
    return result


@mcp.tool(
    name="arcops.full.diagnosis",
    description="Run comprehensive multi-stage diagnostics: connectivity, cluster validation, and TSG suggestions. One-click support diagnostic.",
)
async def full_diagnosis(
    dry_run: Annotated[bool, Field(description="Use fixture data for all checks")] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """
    Run comprehensive AKS Arc diagnostics in a single call.

    This orchestrates multiple diagnostic tools together:
    1. Network connectivity check (52+ Azure endpoints)
    2. AKS Arc cluster validation
    3. Auto-generates TSG search suggestions for any issues found
    4. Produces executive summary with remediation steps

    Perfect for support engineers needing a complete diagnostic snapshot.
    """
    from datetime import datetime

    if ctx:
        await ctx.info("🔍 Starting comprehensive diagnosis...")

    diagnosis = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "stages": [],
        "all_issues": [],
        "tsg_suggestions": [],
        "overall_health": "unknown",
    }

    # Stage 1: Connectivity Check
    if ctx:
        await ctx.info("📡 Stage 1/2: Checking Azure connectivity...")
        await ctx.report_progress(0, 2)

    try:
        conn_result = await _connectivity_tool.execute({"dryRun": dry_run})
        conn_summary = conn_result.get("summary", {})

        diagnosis["stages"].append(
            {
                "name": "Connectivity Check",
                "tool": "arc.connectivity.check",
                "status": (
                    "fail"
                    if conn_summary.get("fail", 0) > 0
                    else ("warn" if conn_summary.get("warn", 0) > 0 else "pass")
                ),
                "summary": conn_summary,
                "issues": [
                    c for c in conn_result.get("checks", []) if c.get("status") in ("fail", "warn")
                ],
            }
        )

        # Collect issues
        for check in conn_result.get("checks", []):
            if check.get("status") in ("fail", "warn"):
                diagnosis["all_issues"].append(
                    {
                        "source": "connectivity",
                        "id": check.get("id"),
                        "title": check.get("title"),
                        "status": check.get("status"),
                        "hint": check.get("hint"),
                    }
                )
    except Exception as e:
        diagnosis["stages"].append(
            {
                "name": "Connectivity Check",
                "tool": "arc.connectivity.check",
                "status": "error",
                "error": str(e),
            }
        )

    # Stage 2: Cluster Validation
    if ctx:
        await ctx.info("🔧 Stage 2/2: Validating AKS Arc cluster...")
        await ctx.report_progress(1, 2)

    try:
        val_result = await _validate_tool.execute({"checks": ["all"], "dryRun": dry_run})
        val_summary = val_result.get("summary", {})

        diagnosis["stages"].append(
            {
                "name": "Cluster Validation",
                "tool": "aks.arc.validate",
                "status": (
                    "fail"
                    if val_summary.get("fail", 0) > 0
                    else ("warn" if val_summary.get("warn", 0) > 0 else "pass")
                ),
                "summary": val_summary,
                "issues": [
                    c for c in val_result.get("checks", []) if c.get("status") in ("fail", "warn")
                ],
            }
        )

        # Collect issues
        for check in val_result.get("checks", []):
            if check.get("status") in ("fail", "warn"):
                diagnosis["all_issues"].append(
                    {
                        "source": "cluster",
                        "id": check.get("id"),
                        "title": check.get("title"),
                        "status": check.get("status"),
                        "hint": check.get("hint"),
                    }
                )
    except Exception as e:
        diagnosis["stages"].append(
            {
                "name": "Cluster Validation",
                "tool": "aks.arc.validate",
                "status": "error",
                "error": str(e),
            }
        )

    # Generate TSG suggestions
    if diagnosis["all_issues"]:
        diagnosis["tsg_suggestions"] = _generate_mcp_tsg_suggestions(diagnosis["all_issues"])

    # Calculate overall health
    fail_count = sum(s["summary"].get("fail", 0) for s in diagnosis["stages"] if s.get("summary"))
    warn_count = sum(s["summary"].get("warn", 0) for s in diagnosis["stages"] if s.get("summary"))
    pass_count = sum(s["summary"].get("pass", 0) for s in diagnosis["stages"] if s.get("summary"))

    if fail_count > 0:
        diagnosis["overall_health"] = "critical"
        diagnosis["health_icon"] = "🔴"
    elif warn_count > 0:
        diagnosis["overall_health"] = "degraded"
        diagnosis["health_icon"] = "🟡"
    else:
        diagnosis["overall_health"] = "healthy"
        diagnosis["health_icon"] = "🟢"

    diagnosis["totals"] = {
        "pass": pass_count,
        "warn": warn_count,
        "fail": fail_count,
        "total_issues": len(diagnosis["all_issues"]),
    }

    # Generate executive summary
    diagnosis["executive_summary"] = _generate_mcp_executive_summary(diagnosis)

    if ctx:
        await ctx.report_progress(2, 2)
        await ctx.info(
            f"{diagnosis['health_icon']} Diagnosis complete: {diagnosis['overall_health'].upper()}"
        )

    return diagnosis


def _generate_mcp_tsg_suggestions(issues: list[dict[str, Any]]) -> list[str]:
    """Generate TSG search suggestions based on found issues."""
    suggestions = []

    tsg_mappings = {
        "connectivity": "Azure Arc connectivity troubleshooting",
        "firewall": "Azure Arc firewall requirements",
        "dns": "Azure Arc DNS resolution",
        "proxy": "Azure Arc proxy configuration",
        "tls": "Azure Arc TLS certificate issues",
        "cluster.offline": "AKS Arc cluster offline troubleshooting",
        "extension": "AKS Arc extension installation",
        "agent": "Azure Arc agent troubleshooting",
        "provisioning": "AKS Arc provisioning failed",
    }

    for issue in issues:
        check_id = issue.get("id", "").lower()
        title = issue.get("title", "").lower()

        for keyword, tsg_query in tsg_mappings.items():
            if keyword in check_id or keyword in title:
                if tsg_query not in suggestions:
                    suggestions.append(tsg_query)
                break
        else:
            if issue.get("status") == "fail" and issue.get("title"):
                clean_title = issue["title"].replace("Check", "").strip()
                if clean_title and f"Azure Local {clean_title}" not in suggestions:
                    suggestions.append(f"AKS Arc {clean_title}")

    return suggestions[:5]


def _generate_mcp_executive_summary(diagnosis: dict[str, Any]) -> str:
    """Generate a human-readable executive summary."""
    lines = []

    health = diagnosis.get("overall_health", "unknown")
    icon = diagnosis.get("health_icon", "❓")
    totals = diagnosis.get("totals", {})

    lines.append(f"{icon} **Overall System Health: {health.upper()}**")
    lines.append("")
    lines.append("**Diagnostics Summary:**")
    lines.append(f"- ✅ Passed: {totals.get('pass', 0)} checks")
    lines.append(f"- ⚠️ Warnings: {totals.get('warn', 0)} checks")
    lines.append(f"- ❌ Failed: {totals.get('fail', 0)} checks")

    critical = [i for i in diagnosis.get("all_issues", []) if i.get("status") == "fail"]
    if critical:
        lines.append("")
        lines.append("**🚨 Critical Issues:**")
        for issue in critical[:5]:
            lines.append(f"- **{issue.get('title', 'Unknown')}**")
            if issue.get("hint"):
                lines.append(f"  └─ 💡 {issue['hint']}")

    suggestions = diagnosis.get("tsg_suggestions", [])
    if suggestions:
        lines.append("")
        lines.append("**📚 Recommended TSG Searches:**")
        for tsg in suggestions[:3]:
            lines.append(f'- Search: *"{tsg}"*')

    return "\n".join(lines)


# =============================================================================
# MCP Resources (for browsable data)
# =============================================================================


@mcp.resource("arcops://tools")
def list_available_tools() -> str:
    """List all available ArcOps tools and their descriptions."""
    tools_info = {
        "arc.connectivity.check": "Check network connectivity to 52+ Azure endpoints",
        "aks.arc.validate": "Validate AKS Arc cluster configuration",
        "aksarc.support.diagnose": "Diagnose common AKS Arc issues",
        "aksarc.logs.collect": "Collect diagnostic logs from cluster nodes",
        "azlocal.tsg.search": "Search troubleshooting guides",
        "arcops.diagnostics.bundle": "Create support bundle",
        "arcops.explain": "Get educational content",
    }
    return json.dumps(tools_info, indent=2)


@mcp.resource("arcops://endpoints")
def list_monitored_endpoints() -> str:
    """List the Azure endpoints that connectivity check monitors."""
    from pathlib import Path
    import yaml

    config_path = Path(__file__).parent / "config" / "endpoints.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
            endpoints = config.get("endpoints", [])
            return json.dumps(endpoints, indent=2)
    return json.dumps([])


# =============================================================================
# MCP Prompts (pre-built workflows)
# =============================================================================


@mcp.prompt(
    name="troubleshoot_connectivity",
    description="Diagnose Azure connectivity issues step by step",
)
def troubleshoot_connectivity_prompt() -> str:
    """Guide for troubleshooting connectivity issues."""
    return """
    To troubleshoot Azure connectivity issues, follow these steps:
    
    1. First, run a connectivity check to identify blocked endpoints:
       Use the arc.connectivity.check tool with mode="full"
    
    2. Review any failed or warning checks:
       - Failed (high severity) = Required endpoints that are blocked
       - Warning (medium severity) = Optional endpoints that may affect features
    
    3. For each failed endpoint:
       - Check if there's a firewall rule blocking it
       - Verify DNS can resolve the FQDN
       - Test TLS connection on the required port
    
    4. If you see specific errors, search the TSG:
       Use azlocal.tsg.search with the error message
    
    5. After fixing issues, re-run the connectivity check to verify
    
    Common fixes:
    - Add proxy exceptions for *.azure.com, *.microsoft.com
    - Open ports 443 (HTTPS) and 80 (HTTP for CRL)
    - Ensure NTP port 123 is open for time sync
    """


@mcp.prompt(
    name="create_support_case",
    description="Collect all diagnostics for a Microsoft support case",
)
def create_support_case_prompt() -> str:
    """Guide for creating a support case bundle."""
    return """
    To create a complete diagnostic package for Microsoft support:
    
    1. Run connectivity check (full mode):
       arc.connectivity.check with mode="full", dry_run=false
    
    2. Run cluster validation:
       aks.arc.validate with checks=["all"], dry_run=false
    
    3. Run AKS Arc known issues check:
       aksarc.support.diagnose with dry_run=false
    
    4. Collect relevant logs:
       aksarc.logs.collect with since_hours=48
    
    5. Create the diagnostic bundle:
       arcops.diagnostics.bundle with include_logs=true
    
    The bundle will contain:
    - All findings in JSON format
    - Collected logs
    - SHA256 checksums for tamper evidence
    
    Upload this bundle to your Microsoft support case.
    """


# =============================================================================
# Entry points for different transports
# =============================================================================


def run_sse():
    """Run MCP server with SSE transport (for web clients)."""
    import asyncio

    asyncio.run(mcp.run_sse_async())


def run_stdio():
    """Run MCP server with stdio transport (for CLI tools like Claude Desktop)."""
    import asyncio

    asyncio.run(mcp.run_stdio_async())


def run_http():
    """Run MCP server with streamable HTTP transport."""
    import asyncio

    asyncio.run(mcp.run_streamable_http_async())


# Expose the MCP app for ASGI mounting
mcp_app = mcp.streamable_http_app()
sse_app = mcp.sse_app()


if __name__ == "__main__":
    # Default to SSE transport
    run_sse()
