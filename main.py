"""
MyAvatar Backend - FastAPI
Alternative implementation af video generation API med direkte Cloudinary konfiguration
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os
import tempfile
import time
import aiohttp
import uuid
from dotenv import load_dotenv
import sys
import traceback

# Cloudinary for audio storage
import cloudinary
import cloudinary.uploader

# Load environment variables
load_dotenv()

# Gemmer legitimationsoplysninger som variabler for at være sikker
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dwnu90g46")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "336129235434633")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "2Dnp1UiQUyrXpltXttYPkoJcCg0")

# Create FastAPI app
app = FastAPI(
    title="MyAvatar API",
    description="AI Video Generation Platform",
    version="1.0.0"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API rodsti
@app.get("/")
async def root():
    return {"message": "MyAvatar API kører!", "version": "1.0.0"}

# Sundhedstjek endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "cloudinary_cloud_name": CLOUDINARY_CLOUD_NAME,
        "cloudinary_api_key": CLOUDINARY_API_KEY,
        "cloudinary_api_secret_exists": bool(CLOUDINARY_API_SECRET),
        "heygen_api_key_exists": bool(os.getenv("HEYGEN_API_KEY"))
    }

# Test Cloudinary forbindelse
@app.get("/test-cloudinary")
async def test_cloudinary():
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as temp_file:
            temp_path = temp_file.name
            temp_file.write(b"Dette er en test")
        
        # Forsøg upload med eksplicitte legitimationsoplysninger
        result = cloudinary.uploader.upload(
            temp_path,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            cloud_name=CLOUDINARY_CLOUD_NAME,
            resource_type="auto"
        )
        
        os.unlink(temp_path)
        
        return {
            "success": True,
            "url": result["secure_url"],
            "message": "Cloudinary test succesfuld!"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Cloudinary test fejlede: {str(e)}"
        }

# Serve HTML app
@app.get("/app")
async def serve_app():
    return FileResponse("mobile_app.html")

# Test HeyGen API forbindelse
@app.get("/test-heygen")
async def test_heygen():
    """Test forbindelse til HeyGen API og hent kontooplysninger."""
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API nøgle ikke fundet"}
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.heygen.com/v2/user/remaining_quota",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "success": True,
                        "message": "HeyGen API forbindelse succesfuld!",
                        "data": data
                    }
                else:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"HeyGen API fejl: {error_text}"
                    }
    except Exception as e:
        return {
            "success": False,
            "error": f"Forbindelsesfejl: {str(e)}"
        }

# Generer video med avatar
@app.post("/api/video/generate")
async def generate_video(audio: UploadFile = File(...)):
    """
    Generer video med uploaded lydfil.
    
    1. Gemmer lydfilen midlertidigt
    2. Uploader lydfilen til Cloudinary med eksplicitte legitimationsoplysninger
    3. Sender URL til HeyGen API for at generere video
    """
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API nøgle ikke fundet"}
    
    # Din avatar ID (bør senere gøres konfigurerbar)
    avatar_id = "b5038ba7bd9b4d94ac6b5c9ea70f8d28"
    
    # Headers for HeyGen API
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        # Opret en unik ID til at identificere denne lydfil
        audio_id = str(uuid.uuid4())[:8]
        
        # Gem lydfil midlertidigt
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_path = temp_file.name
            content = await audio.read()
            temp_file.write(content)
        
        print(f"Debug: Gemt lydfil til {temp_path}, størrelse: {len(content)} bytes")
        
        # Upload til Cloudinary med EKSPLICITTE legitimationsoplysninger
        print("Debug: Uploader til Cloudinary...")
        print(f"Debug: Cloudinary legitimationsoplysninger: {CLOUDINARY_CLOUD_NAME}, {CLOUDINARY_API_KEY}, {bool(CLOUDINARY_API_SECRET)}")
        
        upload_result = cloudinary.uploader.upload(
            temp_path,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            cloud_name=CLOUDINARY_CLOUD_NAME,
            resource_type="auto",
            folder="myavatar_audio",
            public_id=f"audio_{audio_id}"
        )
        
        # Få den offentlige URL fra Cloudinary
        audio_url = upload_result["secure_url"]
        print(f"Debug: Cloudinary upload succesfuld! URL: {audio_url}")
        
        # Fjern midlertidig fil
        os.unlink(temp_path)
        print("Debug: Midlertidig fil fjernet")
        
        # Generer video med HeyGen API
        async with aiohttp.ClientSession() as session:
            # Forbered payload til HeyGen video generation
            payload = {
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": avatar_id
                        },
                        "audio_url": audio_url  # Direkte audio URL format
                    }
                ],
                "dimension": {
                    "width": 1080,
                    "height": 1920
                },
                "aspect_ratio": "9:16"
            }
            
            print(f"Debug: HeyGen API payload: {payload}")
            
            # Udfør API-kald til at generere video
            async with session.post(
                "https://api.heygen.com/v2/video/generate",
                headers=headers,
                json=payload
            ) as response:
                print(f"Debug: Video generation svar status: {response.status}")
                response_text = await response.text()
                print(f"Debug: Video generation svar: {response_text}")
                
                if response.status == 200:
                    data = await response.json()
                    video_id = data["data"]["video_id"]
                    return {
                        "success": True,
                        "video_id": video_id,
                        "message": "Video generation startet!",
                        "audio_url": audio_url
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Video generation fejlede: {response_text}"
                    }
    except Exception as e:
        print(f"Generel exception i video generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Fejl: {str(e)}"
        }

# Tjek video status
@app.get("/api/video/status/{video_id}")
async def check_video_status(video_id: str):
    """Tjek status for en video, der er under generering."""
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API nøgle ikke fundet"}
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.heygen.com/v2/video/status?video_id={video_id}",
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
                        "error": f"Status check fejlede: {error_text}"
                    }
    except Exception as e:
        return {
            "success": False,
            "error": f"Fejl: {str(e)}"
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)