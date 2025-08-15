"""
File Change Tracker Startup Module
Initializes and starts the file change tracking service on application startup
"""
import os
import logging
from pathlib import Path
from ..utils.file_change_tracker import get_file_change_service

logger = logging.getLogger("MyAvatar.FileTracker")

def initialize_file_tracker():
    """Initialize and start the file change tracking service"""
    try:
        # Get the project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        logger.info(f"🔄 Initializing file change tracker for project: {project_root}")
        
        # Get or create the file change service
        service = get_file_change_service(project_root)
        
        if service:
            # Start tracking automatically
            success = service.start_tracking()
            if success:
                logger.info("✅ File change tracker started successfully")
                logger.info(f"📁 Monitoring directory: {project_root}")
                logger.info(f"📝 Log files: changes.log, changes.json")
            else:
                logger.warning("⚠️ File change tracker failed to start")
        else:
            logger.error("❌ Could not initialize file change tracker service")
            
    except Exception as e:
        logger.error(f"❌ Error initializing file change tracker: {e}")
        import traceback
        logger.error(f"🔍 Full traceback: {traceback.format_exc()}")

def get_tracker_status():
    """Get the current status of the file change tracker"""
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        service = get_file_change_service(project_root)
        
        if service:
            is_active = service.observer is not None and service.observer.is_alive()
            recent_changes = service.get_recent_changes(10)
            summary = service.get_change_summary()
            
            return {
                "active": is_active,
                "project_root": project_root,
                "recent_changes_count": len(recent_changes),
                "total_changes": summary.get("total_changes", 0) if summary else 0,
                "log_files": {
                    "text_log": os.path.join(project_root, "changes.log"),
                    "json_log": os.path.join(project_root, "changes.json")
                }
            }
        else:
            return {"active": False, "error": "Service not initialized"}
            
    except Exception as e:
        return {"active": False, "error": str(e)}
