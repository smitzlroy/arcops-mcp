# ArcOps MCP Specification

> Detailed specification for the three readiness packs

## Overview

This document specifies the three readiness packs that form the core of the ArcOps pivot:

1. **Pack A: Supply-Chain Gate** — BYO model verification
2. **Pack B: Network Safety** — Ingress/egress policy generation and validation
3. **Pack C: GPU & Foundry Validation** — Hardware readiness and inference validation

Each pack follows the same structure:
- MCP tool definition (name, inputs, outputs)
- Artifact schema (JSON structure)
- CLI command interface
- Policy format (YAML)
- Acceptance criteria
- Test cases

---

## Pack A: Supply-Chain Gate

### Purpose
Gate every BYO (bring-your-own) model with signature verification, SBOM analysis, and policy evaluation before deployment to sovereign/edge clusters.

### MCP Tool Definition

```json
{
    "name": "supply_chain.gate",
    "description": "Verify BYO model image with signature, attestation, SBOM scan, and policy evaluation",
    "inputSchema": {
        "type": "object",
        "properties": {
            "image": {
                "type": "string",
                "description": "OCI image reference (e.g., oci://registry.local/models/yolo:1.0)"
            },
            "pubKey": {
                "type": "string",
                "description": "Path to public key file for signature verification"
            },
            "attestation": {
                "type": "string",
                "description": "Optional path to attestation file (DSSE/Notary v2)"
            },
            "policy": {
                "type": "string",
                "description": "Path to policy YAML file"
            },
            "outputPath": {
                "type": "string",
                "description": "Path to write approval artifact",
                "default": "artifacts/approval.json"
            }
        },
        "required": ["image", "pubKey", "policy"]
    },
    "outputSchema": {
        "$ref": "#/definitions/ApprovalArtifact"
    }
}
```

### Approval Artifact Schema

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ApprovalArtifact",
    "type": "object",
    "properties": {
        "version": {
            "type": "string",
            "const": "1.0.0"
        },
        "type": {
            "type": "string",
            "const": "approval"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time"
        },
        "runId": {
            "type": "string"
        },
        "metadata": {
            "type": "object",
            "properties": {
                "toolName": { "type": "string" },
                "toolVersion": { "type": "string" },
                "hostname": { "type": "string" }
            }
        },
        "image": {
            "type": "object",
            "properties": {
                "reference": { "type": "string" },
                "digest": { "type": "string" }
            },
            "required": ["reference", "digest"]
        },
        "signature": {
            "type": "object",
            "properties": {
                "validated": { "type": "boolean" },
                "signer": { "type": "string" },
                "algorithm": { "type": "string" },
                "timestamp": { "type": "string", "format": "date-time" }
            },
            "required": ["validated"]
        },
        "attestation": {
            "type": "object",
            "properties": {
                "validated": { "type": "boolean" },
                "type": { "type": "string" },
                "predicateType": { "type": "string" }
            }
        },
        "sbom": {
            "type": "object",
            "properties": {
                "source": { 
                    "type": "string",
                    "enum": ["embedded", "generated", "provided"]
                },
                "format": { "type": "string" },
                "packages": { "type": "integer" },
                "vulnerabilities": {
                    "type": "object",
                    "properties": {
                        "critical": { "type": "integer" },
                        "high": { "type": "integer" },
                        "medium": { "type": "integer" },
                        "low": { "type": "integer" }
                    }
                }
            }
        },
        "policy": {
            "type": "object",
            "properties": {
                "name": { "type": "string" },
                "version": { "type": "string" },
                "rulesEvaluated": { "type": "integer" },
                "rulesPassed": { "type": "integer" },
                "rulesFailed": { "type": "integer" },
                "failures": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule": { "type": "string" },
                            "reason": { "type": "string" }
                        }
                    }
                }
            }
        },
        "verdict": {
            "type": "string",
            "enum": ["GREEN", "AMBER", "RED"]
        },
        "reasons": {
            "type": "array",
            "items": { "type": "string" }
        },
        "artifactHash": {
            "type": "string",
            "pattern": "^sha256:[a-f0-9]{64}$"
        }
    },
    "required": ["version", "type", "timestamp", "runId", "image", "signature", "verdict", "artifactHash"]
}
```

### Policy Format

```yaml
# policies/supply-chain-default.yaml
name: supply-chain-default
version: "1.0"
description: Default supply chain policy for BYO models

rules:
  - name: require-signature
    description: Model must have valid signature
    condition: signature.validated == true
    verdict: GREEN
    failVerdict: RED
    
  - name: require-known-signer
    description: Signer must be in allowlist
    condition: signature.signer in allowedSigners
    verdict: GREEN
    failVerdict: AMBER
    
  - name: no-critical-cves
    description: No critical vulnerabilities allowed
    condition: sbom.vulnerabilities.critical == 0
    verdict: GREEN
    failVerdict: RED
    
  - name: max-high-cves
    description: Maximum 5 high vulnerabilities
    condition: sbom.vulnerabilities.high <= 5
    verdict: GREEN
    failVerdict: AMBER

settings:
  allowedSigners:
    - "org-ml@corp.local"
    - "release-bot@corp.local"
  allowedBaseImages:
    - "nvidia/cuda:*"
    - "python:3.11-slim"
  maxAge: "90d"  # Model must be signed within 90 days
```

### CLI Command

```bash
arcops supply-chain gate \
    --image oci://registry.local/models/yolo:1.0 \
    --pubkey keys/org.pub \
    --attestation attest/yolo.dsse \
    --policy policies/supply-chain-default.yaml \
    --out artifacts/approval.json
```

### Acceptance Criteria

1. ✅ Unsigned images produce RED verdict
2. ✅ Invalid signatures produce RED verdict
3. ✅ Critical CVEs produce RED verdict (configurable)
4. ✅ Missing attestation produces AMBER if required by policy
5. ✅ Deterministic: same inputs → same output
6. ✅ Works offline (uses cached vulnerability database)
7. ✅ Artifact includes complete evidence chain
8. ✅ Artifact hash is valid SHA-256

### Test Cases

| ID | Scenario | Expected Verdict |
|----|----------|------------------|
| SC-01 | Valid signature, no CVEs | GREEN |
| SC-02 | Valid signature, 2 high CVEs | GREEN |
| SC-03 | Valid signature, 1 critical CVE | RED |
| SC-04 | Invalid signature | RED |
| SC-05 | Missing signature | RED |
| SC-06 | Unknown signer (not in allowlist) | AMBER |
| SC-07 | Expired signature (>90 days) | AMBER |
| SC-08 | Missing attestation (required) | AMBER |
| SC-09 | Valid attestation, policy pass | GREEN |

---

## Pack B: Network Safety

### Purpose
Generate and validate Gateway API ingress and Istio egress policies with deny-by-default posture, namespace isolation, and TLS requirements.

### MCP Tool Definitions

#### network.safety (Validation)

```json
{
    "name": "network.safety",
    "description": "Validate network policy against security requirements",
    "inputSchema": {
        "type": "object",
        "properties": {
            "policy": {
                "type": "string",
                "description": "Path to network policy YAML file"
            },
            "outputPath": {
                "type": "string",
                "description": "Path to write safety report",
                "default": "artifacts/safety-report.json"
            }
        },
        "required": ["policy"]
    },
    "outputSchema": {
        "$ref": "#/definitions/SafetyReport"
    }
}
```

#### network.render (Generation)

```json
{
    "name": "network.render",
    "description": "Render Gateway API and Istio manifests from policy",
    "inputSchema": {
        "type": "object",
        "properties": {
            "policy": {
                "type": "string",
                "description": "Path to network policy YAML file"
            },
            "outputDir": {
                "type": "string",
                "description": "Directory to write manifests",
                "default": "manifests/network"
            }
        },
        "required": ["policy"]
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "ingressManifests": {
                "type": "array",
                "items": { "type": "string" }
            },
            "egressManifests": {
                "type": "array",
                "items": { "type": "string" }
            }
        }
    }
}
```

### Safety Report Schema

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SafetyReport",
    "type": "object",
    "properties": {
        "version": { "type": "string", "const": "1.0.0" },
        "type": { "type": "string", "const": "safety-report" },
        "timestamp": { "type": "string", "format": "date-time" },
        "runId": { "type": "string" },
        "metadata": {
            "type": "object",
            "properties": {
                "toolName": { "type": "string" },
                "toolVersion": { "type": "string" },
                "hostname": { "type": "string" }
            }
        },
        "policy": {
            "type": "object",
            "properties": {
                "name": { "type": "string" },
                "path": { "type": "string" },
                "namespaces": { "type": "integer" }
            }
        },
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": { "type": "string" },
                    "category": { 
                        "type": "string",
                        "enum": ["ingress", "egress", "tls", "namespace"]
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"]
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pass", "fail", "warn"]
                    },
                    "title": { "type": "string" },
                    "description": { "type": "string" },
                    "namespace": { "type": "string" },
                    "remediation": { "type": "string" }
                },
                "required": ["id", "category", "severity", "status", "title"]
            }
        },
        "summary": {
            "type": "object",
            "properties": {
                "total": { "type": "integer" },
                "pass": { "type": "integer" },
                "fail": { "type": "integer" },
                "warn": { "type": "integer" },
                "critical": { "type": "integer" },
                "high": { "type": "integer" }
            }
        },
        "verdict": {
            "type": "string",
            "enum": ["PASS", "FAIL", "WARN"]
        },
        "artifactHash": { "type": "string" }
    },
    "required": ["version", "type", "timestamp", "checks", "summary", "verdict"]
}
```

### Network Policy Format

```yaml
# policies/network-sovereign.yaml
name: network-sovereign
version: "1.0"
description: Sovereign network policy with strict egress control

global:
  tlsMinVersion: "1.2"
  requireGatewayAPI: true
  denyByDefault: true

namespaces:
  - name: ai-inference
    ingress:
      hosts:
        - "inference.internal.local"
        - "api.internal.local"
      tlsRequired: true
      tlsSecret: "ai-inference-tls"
      rateLimit:
        requestsPerSecond: 100
        burst: 200
    egress:
      mode: "deny-by-default"
      allowedCidrs:
        - "10.10.0.0/16"    # Internal services
        - "10.20.1.0/24"    # Database subnet
      allowedSNI:
        - "db.internal.local"
        - "cache.internal.local"
      allowedPorts:
        - 443
        - 5432
        - 6379

  - name: model-training
    ingress:
      hosts:
        - "training.internal.local"
      tlsRequired: true
    egress:
      mode: "deny-by-default"
      allowedCidrs:
        - "10.10.0.0/16"
      # No external SNI allowed for training namespace
```

### CLI Commands

```bash
# Validate policy
arcops network safety \
    --policy policies/network-sovereign.yaml \
    --out artifacts/safety-report.json

# Render manifests
arcops network render \
    --policy policies/network-sovereign.yaml \
    --out-dir manifests/network
```

### Acceptance Criteria

1. ✅ Detects wildcard egress (0.0.0.0/0) as CRITICAL
2. ✅ Detects missing TLS as HIGH
3. ✅ Detects non-allowlisted hosts as MEDIUM
4. ✅ Generates valid Gateway API HTTPRoute manifests
5. ✅ Generates valid Istio ServiceEntry/VirtualService manifests
6. ✅ Report includes remediation guidance
7. ✅ Manifests are idempotent (same policy → same manifests)

### Test Cases

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| NS-01 | Policy with all TLS, no wildcards | PASS |
| NS-02 | Policy with wildcard egress | FAIL (critical) |
| NS-03 | Policy missing TLS on public host | FAIL (high) |
| NS-04 | Policy with unknown CIDR | WARN (medium) |
| NS-05 | Render valid Gateway API | Valid YAML |
| NS-06 | Render valid Istio egress | Valid YAML |

---

## Pack C: GPU & Foundry Validation

### Purpose
Verify GPU hardware readiness and validate multi-model inference performance on Azure Local / AKS Arc clusters.

### MCP Tool Definitions

#### gpu.check

```json
{
    "name": "gpu.check",
    "description": "Check GPU presence, drivers, MIG configuration, and capacity",
    "inputSchema": {
        "type": "object",
        "properties": {
            "nodeSelector": {
                "type": "string",
                "description": "Optional Kubernetes node selector label"
            },
            "outputPath": {
                "type": "string",
                "description": "Path to write GPU readiness artifact",
                "default": "artifacts/gpu-readiness.json"
            }
        }
    },
    "outputSchema": {
        "$ref": "#/definitions/GpuReadiness"
    }
}
```

#### foundry.validate

```json
{
    "name": "foundry.validate",
    "description": "Validate multi-model inference with catalog and BYO models",
    "inputSchema": {
        "type": "object",
        "properties": {
            "catalogModel": {
                "type": "string",
                "description": "Foundry Local catalog model ID"
            },
            "byoImage": {
                "type": "string",
                "description": "BYO model OCI image reference (optional)"
            },
            "testAsset": {
                "type": "string",
                "description": "Path to test asset (image, text file, etc.)"
            },
            "thresholds": {
                "type": "string",
                "description": "Path to thresholds YAML file"
            },
            "outputPath": {
                "type": "string",
                "description": "Path to write validation artifact",
                "default": "artifacts/inference-validation.json"
            }
        },
        "required": ["catalogModel"]
    },
    "outputSchema": {
        "$ref": "#/definitions/InferenceValidation"
    }
}
```

### GPU Readiness Schema

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "GpuReadiness",
    "type": "object",
    "properties": {
        "version": { "type": "string", "const": "1.0.0" },
        "type": { "type": "string", "const": "gpu-readiness" },
        "timestamp": { "type": "string", "format": "date-time" },
        "runId": { "type": "string" },
        "metadata": {
            "type": "object",
            "properties": {
                "toolName": { "type": "string" },
                "toolVersion": { "type": "string" },
                "hostname": { "type": "string" },
                "node": { "type": "string" }
            }
        },
        "gpus": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": { "type": "integer" },
                    "name": { "type": "string" },
                    "uuid": { "type": "string" },
                    "memory": {
                        "type": "object",
                        "properties": {
                            "total": { "type": "string" },
                            "used": { "type": "string" },
                            "free": { "type": "string" }
                        }
                    },
                    "driver": { "type": "string" },
                    "cuda": { "type": "string" },
                    "mig": {
                        "type": "object",
                        "properties": {
                            "enabled": { "type": "boolean" },
                            "mode": { "type": "string" },
                            "instances": { "type": "integer" }
                        }
                    },
                    "temperature": { "type": "string" },
                    "utilization": { "type": "string" },
                    "healthy": { "type": "boolean" }
                }
            }
        },
        "summary": {
            "type": "object",
            "properties": {
                "totalGpus": { "type": "integer" },
                "healthyGpus": { "type": "integer" },
                "totalMemory": { "type": "string" },
                "availableMemory": { "type": "string" },
                "driverVersion": { "type": "string" },
                "cudaVersion": { "type": "string" }
            }
        },
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": { "type": "string" },
                    "title": { "type": "string" },
                    "status": { "type": "string", "enum": ["pass", "fail", "warn"] },
                    "detail": { "type": "string" }
                }
            }
        },
        "verdict": {
            "type": "string",
            "enum": ["READY", "DEGRADED", "NOT_READY"]
        },
        "artifactHash": { "type": "string" }
    },
    "required": ["version", "type", "timestamp", "gpus", "summary", "verdict"]
}
```

### Inference Validation Schema

```json
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "InferenceValidation",
    "type": "object",
    "properties": {
        "version": { "type": "string", "const": "1.0.0" },
        "type": { "type": "string", "const": "inference-validation" },
        "timestamp": { "type": "string", "format": "date-time" },
        "runId": { "type": "string" },
        "metadata": {
            "type": "object",
            "properties": {
                "toolName": { "type": "string" },
                "toolVersion": { "type": "string" },
                "hostname": { "type": "string" }
            }
        },
        "models": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": { "type": "string" },
                    "type": { "type": "string", "enum": ["catalog", "byo"] },
                    "image": { "type": "string" },
                    "loaded": { "type": "boolean" },
                    "loadTime": { "type": "string" }
                }
            }
        },
        "inference": {
            "type": "object",
            "properties": {
                "testAsset": { "type": "string" },
                "workflow": { "type": "string" },
                "iterations": { "type": "integer" },
                "metrics": {
                    "type": "object",
                    "properties": {
                        "latencyP50Ms": { "type": "number" },
                        "latencyP95Ms": { "type": "number" },
                        "latencyP99Ms": { "type": "number" },
                        "throughputRps": { "type": "number" },
                        "memoryPeakMb": { "type": "number" },
                        "gpuUtilization": { "type": "number" }
                    }
                }
            }
        },
        "thresholds": {
            "type": "object",
            "properties": {
                "name": { "type": "string" },
                "latencyP95MsMax": { "type": "number" },
                "memoryMbMax": { "type": "number" },
                "throughputRpsMin": { "type": "number" }
            }
        },
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": { "type": "string" },
                    "title": { "type": "string" },
                    "status": { "type": "string", "enum": ["pass", "fail"] },
                    "actual": { "type": "number" },
                    "threshold": { "type": "number" }
                }
            }
        },
        "verdict": {
            "type": "string",
            "enum": ["PASS", "FAIL"]
        },
        "artifactHash": { "type": "string" }
    },
    "required": ["version", "type", "timestamp", "models", "inference", "verdict"]
}
```

### Thresholds Policy Format

```yaml
# policies/inference-thresholds.yaml
name: inference-thresholds-default
version: "1.0"
description: Default performance thresholds for inference validation

thresholds:
  latencyP95MsMax: 200      # Max 200ms P95 latency
  latencyP99MsMax: 500      # Max 500ms P99 latency
  memoryMbMax: 16000        # Max 16GB memory
  throughputRpsMin: 5       # Minimum 5 requests/second
  gpuUtilizationMax: 95     # Max 95% GPU utilization

workflow:
  iterations: 10
  warmupIterations: 2
  cooldownSeconds: 5
```

### CLI Commands

```bash
# Check GPU readiness
arcops gpu check \
    --node-selector "gpu=true" \
    --out artifacts/gpu-readiness.json

# Validate inference
arcops foundry validate \
    --catalog-model qwen2.5-0.5b \
    --byo-image oci://registry.local/models/yolo:1.0 \
    --test-asset samples/test-image.jpg \
    --thresholds policies/inference-thresholds.yaml \
    --out artifacts/inference-validation.json
```

### Acceptance Criteria

1. ✅ Detects GPU presence via nvidia-smi or equivalent
2. ✅ Reports driver and CUDA versions
3. ✅ Detects MIG configuration
4. ✅ Validates memory availability
5. ✅ Loads and runs catalog model from Foundry Local
6. ✅ Measures latency p50/p95/p99
7. ✅ Measures memory consumption
8. ✅ Compares against configurable thresholds
9. ✅ Works without BYO model (catalog-only validation)

### Test Cases

| ID | Scenario | Expected Result |
|----|----------|-----------------|
| GPU-01 | GPU present, healthy | READY |
| GPU-02 | No GPU detected | NOT_READY |
| GPU-03 | GPU memory exhausted | DEGRADED |
| GPU-04 | Invalid driver version | DEGRADED |
| FV-01 | Catalog model, meets thresholds | PASS |
| FV-02 | Catalog model, exceeds latency | FAIL |
| FV-03 | Catalog + BYO, meets thresholds | PASS |
| FV-04 | Model fails to load | FAIL |

---

## Implementation Order

1. **Phase 1: Foundation**
   - Shared services (artifact signer, policy engine)
   - JSON schema files
   - Base test fixtures

2. **Phase 2: Pack A (Supply-Chain Gate)**
   - Highest PM interest
   - Proves the artifact-first pattern
   - Can demo with mock signature verification

3. **Phase 3: Pack B (Network Safety)**
   - Template generation
   - Policy validation
   - Builds on Pack A patterns

4. **Phase 4: Pack C (GPU & Foundry)**
   - Requires Foundry Local integration
   - Most complex, but high demo value
   - Can start with GPU check only

---

*This specification is the contract. All implementations must conform to these schemas and behaviors.*
