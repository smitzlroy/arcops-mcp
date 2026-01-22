"""
Azure Local TSG Search Tool - Wrapper for AzLocalTSGTool.

Thin wrapper that exposes the AzLocalTSGTool PowerShell module via MCP.
The module handles GitHub indexing and local caching internally.

References:
- https://www.powershellgallery.com/packages/AzLocalTSGTool
- https://github.com/smitzlroy/azlocaltsgtool
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Coroutine

from server.tools.base import BaseTool

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class AzLocalTsgTool(BaseTool):
    """
    Wrapper for AzLocalTSGTool Search-AzLocalTSG cmdlet.

    Searches Azure Local troubleshooting guides by keyword, error message,
    or symptom. The module handles GitHub content indexing and local caching.
    """

    name = "azlocal.tsg.search"
    description = (
        "Search Azure Local troubleshooting guides using AzLocalTSGTool. "
        "The module handles GitHub indexing and local caching."
    )
    input_schema = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": "Error message, symptom, or keyword to search",
            },
            "dryRun": {
                "type": "boolean",
                "default": False,
                "description": "Return fixture data without running actual search",
            },
        },
    }

    async def execute(
        self,
        arguments: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Execute TSG search."""
        query = arguments.get("query", "")
        dry_run = arguments.get("dryRun", False)

        if not query:
            return {
                "success": False,
                "error": "Query parameter is required",
                "results": [],
            }

        start_time = time.time()

        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Checking for AzLocalTSGTool module...",
                    "phase": "detect",
                }
            )

        # Check if module is installed
        module_info = self._check_module_installed()

        if dry_run:
            return await self._run_dry_run(query, progress_callback)
        elif not module_info["installed"]:
            return {
                "success": False,
                "query": query,
                "results": [],
                "error": "AzLocalTSGTool module not installed",
                "hint": "Install-Module -Name AzLocalTSGTool -Force",
                "module": module_info,
            }
        else:
            return await self._run_search(query, module_info, start_time, progress_callback)

    def _check_module_installed(self) -> dict[str, Any]:
        """Check if AzLocalTSGTool PowerShell module is installed."""
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-Command",
                    "Get-Module -ListAvailable AzLocalTSGTool | "
                    "Select-Object Name, Version, Path | ConvertTo-Json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                try:
                    module_data = json.loads(result.stdout.strip())
                    if isinstance(module_data, list):
                        module_data = module_data[0]
                    return {
                        "installed": True,
                        "name": module_data.get("Name"),
                        "version": module_data.get("Version"),
                        "path": module_data.get("Path"),
                    }
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug("Module check failed: %s", e)

        return {
            "installed": False,
            "hint": "Install-Module -Name AzLocalTSGTool -Force",
        }

    async def _run_search(
        self,
        query: str,
        module_info: dict[str, Any],
        start_time: float,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Run Search-AzLocalTSG and return results."""
        logger.info("Running Search-AzLocalTSG for query: %s", query)

        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": f"Searching TSGs for: {query}",
                    "phase": "search",
                }
            )

        try:
            # Escape the query for PowerShell
            escaped_query = query.replace("'", "''")

            ps_cmd = f"""
            Import-Module AzLocalTSGTool -Force
            $results = Search-AzLocalTSG -Query '{escaped_query}'
            $results | ConvertTo-Json -Depth 10
            """

            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=120,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.returncode == 0:
                try:
                    search_results = (
                        json.loads(result.stdout.strip()) if result.stdout.strip() else []
                    )

                    # Ensure it's a list
                    if isinstance(search_results, dict):
                        search_results = [search_results]
                    elif search_results is None:
                        search_results = []

                    if progress_callback:
                        await progress_callback(
                            {
                                "type": "complete",
                                "message": f"Found {len(search_results)} TSG matches",
                                "resultCount": len(search_results),
                            }
                        )

                    return {
                        "success": True,
                        "query": query,
                        "resultCount": len(search_results),
                        "results": search_results,
                        "durationMs": duration_ms,
                        "module": module_info,
                    }
                except json.JSONDecodeError:
                    # Module ran but output wasn't JSON
                    return {
                        "success": True,
                        "query": query,
                        "resultCount": 0,
                        "results": [],
                        "rawOutput": result.stdout[:2000] if result.stdout else None,
                        "note": "Search completed but no structured results returned",
                        "durationMs": duration_ms,
                    }
            else:
                return {
                    "success": False,
                    "query": query,
                    "results": [],
                    "error": result.stderr[:1000] if result.stderr else "Search failed",
                    "durationMs": duration_ms,
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "query": query,
                "results": [],
                "error": "Search timed out after 120 seconds",
            }
        except Exception as e:
            logger.exception("Unexpected error running TSG search")
            return {
                "success": False,
                "query": query,
                "results": [],
                "error": str(e),
            }

    async def _run_dry_run(
        self,
        query: str,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Return fixture data for testing."""
        if progress_callback:
            await progress_callback(
                {
                    "type": "status",
                    "message": "Loading fixture data (dry run)...",
                    "phase": "dry-run",
                }
            )

        # Load fixture if available
        fixture_path = (
            Path(__file__).parent.parent.parent / "tests" / "fixtures" / "tsg_search_sample.json"
        )
        if fixture_path.exists():
            try:
                with open(fixture_path, "r", encoding="utf-8") as f:
                    fixture_data = json.load(f)

                results = fixture_data.get("results", [])

                if progress_callback:
                    await progress_callback(
                        {
                            "type": "complete",
                            "message": f"Dry run: {len(results)} sample results",
                            "resultCount": len(results),
                        }
                    )

                return {
                    "success": True,
                    "query": query,
                    "resultCount": len(results),
                    "results": results,
                    "dryRun": True,
                    "fixtureUsed": str(fixture_path),
                }
            except Exception as e:
                logger.warning("Failed to load fixture: %s", e)

        # Return sample data if no fixture
        sample_results = self._get_sample_results(query)

        if progress_callback:
            await progress_callback(
                {
                    "type": "complete",
                    "message": f"Dry run: {len(sample_results)} sample results",
                    "resultCount": len(sample_results),
                }
            )

        return {
            "success": True,
            "query": query,
            "resultCount": len(sample_results),
            "results": sample_results,
            "dryRun": True,
        }

    def _get_sample_results(self, query: str) -> list[dict[str, Any]]:
        """Return sample TSG results for dry run."""
        return [
            {
                "title": "Troubleshoot Azure Local Connectivity Issues",
                "category": "Networking",
                "url": "https://github.com/Azure/AzureLocal-Supportability/blob/main/TSG/Networking/Outbound-Connectivity.md",
                "relevance": 0.85,
                "summary": "Common connectivity issues and resolution steps for Azure Local deployments.",
            },
            {
                "title": "AKS Arc Certificate Rotation",
                "category": "AKS",
                "url": "https://github.com/Azure/AzureLocal-Supportability/blob/main/TSG/AKS/cert-rotation.md",
                "relevance": 0.72,
                "summary": "Steps to troubleshoot and resolve certificate expiration issues in AKS Arc.",
            },
        ]
