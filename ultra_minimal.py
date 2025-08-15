"""
Ultra-minimal FastAPI app for Railway deployment testing
No imports beyond FastAPI itself and standard library
"""
from fastapi import FastAPI
import os
import sys
import logging

# Configure simple logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ultra-minimal")

# Create the simplest possible FastAPI app
app = FastAPI()

@app.get("/")
async def root():
    """Root endpoint for health checks"""
    logger.info("Root endpoint accessed")
    return {"status": "ok", "message": "Ultra-minimal app is running"}

@app.get("/info")
async def info():
    """Info endpoint with environment details"""
    logger.info("Info endpoint accessed")
    return {
        "python_version": sys.version,
        "environment": {k: v for k, v in os.environ.items() if not k.startswith("_")}
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting ultra-minimal app on port {port}")
    uvicorn.run("ultra_minimal:app", host="0.0.0.0", port=port)
