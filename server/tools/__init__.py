"""Tools package for ArcOps MCP server."""

from __future__ import annotations

# Existing diagnostic tools
from server.tools.aks_arc_validate import AksArcValidateTool
from server.tools.aksarc_logs_tool import AksArcLogsTool
from server.tools.aksarc_support_tool import AksArcSupportTool
from server.tools.arc_connectivity_check import ArcConnectivityCheckTool
from server.tools.arc_gateway_egress_check import ArcGatewayEgressCheckTool
from server.tools.azlocal_envcheck_wrap import AzLocalEnvCheckWrapTool
from server.tools.azlocal_tsg_tool import AzLocalTsgTool
from server.tools.diagnostics_bundle import DiagnosticsBundleTool
from server.tools.educational_tool import ArcOpsEducationalTool

# New readiness packs
from server.tools.packs.supply_chain_gate import SupplyChainGateTool
from server.tools.packs.network_safety import NetworkSafetyTool, NetworkRenderTool
from server.tools.packs.gpu_check import GpuCheckTool
from server.tools.packs.foundry_validate import FoundryValidateTool

__all__ = [
    # Existing diagnostic tools
    "AksArcValidateTool",
    "AksArcLogsTool",
    "AksArcSupportTool",
    "ArcConnectivityCheckTool",
    "ArcGatewayEgressCheckTool",
    "AzLocalEnvCheckWrapTool",
    "AzLocalTsgTool",
    "DiagnosticsBundleTool",
    "ArcOpsEducationalTool",
    # New readiness packs
    "SupplyChainGateTool",
    "NetworkSafetyTool",
    "NetworkRenderTool",
    "GpuCheckTool",
    "FoundryValidateTool",
]
