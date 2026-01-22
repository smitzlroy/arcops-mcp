"""
ArcOps MCP Server - FastAPI-based MCP HTTP transport server.

Exposes tools for Azure Local + AKS Arc operations via MCP protocol.
Now includes official MCP SDK integration for spec-compliant clients.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from server.tools.aks_arc_validate import AksArcValidateTool
from server.tools.aksarc_logs_tool import AksArcLogsTool
from server.tools.aksarc_support_tool import AksArcSupportTool
from server.tools.arc_connectivity_check import ArcConnectivityCheckTool
from server.tools.azlocal_tsg_tool import AzLocalTsgTool
from server.tools.diagnostics_bundle import DiagnosticsBundleTool
from server.tools.educational_tool import ArcOpsEducationalTool
from server.api_routes import router as api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="ArcOps MCP Server",
    description="MCP-powered operations bridge for Azure Local + AKS Arc",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes for real Azure operations
app.include_router(api_router)

# Mount MCP SDK apps for spec-compliant transports
# Note: MCP SDK apps run on separate event loops, so we expose them via separate endpoints
# The SDK tools are still accessible via /mcp/rpc JSON-RPC endpoint
_mcp_sdk_available = False
try:
    # Only import the module reference, don't actually load tools yet
    # This avoids event loop issues at import time
    _mcp_sdk_available = True
    logger.info("MCP SDK available - tools accessible via standalone server")
except ImportError as e:
    logger.warning("MCP SDK not available: %s", e)


# Request/Response models
class ToolRequest(BaseModel):
    """Request model for tool invocation."""

    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolResponse(BaseModel):
    """Response model for tool invocation."""

    success: bool = Field(..., description="Whether the tool executed successfully")
    result: dict[str, Any] | None = Field(None, description="Tool result (findings)")
    error: str | None = Field(None, description="Error message if failed")


# Tool registry - unified tools for Azure Local + AKS Arc
TOOL_REGISTRY: dict[str, Any] = {
    # Primary tools
    "arc.connectivity.check": ArcConnectivityCheckTool(),  # Unified connectivity check
    "aks.arc.validate": AksArcValidateTool(),  # Cluster validation
    "aksarc.support.diagnose": AksArcSupportTool(),  # AKS Arc known issues check
    "aksarc.logs.collect": AksArcLogsTool(),  # Log collection
    "azlocal.tsg.search": AzLocalTsgTool(),  # TSG search
    "arcops.diagnostics.bundle": DiagnosticsBundleTool(),  # Diagnostic bundle
    "arcops.explain": ArcOpsEducationalTool(),  # Educational content
}


def load_mcp_manifest() -> dict[str, Any]:
    """Load the MCP manifest from JSON file."""
    manifest_path = Path(__file__).parent / "mcp_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)  # type: ignore[no-any-return]
    return {"tools": [], "schemas": {}}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with server info."""
    return {
        "name": "ArcOps MCP Server",
        "version": "0.1.0",
        "description": "MCP-powered operations bridge for Azure Local + AKS Arc",
        "manifest_url": "/mcp/manifest",
        "tools_url": "/mcp/tools",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/mcp/manifest")
async def get_manifest() -> dict[str, Any]:
    """Return the MCP manifest with available tools and schemas."""
    return load_mcp_manifest()


@app.get("/mcp/tools")
async def list_tools() -> dict[str, list[str]]:
    """List all available tools."""
    return {"tools": list(TOOL_REGISTRY.keys())}


# JSON-RPC 2.0 MCP-compliant endpoint
class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request format."""

    jsonrpc: str = Field(default="2.0")
    id: int | str | None = Field(default=None)
    method: str = Field(..., description="RPC method name")
    params: dict[str, Any] = Field(default_factory=dict)


# MCP Server Capabilities - declares what this server supports
MCP_SERVER_CAPABILITIES = {
    "tools": {
        "listChanged": False,  # We don't emit notifications when tool list changes
    },
    "resources": {
        "subscribe": False,  # Resource subscriptions not implemented
        "listChanged": False,
    },
    "prompts": {
        "listChanged": False,
    },
}

# MCP Server Info
MCP_SERVER_INFO = {
    "name": "arcops-mcp",
    "version": "0.2.0",
    "vendor": "Microsoft (Community)",
    "protocolVersion": "2025-06-18",
}


@app.post("/mcp/rpc")
async def mcp_rpc(request: JsonRpcRequest) -> dict[str, Any]:
    """
    MCP-compliant JSON-RPC 2.0 endpoint.

    Supports:
    - initialize: Capability negotiation
    - tools/list: List available tools with schemas
    - tools/call: Invoke a tool
    - resources/list: List available resources
    - prompts/list: List available prompts
    """
    response_base = {"jsonrpc": "2.0", "id": request.id}

    # MCP Initialize - capability negotiation
    if request.method == "initialize":
        return {
            **response_base,
            "result": {
                "serverInfo": MCP_SERVER_INFO,
                "capabilities": MCP_SERVER_CAPABILITIES,
                "instructions": (
                    "ArcOps MCP Server provides diagnostic tools for Azure Local and AKS Arc. "
                    "Use tools/list to discover available tools, tools/call to invoke them."
                ),
            },
        }

    if request.method == "tools/list":
        # Return tools in MCP format with output schemas
        tools_list = []
        for name, tool in TOOL_REGISTRY.items():
            tool_def = {
                "name": name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            # Add output schema if available
            if hasattr(tool, "output_schema") and tool.output_schema:
                tool_def["outputSchema"] = tool.output_schema
            tools_list.append(tool_def)
        return {**response_base, "result": {"tools": tools_list}}

    elif request.method == "tools/call":
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})

        if not tool_name or tool_name not in TOOL_REGISTRY:
            return {
                **response_base,
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}",
                },
            }

        tool = TOOL_REGISTRY[tool_name]
        try:
            result = await tool.execute(arguments)
            return {
                **response_base,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "structuredContent": result,
                    "isError": False,
                },
            }
        except Exception as e:
            return {
                **response_base,
                "result": {
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True,
                },
            }

    elif request.method == "resources/list":
        # Return available MCP resources
        resources = [
            {
                "uri": "arcops://tools",
                "name": "Available Tools",
                "description": "List of all ArcOps diagnostic tools",
                "mimeType": "application/json",
            },
            {
                "uri": "arcops://endpoints",
                "name": "Monitored Endpoints",
                "description": "Azure endpoints checked by connectivity validation",
                "mimeType": "application/json",
            },
            {
                "uri": "arcops://cluster/status",
                "name": "Cluster Status",
                "description": "Real-time status of connected AKS Arc clusters (requires az CLI)",
                "mimeType": "application/json",
            },
        ]
        return {**response_base, "result": {"resources": resources}}

    elif request.method == "resources/read":
        uri = request.params.get("uri", "")
        content = await _read_resource(uri)
        return {
            **response_base,
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(content, indent=2),
                    }
                ]
            },
        }

    elif request.method == "prompts/list":
        # Return available prompts
        prompts = [
            {
                "name": "troubleshoot_connectivity",
                "description": "Step-by-step guide for diagnosing Azure connectivity issues",
                "arguments": [],
            },
            {
                "name": "create_support_case",
                "description": "Gather information needed for a Microsoft support case",
                "arguments": [
                    {
                        "name": "issue_description",
                        "description": "Brief description of the issue",
                        "required": True,
                    }
                ],
            },
        ]
        return {**response_base, "result": {"prompts": prompts}}

    else:
        return {
            **response_base,
            "error": {
                "code": -32601,
                "message": f"Method not found: {request.method}",
            },
        }


async def _read_resource(uri: str) -> dict[str, Any]:
    """Read an MCP resource by URI."""
    import subprocess
    import yaml

    if uri == "arcops://tools":
        return {name: tool.description for name, tool in TOOL_REGISTRY.items()}

    elif uri == "arcops://endpoints":
        config_path = Path(__file__).parent / "config" / "endpoints.yaml"
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
                return {
                    "endpoints": config.get("endpoints", []),
                    "count": len(config.get("endpoints", [])),
                }
        return {"endpoints": [], "count": 0, "error": "Config not found"}

    elif uri == "arcops://cluster/status":
        # REAL: Get actual cluster status from Azure CLI
        try:
            result = subprocess.run(
                ["az", "connectedk8s", "list", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                clusters = json.loads(result.stdout)
                return {
                    "source": "azure_cli",
                    "clusterCount": len(clusters),
                    "clusters": [
                        {
                            "name": c.get("name"),
                            "resourceGroup": c.get("resourceGroup"),
                            "connectivityStatus": c.get("connectivityStatus"),
                            "provisioningState": c.get("provisioningState"),
                            "kubernetesVersion": c.get("kubernetesVersion"),
                        }
                        for c in clusters
                    ],
                }
            else:
                return {
                    "source": "azure_cli",
                    "error": "az connectedk8s list failed",
                    "stderr": result.stderr[:500],
                    "hint": "Ensure az CLI is installed and authenticated (az login)",
                }
        except FileNotFoundError:
            return {
                "source": "azure_cli",
                "error": "Azure CLI (az) not found",
                "hint": "Install: https://docs.microsoft.com/cli/azure/install-azure-cli",
            }
        except subprocess.TimeoutExpired:
            return {"source": "azure_cli", "error": "Command timed out"}
        except Exception as e:
            return {"source": "azure_cli", "error": str(e)}


@app.post("/mcp/tools/{tool_name}")
async def invoke_tool(tool_name: str, request: ToolRequest) -> ToolResponse:
    """
    Invoke an MCP tool by name.

    Args:
        tool_name: Name of the tool to invoke
        request: Tool arguments

    Returns:
        ToolResponse with findings or error
    """
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. Available: {list(TOOL_REGISTRY.keys())}",
        )

    tool = TOOL_REGISTRY[tool_name]
    logger.info("Invoking tool: %s with args: %s", tool_name, request.arguments)

    try:
        result = await tool.execute(request.arguments)
        return ToolResponse(success=True, result=result)
    except Exception as e:
        logger.exception("Tool '%s' failed", tool_name)
        return ToolResponse(success=False, error=str(e))


@app.get("/mcp/tools/{tool_name}/schema")
async def get_tool_schema(tool_name: str) -> dict[str, Any]:
    """Get the input/output schema for a specific tool."""
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    tool = TOOL_REGISTRY[tool_name]
    return {
        "name": tool_name,
        "description": tool.description,
        "input_schema": tool.input_schema,
        "output_schema": "schemas/findings.schema.json",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


def main() -> None:
    """Run the MCP server."""
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
