vI KOM HERFRA

Nu har jeg lavet en komplet ny implementation af video generation funktionen:
Ændringer:
1. Bruger tempfile for bedre file handling
2. Fjernet alle voice_id referencer (ingen TTS/Jenny referencer)
3. Ryddet op i payload format for HeyGen API
4. Tilføjet mere debugging output
Dette er den mest direkte og rene implementation:
1. Upload audio til Cloudinary
2. Få URL
3. Send URL til HeyGen
4. INGEN TTS eller voice_id referencer
Push denne main.py til GitHub for at få et helt rent slate!
Hvis det stadig fejler med "JennyNeural" fejl, må der være noget i HeyGen API selv der forsøger at bruge TTS i stedet for audio URL. 🔍

JEG FIK DENNE FEJLKODE RETUR

Nu har jeg lavet en komplet ny implementation af video generation funktionen:
Ændringer:
1. Bruger tempfile for bedre file handling
2. Fjernet alle voice_id referencer (ingen TTS/Jenny referencer)
3. Ryddet op i payload format for HeyGen API
4. Tilføjet mere debugging output
Dette er den mest direkte og rene implementation:
1. Upload audio til Cloudinary
2. Få URL
3. Send URL til HeyGen
4. INGEN TTS eller voice_id referencer
Push denne main.py til GitHub for at få et helt rent slate!
Hvis det stadig fejler med "JennyNeural" fejl, må der være noget i HeyGen API selv der forsøger at bruge TTS i stedet for audio URL. 🔍

FÅR FEJL: Fejl ved video generering: Error: Must supply api_secret

Edit

Afdækkede API-hemmelighedsfejl ved videogenerering

4s





Det ser ud til, at du har problemer med Cloudinary-integrationen. Fejlen "Must supply api_secret" indikerer, at Cloudinary kræver den korrekte autentifikation for at uploade filer.

For at løse dette problem skal du sikre, at:

Du inkluderer Cloudinary api_secret i din konfiguration
Autentifikationsoplysningerne sendes korrekt med upload-anmodningen
Her er et eksempel på, hvordan du kan konfigurere Cloudinary korrekt:

python
import cloudinary
import cloudinary.uploader

# Konfigurer Cloudinary
cloudinary.config( 
  cloud_name = "dit_cloud_name", 
  api_key = "din_api_key", 
  api_secret = "din_api_secret" 
)

# Derefter kan du uploade
result = cloudinary.uploader.upload(audio_file_path)
audio_url = result['secure_url']
Kontrollér, at du har alle tre påkrævede parametre (cloud_name, api_key og api_secret) i din Cloudinary-konfiguration. Disse kan hentes fra dit Cloudinary-dashboard.

Fejlen tyder på, at implementationen er på rette vej, men mangler den korrekte autentifikation for Cloudinary-uploaden.




Retry
Jeg har i min .env følgende:

# Cloudinary Credentials
CLOUDINARY_CLOUD_NAME=dwnu90g46
CLOUDINARY_API_KEY=336129235434633
CLOUDINARY_API_SECRET=2Dnp1UiQUyrXpltXttYPkoJcCg0

Min env ligger i \MyAvatar root.

Edit

Afdækkede miljøvariabel-indlæsningsproblem for Cloudinary-credentials.

2s





Det ser ud til, at dine Cloudinary-legitimationsoplysninger er korrekt defineret i din .env fil, men koden læser sandsynligvis ikke disse miljøvariabler korrekt.

Her er en løsning på problemet:

Sørg for at installere og importere python-dotenv biblioteket for at læse .env filen:
python
import os
from dotenv import load_dotenv

# Indlæs miljøvariabler fra .env filen
load_dotenv()

# Konfigurer Cloudinary med miljøvariabler
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)
Sørg for, at python-dotenv er installeret:
pip install python-dotenv
Kontrollér, at stien til .env filen er korrekt. Hvis din kode kører fra en anden mappe, skal du angive den fulde sti til .env filen:
python
load_dotenv(dotenv_path="/path/to/MyAvatar/.env")
Tilføj debug-output for at verificere, at miljøvariablerne faktisk læses:
python
print(f"Cloud Name: {os.getenv('CLOUDINARY_CLOUD_NAME')}")
print(f"API Key: {os.getenv('CLOUDINARY_API_KEY')}")
print(f"API Secret: {os.getenv('CLOUDINARY_API_SECRET')}")
Dette burde hjælpe med at sikre, at Cloudinary-konfigurationen har adgang til dine legitimationsoplysninger fra .env filen.




Retry
(venv) C:\Users\mogen\Projects\python\CHATGPT\MyAvatar>pip install python-dotenv
Requirement already satisfied: python-dotenv in c:\users\mogen\projects\python\chatgpt\myavatar\venv\lib\site-packages (1.1.0)
[notice] A new release of pip is available: 24.0 -> 25.1.1
[notice] To update, run: python.exe -m pip install --upgrade pip
(venv) C:\Users\mogen\Projects\python\CHATGPT\MyAvatar>

Edit

Diagnosed environment variable loading and Cloudinary configuration issues.

7s






Eftersom python-dotenv allerede er installeret, lad os kontrollere, om miljøvariablerne bliver indlæst korrekt. Her er en test-script, du kan køre for at verificere, at dine Cloudinary-legitimationsoplysninger læses korrekt:

python
import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

# Udskriv nuværende arbejdsmappe
print(f"Nuværende arbejdsmappe: {os.getcwd()}")

# Indlæs miljøvariabler
load_dotenv()

# Udskriv miljøvariabler for at verificere de er indlæst
print(f"CLOUDINARY_CLOUD_NAME: {os.getenv('CLOUDINARY_CLOUD_NAME')}")
print(f"CLOUDINARY_API_KEY: {os.getenv('CLOUDINARY_API_KEY')}")
print(f"CLOUDINARY_API_SECRET: {os.getenv('CLOUDINARY_API_SECRET')}")

# Konfigurer Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Test Cloudinary konfiguration
print("Cloudinary konfiguration:")
print(f"cloud_name: {cloudinary.config().cloud_name}")
print(f"api_key: {cloudinary.config().api_key}")
print(f"api_secret: {cloudinary.config().api_secret}")

# Prøv at udføre en simpel Cloudinary operation for at tjekke forbindelsen
try:
    result = cloudinary.api.ping()
    print(f"Cloudinary forbindelse OK: {result}")
except Exception as e:
    print(f"Cloudinary fejl: {e}")
Gem denne fil som test_cloudinary.py og kør den fra din MyAvatar-mappe for at se om miljøvariablerne indlæses korrekt.

Hvis scriptet viser, at miljøvariablerne er tomme, kan det være fordi:

Stien til .env-filen ikke er korrekt
.env-filen har forkert format
Der er whitespace eller skjulte tegn i miljøvariablerne
Prøv eventuelt at specificere den fulde sti til .env-filen:

python
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))



Retry
1 trin af gangen

(venv) C:\Users\mogen\Projects\python\CHATGPT\MyAvatar>python test_cloudinary.py
Nuværende arbejdsmappe: C:\Users\mogen\Projects\python\CHATGPT\MyAvatar
CLOUDINARY_CLOUD_NAME: dwnu90g46
CLOUDINARY_API_KEY: 336129235434633
CLOUDINARY_API_SECRET: 2Dnp1UiQUyrXpltXttYPkoJcCg0
Cloudinary konfiguration:
cloud_name: dwnu90g46
api_key: 336129235434633
api_secret: 2Dnp1UiQUyrXpltXttYPkoJcCg0
Cloudinary fejl: module 'cloudinary' has no attribute 'api'
(venv) C:\Users\mogen\Projects\python\CHATGPT\MyAvatar>

Edit

Diagnosed Cloudinary import issue and proposed upload test.

4s






Godt, miljøvariablerne bliver indlæst korrekt fra .env-filen! Det er et positivt skridt.

Fejlen "module 'cloudinary' has no attribute 'api'" opstår fordi vi mangler en import. Lad os ændre test-scriptet til at teste upload-funktionaliteten i stedet, hvilket er det, du faktisk har brug for:

python
import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import cloudinary.api  # Tilføj denne import
import tempfile

# Indlæs miljøvariabler
load_dotenv()

# Konfigurer Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Lav en test-fil
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
    temp.write(b"Dette er en test")
    temp_file_path = temp.name

print(f"Test fil oprettet: {temp_file_path}")

# Test upload
try:
    result = cloudinary.uploader.upload(temp_file_path)
    print(f"Upload succesfuld! URL: {result['secure_url']}")
except Exception as e:
    print(f"Upload fejl: {e}")

# Opryd
os.unlink(temp_file_path)
Kør dette script for at teste om du faktisk kan uploade til Cloudinary med dine legitimationsoplysninger. Hvis dette fungerer, er det et tegn på, at din konfiguration er korrekt, og problemet muligvis ligger et andet sted i din kode.




Retry
python test_cloudinary.py

Edit

Pondered potential Cloudinary test scenarios and troubleshooting paths.

3s




Du kørte testen, men delte ikke resultaterne. Jeg antager to mulige scenarier:

Hvis testen var succesfuld (og uploadede filen til Cloudinary):
Dette betyder, at dine Cloudinary-legitimationsoplysninger fungerer korrekt, og problemet ligger et andet sted i din kode. Her er de næste skridt:

Kontrollér, hvordan du konfigurerer Cloudinary i din hovedkode (main.py)
Sørg for, at du importerer og indlæser miljøvariablerne der på samme måde
Brug samme konfigurationsmetode som i test-scriptet
Hvis testen fejlede (viste en fejl):
Del venligst fejlbeskeden, så jeg kan hjælpe med at diagnosticere det specifikke problem.

Lad os nu se på din implementering af video generering. Kan du dele den relevante kode, så vi kan se, hvordan du forsøger at uploade lydfilen til Cloudinary og sende URL'en til HeyGen? Specielt ville jeg gerne se:

Hvordan du indlæser miljøvariablerne
Hvordan du konfigurerer Cloudinary
Din upload-kode
Din HeyGen API-kald



Retry
(venv) C:\Users\mogen\Projects\python\CHATGPT\MyAvatar>python test_cloudinary.py
Test fil oprettet: C:\Users\mogen\AppData\Local\Temp\tmp9mxhlh2g.txt
Upload fejl: Invalid image file
(venv) C:\Users\mogen\Projects\python\CHATGPT\MyAvatar>

Edit

Diagnosed Cloudinary upload issue and proposed resource type fix.

3s




Aha! Fejlen "Invalid image file" giver os et vigtigt spor. Cloudinary forsøger at behandle din fil som et billede (standardindstillingen), men vores test-fil er en tekstfil.

For lydupload skal du specificere resource_type="auto" eller resource_type="video" (Cloudinary bruger "video" resource type for både video og audio).

Lad os opdatere test-scriptet for at teste lydupload:

python
import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import tempfile

# Indlæs miljøvariabler
load_dotenv()

# Konfigurer Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Lav en test-fil (denne gang simulerer vi en lydfil)
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
    temp.write(b"Dette er en test")
    temp_file_path = temp.name

print(f"Test fil oprettet: {temp_file_path}")

# Test upload med resource_type="auto" 
try:
    result = cloudinary.uploader.upload(
        temp_file_path, 
        resource_type="auto"  # Vigtigt! Specifiker resource_type
    )
    print(f"Upload succesfuld! URL: {result['secure_url']}")
except Exception as e:
    print(f"Upload fejl: {e}")

# Opryd
os.unlink(temp_file_path)
Kør dette opdaterede script. Hvis det fungerer, er løsningen at tilføje resource_type="auto" eller resource_type="video" i din upload-kode.




Retry
(venv) C:\Users\mogen\Projects\python\CHATGPT\MyAvatar>python test_cloudinary.py
Test fil oprettet: C:\Users\mogen\AppData\Local\Temp\tmpaw80h275.txt
Upload succesfuld! URL: https://res.cloudinary.com/dwnu90g46/raw/upload/v1747485236/fkfraozyjo80w6stkkbc.txt
(venv) C:\Users\mogen\Projects\python\CHATGPT\MyAvatar>

Edit

Diagnosed Cloudinary upload issue and proposed code modification.

3s





Fantastisk! Det fungerede! Nu ved vi, at dine Cloudinary-legitimationsoplysninger er korrekte, og problemet var blot, at Cloudinary forsøgte at behandle filen som et billede.

Her er løsningen til din video-generering:

Når du uploader lydfiler til Cloudinary, skal du inkludere resource_type="auto" eller resource_type="video" i upload-metoden:

python
# Upload audio fil til Cloudinary
result = cloudinary.uploader.upload(
    audio_file_path,
    resource_type="auto"  # Dette er nøglen til at løse problemet
)
audio_url = result['secure_url']
Det fulde eksempel kunne se sådan ud:

python
import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
import tempfile
import requests

# Indlæs miljøvariabler fra .env filen
load_dotenv()

# Konfigurer Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

def generate_video(audio_file_path, avatar_id, heygen_api_key):
    try:
        # Upload audio fil til Cloudinary
        print(f"Uploader audio fil: {audio_file_path}")
        result = cloudinary.uploader.upload(
            audio_file_path,
            resource_type="auto"  # Vigtigt! Specifiker resource_type
        )
        audio_url = result['secure_url']
        print(f"Audio URL fra Cloudinary: {audio_url}")
        
        # Send anmodning til HeyGen API
        headers = {
            "X-Api-Key": heygen_api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "avatar_id": avatar_id,
            "audio_url": audio_url,
            # Ingen TTS eller voice_id referencer
        }
        
        print(f"Sender anmodning til HeyGen med payload: {payload}")
        response = requests.post(
            "https://api.heygen.com/v1/video.generate",
            headers=headers,
            json=payload
        )
        
        # Håndter svar
        response_data = response.json()
        print(f"HeyGen API svar: {response_data}")
        
        if response.status_code != 200:
            raise Exception(f"HeyGen API fejl: {response_data.get('error', 'Ukendt fejl')}")
            
        return response_data
        
    except Exception as e:
        print(f"Fejl ved video generering: {e}")
        raise e
Indsæt denne opdaterede kode i din main.py, og det burde løse "Must supply api_secret" fejlen. Nu burde lydfilen uploades korrekt til Cloudinary, og URL'en sendes til HeyGen API.




Retry

""" MyAvatar Backend - FastAPI Simple starter main.py """ from fastapi import FastAPI, File, UploadFile from fastapi.middleware.cors import CORSMiddleware from fastapi.staticfiles import StaticFiles from fastapi.responses import FileResponse import os from dotenv import load_dotenv # Int

pasted

Her er min nuværende main... 

Gider du give mig en helt ny?

Edit

Udkastede ny, strømlinet implementering af API-kald

5s






Ny Ren Implementation af MyAvatar API
Her er en helt ny og renere implementation af din FastAPI backend:


main.py
Code 
Dette nye script har flere vigtige forbedringer:

Væsentlige ændringer
Bedre fejlhåndtering: Bruger HTTPException med korrekte statuskoder
Forbedret Cloudinary konfiguration: Sikrer, at resource_type="auto" altid er angivet
Ren HeyGen API implementering: Ingen referencer til TTS eller voice_id
Forbedret debugging: Omfattende logging af hver handling
Udvidet sundhedstjek: Viser om Cloudinary og HeyGen er konfigureret
Bedre timeout-håndtering: Tilføjet timeouts til alle API-kald
Bruger httpx i stedet for aiohttp (mere moderne og lettere at arbejde med)
Unikt ID-generering: Sikrer, at hver lydfil får et unikt ID
Korrekt v2 endpoint for video status
For at bruge denne kode:
Installer de nødvendige afhængigheder, hvis du ikke allerede har gjort det:
pip install fastapi uvicorn python-dotenv cloudinary httpx python-multipart
Sørg for, at din .env fil indeholder:
CLOUDINARY_CLOUD_NAME=dwnu90g46
CLOUDINARY_API_KEY=336129235434633
CLOUDINARY_API_SECRET=2Dnp1UiQUyrXpltXttYPkoJcCg0
HEYGEN_API_KEY=din_heygen_api_nøgle
Gem koden som main.py og kør med:
uvicorn main:app --reload
Denne implementation skulle løse problemet med "Must supply api_secret" og sikre, at lydfiler uploades korrekt til Cloudinary og derefter sendes til HeyGen API.




Retry





"""
MyAvatar Backend - FastAPI
Ren implementation af video generation API
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os
import tempfile
import time
import uuid
from dotenv import load_dotenv

# Cloudinary for audio storage
import cloudinary
import cloudinary.uploader

# HTTP client for HeyGen API requests
import httpx

# Load environment variables
load_dotenv()

# Check required environment variables
if not os.getenv("CLOUDINARY_API_SECRET"):
    print("ADVARSEL: CLOUDINARY_API_SECRET mangler i miljøvariablerne")

if not os.getenv("HEYGEN_API_KEY"):
    print("ADVARSEL: HEYGEN_API_KEY mangler i miljøvariablerne")

# Cloudinary konfiguration
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "dwnu90g46"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "336129235434633"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
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
    allow_origins=["*"],  # Allow all origins
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
    cloudinary_configured = bool(os.getenv("CLOUDINARY_API_SECRET"))
    heygen_configured = bool(os.getenv("HEYGEN_API_KEY"))
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "cloudinary_configured": cloudinary_configured,
        "heygen_configured": heygen_configured
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HeyGen API nøgle ikke fundet"
        )
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.heygen.com/v2/user/remaining_quota",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "HeyGen API forbindelse succesfuld!",
                    "data": response.json()
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"HeyGen API fejl: {response.text}"
                }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forbindelsesfejl: {str(e)}"
        )

# Generer video med avatar
@app.post("/api/video/generate")
async def generate_video(audio: UploadFile = File(...)):
    """
    Generer video med uploaded lydfil.
    
    1. Gemmer lydfilen midlertidigt
    2. Uploader lydfilen til Cloudinary
    3. Sender URL til HeyGen API for at generere video
    """
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HeyGen API nøgle ikke fundet"
        )
    
    # Din avatar ID (bør senere gøres konfigurerbar)
    avatar_id = "b5038ba7bd9b4d94ac6b5c9ea70f8d28"
    
    # Headers for HeyGen API
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        # Opret en unik ID til at identificere denne lydfil
        audio_id = str(uuid.uuid4())
        
        # Gem lydfil midlertidigt
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_path = temp_file.name
            content = await audio.read()
            temp_file.write(content)
        
        print(f"Debug: Gemt lydfil til {temp_path}, størrelse: {len(content)} bytes")
        
        # Upload til Cloudinary
        print("Debug: Uploader til Cloudinary...")
        upload_result = cloudinary.uploader.upload(
            temp_path,
            resource_type="auto",  # Vigtigt: håndterer lydfiler korrekt
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
        async with httpx.AsyncClient() as client:
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
            response = await client.post(
                "https://api.heygen.com/v2/video/generate",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            print(f"Debug: Video generation svar status: {response.status_code}")
            print(f"Debug: Video generation svar: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                video_id = data["data"]["video_id"]
                return {
                    "success": True,
                    "video_id": video_id,
                    "message": "Video generation startet!",
                    "audio_url": audio_url
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Video generation fejlede: {response.text}"
                )
    except cloudinary.exceptions.Error as ce:
        print(f"Exception i Cloudinary upload: {str(ce)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cloudinary fejl: {str(ce)}"
        )
    except Exception as e:
        print(f"Generel exception i video generation: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fejl: {str(e)}"
        )

# Tjek video status
@app.get("/api/video/status/{video_id}")
async def check_video_status(video_id: str):
    """Tjek status for en video, der er under generering."""
    heygen_key = os.getenv("HEYGEN_API_KEY")
    if not heygen_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HeyGen API nøgle ikke fundet"
        )
    
    headers = {
        "X-API-KEY": heygen_key,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.heygen.com/v2/video/status?video_id={video_id}",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "status": data["data"]["status"],
                    "video_url": data["data"].get("video_url"),
                    "progress": data["data"].get("progress", 0),
                    "data": data["data"]
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Status check fejlede: {response.text}"
                )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fejl: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)