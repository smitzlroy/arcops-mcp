"""
ArcOps MCP Server - Clean FastAPI server.

Simple, reliable server for the ArcOps UI.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Use the clean API routes
from server.api_routes_clean import router as api_router

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
    version="0.3.0",
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

# Include clean API routes
app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "ArcOps MCP Server",
        "version": "0.3.0",
        "docs": "/docs",
        "status": "/api/status",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
