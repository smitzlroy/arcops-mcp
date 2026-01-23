<#
.SYNOPSIS
    ArcOps MCP - One-click setup and run script

.DESCRIPTION
    Sets up the complete ArcOps MCP environment and starts all services:
    - Creates Python virtual environment
    - Installs Python dependencies
    - Installs PowerShell modules
    - Starts Foundry Local with selected model
    - Starts MCP API server
    - Starts UI development server

.PARAMETER SkipInstall
    Skip installation steps (use if already installed)

.PARAMETER Model
    Foundry Local model to use (default: qwen2.5-0.5b)

.EXAMPLE
    .\start.ps1
    .\start.ps1 -SkipInstall
    .\start.ps1 -Model "phi-4-mini"
#>

param(
    [switch]$SkipInstall,
    [string]$Model = "qwen2.5-0.5b"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    ArcOps MCP Setup                          ║" -ForegroundColor Cyan
Write-Host "║     AI-powered diagnostics for Azure Local & AKS Arc         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Helper function
function Write-Step {
    param([string]$Message, [string]$Status = "...")
    $colors = @{ "..." = "Yellow"; "OK" = "Green"; "SKIP" = "DarkGray"; "FAIL" = "Red" }
    Write-Host "  [$Status] " -ForegroundColor $colors[$Status] -NoNewline
    Write-Host $Message
}

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor White
Write-Host ""

# Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Step "Python 3.11+ required but not found" "FAIL"
    Write-Host "    Download from: https://www.python.org/downloads/" -ForegroundColor Gray
    exit 1
}
$pyVersion = python --version 2>&1
Write-Step "Python: $pyVersion" "OK"

# Node.js
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Step "Node.js 18+ required but not found" "FAIL"
    Write-Host "    Download from: https://nodejs.org/" -ForegroundColor Gray
    exit 1
}
$nodeVersion = node --version 2>&1
Write-Step "Node.js: $nodeVersion" "OK"

# Foundry Local
$foundry = Get-Command foundry -ErrorAction SilentlyContinue
if (-not $foundry) {
    Write-Step "Foundry Local not found" "FAIL"
    Write-Host "    Install from: https://github.com/microsoft/foundry-local" -ForegroundColor Gray
    Write-Host "    Run: winget install Microsoft.FoundryLocal" -ForegroundColor Gray
    exit 1
}
Write-Step "Foundry Local: installed" "OK"

Write-Host ""

# Installation
if (-not $SkipInstall) {
    Write-Host "Installing dependencies..." -ForegroundColor White
    Write-Host ""

    # Python virtual environment
    $venvPath = Join-Path $ProjectRoot ".venv"
    if (-not (Test-Path $venvPath)) {
        Write-Step "Creating Python virtual environment"
        python -m venv $venvPath
        Write-Step "Virtual environment created" "OK"
    } else {
        Write-Step "Virtual environment exists" "SKIP"
    }

    # Activate venv
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    . $activateScript

    # Install Python packages
    Write-Step "Installing Python packages"
    pip install -e ".[dev]" --quiet 2>&1 | Out-Null
    Write-Step "Python packages installed" "OK"

    # Install PowerShell modules
    Write-Step "Installing PowerShell modules"
    
    $modules = @(
        "AzStackHci.EnvironmentChecker",
        "AzLocalTSGTool",
        "Support.AksArc"
    )
    
    foreach ($module in $modules) {
        $installed = Get-Module -ListAvailable -Name $module -ErrorAction SilentlyContinue
        if (-not $installed) {
            try {
                Install-Module -Name $module -Force -Scope CurrentUser -AllowClobber -ErrorAction SilentlyContinue 2>&1 | Out-Null
                Write-Step "  $module" "OK"
            } catch {
                Write-Step "  $module (optional, skipped)" "SKIP"
            }
        } else {
            Write-Step "  $module" "SKIP"
        }
    }

    # Install UI dependencies
    $uiPath = Join-Path $ProjectRoot "ui"
    $nodeModules = Join-Path $uiPath "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Step "Installing UI dependencies"
        Push-Location $uiPath
        npm install --silent 2>&1 | Out-Null
        Pop-Location
        Write-Step "UI dependencies installed" "OK"
    } else {
        Write-Step "UI dependencies exist" "SKIP"
    }

    Write-Host ""
} else {
    Write-Host "Skipping installation (use without -SkipInstall to install)" -ForegroundColor DarkGray
    Write-Host ""
    
    # Still activate venv
    $venvPath = Join-Path $ProjectRoot ".venv"
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        . $activateScript
    }
}

# Start services
Write-Host "Starting services..." -ForegroundColor White
Write-Host ""

# Check/start Foundry Local
Write-Step "Checking Foundry Local service"
$foundryStatus = foundry service status 2>&1
if ($foundryStatus -match "not running") {
    Write-Step "Starting Foundry Local service"
    foundry service start 2>&1 | Out-Null
    Start-Sleep -Seconds 3
}
Write-Step "Foundry Local service running" "OK"

# Load model
Write-Step "Loading model: $Model"
$loadedModels = foundry model list --running 2>&1
if ($loadedModels -notmatch $Model) {
    # Check if model is cached
    $cachedModels = foundry cache list 2>&1
    if ($cachedModels -notmatch $Model) {
        Write-Host ""
        Write-Host "    Model '$Model' not downloaded. Downloading now..." -ForegroundColor Yellow
        Write-Host "    This may take a few minutes depending on your connection." -ForegroundColor Gray
        Write-Host ""
    }
    
    # Start model in background
    Start-Job -Name "FoundryModel" -ScriptBlock {
        param($m)
        foundry model run $m 2>&1
    } -ArgumentList $Model | Out-Null
    
    # Wait for model to load
    Write-Host "    Waiting for model to load" -NoNewline
    $timeout = 120  # 2 minutes max
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        Start-Sleep -Seconds 2
        $elapsed += 2
        Write-Host "." -NoNewline
        
        $running = foundry model list --running 2>&1
        if ($running -match $Model) {
            break
        }
    }
    Write-Host ""
    
    if ($elapsed -ge $timeout) {
        Write-Step "Model loading timed out (may still be downloading)" "FAIL"
        Write-Host "    Try running manually: foundry model run $Model" -ForegroundColor Gray
    } else {
        Write-Step "Model loaded: $Model" "OK"
    }
} else {
    Write-Step "Model already running: $Model" "OK"
}

# Start API server
Write-Step "Starting API server on port 8082"
$apiJob = Start-Job -Name "ArcOpsAPI" -ScriptBlock {
    param($root)
    Set-Location $root
    & "$root\.venv\Scripts\python.exe" -c "from server.main_clean import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8082, log_level='warning')"
} -ArgumentList $ProjectRoot

Start-Sleep -Seconds 3

# Check if API started
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8082/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Step "API server running at http://127.0.0.1:8082" "OK"
} catch {
    Write-Step "API server may still be starting..." "..."
}

# Start UI
Write-Step "Starting UI server"
$uiPath = Join-Path $ProjectRoot "ui"
$uiJob = Start-Job -Name "ArcOpsUI" -ScriptBlock {
    param($path)
    Set-Location $path
    npm run dev 2>&1
} -ArgumentList $uiPath

Start-Sleep -Seconds 4

# Get UI port
$uiOutput = Receive-Job -Name "ArcOpsUI" -Keep 2>&1 | Out-String
if ($uiOutput -match "localhost:(\d+)") {
    $uiPort = $matches[1]
    Write-Step "UI server running at http://localhost:$uiPort" "OK"
} else {
    $uiPort = "5173"
    Write-Step "UI server starting at http://localhost:$uiPort" "OK"
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    ArcOps MCP Ready!                         ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Open in browser: " -NoNewline
Write-Host "http://localhost:$uiPort" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Services running:" -ForegroundColor White
Write-Host "    • UI:     http://localhost:$uiPort" -ForegroundColor Gray
Write-Host "    • API:    http://127.0.0.1:8082" -ForegroundColor Gray
Write-Host "    • Model:  $Model (via Foundry Local)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host ""

# Open browser
Start-Process "http://localhost:$uiPort"

# Keep script running and handle Ctrl+C
try {
    while ($true) {
        Start-Sleep -Seconds 5
        
        # Check if jobs are still running
        $apiState = (Get-Job -Name "ArcOpsAPI" -ErrorAction SilentlyContinue).State
        $uiState = (Get-Job -Name "ArcOpsUI" -ErrorAction SilentlyContinue).State
        
        if ($apiState -eq "Failed") {
            Write-Host "  API server stopped unexpectedly" -ForegroundColor Red
            Receive-Job -Name "ArcOpsAPI" 2>&1 | Write-Host -ForegroundColor Red
        }
        if ($uiState -eq "Failed") {
            Write-Host "  UI server stopped unexpectedly" -ForegroundColor Red
            Receive-Job -Name "ArcOpsUI" 2>&1 | Write-Host -ForegroundColor Red
        }
    }
} finally {
    Write-Host ""
    Write-Host "Stopping services..." -ForegroundColor Yellow
    
    # Stop jobs
    Get-Job -Name "ArcOpsAPI" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job -Force
    Get-Job -Name "ArcOpsUI" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job -Force
    Get-Job -Name "FoundryModel" -ErrorAction SilentlyContinue | Stop-Job -PassThru | Remove-Job -Force
    
    Write-Host "Services stopped." -ForegroundColor Green
}
