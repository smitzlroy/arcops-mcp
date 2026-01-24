"""
Artifact signing service for ArcOps MCP.

Provides SHA-256 hashing and optional cryptographic signing for artifacts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


class ArtifactSigner:
    """Signs and verifies artifact integrity."""

    def __init__(self, signer_identity: str = "arcops-mcp"):
        self.signer_identity = signer_identity

    def compute_hash(self, data: dict[str, Any], exclude_fields: list[str] | None = None) -> str:
        """
        Compute SHA-256 hash of artifact data.

        Args:
            data: The artifact data to hash
            exclude_fields: Fields to exclude from hashing (e.g., artifactHash itself)

        Returns:
            SHA-256 hash prefixed with 'sha256:'
        """
        exclude_fields = exclude_fields or ["artifactHash"]

        # Create copy without excluded fields
        data_to_hash = {k: v for k, v in data.items() if k not in exclude_fields}

        # Serialize deterministically
        json_str = json.dumps(data_to_hash, sort_keys=True, separators=(",", ":"))

        # Compute hash
        hash_bytes = hashlib.sha256(json_str.encode("utf-8")).hexdigest()

        return f"sha256:{hash_bytes}"

    def sign_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        """
        Add hash and signing metadata to artifact.

        Args:
            artifact: The artifact to sign

        Returns:
            Artifact with artifactHash field added
        """
        # Add signing metadata
        artifact["_signed"] = {
            "signer": self.signer_identity,
            "signedAt": datetime.now(timezone.utc).isoformat(),
        }

        # Compute and add hash
        artifact["artifactHash"] = self.compute_hash(artifact)

        return artifact

    def verify_artifact(self, artifact: dict[str, Any]) -> bool:
        """
        Verify artifact hash is valid.

        Args:
            artifact: The artifact to verify

        Returns:
            True if hash is valid
        """
        if "artifactHash" not in artifact:
            return False

        stored_hash = artifact["artifactHash"]
        computed_hash = self.compute_hash(artifact)

        return stored_hash == computed_hash


# Module-level convenience instance and function
_default_signer = ArtifactSigner()


def sign_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Sign artifact with default signer."""
    return _default_signer.sign_artifact(artifact)


def verify_artifact(artifact: dict[str, Any]) -> bool:
    """Verify artifact with default signer."""
    return _default_signer.verify_artifact(artifact)
