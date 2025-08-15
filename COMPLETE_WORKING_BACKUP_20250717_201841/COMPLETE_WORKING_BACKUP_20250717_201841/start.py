#!/usr/bin/env python3
"""
Startup script to debug Railway deployment
"""
import sys
import os
import traceback

print("🚀 STARTUP SCRIPT RUNNING")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Environment PORT: {os.getenv('PORT', 'NOT SET')}")

# List key files
print("\n📁 Key files check:")
key_files = ['main.py', 'requirements.txt', 'Procfile']
for file in key_files:
    exists = os.path.exists(file)
    print(f"  {file}: {'✅ EXISTS' if exists else '❌ MISSING'}")

# Try to import main modules
print("\n📦 Import test:")
try:
    import fastapi
    print(f"  FastAPI: ✅ {fastapi.__version__}")
except Exception as e:
    print(f"  FastAPI: ❌ {e}")

try:
    import uvicorn
    print(f"  Uvicorn: ✅ {uvicorn.__version__}")
except Exception as e:
    print(f"  Uvicorn: ❌ {e}")

# Try to import main app
print("\n🎯 Main app import test:")
try:
    from main import app
    print("  main.py: ✅ Imported successfully")
    print(f"  App type: {type(app)}")
except Exception as e:
    print(f"  main.py: ❌ IMPORT ERROR: {e}")
    print(f"  Traceback: {traceback.format_exc()}")

print("\n🚀 Starting uvicorn...")
try:
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    print(f"Starting on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
except Exception as e:
    print(f"❌ UVICORN START ERROR: {e}")
    print(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)
