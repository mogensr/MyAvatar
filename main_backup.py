"""
MyAvatar - Merged Complete Application
Railway-compatible with full avatar administration
"""

#####################################################################
# IMPORTS
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
import uvicorn
from datetime import datetime, timedelta
import sqlite3
from passlib.context import CryptContext
from jose import jwt
import requests
import json
from dotenv import load_dotenv
from pydub import AudioSegment

# Load environment variables
load_dotenv()

#####################################################################
# CLOUDINARY CONFIGURATION
#####################################################################
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

# HeyGen API handler
try:
    from heygen_api import HeyGenAPI, create_video_from_audio_file
    HEYGEN_HANDLER_AVAILABLE = True
    print("[OK] HeyGen API handler loaded successfully")
except ImportError as e:
    HEYGEN_HANDLER_AVAILABLE = False
    print(f"⚠️ HeyGen API handler not available: {e}")

#####################################################################
# CONFIGURATION
#####################################################################
SECRET_KEY = "your_secret_key_here_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# HeyGen Configuration
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
HEYGEN_BASE_URL = "https://api.heygen.com"
YOUR_AVATAR_ID = "b5038ba7bd9b4d94ac6b5c9ea70f8d28"

# Base URL - Railway will override this
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

print(f"[INFO] Environment loaded. HeyGen API Key: {HEYGEN_API_KEY[:10] if HEYGEN_API_KEY else 'NOT_FOUND'}...")
print(f"[INFO] BASE_URL loaded: {BASE_URL}")

#####################################################################
# FASTAPI APP INITIALIZATION
#####################################################################
app = FastAPI(title="MyAvatar", description="AI Avatar Video Generation Platform")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files - Railway compatible
try:
    app.mount("/static", StaticFiles(directory="public/static"), name="static")
    print("✅ Static files mounted: public/static")
except Exception as e:
    print(f"⚠️ Static files error: {e}")
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        print("✅ Static files mounted: static (fallback)")
    except:
        print("❌ No static directory found")

# Templates - Multi-directory support
templates = Jinja2Templates(directory="templates")
try:
    templates.env.loader = ChoiceLoader([
        FileSystemLoader("templates/portal"),
        FileSystemLoader("templates/landingpage"),
        FileSystemLoader("templates"),
    ])
    print("✅ Templates configured with multi-directory support")
except Exception as e:
    print(f"⚠️ Template configuration error: {e}")

#####################################################################
# DATABASE FUNCTIONS
#####################################################################
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_db_connection():
    conn = sqlite3.connect("myavatar.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database with all required tables and default data"""
    print("🗃️ Initializing database...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
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
    ''')
    
    # Create avatars table
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
    
    # Create videos table
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
    
    # Check if we need to create default users
    existing_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    
    if existing_users == 0:
        # Create admin user
        admin_password = get_password_hash("admin123")
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            ("admin", "admin@myavatar.com", admin_password, 1)
        )
        
        # Create test user
        user_password = get_password_hash("password123")
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            ("testuser", "test@example.com", user_password, 0)
        )
        
        # Create default avatar for admin
        cursor.execute(
            "INSERT INTO avatars (user_id, name, image_path, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (1, "Standard Avatar", "/static/images/avatar1.png", YOUR_AVATAR_ID)
        )
        
        print("✅ Default users created (admin/admin123, testuser/password123)")
    else:
        print("✅ Users already exist, skipping default creation")
    
    conn.commit()
    conn.close()
    print("✅ Database initialization complete")

# Initialize database on startup (Railway compatible)
init_database()

#####################################################################
# AUTHENTICATION FUNCTIONS
#####################################################################
def authenticate_user(username: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    
    if not user or not verify_password(password, user["hashed_password"]):
        return False
    return user

def authenticate_user_by_email(email: str, password: str):
    """Authenticate user by email (for client login)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    
    if not user or not verify_password(password, user["hashed_password"]):
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
# HEYGEN API FUNCTIONS
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
# HTML TEMPLATES
#####################################################################

# Marketing Landing Page (with logo support)
MARKETING_HTML = '''
<!DOCTYPE html>
<html lang="da">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyAvatar.dk - AI Avatar Videoer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        .logo {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 1000;
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 10px;
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .logo img {
            width: 100px;
            height: auto;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .card {
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1);
            max-width: 500px;
            width: 100%;
            text-align: center;
        }
        h1 {
            color: #1e293b;
            margin-bottom: 1rem;
            font-size: 2.5rem;
        }
        .subtitle {
            color: #64748b;
            margin-bottom: 2rem;
            font-size: 1.1rem;
        }
        .form-group {
            margin-bottom: 1.5rem;
            text-align: left;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 600;
            color: #374151;
        }
        input[type="email"],
        input[type="password"] {
            width: 100%;
            padding: 1rem;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }
        input[type="email"]:focus,
        input[type="password"]:focus {
            outline: none;
            border-color: #4f46e5;
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }
        .btn {
            width: 100%;
            padding: 1rem;
            background: linear-gradient(45deg, #4f46e5, #7c3aed);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease;
        }
        .btn:hover {
            transform: translateY(-2px);
        }
        .error {
            background: #fee2e2;
            color: #dc2626;
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        .success {
            background: #dcfce7;
            color: #16a34a;
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        .links {
            margin-top: 1rem;
            color: #6b7280;
        }
        .links a {
            color: #4f46e5;
            text-decoration: none;
        }
        .links a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <!-- Silverback Logo -->
    <div class="logo">
        <img src="/static/images/myavatar_logo.png" alt="MyAvatars.dk - We have your back" onerror="this.style.display='none'">
    </div>

    <div class="container">
        <div class="card">
            <h1>MyAvatar.dk</h1>
            <p class="subtitle">Skab professionelle AI avatar videoer</p>
            
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
            
            {% if success %}
            <div class="success">{{ success }}</div>
            {% endif %}
            
            <form method="post" action="/client-login">
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" required placeholder="din@email.com">
                </div>
                
                <div class="form-group">
                    <label for="password">Adgangskode:</label>
                    <input type="password" id="password" name="password" required placeholder="password123">
                </div>
                
                <button type="submit" class="btn">Log Ind</button>
            </form>
            
            <div class="links">
                <p>Test login: admin@myavatar.com / admin123</p>
                <p>Eller: test@example.com / password123</p>
            </div>
        </div>
    </div>
</body>
</html>
'''

# Dashboard with Avatar Recording
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>MyAvatar Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
        .header { background: #333; color: white; padding: 1rem; display: flex; justify-content: space-between; align-items: center; }
        .container { padding: 20px; max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .btn { background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; border: none; cursor: pointer; }
        .btn:hover { background: #3730a3; }
        .user-info { background: #e0f2fe; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        .recorder-container { text-align: center; margin: 20px 0; }
        .record-btn { background: #dc2626; color: white; border: none; border-radius: 50%; width: 80px; height: 80px; font-size: 16px; cursor: pointer; margin: 10px; }
        .record-btn:hover { background: #b91c1c; }
        .record-btn:disabled { background: #ccc; cursor: not-allowed; }
        .audio-preview { width: 100%; margin: 20px 0; }
        .status-message { margin: 15px 0; padding: 10px; border-radius: 5px; }
        .status-message.success { background: #dcfce7; color: #16a34a; border: 1px solid #bbf7d0; }
        .status-message.error { background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; }
        .status-message.info { background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; }
    </style>
    <script>
        window.mediaRecorder = null;
        window.audioChunks = [];
        window.isRecording = false;
        
        function initializeRecorder() {
            navigator.mediaDevices.getUserMedia({audio: true})
                .then(stream => {
                    window.mediaRecorder = new MediaRecorder(stream);
                    
                    window.mediaRecorder.ondataavailable = event => {
                        window.audioChunks.push(event.data);
                    };
                    
                    window.mediaRecorder.onstop = () => {
                        const audioBlob = new Blob(window.audioChunks, {type: 'audio/wav'});
                        const audioUrl = URL.createObjectURL(audioBlob);
                        const audioPreview = document.getElementById('audio-preview');
                        audioPreview.src = audioUrl;
                        audioPreview.style.display = 'block';
                        document.getElementById('heygen-submit-btn').disabled = false;
                    };
                    
                    document.getElementById('record-btn').disabled = false;
                })
                .catch(error => {
                    console.error('Fejl ved adgang til mikrofon:', error);
                    showStatusMessage('Kunne ikke få adgang til mikrofonen.', 'error');
                });
        }
        
        function toggleRecording() {
            if (!window.isRecording) {
                window.audioChunks = [];
                window.mediaRecorder.start();
                window.isRecording = true;
                document.getElementById('record-btn').textContent = 'Stop';
                showStatusMessage('Optagelse i gang...', 'info');
            } else {
                window.mediaRecorder.stop();
                window.isRecording = false;
                document.getElementById('record-btn').textContent = 'Optag';
                showStatusMessage('Optagelse fuldført!', 'success');
            }
        }
        
        function showStatusMessage(message, type) {
            const statusElement = document.getElementById('status-message');
            statusElement.textContent = message;
            statusElement.className = `status-message ${type}`;
            statusElement.style.display = 'block';
        }
        
        function submitToHeyGen() {
            const title = document.getElementById('heygen-title').value;
            const avatarId = document.getElementById('heygen-avatar-select').value;
            
            if (!title) {
                showStatusMessage('Indtast venligst en titel', 'error');
                return;
            }
            
            if (!avatarId) {
                showStatusMessage('Vælg venligst en avatar', 'error');
                return;
            }
            
            const audioElement = document.getElementById('audio-preview');
            if (!audioElement.src) {
                showStatusMessage('Optag venligst lyd først', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('title', title);
            formData.append('avatar_id', avatarId);
            
            fetch(audioElement.src)
                .then(res => res.blob())
                .then(audioBlob => {
                    formData.append('audio', audioBlob, 'recording.wav');
                    showStatusMessage('Sender til HeyGen...', 'info');
                    document.getElementById('heygen-submit-btn').disabled = true;
                    
                    fetch('/api/heygen', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showStatusMessage('Video generering startet!', 'success');
                        } else {
                            showStatusMessage('Fejl: ' + data.error, 'error');
                        }
                        document.getElementById('heygen-submit-btn').disabled = false;
                    })
                    .catch(error => {
                        showStatusMessage('Der opstod en fejl: ' + error.message, 'error');
                        document.getElementById('heygen-submit-btn').disabled = false;
                    });
                });
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            initializeRecorder();
        });
    </script>
</head>
<body>
    <div class="header">
        <h1>MyAvatar Dashboard</h1>
        <div>
            {% if is_admin %}
            <a href="/admin" class="btn" style="margin-right: 10px;">Admin Panel</a>
            {% endif %}
            <a href="/logout" class="btn">Log Ud</a>
        </div>
    </div>
    
    <div class="container">
        <div class="user-info">
            <h3>Velkommen, {{ user.username }}!</h3>
            <p>Email: {{ user.email }}</p>
            {% if user.is_admin %}
            <p><strong>Administrator</strong></p>
            {% endif %}
        </div>
        
        <div class="card">
            <h2>Optag Avatar Video</h2>
            
            <div class="form-group">
                <label for="heygen-title">Video Titel:</label>
                <input type="text" id="heygen-title" name="title" required placeholder="Min Video Titel">
            </div>
            
            <div class="form-group">
                <label for="heygen-avatar-select">Vælg Avatar:</label>
                <select id="heygen-avatar-select" name="avatar_id" required>
                    <option value="">Vælg en avatar</option>
                    {% for avatar in avatars %}
                    <option value="{{ avatar.id }}">{{ avatar.name }} (ID: {{ avatar.heygen_avatar_id }})</option>
                    {% endfor %}
                </select>
            </div>
            
            <div class="recorder-container">
                <button id="record-btn" class="record-btn" onclick="toggleRecording()" disabled>Optag</button>
                <audio id="audio-preview" class="audio-preview" controls style="display:none;"></audio>
                <div id="status-message" class="status-message info" style="display:none;"></div>
                <button id="heygen-submit-btn" class="btn" onclick="submitToHeyGen()" disabled>Send til HeyGen</button>
            </div>
        </div>
        
        {% if avatars %}
        <div class="card">
            <h2>Dine Avatars</h2>
            <ul>
            {% for avatar in avatars %}
                <li>
                    <strong>{{ avatar.name }}</strong><br>
                    HeyGen ID: {{ avatar.heygen_avatar_id }}<br>
                    {% if avatar.image_path %}
                    <img src="{{ avatar.image_path }}" alt="{{ avatar.name }}" style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin: 5px 0;">
                    {% endif %}
                </li>
            {% endfor %}
            </ul>
        </div>
        {% else %}
        <div class="card">
            <h2>Ingen Avatars</h2>
            <p>Kontakt admin for at få oprettet avatars til din konto.</p>
        </div>
        {% endif %}
        
        {% if videos %}
        <div class="card">
            <h2>Dine Videoer</h2>
            <ul>
            {% for video in videos %}
                <li>
                    <strong>{{ video.title }}</strong><br>
                    Avatar: {{ video.avatar_name }}<br>
                    Status: {{ video.status }}<br>
                    Oprettet: {{ video.created_at }}
                </li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

#####################################################################
# ROUTES - AUTHENTICATION
#####################################################################

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Marketing landing page with client login"""
    return HTMLResponse(content=Template(MARKETING_HTML).render(
        request=request,
        error=request.query_params.get("error"),
        success=request.query_params.get("success")
    ))

@app.post("/client-login")
async def client_login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Client login from marketing landing page using email"""
    user = authenticate_user_by_email(email, password)
    
    if not user:
        return HTMLResponse(content=Template(MARKETING_HTML).render(
            request=request, 
            error="Ugyldig email eller adgangskode"
        ))
    
    user = dict(user)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, 
        expires_delta=access_token_expires
    )
    
    # Redirect based on user type
    if user.get("is_admin", 0) == 1:
        response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    else:
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@app.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page (redirect to main)"""
    return RedirectResponse(url="/")

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

#####################################################################
# ROUTES - USER DASHBOARD
#####################################################################

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/?error=login_required", status_code=status.HTTP_302_FOUND)
    
    # Get user's avatars and videos
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
    
    return HTMLResponse(content=Template(DASHBOARD_HTML).render(
        request=request,
        user=user,
        avatars=avatars,
        videos=videos,
        is_admin=user.get("is_admin", 0) == 1
    ))

#####################################################################
# ROUTES - ADMIN DASHBOARD WITH AVATAR MANAGEMENT
#####################################################################

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/?error=admin_required", status_code=status.HTTP_302_FOUND)
    
    # Try to use template file first, fallback to HTML string
    try:
        return templates.TemplateResponse("admin_dashboard.html", {"request": request})
    except:
        # Fallback admin dashboard
        admin_html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .header { background: #dc2626; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .btn { background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; }
                .btn:hover { background: #3730a3; }
                .btn-danger { background: #dc2626; }
                .btn-danger:hover { background: #b91c1c; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background: #f8f9fa; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Admin Dashboard</h1>
                <div>
                    <a href="/dashboard" class="btn">Dashboard</a>
                    <a href="/logout" class="btn">Log Ud</a>
                </div>
            </div>
            
            <div class="card">
                <h2>Hurtig Navigation</h2>
                <a href="/admin/users" class="btn">Administrer Brugere</a>
                <a href="/admin/create-user" class="btn">Opret Ny Bruger</a>
            </div>
        </body>
        </html>
        '''
        return HTMLResponse(content=admin_html)

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    users = cursor.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    users = [dict(u) for u in users]
    conn.close()
    
    # Try template file first, fallback to HTML
    try:
        return templates.TemplateResponse("admin_users.html", {"request": request, "users": users})
    except:
        users_html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Administrer Brugere</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .header { background: #dc2626; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .btn { background: #4f46e5; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 2px; font-size: 14px; }
                .btn:hover { background: #3730a3; }
                .btn-danger { background: #dc2626; }
                .btn-danger:hover { background: #b91c1c; }
                .btn-success { background: #16a34a; }
                .btn-success:hover { background: #15803d; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background: #f8f9fa; font-weight: bold; }
                tr:hover { background: #f8f9fa; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Administrer Brugere</h1>
                <div>
                    <a href="/admin" class="btn">Tilbage til Admin</a>
                    <a href="/admin/create-user" class="btn btn-success">Opret Ny Bruger</a>
                </div>
            </div>
            
            <div class="card">
                <h2>Brugere</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Brugernavn</th>
                            <th>Email</th>
                            <th>Admin</th>
                            <th>Oprettet</th>
                            <th>Handlinger</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for user in users %}
                        <tr>
                            <td>{{ user.id }}</td>
                            <td>{{ user.username }}</td>
                            <td>{{ user.email }}</td>
                            <td>{{ "Ja" if user.is_admin else "Nej" }}</td>
                            <td>{{ user.created_at }}</td>
                            <td>
                                <a href="/admin/user/{{ user.id }}/avatars" class="btn">Avatars</a>
                                <a href="/admin/edit-user/{{ user.id }}" class="btn">Rediger</a>
                                <a href="/admin/reset-password/{{ user.id }}" class="btn btn-danger">Reset Password</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        '''
        return HTMLResponse(content=Template(users_html).render(request=request, users=users))

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
    
    # Try template first, fallback to HTML
    try:
        return templates.TemplateResponse("admin_user_avatars.html", {"request": request, "user": user, "avatars": avatars})
    except:
        avatar_html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ user.username }} - Avatars</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .header { background: #dc2626; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .btn { background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; border: none; cursor: pointer; }
                .btn:hover { background: #3730a3; }
                .btn-success { background: #16a34a; }
                .btn-success:hover { background: #15803d; }
                .btn-danger { background: #dc2626; }
                .btn-danger:hover { background: #b91c1c; }
                .form-group { margin-bottom: 15px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input[type="text"], input[type="file"] { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background: #f8f9fa; }
                .avatar-img { width: 80px; height: 80px; object-fit: cover; border-radius: 8px; }
                .success { background: #dcfce7; color: #16a34a; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
                .error { background: #fee2e2; color: #dc2626; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{{ user.username }} - Avatar Administration</h1>
                <div>
                    <a href="/admin/users" class="btn">Tilbage til Brugere</a>
                </div>
            </div>
            
            <div class="card">
                <h2>Tilføj Ny Avatar</h2>
                <form method="post" action="/admin/user/{{ user.id }}/avatars" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="avatar_name">Avatar Navn:</label>
                        <input type="text" id="avatar_name" name="avatar_name" required placeholder="fx. Business Avatar">
                    </div>
                    
                    <div class="form-group">
                        <label for="heygen_avatar_id">HeyGen Avatar ID:</label>
                        <input type="text" id="heygen_avatar_id" name="heygen_avatar_id" required placeholder="fx. b5038ba7bd9b4d94ac6b5c9ea70f8d28">
                    </div>
                    
                    <div class="form-group">
                        <label for="avatar_img">Avatar Billede:</label>
                        <input type="file" id="avatar_img" name="avatar_img" accept="image/*" required>
                    </div>
                    
                    <button type="submit" class="btn btn-success">Tilføj Avatar</button>
                </form>
            </div>
            
            {% if avatars %}
            <div class="card">
                <h2>Eksisterende Avatars</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Billede</th>
                            <th>Navn</th>
                            <th>HeyGen ID</th>
                            <th>Oprettet</th>
                            <th>Handlinger</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for avatar in avatars %}
                        <tr>
                            <td>
                                {% if avatar.image_path %}
                                <img src="{{ avatar.image_path }}" alt="{{ avatar.name }}" class="avatar-img">
                                {% else %}
                                <div style="width: 80px; height: 80px; background: #f3f4f6; border-radius: 8px; display: flex; align-items: center; justify-content: center;">Ingen billede</div>
                                {% endif %}
                            </td>
                            <td>{{ avatar.name }}</td>
                            <td>{{ avatar.heygen_avatar_id }}</td>
                            <td>{{ avatar.created_at }}</td>
                            <td>
                                <form method="post" action="/admin/user/{{ user.id }}/avatars/delete/{{ avatar.id }}" style="display: inline;">
                                    <button type="submit" class="btn btn-danger" onclick="return confirm('Er du sikker på at du vil slette denne avatar?')">Slet</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% else %}
            <div class="card">
                <h2>Ingen Avatars</h2>
                <p>{{ user.username }} har ingen avatars endnu. Brug formularen ovenfor til at tilføje den første avatar.</p>
            </div>
            {% endif %}
        </body>
        </html>
        '''
        return HTMLResponse(content=Template(avatar_html).render(request=request, user=user, avatars=avatars))

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
    
    try:
        # Check if Cloudinary is configured
        cloudinary_configured = bool(os.getenv("CLOUDINARY_URL") or os.getenv("CLOUDINARY_CLOUD_NAME"))
        
        if cloudinary_configured:
            try:
                # Upload billede til Cloudinary
                res = cloudinary.uploader.upload(avatar_img.file, folder="avatars")
                img_url = res.get("secure_url")
                print(f"[DEBUG] Cloudinary upload success: {img_url}")
            except Exception as cloudinary_error:
                print(f"[ERROR] Cloudinary upload failed: {cloudinary_error}")
                # Fallback: use placeholder image
                img_url = "/static/images/avatar_placeholder.png"
        else:
            print("[WARNING] Cloudinary not configured, using placeholder image")
            # Use placeholder if Cloudinary not configured
            img_url = "/static/images/avatar_placeholder.png"
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO avatars (user_id, name, image_path, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (user_id, avatar_name, img_url, heygen_avatar_id)
        )
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"[DEBUG] Database insert: {rows_affected} rows affected")
        
        if rows_affected > 0:
            return RedirectResponse(url=f"/admin/user/{user_id}/avatars?success=Avatar tilføjet succesfuldt", status_code=303)
        else:
            return RedirectResponse(url=f"/admin/user/{user_id}/avatars?error=Database fejl - ingen rækker påvirket", status_code=303)
            
    except Exception as e:
        print(f"[ERROR] Avatar creation failed: {str(e)}")
        return RedirectResponse(url=f"/admin/user/{user_id}/avatars?error=Fejl: {str(e)}", status_code=303)

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
    
    return RedirectResponse(url=f"/admin/user/{user_id}/avatars?success=Avatar slettet", status_code=303)

# Continue with the rest of admin routes...
@app.get("/admin/create-user", response_class=HTMLResponse)
async def admin_create_user_page(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    create_user_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Opret Bruger</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .card { background: white; padding: 20px; border-radius: 8px; max-width: 500px; margin: 0 auto; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            .btn { background: #4f46e5; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            .btn:hover { background: #3730a3; }
            .success { background: #dcfce7; color: #16a34a; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
            .error { background: #fee2e2; color: #dc2626; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Opret Ny Bruger</h2>
            
            {% if success %}
            <div class="success">{{ success }}</div>
            {% endif %}
            
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
            
            <form method="post" action="/admin/create-user">
                <div class="form-group">
                    <label for="username">Brugernavn:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" required>
                </div>
                
                <div class="form-group">
                    <label for="password">Adgangskode:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                
                <button type="submit" class="btn">Opret Bruger</button>
                <a href="/admin/users" class="btn" style="background: #6b7280; margin-left: 10px;">Tilbage</a>
            </form>
        </div>
    </body>
    </html>
    '''
    
    return HTMLResponse(content=Template(create_user_html).render(
        request=request,
        success=request.query_params.get("success"),
        error=request.query_params.get("error")
    ))

@app.post("/admin/create-user", response_class=HTMLResponse)
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    # Check if user already exists
    conn = get_db_connection()
    cursor = conn.cursor()
    
    existing = cursor.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?", 
        (username, email)
    ).fetchone()
    
    if existing:
        conn.close()
        return RedirectResponse(
            url="/admin/create-user?error=Brugernavn eller email allerede i brug",
            status_code=status.HTTP_302_FOUND
        )
    
    # Create new user
    hashed_password = get_password_hash(password)
    cursor.execute(
        "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
        (username, email, hashed_password)
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse(
        url="/admin/create-user?success=Bruger oprettet succesfuldt",
        status_code=status.HTTP_302_FOUND
    )

@app.get("/admin/reset-password/{user_id}", response_class=HTMLResponse)
async def admin_reset_password_page(request: Request, user_id: int = Path(...)):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    # Get user info
    conn = get_db_connection()
    cursor = conn.cursor()
    target_user = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    
    if not target_user:
        return RedirectResponse(url="/admin/users?error=Bruger ikke fundet", status_code=status.HTTP_302_FOUND)
    
    target_user = dict(target_user)
    
    reset_password_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reset Password</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .card { background: white; padding: 20px; border-radius: 8px; max-width: 500px; margin: 0 auto; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            .btn { background: #dc2626; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            .btn:hover { background: #b91c1c; }
            .user-info { background: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Reset Password</h2>
            
            <div class="user-info">
                <strong>Bruger:</strong> {{ user.username }}<br>
                <strong>Email:</strong> {{ user.email }}
            </div>
            
            <form method="post" action="/admin/reset-password/{{ user.id }}">
                <div class="form-group">
                    <label for="new_password">Ny Adgangskode:</label>
                    <input type="password" id="new_password" name="new_password" required>
                </div>
                
                <div class="form-group">
                    <label for="confirm_password">Bekræft Ny Adgangskode:</label>
                    <input type="password" id="confirm_password" name="confirm_password" required>
                </div>
                
                <button type="submit" class="btn">Reset Password</button>
                <a href="/admin/users" class="btn" style="background: #6b7280; margin-left: 10px;">Tilbage</a>
            </form>
        </div>
    </body>
    </html>
    '''
    
    return HTMLResponse(content=Template(reset_password_html).render(
        request=request,
        user=target_user
    ))

@app.post("/admin/reset-password/{user_id}")
async def admin_reset_password(
    request: Request,
    user_id: int = Path(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    if new_password != confirm_password:
        return RedirectResponse(
            url=f"/admin/reset-password/{user_id}?error=Adgangskoder matcher ikke",
            status_code=status.HTTP_302_FOUND
        )
    
    # Update password
    hashed_password = get_password_hash(new_password)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE users SET hashed_password = ? WHERE id = ?",
        (hashed_password, user_id)
    )
    affected_rows = cursor.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        return RedirectResponse(
            url="/admin/users?success=Password blev ændret succesfuldt",
            status_code=status.HTTP_302_FOUND
        )
    else:
        return RedirectResponse(
            url="/admin/users?error=Fejl ved password ændring",
            status_code=status.HTTP_302_FOUND
        )

#####################################################################
# API ENDPOINTS - HEYGEN INTEGRATION
#####################################################################

@app.post("/api/heygen")
async def create_heygen_video(
    request: Request,
    title: str = Form(...),
    avatar_id: int = Form(...),
    audio: UploadFile = File(...)
):
    """HeyGen integration - Cloudinary audio upload"""
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

        # Save to database
        cursor.execute(
            "INSERT INTO videos (user_id, avatar_id, title, audio_path, status) VALUES (?, ?, ?, ?, ?)",
            (user["id"], avatar_id, title, audio_url, "processing")
        )
        video_id = cursor.lastrowid
        conn.commit()
        conn.close()

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
                "success": False,
                "error": "HeyGen handler not available - check heygen_api.py file",
                "handler": "fallback",
                "message": "Video saved to database, but HeyGen processing unavailable"
            })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": f"Uventet fejl: {str(e)}"
        }, status_code=500)

#####################################################################
# API ENDPOINTS - GENERAL
#####################################################################

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "timestamp": datetime.utcnow().isoformat(),
        "heygen_available": bool(HEYGEN_API_KEY),
        "handler_available": HEYGEN_HANDLER_AVAILABLE
    }

@app.get("/api/users")
async def get_users(request: Request):
    """Get all users (admin only)"""
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    users = cursor.execute("SELECT id, username, email, is_admin, created_at FROM users").fetchall()
    users = [dict(u) for u in users]
    conn.close()
    
    return {"users": users}

#####################################################################
# STARTUP EVENT
#####################################################################

@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    print("🚀 MyAvatar application startup complete")
    print(f"✅ Database initialized")
    print(f"✅ HeyGen API Key: {'✓ Set' if HEYGEN_API_KEY else '✗ Missing'}")
    print(f"✅ Base URL: {BASE_URL}")
    print(f"✅ Avatar Management: ✓ Available")
    print(f"✅ Cloudinary: ✓ Configured")

#####################################################################
# MAIN ENTRY POINT
#####################################################################

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("static/uploads", exist_ok=True)
    os.makedirs("static/images", exist_ok=True)
    
    print("🌟 Starting MyAvatar server...")
    print("🔗 Local: http://localhost:8000")
    print("🔑 Admin: admin@myavatar.com / admin123")
    print("👤 User: test@example.com / password123")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)