"""
ArcOps MCP Server - FastAPI-based MCP HTTP transport server.

Exposes tools for Azure Local + AKS Arc operations via MCP protocol.
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
from server.tools.arc_connectivity_check import ArcConnectivityCheckTool
from server.tools.diagnostics_bundle import DiagnosticsBundleTool
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
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes for real Azure operations
app.include_router(api_router)


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
    "arcops.diagnostics.bundle": DiagnosticsBundleTool(),  # Diagnostic bundle
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
