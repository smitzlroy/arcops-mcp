"""
ArcOps MCP CLI - Command-line interface for Azure Local + AKS Arc operations.

Usage:
    python -m cli envcheck --mode full --out ./artifacts
    python -m cli egress --cfg server/config/endpoints.yaml --out ./artifacts
    python -m cli validate --kube ~/.kube/config --out ./artifacts
    python -m cli bundle --in ./artifacts --sign false
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.tools.aks_arc_validate import AksArcValidateTool
from server.tools.arc_gateway_egress_check import ArcGatewayEgressCheckTool
from server.tools.azlocal_envcheck_wrap import AzLocalEnvCheckWrapTool
from server.tools.diagnostics_bundle import DiagnosticsBundleTool

app = typer.Typer(
    name="arcops",
    help="ArcOps MCP CLI - Azure Local + AKS Arc operations bridge",
    add_completion=False,
)


def write_output(findings: dict, output_dir: Path, name: str) -> Path:
    """Write findings to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{name}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2)
    return output_file


@app.command()
def envcheck(
    mode: Annotated[
        str,
        typer.Option("--mode", "-m", help="Execution mode: quick or full"),
    ] = "quick",
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output directory for results"),
    ] = Path("./artifacts"),
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Timeout in seconds"),
    ] = 300,
    checker_path: Annotated[
        Optional[str],
        typer.Option("--checker-path", help="Path to Environment Checker executable"),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Include raw output in evidence"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate using fixture data"),
    ] = False,
) -> None:
    """
    Run Azure Local Environment Checker and normalize results.

    Wraps the Azure Local Environment Checker, parsing its output
    and producing normalized findings conforming to the schema.
    """
    typer.echo(f"[*] Running environment check (mode={mode}, dry_run={dry_run})")

    tool = AzLocalEnvCheckWrapTool()
    findings = asyncio.run(
        tool.execute(
            {
                "mode": mode,
                "timeoutSec": timeout,
                "rawOutput": raw,
                "checkerPath": checker_path,
                "dryRun": dry_run,
            }
        )
    )

    output_file = write_output(findings, out, "envcheck")
    summary = findings.get("summary", {})

    typer.echo(f"[OK] Environment check complete")
    typer.echo(
        f"   Results: {summary.get('pass', 0)} pass, "
        f"{summary.get('fail', 0)} fail, "
        f"{summary.get('warn', 0)} warn, "
        f"{summary.get('skipped', 0)} skipped"
    )
    typer.echo(f"📄 Output: {output_file}")

    # Exit with error if any failures
    if summary.get("fail", 0) > 0:
        raise typer.Exit(code=1)


@app.command()
def egress(
    cfg: Annotated[
        Path,
        typer.Option("--cfg", "-c", help="Path to endpoints configuration YAML"),
    ] = Path("server/config/endpoints.yaml"),
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output directory for results"),
    ] = Path("./artifacts"),
    categories: Annotated[
        Optional[str],
        typer.Option("--categories", help="Comma-separated list of endpoint categories"),
    ] = None,
    required_only: Annotated[
        bool,
        typer.Option("--required-only", help="Only check required endpoints"),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Timeout per endpoint in seconds"),
    ] = 10,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate using fixture data"),
    ] = False,
) -> None:
    """
    Check egress connectivity to Azure Arc gateway endpoints.

    Tests TLS/Proxy/FQDN reachability for configured endpoints.
    Supports corporate CA trust and HTTP(S)_PROXY.
    """
    typer.echo(f"🌐 Checking egress connectivity (dry_run={dry_run})")

    category_list = categories.split(",") if categories else None

    tool = ArcGatewayEgressCheckTool()
    findings = asyncio.run(
        tool.execute(
            {
                "configPath": str(cfg),
                "categories": category_list,
                "requiredOnly": required_only,
                "timeoutSec": timeout,
                "dryRun": dry_run,
            }
        )
    )

    output_file = write_output(findings, out, "egress")
    summary = findings.get("summary", {})

    typer.echo(f"[OK] Egress check complete")
    typer.echo(
        f"   Results: {summary.get('pass', 0)} pass, "
        f"{summary.get('fail', 0)} fail, "
        f"{summary.get('warn', 0)} warn, "
        f"{summary.get('skipped', 0)} skipped"
    )
    typer.echo(f"📄 Output: {output_file}")

    if summary.get("fail", 0) > 0:
        raise typer.Exit(code=1)


@app.command()
def validate(
    kube: Annotated[
        Optional[Path],
        typer.Option("--kube", "-k", help="Path to kubeconfig file"),
    ] = None,
    context: Annotated[
        Optional[str],
        typer.Option("--context", help="Kubernetes context to use"),
    ] = None,
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output directory for results"),
    ] = Path("./artifacts"),
    checks: Annotated[
        str,
        typer.Option("--checks", help="Comma-separated checks: extensions,cni,versions,flux,all"),
    ] = "all",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate using fixture data"),
    ] = False,
) -> None:
    """
    Validate AKS Arc cluster configuration.

    Checks extension presence/health, CNI mode, version pins, and Flux GitOps.
    Returns 'skipped' if kubeconfig is unavailable.
    """
    typer.echo(f"[*] Validating AKS Arc cluster (dry_run={dry_run})")

    check_list = checks.split(",")

    tool = AksArcValidateTool()
    findings = asyncio.run(
        tool.execute(
            {
                "kubeconfig": str(kube) if kube else None,
                "context": context,
                "checks": check_list,
                "dryRun": dry_run,
            }
        )
    )

    output_file = write_output(findings, out, "validate")
    summary = findings.get("summary", {})

    typer.echo(f"[OK] Validation complete")
    typer.echo(
        f"   Results: {summary.get('pass', 0)} pass, "
        f"{summary.get('fail', 0)} fail, "
        f"{summary.get('warn', 0)} warn, "
        f"{summary.get('skipped', 0)} skipped"
    )
    typer.echo(f"📄 Output: {output_file}")

    if summary.get("fail", 0) > 0:
        raise typer.Exit(code=1)


@app.command("bundle")
def create_bundle(
    inputs: Annotated[
        str,
        typer.Option("--in", "-i", help="Comma-separated input paths (files or directories)"),
    ] = "./artifacts",
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output directory for bundle"),
    ] = Path("./artifacts"),
    sign: Annotated[
        bool,
        typer.Option("--sign/--no-sign", help="Sign the bundle"),
    ] = False,
    include_logs: Annotated[
        bool,
        typer.Option("--logs/--no-logs", help="Include log files in bundle"),
    ] = True,
    run_id: Annotated[
        Optional[str],
        typer.Option("--run-id", help="Custom run ID for the bundle"),
    ] = None,
) -> None:
    """
    Create a diagnostics bundle from findings and logs.

    Bundles findings.json, raw logs, and SHA256 manifest into a ZIP file.
    Supports optional signing.
    """
    typer.echo(f"📦 Creating diagnostics bundle")

    input_paths = [p.strip() for p in inputs.split(",")]

    tool = DiagnosticsBundleTool()
    result = asyncio.run(
        tool.execute(
            {
                "inputPaths": input_paths,
                "outputDir": str(out),
                "sign": sign,
                "includeLogs": include_logs,
                "runId": run_id,
            }
        )
    )

    typer.echo(f"[OK] Bundle created successfully")
    typer.echo(f"   Run ID: {result.get('runId')}")
    typer.echo(f"   Files: {result.get('fileCount')}")
    typer.echo(f"   Total checks: {result.get('totalChecks')}")
    typer.echo(f"📦 Bundle: {result.get('bundlePath')}")
    typer.echo(f"📋 Manifest: {result.get('manifestPath')}")

    if sign:
        typer.echo(f"🔐 Signature: {result.get('signaturePath', 'N/A')}")


@app.command()
def export(
    findings: Annotated[
        Path,
        typer.Option("--findings", "-f", help="Path to findings JSON file"),
    ] = Path("./artifacts/findings.json"),
    format: Annotated[
        str,
        typer.Option("--format", help="Export format: json, csv, html"),
    ] = "json",
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output file path"),
    ] = Path("./artifacts/export"),
) -> None:
    """
    Export findings to different formats.

    Supports JSON (default), CSV, and HTML export formats.
    """
    typer.echo(f"📤 Exporting findings to {format}")

    if not findings.exists():
        typer.echo(f"[ERROR] Findings file not found: {findings}", err=True)
        raise typer.Exit(code=1)

    with open(findings, "r", encoding="utf-8") as f:
        data = json.load(f)

    out.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        output_file = out.with_suffix(".json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    elif format == "csv":
        output_file = out.with_suffix(".csv")
        checks = data.get("checks", [])
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("id,title,severity,status,hint\n")
            for check in checks:
                hint = check.get("hint", "").replace('"', '""')
                f.write(
                    f'"{check.get("id")}","{check.get("title")}",'
                    f'"{check.get("severity")}","{check.get("status")}","{hint}"\n'
                )

    elif format == "html":
        output_file = out.with_suffix(".html")
        html = _generate_html_report(data)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

    else:
        typer.echo(f"[ERROR] Unsupported format: {format}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"[OK] Export complete: {output_file}")


def _generate_html_report(data: dict) -> str:
    """Generate a simple HTML report from findings."""
    summary = data.get("summary", {})
    checks = data.get("checks", [])

    status_colors = {
        "pass": "#10b981",
        "fail": "#ef4444",
        "warn": "#f59e0b",
        "skipped": "#6b7280",
    }

    checks_html = ""
    for check in checks:
        status = check.get("status", "unknown")
        color = status_colors.get(status, "#6b7280")
        checks_html += f"""
        <div class="check" style="border-left: 4px solid {color};">
            <h3>{check.get('title')}</h3>
            <p><strong>ID:</strong> {check.get('id')}</p>
            <p><strong>Severity:</strong> {check.get('severity')}</p>
            <p><strong>Status:</strong> <span style="color: {color};">{status.upper()}</span></p>
            {f"<p><strong>Hint:</strong> {check.get('hint')}</p>" if check.get('hint') else ""}
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ArcOps Findings Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f3f4f6; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header {{ background: #1f2937; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .summary {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .summary-card {{ background: white; padding: 15px 20px; border-radius: 8px; flex: 1; text-align: center; }}
        .summary-card h2 {{ margin: 0; font-size: 2em; }}
        .summary-card p {{ margin: 5px 0 0 0; color: #6b7280; }}
        .check {{ background: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 10px; }}
        .check h3 {{ margin: 0 0 10px 0; }}
        .check p {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ArcOps Findings Report</h1>
            <p>Generated: {data.get('timestamp', 'N/A')}</p>
            <p>Run ID: {data.get('runId', 'N/A')}</p>
        </div>
        <div class="summary">
            <div class="summary-card" style="border-top: 4px solid #10b981;">
                <h2>{summary.get('pass', 0)}</h2>
                <p>Passed</p>
            </div>
            <div class="summary-card" style="border-top: 4px solid #ef4444;">
                <h2>{summary.get('fail', 0)}</h2>
                <p>Failed</p>
            </div>
            <div class="summary-card" style="border-top: 4px solid #f59e0b;">
                <h2>{summary.get('warn', 0)}</h2>
                <p>Warnings</p>
            </div>
            <div class="summary-card" style="border-top: 4px solid #6b7280;">
                <h2>{summary.get('skipped', 0)}</h2>
                <p>Skipped</p>
            </div>
        </div>
        <h2>Checks</h2>
        {checks_html}
    </div>
</body>
</html>"""


@app.command()
def server(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to listen on"),
    ] = 8080,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Enable auto-reload for development"),
    ] = False,
) -> None:
    """
    Start the MCP HTTP server.

    Runs the FastAPI-based MCP server for tool invocation via HTTP.
    """
    typer.echo(f"🚀 Starting MCP server on {host}:{port}")

    import uvicorn

    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@app.command()
def version() -> None:
    """Show version information."""
    from cli import __version__

    typer.echo(f"arcops-mcp version {__version__}")


if __name__ == "__main__":
    app()
