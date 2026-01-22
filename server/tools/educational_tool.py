"""
ArcOps Educational Content Tool.

Provides explanations, documentation, and learning paths for Azure Local and AKS Arc.
"""

from __future__ import annotations

from typing import Any

from server.tools.base import BaseTool


class ArcOpsEducationalTool(BaseTool):
    """
    Tool that provides educational content about Azure Local and AKS Arc.

    This tool helps users understand:
    - What each diagnostic tool does
    - How to interpret results
    - Learning paths for Azure Local and AKS Arc
    - Links to official documentation
    """

    name = "arcops.explain"
    description = "Get educational content about Azure Local and AKS Arc topics"
    input_schema = {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Topic to explain (connectivity, cluster_validation, known_issues, tsg_search, logs_collection, learning_path, or list)",
                "enum": [
                    "connectivity",
                    "cluster_validation",
                    "known_issues",
                    "tsg_search",
                    "logs_collection",
                    "learning_path",
                    "list",
                ],
            }
        },
        "required": ["topic"],
    }

    TOPICS: dict[str, dict[str, Any]] = {
        "connectivity": {
            "title": "Connectivity & Network Egress",
            "description": "Understanding Azure endpoint connectivity for Azure Local",
            "content": """
## Azure Connectivity for Azure Local

Azure Local requires connectivity to various Azure endpoints for management, updates, and services.

### What Gets Checked

1. **DNS Resolution** - Can we resolve Azure hostnames?
2. **TLS Certificates** - Are certificates valid and trusted?
3. **HTTP Reachability** - Can we establish HTTPS connections?
4. **Port Access** - Are required ports (443, 5671) accessible?

### Required Endpoints

Key endpoint categories:
- **Azure Resource Manager** (management.azure.com)
- **Azure Active Directory** (login.microsoftonline.com)
- **Azure Arc** (guestnotificationservice.azure.com)
- **Windows Update** (windowsupdate.microsoft.com)
- **Container Registry** (mcr.microsoft.com)

### Common Issues

- **Proxy Configuration**: Ensure proxy allows Azure endpoints
- **Firewall Rules**: Open ports 443 (HTTPS) and 5671 (AMQP)
- **DNS**: Azure DNS should be reachable
- **Certificate Trust**: Root CAs must be installed

### Tools Used

The `arc.connectivity.check` tool uses the Microsoft Environment Checker to validate all required endpoints.
            """,
            "links": [
                {
                    "title": "Azure Local Firewall Requirements",
                    "url": "https://learn.microsoft.com/azure-stack/hci/concepts/firewall-requirements",
                },
                {
                    "title": "Azure Arc Network Requirements",
                    "url": "https://learn.microsoft.com/azure/azure-arc/servers/network-requirements",
                },
            ],
        },
        "cluster_validation": {
            "title": "AKS Arc Cluster Validation",
            "description": "Understanding AKS Arc cluster health checks",
            "content": """
## AKS Arc Cluster Validation

AKS Arc clusters run Kubernetes on Azure Local. Validation checks ensure the cluster is healthy and properly configured.

### What Gets Validated

1. **Node Status** - Are all nodes Ready?
2. **Pod Health** - Are system pods running?
3. **Connectivity Status** - Is Azure Arc connected?
4. **Kubernetes Version** - Is it supported?
5. **Agent Version** - Is the Arc agent current?

### Key Components

- **Control Plane**: API server, etcd, controllers
- **Azure Arc Agents**: Connect cluster to Azure
- **System Pods**: CoreDNS, kube-proxy, CNI
- **Node Pools**: Worker nodes with compute

### Common Issues

- **Node NotReady**: Check kubelet, networking, disk space
- **Pod CrashLoopBackOff**: Check logs, resources, config
- **Disconnected State**: Network/proxy issues with Azure

### Tools Used

The `aks.arc.validate` tool runs `kubectl` commands and Azure CLI to validate cluster health.
            """,
            "links": [
                {
                    "title": "AKS Arc Overview",
                    "url": "https://learn.microsoft.com/azure/aks/hybrid/aks-hybrid-options-overview",
                },
                {
                    "title": "Troubleshoot AKS Arc",
                    "url": "https://learn.microsoft.com/azure/aks/hybrid/troubleshoot-known-issues",
                },
            ],
        },
        "known_issues": {
            "title": "Known Issues & Support Diagnostics",
            "description": "Understanding AKS Arc known issues detection",
            "content": """
## AKS Arc Known Issues Detection

Microsoft provides PowerShell tools to detect known issues that have documented resolutions.

### What Gets Checked

The Support.AksArc module checks for:
- Known configuration problems
- Version compatibility issues
- Common misconfigurations
- Issues with documented fixes

### How It Works

1. Runs `Test-SupportAksArcKnownIssues` cmdlet
2. Compares cluster state to known issue patterns
3. Returns matches with resolution guidance
4. Includes links to official documentation

### Result States

- **Pass**: No known issues detected
- **Fail**: Known issue found - follow resolution steps
- **Warn**: Potential issue that needs verification

### Using Results

Each finding includes:
- Issue description
- Why it matters
- Steps to resolve
- Documentation link

### Tools Used

The `aksarc.support.diagnose` tool wraps the Support.AksArc PowerShell module.
            """,
            "links": [
                {
                    "title": "Support.AksArc Module",
                    "url": "https://www.powershellgallery.com/packages/Support.AksArc",
                },
                {
                    "title": "AKS Arc Known Issues",
                    "url": "https://learn.microsoft.com/azure/aks/hybrid/troubleshoot-known-issues",
                },
            ],
        },
        "tsg_search": {
            "title": "Troubleshooting Guide (TSG) Search",
            "description": "Searching Azure Local troubleshooting documentation",
            "content": """
## Azure Local TSG Search

Troubleshooting Guides (TSGs) are structured documents that help resolve specific issues.

### What Is a TSG?

A TSG contains:
- **Symptom**: How the problem manifests
- **Cause**: Why the problem occurs
- **Resolution**: Steps to fix it
- **Verification**: How to confirm it's resolved

### How Search Works

1. Query is matched against TSG content
2. Results are ranked by relevance
3. Includes GitHub links to full documents
4. Searches across Azure Local TSG repository

### Using TSG Results

When you find a relevant TSG:
1. Read the symptoms to confirm match
2. Check the cause section
3. Follow resolution steps in order
4. Verify the fix worked

### TSG Sources

TSGs come from:
- Microsoft official documentation
- Azure Local GitHub repository
- Community contributions

### Tools Used

The `azlocal.tsg.search` tool uses the AzLocalTSGTool PowerShell module.
            """,
            "links": [
                {
                    "title": "Azure Local Troubleshooting",
                    "url": "https://learn.microsoft.com/azure-stack/hci/manage/troubleshoot",
                },
                {
                    "title": "AzLocalTSGTool",
                    "url": "https://www.powershellgallery.com/packages/AzLocalTSGTool",
                },
            ],
        },
        "logs_collection": {
            "title": "Log Collection for Support",
            "description": "Collecting diagnostic logs for Microsoft Support",
            "content": """
## AKS Arc Log Collection

When working with Microsoft Support, you may need to collect diagnostic logs.

### What Gets Collected

The log collection gathers:
- **Kubernetes Logs**: API server, kubelet, pods
- **System Logs**: Windows Event logs, Linux journals
- **Network Logs**: CNI, networking diagnostics
- **Azure Arc Logs**: Agent logs, connectivity info

### Output Format

Logs are collected into:
- ZIP archive for easy sharing
- Organized directory structure
- Includes timestamps
- Can be uploaded to support case

### Privacy Considerations

Logs may contain:
- Node names and IPs
- Pod/service names
- Configuration details
- Error messages

Review before sharing and redact sensitive data if needed.

### When to Use

Collect logs when:
- Opening a support case
- Requested by Microsoft Support
- Debugging complex issues
- Before making major changes

### Tools Used

The `aksarc.logs.collect` tool uses `az aksarc get-logs` Azure CLI command.
            """,
            "links": [
                {
                    "title": "Collect AKS Arc Logs",
                    "url": "https://learn.microsoft.com/azure/aks/hybrid/collect-logs",
                },
                {
                    "title": "Create Support Request",
                    "url": "https://learn.microsoft.com/azure/azure-supportability/how-to-create-azure-support-request",
                },
            ],
        },
        "learning_path": {
            "title": "Azure Local & AKS Arc Learning Path",
            "description": "Recommended learning resources and progression",
            "content": """
## Learning Path: Azure Local & AKS Arc

### Beginner Level

1. **Understand Azure Local**
   - What is Azure Local (formerly Azure Stack HCI)?
   - Hybrid cloud concepts
   - When to use Azure Local

2. **Azure Arc Fundamentals**
   - What is Azure Arc?
   - Arc-enabled servers
   - Arc-enabled Kubernetes

3. **Kubernetes Basics**
   - Pods, Services, Deployments
   - kubectl commands
   - YAML manifests

### Intermediate Level

4. **Deploy Azure Local**
   - Hardware requirements
   - Network planning
   - Deployment options

5. **Set Up AKS Arc**
   - Create management cluster
   - Deploy workload clusters
   - Configure networking

6. **Day-2 Operations**
   - Monitoring and logging
   - Updates and patching
   - Scaling clusters

### Advanced Level

7. **Troubleshooting**
   - Using diagnostic tools
   - Reading logs
   - Network debugging

8. **Security**
   - RBAC configuration
   - Network policies
   - Secrets management

9. **Integration**
   - GitOps with Flux
   - Azure services integration
   - Multi-cluster management

### Certifications

- AZ-900: Azure Fundamentals
- AZ-104: Azure Administrator
- AZ-305: Azure Solutions Architect
- CKA: Certified Kubernetes Administrator
            """,
            "links": [
                {
                    "title": "Azure Local Documentation",
                    "url": "https://learn.microsoft.com/azure-stack/hci/",
                },
                {
                    "title": "AKS Arc Documentation",
                    "url": "https://learn.microsoft.com/azure/aks/hybrid/",
                },
                {
                    "title": "Azure Arc Learn Path",
                    "url": "https://learn.microsoft.com/training/paths/manage-hybrid-infrastructure-with-azure-arc/",
                },
            ],
        },
    }

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the educational tool and return content for the requested topic."""
        topic = arguments.get("topic", "list")

        if topic == "list":
            # Return list of available topics
            topics_list: list[dict[str, str]] = [
                {"id": tid, "title": str(tdata["title"]), "description": str(tdata["description"])}
                for tid, tdata in self.TOPICS.items()
            ]
            return {
                "success": True,
                "type": "topic_list",
                "topics": topics_list,
                "hint": "Use arcops.explain with a topic to get detailed content",
            }

        if topic not in self.TOPICS:
            return {
                "success": False,
                "error": f"Unknown topic: {topic}. Use 'list' to see available topics.",
            }

        topic_data = self.TOPICS[topic]

        return {
            "success": True,
            "type": "educational_content",
            "topic": topic,
            "title": topic_data["title"],
            "description": topic_data["description"],
            "content": topic_data["content"].strip(),
            "links": topic_data["links"],
            "related_topics": [t for t in self.TOPICS.keys() if t != topic][:3],
        }
