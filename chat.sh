#!/bin/bash
echo "Starting ArcOps Chat..."
echo

# Check if Foundry is running
if ! foundry service status &>/dev/null; then
    echo "Starting Foundry Local service..."
    foundry service start
    sleep 3
fi

# Check if model is loaded  
if ! foundry model list --loaded 2>/dev/null | grep -qi "phi"; then
    echo "Loading phi-4-mini model (first run may take a few minutes)..."
    foundry model run phi-4-mini --port 5272 &
    sleep 10
fi

# Start the chat
python -m agent.simple_chat
