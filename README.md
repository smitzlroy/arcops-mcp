# ArcOps

Check if your system is ready for Azure Local and AKS Arc - just ask questions in plain English.

## What does this do?

Instead of running complex PowerShell scripts and reading through logs, you can just ask:

- "Is my system ready for Azure Local?"
- "Can I reach Azure from here?"
- "Is my cluster configured correctly?"

The tool runs the actual diagnostic checks and explains the results.

## Setup (5 minutes)

### Step 1: Install Foundry Local

This runs the AI locally on your machine (no cloud needed).

Open PowerShell and run:
```powershell
winget install Microsoft.FoundryLocal
```

### Step 2: Download this project

```powershell
git clone https://github.com/smitzlroy/arcops-mcp
cd arcops-mcp
```

### Step 3: Install dependencies

```powershell
pip install -e .
pip install foundry-local-sdk
```

## Usage

### Option 1: Chat interface (easiest)

```powershell
.\start.ps1
```

This starts everything and opens a chat where you can ask questions.

### Option 2: Run checks directly

If you don't want to use the chat, you can run checks directly:

```powershell
# Check environment
python -m cli envcheck --dry-run

# Check connectivity  
python -m cli egress --dry-run

# Validate cluster
python -m cli validate --dry-run
```

## Troubleshooting

**"Foundry Local not running"**

Run this first:
```powershell
foundry model run phi-4-mini
```

Wait for it to download (first time only, ~2GB), then try again.

**"Access denied" when starting service**

Run PowerShell as Administrator, then:
```powershell
foundry service start
```

**"Cannot connect"**

Check if the service is running:
```powershell
foundry service status
```

## What's inside

| Tool | What it checks |
|------|----------------|
| `envcheck` | Hardware, OS, prerequisites for Azure Local |
| `egress` | Network connectivity to Azure endpoints |
| `validate` | AKS Arc cluster configuration |
| `bundle` | Package all results into a ZIP for support |

## Advanced: HTTP API

If you want to integrate with other tools, start the server:

```powershell
python -m cli server --port 8080
```

Then call:
```
POST http://localhost:8080/mcp/tools/azlocal.envcheck.wrap
```

## License

MIT
