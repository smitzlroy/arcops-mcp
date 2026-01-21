# Install Foundry Local as a Windows Startup Task
# This ensures the service and model are ready when you boot your computer

$taskName = "FoundryLocalService"
$foundryPath = (Get-Command foundry -ErrorAction SilentlyContinue).Source

if (-not $foundryPath) {
    Write-Host "[ERROR] Foundry CLI not found. Install with: winget install Microsoft.FoundryLocal" -ForegroundColor Red
    exit 1
}

# Create a startup script
$startupScript = @"
# Start Foundry Local service and load default model
`$logFile = "`$env:USERPROFILE\foundry-startup.log"
Add-Content `$logFile "$(Get-Date) - Starting Foundry Local..."

# Start the service
foundry service start 2>&1 | Add-Content `$logFile

# Wait for service to be ready
Start-Sleep -Seconds 5

# Load the default model
foundry model load qwen2.5-0.5b 2>&1 | Add-Content `$logFile

Add-Content `$logFile "$(Get-Date) - Foundry Local ready"
"@

$scriptPath = "$env:USERPROFILE\foundry-startup.ps1"
$startupScript | Out-File -FilePath $scriptPath -Encoding UTF8

Write-Host "Created startup script: $scriptPath" -ForegroundColor Green

# Create scheduled task to run at login
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -AtLogon
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Remove existing task if it exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create new task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Start Foundry Local AI service at login"

if ($?) {
    Write-Host ""
    Write-Host "[OK] Foundry Local will now start automatically at login!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The service will:"
    Write-Host "  1. Start the Foundry Local service"
    Write-Host "  2. Load the qwen2.5-0.5b model"
    Write-Host "  3. Be ready for AI chat"
    Write-Host ""
    Write-Host "To test now, run: foundry service ps"
} else {
    Write-Host "[ERROR] Failed to create scheduled task" -ForegroundColor Red
}
