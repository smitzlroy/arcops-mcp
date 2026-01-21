# Simple Foundry Local Auto-Start Setup
# Adds a shortcut to your Startup folder (no admin required)

$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder "Foundry Local.lnk"

# Create startup script
$scriptContent = @"
# Foundry Local Auto-Start
Start-Sleep -Seconds 10  # Wait for network
foundry service start
Start-Sleep -Seconds 3
foundry model load qwen2.5-0.5b
"@

$scriptPath = "$env:USERPROFILE\foundry-autostart.ps1"
$scriptContent | Out-File -FilePath $scriptPath -Encoding UTF8

# Create shortcut
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
$shortcut.WindowStyle = 7  # Minimized
$shortcut.Description = "Start Foundry Local AI Service"
$shortcut.Save()

Write-Host ""
Write-Host "[OK] Foundry Local will now auto-start on login!" -ForegroundColor Green
Write-Host ""
Write-Host "Created:"
Write-Host "  Script:   $scriptPath"
Write-Host "  Shortcut: $shortcutPath"
Write-Host ""
Write-Host "The model will be ready ~15 seconds after login."
Write-Host ""
Write-Host "To remove auto-start, delete: $shortcutPath"
