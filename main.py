"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
Modular version with enhanced organization
"""
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import logging
import traceback
import uuid
from datetime import datetime
from typing import Optional

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MyAvatar")

# SAFE IMPORTS - wrap in try/catch to prevent startup crashes
try:
    from app.services.notifications import send_alert, notify_service_status
except ImportError as e:
    logger.warning(f"Notifications service not available: {e}")
    def notify_service_status(*args, **kwargs): pass

try:
    # Import compatibility mode checking
    from app.compatibility import ENABLE_SAFE_MODE, ENABLE_BACKGROUND_REPLACEMENT, log_compatibility_status
except ImportError as e:
    logger.warning(f"Compatibility module not available: {e}")
    ENABLE_SAFE_MODE = True
    ENABLE_BACKGROUND_REPLACEMENT = False
    def log_compatibility_status(): return {"safe_mode": True}

try:
    # Import modular components
    from app.logger.log_handler import log_handler, log_info, log_error, log_warning
except ImportError as e:
    logger.warning(f"Log handler not available: {e}")
    def log_info(msg, context): logger.info(f"[{context}] {msg}")
    def log_error(msg, context, exc=None): logger.error(f"[{context}] {msg}")
    def log_warning(msg, context): logger.warning(f"[{context}] {msg}")

try:
    from app.db.database import init_database, update_database_schema, get_db_connection
    from app.db.admin import create_admin_user
except ImportError as e:
    logger.error(f"Database modules not available: {e}")
    def init_database(): pass
    def update_database_schema(): pass
    def create_admin_user(): pass

# FASTAPI APP INITIALIZATION
app = FastAPI(title="MyAvatar", description="AI Avatar Video Generation Platform - Premium Edition")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_error(f"Uncaught exception: {str(exc)}", "Server", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )

# Mount static files safely
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# SAFE ROUTE IMPORTS - each wrapped individually with DETAILED ERROR LOGGING
routers_loaded = []
router_errors = []

# Import and register routes safely
route_imports = [
    ("app.routes.api_routes", "router"),
    ("app.routes.web_routes", "router"), 
    ("app.routes.finance_routes", "router"),
    ("app.routes.health_routes", "router"),
    ("app.routes.admin_routes", "router"),
    ("app.routes.debug_routes", "router"),
    ("app.routes.voice_routes", "router"),
]

for module_name, router_name in route_imports:
    try:
        logger.info(f"Attempting to import {module_name}...")
        module = __import__(module_name, fromlist=[router_name])
        logger.info(f"Successfully imported {module_name}, getting router...")
        router = getattr(module, router_name)
        logger.info(f"Got router from {module_name}, including in app...")
        app.include_router(router)
        routers_loaded.append(module_name)
        logger.info(f"✅ Successfully loaded router: {module_name}")
    except Exception as e:
        error_details = {
            "module": module_name,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        router_errors.append(error_details)
        logger.error(f"❌ Could not load router {module_name}: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")

# Background routes - conditional and safe
if ENABLE_BACKGROUND_REPLACEMENT:
    try:
        from app.database.background_schema import initialize_backgrounds_schema, add_default_backgrounds
        from app.routes.background_routes import router as background_router
        app.include_router(background_router, prefix="/background", tags=["background"])
        routers_loaded.append("background_routes")
        logger.info("Background replacement routes loaded")
    except Exception as e:
        logger.warning(f"Could not load background routes: {e}")

# Additional background routes (the problematic one from bottom of file)
try:
    from app.routes import background as background_routes
    app.include_router(background_routes.router)
    routers_loaded.append("background (secondary)")
    logger.info("Secondary background routes loaded")
except Exception as e:
    logger.warning(f"Could not load secondary background routes: {e}")

# Create necessary directories
directories = [
    "static/uploads/audio", 
    "static/uploads/images", 
    "output", 
    "processed", 
    "uploads", 
    "temp_audio", 
    "static/backgrounds", 
    "temp/background_processing", 
    "temp/video_processing"
]

for directory in directories:
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create directory {directory}: {e}")

# BULLETPROOF Health check endpoint
@app.get("/health")
async def health_check():
    """Bulletproof health check that never fails"""
    try:
        log_info("Health check endpoint accessed", "Health") 
        return {"status": "ok", "timestamp": datetime.now().isoformat()}
    except Exception:
        # Even if logging fails, return basic response
        return {"status": "ok"}

@app.get("/simple-health") 
async def simple_health_check():
    """Ultra-simple health check for deployment platforms"""
    return {"status": "ok"}

# DEBUG ROUTE - TO DIAGNOSE ROUTE LOADING ISSUES
@app.get("/debug-routes")
async def debug_routes():
    """Debug which routes are loaded and why others failed"""
    routes = []
    for route in app.routes:
        routes.append({
            "path": getattr(route, 'path', 'unknown'),
            "methods": getattr(route, 'methods', []),
            "name": getattr(route, 'name', 'unknown')
        })
    
    return {
        "total_routes": len(app.routes),
        "routes_loaded_successfully": routers_loaded,
        "router_import_errors": router_errors,
        "all_routes": routes
    }

# TEST ROUTE - Simple route to confirm basic functionality
@app.get("/test")
async def test_route():
    """Test route to confirm FastAPI is working"""
    return {
        "message": "FastAPI is working!", 
        "routers_loaded": routers_loaded,
        "timestamp": datetime.now().isoformat()
    }

# Startup event with safe initialization
@app.on_event("startup")
async def startup_event():
    """Safe startup with comprehensive error handling"""
    
    # Initialize the notification system safely
    try:
        notify_service_status("MyAvatar", "up", "Application started successfully")
        logger.info("Notification system initialized successfully")
    except Exception as e:
        logger.warning(f"Notification system unavailable: {str(e)}")

    # Log compatibility status safely
    try:
        status = log_compatibility_status()
        log_info(f"Starting MyAvatar application (Safe Mode: {status.get('safe_mode', 'unknown')})", "Server")
    except Exception as e:
        logger.warning(f"Could not determine compatibility status: {e}")
        log_info("Starting MyAvatar application", "Server")
    
    # Database initialization with error handling
    try:
        init_database()
        update_database_schema()
        create_admin_user()
        logger.info("Database initialization completed")
    except Exception as e:
        log_error(f"Database initialization failed: {str(e)}", "Server", e)
        logger.warning("Application may have limited functionality due to database issues")
    
    # GDPR schema initialization
    try:
        from app.database.gdpr_schema import initialize_gdpr_schema
        initialize_gdpr_schema()
        logger.info("GDPR schema initialized")
    except Exception as gdpr_error:
        logger.warning(f"GDPR schema initialization failed: {str(gdpr_error)}")
    
    # Background replacement initialization
    if ENABLE_BACKGROUND_REPLACEMENT:
        try:
            logger.info("Background replacement functionality enabled via BackgroundFX microservice")
        except Exception as e:
            logger.warning(f"Background replacement initialization warning: {e}")
    
    # Report successful startup
    edition_name = "Premium Edition" if not ENABLE_SAFE_MODE else "Premium Edition (Safe Mode)"
    log_info(f"MyAvatar {edition_name} is running", "Server")
    logger.info(f"✅ Successfully loaded {len(routers_loaded)} route modules: {', '.join(routers_loaded)}")
    
    if router_errors:
        logger.error(f"❌ Failed to load {len(router_errors)} route modules")
        for error in router_errors:
            logger.error(f"   - {error['module']}: {error['error']}")

# Entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)