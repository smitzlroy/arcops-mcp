# Privacy & Security Guidelines

## Overview

ArcOps MCP Bridge is designed with sovereignty and security as core principles. This document outlines the security model and privacy considerations.

## Sovereign-Safe Design

### Offline by Default

- **No Background Egress**: The system never initiates outbound connections without explicit operator action
- **No Telemetry**: No data is sent to external services automatically
- **Local Artifacts**: All outputs remain on the local filesystem until explicitly exported

### Explicit Outbound Actions

When network access is required (e.g., egress checks), the following principles apply:

1. **Operator Initiated**: All network operations require explicit CLI flags or API calls
2. **Visible**: Network targets are clearly displayed before any connection
3. **Configurable**: All endpoints are defined in `config/endpoints.yaml`
4. **Auditable**: All operations are logged with timestamps

## Secret Management

### What We DO NOT Store

- Azure AD credentials
- Kubernetes tokens
- API keys
- Certificates private keys
- Tenant IDs (hardcoded)

### Where Secrets Should Live

| Secret Type | Recommended Location |
|-------------|---------------------|
| Kubeconfig | `~/.kube/config` with proper permissions |
| Proxy credentials | Environment variables (`HTTP_PROXY`) |
| CA certificates | System trust store or `ca_bundle` config |
| Service principals | Azure Key Vault or environment variables |

### Environment Variables

```bash
# Proxy (if required)
export HTTP_PROXY=http://proxy:8080
export HTTPS_PROXY=http://proxy:8080
export NO_PROXY=localhost,127.0.0.1

# Azure (if required for authenticated checks)
export AZURE_TENANT_ID=<from-keyvault>
export AZURE_CLIENT_ID=<from-keyvault>
export AZURE_CLIENT_SECRET=<from-keyvault>
```

## Data Handling

### Sensitive Data Redaction

The tools automatically redact sensitive information:

- **Kubernetes**: Bearer tokens, certificates
- **Proxy**: Authentication credentials
- **Azure**: Subscription IDs (partial), tenant info

### Evidence Packs

Evidence packs (`bundle.zip`) may contain:

| Content | Sensitivity | Handling |
|---------|-------------|----------|
| `findings.json` | Low | Safe to share |
| `sha256sum.txt` | Low | Safe to share |
| Raw logs | Medium | Review before sharing |
| Config dumps | High | May need redaction |

### Log Sanitization

Before sharing logs:

1. Review for IP addresses
2. Check for hostnames
3. Remove any tokens/keys
4. Redact user identifiers

## Network Security

### TLS Validation

- All HTTPS connections validate certificates by default
- Corporate CA chains are supported via config
- Certificate errors are logged but don't expose certificate content

### Proxy Support

- HTTP(S)_PROXY environment variables respected
- Proxy credentials should use environment variables
- No proxy credentials are logged

## Access Control

### File Permissions

```bash
# Configuration files
chmod 600 server/config/endpoints.yaml

# Artifacts directory
chmod 700 artifacts/

# Evidence packs
chmod 600 artifacts/**/bundle.zip
```

### CODEOWNERS

Protected paths require review:
- `/schemas/` - Contract changes
- `/server/config/` - Configuration
- `/.github/workflows/` - CI/CD

## Audit Trail

### What Gets Logged

- Tool invocations (name, arguments, timestamp)
- Check results (pass/fail/warn/skipped)
- Error conditions (without sensitive details)
- Run IDs for correlation

### What Does NOT Get Logged

- Credentials
- Full request/response bodies with secrets
- Certificate private keys
- Token values

## Incident Response

### If Secrets Are Exposed

1. Rotate affected credentials immediately
2. Review git history for commits
3. Check CI/CD logs
4. Review evidence packs

### Security Contact

Report security issues via GitHub Security Advisories (private disclosure).

## Compliance Considerations

### Air-Gapped Environments

ArcOps MCP is designed to work in air-gapped environments:

1. Use `--dry-run` flags for offline testing
2. Pre-populate fixtures for expected checks
3. Export evidence packs manually

### Regulatory Requirements

- **Audit Logs**: All operations are traceable via run IDs
- **Data Locality**: All data stays local by default
- **Access Control**: Integrates with OS-level permissions

## Best Practices

1. **Never commit secrets** - Use `.gitignore` and pre-commit hooks
2. **Review before sharing** - Check evidence packs for sensitive data
3. **Use environment variables** - For any sensitive configuration
4. **Regular rotation** - Rotate credentials periodically
5. **Principle of least privilege** - Only request necessary permissions
