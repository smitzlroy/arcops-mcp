@echo off
echo Starting ArcOps Chat...
echo.

REM Check if Foundry is running
foundry service status >nul 2>&1
if errorlevel 1 (
    echo Starting Foundry Local service...
    foundry service start
    timeout /t 3 >nul
)

REM Check if model is loaded
foundry model list --loaded 2>nul | findstr /i "phi" >nul
if errorlevel 1 (
    echo Loading phi-4-mini model ^(first run may take a few minutes^)...
    start /b foundry model run phi-4-mini --port 5272
    timeout /t 10 >nul
)

REM Start the chat
python -m agent.simple_chat
