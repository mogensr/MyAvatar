#!/bin/bash
set -e

# Print environment information for debugging
echo "Current environment:"
echo "PORT=${PORT}"
echo "PYTHONPATH=${PYTHONPATH}"
echo "PWD=$(pwd)"
echo "Files in current directory:"
ls -la

# HARDCODED approach for Railway - use port 8080 as a reliable fallback
# This ignores any PORT environment variable to avoid parsing issues
PORT=8080
echo "HARDCODED PORT: Using fixed port ${PORT} for Railway deployment"

# Start the application
echo "Starting uvicorn on port ${PORT}"
exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT}
