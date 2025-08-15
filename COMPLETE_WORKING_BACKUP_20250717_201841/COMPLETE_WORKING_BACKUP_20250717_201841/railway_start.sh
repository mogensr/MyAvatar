#!/bin/bash
# Railway startup script with extensive debugging

# Print environment information
echo "=== ENVIRONMENT INFO ==="
echo "Python version: $(python -V)"
echo "Current directory: $(pwd)"
echo "Directory contents: $(ls -la)"
echo "Available memory: $(free -h)"
echo "CPU info: $(cat /proc/cpuinfo | grep 'model name' | head -1)"
echo "=== END ENVIRONMENT INFO ==="

# Set environment variables
export PYTHONUNBUFFERED=1
export LOG_LEVEL=DEBUG
export ENABLE_SAFE_MODE=true

# Attempt to start the application with extensive logging
echo "Starting application with safe mode enabled..."
python -m uvicorn main:app --host 0.0.0.0 --port $PORT --log-level debug
