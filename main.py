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

# Load environment variables
load_dotenv()

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
    return FileResponse("../mobile_app.html")

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
    
    # Create uploads directory if not exists
    os.makedirs("../uploads/audio", exist_ok=True)
    
    # Save uploaded audio file
    audio_filename = f"audio_{hash(str(audio.filename))}_{audio.filename}"
    audio_path = f"../uploads/audio/{audio_filename}"
    
    print(f"Saving audio to: {audio_path}")
    print(f"Audio file size: {audio.size} bytes")
    print(f"Audio content type: {audio.content_type}")
    
    with open(audio_path, "wb") as buffer:
        content = await audio.read()
        buffer.write(content)
        print(f"Saved {len(content)} bytes to file")
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print("Starting HeyGen upload process...")
            
            # Get upload URL - using v2 API
            print("Getting upload URL...")
            async with session.get(
                "https://api.heygen.com/v2/assets/upload_url",
                headers=headers,
                params={"type": "audio"}
            ) as response:
                print(f"Upload URL response status: {response.status}")
                response_text = await response.text()
                print(f"Upload URL response: {response_text}")
                
                if response.status != 200:
                    return {"error": f"Failed to get upload URL: {response_text}"}
                
                upload_info = await response.json()
                upload_url = upload_info["data"]["upload_url"]
                asset_id = upload_info["data"]["asset_id"]
                print(f"Got upload URL and asset_id: {asset_id}")
            
            # Upload file to S3/storage
            print("Uploading file...")
            with open(audio_path, 'rb') as audio_file:
                async with session.put(upload_url, data=audio_file) as upload_response:
                    print(f"Upload response status: {upload_response.status}")
                    upload_response_text = await upload_response.text()
                    print(f"Upload response text: {upload_response_text}")
                    
                    if upload_response.status not in [200, 204]:
                        return {"error": f"Failed to upload audio file. Status: {upload_response.status}"}
            
            # Get asset URL
            print("Getting asset URL...")
            async with session.get(
                f"https://api.heygen.com/v2/assets/{asset_id}",
                headers=headers
            ) as asset_response:
                print(f"Asset URL response status: {asset_response.status}")
                asset_response_text = await asset_response.text()
                print(f"Asset URL response: {asset_response_text}")
                
                if asset_response.status != 200:
                    return {"error": f"Failed to get asset URL: {asset_response_text}"}
                
                asset_data = await asset_response.json()
                audio_url = asset_data["data"]["url"]
                print(f"Got audio URL: {audio_url}")
            
            # Generate video
            print("Starting video generation...")
            video_payload = {
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": avatar_id
                        },
                        "voice": {
                            "type": "audio",
                            "audio_url": audio_url
                        }
                    }
                ],
                "dimension": {
                    "width": 1080,
                    "height": 1920
                },
                "aspect_ratio": "9:16"
            }
            
            print(f"Video payload: {video_payload}")
            
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
                        "message": "Video generation started!",
                        "audio_file": audio_filename
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