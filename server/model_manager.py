"""
Foundry Model Manager - Clean interface for Foundry Local model operations.

Handles:
- Listing all available models
- Checking downloaded status
- Starting/stopping models
- Detecting tool support
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FoundryModel:
    """Represents a Foundry Local model."""

    alias: str
    model_id: str
    size: str
    license: str
    device: str
    tasks: list[str]
    downloaded: bool = False
    running: bool = False

    @property
    def supports_tools(self) -> bool:
        """Check if this model supports function calling."""
        return "tools" in self.tasks

    @property
    def is_recommended(self) -> bool:
        """Check if this is a recommended model for our use case."""
        # Recommended models: tool support + good size/quality balance
        recommended = [
            "phi-4-mini",  # Best overall - Microsoft, 3.6GB, excellent
            "qwen2.5-7b",  # Good balance - 4.7GB
            "qwen2.5-coder-7b",  # Code-focused - 4.7GB
        ]
        return self.alias in recommended

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.alias,
            "name": self._format_name(),
            "model_id": self.model_id,
            "size": self.size,
            "license": self.license,
            "device": self.device,
            "tasks": self.tasks,
            "supports_tools": self.supports_tools,
            "downloaded": self.downloaded,
            "running": self.running,
            "recommended": self.is_recommended,
        }

    def _format_name(self) -> str:
        """Create a display name for the model."""
        name = self.alias.replace("-", " ").title()
        return name


class ModelManager:
    """
    Manages Foundry Local models.
    """

    def __init__(self):
        self._endpoint: str | None = None
        self._current_model: str | None = None

    @property
    def endpoint(self) -> str | None:
        """Get the current Foundry endpoint."""
        return self._endpoint

    @property
    def current_model(self) -> str | None:
        """Get the currently running model."""
        return self._current_model

    def list_models(self) -> list[FoundryModel]:
        """
        List all available Foundry Local models.

        Returns:
            List of FoundryModel objects with download/running status
        """
        models = []

        # Get available models from Foundry
        available = self._get_available_models()

        # Get downloaded models
        downloaded = self._get_downloaded_models()

        # Get currently running model
        running = self._get_running_model()

        # Merge information
        for alias, info in available.items():
            model = FoundryModel(
                alias=alias,
                model_id=info.get("model_id", ""),
                size=info.get("size", "Unknown"),
                license=info.get("license", "Unknown"),
                device=info.get("device", "Unknown"),
                tasks=info.get("tasks", ["chat"]),
                downloaded=alias in downloaded,
                running=alias == running,
            )
            models.append(model)

        # Sort: recommended first, then by tool support, then by name
        models.sort(key=lambda m: (not m.is_recommended, not m.supports_tools, m.alias))

        return models

    def _get_available_models(self) -> dict[str, dict]:
        """Parse foundry model list output."""
        try:
            result = subprocess.run(
                ["foundry", "model", "list"], capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                logger.error(f"foundry model list failed: {result.stderr}")
                return {}

            return self._parse_model_list(result.stdout)

        except FileNotFoundError:
            logger.error("Foundry CLI not found")
            return {}
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return {}

    def _parse_model_list(self, output: str) -> dict[str, dict]:
        """Parse the foundry model list text output."""
        models = {}
        current_alias = None

        # Known models with their properties (from Foundry documentation)
        # This is more reliable than parsing the variable-width CLI output
        known_models = {
            # Tool-capable models
            "qwen2.5-0.5b": {"tasks": ["chat", "tools"], "size": "0.52 GB"},
            "qwen2.5-1.5b": {"tasks": ["chat", "tools"], "size": "1.25 GB"},
            "qwen2.5-7b": {"tasks": ["chat", "tools"], "size": "4.73 GB"},
            "qwen2.5-14b": {"tasks": ["chat", "tools"], "size": "8.79 GB"},
            "qwen2.5-coder-0.5b": {"tasks": ["chat", "tools"], "size": "0.52 GB"},
            "qwen2.5-coder-1.5b": {"tasks": ["chat", "tools"], "size": "1.25 GB"},
            "qwen2.5-coder-7b": {"tasks": ["chat", "tools"], "size": "4.73 GB"},
            "qwen2.5-coder-14b": {"tasks": ["chat", "tools"], "size": "8.79 GB"},
            "phi-4-mini": {"tasks": ["chat", "tools"], "size": "3.60 GB"},
            # Chat-only models
            "phi-4": {"tasks": ["chat"], "size": "8.37 GB"},
            "phi-3.5-mini": {"tasks": ["chat"], "size": "2.13 GB"},
            "phi-3-mini-128k": {"tasks": ["chat"], "size": "2.13 GB"},
            "phi-3-mini-4k": {"tasks": ["chat"], "size": "2.13 GB"},
            "mistral-7b-v0.2": {"tasks": ["chat"], "size": "3.98 GB"},
            "deepseek-r1-1.5b": {"tasks": ["chat"], "size": "1.43 GB"},
            "deepseek-r1-7b": {"tasks": ["chat"], "size": "5.28 GB"},
            "deepseek-r1-14b": {"tasks": ["chat"], "size": "9.83 GB"},
            "phi-4-mini-reasoning": {"tasks": ["chat"], "size": "3.15 GB"},
            "gpt-oss-20b": {"tasks": ["chat"], "size": "12.26 GB"},
        }

        # Parse output to find which aliases are available
        lines = output.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("-") or line.startswith("Alias"):
                continue

            # Check if this line starts with a known alias
            parts = line.split()
            if parts:
                potential_alias = parts[0]
                if potential_alias in known_models and potential_alias not in models:
                    info = known_models[potential_alias]
                    models[potential_alias] = {
                        "model_id": potential_alias,
                        "size": info["size"],
                        "license": "MIT",
                        "device": "GPU",
                        "tasks": info["tasks"],
                    }

        # If parsing failed, return the known models
        if not models:
            models = {
                k: {
                    "model_id": k,
                    "size": v["size"],
                    "license": "MIT",
                    "device": "GPU",
                    "tasks": v["tasks"],
                }
                for k, v in known_models.items()
            }

        return models

    def _get_downloaded_models(self) -> set[str]:
        """Get set of downloaded model aliases."""
        downloaded = set()

        try:
            result = subprocess.run(
                ["foundry", "cache", "list"],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    # Skip header lines
                    if "Alias" in line or "cached" in line.lower() or not line.strip():
                        continue
                    # Extract alias - it's the first non-emoji word on lines with models
                    # Remove any special characters and find the alias
                    clean_line = line.strip()
                    # Split and find the model alias (skip emoji characters)
                    parts = clean_line.split()
                    for part in parts:
                        # Model aliases are lowercase with dots and dashes
                        if part and part[0].isalnum() and "-" in part or "." in part:
                            if part not in ["Model", "ID"]:
                                downloaded.add(part)
                                break

        except Exception as e:
            logger.error(f"Failed to get downloaded models: {e}")

        return downloaded

    def _get_running_model(self) -> str | None:
        """Get the currently running model alias."""
        try:
            # Try to use foundry-local-python if available
            from foundry_local import FoundryLocalManager

            manager = FoundryLocalManager()
            loaded = manager.list_loaded_models()
            if loaded:
                # loaded[0] is a FoundryModelInfo object with an alias attribute
                model_info = loaded[0]
                alias = (
                    model_info.alias
                    if hasattr(model_info, "alias")
                    else str(model_info).split("-instruct")[0].lower()
                )
                self._endpoint = manager.endpoint
                self._current_model = alias
                return alias
        except Exception as e:
            logger.debug(f"FoundryLocalManager check failed: {e}")

        return None

    def start_model(self, alias: str) -> dict[str, Any]:
        """
        Start a Foundry model (downloads if needed).

        Args:
            alias: Model alias (e.g., "phi-4-mini")

        Returns:
            Dictionary with success status and endpoint
        """
        logger.info(f"Starting model: {alias}")

        try:
            # Use foundry-local-python for proper model management
            from foundry_local import FoundryLocalManager

            manager = FoundryLocalManager(alias)
            endpoint = manager.endpoint

            self._endpoint = endpoint
            self._current_model = alias

            return {
                "success": True,
                "model": alias,
                "endpoint": endpoint,
                "message": f"Model {alias} is running",
            }

        except Exception as e:
            logger.error(f"Failed to start model {alias}: {e}")
            return {
                "success": False,
                "error": str(e),
                "hint": "Make sure Foundry Local is installed and running",
            }

    def stop_model(self) -> dict[str, Any]:
        """Stop the currently running model."""
        try:
            result = subprocess.run(
                ["foundry", "service", "stop"], capture_output=True, text=True, timeout=30
            )

            self._endpoint = None
            self._current_model = None

            return {"success": True, "message": "Model stopped"}

        except Exception as e:
            logger.error(f"Failed to stop model: {e}")
            return {"success": False, "error": str(e)}

    def get_status(self) -> dict[str, Any]:
        """Get current model status."""
        running = self._get_running_model()

        return {
            "model_running": running is not None,
            "current_model": running,
            "endpoint": self._endpoint,
        }


# Global instance
model_manager = ModelManager()
