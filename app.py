#!/usr/bin/env python3
"""
Minimal MyAvatar startup script for debugging healthcheck issues
"""
import os
import sys
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create minimal FastAPI app
app = FastAPI(title="MyAvatar", version="1.0.0")

@app.get("/")
def root():
    """Root endpoint"""
    return {"message": "MyAvatar is running", "status": "ok"}

@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "MyAvatar"}

@app.get("/healthz")
def healthz():
    """Alternative health check"""
    return {"status": "healthy"}

@app.get("/ping")
def ping():
    """Ping endpoint"""
    return {"ping": "pong"}

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting MyAvatar on {host}:{port}")
    logger.info(f"Starting MyAvatar on {host}:{port}")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )
