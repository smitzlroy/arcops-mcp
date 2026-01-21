<#
.SYNOPSIS
    ArcOps Setup - One-time setup and daily launcher for ArcOps diagnostics

.DESCRIPTION
    This script handles everything:
    - First run: Downloads required model, sets up environment
    - Every run: Starts services and launches chat interface

.EXAMPLE
    .\start.ps1
#>

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ArcOps - Azure Local Diagnostics" -ForegroundColor Cyan  
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Foundry Local is installed
$foundryPath = Get-Command foundry -ErrorAction SilentlyContinue
if (-not $foundryPath) {
    Write-Host "Foundry Local not found. Installing..." -ForegroundColor Yellow
    Write-Host ""
    winget install Microsoft.FoundryLocal --accept-source-agreements --accept-package-agreements
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    $foundryPath = Get-Command foundry -ErrorAction SilentlyContinue
    if (-not $foundryPath) {
        Write-Host "Please restart your terminal and run this script again." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Foundry Local: " -NoNewline
foundry --version

# Check/start service
Write-Host ""
Write-Host "Checking Foundry service..." -ForegroundColor Gray
$status = foundry service status 2>&1

if ($status -match "not running" -or $status -match "Failed") {
    Write-Host "Starting Foundry service..." -ForegroundColor Yellow
    
    # Try to start service
    $result = foundry service start 2>&1
    
    if ($result -match "Access.*denied") {
        Write-Host ""
        Write-Host "Need admin rights to start Foundry service (first time only)." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Please run this in an Administrator PowerShell:" -ForegroundColor White
        Write-Host "  foundry service start" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Then run .\start.ps1 again." -ForegroundColor White
        Write-Host ""
        
        # Offer to elevate
        $response = Read-Host "Try to run as admin now? (y/n)"
        if ($response -eq 'y') {
            Start-Process powershell -Verb RunAs -ArgumentList "-Command `"foundry service start; Read-Host 'Press Enter to close'`"" -Wait
        }
        exit 1
    }
    
    Start-Sleep -Seconds 2
}

# Verify service is running
$status = foundry service status 2>&1
if ($status -match "not running") {
    Write-Host "Could not start Foundry service." -ForegroundColor Red
    exit 1
}

Write-Host "Foundry service is running." -ForegroundColor Green

# Check if model is available
Write-Host ""
Write-Host "Checking for AI model..." -ForegroundColor Gray

$loadedModels = foundry model list --loaded 2>&1
$hasModel = $loadedModels -match "phi"

if (-not $hasModel) {
    Write-Host ""
    Write-Host "Starting AI model (first time downloads ~2GB)..." -ForegroundColor Yellow
    Write-Host "This may take a few minutes." -ForegroundColor Gray
    Write-Host ""
    
    # Run model in background
    Start-Process -FilePath "foundry" -ArgumentList "model", "run", "phi-4-mini" -WindowStyle Hidden
    
    # Wait for model to be ready
    Write-Host "Waiting for model to initialize..." -ForegroundColor Gray
    $attempts = 0
    while ($attempts -lt 60) {
        Start-Sleep -Seconds 5
        $loaded = foundry model list --loaded 2>&1
        if ($loaded -match "phi") {
            break
        }
        Write-Host "." -NoNewline
        $attempts++
    }
    Write-Host ""
}

Write-Host "AI model ready!" -ForegroundColor Green

# Check Python environment
Write-Host ""
Write-Host "Checking Python..." -ForegroundColor Gray

$pythonPath = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonPath) {
    Write-Host "Python not found. Please install Python 3.11+ from python.org" -ForegroundColor Red
    exit 1
}

# Check if arcops-mcp is installed
$installed = pip show arcops-mcp 2>&1
if ($installed -match "not found") {
    Write-Host "Installing ArcOps..." -ForegroundColor Yellow
    pip install -e . --quiet
    pip install foundry-local-sdk --quiet
}

Write-Host "Ready!" -ForegroundColor Green

# Start the chat
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting ArcOps Chat" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Ask questions like:" -ForegroundColor Gray
Write-Host "  - Is my system ready for Azure Local?" -ForegroundColor White
Write-Host "  - Check network connectivity" -ForegroundColor White  
Write-Host "  - Validate my cluster" -ForegroundColor White
Write-Host ""
Write-Host "Type 'quit' to exit" -ForegroundColor Gray
Write-Host ""

# Run the chat agent
python -m agent.simple_chat
