"""
Ultra simple test server to verify local functionality
"""
from fastapi import FastAPI, Request
import uvicorn
import os

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting test server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
