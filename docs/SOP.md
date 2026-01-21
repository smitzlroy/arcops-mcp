# SOP — ArcOps MCP Bridge (Azure Local + AKS Arc)

## Purpose

Deliver a sovereign-safe, MCP-powered operations bridge that exposes deterministic, auditable tools for Azure Local and AKS enabled by Azure Arc—focusing on validation (pre/post), diagnostics bundles, and evidence packs—without duplicating Microsoft tools. This project wraps and normalizes outputs from existing checkers (e.g., Azure Local Environment Checker, Supportability TSG scripts) into a versioned Findings JSON contract plus a signed evidence bundle.

## Scope

### In-scope (MVP v0.1.x):

**MCP server (HTTP transport) exposing tools:**
- `azlocal.envcheck.wrap` (wrap and normalize Environment Checker outputs)
- `arc.gateway.egress.check` (TLS/Proxy/FQDN reachability checks via configurable endpoints)
- `aks.arc.validate` (read-only cluster invariants: extension presence/health, CNI mode, version pins; returns "skipped" when kubeconfig/cluster is unavailable)
- `arcops.diagnostics.bundle` (ZIP with findings.json, raw logs, SHA256 manifest, optional signing)

**Contracts first:** `schemas/findings.schema.json` (pass|fail|warn; evidence; doc links; sources; versioned).

**Sovereign-first defaults:** No egress; no background agents; explicit operator actions for any outbound steps.

**Quality gates:** type hints, docstrings, unit tests, lint, static type check, pre-commit.

**CI:** GitHub Actions for lint/mypy/pytest + UI build check.

### Out-of-scope (MVP):
- Any "new dashboard" duplicating Azure Portal or Portainer.
- Auto-remediation. (We emit scripts as suggestions; operators copy-paste.)
- Re-implementing Microsoft check logic. (We wrap & normalize only.)

## Principles

1. **Integrate, don't replicate:** call Environment Checker & TSG scripts; normalize results; cite sources.
2. **Sovereign-safe:** local-only by default; clearly label any optional cloud usage.
3. **Contracts-first:** nothing merges without a schema-backed test for every new finding.
4. **Deterministic & auditable:** every run produces a reproducible evidence pack.
5. **MCP everywhere:** same tools callable from VS Code, Foundry Local, or future Azure agents.

## Architecture (MVP)

```
arcops-mcp/
  server/                # FastAPI-based MCP server (HTTP transport)
    main.py              # MCP dispatcher + tool registry
    tools/
      azlocal_envcheck_wrap.py
      arc_gateway_egress_check.py
      aks_arc_validate.py
      diagnostics_bundle.py
    mcp_manifest.json    # Advertises tools + schemas for MCP clients
    config/
      endpoints.yaml     # FQDN/port list for egress checks (env/tenant specific)
  cli/
    __main__.py          # Typer CLI: envcheck, validate, egress, bundle, export
  schemas/
    findings.schema.json # Versioned contract for all tool outputs
  ui/
    src/...              # React 18 + Vite + Tailwind; single-page report viewer
  tests/
    test_envcheck_wrap.py
    test_egress_check.py
    test_findings_schema.py
  .github/workflows/
    ci.yml               # lint, mypy, pytest, ui build
    release.yml          # cut release on tags v*
  .pre-commit-config.yaml
  pyproject.toml         # black, isort, mypy, pylint, pytest config
  package.json           # ui build/lint scripts
  README.md
  docs/
    SOP.md               # <-- this file
    ARCHITECTURE.md
    CONTRIBUTING.md
    PRIVACY_SECURITY.md
    SOURCES.md           # links to official docs/TSGs used in hints
    ROADMAP.md
  CODEOWNERS
```

## Contracts

`schemas/findings.schema.json` (semver) governs every tool result:
- `version`, `target` (cluster|host|site), `checks[]`
- `checks[]` items have: `id`, `title`, `severity`, `status`, `evidence{}`, `hint`, `sources[]`

All new rules must add:
1. A schema example under `tests/fixtures/`
2. A unit test proving schema compliance and stable serialization

## Tool Behaviors

### azlocal.envcheck.wrap
Runs the Azure Local Environment Checker or module via subprocess. Ingests JSON/STDOUT, maps to normalized checks (e.g., connectivity, TLS chain, proxy path, time/NTP), and injects `sources[]` links back to official docs/TSG pages.

### arc.gateway.egress.check
Uses `config/endpoints.yaml` (per-tenant FQDN/ports) to perform TLS & proxy tests; supports corporate CA trust and HTTP(S)_PROXY. Emits evidence (probe/port, tls_chain_ok, proxy_used, error).

### aks.arc.validate
If no kubeconfig/Arc context is detected, returns `status: "skipped"` with hint on how to enable. If present, validates read-only invariants (extensions present/healthy, CNI mode, version pins, flux/policy wiring).

### arcops.diagnostics.bundle
Writes `findings.json` + raw logs into `./artifacts/<run-id>/bundle.zip` with `sha256sum.txt`; optional local signing.

## Security & Sovereignty

- No secrets in code or logs; redact kube and proxy creds.
- Offline by default; any outbound step is explicit, visible, and documented.
- Evidence packs are local artifacts; export/upload is always operator‑initiated.

## Development Workflow

- **Branching:** `main` (protected), feature branches `feat/*`, fixes `fix/*`
- **Commits:** Conventional Commits; signed commits preferred
- **CI gates:** lint, type checks, tests must pass before merge
- **Versioning:** Tag releases `vMAJOR.MINOR.PATCH`. `release.yml` creates a GitHub Release and attaches the packaged artifacts.

## Testing Strategy (no AKS Arc cluster required)

- Unit tests mock subprocess for Environment Checker and kube clients.
- Golden samples under `tests/fixtures/` (simulated outputs) ensure determinism.
- UI snapshot tests for the report page.

## Runbooks (Operator)

### Local run (all offline by default):

```bash
# CLI
python -m cli envcheck --mode full --out ./artifacts
python -m cli egress   --cfg server/config/endpoints.yaml --out ./artifacts
python -m cli validate --kube ~/.kube/config --out ./artifacts   # safe if present; skipped otherwise
python -m cli bundle   --in ./artifacts --sign false
```

### UI report (optional):

```bash
cd ui && npm ci && npm run build && npm run preview
```

## Governance

Any new check must:
1. Link to official Microsoft doc/TSG in `SOURCES.md`
2. Include a schema example
3. Ship a unit test
