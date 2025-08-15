#!/bin/bash
set -e

# Print environment information for debugging
echo "🚀 Starting MyAvatar on Railway..."
echo "Environment Variables:"
echo "PORT: ${PORT:-8080}"
echo "RAILWAY_ENVIRONMENT: ${RAILWAY_ENVIRONMENT:-unknown}"
echo "PWD: $(pwd)"
echo "Python version: $(python --version)"
echo "Pip packages:"
pip list | head -10

# Set defaults
export PORT=${PORT:-8080}
export HOST=${HOST:-0.0.0.0}

# Test basic Python functionality
echo "Testing Python imports..."
python -c "
import sys
print(f'Python executable: {sys.executable}')
print(f'Python path: {sys.path}')

try:
    import fastapi
    print('✅ FastAPI import successful')
except ImportError as e:
    print(f'❌ FastAPI import failed: {e}')
    exit(1)

try:
    import uvicorn
    print('✅ Uvicorn import successful')
except ImportError as e:
    print(f'❌ Uvicorn import failed: {e}')
    exit(1)
"

# Check if main.py exists and is valid
if [ -f "main.py" ]; then
    echo "✅ main.py found"
    echo "Testing main.py syntax..."
    python -m py_compile main.py
    if [ $? -eq 0 ]; then
        echo "✅ main.py syntax valid"
    else
        echo "❌ main.py syntax error"
        exit 1
    fi
else
    echo "❌ main.py not found"
    exit 1
fi

# Start the application
echo "🌟 Starting FastAPI application..."
echo "Binding to: $HOST:$PORT"

# Use exec to replace the shell process (better for signal handling)
exec python -m uvicorn main:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level info \
    --access-log \
    --no-use-colors
