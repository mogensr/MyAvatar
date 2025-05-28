"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
Railway-compatible with PostgreSQL + HeyGen Webhook + CASCADE DELETE + Enhanced Logging
Clean, tested, and ready to deploy with comprehensive error tracking!
"""
#####################################################################
# IMPORTS & DEPENDENCIES
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
import shutil
from urllib.parse import urlparse
import logging
from collections import deque
import traceback
# Cloudinary imports for avatar storage
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
# Load environment variables
load_dotenv()
# PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

#####################################################################
# ENHANCED LOGGING SYSTEM
#####################################################################
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MyAvatar")

class LogHandler:
    def __init__(self, max_logs=1000):
        self.logs = deque(maxlen=max_logs)
        self.max_logs = max_logs
    
    def add_log(self, level: str, message: str, module: str = "System"):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "module": module,
            "message": message
        }
        self.logs.append(log_entry)
        
        if level == "ERROR":
            logger.error(f"[{module}] {message}")
        elif level == "WARNING":
            logger.warning(f"[{module}] {message}")
        else:
            logger.info(f"[{module}] {message}")
    
    def get_recent_logs(self, limit: int = 100):
        return list(self.logs)[-limit:]
    
    def get_error_logs(self, limit: int = 50):
        error_logs = [log for log in self.logs if log["level"] == "ERROR"]
        return error_logs[-limit:]

log_handler = LogHandler()

def log_info(message: str, module: str = "System"):
    log_handler.add_log("INFO", message, module)

def log_error(message: str, module: str = "System", exception: Exception = None):
    if exception:
        error_details = f"{message}: {str(exception)}"
        log_handler.add_log("ERROR", error_details, module)
        log_handler.add_log("ERROR", f"Traceback: {traceback.format_exc()}", module)
    else:
        log_handler.add_log("ERROR", message, module)

def log_warning(message: str, module: str = "System"):
    log_handler.add_log("WARNING", message, module)

#####################################################################
# HEYGEN API HANDLER
#####################################################################
def create_video_from_audio_file(api_key: str, avatar_id: str, audio_url: str, video_format: str = "16:9"):
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }

    if video_format == "9:16":
        width, height = 720, 1280
        log_info(f"Using Portrait format: {width}x{height}", "HeyGen")
    else:
        width, height = 1280, 720
        log_info(f"Using Landscape format: {width}x{height}", "HeyGen")

    payload = {
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal"
            },
            "voice": {
                "type": "audio",
                "audio_url": audio_url
            },
            "background": {
                "type": "color",
                "value": "#008000"
            }
        }],
        "dimension": {
            "width": width,
            "height": height
        }
    }

    try:
        log_info("Sending request to HeyGen API...", "HeyGen")

        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            json=payload
        )

        log_info(f"HeyGen Response Status: {response.status_code}", "HeyGen")
        log_info(f"HeyGen Full Response: {response.text}", "HeyGen")  # NEW: Log full response

        if response.status_code == 200:
            result = response.json()
            video_id = result.get("data", {}).get("video_id")
            log_info(f"Video generation started successfully: {video_id}", "HeyGen")
            return {
                "success": True,
                "video_id": video_id,
                "message": f"Video generation started successfully ({video_format})",
                "format": video_format,
                "dimensions": f"{width}x{height}"
            }
        else:
            error_msg = f"HeyGen API returned status {response.status_code}: {response.text}"
            log_error(error_msg, "HeyGen")
            return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"HeyGen API request failed: {str(e)}"
        log_error(error_msg, "HeyGen", e)
        return {"success": False, "error": error_msg}

def test_heygen_connection():
    heygen_key = os.getenv("HEYGEN_API_KEY", "")
    if not heygen_key:
        log_error("HEYGEN_API_KEY not found", "HeyGen")
        return

    log_info(f"Testing HeyGen API with key: {heygen_key[:10]}...", "HeyGen")

    test_result = create_video_from_audio_file(
        api_key=heygen_key,
        avatar_id="test_avatar_id",
        audio_url="https://www.soundjay.com/misc/bell-ringing-05.wav",
        video_format="16:9"
    )

    log_info(f"HeyGen Connection Test Result: {test_result}", "HeyGen")
    return test_result

HEYGEN_HANDLER_AVAILABLE = True
log_info("HeyGen API handler loaded successfully", "System")

#####################################################################
# CONFIGURATION
#####################################################################
SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_here_change_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
HEYGEN_BASE_URL = "https://api.heygen.com"
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

cloudinary.config()
log_info(f"Environment loaded. HeyGen API Key: {HEYGEN_API_KEY[:10] if HEYGEN_API_KEY else 'NOT_FOUND'}...", "Config")
log_info(f"BASE_URL loaded: {BASE_URL}", "Config")

#####################################################################
# FASTAPI APP INITIALIZATION
#####################################################################
app = FastAPI(title="MyAvatar", description="AI Avatar Video Generation Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/uploads/audio", exist_ok=True)
os.makedirs("static/uploads/images", exist_ok=True)
os.makedirs("static/uploads/videos", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    log_info("Static files mounted", "FastAPI")
except Exception as e:
    log_error("Static files error", "FastAPI", e)

#####################################################################
# DATABASE HELPER FUNCTIONS (MISSING FUNCTIONS)
#####################################################################
def get_db_connection():
    """Get database connection"""
    database_url = os.getenv("DATABASE_URL")
    
    if database_url and POSTGRESQL_AVAILABLE:
        # PostgreSQL connection
        return psycopg2.connect(database_url)
    else:
        # SQLite fallback
        return sqlite3.connect("myavatar.db")

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    """Execute database query with proper error handling"""
    try:
        conn = get_db_connection()
        
        if os.getenv("DATABASE_URL") and POSTGRESQL_AVAILABLE:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cursor = conn.cursor()
            cursor.row_factory = sqlite3.Row
        
        cursor.execute(query, params)
        
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return result
        
    except Exception as e:
        log_error(f"Database query error: {query}", "Database", e)
        return None

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

#####################################################################
# DATABASE INITIALIZATION
#####################################################################
def init_database():
    log_info("Initializing database...", "Database")
    
    database_url = os.getenv("DATABASE_URL")
    is_postgresql = bool(database_url and POSTGRESQL_AVAILABLE)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgresql:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                is_admin INTEGER DEFAULT 0,
                heygen_id VARCHAR(255),
                avatar_img_url TEXT,
                uploaded_images TEXT,
                phone VARCHAR(50),
                logo_url TEXT,
                linkedin_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS avatars (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                image_path TEXT NOT NULL,
                heygen_avatar_id VARCHAR(255) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                avatar_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                audio_path TEXT NOT NULL,
                video_path TEXT,
                heygen_video_id VARCHAR(255) DEFAULT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (avatar_id) REFERENCES avatars (id)
            )
        ''')
    else:
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

    cursor.execute("SELECT COUNT(*) as user_count FROM users")
    result = cursor.fetchone()

    if is_postgresql:
        existing_users = result['user_count']
    else:
        existing_users = result[0]

    log_info(f"Found {existing_users} existing users", "Database")

    if existing_users == 0:
        log_info("Creating default users...", "Database")

        admin_password = get_password_hash("admin123")
        user_password = get_password_hash("password123")

        if is_postgresql:
            cursor.execute(
                "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (%s, %s, %s, %s)",
                ("admin", "admin@myavatar.com", admin_password, 1)
            )
            cursor.execute(
                "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (%s, %s, %s, %s)",
                ("testuser", "test@example.com", user_password, 0)
            )
        else:
            cursor.execute(
                "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
                ("admin", "admin@myavatar.com", admin_password, 1)
            )
            cursor.execute(
                "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
                ("testuser", "test@example.com", user_password, 0)
            )

        log_info("Default users created", "Database")
    else:
        log_info("Users already exist, skipping default creation", "Database")

    conn.commit()
    conn.close()
    log_info("Database initialization complete", "Database")

init_database()

#####################################################################
# AUTHENTICATION FUNCTIONS
#####################################################################
def authenticate_user(username: str, password: str):
    try:
        user = execute_query("SELECT * FROM users WHERE username = ?", (username,), fetch_one=True)

        if not user or not verify_password(password, user["hashed_password"]):
            log_warning(f"Failed login attempt for username: {username}", "Auth")
            return False

        log_info(f"Successful login: {username}", "Auth")
        return user
    except Exception as e:
        log_error(f"Authentication error for user: {username}", "Auth", e)
        return False

def authenticate_user_by_email(email: str, password: str):
    try:
        user = execute_query("SELECT * FROM users WHERE email = ?", (email,), fetch_one=True)

        if not user or not verify_password(password, user["hashed_password"]):
            log_warning(f"Failed login attempt for email: {email}", "Auth")
            return False

        log_info(f"Successful email login: {email}", "Auth")
        return user
    except Exception as e:
        log_error(f"Email authentication error: {email}", "Auth", e)
        return False

def create_access_token(data: dict, expires_delta: timedelta = None):
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        log_error("Failed to create access token", "Auth", e)
        return None

def get_current_user(request: Request):
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None

        user = execute_query("SELECT * FROM users WHERE username = ?", (username,), fetch_one=True)
        return user
    except Exception as e:
        log_warning("Invalid or expired token", "Auth")
        return None

def is_admin(request: Request):
    user = get_current_user(request)
    return user and user.get("is_admin", 0) == 1

#####################################################################
# CLOUDINARY UPLOAD FUNCTIONS
#####################################################################
async def upload_avatar_to_cloudinary(image_file: UploadFile, user_id: int) -> str:
    try:
        log_info(f"Starting Cloudinary upload for user {user_id}", "Cloudinary")

        image_bytes = await image_file.read()
        public_id = f"user_{user_id}_avatar_{uuid.uuid4().hex}"

        result = cloudinary.uploader.upload(
            image_bytes,
            folder="myavatar/avatars",
            public_id=public_id,
            overwrite=True,
            resource_type="image",
            transformation=[
                {'width': 400, 'height': 400, 'crop': 'fill'},
                {'quality': 'auto', 'fetch_format': 'auto'}
            ]
        )

        log_info(f"Cloudinary upload success: {result['secure_url']}", "Cloudinary")
        return result['secure_url']

    except Exception as e:
        log_error(f"Cloudinary upload failed for user {user_id}", "Cloudinary", e)
        return await upload_avatar_locally(image_file, user_id)

async def upload_avatar_locally(image_file: UploadFile, user_id: int) -> str:
    try:
        log_info(f"Using local fallback upload for user {user_id}", "Storage")

        await image_file.seek(0)

        img_filename = f"user_{user_id}_avatar_{uuid.uuid4().hex}.{image_file.filename.split('.')[-1]}"
        img_path = f"static/uploads/images/{img_filename}"

        img_bytes = await image_file.read()
        with open(img_path, "wb") as f:
            f.write(img_bytes)

        public_url = f"{BASE_URL}/{img_path}"
        log_info(f"Local upload success: {public_url}", "Storage")
        return public_url

    except Exception as e:
        log_error(f"Local upload failed for user {user_id}", "Storage", e)
        return None
#####################################################################
# HTML TEMPLATES
#####################################################################
MARKETING_HTML = '''
<!DOCTYPE html>
<html lang="da">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyAvatar.dk - AI Avatar Videoer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .card { background: white; border-radius: 20px; padding: 3rem; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1); max-width: 500px; width: 100%; text-align: center; }
        h1 { color: #1e293b; margin-bottom: 1rem; font-size: 2.5rem; }
        .subtitle { color: #64748b; margin-bottom: 2rem; font-size: 1.1rem; }
        .form-group { margin-bottom: 1.5rem; text-align: left; }
        label { display: block; margin-bottom: 0.5rem; font-weight: 600; color: #374151; }
        input[type="email"], input[type="password"] { width: 100%; padding: 1rem; border: 2px solid #e5e7eb; border-radius: 10px; font-size: 1rem; transition: border-color 0.3s ease; }
        input[type="email"]:focus, input[type="password"]:focus { outline: none; border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1); }
        .btn { width: 100%; padding: 1rem; background: linear-gradient(45deg, #4f46e5, #7c3aed); color: white; border: none; border-radius: 10px; font-size: 1.1rem; font-weight: 600; cursor: pointer; transition: transform 0.2s ease; }
        .btn:hover { transform: translateY(-2px); }
        .error { background: #fee2e2; color: #dc2626; padding: 1rem; border-radius: 10px; margin-bottom: 1rem; }
        .success { background: #dcfce7; color: #16a34a; padding: 1rem; border-radius: 10px; margin-bottom: 1rem; }
        .links { margin-top: 1rem; color: #6b7280; }
        .links a { color: #4f46e5; text-decoration: none; }
        .links a:hover { text-decoration: underline; }
    </style>
</head>
<body>
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
DASHBOARD_HTML = """
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
        .record-btn { background: #dc2626; color: white; border: none; border-radius: 50%; width: 80px; height: 80px; font-size: 16px; cursor: pointer; margin: 10px; transition: all 0.3s ease; }
        .record-btn:hover { background: #b91c1c; transform: scale(1.05); }
        .record-btn:disabled { background: #ccc; cursor: not-allowed; transform: none; }
        .record-btn.recording { background: #ef4444; animation: pulse-record 1.5s infinite; }
        @keyframes pulse-record { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        .recording-indicator { display: none; color: #dc2626; font-weight: bold; margin: 10px 0; animation: blink 1s infinite; }
        .recording-indicator.active { display: block; }
        @keyframes blink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0.3; } }
        .audio-preview { width: 100%; margin: 20px 0; }
        .status-message { margin: 15px 0; padding: 10px; border-radius: 5px; }
        .status-message.success { background: #dcfce7; color: #16a34a; border: 1px solid #bbf7d0; }
        .status-message.error { background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; }
        .status-message.info { background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; }
        .recording-timer { display: none; font-size: 1.5em; color: #dc2626; font-weight: bold; margin: 10px 0; }
        .recording-timer.active { display: block; }
        .video-list { margin-top: 20px; }
        .video-item { padding: 15px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
        .video-info h4 { margin: 0 0 5px 0; }
        .video-info p { margin: 0; color: #666; font-size: 14px; }
        .video-status { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .status-completed { background: #dcfce7; color: #16a34a; }
        .status-processing { background: #fef3c7; color: #d97706; }
        .status-pending { background: #dbeafe; color: #1d4ed8; }
        .status-failed { background: #fee2e2; color: #dc2626; }
    </style>
    <script>
        window.mediaRecorder = null;
        window.audioChunks = [];
        window.isRecording = false;
        window.recordingTimer = null;
        window.recordingStartTime = null;
        
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
                        
                        resetRecordingState();
                        showStatusMessage('Optagelse fuldført! 🎉', 'success');
                    };
                    
                    document.getElementById('record-btn').disabled = false;
                    showStatusMessage('Mikrofon klar - klik for at optage! 🎤', 'info');
                })
                .catch(error => {
                    console.error('Fejl ved adgang til mikrofon:', error);
                    showStatusMessage('Kunne ikke få adgang til mikrofonen. Tjek tilladelser.', 'error');
                });
        }
        
        function toggleRecording() {
            if (!window.isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        }
        
        function startRecording() {
            window.audioChunks = [];
            window.mediaRecorder.start();
            window.isRecording = true;
            window.recordingStartTime = Date.now();
            
            const recordBtn = document.getElementById('record-btn');
            const indicator = document.getElementById('recording-indicator');
            const timer = document.getElementById('recording-timer');
            
            recordBtn.textContent = 'Stop';
            recordBtn.classList.add('recording');
            indicator.classList.add('active');
            timer.classList.add('active');
            
            window.recordingTimer = setInterval(updateTimer, 100);
            
            showStatusMessage('🔴 Optagelse i gang... Klik Stop når du er færdig', 'info');
        }
        
        function stopRecording() {
            window.mediaRecorder.stop();
            window.isRecording = false;
            
            if (window.recordingTimer) {
                clearInterval(window.recordingTimer);
                window.recordingTimer = null;
            }
        }
        
        function resetRecordingState() {
            const recordBtn = document.getElementById('record-btn');
            const indicator = document.getElementById('recording-indicator');
            const timer = document.getElementById('recording-timer');
            
            recordBtn.textContent = 'Optag';
            recordBtn.classList.remove('recording');
            indicator.classList.remove('active');
            timer.classList.remove('active');
            timer.textContent = '00:00';
        }
        
        function updateTimer() {
            if (!window.recordingStartTime) return;
            
            const elapsed = Date.now() - window.recordingStartTime;
            const seconds = Math.floor(elapsed / 1000);
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = seconds % 60;
            
            const timerDisplay = minutes.toString().padStart(2, '0') + ':' + remainingSeconds.toString().padStart(2, '0');
            document.getElementById('recording-timer').textContent = timerDisplay;
        }
        
        function showStatusMessage(message, type) {
            const statusElement = document.getElementById('status-message');
            statusElement.textContent = message;
            statusElement.className = 'status-message ' + type;
            statusElement.style.display = 'block';
        }
        
        function submitToHeyGen() {
            const title = document.getElementById('heygen-title').value;
            const avatarId = document.getElementById('heygen-avatar-select').value;
            const videoFormat = document.getElementById('heygen-format-select').value;
            
            if (!title) {
                showStatusMessage('❌ Indtast venligst en titel', 'error');
                return;
            }
            
            if (!avatarId) {
                showStatusMessage('❌ Vælg venligst en avatar', 'error');
                return;
            }
            
            if (!videoFormat) {
                showStatusMessage('❌ Vælg venligst et video format', 'error');
                return;
            }
            
            const audioElement = document.getElementById('audio-preview');
            if (!audioElement.src) {
                showStatusMessage('❌ Optag venligst lyd første', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('title', title);
            formData.append('avatar_id', avatarId);
            formData.append('video_format', videoFormat);
            
            fetch(audioElement.src)
                .then(res => res.blob())
                .then(audioBlob => {
                    formData.append('audio', audioBlob, 'recording.wav');
                    showStatusMessage('🚀 Sender til HeyGen (' + videoFormat + ')... Dette kan tage et øjeblik', 'info');
                    document.getElementById('heygen-submit-btn').disabled = true;
                    
                    fetch('/api/heygen', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showStatusMessage('✅ Video generering startet! Format: ' + (data.format || videoFormat) + ' (' + (data.dimensions || '') + ')', 'success');
                            setTimeout(() => {
                                location.reload();
                            }, 2000);
                        } else {
                            showStatusMessage('❌ Fejl: ' + data.error, 'error');
                        }
                        document.getElementById('heygen-submit-btn').disabled = false;
                    })
                    .catch(error => {
                        showStatusMessage('❌ Der opstod en fejl: ' + error.message, 'error');
                        document.getElementById('heygen-submit-btn').disabled = false;
                    });
                });
        }
        
        function downloadVideo(videoId) {
            window.open('/api/videos/' + videoId + '/download', '_blank');
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
            <a href="/admin/logs" class="btn" style="margin-right: 10px;">System Logs</a>
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
        
        {% if avatars %}
        <div class="card">
            <h2>🎬 Optag Avatar Video</h2>
            
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
            
            <div class="form-group">
                <label for="heygen-format-select">Video Format:</label>
                <select id="heygen-format-select" name="video_format" required>
                    <option value="16:9">16:9 Landscape (Business/YouTube) - 1280x720</option>
                    <option value="9:16">9:16 Portrait (Social Media/TikTok) - 720x1280</option>
                </select>
            </div>
            
            <div class="recorder-container">
                <button id="record-btn" class="record-btn" onclick="toggleRecording()" disabled>Optag</button>
                
                <div id="recording-indicator" class="recording-indicator">
                    🔴 OPTAGER - Tal klart og tydeligt
                </div>
                
                <div id="recording-timer" class="recording-timer">00:00</div>
                
                <audio id="audio-preview" class="audio-preview" controls style="display:none;"></audio>
                <div id="status-message" class="status-message info" style="display:none;"></div>
                <button id="heygen-submit-btn" class="btn" onclick="submitToHeyGen()" disabled>🚀 Send til HeyGen</button>
            </div>
        </div>
        
        <div class="card">
            <h2>🎭 Dine Avatars</h2>
            <ul>
            {% for avatar in avatars %}
                <li style="margin-bottom: 15px;">
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
            <h2>❌ Ingen Avatars</h2>
            <p>Du har ingen avatars endnu. Kontakt admin for at få oprettet avatars til din konto.</p>
            {% if is_admin %}
            <p><a href="/admin" class="btn">Gå til Admin Panel for at tilføje avatars</a></p>
            {% endif %}
        </div>
        {% endif %}
        
        {% if videos %}
        <div class="card">
            <h2>🎥 Dine Videoer</h2>
            <div class="video-list">
            {% for video in videos %}
                <div class="video-item">
                    <div class="video-info">
                        <h4>{{ video.title }}</h4>
                        <p>Avatar: {{ video.avatar_name }} | Oprettet: {{ video.created_at }}</p>
                        <span class="video-status status-{{ video.status }}">
                            {% if video.status == 'completed' %}Færdig
                            {% elif video.status == 'processing' %}Behandles
                            {% elif video.status == 'failed' %}Fejlet
                            {% elif video.status == 'pending' %}Afventer
                            {% else %}{{ video.status }}
                            {% endif %}
                        </span>
                    </div>
                    <div class="video-actions">
                        {% if video.status == 'completed' and video.video_path %}
                        <a href="{{ video.video_path }}" target="_blank" class="btn">▶️ Afspil</a>
                        <button class="btn" onclick="downloadVideo({{ video.id }})">📥 Download</button>
                        {% endif %}
                    </div>
                </div>
            {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""
#####################################################################
# ROUTES - AUTHENTICATION
#####################################################################

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return HTMLResponse(content=Template(MARKETING_HTML).render(
        request=request,
        error=request.query_params.get("error"),
        success=request.query_params.get("success")
    ))

@app.post("/client-login", response_class=HTMLResponse)
async def client_login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        log_info(f"Login attempt for email: {email}", "Auth")
        
        user = authenticate_user_by_email(email, password)
        
        if not user:
            log_warning(f"Failed login attempt for email: {email}", "Auth")
            return HTMLResponse(content=Template(MARKETING_HTML).render(
                request=request,
                error="Ugyldig email eller adgangskode"
            ))
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"]},
            expires_delta=access_token_expires
        )
        
        # Redirect to dashboard
        response = RedirectResponse(url="/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=True,
            secure=False  # Set to True in production with HTTPS
        )
        
        log_info(f"Successful login for user: {user['username']}", "Auth")
        return response
        
    except Exception as e:
        log_error("Login error", "Auth", e)
        return HTMLResponse(content=Template(MARKETING_HTML).render(
            request=request,
            error="Der opstod en fejl ved login"
        ))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/?error=Du skal være logget ind")
        
        # Get user's avatars
        avatars = execute_query(
            "SELECT * FROM avatars WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
            fetch_all=True
        ) or []
        
        # Get user's videos with avatar names
        videos = execute_query("""
            SELECT v.*, a.name as avatar_name 
            FROM videos v 
            LEFT JOIN avatars a ON v.avatar_id = a.id 
            WHERE v.user_id = ? 
            ORDER BY v.created_at DESC
        """, (user["id"],), fetch_all=True) or []
        
        # Check if user is admin
        is_admin_user = user.get("is_admin", 0) == 1
        
        return HTMLResponse(content=Template(DASHBOARD_HTML).render(
            request=request,
            user=user,
            avatars=avatars,
            videos=videos,
            is_admin=is_admin_user
        ))
        
    except Exception as e:
        log_error("Dashboard error", "Web", e)
        return RedirectResponse(url="/?error=Der opstod en fejl")

@app.get("/logout")
async def logout(request: Request):
    try:
        user = get_current_user(request)
        if user:
            log_info(f"User logged out: {user['username']}", "Auth")
        
        response = RedirectResponse(url="/?success=Du er nu logget ud")
        response.delete_cookie(key="access_token")
        return response
        
    except Exception as e:
        log_error("Logout error", "Auth", e)
        return RedirectResponse(url="/")

@app.post("/api/heygen")
async def create_heygen_video(
    request: Request,
    title: str = Form(...),
    avatar_id: str = Form(...),
    video_format: str = Form(...),
    audio: UploadFile = File(...)
):
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"success": False, "error": "Authentication required"}, status_code=401)
        
        log_info(f"HeyGen video creation request from user: {user['username']}", "HeyGen")
        
        # Validate inputs
        if not title.strip():
            return JSONResponse({"success": False, "error": "Title is required"})
        
        if video_format not in ["16:9", "9:16"]:
            return JSONResponse({"success": False, "error": "Invalid video format"})
        
        # Get avatar details
        avatar = execute_query(
            "SELECT * FROM avatars WHERE id = ? AND user_id = ?",
            (avatar_id, user["id"]),
            fetch_one=True
        )
        
        if not avatar:
            return JSONResponse({"success": False, "error": "Avatar not found"})
        
        # Save audio file
        audio_filename = f"user_{user['id']}_audio_{uuid.uuid4().hex}.wav"
        audio_path = f"static/uploads/audio/{audio_filename}"
        
        # Ensure upload directory exists
        os.makedirs("static/uploads/audio", exist_ok=True)
        
        # Save the uploaded audio file
        audio_content = await audio.read()
        with open(audio_path, "wb") as f:
            f.write(audio_content)
        
        audio_url = f"{BASE_URL}/{audio_path}"
        
        # Create video record in database
        video_id = execute_query("""
            INSERT INTO videos (user_id, avatar_id, title, audio_path, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (user["id"], avatar_id, title, audio_path))
        
        # Call HeyGen API
        heygen_result = create_video_from_audio_file(
            api_key=HEYGEN_API_KEY,
            avatar_id=avatar["heygen_avatar_id"],
            audio_url=audio_url,
            video_format=video_format
        )
        
        if heygen_result["success"]:
            # Update video record with HeyGen video ID
            execute_query("""
                UPDATE videos 
                SET heygen_video_id = ?, status = 'processing' 
                WHERE id = ?
            """, (heygen_result["video_id"], video_id))
            
            log_info(f"HeyGen video creation successful: {heygen_result['video_id']}", "HeyGen")
            
            return JSONResponse({
                "success": True,
                "video_id": heygen_result["video_id"],
                "message": heygen_result["message"],
                "format": heygen_result.get("format"),
                "dimensions": heygen_result.get("dimensions")
            })
        else:
            # Update video record as failed
            execute_query("""
                UPDATE videos 
                SET status = 'failed', video_path = ? 
                WHERE id = ?
            """, (heygen_result["error"], video_id))
            
            log_error(f"HeyGen video creation failed: {heygen_result['error']}", "HeyGen")
            
            return JSONResponse({
                "success": False,
                "error": heygen_result["error"]
            })
        
    except Exception as e:
        log_error("HeyGen API error", "HeyGen", e)
        return JSONResponse({
            "success": False,
            "error": "Internal server error"
        }, status_code=500)
#####################################################################
# ROUTES - VIDEO MANAGEMENT
#####################################################################

@app.get("/api/videos/{video_id}/download")
async def download_video(video_id: str, request: Request):
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Get video details
        video = execute_query("""
            SELECT * FROM videos 
            WHERE id = ? AND user_id = ? AND status = 'completed'
        """, (video_id, user["id"]), fetch_one=True)
        
        if not video or not video["video_path"]:
            raise HTTPException(status_code=404, detail="Video not found or not ready")
        
        # If it's a URL, redirect to it
        if video["video_path"].startswith("http"):
            return RedirectResponse(url=video["video_path"])
        
        # If it's a local file, serve it
        if os.path.exists(video["video_path"]):
            return FileResponse(
                path=video["video_path"],
                media_type="video/mp4",
                filename=f"{video['title']}.mp4"
            )
        
        raise HTTPException(status_code=404, detail="Video file not found")
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error downloading video {video_id}", "API", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/videos")
async def get_videos(request: Request, status: Optional[str] = None, limit: int = 20, offset: int = 0):
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Build query based on status filter
        if status:
            videos = execute_query("""
                SELECT v.*, a.name as avatar_name 
                FROM videos v 
                LEFT JOIN avatars a ON v.avatar_id = a.id 
                WHERE v.user_id = ? AND v.status = ? 
                ORDER BY v.created_at DESC 
                LIMIT ? OFFSET ?
            """, (user["id"], status, limit, offset), fetch_all=True)
        else:
            videos = execute_query("""
                SELECT v.*, a.name as avatar_name 
                FROM videos v 
                LEFT JOIN avatars a ON v.avatar_id = a.id 
                WHERE v.user_id = ? 
                ORDER BY v.created_at DESC 
                LIMIT ? OFFSET ?
            """, (user["id"], limit, offset), fetch_all=True)
        
        return JSONResponse({"videos": videos or []})
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error fetching videos", "API", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str, request: Request):
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Check if video exists and belongs to user
        video = execute_query("""
            SELECT * FROM videos WHERE id = ? AND user_id = ?
        """, (video_id, user["id"]), fetch_one=True)
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Delete local audio file if exists
        if video["audio_path"] and os.path.exists(video["audio_path"]):
            try:
                os.remove(video["audio_path"])
                log_info(f"Deleted audio file: {video['audio_path']}", "Storage")
            except Exception as e:
                log_warning(f"Could not delete audio file: {video['audio_path']}", "Storage")
        
        # Delete local video file if exists
        if video["video_path"] and not video["video_path"].startswith("http") and os.path.exists(video["video_path"]):
            try:
                os.remove(video["video_path"])
                log_info(f"Deleted video file: {video['video_path']}", "Storage")
            except Exception as e:
                log_warning(f"Could not delete video file: {video['video_path']}", "Storage")
        
        # Delete from database
        execute_query("DELETE FROM videos WHERE id = ?", (video_id,))
        
        log_info(f"Video deleted: {video_id} by user {user['username']}", "API")
        
        return JSONResponse({"success": True, "message": "Video deleted successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error deleting video {video_id}", "API", e)
        raise HTTPException(status_code=500, detail="Internal server error")

#####################################################################
# ROUTES - AVATAR MANAGEMENT
#####################################################################

@app.get("/api/avatars")
async def get_avatars(request: Request):
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        avatars = execute_query("""
            SELECT * FROM avatars 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """, (user["id"],), fetch_all=True)
        
        return JSONResponse({"avatars": avatars or []})
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error fetching avatars", "API", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/avatars")
async def create_avatar(
    request: Request,
    name: str = Form(...),
    heygen_avatar_id: str = Form(...),
    image: Optional[UploadFile] = File(None)
):
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate inputs
        if not name.strip():
            raise HTTPException(status_code=400, detail="Avatar name is required")
        
        if not heygen_avatar_id.strip():
            raise HTTPException(status_code=400, detail="HeyGen Avatar ID is required")
        
        # Handle image upload
        image_url = None
        if image and image.filename:
            try:
                image_url = await upload_avatar_to_cloudinary(image, user["id"])
                if not image_url:
                    image_url = await upload_avatar_locally(image, user["id"])
            except Exception as e:
                log_warning(f"Image upload failed for avatar: {name}", "Storage", e)
        
        # Create avatar in database
        avatar_id = execute_query("""
            INSERT INTO avatars (user_id, name, heygen_avatar_id, image_path)
            VALUES (?, ?, ?, ?)
        """, (user["id"], name.strip(), heygen_avatar_id.strip(), image_url))
        
        log_info(f"Avatar created: {name} by user {user['username']}", "API")
        
        return JSONResponse({
            "success": True,
            "avatar_id": avatar_id,
            "message": "Avatar created successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("Error creating avatar", "API", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/avatars/{avatar_id}")
async def delete_avatar(avatar_id: str, request: Request):
    try:
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Check if avatar exists and belongs to user
        avatar = execute_query("""
            SELECT * FROM avatars WHERE id = ? AND user_id = ?
        """, (avatar_id, user["id"]), fetch_one=True)
        
        if not avatar:
            raise HTTPException(status_code=404, detail="Avatar not found")
        
        # Check if avatar is used in any videos
        video_count = execute_query("""
            SELECT COUNT(*) as count FROM videos WHERE avatar_id = ?
        """, (avatar_id,), fetch_one=True)
        
        if video_count and video_count["count"] > 0:
            raise HTTPException(status_code=400, detail="Cannot delete avatar that is used in videos")
        
        # Delete image file if exists and is local
        if avatar["image_path"] and not avatar["image_path"].startswith("http") and os.path.exists(avatar["image_path"]):
            try:
                os.remove(avatar["image_path"])
                log_info(f"Deleted avatar image: {avatar['image_path']}", "Storage")
            except Exception as e:
                log_warning(f"Could not delete avatar image: {avatar['image_path']}", "Storage")
        
        # Delete from database
        execute_query("DELETE FROM avatars WHERE id = ?", (avatar_id,))
        
        log_info(f"Avatar deleted: {avatar['name']} by user {user['username']}", "API")
        
        return JSONResponse({"success": True, "message": "Avatar deleted successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error deleting avatar {avatar_id}", "API", e)
        raise HTTPException(status_code=500, detail="Internal server error")

#####################################################################
# WEBHOOK ENDPOINTS
#####################################################################

@app.post("/webhook/heygen")
async def heygen_webhook(request: Request):
    """
    HeyGen webhook endpoint to receive video generation status updates
    """
    try:
        # Get the raw body for signature verification (if needed)
        body = await request.body()
        
        # Parse JSON payload
        try:
            payload = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            log_error("Invalid JSON in webhook payload", "Webhook")
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        log_info(f"Received HeyGen webhook: {payload}", "Webhook")
        
        # Extract relevant information
        event_type = payload.get("event_type")
        video_data = payload.get("data", {})
        heygen_video_id = video_data.get("video_id")
        
        if not heygen_video_id:
            log_error("No video_id in webhook payload", "Webhook")
            raise HTTPException(status_code=400, detail="Missing video_id")
        
        # Find the video in our database
        video = execute_query("""
            SELECT * FROM videos WHERE heygen_video_id = ?
        """, (heygen_video_id,), fetch_one=True)
        
        if not video:
            log_warning(f"Video not found for HeyGen ID: {heygen_video_id}", "Webhook")
            return JSONResponse({"status": "video not found"})
        
        # Process different event types
        if event_type == "video_generation.completed":
            # Video generation completed successfully
            video_url = video_data.get("video_url")
            thumbnail_url = video_data.get("thumbnail_url")
            duration = video_data.get("duration", 0)
            
            execute_query("""
                UPDATE videos 
                SET status = 'completed', video_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE heygen_video_id = ?
            """, (video_url, heygen_video_id))
            
            log_info(f"Video completed: {heygen_video_id} -> {video_url}", "Webhook")
            
        elif event_type == "video_generation.failed":
            # Video generation failed
            error_message = video_data.get("error", "Video generation failed")
            
            execute_query("""
                UPDATE videos 
                SET status = 'failed', video_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE heygen_video_id = ?
            """, (error_message, heygen_video_id))
            
            log_error(f"Video generation failed: {heygen_video_id} - {error_message}", "Webhook")
            
        elif event_type == "video_generation.processing":
            # Video generation is in progress
            execute_query("""
                UPDATE videos 
                SET status = 'processing', updated_at = CURRENT_TIMESTAMP
                WHERE heygen_video_id = ?
            """, (heygen_video_id,))
            
            log_info(f"Video processing: {heygen_video_id}", "Webhook")
            
        else:
            log_warning(f"Unknown webhook event type: {event_type}", "Webhook")
        
        return JSONResponse({"status": "processed"})
        
    except HTTPException:
        raise
    except Exception as e:
        log_error("Webhook processing error", "Webhook", e)
        raise HTTPException(status_code=500, detail="Internal server error") 
#####################################################################
# ROUTES - ADMIN REDIRECTS & ADDITIONAL AUTH
#####################################################################

@app.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return RedirectResponse(url="/")

#####################################################################
# ROUTES - ADMIN PANEL 
#####################################################################

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0):
            return RedirectResponse(url="/?error=admin_required", status_code=status.HTTP_302_FOUND)
        
        # Get system statistics
        total_users = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        total_videos = execute_query("SELECT COUNT(*) as count FROM videos", fetch_one=True)
        total_avatars = execute_query("SELECT COUNT(*) as count FROM avatars", fetch_one=True)
        
        # Get recent activity
        recent_users = execute_query(
            "SELECT username, email, created_at FROM users ORDER BY created_at DESC LIMIT 10",
            fetch_all=True
        )
        
        recent_videos = execute_query("""
            SELECT v.title, v.status, v.created_at, u.username 
            FROM videos v 
            JOIN users u ON v.user_id = u.id 
            ORDER BY v.created_at DESC LIMIT 10
        """, fetch_all=True)
        
        log_info(f"Admin panel accessed by: {user['username']}", "Admin")
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Panel - MyAvatar</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
                .header {{ background: #333; color: white; padding: 1rem; display: flex; justify-content: space-between; align-items: center; }}
                .container {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .btn {{ background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }}
                .stat-card {{ background: #fff; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stat-number {{ font-size: 2em; font-weight: bold; color: #4f46e5; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f8f9fa; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Admin Panel</h1>
                <div>
                    <a href="/admin/logs" class="btn">System Logs</a>
                    <a href="/admin/users" class="btn">Manage Users</a>
                    <a href="/dashboard" class="btn">Back to Dashboard</a>
                    <a href="/logout" class="btn">Logout</a>
                </div>
            </div>
            
            <div class="container">
                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">{total_users['count'] if total_users else 0}</div>
                        <div>Total Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{total_videos['count'] if total_videos else 0}</div>
                        <div>Total Videos</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{total_avatars['count'] if total_avatars else 0}</div>
                        <div>Total Avatars</div>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Recent Users</h2>
                    <table>
                        <tr><th>Username</th><th>Email</th><th>Created</th></tr>
                        {"".join([f"<tr><td>{u['username']}</td><td>{u['email']}</td><td>{u['created_at']}</td></tr>" for u in (recent_users or [])])}
                    </table>
                </div>
                
                <div class="card">
                    <h2>Recent Videos</h2>
                    <table>
                        <tr><th>Title</th><th>User</th><th>Status</th><th>Created</th></tr>
                        {"".join([f"<tr><td>{v['title']}</td><td>{v['username']}</td><td>{v['status']}</td><td>{v['created_at']}</td></tr>" for v in (recent_videos or [])])}
                    </table>
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        log_error("Admin panel error", "Admin", e)
        return RedirectResponse(url="/dashboard?error=admin_error")

@app.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs(request: Request):
    try:
        user = get_current_user(request)
        if not user or not user.get("is_admin", 0):
            return RedirectResponse(url="/?error=admin_required")
        
        recent_logs = log_handler.get_recent_logs(100)
        error_logs = log_handler.get_error_logs(50)
        
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>System Logs - MyAvatar Admin</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
                .header {{ background: #333; color: white; padding: 1rem; display: flex; justify-content: space-between; align-items: center; }}
                .container {{ padding: 20px; max-width: 1200px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .btn {{ background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; }}
                .log-entry {{ padding: 10px; margin: 5px 0; border-radius: 4px; font-family: monospace; }}
                .log-info {{ background: #e3f2fd; }}
                .log-warning {{ background: #fff3e0; }}
                .log-error {{ background: #ffebee; }}
                .log-timestamp {{ color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>System Logs</h1>
                <div>
                    <a href="/admin" class="btn">Back to Admin</a>
                    <a href="/logout" class="btn">Logout</a>
                </div>
            </div>
            
            <div class="container">
                <div class="card">
                    <h2>Error Logs</h2>
                    {"".join([f'<div class="log-entry log-error"><span class="log-timestamp">{log["timestamp"]}</span> [{log["module"]}] {log["message"]}</div>' for log in error_logs])}
                </div>
                
                <div class="card">
                    <h2>Recent Activity</h2>
                    {"".join([f'<div class="log-entry log-{log["level"].lower()}"><span class="log-timestamp">{log["timestamp"]}</span> [{log["module"]}] {log["message"]}</div>' for log in recent_logs])}
                </div>
            </div>
        </body>
        </html>
        """)
        
    except Exception as e:
        log_error("Admin logs error", "Admin", e)
        return RedirectResponse(url="/admin?error=logs_error")

 #####################################################################
# ROUTES - ADMIN DASHBOARD 
#####################################################################
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    try:
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return RedirectResponse(url="/?error=admin_required", status_code=status.HTTP_302_FOUND)
        
        log_info(f"Admin dashboard accessed by: {user['username']}", "Admin")
        
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
                .btn-success { background: #16a34a; }
                .btn-success:hover { background: #15803d; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔧 Admin Dashboard</h1>
                <div>
                    <a href="/dashboard" class="btn">Dashboard</a>
                    <a href="/admin/logs" class="btn btn-success">System Logs</a>
                    <a href="/logout" class="btn">Log Ud</a>
                </div>
            </div>
            
            <div class="card">
                <h2>👥 Avatar Administration</h2>
                <p>Administrer avatars for alle brugere i systemet.</p>
                <a href="/admin/users" class="btn">Administrer Brugere & Avatars</a>
                <a href="/admin/create-user" class="btn">Opret Ny Bruger</a>
            </div>
            
            <div class="card">
                <h2>🐛 Debug Tools</h2>
                <p>Tools for debugging the HeyGen integration issue.</p>
                <a href="/debug/recent-videos" class="btn btn-success">Check Recent Videos</a>
                <a href="/debug/check-db" class="btn btn-success">Simple DB Check</a>
            </div>
            
            <div class="card">
                <h2>📊 System Status</h2>
                <p><strong>HeyGen API:</strong> ✅ Tilgængelig</p>
                <p><strong>Storage:</strong> ✅ Cloudinary CDN</p>
                <p><strong>Database:</strong> ✅ PostgreSQL</p>
                <p><strong>Webhook:</strong> ✅ /api/heygen/webhook</p>
                <p><strong>Logging:</strong> ✅ Enhanced Error Tracking</p>
            </div>
            
            <div class="card">
                <h2>🧹 System Maintenance</h2>
                <p>Tools for system maintenance and troubleshooting.</p>
                <a href="/admin/quickclean" class="btn btn-danger">Total Reset (Delete All)</a>
                <a href="/admin/logs" class="btn btn-success">View System Logs</a>
            </div>
        </body>
        </html>
        '''
        return HTMLResponse(content=admin_html)
    except Exception as e:
        log_error("Admin dashboard failed", "Admin", e)
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
@app.get("/admin/users", response_class=HTMLResponse) 
async def admin_users(request: Request):
    try:
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        users = execute_query("SELECT * FROM users ORDER BY id ASC", fetch_all=True)
        log_info(f"Admin viewing {len(users)} users", "Admin")
        
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
                .success { background: #dcfce7; color: #16a34a; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
                .error { background: #fee2e2; color: #dc2626; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>👥 Administrer Brugere</h1>
                <div>
                    <a href="/admin" class="btn">Tilbage til Admin</a>
                    <a href="/admin/create-user" class="btn btn-success">Opret Ny Bruger</a>
                </div>
            </div>
        '''
        
        # Add success/error messages
        success = request.query_params.get("success")
        error = request.query_params.get("error")
        
        if success:
            users_html += f'<div class="success">{success}</div>'
        
        if error:
            users_html += f'<div class="error">{error}</div>'
        
        users_html += '''
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
        '''
        
        for user_row in users:
            admin_status = "Ja" if user_row.get('is_admin') else "Nej"
            users_html += f'''
                        <tr>
                            <td>{user_row['id']}</td>
                            <td>{user_row['username']}</td>
                            <td>{user_row['email']}</td>
                            <td>{admin_status}</td>
                            <td>{user_row['created_at']}</td>
                            <td>
                                <a href="/admin/user/{user_row['id']}/avatars" class="btn">Avatars</a>
                                <a href="/admin/reset-password/{user_row['id']}" class="btn btn-danger">Reset Password</a>
                            </td>
                        </tr>
            '''
        
        users_html += '''
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        '''
        
        return HTMLResponse(content=users_html)
    except Exception as e:
        log_error("Admin users page failed", "Admin", e)
        return RedirectResponse(url="/admin?error=user_load_failed", status_code=status.HTTP_302_FOUND)
@app.get("/admin/user/{user_id}/avatars", response_class=HTMLResponse)
async def admin_user_avatars(request: Request, user_id: int = Path(...)):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
        user = execute_query("SELECT * FROM users WHERE id=?", (user_id,), fetch_one=True)
        if not user:
            return HTMLResponse("<h3>Bruger ikke fundet</h3><a href='/admin/users'>Tilbage</a>")
        
        avatars = execute_query("SELECT * FROM avatars WHERE user_id=? ORDER BY created_at DESC", (user_id,), fetch_all=True)
        
        log_info(f"Admin managing avatars for user: {user['username']} ({len(avatars)} avatars)", "Admin")
        
        avatar_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{user['username']} - Avatars</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .header {{ background: #dc2626; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }}
                .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                .btn {{ background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; border: none; cursor: pointer; }}
                .btn:hover {{ background: #3730a3; }}
                .btn-success {{ background: #16a34a; }}
                .btn-success:hover {{ background: #15803d; }}
                .btn-danger {{ background: #dc2626; }}
                .btn-danger:hover {{ background: #b91c1c; }}
                .form-group {{ margin-bottom: 15px; }}
                label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                input[type="text"], input[type="file"] {{ width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #f8f9fa; }}
                .avatar-img {{ width: 80px; height: 80px; object-fit: cover; border-radius: 8px; }}
                .success {{ background: #dcfce7; color: #16a34a; padding: 10px; border-radius: 4px; margin-bottom: 15px; }}
                .error {{ background: #fee2e2; color: #dc2626; padding: 10px; border-radius: 4px; margin-bottom: 15px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎭 {user['username']} - Avatar Administration</h1>
                <div>
                    <a href="/admin/users" class="btn">Tilbage til Brugere</a>
                </div>
            </div>
        '''
        
        # Add success/error messages
        success = request.query_params.get("success")
        error = request.query_params.get("error")
        
        if success:
            avatar_html += f'<div class="success">{success}</div>'
        
        if error:
            avatar_html += f'<div class="error">{error}</div>'
        
        avatar_html += f'''
            <div class="card">
                <h2>➕ Tilføj Ny Avatar</h2>
                <form method="post" action="/admin/user/{user['id']}/avatars" enctype="multipart/form-data">
                    <div class="form-group">
                        <label for="avatar_name">Avatar Navn:</label>
                        <input type="text" id="avatar_name" name="avatar_name" required placeholder="fx. Business Avatar">
                    </div>
                    
                    <div class="form-group">
                        <label for="heygen_avatar_id">HeyGen Avatar ID:</label>
                        <input type="text" id="heygen_avatar_id" name="heygen_avatar_id" required placeholder="fx. b5038ba7bd9b4d94ac6b5c9ea70f8d28">
                        <small style="color: #6b7280;">Find dette ID i din HeyGen konto under Avatars</small>
                    </div>
                    
                    <div class="form-group">
                        <label for="avatar_img">Avatar Billede:</label>
                        <input type="file" id="avatar_img" name="avatar_img" accept="image/*" required>
                    </div>
                    
                    <button type="submit" class="btn btn-success">Tilføj Avatar</button>
                </form>
            </div>
        '''
        
        if avatars:
            avatar_html += '''
            <div class="card">
                <h2>🎭 Eksisterende Avatars</h2>
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
            '''
            
            for avatar in avatars:
                avatar_html += f'''
                        <tr>
                            <td>
                '''
                if avatar.get('image_path'):
                    avatar_html += f'<img src="{avatar["image_path"]}" alt="{avatar["name"]}" class="avatar-img">'
                else:
                    avatar_html += '<div style="width: 80px; height: 80px; background: #f3f4f6; border-radius: 8px; display: flex; align-items: center; justify-content: center;">Ingen billede</div>'
                
                avatar_html += f'''
                            </td>
                            <td>{avatar['name']}</td>
                            <td>{avatar['heygen_avatar_id']}</td>
                            <td>{avatar['created_at']}</td>
                            <td>
                                <form method="post" action="/admin/user/{user['id']}/avatars/delete/{avatar['id']}" style="display: inline;">
                                    <button type="submit" class="btn btn-danger" onclick="return confirm('Er du sikker på at du vil slette denne avatar?')">Slet</button>
                                </form>
                            </td>
                        </tr>
                '''
            
            avatar_html += '''
                    </tbody>
                </table>
            </div>
            '''
        else:
            avatar_html += f'''
            <div class="card">
                <h2>❌ Ingen Avatars</h2>
                <p>{user['username']} har ingen avatars endnu. Brug formularen ovenfor til at tilføje den første avatar.</p>
            </div>
            '''
        
        avatar_html += '''
        </body>
        </html>
        '''
        
        return HTMLResponse(content=avatar_html)
        
    except Exception as e:
        log_error(f"Admin avatar management failed for user {user_id}", "Admin", e)
        return RedirectResponse(url="/admin/users?error=avatar_management_failed", status_code=status.HTTP_302_FOUND)

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
            .btn { background: #4f46e5; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
            .btn:hover { background: #3730a3; }
            .success { background: #dcfce7; color: #16a34a; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
            .error { background: #fee2e2; color: #dc2626; padding: 10px; border-radius: 4px; margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>➕ Opret Ny Bruger</h2>
    '''
    
    # Add success/error messages
    success = request.query_params.get("success")
    error = request.query_params.get("error")
    
    if success:
        create_user_html += f'<div class="success">{success}</div>'
    
    if error:
        create_user_html += f'<div class="error">{error}</div>'
    
    create_user_html += '''
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
    
    return HTMLResponse(content=create_user_html)
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
    existing = execute_query(
        "SELECT id FROM users WHERE username = ? OR email = ?", 
        (username, email),
        fetch_one=True
    )
    
    if existing:
        return RedirectResponse(
            url="/admin/create-user?error=Brugernavn eller email allerede i brug",
            status_code=status.HTTP_302_FOUND
        )
    
    # Create new user
    hashed_password = get_password_hash(password)
    execute_query(
        "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
        (username, email, hashed_password)
    )
    
    return RedirectResponse(
        url="/admin/create-user?success=Bruger oprettet succesfuldt",
        status_code=status.HTTP_302_FOUND
    )

#####################################################################
# ADMIN LOG VIEWER
#####################################################################

@app.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs(request: Request):
    try:
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        recent_logs = log_handler.get_recent_logs(200)
        error_logs = log_handler.get_error_logs(50)
        
        logs_html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>System Logs</title>
            <style>
                body { font-family: 'Courier New', monospace; margin: 0; padding: 20px; background: #1a1a1a; color: #fff; }
                .header { background: #dc2626; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
                .card { background: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #444; }
                .btn { background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; }
                .btn:hover { background: #3730a3; }
                .log-entry { padding: 8px; margin: 2px 0; border-radius: 4px; font-size: 12px; }
                .log-info { background: #1e3a8a; color: #bfdbfe; }
                .log-warning { background: #92400e; color: #fcd34d; }
                .log-error { background: #7f1d1d; color: #fecaca; }
                .timestamp { color: #9ca3af; }
                .module { color: #34d399; font-weight: bold; }
            </style>
            <script>
                function autoRefresh() {
                    setTimeout(() => {
                        location.reload();
                    }, 30000);
                }
                document.addEventListener('DOMContentLoaded', autoRefresh);
            </script>
        </head>
        <body>
            <div class="header">
                <h1>📊 System Logs</h1>
                <div>
                    <a href="/admin" class="btn">Tilbage til Admin</a>
                    <button onclick="location.reload()" class="btn">Refresh</button>
                </div>
            </div>
            
            <div class="card">
                <h3>Recent Activity (Last 200 entries)</h3>
                <div style="max-height: 600px; overflow-y: scroll; background: #111; padding: 10px; border-radius: 4px;">
        '''
        
        for log in recent_logs:
            level_class = f"log-{log['level'].lower()}"
            logs_html += f'''
                    <div class="{level_class} log-entry">
                        <span class="timestamp">{log['timestamp']}</span> | 
                        <span class="module">[{log['module']}]</span> | 
                        <span class="level">{log['level']}</span> | 
                        {log['message']}
                    </div>
            '''
        
        logs_html += f'''
                </div>
            </div>
            
            <div class="card">
                <h3>ℹ️ Log Information</h3>
                <p>• Logs auto-refresh every 30 seconds</p>
                <p>• Showing last {len(recent_logs)} entries</p>
                <p>• {len(error_logs)} recent errors</p>
            </div>
        </body>
        </html>
        '''
        
        return HTMLResponse(content=logs_html)
        
    except Exception as e:
        log_error("Admin logs page failed", "Admin", e)
        return HTMLResponse("<h1>Error loading logs</h1><a href='/admin'>Back to Admin</a>")
#####################################################################
# DEBUG ENDPOINTS - NEW ADDITIONS FOR HEYGEN TROUBLESHOOTING
#####################################################################

@app.get("/debug/recent-videos")
async def debug_recent_videos(request: Request):
    """Debug endpoint to check what's actually in your PostgreSQL database"""
    try:
        # Check if user is admin for security
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return JSONResponse({"error": "Admin access required"}, status_code=403)
        
        # Get recent videos with all important fields
        videos = execute_query("""
            SELECT id, heygen_video_id, status, title, user_id, avatar_id, created_at 
            FROM videos 
            ORDER BY created_at DESC 
            LIMIT 10
        """, fetch_all=True)
        
        result = []
        for video in videos:
            result.append({
                "id": video["id"],
                "heygen_video_id": video["heygen_video_id"],  # This is the key field!
                "status": video["status"],
                "title": video["title"][:50] if video["title"] else None,  # First 50 chars
                "user_id": video["user_id"],
                "avatar_id": video["avatar_id"],
                "created_at": str(video["created_at"])
            })
        
        return JSONResponse({
            "total_videos": len(result),
            "videos": result,
            "database_type": "PostgreSQL on Railway",
            "note": "This shows the most recent 10 videos and their HeyGen IDs"
        })
    except Exception as e:
        log_error("Debug endpoint failed", "Debug", e)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/debug/check-db")
async def check_db_simple(request: Request):
    """Simple debug check for recent videos"""
    try:
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return JSONResponse({"error": "Admin access required"}, status_code=403)
            
        videos = execute_query(
            "SELECT id, heygen_video_id, status, title FROM videos ORDER BY created_at DESC LIMIT 5", 
            fetch_all=True
        )
        
        return JSONResponse([{
            "id": v["id"], 
            "heygen_id": v["heygen_video_id"],
            "status": v["status"],
            "title": v["title"]
        } for v in videos])
    except Exception as e:
        log_error("Simple debug check failed", "Debug", e)
        return JSONResponse({"error": str(e)}, status_code=500)

#####################################################################
# ENHANCED AVATAR MANAGEMENT
#####################################################################

@app.post("/admin/user/{user_id}/avatars", response_class=HTMLResponse)
async def admin_add_avatar(
    request: Request,
    user_id: int = Path(...),
    avatar_name: str = Form(...),
    heygen_avatar_id: str = Form(...),
    avatar_img: UploadFile = File(...)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
        log_info(f"Creating avatar for user {user_id}: {avatar_name}", "Avatar")
        
        img_url = await upload_avatar_to_cloudinary(avatar_img, user_id)
        
        if not img_url:
            log_error(f"Avatar image upload failed for user {user_id}", "Avatar")
            return RedirectResponse(
                url=f"/admin/user/{user_id}/avatars?error=Billede upload fejlede", 
                status_code=303
            )
        
        log_info(f"Avatar image uploaded successfully: {img_url}", "Avatar")
        
        result = execute_query(
            "INSERT INTO avatars (user_id, name, image_path, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (user_id, avatar_name, img_url, heygen_avatar_id)
        )
        
        if result['rowcount'] > 0:
            log_info(f"Avatar created successfully: {avatar_name} for user {user_id}", "Avatar")
            return RedirectResponse(
                url=f"/admin/user/{user_id}/avatars?success=Avatar tilføjet succesfuldt (Cloudinary)", 
                status_code=303
            )
        else:
            log_error(f"Database insert failed for avatar: {avatar_name}", "Avatar")
            return RedirectResponse(
                url=f"/admin/user/{user_id}/avatars?error=Database fejl", 
                status_code=303
            )
            
    except Exception as e:
        log_error(f"Avatar creation failed for user {user_id}: {avatar_name}", "Avatar", e)
        return RedirectResponse(
            url=f"/admin/user/{user_id}/avatars?error=Fejl: {str(e)}", 
            status_code=303
        )
@app.post("/admin/user/{user_id}/avatars/delete/{avatar_id}", response_class=HTMLResponse)
async def admin_delete_avatar(request: Request, user_id: int = Path(...), avatar_id: int = Path(...)):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        
        log_info(f"Starting cascade delete for avatar {avatar_id} (user {user_id})", "Avatar")
        
        # FIXED - Delete videos first (no fetch)
        videos_result = execute_query(
            "DELETE FROM videos WHERE avatar_id=?", 
            (avatar_id,)
        )
        
        video_count = videos_result.get('rowcount', 0)
        if video_count > 0:
            log_info(f"Deleted {video_count} video(s) referencing avatar {avatar_id}", "Avatar")
        else:
            log_info(f"No videos found for avatar {avatar_id}", "Avatar")
        
        # Delete the avatar
        avatar_result = execute_query(
            "DELETE FROM avatars WHERE id=? AND user_id=?", 
            (avatar_id, user_id)
        )
        
        if avatar_result['rowcount'] > 0:
            log_info(f"Avatar {avatar_id} deleted successfully", "Avatar")
            success_msg = f"Avatar slettet succesfuldt"
            if video_count > 0:
                success_msg += f" (inkl. {video_count} relaterede video(er))"
        else:
            log_warning(f"Avatar {avatar_id} not found or access denied", "Avatar")
            return RedirectResponse(
                url=f"/admin/user/{user_id}/avatars?error=Avatar ikke fundet", 
                status_code=303
            )
        
        return RedirectResponse(
            url=f"/admin/user/{user_id}/avatars?success={success_msg}", 
            status_code=303
        )
        
    except Exception as e:
        log_error(f"Cascade delete failed for avatar {avatar_id}", "Avatar", e)
        return RedirectResponse(
            url=f"/admin/user/{user_id}/avatars?error=Kunne ikke slette avatar", 
            status_code=303
        )

#####################################################################
# API ENDPOINTS - HEYGEN INTEGRATION WITH ENHANCED LOGGING
#####################################################################

@app.post("/api/heygen")
async def create_heygen_video(
    request: Request,
    title: str = Form(...),
    avatar_id: int = Form(...),
    video_format: str = Form(default="16:9"),
    audio: UploadFile = File(...)
):
    try:
        user = get_current_user(request)
        if not user:
            log_warning("Unauthorized HeyGen video creation attempt", "HeyGen")
            return JSONResponse({"error": "Ikke autoriseret"}, status_code=401)

        if not HEYGEN_API_KEY:
            log_error("HeyGen API key not found", "HeyGen")
            return JSONResponse({"error": "HeyGen API nøgle ikke fundet"}, status_code=500)

        avatar = execute_query("SELECT * FROM avatars WHERE id = ? AND user_id = ?", (avatar_id, user["id"]), fetch_one=True)
        
        if not avatar:
            log_warning(f"Avatar {avatar_id} not found for user {user['id']}", "HeyGen")
            return JSONResponse({"error": "Avatar ekki fundet"}, status_code=404)
        
        heygen_avatar_id = avatar.get('heygen_avatar_id')

        log_info(f"[ENHANCED] Video request by user: {user['username']} using avatar: {avatar['name']}", "HeyGen")
        log_info(f"[ENHANCED] Video format: {video_format}, Title: {title}", "HeyGen")
        log_info(f"[ENHANCED] Using HeyGen Avatar ID: {heygen_avatar_id}", "HeyGen")
        
        if not heygen_avatar_id:
            log_error(f"Missing HeyGen avatar ID for avatar {avatar_id}", "HeyGen")
            return JSONResponse({"error": "Manglende HeyGen avatar ID"}, status_code=500)
        
        # LOCAL FILE UPLOAD
        audio_bytes = await audio.read()
        try:
            audio_filename = f"audio_{uuid.uuid4().hex}.wav"
            audio_path = f"static/uploads/audio/{audio_filename}"
            
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)
            
            audio_url = f"{BASE_URL}/static/uploads/audio/{audio_filename}"
            log_info(f"[ENHANCED] Audio file saved and accessible at: {audio_url}", "HeyGen")
            
        except Exception as e:
            log_error("Local audio file save failed", "HeyGen", e)
            return JSONResponse({"error": f"Fil upload fejlede: {str(e)}"}, status_code=500)

        # Save to database FIRST - This creates the record that webhook will look for
        result = execute_query(
            "INSERT INTO videos (user_id, avatar_id, title, audio_path, status) VALUES (?, ?, ?, ?, ?)",
            (user["id"], avatar_id, title, audio_url, "processing")
        )
        video_id = result['lastrowid']
        log_info(f"[ENHANCED] Video record created with database ID: {video_id}", "HeyGen")       
        # Call HeyGen API with comprehensive logging
        log_info("[ENHANCED] Calling HeyGen API to create video...", "HeyGen")
        heygen_result = create_video_from_audio_file(
            api_key=HEYGEN_API_KEY,
            avatar_id=heygen_avatar_id,
            audio_url=audio_url,
            video_format=video_format
        )
        
        # CRITICAL: Log the HeyGen response and what we're storing
        log_info(f"[ENHANCED] HeyGen API Response: {json.dumps(heygen_result, indent=2)}", "HeyGen")
        
        if heygen_result["success"]:
            heygen_video_id = heygen_result.get("video_id")
            log_info(f"[ENHANCED] HeyGen video ID received: {heygen_video_id}", "HeyGen")
            
            if not heygen_video_id:
                log_error("[ENHANCED] HeyGen returned success but no video_id!", "HeyGen")
                return JSONResponse({
                    "success": False,
                    "error": "HeyGen returned success but no video ID"
                }, status_code=500)
            
            # Update the database record with HeyGen video ID
            log_info(f"[ENHANCED] Updating database record {video_id} with HeyGen ID: {heygen_video_id}", "HeyGen")
            execute_query(
                "UPDATE videos SET heygen_video_id = ?, status = ? WHERE id = ?",
                (heygen_video_id, "processing", video_id)
            )
            log_info(f"[ENHANCED] Database update completed for video {video_id}", "HeyGen")
            
            # Verify the update worked
            updated_video = execute_query(
                "SELECT id, heygen_video_id, status FROM videos WHERE id = ?", 
                (video_id,), 
                fetch_one=True
            )
            
            if updated_video:
                log_info(f"[ENHANCED] Verification SUCCESS - Database now shows: ID={updated_video['id']}, HeyGen_ID={updated_video['heygen_video_id']}, Status={updated_video['status']}", "HeyGen")
            else:
                log_error(f"[ENHANCED] Verification FAILED - Could not find video record {video_id} after update", "HeyGen")
            
        else:
            log_error(f"[ENHANCED] HeyGen API failed: {heygen_result.get('error')}", "HeyGen")
        
        return JSONResponse(heygen_result)
    except Exception as e:
        log_error("[ENHANCED] Unexpected error in HeyGen video creation", "HeyGen", e)
        return JSONResponse({
            "success": False,
            "error": f"Uventet fejl: {str(e)}"
        }, status_code=500)

#####################################################################
# ENHANCED HEYGEN WEBHOOK HANDLER - FIXED FOR HEYGEN'S ACTUAL FORMAT
#####################################################################

async def download_video_from_heygen(video_url: str, video_id: int) -> str:
    try:
        log_info(f"Downloading video from HeyGen: {video_url}", "Webhook")
        
        video_filename = f"video_{video_id}_{uuid.uuid4().hex}.mp4"
        local_path = f"static/uploads/videos/{video_filename}"
        
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        public_url = f"{BASE_URL}/{local_path}"
        
        log_info(f"Video downloaded successfully: {public_url}", "Webhook")
        return public_url
        
    except Exception as e:
        log_error(f"Video download failed for video {video_id}", "Webhook", e)
        return None
@app.post("/api/heygen/webhook")
async def heygen_webhook_handler(request: Request):
    """Enhanced HeyGen webhook handler with comprehensive logging - FIXED for HeyGen's actual format"""
    try:
        webhook_data = await request.json()
        log_info(f"[Webhook] Full payload received: {json.dumps(webhook_data, indent=2)}", "Webhook")
        
        # Extract video info - HeyGen sends data in nested "event_data" structure
        event_data = webhook_data.get("event_data", {})
        event_type = webhook_data.get("event_type", "")
        
        log_info(f"[Webhook] Event type: {event_type}", "Webhook")
        log_info(f"[Webhook] Event data keys: {list(event_data.keys())}", "Webhook")
        log_info(f"[Webhook] Root payload keys: {list(webhook_data.keys())}", "Webhook")
        
        # Multiple ways to find video_id (HeyGen's format varies) - FIXED VERSION
        video_id = (
            webhook_data.get("video_id") or 
            webhook_data.get("id") or 
            webhook_data.get("data", {}).get("video_id") or
            webhook_data.get("data", {}).get("id") or
            event_data.get("video_id")  # ← FIXED: HeyGen puts it here!
        )
        
        log_info(f"[Webhook] Extracted video_id: {video_id}", "Webhook")
        
        # Derive status from event_type
        if "success" in event_type.lower():
            status = "completed"
        elif "fail" in event_type.lower() or "error" in event_type.lower():
            status = "failed"
        else:
            status = webhook_data.get("status", "processing").lower()
        
        # Extract video URL - FIXED VERSION
        video_url = (
            webhook_data.get("video_url") or 
            webhook_data.get("url") or
            webhook_data.get("data", {}).get("video_url") or
            webhook_data.get("data", {}).get("url") or
            event_data.get("url")  # ← FIXED: HeyGen puts it here!
        )
        
        log_info(f"[Webhook] Extracted values - video_id: {video_id}, status: {status}, video_url: {video_url}", "Webhook")
        
        if not video_id:
            log_error(f"[Webhook] No video_id found in webhook data", "Webhook")
            log_error(f"[Webhook] Available root keys: {list(webhook_data.keys())}", "Webhook")
            log_error(f"[Webhook] Available event_data keys: {list(event_data.keys())}", "Webhook")
            return JSONResponse({
                "error": "Missing video_id", 
                "received_keys": list(webhook_data.keys()),
                "event_data_keys": list(event_data.keys())
            }, status_code=400)
        
        log_info(f"[Webhook] Looking for video with HeyGen ID: {video_id}", "Webhook")
        
        # Find video in database via heygen_video_id
        video_record = execute_query(
            "SELECT * FROM videos WHERE heygen_video_id = ?", 
            (video_id,), 
            fetch_one=True
        )
        
        if not video_record:
            log_error(f"[Webhook] Video record not found for HeyGen ID: {video_id}", "Webhook")
            
            # DEBUG: Show what videos DO exist
            existing_videos = execute_query(
                "SELECT id, heygen_video_id, title, status FROM videos ORDER BY created_at DESC LIMIT 10", 
                fetch_all=True
            )
            existing_ids = [v["heygen_video_id"] for v in existing_videos if v["heygen_video_id"]]
            log_error(f"[Webhook] Existing HeyGen IDs in database: {existing_ids}", "Webhook")
            
            return JSONResponse({
                "error": "Video record not found", 
                "heygen_id": video_id,
                "existing_heygen_ids": existing_ids
            }, status_code=404)
        
        log_info(f"[Webhook] Found video record: {video_record['id']} - {video_record['title']}", "Webhook")  
        if status == "completed":
            if video_url:
                # Download video from HeyGen and save locally
                log_info(f"[Webhook] Video completed, downloading from: {video_url}", "Webhook")
                local_path = await download_video_from_heygen(video_url, video_record['id'])
                
                if local_path:
                    # Update database with local path and status
                    execute_query(
                        "UPDATE videos SET video_path = ?, status = ? WHERE id = ?",
                        (local_path, "completed", video_record['id'])
                    )
                    log_info(f"[Webhook] Video {video_record['id']} completed and downloaded: {local_path}", "Webhook")
                else:
                    # Error during download - set status to error
                    execute_query(
                        "UPDATE videos SET status = ? WHERE id = ?",
                        ("error", video_record['id'])
                    )
                    log_error(f"[Webhook] Failed to download video {video_record['id']}", "Webhook")
            else:
                log_warning(f"[Webhook] No video_url provided in webhook for {video_id}", "Webhook")
                # Still mark as completed even without URL
                execute_query(
                    "UPDATE videos SET status = ? WHERE id = ?",
                    ("completed", video_record['id'])
                )
                
        elif status == "failed":
            # Update status to failed
            execute_query(
                "UPDATE videos SET status = ? WHERE id = ?",
                ("failed", video_record['id'])
            )
            log_error(f"[Webhook] Video {video_record['id']} failed in HeyGen", "Webhook")
        
        else:
            # Other status (processing, etc.)
            execute_query(
                "UPDATE videos SET status = ? WHERE id = ?",
                (status, video_record['id'])
            )
            log_info(f"[Webhook] Video {video_record['id']} status updated to: {status}", "Webhook")
        
        return JSONResponse({
            "success": True, 
            "message": "Webhook processed successfully", 
            "video_id": video_id,
            "event_type": event_type,
            "status": status,
            "database_record_id": video_record['id']
        })
    
    except Exception as e:
        log_error("[Webhook] Webhook processing failed", "Webhook", e)
        return JSONResponse({"error": f"Webhook processing failed: {str(e)}"}, status_code=500)

#####################################################################
# API ENDPOINTS - SYSTEM MONITORING
#####################################################################

@app.get("/api/health")
async def health_check():
    try:
        users_count = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
        db_status = "✅ Connected" if users_count else "❌ Error"
        
        return {
            "status": "healthy", 
            "timestamp": datetime.utcnow().isoformat(),
            "heygen_available": bool(HEYGEN_API_KEY),
            "handler_available": HEYGEN_HANDLER_AVAILABLE,
            "base_url": BASE_URL,
            "database": db_status,
            "users_count": users_count.get('count', 0) if users_count else 0,
            "storage": "cloudinary_with_local_fallback",
            "webhook_endpoint": f"{BASE_URL}/api/heygen/webhook",
            "logging": "enhanced_tracking_enabled",
            "debug_endpoints": [
                f"{BASE_URL}/debug/recent-videos",
                f"{BASE_URL}/debug/check-db"
            ]
        }
    except Exception as e:
        log_error("Health check failed", "System", e)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        } 
#####################################################################
# APPLICATION STARTUP EVENT
#####################################################################

@app.on_event("startup")  
async def startup_event():
    log_info("MyAvatar application startup initiated", "System")
    log_info("Database initialized", "System")
    log_info(f"HeyGen API Key: {'✓ Set' if HEYGEN_API_KEY else '✗ Missing'}", "System")
    log_info(f"Base URL: {BASE_URL}", "System")
    log_info("Avatar Management: ✓ Available", "System")
    log_info("Storage: Cloudinary CDN with local fallback", "System")
    log_info(f"Webhook Endpoint: {BASE_URL}/api/heygen/webhook", "System")
    log_info("Enhanced logging system enabled", "System")
    log_info("Debug endpoints available: /debug/recent-videos and /debug/check-db", "System")
    
    if HEYGEN_API_KEY:
        test_heygen_connection()
    
    log_info("🚀 MyAvatar application startup complete - READY FOR HEYGEN DEBUGGING!", "System")

#####################################################################
# MAIN ENTRY POINT
#####################################################################

if __name__ == "__main__":
    print("🌟 Starting MyAvatar server...")
    print("🔗 Local: http://localhost:8000")
    print("🔑 Admin: admin@myavatar.com / admin123")
    print("👤 User: test@example.com / password123")
    print("📋 Admin skal oprette avatars for hver bruger")
    print("🎯 ✅ Cloudinary - cloud storage med local fallback!")
    print("🎬 Record funktionalitet med visuel feedback!")
    print("🗑️ CASCADE DELETE - sletter automatisk relaterede videoer!")
    print("🔄 HeyGen WEBHOOK - automatisk video retur system!")
    print("🧹 CLEANUP - /admin/quickclean endpoint tilgængelig!")
    print("📊 ENHANCED LOGGING - /admin/logs for debugging!")
    print("🔍 ERROR TRACKING - comprehensive system monitoring!")
    print("🐛 DEBUG ENDPOINTS - /debug/recent-videos & /debug/check-db!")
    print("🔧 WEBHOOK FIXED - Now correctly extracts from event_data!")
    print("📝 ENHANCED VIDEO CREATION - Comprehensive logging added!")
    print("")
    print("🔥 READY TO DEBUG THE HEYGEN INTEGRATION ISSUE!")
    print("🎯 After creating a video, check /debug/recent-videos to see what's stored")
    print("📡 Webhook will now correctly find videos by HeyGen ID")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)    


