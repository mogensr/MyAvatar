"""
Health check endpoints for service deployment
"""
import os
import sys
import platform
import psutil
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Response, Request
import logging

router = APIRouter()
logger = logging.getLogger("MyAvatar.Health")

# Track startup time for uptime reporting
STARTUP_TIME = time.time()

@router.get("/simple-health")
async def simple_health():
    """
    Very simple health check endpoint that always returns OK
    Used for Railway deployment health checks
    """
    logger.info("Simple health check endpoint called")
    return {"status": "ok", "message": "MyAvatar service is running"}

@router.get("/deep-health")
async def deep_health(request: Request):
    """
    More detailed health check for monitoring systems
    Includes system information and basic diagnostics
    """
    logger.info("Deep health check endpoint called")
    
    # Calculate uptime
    uptime_seconds = time.time() - STARTUP_TIME
    uptime_formatted = format_uptime(uptime_seconds)
    
    # Get memory usage
    memory = psutil.virtual_memory()
    memory_used_mb = memory.used / (1024 * 1024)
    memory_total_mb = memory.total / (1024 * 1024)
    
    # Check deployment environment
    is_deployment = os.environ.get("DEPLOYMENT_ENVIRONMENT", "false").lower() == "true"
    deployment_platform = os.environ.get("DEPLOYMENT_PLATFORM", "unknown")
    
    # Build health report
    health_data = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "MyAvatar",
        "uptime": {
            "seconds": uptime_seconds,
            "formatted": uptime_formatted
        },
        "system": {
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "memory_used_mb": round(memory_used_mb, 2),
            "memory_total_mb": round(memory_total_mb, 2),
            "memory_percent": memory.percent
        },
        "deployment": {
            "is_deployment": is_deployment,
            "platform": deployment_platform,
            "environment": os.environ.get("ENVIRONMENT", "development")
        },
        "request": {
            "client": request.client.host if request.client else "unknown",
            "url": str(request.url)
        },
        "backgroundfx_configured": os.environ.get("BACKGROUNDFX_URL") is not None
    }
    
    return health_data

@router.get("/readiness")
async def readiness_probe():
    """
    Kubernetes-style readiness probe endpoint
    Used to determine if the service is ready to receive traffic
    """
    logger.debug("Readiness probe called")
    return {"status": "ready"}

@router.get("/liveness")
async def liveness_probe():
    """
    Kubernetes-style liveness probe endpoint
    Used to determine if the service is alive and should be restarted if not
    """
    logger.debug("Liveness probe called")
    return {"status": "alive"}

def format_uptime(seconds: float) -> str:
    """
    Format uptime seconds into a human-readable string
    """
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    
    return " ".join(parts)
