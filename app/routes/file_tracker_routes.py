"""
File Change Tracker Routes
Provides web interface to view file changes and tracking statistics
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..utils.file_change_tracker import get_file_change_service
from ..auth.authentication import require_admin
import os

router = APIRouter(prefix="/admin/file-tracker", tags=["file-tracker"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def file_tracker_dashboard(request: Request):
    """File change tracker dashboard"""
    admin_user = require_admin(request)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    service = get_file_change_service(project_root)
    
    if not service:
        return templates.TemplateResponse("admin/file_tracker_dashboard.html", {
            "request": request,
            "admin_user": admin_user,
            "error": "File tracking service not initialized"
        })
    
    # Get tracking data
    recent_changes = service.get_recent_changes(50)
    summary = service.get_change_summary()
    
    return templates.TemplateResponse("admin/file_tracker_dashboard.html", {
        "request": request,
        "admin_user": admin_user,
        "recent_changes": recent_changes,
        "summary": summary,
        "tracking_active": service.observer is not None and service.observer.is_alive()
    })

@router.get("/api/recent-changes")
async def get_recent_changes(request: Request, limit: int = 50):
    """API endpoint to get recent file changes"""
    admin_user = require_admin(request)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    service = get_file_change_service(project_root)
    
    if not service:
        return JSONResponse({"error": "File tracking service not initialized"})
    
    changes = service.get_recent_changes(limit)
    return JSONResponse({"changes": changes})

@router.get("/api/summary")
async def get_change_summary(request: Request):
    """API endpoint to get file change summary"""
    admin_user = require_admin(request)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    service = get_file_change_service(project_root)
    
    if not service:
        return JSONResponse({"error": "File tracking service not initialized"})
    
    summary = service.get_change_summary()
    return JSONResponse(summary)

@router.post("/api/start-tracking")
async def start_tracking(request: Request):
    """Start file change tracking"""
    admin_user = require_admin(request)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    service = get_file_change_service(project_root)
    
    if not service:
        return JSONResponse({"success": False, "error": "File tracking service not initialized"})
    
    success = service.start_tracking()
    return JSONResponse({"success": success})

@router.post("/api/stop-tracking")
async def stop_tracking(request: Request):
    """Stop file change tracking"""
    admin_user = require_admin(request)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    service = get_file_change_service(project_root)
    
    if not service:
        return JSONResponse({"success": False, "error": "File tracking service not initialized"})
    
    service.stop_tracking()
    return JSONResponse({"success": True})
