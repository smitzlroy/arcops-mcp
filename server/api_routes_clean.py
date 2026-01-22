"""
Clean API Routes - Simple, reliable endpoints for the ArcOps UI.

Endpoints:
- GET  /api/status          - Overall system status
- GET  /api/models          - List all Foundry models
- POST /api/models/start    - Start a model
- POST /api/models/stop     - Stop current model
- POST /api/chat            - Send a chat message
- GET  /api/tools           - List available MCP tools
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.model_manager import model_manager
from server.chat_service import ChatService, TOOL_REGISTRY, get_tools_schema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Global chat service instance (initialized when model starts)
_chat_service: ChatService | None = None


# =============================================================================
# Request/Response Models
# =============================================================================


class StartModelRequest(BaseModel):
    model_id: str


class ChatRequest(BaseModel):
    message: str
    dry_run: bool = False


class ChatResponse(BaseModel):
    success: bool
    response: str
    tools_executed: list[dict] = []
    model: str | None = None
    error: str | None = None


# =============================================================================
# Status Endpoints
# =============================================================================


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get overall system status."""
    status = model_manager.get_status()

    return {
        "healthy": True,
        "model_running": status["model_running"],
        "current_model": status["current_model"],
        "endpoint": status["endpoint"],
        "tools_available": len(TOOL_REGISTRY),
    }


# =============================================================================
# Model Management Endpoints
# =============================================================================


@router.get("/models")
async def list_models() -> dict[str, Any]:
    """List all available Foundry Local models."""
    models = model_manager.list_models()

    # Group by recommendation
    recommended = [m.to_dict() for m in models if m.is_recommended]
    with_tools = [m.to_dict() for m in models if m.supports_tools and not m.is_recommended]
    chat_only = [m.to_dict() for m in models if not m.supports_tools]

    return {
        "models": [m.to_dict() for m in models],
        "groups": {
            "recommended": recommended,
            "with_tools": with_tools,
            "chat_only": chat_only,
        },
        "current_model": model_manager.current_model,
    }


@router.post("/models/start")
async def start_model(request: StartModelRequest) -> dict[str, Any]:
    """Start a Foundry model (downloads if needed)."""
    global _chat_service

    result = model_manager.start_model(request.model_id)

    if result["success"]:
        # Initialize chat service with the new model
        _chat_service = ChatService(endpoint=result["endpoint"], model=request.model_id)
        logger.info(f"Chat service initialized with {request.model_id}")

    return result


@router.post("/models/stop")
async def stop_model() -> dict[str, Any]:
    """Stop the currently running model."""
    global _chat_service

    result = model_manager.stop_model()

    if result["success"]:
        _chat_service = None

    return result


# =============================================================================
# Chat Endpoints
# =============================================================================


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a chat message and get a response with potential tool execution."""
    global _chat_service

    # Dry-run mode can work without a model (simulated response)
    if request.dry_run and not _chat_service:
        # Simulate a tool call based on keywords
        tools_executed = []
        response = ""

        message_lower = request.message.lower()

        if "connectivity" in message_lower or "egress" in message_lower:
            # Simulate connectivity check
            from server.chat_service import execute_tool

            result = await execute_tool("arc.connectivity.check", {"dryRun": True})
            tools_executed.append(
                {
                    "name": "arc.connectivity.check",
                    "arguments": {"dryRun": True},
                    "result_summary": f"Pass: {result.get('summary', {}).get('pass', 0)}, Fail: {result.get('summary', {}).get('fail', 0)}",
                }
            )
            response = f"**Connectivity Check Results (DRY-RUN)**\n\n✅ Checked 52 endpoints\n\nSummary:\n- Pass: {result.get('summary', {}).get('pass', 0)}\n- Fail: {result.get('summary', {}).get('fail', 0)}\n- Warn: {result.get('summary', {}).get('warn', 0)}"

        elif "validate" in message_lower or "cluster" in message_lower:
            from server.chat_service import execute_tool

            result = await execute_tool("aks.arc.validate", {"dryRun": True})
            tools_executed.append(
                {
                    "name": "aks.arc.validate",
                    "arguments": {"dryRun": True},
                    "result_summary": f"Pass: {result.get('summary', {}).get('pass', 0)}, Fail: {result.get('summary', {}).get('fail', 0)}",
                }
            )
            response = f"**Cluster Validation Results (DRY-RUN)**\n\n✅ Validated cluster\n\nSummary:\n- Pass: {result.get('summary', {}).get('pass', 0)}\n- Fail: {result.get('summary', {}).get('fail', 0)}\n- Warn: {result.get('summary', {}).get('warn', 0)}"

        elif "tsg" in message_lower or "error" in message_lower or "0x" in message_lower:
            from server.chat_service import execute_tool

            result = await execute_tool(
                "azlocal.tsg.search", {"errorText": request.message, "dryRun": True}
            )
            tools_executed.append(
                {
                    "name": "azlocal.tsg.search",
                    "arguments": {"errorText": request.message, "dryRun": True},
                    "result_summary": f"Found {result.get('resultCount', 0)} results",
                }
            )
            response = f"**TSG Search Results (DRY-RUN)**\n\nFound {result.get('resultCount', 0)} troubleshooting guides for your error."

        else:
            response = "🧪 **Dry-run mode enabled**\n\nI'm running without a model. Try asking about:\n- Connectivity checks\n- Cluster validation\n- Error codes (TSG search)"

        return ChatResponse(
            success=True,
            response=response,
            tools_executed=tools_executed,
            model="dry-run",
            error=None,
        )

    if not _chat_service:
        # Try to initialize with current running model
        status = model_manager.get_status()
        if status["model_running"] and status["endpoint"]:
            _chat_service = ChatService(endpoint=status["endpoint"], model=status["current_model"])
        else:
            raise HTTPException(status_code=503, detail="No model is running. Start a model first.")

    result = await _chat_service.chat(user_message=request.message, dry_run=request.dry_run)

    return ChatResponse(
        success=result["success"],
        response=result["response"],
        tools_executed=result.get("tools_executed", []),
        model=result.get("model"),
        error=result.get("error"),
    )


@router.post("/chat/reset")
async def reset_chat() -> dict[str, Any]:
    """Reset the conversation history."""
    global _chat_service

    if _chat_service:
        _chat_service.reset_conversation()

    return {"success": True, "message": "Conversation reset"}


# =============================================================================
# Tools Endpoints
# =============================================================================


@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    """List all available MCP tools."""
    tools = []
    for name, tool in TOOL_REGISTRY.items():
        tools.append(
            {
                "name": name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
        )

    return {
        "tools": tools,
        "count": len(tools),
    }


@router.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, arguments: dict[str, Any] = {}) -> dict[str, Any]:
    """Execute a specific MCP tool directly."""
    from server.chat_service import execute_tool as exec_tool

    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    result = await exec_tool(tool_name, arguments)
    return result
