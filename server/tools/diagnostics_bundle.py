"""
Diagnostics Bundle Tool.

Creates a diagnostics bundle ZIP with findings.json, raw logs, and SHA256 manifest.
References: docs/SOURCES.md#diagnostics-bundle
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.tools.base import BaseTool

logger = logging.getLogger(__name__)


class DiagnosticsBundleTool(BaseTool):
    """
    Tool to create diagnostics bundle with findings, logs, and manifest.

    Supports optional signing (stub for MVP).
    """

    name = "arcops.diagnostics.bundle"
    description = (
        "Create a diagnostics bundle ZIP with findings.json, raw logs, and SHA256 manifest. "
        "Optional signing support."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "inputPaths": {
                "type": "array",
                "items": {"type": "string"},
            },
            "outputDir": {"type": "string", "default": "./artifacts"},
            "sign": {"type": "boolean", "default": False},
            "includeLogs": {"type": "boolean", "default": True},
            "runId": {"type": "string"},
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Create diagnostics bundle."""
        input_paths = arguments.get("inputPaths", [])
        output_dir = arguments.get("outputDir", "./artifacts")
        sign = arguments.get("sign", False)
        include_logs = arguments.get("includeLogs", True)
        run_id = arguments.get("runId") or self.generate_run_id()

        # Create output directory
        output_path = Path(output_dir) / run_id
        output_path.mkdir(parents=True, exist_ok=True)

        bundle_path = output_path / "bundle.zip"
        manifest_path = output_path / "sha256sum.txt"

        # Collect files to bundle
        files_to_bundle: list[tuple[Path, str]] = []
        combined_findings: dict[str, Any] = {
            "version": "0.1.0",
            "target": "bundle",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runId": run_id,
            "metadata": {
                "toolName": self.name,
                "toolVersion": "0.1.0",
                "bundleType": "diagnostics",
            },
            "sources": [],
            "checks": [],
            "summary": {
                "total": 0,
                "pass": 0,
                "fail": 0,
                "warn": 0,
                "skipped": 0,
            },
        }

        # Process input paths
        for input_path in input_paths:
            path = Path(input_path)
            if path.is_file():
                if path.suffix == ".json":
                    await self._process_json_file(path, combined_findings, files_to_bundle)
                elif include_logs:
                    files_to_bundle.append((path, f"logs/{path.name}"))
            elif path.is_dir():
                await self._process_directory(path, combined_findings, files_to_bundle, include_logs)

        # Write combined findings
        findings_file = output_path / "findings.json"
        with open(findings_file, "w", encoding="utf-8") as f:
            json.dump(combined_findings, f, indent=2)
        files_to_bundle.append((findings_file, "findings.json"))

        # Create manifest
        manifest_entries: list[str] = []
        for file_path, archive_name in files_to_bundle:
            sha256 = await self._compute_sha256(file_path)
            manifest_entries.append(f"{sha256}  {archive_name}")

        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("\n".join(manifest_entries) + "\n")
        files_to_bundle.append((manifest_path, "sha256sum.txt"))

        # Create ZIP bundle
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path, archive_name in files_to_bundle:
                zf.write(file_path, archive_name)

        # Optional signing (stub)
        signature_path = None
        if sign:
            signature_path = await self._sign_bundle(bundle_path)

        result = {
            "bundlePath": str(bundle_path.absolute()),
            "manifestPath": str(manifest_path.absolute()),
            "findingsPath": str(findings_file.absolute()),
            "runId": run_id,
            "fileCount": len(files_to_bundle),
            "totalChecks": combined_findings["summary"]["total"],
            "signed": sign,
        }

        if signature_path:
            result["signaturePath"] = signature_path

        return result

    async def _process_json_file(
        self,
        path: Path,
        combined_findings: dict[str, Any],
        files_to_bundle: list[tuple[Path, str]],
    ) -> None:
        """Process a JSON findings file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if this is a findings file
            if "checks" in data and isinstance(data["checks"], list):
                # Merge checks
                for check in data["checks"]:
                    combined_findings["checks"].append(check)
                    status = check.get("status", "")
                    combined_findings["summary"]["total"] += 1
                    if status in combined_findings["summary"]:
                        combined_findings["summary"][status] += 1

                # Track source
                combined_findings["sources"].append({
                    "file": path.name,
                    "target": data.get("target"),
                    "timestamp": data.get("timestamp"),
                    "runId": data.get("runId"),
                })

            # Add to bundle
            files_to_bundle.append((path, f"findings/{path.name}"))

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON file %s: %s", path, e)
        except Exception as e:
            logger.warning("Failed to process file %s: %s", path, e)

    async def _process_directory(
        self,
        path: Path,
        combined_findings: dict[str, Any],
        files_to_bundle: list[tuple[Path, str]],
        include_logs: bool,
    ) -> None:
        """Process all files in a directory."""
        for item in path.iterdir():
            if item.is_file():
                if item.suffix == ".json":
                    await self._process_json_file(item, combined_findings, files_to_bundle)
                elif include_logs and item.suffix in [".log", ".txt", ".yaml", ".yml"]:
                    files_to_bundle.append((item, f"logs/{item.name}"))

    async def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    async def _sign_bundle(self, bundle_path: Path) -> str | None:
        """
        Sign the bundle (stub implementation).

        In production, this would use a signing key from:
        - Azure Key Vault
        - Local certificate store
        - Environment variable

        Returns path to signature file or None if signing failed.
        """
        logger.info("Bundle signing requested but not implemented in MVP")

        # Stub: Create a placeholder signature file
        signature_path = bundle_path.with_suffix(".sig")

        # In production, would do something like:
        # from cryptography.hazmat.primitives import hashes
        # from cryptography.hazmat.primitives.asymmetric import padding
        # private_key.sign(bundle_hash, padding.PKCS1v15(), hashes.SHA256())

        signature_content = {
            "warning": "This is a stub signature for MVP",
            "bundle": bundle_path.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "algorithm": "SHA256withRSA",
            "signed": False,
        }

        with open(signature_path, "w", encoding="utf-8") as f:
            json.dump(signature_content, f, indent=2)

        return str(signature_path.absolute())
