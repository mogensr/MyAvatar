"""
MyAvatar Backend - FastAPI
Simple starter main.py
"""
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv

# Integrate Cloudinary for audio storage
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# Load environment variables
load_dotenv()

# Cloudinary Configuration from environment variables
cloudinary.config( 
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "dwnu90g46"),
    api_key = os.getenv("CLOUDINARY_API_KEY", "336129235434633"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET"),
    secure = True
)

# Create FastAPI app
app = FastAPI(
    title="MyAvatar API",
    description="AI Video Generation Platform",
    version="1.0.0"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve HTML app
@app.get("/app")
async def serve_app():
    return FileResponse("mobile_app.html")

# Simple test endpoint
@app.get("/")
async def root():
    return {"message": "MyAvatar API is running!"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": "MyAvatar",
        "version": "1.0.0"
    }

# Test HeyGen API connection
@app.get("/test-heygen")
async def test_heygen():
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API key not found"}
    
    return {
        "message": "HeyGen API key loaded successfully!",
        "key_preview": heygen_key[:10] + "...",
        "key_length": len(heygen_key)
    }

# Test actual HeyGen API call
@app.get("/test-heygen-real")
async def test_heygen_real():
    import aiohttp
    
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API key not found"}
    
    # Test with HeyGen API - get account info
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Try to get account info
            async with session.get(
                "https://api.heygen.com/v2/user/remaining_quota",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "message": "HeyGen API connection successful!",
                        "status": response.status,
                        "data": data
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"HeyGen API error: {response.status}",
                        "details": error_text
                    }
    except Exception as e:
        return {
            "success": False,
            "error": f"Connection error: {str(e)}"
        }

# Generate video with your avatar
@app.post("/api/video/generate")
async def generate_video(audio: UploadFile = File(...)):
    import aiohttp
    
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API key not found"}
    
    # Your avatar ID
    avatar_id = "b5038ba7bd9b4d94ac6b5c9ea70f8d28"
    
    # Create uploads directory if not exists (for logs)
    os.makedirs("uploads/audio", exist_ok=True)
    
    # Set up headers for HeyGen API
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print("Starting HeyGen upload process...")
            
            # Alternative: Use text-to-speech instead of audio upload
            # This is more reliable with current HeyGen API
            
            print("Using text-to-speech approach...")
            
            # For now, let's use a placeholder text and the user's voice
            # In production, you'd implement speech-to-text to convert audio to text
            placeholder_text = "Dette er en test af MyAvatar systemet. Din audio er blevet modtaget og vi genererer nu video med din avatar."
            
            video_payload = {
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": avatar_id
                        },
                        "voice": {
                            "type": "text",
                            "input_text": placeholder_text,
                            "voice_id": "en-US-JennyNeural"  # You can change this to match user's voice later
                        }
                    }
                ],
                "dimension": {
                    "width": 1080,
                    "height": 1920
                },
                "aspect_ratio": "9:16"
            }
            
            print("Sending video generation request with text-to-speech...")
            print(f"Payload: {video_payload}")
            
            async with session.post(
                "https://api.heygen.com/v2/video/generate",
                headers=headers,
                json=video_payload
            ) as response:
                print(f"Video generation response status: {response.status}")
                response_text = await response.text()
                print(f"Video generation response: {response_text}")
                
                if response.status == 200:
                    data = await response.json()
                    video_id = data["data"]["video_id"]
                    return {
                        "success": True,
                        "video_id": video_id,
                        "message": "Video generation started! (Using text-to-speech as fallback)",
                        "audio_file": audio_filename,
                        "note": "Audio upload not supported yet - using text-to-speech"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Video generation failed: {response_text}"
                    }
                    
    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Error: {str(e)}"
        }

# Check video status
@app.get("/api/video/status/{video_id}")
async def check_video_status(video_id: str):
    import aiohttp
    
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API key not found"}
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "status": data["data"]["status"],
                        "video_url": data["data"].get("video_url"),
                        "progress": data["data"].get("progress", 0),
                        "data": data["data"]
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"Status check failed: {error_text}"
                    }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)