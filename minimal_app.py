"""
Minimal FastAPI app for debugging Railway deployment
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MinimalApp")

# Create a minimal FastAPI app
app = FastAPI(title="Minimal MyAvatar", description="Minimal version for deployment testing")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint returning a simple HTML page"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MyAvatar - Deployment Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 50px; text-align: center; }
            .container { max-width: 800px; margin: 0 auto; }
            h1 { color: #333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MyAvatar Deployment Test</h1>
            <p>This minimal app is running successfully!</p>
            <p>Environment: Railway Production</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Minimal app is running"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Uncaught exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "message": str(exc)}
    )

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("Starting minimal app")
    logger.info(f"Environment variables: {dict(os.environ)}")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("minimal_app:app", host="0.0.0.0", port=8000, reload=True)
