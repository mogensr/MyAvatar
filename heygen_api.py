"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
Railway-compatible with PostgreSQL + HeyGen Webhook + CASCADE DELETE + Enhanced Logging
Enhanced with Text-to-Speech and proper video format support (16:9, 9:16, 1:1)
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
# HEYGEN API HANDLER - ENHANCED WITH TEXT SUPPORT
#####################################################################
def create_video_from_audio_file(api_key: str, avatar_id: str, audio_url: str, video_format: str = "16:9"):
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Properly set dimensions based on format
    if video_format == "9:16":
        width, height = 720, 1280
        log_info(f"Using Portrait format: {width}x{height}", "HeyGen")
    elif video_format == "1:1":
        width, height = 720, 720
        log_info(f"Using Square format: {width}x{height}", "HeyGen")
    else:  # Default to 16:9
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
        log_info(f"HeyGen Full Response: {response.text}", "HeyGen")
        
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

def create_video_from_text(api_key: str, avatar_id: str, text: str, video_format: str = "16:9", voice_id: str = "en-US-JennyNeural"):
    """Create video using text-to-speech instead of audio file"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Set dimensions based on format
    if video_format == "9:16":
        width, height = 720, 1280
        log_info(f"Using Portrait format: {width}x{height}", "HeyGen")
    elif video_format == "1:1":
        width, height = 720, 720
        log_info(f"Using Square format: {width}x{height}", "HeyGen")
    else:  # Default to 16:9
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
                "type": "text",
                "input_text": text,
                "voice_id": voice_id
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
        log_info(f"Sending text-to-speech request to HeyGen API (format: {video_format})...", "HeyGen")
        log_info(f"Text length: {len(text)} characters", "HeyGen")
        
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            json=payload
        )
        
        log_info(f"HeyGen Response Status: {response.status_code}", "HeyGen")
        log_info(f"HeyGen Full Response: {response.text}", "HeyGen")
        
        if response.status_code == 200:
            result = response.json()
            video_id = result.get("data", {}).get("video_id")
            log_info(f"Text-to-speech video generation started successfully: {video_id}", "HeyGen")
            return {
                "success": True,
                "video_id": video_id,
                "message": f"Text-to-speech video generation started ({video_format})",
                "format": video_format,
                "dimensions": f"{width}x{height}",
                "text_length": len(text)
            }
        else:
            error_msg = f"HeyGen API returned status {response.status_code}: {response.text}"
            log_error(error_msg, "HeyGen")
            return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"HeyGen text-to-speech API request failed: {str(e)}"
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

# Available voice IDs for text-to-speech
AVAILABLE_VOICES = {
    "en-US-JennyNeural": "Jenny (US English - Female)",
    "en-US-GuyNeural": "Guy (US English - Male)",
    "en-GB-SoniaNeural": "Sonia (British English - Female)",
    "en-GB-RyanNeural": "Ryan (British English - Male)",
    "da-DK-ChristelNeural": "Christel (Danish - Female)",
    "da-DK-JeppeNeural": "Jeppe (Danish - Male)"
}

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
templates = Jinja2Templates(directory="templates")
try:
    templates.env.loader = ChoiceLoader([
        FileSystemLoader("templates/portal"),
        FileSystemLoader("templates/landingpage"),
        FileSystemLoader("templates"),
    ])
    log_info("Templates configured", "FastAPI")
except Exception as e:
    log_error("Template configuration error", "FastAPI", e)

#####################################################################
# DATABASE FUNCTIONS
#####################################################################
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    
    if database_url and POSTGRESQL_AVAILABLE:
        log_info("Using PostgreSQL database (Railway)", "Database")
        try:
            conn = psycopg2.connect(database_url)
            return conn, True
        except Exception as e:
            log_error("PostgreSQL connection failed", "Database", e)
            raise
    else:
        log_info("Using SQLite database (local)", "Database")
        conn = sqlite3.connect("myavatar.db")
        conn.row_factory = sqlite3.Row
        return conn, False

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    try:
        conn, is_postgresql = get_db_connection()
        
        try:
            if is_postgresql:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                pg_query = query.replace("?", "%s")
                cursor.execute(pg_query, params)
            else:
                cursor = conn.cursor()
                cursor.execute(query, params)
            
            if fetch_one:
                result = cursor.fetchone()
                return dict(result) if result else None
            elif fetch_all:
                results = cursor.fetchall()
                return [dict(row) for row in results] if results else []
            else:
                rowcount = cursor.rowcount
                lastrowid = getattr(cursor, 'lastrowid', None)
                conn.commit()
                return {"rowcount": rowcount, "lastrowid": lastrowid}
        
        finally:
            conn.close()
    except Exception as e:
        log_error(f"Database query failed: {query}", "Database", e)
        raise           
def init_database():
    log_info("Initializing database...", "Database")
    
    database_url = os.getenv("DATABASE_URL")
    is_postgresql = bool(database_url and POSTGRESQL_AVAILABLE)
    
    conn, _ = get_db_connection()
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
                avatar_url TEXT NOT NULL,
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
                audio_path TEXT,
                text_content TEXT,
                voice_id VARCHAR(255),
                video_path TEXT,
                heygen_video_id VARCHAR(255) DEFAULT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                video_format VARCHAR(10) DEFAULT '16:9',
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
                avatar_url TEXT NOT NULL,
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
                audio_path TEXT,
                text_content TEXT,
                voice_id TEXT,
                video_path TEXT,
                heygen_video_id TEXT DEFAULT NULL,
                status TEXT DEFAULT 'pending',
                video_format TEXT DEFAULT '16:9',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (avatar_id) REFERENCES avatars (id)
            )
        ''')
        
    # Check if we need to add new columns for existing databases
    try:
        cursor.execute("SELECT text_content FROM videos LIMIT 1")
    except:
        log_info("Adding text_content column to videos table", "Database")
        if is_postgresql:
            cursor.execute("ALTER TABLE videos ADD COLUMN text_content TEXT")
            cursor.execute("ALTER TABLE videos ADD COLUMN voice_id VARCHAR(255)")
            cursor.execute("ALTER TABLE videos ADD COLUMN video_format VARCHAR(10) DEFAULT '16:9'")
        else:
            cursor.execute("ALTER TABLE videos ADD COLUMN text_content TEXT")
            cursor.execute("ALTER TABLE videos ADD COLUMN voice_id TEXT")
            cursor.execute("ALTER TABLE videos ADD COLUMN video_format TEXT DEFAULT '16:9'")
        conn.commit()
        
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
        input[type="text"], select, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        textarea { min-height: 100px; resize: vertical; }
        .input-method-selector { display: flex; gap: 10px; margin-bottom: 20px; }
        .method-btn { padding: 10px 20px; border: 2px solid #4f46e5; background: white; color: #4f46e5; border-radius: 5px; cursor: pointer; font-weight: bold; transition: all 0.3s ease; }
        .method-btn.active { background: #4f46e5; color: white; }
        .method-btn:hover { background: #e0e7ff; }
        .input-section { display: none; }
        .input-section.active { display: block; }
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
        .format-preview { display: flex; gap: 10px; margin-top: 10px; justify-content: center; }
        .format-box { border: 2px solid #e5e7eb; border-radius: 4px; padding: 5px; background: #f9fafb; }
        .format-box.selected { border-color: #4f46e5; background: #e0e7ff; }
        .format-box span { display: block; text-align: center; font-size: 12px; color: #6b7280; }
    </style>
    <script>
        window.mediaRecorder = null;
        window.audioChunks = [];
        window.isRecording = false;
        window.recordingTimer = null;
        window.recordingStartTime = null;
        window.inputMethod = 'audio';
        
        function switchInputMethod(method) {
            window.inputMethod = method;
            
            // Update button states
            document.querySelectorAll('.method-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.getElementById(method + '-method-btn').classList.add('active');
            
            // Show/hide sections
            document.querySelectorAll('.input-section').forEach(section => {
                section.classList.remove('active');
            });
            document.getElementById(method + '-input-section').classList.add('active');
            
            // Reset status messages
            document.getElementById('status-message').style.display = 'none';
        }
        
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
        
        function updateTextCharCount() {
            const textArea = document.getElementById('text-content');
            const charCount = document.getElementById('char-count');
            charCount.textContent = textArea.value.length + ' / 5000 tegn';
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
            
            const formData = new FormData();
            formData.append('title', title);
            formData.append('avatar_id', avatarId);
            formData.append('video_format', videoFormat);
            
            if (window.inputMethod === 'audio') {
                const audioElement = document.getElementById('audio-preview');
                if (!audioElement.src) {
                    showStatusMessage('❌ Optag venligst lyd først', 'error');
                    return;
                }
                
                fetch(audioElement.src)
                    .then(res => res.blob())
                    .then(audioBlob => {
                        formData.append('audio', audioBlob, 'recording.wav');
                        sendToHeyGen(formData, videoFormat);
                    });
            } else {
                // Text input
                const textContent = document.getElementById('text-content').value;
                const voiceId = document.getElementById('voice-select').value;
                
                if (!textContent.trim()) {
                    showStatusMessage('❌ Indtast venligst tekst', 'error');
                    return;
                }
                
                formData.append('text_content', textContent);
                formData.append('voice_id', voiceId);
                sendToHeyGen(formData, videoFormat);
            }
        }
        
        function sendToHeyGen(formData, videoFormat) {
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
        }               
        
        function downloadVideo(videoId) {
            window.open('/api/videos/' + videoId + '/download', '_blank');
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            initializeRecorder();
            switchInputMethod('audio'); // Start with audio method
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
            <h2>🎬 Opret Avatar Video</h2>
            
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
                    <option value="1:1">1:1 Square (Instagram/Facebook) - 720x720</option>
                </select>
                <div class="format-preview">
                    <div class="format-box" style="width: 80px; height: 45px;">
                        <span>16:9</span>
                    </div>
                    <div class="format-box" style="width: 45px; height: 80px;">
                        <span>9:16</span>
                    </div>
                    <div class="format-box" style="width: 60px; height: 60px;">
                        <span>1:1</span>
                    </div>
                </div>
            </div>
            
            <div class="input-method-selector">
                <button id="audio-method-btn" class="method-btn active" onclick="switchInputMethod('audio')">🎤 Optag Lyd</button>
                <button id="text-method-btn" class="method-btn" onclick="switchInputMethod('text')">📝 Indtast Tekst</button>
            </div>
            
            <div id="audio-input-section" class="input-section active">
                <div class="recorder-container">
                    <button id="record-btn" class="record-btn" onclick="toggleRecording()" disabled>Optag</button>
                    
                    <div id="recording-indicator" class="recording-indicator">
                        🔴 OPTAGER - Tal klart og tydeligt
                    </div>
                    
                    <div id="recording-timer" class="recording-timer">00:00</div>
                    
                    <audio id="audio-preview" class="audio-preview" controls style="display:none;"></audio>
                </div>
            </div>
            
            <div id="text-input-section" class="input-section">
                <div class="form-group">
                    <label for="text-content">Tekst Indhold:</label>
                    <textarea id="text-content" name="text_content" placeholder="Indtast den tekst, som avataren skal sige..." maxlength="5000" oninput="updateTextCharCount()"></textarea>
                    <small id="char-count" style="color: #6b7280;">0 / 5000 tegn</small>
                </div>
                
                <div class="form-group">
                    <label for="voice-select">Vælg Stemme:</label>
                    <select id="voice-select" name="voice_id">
                        <option value="en-US-JennyNeural">Jenny (US English - Female)</option>
                        <option value="en-US-GuyNeural">Guy (US English - Male)</option>
                        <option value="en-GB-SoniaNeural">Sonia (British English - Female)</option>
                        <option value="en-GB-RyanNeural">Ryan (British English - Male)</option>
                        <option value="da-DK-ChristelNeural">Christel (Danish - Female)</option>
                        <option value="da-DK-JeppeNeural">Jeppe (Danish - Male)</option>
                    </select>
                </div>
            </div>
            
            <div id="status-message" class="status-message info" style="display:none;"></div>
            <button id="heygen-submit-btn" class="btn" onclick="submitToHeyGen()">🚀 Send til HeyGen</button>
        </div>
        
        <div class="card">
            <h2>🎭 Dine Avatars</h2>
            <ul>
            {% for avatar in avatars %}
                <li style="margin-bottom: 15px;">
                    <strong>{{ avatar.name }}</strong><br>
                    HeyGen ID: {{ avatar.heygen_avatar_id }}<br>
                    {% if avatar.avatar_url %}
                    <img src="{{ avatar.avatar_url }}" alt="{{ avatar.name }}" style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin: 5px 0;">
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
                        <p>
                            Avatar: {{ video.avatar_name }} | 
                            Format: {{ video.video_format or '16:9' }} | 
                            Type: {% if video.text_content %}Text{% else %}Audio{% endif %} | 
                            Oprettet: {{ video.created_at }}
                        </p>
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

@app.post("/client-login")
async def client_login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        user = authenticate_user_by_email(email, password)
        
        if not user:
            return HTMLResponse(content=Template(MARKETING_HTML).render(
                request=request, 
                error="Ugyldig email eller adgangskode"
            ))
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"]}, 
            expires_delta=access_token_expires
        )
        
        if user.get("is_admin", 0) == 1:
            response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        else:
            response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response
    except Exception as e:
        log_error("Client login failed", "Auth", e)
        return HTMLResponse(content=Template(MARKETING_HTML).render(
            request=request, 
            error="Login fejl - prøv igen"
        ))

@app.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return RedirectResponse(url="/")

@app.get("/logout")
async def logout():
    log_info("User logged out", "Auth")
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

#####################################################################
# ROUTES - USER DASHBOARD
#####################################################################

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        user = get_current_user(request)
        if not user:
            return RedirectResponse(url="/?error=login_required", status_code=status.HTTP_302_FOUND)
        
        avatars = execute_query(
            "SELECT * FROM avatars WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
            fetch_all=True
        )
        
        videos = execute_query(
            "SELECT v.*, a.name as avatar_name FROM videos v JOIN avatars a ON v.avatar_id = a.id WHERE v.user_id = ? ORDER BY v.created_at DESC",
            (user["id"],),
            fetch_all=True
        )
        
        log_info(f"Dashboard accessed by user: {user['username']}", "Dashboard")
        
        return HTMLResponse(content=Template(DASHBOARD_HTML).render(
            request=request,
            user=user,
            avatars=avatars,
            videos=videos,
            is_admin=user.get("is_admin", 0) == 1
        ))
    except Exception as e:
        log_error("Dashboard load failed", "Dashboard", e)
        return RedirectResponse(url="/?error=dashboard_error", status_code=status.HTTP_302_FOUND)
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
                .error { background: #fee2e2; color: #dc2626; padding: 10px; border-radius: 4px; margin-bottom: 15px; }1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
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
                <p><strong>Text-to-Speech:</strong> ✅ Multiple voices available</p>
                <p><strong>Video Formats:</strong> ✅ 16:9, 9:16, 1:1 supported</p>
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
                .header { background: #dc2626; color: white; padding: