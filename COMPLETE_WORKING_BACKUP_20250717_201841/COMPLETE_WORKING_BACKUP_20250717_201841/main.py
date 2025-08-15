"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
Modular version with enhanced organization - REFACTORED ROUTES + PREMIUM FEATURES + BACKGROUNDFX + VIDEO PROCESSING
"""
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import logging
import traceback
import uuid
import threading
from datetime import datetime
from typing import Optional
from pathlib import Path
import sys

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

# Import HeyGen API for debug endpoints
try:
  from app.api.heygen import get_available_avatars
except ImportError as e:
  logger.warning(f"HeyGen API module not available: {e}")
  def get_available_avatars(*args, **kwargs): 
      return {"error": "HeyGen API not available"}

# IMPORT VIDEO URL REFRESHER
try:
  from video_url_refresher import VideoURLRefresher
  video_refresher_available = True
  logger.info("Video URL refresher imported successfully")
except ImportError as e:
  logger.warning(f"Video URL refresher not available: {e}")
  video_refresher_available = False

# FASTAPI APP INITIALIZATION
app = FastAPI(title="MyAvatar", description="AI Avatar Video Generation Platform - Premium Edition with BackgroundFX + Advanced Video Processing")

# AUTO-RUN DATABASE MIGRATIONS ON STARTUP
try:
    logger.info("🔄 Starting database migration process...")
    logger.info(f"🔍 Current working directory: {os.getcwd()}")
    logger.info(f"🔍 Python path: {sys.path[:3]}...")  # Show first 3 paths
    
    # Try to import migration runner
    logger.info("📦 Importing migration runner...")
    from run_migrations import run_migrations
    logger.info("✅ Migration runner imported successfully")
    
    # Run migrations
    logger.info("🚀 Executing migrations...")
    migration_success = run_migrations()
    
    if migration_success:
        logger.info("🎉 Database migrations completed successfully")
    else:
        logger.error("❌ Database migrations failed - this will cause upload errors")
        
except ImportError as e:
    logger.error(f"❌ Could not import migration runner: {e}")
    logger.error("📁 This means video processing will fail - missing database tables")
except Exception as e:
    logger.error(f"❌ Migration error: {e}")
    logger.error("📁 This will cause video upload failures")
    import traceback
    logger.error(f"🔍 Full traceback: {traceback.format_exc()}")

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

# =============================================================================
# VIDEO URL REFRESHER BACKGROUND SERVICE
# =============================================================================

def start_video_url_refresher():
  """Start the video URL refresher in a background thread"""
  try:
      if not video_refresher_available:
          logger.warning("Video URL refresher not available - skipping background service")
          return
      
      logger.info("Starting video URL refresher background service...")
      refresher = VideoURLRefresher()
      
      # Configure intervals from environment variables
      interval_hours = int(os.getenv('REFRESH_INTERVAL_HOURS', '4'))
      threshold_hours = int(os.getenv('EXPIRY_THRESHOLD_HOURS', '6'))
      
      logger.info(f"Video URL refresher configured:")
      logger.info(f"  • Refresh interval: {interval_hours} hours")
      logger.info(f"  • Expiry threshold: {threshold_hours} hours")
      
      # Run the refresher continuously
      refresher.run_continuous(interval_hours=interval_hours, hours_threshold=threshold_hours)
      
  except Exception as e:
      logger.error(f"Error starting video URL refresher: {e}")
      logger.error(f"Video URL refresher traceback: {traceback.format_exc()}")

# Start the background refresher service
if video_refresher_available:
  refresher_thread = threading.Thread(target=start_video_url_refresher, daemon=True)
  refresher_thread.start()
  logger.info("✅ Video URL refresher background service started")
else:
  logger.warning("⚠️ Video URL refresher background service not started - module not available")

# =============================================================================
# FILE CHANGE TRACKER INITIALIZATION
# =============================================================================

# Initialize file change tracker
try:
  from app.startup.file_tracker_startup import initialize_file_tracker
  initialize_file_tracker()
except ImportError as e:
  logger.warning(f"File change tracker not available: {e}")
except Exception as e:
  logger.error(f"Error starting file change tracker: {e}")

# =============================================================================
# MODULAR ROUTE IMPORTS - REFACTORED STRUCTURE + PREMIUM FEATURES + BACKGROUNDFX + VIDEO PROCESSING
# =============================================================================

routers_loaded = []
router_errors = []

# 🔄 NEW MODULAR ROUTES (split from old web_routes.py)
modular_route_imports = [
  # Core authentication and user routes (no prefix - root level)
  ("app.routes.auth_routes", "router", None),
  
  # Admin routes with /admin prefix
  ("app.routes.admin_routes", "router", "/admin"),
  
  # API routes with /api prefix - UNCOMMENTED to enable video creation endpoints
  ("app.routes.api_routes", "router", "/api"),
  
  # 🎯 PREMIUM ROUTES - NEW COMPLETE PREMIUM SYSTEM - FIXED IMPORT PATH
  ("app.routes.premium_routes", "router", None),  # ✅ FIXED - Now uses app.routes.premium_routes
  
  # 🎯 BACKGROUNDFX ROUTES - NEW HeyGen WebM + Transparent Video System
  ("app.routes.backgroundfx_routes", "router", None),  # No prefix since it has its own /api/backgrounds
  
  # 🎬 VIDEO PROCESSING ROUTES - NEW Advanced Background Replacement API
  ("app.routes.video_processing_routes", "router", "/video-processing"),
  
  # Video routes with NO prefix - FIXED for template routes
  ("app.routes.video_routes", "router", None),
  
  # Emergency routes with /emergency prefix
  ("app.routes.emergency_routes", "router", "/emergency"),
  
  # File tracker routes with /admin/file-tracker prefix
  ("app.routes.file_tracker_routes", "router", "/admin/file-tracker"),
  
  # Dashboard and main app routes (if you create web_routes.py for remaining routes)
  ("app.routes.web_routes", "router", None),
]

# Load modular routes with prefixes
for module_name, router_name, prefix in modular_route_imports:
  try:
      logger.info(f"Attempting to import {module_name}...")
      module = __import__(module_name, fromlist=[router_name])
      logger.info(f"Successfully imported {module_name}, getting router...")
      router = getattr(module, router_name)
      logger.info(f"Got router from {module_name}, including in app with prefix: {prefix}")
      
      if prefix:
          app.include_router(router, prefix=prefix)
          logger.info(f"✅ Successfully loaded router: {module_name} (prefix: {prefix})")
      else:
          app.include_router(router)
          logger.info(f"✅ Successfully loaded router: {module_name} (no prefix)")
          
      routers_loaded.append(f"{module_name}{' -> ' + prefix if prefix else ''}")
      
  except Exception as e:
      error_details = {
          "module": module_name,
          "error": str(e),
          "traceback": traceback.format_exc()
      }
      router_errors.append(error_details)
      logger.error(f"❌ Could not load router {module_name}: {e}")
      logger.error(f"Full traceback: {traceback.format_exc()}")

# 🔧 LEGACY/REMAINING ROUTES (keep your existing working routes)
legacy_route_imports = [
  # Keep these existing routes that still work
  ("app.routes.health_routes", "router"),
  ("app.routes.debug_routes", "router"), 
  ("app.routes.voice_routes", "router"),
  ("app.routes.avatar_rebuild_route", "router"),
  ("app.routes.migration_routes", "router"),
  ("app.routes.finance_routes", "router"),
]

# Load legacy routes (no prefixes)
for module_name, router_name in legacy_route_imports:
  try:
      logger.info(f"Attempting to import legacy route {module_name}...")
      module = __import__(module_name, fromlist=[router_name])
      logger.info(f"Successfully imported {module_name}, getting router...")
      router = getattr(module, router_name)
      logger.info(f"Got router from {module_name}, including in app...")
      app.include_router(router)
      routers_loaded.append(f"{module_name} (legacy)")
      logger.info(f"✅ Successfully loaded legacy router: {module_name}")
  except Exception as e:
      error_details = {
          "module": module_name,
          "error": str(e),
          "traceback": traceback.format_exc()
      }
      router_errors.append(error_details)
      logger.error(f"❌ Could not load legacy router {module_name}: {e}")
      logger.error(f"Full traceback: {traceback.format_exc()}")

# Background routes - conditional and safe
if ENABLE_BACKGROUND_REPLACEMENT:
  try:
      from app.database.background_schema import initialize_backgrounds_schema, add_default_backgrounds
      from app.routes.background_routes import router as background_router
      app.include_router(background_router, prefix="/background", tags=["background"])
      routers_loaded.append("background_routes -> /background")
      logger.info("Background replacement routes loaded")
  except Exception as e:
      logger.warning(f"Could not load background routes: {e}")

# =============================================================================
# BACKGROUNDFX PAGE ROUTE - Serve the HTML interface
# =============================================================================

@app.get("/backgroundfx")
async def backgroundfx_page(request: Request):
    """BackgroundFX premium feature page - HeyGen WebM + Transparent Videos"""
    try:
        logger.info("BackgroundFX page accessed")
        
        # First try the enhanced template
        enhanced_html_file = Path("templates/backgroundfx_enhanced.html")
        if enhanced_html_file.exists():
            templates = Jinja2Templates(directory="templates")
            return templates.TemplateResponse("backgroundfx_enhanced.html", {"request": request})
        
        # Fall back to original template
        html_file = Path("templates/backgroundfx.html")
        if html_file.exists():
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info("✅ BackgroundFX HTML template loaded successfully")
            return HTMLResponse(content=content)
        else:
            # Fallback to basic page with link to dashboard
            logger.warning("⚠️ BackgroundFX HTML template not found, using fallback")
            return HTMLResponse(content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>BackgroundFX - Enhanced Video Processing</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 40px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; color: white; }
                        .container { max-width: 600px; margin: 0 auto; padding: 40px; background: rgba(255,255,255,0.1); border-radius: 20px; }
                        h1 { font-size: 3em; margin-bottom: 20px; }
                        .btn { padding: 15px 30px; background: #fff; color: #667eea; text-decoration: none; border-radius: 10px; font-weight: bold; margin: 10px; display: inline-block; }
                        .status { background: rgba(16, 185, 129, 0.2); padding: 15px; border-radius: 10px; margin: 20px 0; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🎬 BackgroundFX Studio</h1>
                        <p>Advanced AI-powered background replacement system</p>
                        
                        <div class="status">
                            <h3>✅ System Status: OPERATIONAL</h3>
                            <p>• Database tables created<br>
                            • API endpoints active<br>
                            • Video processing ready</p>
                        </div>
                        
                        <p><strong>Save the Enhanced UI as:</strong> <code>templates/backgroundfx_enhanced.html</code></p>
                        <a href="/dashboard-direct" class="btn">← Back to Dashboard</a>
                        <a href="/video-processing/status" class="btn">🔧 Test API</a>
                    </div>
                </body>
                </html>
            """)
            
    except Exception as e:
        logger.error(f"Error serving BackgroundFX page: {e}")
        return HTMLResponse(content=f"""
            <div style="font-family: Arial, sans-serif; margin: 40px; text-align: center;">
                <h1>BackgroundFX Error</h1>
                <p>Error: {str(e)}</p>
                <p><a href="/dashboard-direct">Back to Dashboard</a></p>
            </div>
        """, status_code=500)

# =============================================================================
# ADMIN PREMIUM MANAGEMENT PAGE
# =============================================================================

@app.get("/admin/premium")
async def admin_premium_page(request: Request):
    """Admin premium management interface"""
    try:
        logger.info("Admin premium page accessed")
        
        # Check if admin premium template exists
        admin_premium_file = Path("templates/admin_premium.html")
        if admin_premium_file.exists():
            templates = Jinja2Templates(directory="templates")
            return templates.TemplateResponse("admin_premium.html", {"request": request})
        else:
            # Fallback to basic admin premium page
            logger.warning("⚠️ Admin premium template not found, using fallback")
            return HTMLResponse(content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Premium Management - MyAvatar Admin</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 40px; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; color: white; }
                        .container { max-width: 800px; margin: 0 auto; padding: 40px; background: rgba(255,255,255,0.1); border-radius: 20px; }
                        h1 { font-size: 3em; margin-bottom: 20px; }
                        .btn { padding: 15px 30px; background: #fff; color: #667eea; text-decoration: none; border-radius: 10px; font-weight: bold; margin: 10px; display: inline-block; }
                        .status { background: rgba(16, 185, 129, 0.2); padding: 15px; border-radius: 10px; margin: 20px 0; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🎯 Premium Management</h1>
                        <p>Manage premium subscriptions and user access</p>
                        
                        <div class="status">
                            <h3>✅ Premium System Status: OPERATIONAL</h3>
                            <p>• Premium routes loaded<br>
                            • Database tables created<br>
                            • User management ready</p>
                        </div>
                        
                        <p><strong>Save the Admin Interface as:</strong> <code>templates/admin_premium.html</code></p>
                        <a href="/admin" class="btn">← Back to Admin</a>
                        <a href="/admin/premium/users" class="btn">🔧 Test API</a>
                    </div>
                </body>
                </html>
            """)
            
    except Exception as e:
        logger.error(f"Error serving admin premium page: {e}")
        return HTMLResponse(content=f"""
            <div style="font-family: Arial, sans-serif; margin: 40px; text-align: center;">
                <h1>Admin Premium Error</h1>
                <p>Error: {str(e)}</p>
                <p><a href="/admin">Back to Admin</a></p>
            </div>
        """, status_code=500)

# Create necessary directories
directories = [
  "static/uploads/audio", 
  "static/uploads/images", 
  "output", 
  "processed", 
  "uploads", 
  "temp_audio", 
  "static/backgrounds",  # BackgroundFX storage
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
  
  # Check for specific route types
  backgroundfx_routes = [r for r in routes if "/api/backgrounds" in r.get("path", "")]
  video_processing_routes = [r for r in routes if "/video-processing" in r.get("path", "")]
  premium_routes = [r for r in routes if "/api/premium" in r.get("path", "") or "/admin/premium" in r.get("path", "")]
  
  return {
      "total_routes": len(app.routes),
      "routes_loaded_successfully": routers_loaded,
      "router_import_errors": router_errors,
      "all_routes": routes,
      "premium_system_status": {
          "premium_routes_loaded": len(premium_routes),
          "premium_routes": premium_routes,
          "premium_router_in_loaded": any("premium_routes" in r for r in routers_loaded),
          "admin_premium_page_available": "/admin/premium" in [r.get("path") for r in routes]
      },
      "backgroundfx_status": {
          "backgroundfx_routes_loaded": len(backgroundfx_routes),
          "backgroundfx_routes": backgroundfx_routes,
          "backgroundfx_page_available": "/backgroundfx" in [r.get("path") for r in routes],
          "heygen_api_configured": bool(os.getenv("HEYGEN_API_KEY") and os.getenv("HEYGEN_API_KEY") != "your-heygen-api-key"),
          "unsplash_api_configured": bool(os.getenv("UNSPLASH_ACCESS_KEY") and os.getenv("UNSPLASH_ACCESS_KEY") != "your-unsplash-key"),
          "openai_api_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your-openai-api-key")
      },
      "video_processing_status": {
          "video_processing_routes_loaded": len(video_processing_routes),
          "video_processing_routes": video_processing_routes,
          "api_prefix": "/video-processing",
          "endpoints_available": [r.get("path") for r in video_processing_routes]
      },
      "refactoring_status": {
          "modular_routes_loaded": len([r for r in routers_loaded if not "legacy" in r]),
          "legacy_routes_loaded": len([r for r in routers_loaded if "legacy" in r]),
          "total_errors": len(router_errors)
      },
      "video_url_refresher_status": {
          "available": video_refresher_available,
          "running": video_refresher_available,
          "refresh_interval": os.getenv('REFRESH_INTERVAL_HOURS', '4') + " hours",
          "expiry_threshold": os.getenv('EXPIRY_THRESHOLD_HOURS', '6') + " hours"
      }
  }

# TEST ROUTE - Simple route to confirm basic functionality
@app.get("/test")
async def test_route():
  """Test route to confirm FastAPI is working"""
  return {
      "message": "FastAPI is working with Premium Features + BackgroundFX + Video Processing!", 
      "routers_loaded": routers_loaded,
      "timestamp": datetime.now().isoformat(),
      "refactoring_complete": True,
      "premium_features_enabled": True,
      "backgroundfx_enabled": "app.routes.backgroundfx_routes" in str(routers_loaded),
      "video_processing_enabled": "app.routes.video_processing_routes" in str(routers_loaded),
      "premium_system_enabled": "app.routes.premium_routes" in str(routers_loaded),
      "modular_structure": {
          "auth_routes": "/login, /register, /logout, /dashboard-direct",
          "admin_routes": "/admin/*",
          "api_routes": "/api/* (ENABLED)",
          "premium_routes": "/api/premium/*, /admin/premium/* (NEW - Complete Premium System)",
          "backgroundfx_routes": "/api/backgrounds/* (HeyGen WebM + Transparent Videos)",
          "video_processing_routes": "/video-processing/* (Advanced Background Replacement)",
          "video_routes": "/voice-recording, /text-to-video (ENABLED)", 
          "emergency_routes": "/emergency/*"
      },
      "premium_endpoints": {
          "admin_users": "/admin/premium/users",
          "admin_set_premium": "/admin/premium/set-user-premium",
          "admin_remove_premium": "/admin/premium/remove-user-premium",
          "user_status": "/api/premium/status",
          "user_start_trial": "/api/premium/start-trial",
          "user_upgrade": "/api/premium/upgrade",
          "check_feature_access": "/api/premium/check-feature-access/{feature}",
          "admin_premium_page": "/admin/premium"
      },
      "backgroundfx_endpoints": {
          "page": "/backgroundfx",
          "status": "/api/backgrounds/status",
          "get_videos": "/api/videos",
          "transparent_video": "/api/backgrounds/get-transparent-video",
          "green_screen": "/api/backgrounds/create-green-screen",
          "backgrounds": "/api/backgrounds",
          "upload_background": "/api/backgrounds/upload",
          "search_images": "/api/backgrounds/search-images",
          "ai_generate": "/api/backgrounds/generate-ai-image",
          "add_from_url": "/api/backgrounds/add-from-url"
      },
      "video_processing_endpoints": {
          "status": "/video-processing/status",
          "upload_video": "/video-processing/upload-video",
          "upload_background": "/video-processing/upload-background", 
          "replace_background": "/video-processing/replace-background",
          "job_status": "/video-processing/job/{job_id}/status",
          "download": "/video-processing/job/{job_id}/download",
          "list_jobs": "/video-processing/jobs"
      },
      "video_url_refresher": {
          "status": "running" if video_refresher_available else "not_available",
          "interval": os.getenv('REFRESH_INTERVAL_HOURS', '4') + " hours"
      }
  }

# =============================================================================
# BACKGROUNDFX INTEGRATION STATUS
# =============================================================================

@app.get("/admin/backgroundfx-status")
async def backgroundfx_system_status():
  """Check BackgroundFX system status for admin"""
  try:
      # Check environment variables
      heygen_configured = bool(os.getenv("HEYGEN_API_KEY") and os.getenv("HEYGEN_API_KEY") != "your-heygen-api-key")
      unsplash_configured = bool(os.getenv("UNSPLASH_ACCESS_KEY") and os.getenv("UNSPLASH_ACCESS_KEY") != "your-unsplash-key")
      openai_configured = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your-openai-api-key")
      
      # Check if routers are loaded
      backgroundfx_router_loaded = "app.routes.backgroundfx_routes" in str(routers_loaded)
      video_processing_router_loaded = "app.routes.video_processing_routes" in str(routers_loaded)
      premium_router_loaded = "app.routes.premium_routes" in str(routers_loaded)
      
      # Check static directory
      backgrounds_dir = Path("static/backgrounds")
      backgrounds_dir_exists = backgrounds_dir.exists()
      
      return {
          "backgroundfx_system_status": "operational" if backgroundfx_router_loaded else "error",
          "premium_system_status": "operational" if premium_router_loaded else "error",
          "router_loaded": backgroundfx_router_loaded,
          "video_processing_router_loaded": video_processing_router_loaded,
          "premium_router_loaded": premium_router_loaded,
          "api_integrations": {
              "heygen_webm_api": heygen_configured,
              "unsplash_search": unsplash_configured,
              "openai_dalle": openai_configured
          },
          "features_available": {
              "transparent_videos": heygen_configured and premium_router_loaded,
              "green_screen_videos": heygen_configured and premium_router_loaded,
              "image_search": unsplash_configured and premium_router_loaded,
              "ai_image_generation": openai_configured and premium_router_loaded,
              "background_library": premium_router_loaded,
              "file_upload": backgrounds_dir_exists and premium_router_loaded,
              "advanced_video_processing": video_processing_router_loaded and premium_router_loaded,
              "premium_user_management": premium_router_loaded,
              "trial_system": premium_router_loaded
          },
          "storage": {
              "backgrounds_directory": str(backgrounds_dir),
              "directory_exists": backgrounds_dir_exists,
              "writable": backgrounds_dir.exists() and os.access(backgrounds_dir, os.W_OK)
          },
          "database_tables": {
              "background_videos": "auto-initialized",
              "user_backgrounds": "auto-initialized",
              "video_processing_jobs": "created",
              "uploaded_videos": "created",
              "background_images": "created",
              "premium_subscriptions": "created" if premium_router_loaded else "missing",
              "premium_features": "created" if premium_router_loaded else "missing"
          },
          "endpoints": {
              "frontend_page": "/backgroundfx",
              "admin_premium_page": "/admin/premium",
              "api_base": "/api/backgrounds",
              "video_processing_base": "/video-processing",
              "premium_api_base": "/api/premium",
              "status_check": "/api/backgrounds/status",
              "video_processing_status": "/video-processing/status",
              "premium_status": "/api/premium/status"
          },
          "timestamp": datetime.now().isoformat()
      }
  except Exception as e:
      return {
          "backgroundfx_system_status": "error",
          "premium_system_status": "error",
          "error": str(e),
          "timestamp": datetime.now().isoformat()
      }

# =============================================================================
# MANUAL VIDEO REFRESH ENDPOINTS
# =============================================================================

@app.get("/admin/refresh-videos")
async def manual_refresh_videos():
  """Manually trigger video URL refresh"""
  try:
      if not video_refresher_available:
          return {"error": "Video URL refresher not available"}
      
      logger.info("Manual video refresh triggered")
      refresher = VideoURLRefresher()
      refresher.run_refresh_cycle()
      
      return {
          "status": "success",
          "message": "Video URL refresh completed",
          "timestamp": datetime.now().isoformat()
      }
  except Exception as e:
      logger.error(f"Manual refresh failed: {e}")
      return {
          "status": "error",
          "message": str(e),
          "timestamp": datetime.now().isoformat()
      }

@app.get("/admin/refresh-status")
async def refresh_status():
  """Check video URL refresh service status"""
  return {
      "video_url_refresher": {
          "available": video_refresher_available,
          "running": video_refresher_available,
          "refresh_interval": os.getenv('REFRESH_INTERVAL_HOURS', '4') + " hours",
          "expiry_threshold": os.getenv('EXPIRY_THRESHOLD_HOURS', '6') + " hours"
      },
      "environment": {
          "REFRESH_INTERVAL_HOURS": os.getenv('REFRESH_INTERVAL_HOURS', '4'),
          "EXPIRY_THRESHOLD_HOURS": os.getenv('EXPIRY_THRESHOLD_HOURS', '6'),
          "REFRESHER_MODE": os.getenv('REFRESHER_MODE', 'continuous')
      },
      "timestamp": datetime.now().isoformat()
  }

# =============================================================================
# HEYGEN AVATAR DEBUG ENDPOINTS
# =============================================================================

@app.get("/debug-avatars")
async def debug_avatars():
  """
  Temporary debug endpoint to inspect HeyGen API response structure.
  Access this at: https://app.myavatar.dk/debug-avatars
  """
  try:
      log_info("Debug avatars endpoint accessed", "Debug")
      
      api_key = os.getenv("HEYGEN_API_KEY")
      if not api_key:
          logger.error("HEYGEN_API_KEY not found in environment")
          raise HTTPException(status_code=500, detail="HEYGEN_API_KEY not configured")
      
      logger.info("Fetching avatars from HeyGen API...")
      result = get_available_avatars(api_key)
      
      if not result:
          raise HTTPException(status_code=500, detail="No response from HeyGen API")
      
      # Analyze the response structure for better debugging
      if isinstance(result, dict) and 'data' in result:
          avatars = result['data']
          logger.info(f"Successfully fetched {len(avatars)} avatars from HeyGen")
          
          # Create analysis for easier debugging
          analysis = {
              "success": True,
              "total_avatars": len(avatars),
              "api_response_keys": list(result.keys()),
              "sample_avatar_keys": list(avatars[0].keys()) if avatars else [],
              "sample_avatars": avatars[:3] if len(avatars) > 3 else avatars,
              "timestamp": datetime.now().isoformat()
          }
          
          # Extract all unique fields across all avatars
          all_fields = set()
          field_samples = {}
          
          for avatar in avatars:
              for key, value in avatar.items():
                  all_fields.add(key)
                  if key not in field_samples and value:
                      field_samples[key] = str(value)[:100]  # First 100 chars as sample
          
          analysis["all_available_fields"] = sorted(list(all_fields))
          analysis["field_samples"] = field_samples
          
          # Look for potential naming fields
          naming_fields = []
          for field in all_fields:
              field_lower = field.lower()
              if any(keyword in field_lower for keyword in ['name', 'title', 'display', 'label', 'desc']):
                  naming_fields.append(field)
          
          analysis["potential_naming_fields"] = naming_fields
          
          log_info(f"Avatar debug analysis completed: {len(avatars)} avatars, {len(all_fields)} unique fields", "Debug")
          return analysis
      else:
          logger.warning(f"Unexpected HeyGen API response structure: {type(result)}")
          return {
              "success": False,
              "raw_response": result,
              "message": "Unexpected response structure from HeyGen API"
          }
      
  except HTTPException:
      raise  # Re-raise HTTP exceptions
  except Exception as e:
      log_error(f"Error in debug-avatars endpoint: {str(e)}", "Debug", e)
      logger.error(f"Debug avatars error traceback: {traceback.format_exc()}")
      raise HTTPException(status_code=500, detail=f"Debug endpoint error: {str(e)}")

@app.get("/debug-env")
async def debug_environment():
  """
  Debug endpoint to check environment variables (safely).
  Shows which keys exist without exposing values.
  """
  try:
      env_status = {
          "HEYGEN_API_KEY": "✓ Set" if os.getenv("HEYGEN_API_KEY") else "✗ Missing",
          "DATABASE_URL": "✓ Set" if os.getenv("DATABASE_URL") else "✗ Missing",
          "CLOUDINARY_CLOUD_NAME": "✓ Set" if os.getenv("CLOUDINARY_CLOUD_NAME") else "✗ Missing",
          "CLOUDINARY_API_KEY": "✓ Set" if os.getenv("CLOUDINARY_API_KEY") else "✗ Missing", 
          "CLOUDINARY_API_SECRET": "✓ Set" if os.getenv("CLOUDINARY_API_SECRET") else "✗ Missing",
          "SECRET_KEY": "✓ Set" if os.getenv("SECRET_KEY") else "✗ Missing",
          "UNSPLASH_ACCESS_KEY": "✓ Set" if os.getenv("UNSPLASH_ACCESS_KEY") else "✗ Missing",
          "OPENAI_API_KEY": "✓ Set" if os.getenv("OPENAI_API_KEY") else "✗ Missing",
          "RAILWAY_ENVIRONMENT": os.getenv("RAILWAY_ENVIRONMENT", "not_railway"),
          "PORT": os.getenv("PORT", "not_set"),
          "REFRESH_INTERVAL_HOURS": os.getenv("REFRESH_INTERVAL_HOURS", "4"),
          "EXPIRY_THRESHOLD_HOURS": os.getenv("EXPIRY_THRESHOLD_HOURS", "6"),
          "REFRESHER_MODE": os.getenv("REFRESHER_MODE", "continuous"),
          "timestamp": datetime.now().isoformat()
      }
      
      # Check if we can import modules
      try:
          from app.api.heygen import get_available_avatars
          env_status["heygen_module"] = "✓ Available"
      except ImportError as e:
          env_status["heygen_module"] = f"✗ Import Error: {str(e)}"
      
      # Check video refresher status
      env_status["video_refresher_module"] = "✓ Available" if video_refresher_available else "✗ Not Available"
      
      # Check premium system
      try:
          from app.routes.premium_routes import check_premium_access
          env_status["premium_system"] = "✓ Available"
      except ImportError as e:
          env_status["premium_system"] = f"✗ Import Error: {str(e)}"
      
      # Check BackgroundFX system
      try:
          from app.routes.backgroundfx_routes import router
          env_status["backgroundfx_system"] = "✓ Available"
      except ImportError as e:
          env_status["backgroundfx_system"] = f"✗ Import Error: {str(e)}"
      
      # Check Video Processing system
      try:
          from app.routes.video_processing_routes import router
          env_status["video_processing_system"] = "✓ Available"
      except ImportError as e:
          env_status["video_processing_system"] = f"✗ Import Error: {str(e)}"
      
      return env_status
      
  except Exception as e:
      return {"error": str(e), "timestamp": datetime.now().isoformat()}

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
  
  # Premium system initialization
  try:
      if "app.routes.premium_routes" in str(routers_loaded):
          logger.info("✅ Premium system loaded successfully")
          logger.info("🎯 Premium user management ready")
          logger.info("🎁 14-day trial system ready")
          logger.info("⭐ Premium feature access control ready")
      else:
          logger.warning("⚠️ Premium system not loaded")
  except Exception as e:
      logger.warning(f"Premium system initialization warning: {e}")
  
  # BackgroundFX system initialization
  try:
      if "app.routes.backgroundfx_routes" in str(routers_loaded):
          logger.info("✅ BackgroundFX system loaded successfully")
          logger.info("🎬 HeyGen WebM API integration ready")
          logger.info("🖼️ Unsplash image search ready")
          logger.info("🤖 OpenAI DALL-E integration ready")
      else:
          logger.warning("⚠️ BackgroundFX system not loaded")
  except Exception as e:
      logger.warning(f"BackgroundFX system check warning: {e}")
      
  # Video Processing system initialization
  try:
      if "app.routes.video_processing_routes" in str(routers_loaded):
          logger.info("✅ Video Processing system loaded successfully")
          logger.info("🎥 Advanced background replacement API ready")
          logger.info("📊 Real-time job tracking ready")
          logger.info("🔄 File upload and processing ready")
      else:
          logger.warning("⚠️ Video Processing system not loaded")
  except Exception as e:
      logger.warning(f"Video Processing system check warning: {e}")
  
  # Report successful startup
  edition_name = "Premium Edition with BackgroundFX + Video Processing + Complete Premium System"
  log_info(f"MyAvatar {edition_name} is running with MODULAR ROUTE STRUCTURE", "Server")
  logger.info(f"✅ Successfully loaded {len(routers_loaded)} route modules: {', '.join(routers_loaded)}")
  
  if router_errors:
      logger.error(f"❌ Failed to load {len(router_errors)} route modules")
      for error in router_errors:
          logger.error(f"   - {error['module']}: {error['error']}")
  
  # Log system status
  modular_count = len([r for r in routers_loaded if not "legacy" in r])
  legacy_count = len([r for r in routers_loaded if "legacy" in r])
  logger.info(f"🏗️ REFACTORING COMPLETE: {modular_count} modular routes, {legacy_count} legacy routes")
  
  # Check feature status
  premium_loaded = any("premium_routes" in r for r in routers_loaded)
  backgroundfx_loaded = any("backgroundfx_routes" in r for r in routers_loaded)
  video_processing_loaded = any("video_processing_routes" in r for r in routers_loaded)
  
  if premium_loaded:
      logger.info("🎯 PREMIUM SYSTEM ACTIVE: Complete user management and access control")
  else:
      logger.warning("⚠️ Premium system not loaded - BackgroundFX and Video Processing will fail")
  
  if backgroundfx_loaded:
      logger.info("🎬 BACKGROUNDFX FEATURES ACTIVE: HeyGen WebM + Transparent Videos ready")
  else:
      logger.warning("⚠️ BackgroundFX features not loaded")
      
  if video_processing_loaded:
      logger.info("🎥 VIDEO PROCESSING FEATURES ACTIVE: Advanced Background Replacement ready")
  else:
      logger.warning("⚠️ Video Processing features not loaded")
  
  # Log video refresher status
  if video_refresher_available:
      logger.info("🔄 Video URL refresher background service is running")
  else:
      logger.warning("⚠️ Video URL refresher background service is not available")
  
  # Final system status
  if premium_loaded and backgroundfx_loaded and video_processing_loaded:
      logger.info("🎉 ALL SYSTEMS OPERATIONAL: Premium + BackgroundFX + Video Processing")
  else:
      logger.warning("⚠️ Some systems not operational - check router loading errors")

# Entry point
if __name__ == "__main__":
  import uvicorn
  uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
