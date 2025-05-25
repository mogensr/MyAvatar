"""
MyAvatar - Komplet Én-Server Løsning med HeyGen Integration
Alt i én fil - frontend, backend, auth, api - kører på én enkelt port
FORCED DIRECT UPLOAD - INGEN URL METODE
"""

#####################################################################
# IMPORTS OG KONFIGURATION
#####################################################################
from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, File, UploadFile, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from jinja2 import Template, ChoiceLoader, FileSystemLoader
from typing import List, Optional, Dict, Any
import os
import uuid
import shutil
import uvicorn
from datetime import datetime, timedelta
import secrets
import sqlite3
from passlib.context import CryptContext
import jwt
import requests
import json
from dotenv import load_dotenv
import threading
import time
from pydub import AudioSegment

# Load environment variables as early as possible
load_dotenv()

# Initialize FastAPI app and mount static files before any routes or template loader setup
app = FastAPI(title="MyAvatar")
app.mount("/static", StaticFiles(directory="public/static"), name="static")

# CORS MIDDLEWARE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DEBUG: Print all registered routes at startup to diagnose static route issues
if __name__ == "__main__":
    print("[DEBUG] Registered routes:")
    for route in app.routes:
        print(f"  {route.name}: {route.path}")

# Jinja2 multi-directory template loader setup
templates = Jinja2Templates(directory="templates")
templates.env.loader = ChoiceLoader([
    FileSystemLoader("templates/portal"),
    FileSystemLoader("templates/landingpage"),
    FileSystemLoader("templates"),
])

# Cloudinary integration
import cloudinary
import cloudinary.uploader

# Prefer CLOUDINARY_URL if present, otherwise use explicit credentials
if os.getenv("CLOUDINARY_URL"):
    cloudinary.config()
else:
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )

# Import nye HeyGen API handler
try:
    from heygen_api import HeyGenAPI, create_video_from_audio_file
    HEYGEN_HANDLER_AVAILABLE = True
    print("[OK] HeyGen API handler loaded successfully")
except ImportError as e:
    HEYGEN_HANDLER_AVAILABLE = False
    print(f"⚠️ HeyGen API handler not available: {e}")

# Indlæs miljøvariabler fra .env filen
load_dotenv()
print(f"[INFO] Environment loaded. HeyGen API Key: {os.getenv('HEYGEN_API_KEY', 'NOT_FOUND')[:10]}...")

# Konfiguration
SECRET_KEY = "din_hemmelige_nøgle_her"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# HeyGen API-nøgle fra miljøvariabel
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
if not HEYGEN_API_KEY or HEYGEN_API_KEY.startswith("your_"):
    try:
        with open(".env", "r") as env_file:
            for line in env_file:
                if line.startswith("HEYGEN_API_KEY="):
                    HEYGEN_API_KEY = line.split("=", 1)[1].strip()
                    break
        print(f"[INFO] Loaded API key directly from .env file: {HEYGEN_API_KEY[:10]}...")
    except Exception as e:
        print(f"[WARN] Error loading from .env file: {e}")

# HeyGen API configuration
HEYGEN_BASE_URL = "https://api.heygen.com"
YOUR_AVATAR_ID = "b5038ba7bd9b4d94ac6b5c9ea70f8d28"

# Base URL for public audio access - NGROK SUPPORT
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
print(f"[INFO] BASE_URL loaded: {BASE_URL}")


#####################################################################
# PASSWORD HASHING OG DATABASE FUNKTIONER
#####################################################################
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_db_connection():
    conn = sqlite3.connect("myavatar.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db_exists = os.path.exists("myavatar.db")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        heygen_id TEXT,
        avatar_img_url TEXT,
        uploaded_images TEXT,
        phone TEXT,
        logo_url TEXT,
        linkedin_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    '''),
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS avatars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        image_path TEXT NOT NULL,
        heygen_avatar_id TEXT DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        avatar_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        audio_path TEXT NOT NULL,
        video_path TEXT,
        heygen_video_id TEXT DEFAULT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (avatar_id) REFERENCES avatars (id)
    )
    ''')
    
    if not db_exists:
        admin_password = get_password_hash("admin123")
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            ("admin", "admin@myavatar.com", admin_password, 1)
        )
        
        user_password = get_password_hash("password123")
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            ("testuser", "test@example.com", user_password, 0)
        )
        
        admin_id = 1
        cursor.execute(
            "INSERT INTO avatars (user_id, name, image_path, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (admin_id, "Standard", "/static/images/avatar1.png", YOUR_AVATAR_ID)
        )
        
        print("Database initialized with admin user (admin/admin123) and test user (testuser/password123)")
    else:
        # Dynamisk tilføjelse af nye felter hvis de mangler
        columns = [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
        alter_statements = []
        if "is_admin" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        if "heygen_id" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN heygen_id TEXT")
        if "avatar_img_url" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN avatar_img_url TEXT")
        if "uploaded_images" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN uploaded_images TEXT")
        if "phone" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN phone TEXT")
        if "logo_url" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN logo_url TEXT")
        if "linkedin_url" not in columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN linkedin_url TEXT")
        for stmt in alter_statements:
            cursor.execute(stmt)
        if "is_admin" not in columns:
            cursor.execute("UPDATE users SET is_admin = 1 WHERE id = 1")
        print("Checked/updated users table columns")
        print("Using existing database")
    
    conn.commit()
    conn.close()

#####################################################################
# HJÆLPEFUNKTIONER TIL AUTENTIFICERING
#####################################################################
def authenticate_user(username: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except:
        return None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    
    if user is None:
        return None
    
    return dict(user)

def is_admin(request: Request):
    user = get_current_user(request)
    return user and user.get("is_admin", 0) == 1

#####################################################################
# HEYGEN API - CONFIGURATION & UTILITIES
#####################################################################
def get_heygen_headers():
    return {
        "X-API-KEY": HEYGEN_API_KEY,
        "Content-Type": "application/json"
    }

def validate_heygen_api_key():
    try:
        headers = get_heygen_headers()
        response = requests.get(f"{HEYGEN_BASE_URL}/v2/user/remaining_quota", headers=headers)
        return response.status_code == 200
    except:
        return False

#####################################################################
# HTML SKABELONER (forkortet for plads - samme som før)
#####################################################################
LOGIN_HTML = '''<!DOCTYPE html><html><head><title>Log ind - MyAvatar</title><style>body{font-family:Arial,sans-serif;background-color:#f4f4f4;margin:0;padding:0;display:flex;justify-content:center;align-items:center;height:100vh}.container{background-color:white;padding:30px;border-radius:8px;box-shadow:0 0 10px rgba(0,0,0,0.1);width:350px}h1{color:#333;text-align:center;margin-bottom:20px}input[type="text"],input[type="password"]{width:100%;padding:10px;margin:10px 0;border:1px solid #ddd;border-radius:5px;box-sizing:border-box}button{width:100%;padding:10px;background-color:#4CAF50;color:white;border:none;border-radius:5px;cursor:pointer;margin-top:10px}button:hover{background-color:#45a049}.register-link{text-align:center;margin-top:20px}.error{color:red;text-align:center;margin-top:10px}.success{color:green;text-align:center;margin-top:10px}</style></head><body><div class="container"><h1>Log ind på MyAvatar</h1>{% if error %}<p class="error">{{ error }}</p>{% endif %}{% if success %}<p class="success">{{ success }}</p>{% endif %}<form method="post" action="/login"><input type="text" name="username" placeholder="Brugernavn" required><input type="password" name="password" placeholder="Adgangskode" required><button type="submit">Log ind</button></form><p class="register-link">Har du ikke en konto? <a href="/register">Opret konto</a></p></div></body></html>'''

REGISTER_HTML = '''<!DOCTYPE html><html><head><title>Opret konto</title></head><body><h1>Opret konto</h1><form method="post" action="/register"><input type="text" name="username" placeholder="Brugernavn" required><input type="email" name="email" placeholder="Email" required><input type="password" name="password" placeholder="Adgangskode" required><input type="password" name="confirm_password" placeholder="Bekræft adgangskode" required><button type="submit">Opret konto</button></form></body></html>'''

DASHBOARD_HTML = '''<!DOCTYPE html><html><head><title>Dashboard - MyAvatar</title><style>body{font-family:Arial,sans-serif;background-color:#f4f4f4;margin:0;padding:0}.navbar{background-color:#333;color:white;padding:15px;display:flex;justify-content:space-between;align-items:center}.navbar h1{margin:0}.navbar a{color:white;text-decoration:none}.container{padding:20px;max-width:1200px;margin:0 auto}.card{background-color:white;border-radius:8px;box-shadow:0 0 10px rgba(0,0,0,0.1);padding:20px;margin-bottom:20px}h2{color:#333;margin-top:0}.btn{padding:10px 15px;background-color:#4CAF50;color:white;border:none;border-radius:5px;cursor:pointer;text-decoration:none;display:inline-block;margin-top:10px}.btn:hover{background-color:#45a049}.form-group{margin-bottom:15px}label{display:block;margin-bottom:5px}input[type="text"],input[type="file"],select{width:100%;padding:10px;border:1px solid #ddd;border-radius:5px;box-sizing:border-box}.recorder-container{text-align:center;margin:20px 0}.record-btn{background-color:#f44336;color:white;border:none;border-radius:50%;width:80px;height:80px;font-size:16px;cursor:pointer;margin:10px}.record-btn:hover{background-color:#d32f2f}.record-btn:disabled{background-color:#ccc}.audio-preview{width:100%;margin:20px 0}.status-message{margin:15px 0;padding:10px;border-radius:5px}.status-message.success{background-color:#e8f5e9;color:#2e7d32;border:1px solid #c8e6c9}.status-message.error{background-color:#ffebee;color:#c62828;border:1px solid #ffcdd2}.status-message.info{background-color:#e3f2fd;color:#1565c0;border:1px solid #bbdefb}</style><script>window.mediaRecorder=null;window.audioChunks=[];window.isRecording=false;function initializeRecorder(){navigator.mediaDevices.getUserMedia({audio:true}).then(stream=>{window.mediaRecorder=new MediaRecorder(stream);window.mediaRecorder.ondataavailable=event=>{window.audioChunks.push(event.data)};window.mediaRecorder.onstop=()=>{const audioBlob=new Blob(window.audioChunks,{type:'audio/wav'});const audioUrl=URL.createObjectURL(audioBlob);const audioPreview=document.getElementById('audio-preview');audioPreview.src=audioUrl;audioPreview.style.display='block';document.getElementById('heygen-submit-btn').disabled=false};document.getElementById('record-btn').disabled=false}).catch(error=>{console.error('Fejl ved adgang til mikrofon:',error);showStatusMessage('Kunne ikke få adgang til mikrofonen.','error')})}function toggleRecording(){if(!window.isRecording){window.audioChunks=[];window.mediaRecorder.start();window.isRecording=true;document.getElementById('record-btn').textContent='Stop';showStatusMessage('Optagelse i gang...','info')}else{window.mediaRecorder.stop();window.isRecording=false;document.getElementById('record-btn').textContent='Optag';showStatusMessage('Optagelse fuldført!','success')}}function showStatusMessage(message,type){const statusElement=document.getElementById('status-message');statusElement.textContent=message;statusElement.className=`status-message ${type}`;statusElement.style.display='block'}function submitToHeyGen(){const title=document.getElementById('heygen-title').value;const avatarId=document.getElementById('heygen-avatar-select').value;if(!title){showStatusMessage('Indtast venligst en titel','error');return}if(!avatarId){showStatusMessage('Vælg venligst en avatar','error');return}const audioElement=document.getElementById('audio-preview');if(!audioElement.src){showStatusMessage('Optag venligst lyd først','error');return}const formData=new FormData();formData.append('title',title);formData.append('avatar_id',avatarId);fetch(audioElement.src).then(res=>res.blob()).then(audioBlob=>{formData.append('audio',audioBlob,'recording.wav');showStatusMessage('Sender til HeyGen...','info');document.getElementById('heygen-submit-btn').disabled=true;fetch('/api/heygen',{method:'POST',body:formData}).then(response=>response.json()).then(data=>{if(data.success){showStatusMessage('Video generering startet!','success')}else{showStatusMessage('Fejl: '+data.error,'error')}document.getElementById('heygen-submit-btn').disabled=false}).catch(error=>{showStatusMessage('Der opstod en fejl: '+error.message,'error');document.getElementById('heygen-submit-btn').disabled=false})})}document.addEventListener('DOMContentLoaded',function(){initializeRecorder()})</script></head><body><div class="navbar"><h1>MyAvatar Dashboard</h1><div>{% if is_admin %}<a href="/admin" style="margin-right: 15px;">Admin</a>{% endif %}<a href="/logout">Log ud</a></div></div><div class="container"><div class="card"><h2>Optag Video med HeyGen</h2><div class="form-group"><label for="heygen-title">Titel:</label><input type="text" id="heygen-title" name="title" required></div><div class="form-group"><label for="heygen-avatar-select">Vælg avatar:</label><select id="heygen-avatar-select" name="avatar_id" required><option value="">Vælg en avatar</option>{% for avatar in avatars %}<option value="{{ avatar['id'] }}">{{ avatar['name'] }}</option>{% endfor %}</select></div><div class="recorder-container"><button id="record-btn" class="record-btn" onclick="toggleRecording()" disabled>Optag</button><audio id="audio-preview" class="audio-preview" controls style="display:none;"></audio><div id="status-message" class="status-message info" style="display:none;"></div><button id="heygen-submit-btn" class="btn" onclick="submitToHeyGen()" disabled>Send til HeyGen</button></div></div></div></body></html>'''

# ADMIN_HTML er nu erstattet af en rigtig template-fil (admin_dashboard.html)

#####################################################################
# AUTHENTICATION ROUTES
#####################################################################
# Public landing page route (always shows landingpage/customer_portal.html)
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
   return templates.TemplateResponse("marketing_landing.html", {"request": request})

@app.get("/customer-portal", response_class=HTMLResponse)
async def customer_portal(request: Request):
    return templates.TemplateResponse("marketing_landing.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return HTMLResponse(content=Template(LOGIN_HTML).render(
        request=request,
        error=request.query_params.get("error"),
        success=request.query_params.get("success")
    ))

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        return HTMLResponse(
            content=Template(LOGIN_HTML).render(
                request=request, error="Ugyldigt brugernavn eller adgangskode"
            )
        )
    user = dict(user)  # Konverterer sqlite3.Row til dict
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
    )
    # Admin redirect
    if user.get("is_admin", 0) == 1:
        response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    else:
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return HTMLResponse(content=Template(REGISTER_HTML).render(request=request))

@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if password != confirm_password:
        return HTMLResponse(
            content=Template(REGISTER_HTML).render(
                request=request, error="Adgangskoderne matcher ikke"
            )
        )
    
    hashed_password = get_password_hash(password)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            (username, email, hashed_password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return HTMLResponse(
            content=Template(REGISTER_HTML).render(
                request=request, error="Brugernavn eller email er allerede i brug"
            )
        )
    finally:
        conn.close()
    
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

#####################################################################
# ADMIN DASHBOARD ROUTES
#####################################################################

@app.post("/admin/users/delete/{user_id}", response_class=HTMLResponse)
async def admin_delete_user(request: Request, user_id: int = Path(...)):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete user's avatars and videos first (to maintain integrity)
    cursor.execute("DELETE FROM avatars WHERE user_id=?", (user_id,))
    cursor.execute("DELETE FROM videos WHERE user_id=?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin/users", status_code=303)

@app.get("/admin/user/{user_id}/avatars", response_class=HTMLResponse)
async def admin_user_avatars(request: Request, user_id: int = Path(...)):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return HTMLResponse("<h3>Bruger ikke fundet</h3><a href='/admin/users'>Tilbage</a>")
    user = dict(user)
    avatars = cursor.execute("SELECT * FROM avatars WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    avatars = [dict(a) for a in avatars]
    conn.close()
    return templates.TemplateResponse("admin_user_avatars.html", {"request": request, "user": user, "avatars": avatars})

@app.post("/admin/user/{user_id}/avatars", response_class=HTMLResponse)
async def admin_add_avatar(
    request: Request,
    user_id: int = Path(...),
    avatar_name: str = Form(...),
    heygen_avatar_id: str = Form(...),
    avatar_img: UploadFile = File(...)
):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    # Upload billede til Cloudinary
    res = cloudinary.uploader.upload(avatar_img.file, folder="avatars")
    img_url = res.get("secure_url")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO avatars (user_id, name, image_path, heygen_avatar_id) VALUES (?, ?, ?, ?)",
        (user_id, avatar_name, img_url, heygen_avatar_id)
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/user/{user_id}/avatars", status_code=303)

@app.post("/admin/user/{user_id}/avatars/delete/{avatar_id}", response_class=HTMLResponse)
async def admin_delete_avatar(request: Request, user_id: int = Path(...), avatar_id: int = Path(...)):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM avatars WHERE id=? AND user_id=?", (avatar_id, user_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/admin/user/{user_id}/avatars", status_code=303)


from fastapi import Path
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

# Jinja2 multi-directory template loader setup
templates = Jinja2Templates(directory="templates")
templates.env.loader = ChoiceLoader([
    FileSystemLoader("templates/portal"),
    FileSystemLoader("templates/landingpage"),
    FileSystemLoader("templates"),
])

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    conn = get_db_connection()
    cursor = conn.cursor()
    users = cursor.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    users = [dict(u) for u in users]
    conn.close()
    return templates.TemplateResponse("admin_users.html", {"request": request, "users": users})

@app.get("/admin/edit-user/{user_id}", response_class=HTMLResponse)
async def admin_edit_user(request: Request, user_id: int = Path(...)):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    conn = get_db_connection()
    cursor = conn.cursor()
    db_user = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not db_user:
        conn.close()
        return HTMLResponse("<h3>Bruger ikke fundet</h3><a href='/admin/users'>Tilbage</a>")
    db_user = dict(db_user)
    conn.close()
    return templates.TemplateResponse("admin_edit_user.html", {"request": request, "user": db_user})

@app.post("/admin/edit-user/{user_id}", response_class=HTMLResponse)
async def admin_edit_user_post(
    request: Request,
    user_id: int = Path(...),
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    heygen_id: str = Form(None),
    linkedin_url: str = Form(None),
    avatar_img: UploadFile = File(None),
    logo_img: UploadFile = File(None),
    uploaded_images: list = File(None)
):
    admin_user = get_current_user(request)
    if not admin_user or admin_user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    conn = get_db_connection()
    cursor = conn.cursor()
    db_user = cursor.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not db_user:
        conn.close()
        return HTMLResponse("<h3>Bruger ikke fundet</h3><a href='/admin/users'>Tilbage</a>")
    db_user = dict(db_user)
    # Upload avatar hvis valgt
    avatar_img_url = db_user.get("avatar_img_url")
    if avatar_img:
        res = cloudinary.uploader.upload(avatar_img.file, folder="avatars")
        avatar_img_url = res.get("secure_url")
    # Upload logo hvis valgt
    logo_url = db_user.get("logo_url")
    if logo_img:
        res = cloudinary.uploader.upload(logo_img.file, folder="logos")
        logo_url = res.get("secure_url")
    # Upload ekstra billeder
    uploaded_urls = db_user.get("uploaded_images", "")
    if uploaded_images:
        if not isinstance(uploaded_images, list):
            uploaded_images = [uploaded_images]
        new_urls = []
        for img in uploaded_images:
            res = cloudinary.uploader.upload(img.file, folder="user_uploads")
            new_urls.append(res.get("secure_url"))
        if uploaded_urls:
            uploaded_urls = uploaded_urls + "," + ",".join(new_urls)
        else:
            uploaded_urls = ",".join(new_urls)
    # Opdater bruger i databasen
    cursor.execute(
        "UPDATE users SET username=?, email=?, phone=?, heygen_id=?, avatar_img_url=?, logo_url=?, linkedin_url=?, uploaded_images=? WHERE id=?",
        (username, email, phone, heygen_id, avatar_img_url, logo_url, linkedin_url, uploaded_urls, user_id)
    )
    conn.commit()
    conn.close()
    # Success og redirect
    db_user.update({
        "username": username,
        "email": email,
        "phone": phone,
        "heygen_id": heygen_id,
        "avatar_img_url": avatar_img_url,
        "logo_url": logo_url,
        "linkedin_url": linkedin_url,
        "uploaded_images": uploaded_urls
    })
    return templates.TemplateResponse("admin_edit_user.html", {"request": request, "user": db_user, "success": "Bruger opdateret!"})


@app.get("/admin/create-user", response_class=HTMLResponse)
async def admin_create_user(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    with open("templates/portal/admin_create_user.html", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.post("/admin/create-user", response_class=HTMLResponse)
async def admin_create_user_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: str = Form(None),
    heygen_id: str = Form(None),
    linkedin_url: str = Form(None),
    avatar_img: UploadFile = File(None),
    logo_img: UploadFile = File(None),
    uploaded_images: list = File(None)
):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    # Check if email/username already exists
    conn = get_db_connection()
    cursor = conn.cursor()
    exists = cursor.execute("SELECT id FROM users WHERE username=? OR email=?", (username, email)).fetchone()
    if exists:
        with open("templates/portal/admin_create_user.html", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content.replace("{% if error %}", "<div class='alert alert-danger'>Brugernavn eller email er allerede i brug</div>{% if error %}"))
    # Hash password
    hashed_password = get_password_hash(password)
    # Upload logo (valgfrit)
    logo_url = None
    if logo_img and getattr(logo_img, 'filename', None):
        if logo_img.filename:
            res = cloudinary.uploader.upload(logo_img.file, folder="logos")
            logo_url = res.get("secure_url")
    # Upload ekstra billeder (valgfrit)
    uploaded_urls = []
    if uploaded_images:
        if not isinstance(uploaded_images, list):
            uploaded_images = [uploaded_images]
        for img in uploaded_images:
            if getattr(img, 'filename', None) and img.filename:
                res = cloudinary.uploader.upload(img.file, folder="user_uploads")
                uploaded_urls.append(res.get("secure_url"))
    uploaded_images_str = ",".join(uploaded_urls) if uploaded_urls else None
    # Indsæt bruger i DB (uden heygen_id og avatar_img_url)
    cursor.execute(
        "INSERT INTO users (username, email, hashed_password, phone, logo_url, linkedin_url, uploaded_images) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username, email, hashed_password, phone, logo_url, linkedin_url, uploaded_images_str)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    # Succesbesked og link til bruger-dashboard
    dashboard_link = f"/dashboard?user_id={user_id}"
    with open("templates/portal/admin_create_user.html", encoding="utf-8") as f:
        html_content = f.read()
    html_content = html_content.replace("{% if success %}", f"<div class='alert alert-success'>Bruger oprettet! <a href='{dashboard_link}'>Gå til brugerens dashboard</a></div>{{% if success %}}")
    return HTMLResponse(content=html_content)


@app.get("/admin/upload-avatar", response_class=HTMLResponse)
async def admin_upload_avatar(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return HTMLResponse("<h3>Upload avatar (kommer snart)</h3><a href='/admin'>Tilbage</a>")

@app.get("/admin/manage-passwords", response_class=HTMLResponse)
async def admin_manage_passwords(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return HTMLResponse("<h3>Administrér adgangskoder (kommer snart)</h3><a href='/admin'>Tilbage</a>")

@app.get("/admin/manage-data", response_class=HTMLResponse)
async def admin_manage_data(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return HTMLResponse("<h3>Administrér data (kommer snart)</h3><a href='/admin'>Tilbage</a>")

#####################################################################
# USER DASHBOARD ROUTES
#####################################################################
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    avatars = cursor.execute(
        "SELECT * FROM avatars WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],)
    ).fetchall()
    avatars = [dict(avatar) for avatar in avatars]
    
    videos = cursor.execute(
        "SELECT v.*, a.name as avatar_name FROM videos v JOIN avatars a ON v.avatar_id = a.id WHERE v.user_id = ? ORDER BY v.created_at DESC",
        (user["id"],)
    ).fetchall()
    videos = [dict(video) for video in videos]
    
    conn.close()
    
    is_user_admin = user.get("is_admin", 0) == 1
    
    html_template = Template(DASHBOARD_HTML)
    html_content = html_template.render(
        request=request, 
        user=user, 
        avatars=avatars, 
        videos=videos, 
        is_admin=is_user_admin
    )
    
    return HTMLResponse(content=html_content)

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    with open("templates/portal/admin_dashboard.html", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

#####################################################################
# HEYGEN API INTEGRATION - CLOUDINARY AUDIO UPLOAD
#####################################################################
@app.post("/api/heygen")
async def create_heygen_video(
    request: Request,
    title: str = Form(...),
    avatar_id: int = Form(...),
    audio: UploadFile = File(...)
):
    """
    HeyGen integration - Cloudinary audio upload
    """
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Ikke autoriseret"}, status_code=401)

        if not HEYGEN_API_KEY:
            return JSONResponse({"error": "HeyGen API nøgle ikke fundet"}, status_code=500)

        # Get avatar details from database
        conn = get_db_connection()
        cursor = conn.cursor()
        avatar = cursor.execute("SELECT * FROM avatars WHERE id = ? AND user_id = ?", (avatar_id, user["id"])).fetchone()
        
        if not avatar:
            conn.close()
            return JSONResponse({"error": "Avatar ikke fundet"}, status_code=404)
        
        avatar_data = dict(avatar)
        heygen_avatar_id = avatar_data.get('heygen_avatar_id')

        # DEBUG LOGGING
        print(f"[DEBUG] Video request by user: {user['id']} / {user.get('username')}")
        print(f"[DEBUG] Requested avatar_id: {avatar_id}")
        print(f"[DEBUG] Using heygen_avatar_id: {heygen_avatar_id}")
        
        if not heygen_avatar_id:
            conn.close()
            return JSONResponse({"error": "Manglende HeyGen avatar ID"}, status_code=500)
        
        # Upload audio to Cloudinary
        audio_bytes = await audio.read()
        audio_filename = f"audio_{uuid.uuid4()}.mp3"
        try:
            upload_result = cloudinary.uploader.upload(
                audio_bytes,
                resource_type="raw",
                folder="myavatar/audio",
                public_id=audio_filename,
                overwrite=True
            )
            audio_url = upload_result["secure_url"]
        except Exception as e:
            return JSONResponse({"error": f"Cloudinary upload fejlede: {str(e)}"}, status_code=500)

        # (Optional) Save to database if you want to keep local reference
        # cursor.execute(
        #     "INSERT INTO videos (user_id, avatar_id, title, audio_path, status) VALUES (?, ?, ?, ?, ?)",
        #     (user["id"], avatar_id, title, audio_url, "processing")
        # )
        # video_id = cursor.lastrowid
        # conn.commit()
        # conn.close()

        # Call HeyGen API with Cloudinary audio URL
        if HEYGEN_HANDLER_AVAILABLE:
            print("🚀 Using NEW HeyGen API handler")
            heygen_result = create_video_from_audio_file(
                api_key=HEYGEN_API_KEY,
                avatar_id=heygen_avatar_id,
                audio_file_path="",  # No local file upload
                audio_url=audio_url
            )
            return JSONResponse(heygen_result)
        else:
            return JSONResponse({
                "error": "HeyGen handler not available - check heygen_api.py file",
                "handler": "old",
                "message": "New API endpoints not accessible"
            }, status_code=500)

    except Exception as e:
        return JSONResponse({
            "error": f"Uventet fejl: {str(e)}"
        }, status_code=500)

#####################################################################
# DEBUG ENDPOINTS
#####################################################################
@app.get("/debug/manual-video-check/{heygen_video_id}")
async def manual_video_check(heygen_video_id: str):
    """Manual video status check"""
    try:
        headers = {
            "X-API-KEY": HEYGEN_API_KEY,
            "Accept": "application/json"
        }
        
        status_url = f"https://api.heygen.com/v1/video_status.get?video_id={heygen_video_id}"
        
        response = requests.get(status_url, headers=headers)
        
        if response.status_code != 200:
            return {
                "error": f"Status check fejlede: {response.status_code}",
                "response": response.text,
                "video_id": heygen_video_id,
                "base_url": BASE_URL
            }
        
        data = response.json()
        video_data = data.get("data", {})
        status = video_data.get("status")
        
        result = {
            "heygen_video_id": heygen_video_id,
            "status": status,
            "base_url": BASE_URL,
            "full_response": data
        }
        
        if status == "completed":
            video_url = video_data.get("video_url")
            if video_url:
                try:
                    video_filename = f"heygen_{heygen_video_id}.mp4"
                    local_video_path = f"static/uploads/videos/{video_filename}"
                    
                    os.makedirs("static/uploads/videos", exist_ok=True)
                    
                    video_response = requests.get(video_url)
                    if video_response.status_code == 200:
                        with open(local_video_path, "wb") as f:
                            f.write(video_response.content)
                        
                        result["downloaded_to"] = local_video_path
                        result["download_success"] = True
                        result["video_url"] = video_url
                        result["local_path"] = local_video_path
                        
                except Exception as download_error:
                    result["download_error"] = str(download_error)
        
        return result
        
    except Exception as e:
        return {"error": str(e), "video_id": heygen_video_id, "base_url": BASE_URL}

#####################################################################
# SERVER STARTUP
#####################################################################
if __name__ == "__main__":
    # Create directories
    os.makedirs("static/uploads/avatars", exist_ok=True)
    os.makedirs("static/uploads/audio", exist_ok=True)
    os.makedirs("static/uploads/videos", exist_ok=True)
    os.makedirs("static/images", exist_ok=True)
    
    # Initialize database
    init_db()
    
    # Print startup info
    print("-"*60)
    print("[INFO] MyAvatar Server starting up ...")
    print("-"*60)
    print(f"[OK] HeyGen API Key configured: {bool(HEYGEN_API_KEY)}")
    print(f"[INFO] Your Avatar ID: {YOUR_AVATAR_ID}")
    print(f"[INFO] HeyGen Handler Available: {HEYGEN_HANDLER_AVAILABLE}")
    print(f"[INFO] Server starting on: http://localhost:8000")
    print(f"[INFO] Base URL for HeyGen: {BASE_URL}")
    print("[OK] CORS middleware enabled")
    print("[INFO] FORCED DIRECT UPLOAD - INGEN URL METODE!")
    print("-"*60)
    
    # Start server
    uvicorn.run(app, host="0.0.0.0", port=8001)