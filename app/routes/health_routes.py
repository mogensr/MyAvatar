"""
Simple health check endpoint for Railway deployment
"""
from fastapi import APIRouter, Response
import logging

router = APIRouter()
logger = logging.getLogger("MyAvatar.Health")

@router.get("/simple-health")
async def simple_health():
    """
    Very simple health check endpoint that always returns OK
    Used for Railway deployment health checks
    """
    logger.info("Health check endpoint called")
    return {"status": "ok", "message": "MyAvatar service is running"}
