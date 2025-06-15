"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
Modular version with enhanced organization
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import logging
import traceback

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MyAvatar")

# Import modular components
from app.logger.log_handler import log_handler, log_info, log_error, log_warning
from app.db.database import init_database, update_database_schema
from app.db.admin import create_admin_user
from app.routes.api_routes import router as api_router
from app.routes.web_routes import router as web_router
from app.routes.finance_routes import router as finance_router

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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register routes
app.include_router(api_router)
app.include_router(web_router)
app.include_router(finance_router)

# Create necessary directories
for directory in ["static/uploads/audio", "static/uploads/images", "output", "processed", "uploads", "temp_audio"]:
    os.makedirs(directory, exist_ok=True)

# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Initialize database and update schema on startup
    """
    log_info("Starting MyAvatar application", "Server")
    
    try:
        init_database()
        update_database_schema()
        create_admin_user()  # Create admin user if not exists
        log_info("[\n\n\n\n\n\n                                            [Server] MyAvatar Premium Edition is running  ")
    except Exception as e:
        log_error("Error during startup", "Server", e)
        log_warning("Application may not function correctly without database", "Server")
    
    log_info("MyAvatar Premium Edition is running", "Server")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
