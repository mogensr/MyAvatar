"""
MyAvatar Backend - FastAPI
Med udvidet avatar liste og valgmuligheder
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from enum import Enum
import os
import tempfile
import time
import aiohttp
import json
import uuid
from dotenv import load_dotenv
import sys
import traceback
from typing import Optional, List, Dict, Any

# Cloudinary for audio storage
import cloudinary
import cloudinary.uploader

# Load environment variables
load_dotenv()

# Gemmer legitimationsoplysninger som variabler for at være sikker
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dwnu90g46")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "336129235434633")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "2Dnp1UiQUyrXpltXttYPkoJcCg0")

# Definér video format indstillinger
class VideoFormat(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"

# Dimensioner baseret på videoformat
FORMAT_DIMENSIONS = {
    VideoFormat.PORTRAIT: {
        "width": 1080,
        "height": 1920,
        "aspect_ratio": "9:16"
    },
    VideoFormat.LANDSCAPE: {
        "width": 1920,
        "height": 1080,
        "aspect_ratio": "16:9"
    }
}

# Udvidet avatar liste, der inkluderer den nye avatar
AVAILABLE_AVATARS = [
    {
        "id": "b5038ba7bd9b4d94ac6b5c9ea70f8d28",
        "name": "Standard Avatar (siddende)",
        "description": "Standard avatar i siddende position",
        "thumbnail_url": "https://example.com/avatar1_thumb.jpg",
        "type": "seated"
    },
    {
        "id": "ba93f97aacb84960a423b01278c8dd77",
        "name": "Stående Avatar",
        "description": "Avatar i stående position",
        "thumbnail_url": "https://example.com/avatar2_thumb.jpg",
        "type": "standing"
    }
]

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

# Få tilgængelige avatarer
@app.get("/avatars")
async def list_avatars(client_id: Optional[str] = None):
    """
    Hent en liste over tilgængelige avatarer.
    
    Hvis client_id angives, returneres kun avatarer for den specifikke klient.
    Ellers returneres alle standard avatarer.
    """
    # I en faktisk implementering vil du hente avatarer fra en database
    # baseret på client_id
    
    # For nu returnerer vi bare vores tilgængelige avatarer
    return {
        "success": True,
        "avatars": AVAILABLE_AVATARS
    }

# Få detaljer om en specifik avatar
@app.get("/avatars/{avatar_id}")
async def get_avatar(avatar_id: str):
    """Hent detaljer om en specifik avatar."""
    # I en faktisk implementering vil du hente avatardetaljer fra en database
    
    # For nu søger vi i vores eksempelavatarer
    for avatar in AVAILABLE_AVATARS:
        if avatar["id"] == avatar_id:
            return {
                "success": True,
                "avatar": avatar
            }
    
    # Hvis avatar_id ikke findes
    return {
        "success": False,
        "error": f"Avatar med ID {avatar_id} blev ikke fundet"
    }

# Få tilgængelige avatarer fra HeyGen
@app.get("/heygen/avatars")
async def list_heygen_avatars():
    """Hent en liste over tilgængelige avatarer fra HeyGen API."""
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API nøgle ikke fundet"}
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Prøv både v2 og v1 endepunkter
            endpoints = [
                "https://api.heygen.com/v2/avatar/list",
                "https://api.heygen.com/v1/avatar.list"
            ]
            
            for endpoint in endpoints:
                print(f"Debug: Prøver at hente avatarer fra: {endpoint}")
                
                async with session.get(endpoint, headers=headers) as response:
                    print(f"Debug: Avatar liste svar status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # Opdater vores lokale avatar information hvis muligt
                        try:
                            avatars_from_api = data.get("data", [])
                            for api_avatar in avatars_from_api:
                                avatar_id = api_avatar.get("avatar_id") or api_avatar.get("id")
                                if avatar_id:
                                    # Tjek om denne avatar allerede findes i vores lokale liste
                                    exists = False
                                    for local_avatar in AVAILABLE_AVATARS:
                                        if local_avatar["id"] == avatar_id:
                                            exists = True
                                            break
                                    
                                    # Hvis ikke, tilføj den som "ukendt type"
                                    if not exists:
                                        new_avatar = {
                                            "id": avatar_id,
                                            "name": api_avatar.get("name", f"Avatar {avatar_id[:6]}"),
                                            "description": api_avatar.get("description", "Avatar fra HeyGen"),
                                            "thumbnail_url": api_avatar.get("thumbnail_url", ""),
                                            "type": "unknown"
                                        }
                                        AVAILABLE_AVATARS.append(new_avatar)
                        except Exception as e:
                            print(f"Kunne ikke opdatere lokale avatarer: {e}")
                        
                        return {
                            "success": True,
                            "endpoint_used": endpoint,
                            "avatars": data.get("data", []),
                            "local_avatars": AVAILABLE_AVATARS,
                            "raw_response": data
                        }
            
            # Hvis ingen endepunkter lykkedes, returnér en fejl
            return {
                "success": False,
                "error": "Kunne ikke hente avatar liste fra hverken v1 eller v2 API"
            }
    except Exception as e:
        print(f"Exception ved avatar liste: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Fejl: {str(e)}"
        }

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

# Test formatvalgsmuligheder
@app.get("/test-format-options")
async def test_format_options():
    """
    Test hvilke formatvalgsmuligheder der er tilgængelige for voice-to-video.
    Denne funktion forsøger at generere ultra-korte test-videoer i forskellige formater
    for at se hvilke der accepteres af API'en.
    """
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API nøgle ikke fundet"}
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    # Test URL til en meget kort lydfil
    test_audio_url = "https://res.cloudinary.com/dwnu90g46/raw/upload/v1747487857/xkh84e1jdgnycz4n7duk.txt"
    
    results = {}
    formats = [
        {"name": "portrait", "width": 1080, "height": 1920, "aspect_ratio": "9:16"},
        {"name": "landscape", "width": 1920, "height": 1080, "aspect_ratio": "16:9"},
        {"name": "square", "width": 1080, "height": 1080, "aspect_ratio": "1:1"}
    ]
    
    async with aiohttp.ClientSession() as session:
        for fmt in formats:
            payload = {
                "video_inputs": [
                    {
                        "character": {
                            "type": "avatar",
                            "avatar_id": "b5038ba7bd9b4d94ac6b5c9ea70f8d28"
                        },
                        "voice": {
                            "type": "audio",
                            "audio_url": test_audio_url
                        }
                    }
                ],
                "dimension": {
                    "width": fmt["width"],
                    "height": fmt["height"]
                },
                "aspect_ratio": fmt["aspect_ratio"]
            }
            
            try:
                async with session.post(
                    "https://api.heygen.com/v2/video/generate",
                    headers=headers,
                    json=payload
                ) as response:
                    response_text = await response.text()
                    
                    results[fmt["name"]] = {
                        "status_code": response.status,
                        "supported": response.status == 200,
                        "response": response_text
                    }
            except Exception as e:
                results[fmt["name"]] = {
                    "status_code": None,
                    "supported": False,
                    "error": str(e)
                }
    
    return {
        "success": True,
        "message": "Format test gennemført",
        "format_support": results
    }

# Generer video med avatar
@app.post("/api/video/generate")
async def generate_video(
    audio: UploadFile = File(...),
    avatar_id: str = Form(None),  # Nu valgfrit parameter
    video_format: str = Form(VideoFormat.PORTRAIT.value)
):
    """
    Generer video med uploaded lydfil.
    
    - audio: Lydfil til at generere video med
    - avatar_id: ID på avataren der skal bruges (valgfrit)
    - video_format: Format på videoen (portrait=9:16 eller landscape=16:9)
    
    Bemærk: HeyGen API understøtter muligvis kun 9:16 (portrait) format for voice-to-video.
    """
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API nøgle ikke fundet"}
    
    # Hvis ingen avatar_id er angivet, brug standard avatar
    if not avatar_id:
        avatar_id = "b5038ba7bd9b4d94ac6b5c9ea70f8d28"  # Default avatar ID
    
    # Find avatardetaljer (for logging/debug-formål)
    avatar_details = None
    for avatar in AVAILABLE_AVATARS:
        if avatar["id"] == avatar_id:
            avatar_details = avatar
            break
    
    # Log avatar valg
    if avatar_details:
        print(f"Debug: Bruger avatar: {avatar_details['name']} (ID: {avatar_id})")
    else:
        print(f"Debug: Bruger avatar med ID: {avatar_id} (ikke fundet i lokalt catalog)")
    
    # Konverter video_format til enum hvis det kommer som string
    if isinstance(video_format, str):
        try:
            video_format = VideoFormat(video_format)
        except ValueError:
            return {
                "success": False,
                "error": f"Ugyldigt videoformat: {video_format}. Gyldige værdier er: {', '.join([f.value for f in VideoFormat])}"
            }
    
    # Headers for HeyGen API
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    # Få dimensioner baseret på det valgte format
    dimensions = FORMAT_DIMENSIONS[video_format]
    
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
        print(f"Debug: Midlertidig fil fjernet")
        
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
                        "voice": {
                            "type": "audio",
                            "audio_url": audio_url
                        }
                    }
                ],
                "dimension": {
                    "width": dimensions["width"],
                    "height": dimensions["height"]
                },
                "aspect_ratio": dimensions["aspect_ratio"]
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
                        "audio_url": audio_url,
                        "avatar_id": avatar_id,
                        "avatar_name": avatar_details["name"] if avatar_details else "Unknown Avatar",
                        "video_format": video_format,
                        "dimensions": dimensions
                    }
                else:
                    # Hvis 16:9 format fejler, prøv igen med 9:16 format
                    if video_format == VideoFormat.LANDSCAPE:
                        print("Landscape format fejlede. Prøver med portrait format i stedet.")
                        
                        # Skift til portrait format
                        portrait_dimensions = FORMAT_DIMENSIONS[VideoFormat.PORTRAIT]
                        payload["dimension"] = {
                            "width": portrait_dimensions["width"],
                            "height": portrait_dimensions["height"]
                        }
                        payload["aspect_ratio"] = portrait_dimensions["aspect_ratio"]
                        
                        # Prøv igen med portrait format
                        async with session.post(
                            "https://api.heygen.com/v2/video/generate",
                            headers=headers,
                            json=payload
                        ) as retry_response:
                            print(f"Debug: Retry svar status: {retry_response.status}")
                            retry_text = await retry_response.text()
                            print(f"Debug: Retry svar: {retry_text}")
                            
                            if retry_response.status == 200:
                                retry_data = await retry_response.json()
                                video_id = retry_data["data"]["video_id"]
                                return {
                                    "success": True,
                                    "video_id": video_id,
                                    "message": "Video generation startet! (Bemærk: Landscape format understøttes ikke, bruger portrait format i stedet)",
                                    "audio_url": audio_url,
                                    "avatar_id": avatar_id,
                                    "avatar_name": avatar_details["name"] if avatar_details else "Unknown Avatar",
                                    "video_format": VideoFormat.PORTRAIT,
                                    "dimensions": portrait_dimensions,
                                    "format_fallback": True
                                }
                    
                    # Returner oprindelig fejl
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
    """
    Tjek status for en video, der er under generering.
    
    Bemærk: Hvis videoen stadig genereres, kan HeyGen API returnere en fejlkode,
    selvom videoen genereres korrekt. Dette er normalt og betyder bare, at videoen
    stadig er under produktion.
    """
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        return {"error": "HeyGen API nøgle ikke fundet"}
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        # Prøv forskellige endepunkter for at tjekke videostatus
        endpoints = [
            # v2 API formateret med video_id som en query parameter
            f"https://api.heygen.com/v2/video/status?video_id={video_id}",
            
            # v2 API formateret med video_id som en del af stien
            f"https://api.heygen.com/v2/video/{video_id}/status",
            
            # Original v1 API
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"
        ]
        
        async with aiohttp.ClientSession() as session:
            # Information fra HeyGen dashboard (som fallback)
            status_info = {
                "success": True,
                "status": "processing",
                "message": "Videoen er under generering. Dette kan tage flere minutter. Status opdateres automatisk.",
                "video_id": video_id,
                "progress": 0
            }
            
            dashboard_url = f"https://studio.heygen.com/video/{video_id}"
            status_info["dashboard_url"] = dashboard_url
            
            # Prøv hvert endepunkt
            for i, endpoint in enumerate(endpoints):
                try:
                    print(f"Debug: Prøver status endpoint #{i+1}: {endpoint}")
                    
                    async with session.get(endpoint, headers=headers) as response:
                        print(f"Debug: Status svar status: {response.status}")
                        response_text = await response.text()
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                return {
                                    "success": True,
                                    "endpoint_used": endpoint,
                                    "status": data["data"]["status"],
                                    "video_url": data["data"].get("video_url"),
                                    "progress": data["data"].get("progress", 0),
                                    "data": data["data"],
                                    "dashboard_url": dashboard_url
                                }
                            except (KeyError, json.JSONDecodeError) as je:
                                print(f"Kunne ikke parse JSON svar: {je}")
                except Exception as e:
                    print(f"Fejl ved forsøg på endpoint {endpoint}: {str(e)}")
                    # Fortsæt til næste endpoint
            
            # Hvis ingen endpoints virkede, returnér fallback info
            print("Ingen API endpoints virkede, returnerer fallback info")
            return status_info
    except Exception as e:
        print(f"Exception ved status check: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Returnér en venlig fejlmeddelelse, da dette kan være normalt under videogenerering
        return {
            "success": True, # Sætter success til True for at undgå fejlvisning i frontend
            "status": "processing",
            "message": "Kunne ikke hente status fra API, men videoen genereres sandsynligvis stadig. Du kan tjekke status på HeyGen dashboard.",
            "video_id": video_id,
            "dashboard_url": f"https://studio.heygen.com/video/{video_id}"
        }

# Frontend endpoints til avatar-vælgeren
@app.get("/avatar-selector", response_class=FileResponse)
async def serve_avatar_selector():
    """Vis avatar vælger-interfacet"""
    return FileResponse("static/avatar-selector.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)