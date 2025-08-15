#!/bin/bash
# Startup script for MyAvatar application

# Print environment information
echo "Starting MyAvatar application..."
python --version

# Start the application
exec uvicorn main:app --host 0.0.0.0 --port $PORT
