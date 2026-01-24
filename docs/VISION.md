# ArcOps MCP Vision

> **Edge AI Readiness, Trust & Safety Platform for Azure Local and AKS Arc**

## Mission

Enable sovereign and edge AI deployments to be **predictable, auditable, and safe** by providing standardized readiness gates, supply-chain trust verification, and runtime safety policies—all accessible through the Model Context Protocol (MCP).

## Problem Statement

Organizations deploying AI models to Azure Local and AKS Arc face critical challenges:

1. **No standardized readiness checks** — Teams manually verify GPU drivers, networking, and cluster health before model deployment
2. **BYO model trust gaps** — Custom models lack verification for signatures, attestations, and vulnerability scanning
3. **Network policy drift** — Ingress/egress configurations are ad-hoc, leading to security exposure
4. **Multi-model complexity** — GPU sharing and co-deployment validation is manual and error-prone

## Solution

ArcOps MCP provides **three strategic packs** that gate and validate AI deployments:

| Pack | Purpose | Outcome |
|------|---------|---------|
| **A. Supply-Chain Gate** | Verify BYO model signatures, attestations, SBOM | GREEN/AMBER/RED approval artifact |
| **B. Network Safety** | Generate & validate Gateway API + Istio policies | Deny-by-default ingress/egress manifests |
| **C. GPU & Foundry Validation** | Check GPU health, validate multi-model inference | Readiness + performance artifacts |

## Design Principles

### 1. Artifacts are the Product
Every tool produces **signed JSON artifacts** that are:
- Machine-readable for automation
- Human-reviewable for audit
- Storable alongside deployment manifests
- Consumable by LLM agents

### 2. Offline-First, Connected-Ready
Design for three connectivity tiers:
- **Air-gapped**: All checks run with local caches
- **Restricted egress**: Optional enrichment through proxy
- **Connected sovereign**: Opportunistic updates, local decisions

### 3. MCP as the Contract
Tools are exposed via Model Context Protocol:
- Consistent request/response schemas
- Agent-friendly (Foundry Local, Copilot, Claude)
- CLI and UI are thin wrappers over MCP

### 4. Fail-Closed by Default
- Missing signatures → RED
- Unknown egress → DENIED
- GPU not ready → BLOCKED

## Target Users

| Persona | Need | ArcOps Value |
|---------|------|--------------|
| **AI/ML Engineer** | Deploy BYO models safely | Supply-chain gate, performance validation |
| **Cluster SRE** | Consistent network policies | Safety pack templates, violation reports |
| **Security Architect** | Audit trail for AI deployments | Signed artifacts, attestation verification |
| **Platform PM** | Reduce time-to-first-inference | Standardized readiness gates |

## Non-Goals

- **Not a product** — This is a platform pattern and prototype
- **Not a dashboard** — UI is for evidence review, not monitoring
- **Not replacing Azure services** — Complements, not competes

## Success Metrics

1. **Time-to-first-inference** reduced by 50%+
2. **100% of BYO models** pass supply-chain gate before deployment
3. **Zero wildcard egress** in production namespaces
4. **Reproducible GPU readiness** across sites

## Alignment

This work directly supports:
- **Foundry Local** — BYO model workflows, agent tool calling
- **AKS Arc** — Cluster readiness, network policies
- **Azure Local** — Sovereign/offline AI deployments
- **Edge AI team priorities** — Trust, governance, multi-model GPU sharing

---

*Built for sovereign AI operators who need confidence before deployment.*
