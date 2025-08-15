"""
Ultra-simple FastAPI app for Railway deployment testing
"""
import os
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get port from environment with fallback
PORT = os.environ.get("PORT", 8000)
logger.info(f"PORT environment variable: {PORT}")

# Create FastAPI app
app = FastAPI()

@app.get("/")
async def root():
    """Root endpoint that always returns success"""
    logger.info("Root endpoint called")
    return {"status": "ok", "message": "Ultra-simple FastAPI app is running"}

@app.get("/health")
async def health():
    """Health check endpoint for Railway"""
    logger.info("Health check endpoint called")
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "message": "Health check passed"}
    )

if __name__ == "__main__":
    import uvicorn
    # Try to convert PORT to int with fallback
    try:
        port_number = int(PORT)
    except (ValueError, TypeError):
        port_number = 8000
        logger.warning(f"Invalid PORT value: {PORT}, using default: {port_number}")
    
    logger.info(f"Starting server on port: {port_number}")
    uvicorn.run(app, host="0.0.0.0", port=port_number)
