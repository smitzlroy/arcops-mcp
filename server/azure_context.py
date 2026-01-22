"""
Azure Context Manager - Manages Azure CLI authentication state.

Provides a clean interface for checking Azure authentication,
getting subscription context, and ensuring tools have proper access.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AzureAuthStatus:
    """Azure authentication status."""

    authenticated: bool
    az_cli_installed: bool
    subscription_id: str | None = None
    subscription_name: str | None = None
    tenant_id: str | None = None
    user: str | None = None
    user_type: str | None = None
    error: str | None = None
    hint: str | None = None


class AzureContext:
    """
    Manages Azure CLI authentication state.

    This class provides methods to check authentication status,
    get current subscription context, and ensure tools can access Azure.
    """

    _az_cmd: str | None = None

    @classmethod
    def find_az_cli(cls) -> str | None:
        """Find Azure CLI executable, checking common paths."""
        if cls._az_cmd:
            return cls._az_cmd

        # Try standard PATH first
        az_cmd = shutil.which("az")
        if az_cmd:
            cls._az_cmd = az_cmd
            return az_cmd

        # Try common Windows paths
        windows_paths = [
            r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
            r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
            r"C:\Users\{}\AppData\Local\Programs\Microsoft VS Code\bin\az.cmd",
        ]

        for path in windows_paths:
            expanded = Path(path.format(Path.home().name))
            if expanded.exists():
                cls._az_cmd = str(expanded)
                return cls._az_cmd

        return None

    @classmethod
    async def check_auth(cls) -> AzureAuthStatus:
        """
        Check if Azure CLI is authenticated and return status.

        Returns:
            AzureAuthStatus with authentication details or error info.
        """
        az_cmd = cls.find_az_cli()

        if not az_cmd:
            return AzureAuthStatus(
                authenticated=False,
                az_cli_installed=False,
                error="Azure CLI (az) not found",
                hint="Install Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli",
            )

        try:
            # Check current account
            result = subprocess.run(
                [az_cmd, "account", "show", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Check if it's an auth error vs other error
                stderr = result.stderr.lower()
                if "please run 'az login'" in stderr or "no subscription" in stderr:
                    return AzureAuthStatus(
                        authenticated=False,
                        az_cli_installed=True,
                        error="Not logged in to Azure",
                        hint="Run 'az login' to authenticate",
                    )
                else:
                    return AzureAuthStatus(
                        authenticated=False,
                        az_cli_installed=True,
                        error=result.stderr.strip(),
                        hint="Check Azure CLI configuration",
                    )

            account = json.loads(result.stdout)

            return AzureAuthStatus(
                authenticated=True,
                az_cli_installed=True,
                subscription_id=account.get("id"),
                subscription_name=account.get("name"),
                tenant_id=account.get("tenantId"),
                user=account.get("user", {}).get("name"),
                user_type=account.get("user", {}).get("type"),
            )

        except subprocess.TimeoutExpired:
            return AzureAuthStatus(
                authenticated=False,
                az_cli_installed=True,
                error="Azure CLI command timed out",
                hint="Check network connectivity or try again",
            )
        except json.JSONDecodeError as e:
            return AzureAuthStatus(
                authenticated=False,
                az_cli_installed=True,
                error=f"Failed to parse Azure CLI response: {e}",
                hint="Azure CLI may need to be updated",
            )
        except Exception as e:
            logger.exception("Error checking Azure auth")
            return AzureAuthStatus(
                authenticated=False,
                az_cli_installed=True,
                error=str(e),
            )

    @classmethod
    async def get_subscriptions(cls) -> dict[str, Any]:
        """Get list of available Azure subscriptions."""
        az_cmd = cls.find_az_cli()

        if not az_cmd:
            return {"success": False, "subscriptions": [], "error": "Azure CLI not found"}

        try:
            result = subprocess.run(
                [az_cmd, "account", "list", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return {"success": False, "subscriptions": [], "error": result.stderr}

            subscriptions = json.loads(result.stdout)
            return {
                "success": True,
                "subscriptions": [
                    {
                        "id": sub.get("id"),
                        "name": sub.get("name"),
                        "isDefault": sub.get("isDefault", False),
                        "state": sub.get("state"),
                    }
                    for sub in subscriptions
                ],
            }

        except Exception as e:
            return {"success": False, "subscriptions": [], "error": str(e)}

    @classmethod
    async def set_subscription(cls, subscription_id: str) -> dict[str, Any]:
        """Set the active Azure subscription."""
        az_cmd = cls.find_az_cli()

        if not az_cmd:
            return {"success": False, "error": "Azure CLI not found"}

        try:
            result = subprocess.run(
                [az_cmd, "account", "set", "--subscription", subscription_id],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return {"success": False, "error": result.stderr}

            return {"success": True, "subscription_id": subscription_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    async def get_connected_clusters(cls, subscription: str | None = None) -> dict[str, Any]:
        """
        Get Arc-connected Kubernetes clusters.

        Args:
            subscription: Optional subscription ID to query

        Returns:
            Dict with success status and cluster list
        """
        az_cmd = cls.find_az_cli()

        if not az_cmd:
            return {
                "success": False,
                "clusters": [],
                "error": "Azure CLI not found",
                "hint": "Install Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli",
            }

        # First verify we're authenticated
        auth_status = await cls.check_auth()
        if not auth_status.authenticated:
            return {
                "success": False,
                "clusters": [],
                "error": auth_status.error,
                "hint": auth_status.hint,
            }

        try:
            cmd = [az_cmd, "connectedk8s", "list", "-o", "json"]
            if subscription:
                cmd.extend(["--subscription", subscription])

            logger.info("Running: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                # Check for common errors
                if "extension" in error_msg.lower() and "not installed" in error_msg.lower():
                    return {
                        "success": False,
                        "clusters": [],
                        "error": "connectedk8s extension not installed",
                        "hint": "Run: az extension add --name connectedk8s",
                    }
                return {
                    "success": False,
                    "clusters": [],
                    "error": error_msg,
                }

            clusters = json.loads(result.stdout)

            # Extract key info for each cluster
            cluster_summaries = [
                {
                    "name": c.get("name"),
                    "resourceGroup": c.get("resourceGroup"),
                    "location": c.get("location"),
                    "connectivityStatus": c.get("connectivityStatus"),
                    "provisioningState": c.get("provisioningState"),
                    "kubernetesVersion": c.get("kubernetesVersion"),
                    "agentVersion": c.get("agentVersion"),
                    "distribution": c.get("distribution"),
                    "infrastructure": c.get("infrastructure"),
                    "totalNodeCount": c.get("totalNodeCount"),
                    "lastConnectivityTime": c.get("lastConnectivityTime"),
                }
                for c in clusters
            ]

            return {
                "success": True,
                "count": len(clusters),
                "clusters": cluster_summaries,
                "subscription": subscription or auth_status.subscription_id,
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "clusters": [], "error": "Command timed out"}
        except json.JSONDecodeError as e:
            return {"success": False, "clusters": [], "error": f"Failed to parse response: {e}"}
        except Exception as e:
            logger.exception("Error listing clusters")
            return {"success": False, "clusters": [], "error": str(e)}

    @classmethod
    def to_api_response(cls, auth_status: AzureAuthStatus) -> dict[str, Any]:
        """Convert AzureAuthStatus to API-friendly dict."""
        response = {
            "authenticated": auth_status.authenticated,
            "azCliInstalled": auth_status.az_cli_installed,
        }

        if auth_status.authenticated:
            response["subscription"] = {
                "id": auth_status.subscription_id,
                "name": auth_status.subscription_name,
            }
            response["tenant"] = auth_status.tenant_id
            response["user"] = auth_status.user
            response["userType"] = auth_status.user_type
        else:
            response["error"] = auth_status.error
            response["hint"] = auth_status.hint

        return response
