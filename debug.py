"""
Debug script to identify import issues
"""
import sys
import os

print("Python version:", sys.version)
print("Current directory:", os.getcwd())

try:
    print("Testing FastAPI import...")
    from fastapi import FastAPI
    print("FastAPI import successful")
except Exception as e:
    print("FastAPI import failed:", str(e))

try:
    print("\nTesting logger import...")
    from app.logger.log_handler import log_info
    print("Logger import successful")
except Exception as e:
    print("Logger import failed:", str(e))

try:
    print("\nTesting database import...")
    from app.db.database import init_database
    print("Database import successful")
except Exception as e:
    print("Database import failed:", str(e))

try:
    print("\nTesting routes imports...")
    print("Testing API routes...")
    from app.routes.api_routes import router as api_router
    print("API routes import successful")
    
    print("Testing web routes...")
    from app.routes.web_routes import router as web_router
    print("Web routes import successful")
    
    print("Testing finance routes...")
    from app.routes.finance_routes import router as finance_router
    print("Finance routes import successful")
except Exception as e:
    print("Routes import failed:", str(e))
    import traceback
    traceback.print_exc()
