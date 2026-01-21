# External Sources & References

This document contains references to official Microsoft documentation used by ArcOps MCP tools. All checks reference these sources rather than hardcoding internal URLs.

> **Note**: URLs are provided as reference. Verify current documentation as Microsoft may update URLs.

## Azure Arc

### arc-required-endpoints
**Azure Arc-enabled servers network requirements**
- Official documentation for required endpoints for Azure Arc connectivity
- https://learn.microsoft.com/azure/azure-arc/servers/network-requirements

### arc-extensions
**Azure Arc-enabled Kubernetes cluster extensions**
- Documentation for managing extensions on Arc-enabled Kubernetes clusters
- https://learn.microsoft.com/azure/azure-arc/kubernetes/extensions

### arc-gitops
**GitOps with Flux v2 on Azure Arc-enabled Kubernetes**
- Guide for GitOps configurations using Flux
- https://learn.microsoft.com/azure/azure-arc/kubernetes/conceptual-gitops-flux2

## Azure Local (formerly Azure Stack HCI)

### azure-local-environment-checker
**Azure Local Environment Checker**
- Pre-deployment validation tool for Azure Local
- https://learn.microsoft.com/azure-stack/hci/manage/use-environment-checker

### azure-local-networking
**Azure Local networking requirements**
- Network configuration and requirements
- https://learn.microsoft.com/azure-stack/hci/concepts/network-requirements

### azure-local-firewall
**Firewall requirements for Azure Local**
- Required firewall rules and endpoints
- https://learn.microsoft.com/azure-stack/hci/concepts/firewall-requirements

## AKS Arc (AKS on Azure Local)

### aks-arc-overview
**AKS enabled by Azure Arc overview**
- Overview of running AKS on Azure Local
- https://learn.microsoft.com/azure/aks/hybrid/aks-overview

### aks-arc-networking
**AKS Arc networking concepts**
- CNI options and network configuration
- https://learn.microsoft.com/azure/aks/hybrid/concepts-networking

### aks-arc-versions
**Supported Kubernetes versions**
- Version support matrix for AKS Arc
- https://learn.microsoft.com/azure/aks/hybrid/supported-kubernetes-versions

### aks-arc-validation
**AKS Arc cluster validation**
- Validation and troubleshooting guidance
- https://learn.microsoft.com/azure/aks/hybrid/validate-deployment

## Diagnostics & Troubleshooting

### arc-troubleshooting
**Troubleshoot Azure Arc-enabled Kubernetes**
- Common issues and resolutions
- https://learn.microsoft.com/azure/azure-arc/kubernetes/troubleshooting

### azure-local-diagnostics
**Collect diagnostic logs for Azure Local**
- Log collection and diagnostic procedures
- https://learn.microsoft.com/azure-stack/hci/manage/collect-logs

### support-diagnostics
**Get support for Azure Local**
- Support options and diagnostic bundle creation
- https://learn.microsoft.com/azure-stack/hci/manage/get-support

## Security & Compliance

### arc-security
**Security overview for Azure Arc-enabled servers**
- Security considerations and best practices
- https://learn.microsoft.com/azure/azure-arc/servers/security-overview

### azure-local-security
**Security considerations for Azure Local**
- Security features and configuration
- https://learn.microsoft.com/azure-stack/hci/concepts/security

---

## Adding New Sources

When adding a new check that references external documentation:

1. Add an anchor entry to this file with:
   - Unique anchor ID (lowercase, hyphenated)
   - Descriptive title
   - Brief description
   - Official Microsoft Learn URL

2. Reference in code using:
   ```python
   self.get_source_ref("anchor-id", "Human-readable label")
   ```

3. Never hardcode URLs in tool code - always use this reference file.

## Verification

Sources should be verified periodically as Microsoft may:
- Update URLs
- Restructure documentation
- Deprecate content

Last verified: January 2025
