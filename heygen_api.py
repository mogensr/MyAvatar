"""
MyAvatar - Complete AI Avatar Video Generation Platform
========================================================
Railway-compatible with PostgreSQL + HeyGen Webhook + CASCADE DELETE + Enhanced Logging
Enhanced with Text-to-Speech and proper video format support (16:9, 9:16, 1:1)
Premium features: Templates, Interactive Avatars, Custom Backgrounds
WITH PREMIUM DASHBOARD UI
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
            "timestamp": datetime.now().isoformat(),
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
# HEYGEN API HANDLER - ENHANCED WITH TEXT SUPPORT & PREMIUM FEATURES
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

# PREMIUM FEATURES - New Enhanced Functions
def get_available_avatars(api_key: str):
    """Get list of available avatars from HeyGen"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers=headers
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "avatars": response.json().get("data", {}).get("avatars", [])
            }
        else:
            return {"success": False, "error": f"Failed to fetch avatars: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_available_voices(api_key: str, language: str = None):
    """Get list of available voices from HeyGen"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        url = "https://api.heygen.com/v2/voices"
        if language:
            url += f"?language={language}"
            
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return {
                "success": True,
                "voices": response.json().get("data", {}).get("voices", [])
            }
        else:
            return {"success": False, "error": f"Failed to fetch voices: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_video_with_template(api_key: str, template_id: str, variables: dict, avatar_id: str = None):
    """Create video using HeyGen templates (Premium feature)"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "template_id": template_id,
        "variables": variables
    }
    
    if avatar_id:
        payload["character"] = {
            "type": "avatar",
            "avatar_id": avatar_id,
            "avatar_style": "normal"
        }
    
    try:
        log_info(f"Creating video with template: {template_id}", "HeyGen")
        
        response = requests.post(
            "https://api.heygen.com/v2/template",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            video_id = result.get("data", {}).get("video_id")
            return {
                "success": True,
                "video_id": video_id,
                "message": "Template video generation started",
                "template_id": template_id
            }
        else:
            return {"success": False, "error": f"Template API error: {response.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_video_with_background(api_key: str, avatar_id: str, audio_url: str, background: dict, video_format: str = "16:9"):
    """Create video with custom background"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Set dimensions based on format
    if video_format == "9:16":
        width, height = 720, 1280
    elif video_format == "1:1":
        width, height = 720, 720
    else:
        width, height = 1280, 720
    
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
            "background": background  # Can be color, image URL, or video URL
        }],
        "dimension": {
            "width": width,
            "height": height
        }
    }
    
    try:
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "video_id": result.get("data", {}).get("video_id"),
                "message": "Video generation with custom background started"
            }
        else:
            return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_video_details(api_key: str, video_id: str):
    """Get detailed information about a video"""
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json().get("data", {})
            return {
                "success": True,
                "status": data.get("status"),
                "video_url": data.get("video_url"),
                "thumbnail_url": data.get("thumbnail_url"),
                "duration": data.get("duration"),
                "created_at": data.get("created_at")
            }
        else:
            return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

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
log_info("HeyGen API handler loaded successfully with premium features", "System")

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
app = FastAPI(title="MyAvatar", description="AI Avatar Video Generation Platform - Premium Edition")

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
                thumbnail_url TEXT,
                error_message TEXT,
                duration INTEGER,
                template_id VARCHAR(255),
                background_type VARCHAR(50),
                background_value TEXT,
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
                thumbnail_url TEXT,
                error_message TEXT,
                duration INTEGER,
                template_id TEXT,
                background_type TEXT,
                background_value TEXT,
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

# Update database schema for premium features
def update_database_schema():
    conn, is_postgresql = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if is_postgresql:
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS thumbnail_url TEXT")
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS error_message TEXT")
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS duration INTEGER")
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS template_id VARCHAR(255)")
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS background_type VARCHAR(50)")
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS background_value TEXT")
        else:
            # SQLite doesn't support IF NOT EXISTS for columns, so we check first
            cursor.execute("PRAGMA table_info(videos)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'thumbnail_url' not in columns:
                cursor.execute("ALTER TABLE videos ADD COLUMN thumbnail_url TEXT")
            if 'error_message' not in columns:
                cursor.execute("ALTER TABLE videos ADD COLUMN error_message TEXT")
            if 'duration' not in columns:
                cursor.execute("ALTER TABLE videos ADD COLUMN duration INTEGER")
            if 'template_id' not in columns:
                cursor.execute("ALTER TABLE videos ADD COLUMN template_id VARCHAR(255)")
            if 'background_type' not in columns:
                cursor.execute("ALTER TABLE videos ADD COLUMN background_type VARCHAR(50)")
            if 'background_value' not in columns:
                cursor.execute("ALTER TABLE videos ADD COLUMN background_value TEXT")
        
        conn.commit()
        log_info("Database schema updated successfully", "Database")
    except Exception as e:
        log_error("Failed to update database schema", "Database", e)
    finally:
        conn.close()

init_database()
update_database_schema()

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
            expire = datetime.now() + expires_delta
        else:
            expire = datetime.now() + timedelta(minutes=15)
        
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

async def upload_audio_to_cloudinary(audio_file: UploadFile, user_id: int) -> str:
    """Upload audio file to Cloudinary"""
    try:
        log_info(f"Starting audio upload to Cloudinary for user {user_id}", "Cloudinary")
        
        audio_bytes = await audio_file.read()
        public_id = f"user_{user_id}_audio_{uuid.uuid4().hex}"
        
        result = cloudinary.uploader.upload(
            audio_bytes,
            resource_type="auto",
            folder="myavatar/audio",
            public_id=public_id
        )
        
        log_info(f"Audio upload success: {result['secure_url']}", "Cloudinary")
        return result['secure_url']
        
    except Exception as e:
        log_error(f"Audio upload failed for user {user_id}", "Cloudinary", e)
        # Fallback to local storage
        return await upload_audio_locally(audio_file, user_id)

async def upload_audio_locally(audio_file: UploadFile, user_id: int) -> str:
    """Fallback local audio upload"""
    try:
        await audio_file.seek(0)
        
        audio_filename = f"user_{user_id}_audio_{uuid.uuid4().hex}.{audio_file.filename.split('.')[-1]}"
        audio_path = f"static/uploads/audio/{audio_filename}"
        
        audio_bytes = await audio_file.read()
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        
        public_url = f"{BASE_URL}/{audio_path}"
        log_info(f"Local audio upload success: {public_url}", "Storage")
        return public_url
        
    except Exception as e:
        log_error(f"Local audio upload failed for user {user_id}", "Storage", e)
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

# Use the premium dashboard HTML from the artifact
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyAvatar Studio - Professional AI Video Platform</title>
    
    <!-- Font Awesome for Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
        /* ==================== DESIGN SYSTEM ==================== */
        :root {
            /* Premium Color Palette */
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --primary-light: #818cf8;
            --secondary: #8b5cf6;
            --accent: #ec4899;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --info: #3b82f6;
            
            /* Neutral Colors */
            --gray-900: #111827;
            --gray-800: #1f2937;
            --gray-700: #374151;
            --gray-600: #4b5563;
            --gray-500: #6b7280;
            --gray-400: #9ca3af;
            --gray-300: #d1d5db;
            --gray-200: #e5e7eb;
            --gray-100: #f3f4f6;
            --gray-50: #f9fafb;
            --white: #ffffff;
            
            /* Gradients */
            --gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --gradient-premium: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --gradient-dark: linear-gradient(135deg, #232526 0%, #414345 100%);
            
            /* Shadows */
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
            --shadow-glow: 0 0 30px rgba(99, 102, 241, 0.3);
            
            /* Animations */
            --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-base: 300ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-slow: 500ms cubic-bezier(0.4, 0, 0.2, 1);
            
            /* Layout */
            --sidebar-width: 280px;
            --header-height: 72px;
            --content-max-width: 1400px;
        }
        
        /* Dark Mode Variables */
        [data-theme="dark"] {
            --gray-900: #f9fafb;
            --gray-800: #f3f4f6;
            --gray-700: #e5e7eb;
            --gray-600: #d1d5db;
            --gray-500: #9ca3af;
            --gray-400: #6b7280;
            --gray-300: #4b5563;
            --gray-200: #374151;
            --gray-100: #1f2937;
            --gray-50: #111827;
            --white: #0f172a;
        }
        
        /* ==================== GLOBAL STYLES ==================== */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: var(--gray-50);
            color: var(--gray-900);
            line-height: 1.6;
            overflow-x: hidden;
            transition: background var(--transition-base);
        }
        
        /* ==================== LAYOUT ==================== */
        .app-container {
            display: flex;
            min-height: 100vh;
        }
        
        /* Sidebar */
        .sidebar {
            width: var(--sidebar-width);
            background: var(--white);
            border-right: 1px solid var(--gray-200);
            display: flex;
            flex-direction: column;
            position: fixed;
            height: 100vh;
            z-index: 40;
            transform: translateX(0);
            transition: transform var(--transition-base);
        }
        
        .sidebar.collapsed {
            transform: translateX(-100%);
        }
        
        .sidebar-header {
            padding: 1.5rem;
            border-bottom: 1px solid var(--gray-200);
            background: var(--gradient-primary);
            color: white;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .logo-icon {
            font-size: 2rem;
        }
        
        .nav-menu {
            flex: 1;
            padding: 1rem 0;
            overflow-y: auto;
        }
        
        .nav-section {
            margin-bottom: 2rem;
        }
        
        .nav-section-title {
            padding: 0 1.5rem;
            margin-bottom: 0.5rem;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--gray-500);
            letter-spacing: 0.05em;
        }
        
        .nav-item {
            position: relative;
            margin: 0.25rem 0.75rem;
        }
        
        .nav-link {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 1rem;
            color: var(--gray-700);
            text-decoration: none;
            border-radius: 0.5rem;
            transition: all var(--transition-fast);
            position: relative;
            overflow: hidden;
        }
        
        .nav-link:hover {
            background: var(--gray-100);
            color: var(--primary);
            transform: translateX(2px);
        }
        
        .nav-link.active {
            background: var(--primary);
            color: white;
            font-weight: 600;
        }
        
        .nav-link.active::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: white;
        }
        
        .nav-badge {
            margin-left: auto;
            padding: 0.125rem 0.5rem;
            background: var(--danger);
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 9999px;
        }
        
        .premium-badge {
            background: var(--gradient-premium);
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            color: white;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Main Content */
        .main-content {
            flex: 1;
            margin-left: var(--sidebar-width);
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            transition: margin-left var(--transition-base);
        }
        
        .main-content.full-width {
            margin-left: 0;
        }
        
        /* Header */
        .header {
            height: var(--header-height);
            background: var(--white);
            border-bottom: 1px solid var(--gray-200);
            display: flex;
            align-items: center;
            padding: 0 2rem;
            position: sticky;
            top: 0;
            z-index: 30;
            box-shadow: var(--shadow-sm);
        }
        
        .header-left {
            display: flex;
            align-items: center;
            gap: 1rem;
            flex: 1;
        }
        
        .menu-toggle {
            display: none;
            background: none;
            border: none;
            font-size: 1.5rem;
            color: var(--gray-700);
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 0.375rem;
            transition: all var(--transition-fast);
        }
        
        .menu-toggle:hover {
            background: var(--gray-100);
            color: var(--primary);
        }
        
        .search-bar {
            position: relative;
            width: 400px;
        }
        
        .search-input {
            width: 100%;
            padding: 0.625rem 1rem 0.625rem 3rem;
            background: var(--gray-100);
            border: 1px solid transparent;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            transition: all var(--transition-fast);
        }
        
        .search-input:focus {
            outline: none;
            background: white;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        
        .search-icon {
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--gray-400);
        }
        
        .header-right {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .header-btn {
            position: relative;
            background: none;
            border: none;
            padding: 0.5rem;
            font-size: 1.25rem;
            color: var(--gray-600);
            cursor: pointer;
            border-radius: 0.5rem;
            transition: all var(--transition-fast);
        }
        
        .header-btn:hover {
            background: var(--gray-100);
            color: var(--primary);
        }
        
        .notification-dot {
            position: absolute;
            top: 0.25rem;
            right: 0.25rem;
            width: 0.5rem;
            height: 0.5rem;
            background: var(--danger);
            border-radius: 50%;
            border: 2px solid var(--white);
        }
        
        .user-menu {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.5rem;
            border-radius: 0.5rem;
            cursor: pointer;
            transition: all var(--transition-fast);
        }
        
        .user-menu:hover {
            background: var(--gray-100);
        }
        
        .user-avatar {
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 50%;
            background: var(--gradient-primary);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
        }
        
        .user-info {
            text-align: left;
        }
        
        .user-name {
            font-weight: 600;
            font-size: 0.875rem;
            color: var(--gray-900);
        }
        
        .user-role {
            font-size: 0.75rem;
            color: var(--gray-500);
        }
        
        /* Page Content */
        .page-content {
            flex: 1;
            padding: 2rem;
            max-width: var(--content-max-width);
            margin: 0 auto;
            width: 100%;
        }
        
        /* ==================== COMPONENTS ==================== */
        
        /* Cards */
        .card {
            background: var(--white);
            border-radius: 1rem;
            box-shadow: var(--shadow-md);
            overflow: hidden;
            transition: all var(--transition-base);
        }
        
        .card:hover {
            box-shadow: var(--shadow-lg);
            transform: translateY(-2px);
        }
        
        .card-header {
            padding: 1.5rem 2rem;
            border-bottom: 1px solid var(--gray-200);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .card-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--gray-900);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .card-actions {
            display: flex;
            gap: 0.5rem;
        }
        
        .card-body {
            padding: 2rem;
        }
        
        /* Feature Grid */
        .feature-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .feature-card {
            background: var(--white);
            border-radius: 1rem;
            padding: 2rem;
            border: 2px solid var(--gray-200);
            transition: all var(--transition-base);
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }
        
        .feature-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: var(--gradient-primary);
            transform: scaleX(0);
            transition: transform var(--transition-base);
        }
        
        .feature-card:hover {
            border-color: var(--primary);
            box-shadow: var(--shadow-lg);
            transform: translateY(-4px);
        }
        
        .feature-card:hover::before {
            transform: scaleX(1);
        }
        
        .feature-card.premium {
            background: linear-gradient(135deg, rgba(236, 72, 153, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%);
            border-color: var(--secondary);
        }
        
        .feature-card.premium::before {
            background: var(--gradient-premium);
        }
        
        .feature-icon {
            width: 3.5rem;
            height: 3.5rem;
            background: var(--gradient-primary);
            border-radius: 1rem;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            color: white;
            margin-bottom: 1rem;
        }
        
        .feature-card.premium .feature-icon {
            background: var(--gradient-premium);
        }
        
        .feature-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--gray-900);
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .feature-description {
            color: var(--gray-600);
            font-size: 0.875rem;
            line-height: 1.5;
            margin-bottom: 1rem;
        }
        
        .feature-tags {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        .tag {
            padding: 0.25rem 0.75rem;
            background: var(--gray-100);
            color: var(--gray-700);
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .tag.new {
            background: var(--success);
            color: white;
        }
        
        .tag.coming-soon {
            background: var(--warning);
            color: white;
        }
        
        /* Creation Wizard */
        .wizard-container {
            background: var(--white);
            border-radius: 1rem;
            box-shadow: var(--shadow-xl);
            overflow: hidden;
        }
        
        .wizard-header {
            background: var(--gradient-primary);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        
        .wizard-title {
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
        }
        
        .wizard-subtitle {
            opacity: 0.9;
            font-size: 1.125rem;
        }
        
        .wizard-steps {
            display: flex;
            background: var(--gray-50);
            padding: 1.5rem;
            justify-content: center;
            gap: 2rem;
            border-bottom: 1px solid var(--gray-200);
        }
        
        .wizard-step {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: var(--gray-500);
            font-weight: 600;
            position: relative;
        }
        
        .wizard-step.active {
            color: var(--primary);
        }
        
        .wizard-step.completed {
            color: var(--success);
        }
        
        .step-number {
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 50%;
            background: var(--gray-200);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            transition: all var(--transition-base);
        }
        
        .wizard-step.active .step-number {
            background: var(--primary);
            color: white;
            box-shadow: var(--shadow-glow);
        }
        
        .wizard-step.completed .step-number {
            background: var(--success);
            color: white;
        }
        
        .wizard-body {
            padding: 3rem;
            min-height: 400px;
        }
        
        /* Input Method Selector */
        .input-methods {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .input-method {
            padding: 1.5rem;
            border: 2px solid var(--gray-200);
            border-radius: 1rem;
            text-align: center;
            cursor: pointer;
            transition: all var(--transition-base);
            background: var(--white);
        }
        
        .input-method:hover {
            border-color: var(--primary);
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }
        
        .input-method.active {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
            box-shadow: var(--shadow-glow);
        }
        
        .input-method-icon {
            font-size: 2.5rem;
            margin-bottom: 0.75rem;
        }
        
        .input-method-title {
            font-weight: 700;
            font-size: 1.125rem;
            margin-bottom: 0.25rem;
        }
        
        .input-method-desc {
            font-size: 0.875rem;
            opacity: 0.8;
        }
        
        /* Avatar Selection */
        .avatar-selection {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .avatar-option {
            text-align: center;
            cursor: pointer;
            padding: 1rem;
            border-radius: 1rem;
            border: 3px solid transparent;
            transition: all var(--transition-base);
            background: var(--gray-50);
        }
        
        .avatar-option:hover {
            border-color: var(--primary-light);
            transform: translateY(-4px);
            box-shadow: var(--shadow-md);
        }
        
        .avatar-option.selected {
            border-color: var(--primary);
            background: white;
            box-shadow: var(--shadow-glow);
        }
        
        .avatar-image {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            object-fit: cover;
            margin: 0 auto 0.75rem;
            border: 4px solid var(--gray-200);
            transition: all var(--transition-base);
        }
        
        .avatar-option.selected .avatar-image {
            border-color: var(--primary);
        }
        
        .avatar-label {
            font-weight: 600;
            color: var(--gray-900);
            font-size: 0.875rem;
        }
        
        /* Recording Interface */
        .recording-interface {
            text-align: center;
            padding: 3rem;
            background: var(--gray-50);
            border-radius: 1rem;
            position: relative;
            overflow: hidden;
        }
        
        .recording-interface::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.1) 0%, transparent 70%);
            animation: pulse-bg 3s ease-in-out infinite;
            opacity: 0;
            transition: opacity var(--transition-base);
        }
        
        .recording-interface.active::before {
            opacity: 1;
        }
        
        @keyframes pulse-bg {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }
        
        .record-button {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: var(--gradient-primary);
            border: none;
            color: white;
            font-size: 3rem;
            cursor: pointer;
            transition: all var(--transition-base);
            position: relative;
            z-index: 10;
            box-shadow: var(--shadow-lg);
        }
        
        .record-button:hover:not(:disabled) {
            transform: scale(1.05);
            box-shadow: var(--shadow-xl), var(--shadow-glow);
        }
        
        .record-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .record-button.recording {
            background: var(--gradient-premium);
            animation: pulse-record 1.5s ease-in-out infinite;
        }
        
        @keyframes pulse-record {
            0%, 100% { transform: scale(1); box-shadow: var(--shadow-lg); }
            50% { transform: scale(1.1); box-shadow: var(--shadow-xl), 0 0 40px rgba(236, 72, 153, 0.5); }
        }
        
        .recording-timer {
            font-size: 3rem;
            font-weight: 300;
            color: var(--primary);
            margin-top: 2rem;
            font-family: 'SF Mono', Monaco, monospace;
            letter-spacing: 0.1em;
        }
        
        .waveform {
            margin: 2rem 0;
            height: 80px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
        }
        
        .waveform-bar {
            width: 4px;
            background: var(--primary);
            border-radius: 2px;
            animation: wave 1s ease-in-out infinite;
        }
        
        .waveform-bar:nth-child(1) { height: 20px; animation-delay: 0s; }
        .waveform-bar:nth-child(2) { height: 30px; animation-delay: 0.1s; }
        .waveform-bar:nth-child(3) { height: 45px; animation-delay: 0.2s; }
        .waveform-bar:nth-child(4) { height: 35px; animation-delay: 0.3s; }
        .waveform-bar:nth-child(5) { height: 50px; animation-delay: 0.4s; }
        .waveform-bar:nth-child(6) { height: 35px; animation-delay: 0.5s; }
        .waveform-bar:nth-child(7) { height: 45px; animation-delay: 0.6s; }
        .waveform-bar:nth-child(8) { height: 30px; animation-delay: 0.7s; }
        .waveform-bar:nth-child(9) { height: 20px; animation-delay: 0.8s; }
        
        @keyframes wave {
            0%, 100% { transform: scaleY(1); }
            50% { transform: scaleY(1.5); }
        }
        
        /* Text Input */
        .text-input-container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .text-area {
            width: 100%;
            min-height: 200px;
            padding: 1.5rem;
            border: 2px solid var(--gray-200);
            border-radius: 1rem;
            font-size: 1rem;
            line-height: 1.6;
            resize: vertical;
            transition: all var(--transition-fast);
            background: var(--white);
        }
        
        .text-area:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        
        .char-counter {
            text-align: right;
            margin-top: 0.5rem;
            font-size: 0.875rem;
            color: var(--gray-500);
        }
        
        .voice-selector {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 2rem;
        }
        
        .voice-option {
            padding: 1rem;
            border: 2px solid var(--gray-200);
            border-radius: 0.75rem;
            cursor: pointer;
            transition: all var(--transition-fast);
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .voice-option:hover {
            border-color: var(--primary);
            background: var(--gray-50);
        }
        
        .voice-option.selected {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
        }
        
        .voice-icon {
            font-size: 1.5rem;
        }
        
        .voice-details {
            flex: 1;
        }
        
        .voice-name {
            font-weight: 600;
            font-size: 0.875rem;
        }
        
        .voice-lang {
            font-size: 0.75rem;
            opacity: 0.8;
        }
        
        /* Format Selector */
        .format-selector {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
            max-width: 600px;
            margin: 2rem auto;
        }
        
        .format-option {
            text-align: center;
            padding: 2rem 1rem;
            border: 2px solid var(--gray-200);
            border-radius: 1rem;
            cursor: pointer;
            transition: all var(--transition-base);
            background: var(--white);
        }
        
        .format-option:hover {
            border-color: var(--primary);
            transform: translateY(-2px);
            box-shadow: var(--shadow-md);
        }
        
        .format-option.selected {
            border-color: var(--primary);
            background: var(--primary);
            color: white;
            box-shadow: var(--shadow-glow);
        }
        
        .format-preview {
            width: 80px;
            height: 60px;
            margin: 0 auto 1rem;
            background: var(--gray-200);
            border-radius: 0.5rem;
            position: relative;
            overflow: hidden;
        }
        
        .format-option.selected .format-preview {
            background: rgba(255, 255, 255, 0.3);
        }
        
        .format-option[data-format="9:16"] .format-preview {
            width: 40px;
            height: 70px;
        }
        
        .format-option[data-format="1:1"] .format-preview {
            width: 60px;
            height: 60px;
        }
        
        .format-name {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.25rem;
        }
        
        .format-desc {
            font-size: 0.75rem;
            opacity: 0.8;
        }
        
        /* Background Selector (Future Feature) */
        .background-selector {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 1rem;
            margin-top: 2rem;
        }
        
        .background-option {
            aspect-ratio: 16/9;
            border-radius: 0.5rem;
            overflow: hidden;
            cursor: pointer;
            position: relative;
            border: 3px solid transparent;
            transition: all var(--transition-fast);
        }
        
        .background-option:hover {
            transform: scale(1.05);
            box-shadow: var(--shadow-md);
        }
        
        .background-option.selected {
            border-color: var(--primary);
            box-shadow: var(--shadow-glow);
        }
        
        .background-preview {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .background-label {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 0.5rem;
            background: linear-gradient(to top, rgba(0,0,0,0.8), transparent);
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        /* Buttons */
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 0.875rem;
            cursor: pointer;
            transition: all var(--transition-fast);
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
            position: relative;
            overflow: hidden;
        }
        
        .btn::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.2);
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }
        
        .btn:active::before {
            width: 300px;
            height: 300px;
        }
        
        .btn-primary {
            background: var(--gradient-primary);
            color: white;
            box-shadow: var(--shadow-md);
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg), var(--shadow-glow);
        }
        
        .btn-secondary {
            background: var(--gray-200);
            color: var(--gray-700);
        }
        
        .btn-secondary:hover {
            background: var(--gray-300);
            transform: translateY(-1px);
        }
        
        .btn-success {
            background: var(--success);
            color: white;
            box-shadow: var(--shadow-md);
        }
        
        .btn-success:hover {
            background: #059669;
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        
        .btn-danger {
            background: var(--danger);
            color: white;
        }
        
        .btn-premium {
            background: var(--gradient-premium);
            color: white;
            box-shadow: var(--shadow-md);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .btn-premium:hover {
            transform: translateY(-2px) scale(1.02);
            box-shadow: var(--shadow-xl), 0 0 30px rgba(236, 72, 153, 0.3);
        }
        
        .btn-group {
            display: flex;
            gap: 1rem;
            justify-content: center;
            margin-top: 2rem;
        }
        
        /* Loading States */
        .skeleton {
            background: linear-gradient(90deg, var(--gray-200) 25%, var(--gray-100) 50%, var(--gray-200) 75%);
            background-size: 200% 100%;
            animation: loading 1.5s infinite;
            border-radius: 0.5rem;
        }
        
        @keyframes loading {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }
        
        .spinner {
            display: inline-block;
            width: 1.5rem;
            height: 1.5rem;
            border: 3px solid var(--gray-200);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Progress Indicator */
        .progress-bar {
            width: 100%;
            height: 8px;
            background: var(--gray-200);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 1rem;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--gradient-primary);
            border-radius: 4px;
            transition: width var(--transition-slow);
            position: relative;
            overflow: hidden;
        }
        
        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            animation: shimmer 2s infinite;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(8px);
            z-index: 100;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity var(--transition-base);
        }
        
        .modal.show {
            display: flex;
            opacity: 1;
        }
        
        .modal-content {
            background: var(--white);
            border-radius: 1rem;
            padding: 2rem;
            max-width: 500px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            transform: scale(0.9);
            transition: transform var(--transition-base);
            box-shadow: var(--shadow-xl);
        }
        
        .modal.show .modal-content {
            transform: scale(1);
        }
        
        .modal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.5rem;
        }
        
        .modal-title {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--gray-900);
        }
        
        .modal-close {
            background: none;
            border: none;
            font-size: 1.5rem;
            color: var(--gray-500);
            cursor: pointer;
            padding: 0.5rem;
            border-radius: 0.375rem;
            transition: all var(--transition-fast);
        }
        
        .modal-close:hover {
            background: var(--gray-100);
            color: var(--gray-900);
        }
        
        /* Notifications */
        .notification-container {
            position: fixed;
            top: calc(var(--header-height) + 1rem);
            right: 1rem;
            z-index: 90;
            pointer-events: none;
        }
        
        .notification {
            background: var(--white);
            padding: 1rem 1.5rem;
            border-radius: 0.75rem;
            box-shadow: var(--shadow-lg);
            margin-bottom: 1rem;
            min-width: 300px;
            transform: translateX(400px);
            transition: transform var(--transition-base);
            pointer-events: all;
            display: flex;
            align-items: center;
            gap: 1rem;
            border-left: 4px solid var(--primary);
        }
        
        .notification.show {
            transform: translateX(0);
        }
        
        .notification.success {
            border-left-color: var(--success);
        }
        
        .notification.error {
            border-left-color: var(--danger);
        }
        
        .notification.warning {
            border-left-color: var(--warning);
        }
        
        .notification-icon {
            font-size: 1.25rem;
        }
        
        .notification-content {
            flex: 1;
        }
        
        .notification-title {
            font-weight: 600;
            font-size: 0.875rem;
            color: var(--gray-900);
            margin-bottom: 0.25rem;
        }
        
        .notification-message {
            font-size: 0.875rem;
            color: var(--gray-600);
        }
        
        /* Stats Cards */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: var(--white);
            padding: 1.5rem;
            border-radius: 1rem;
            box-shadow: var(--shadow-md);
            position: relative;
            overflow: hidden;
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 100px;
            height: 100px;
            background: var(--gradient-primary);
            opacity: 0.1;
            border-radius: 50%;
            transform: translate(30px, -30px);
        }
        
        .stat-icon {
            width: 3rem;
            height: 3rem;
            background: var(--gradient-primary);
            border-radius: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.5rem;
            margin-bottom: 1rem;
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--gray-900);
            margin-bottom: 0.25rem;
        }
        
        .stat-label {
            color: var(--gray-600);
            font-size: 0.875rem;
        }
        
        .stat-change {
            position: absolute;
            top: 1rem;
            right: 1rem;
            padding: 0.25rem 0.75rem;
            background: var(--success);
            color: white;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 9999px;
        }
        
        .stat-change.negative {
            background: var(--danger);
        }
        
        /* Video Grid */
        .videos-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
        }
        
        .video-card {
            background: var(--white);
            border-radius: 1rem;
            overflow: hidden;
            box-shadow: var(--shadow-md);
            transition: all var(--transition-base);
            cursor: pointer;
        }
        
        .video-card:hover {
            transform: translateY(-4px);
            box-shadow: var(--shadow-lg);
        }
        
        .video-thumbnail {
            aspect-ratio: 16/9;
            background: var(--gray-200);
            position: relative;
            overflow: hidden;
        }
        
        .video-thumbnail img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .video-duration {
            position: absolute;
            bottom: 0.5rem;
            right: 0.5rem;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        .video-status {
            position: absolute;
            top: 0.5rem;
            left: 0.5rem;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .video-status.processing {
            background: var(--warning);
            color: white;
        }
        
        .video-status.completed {
            background: var(--success);
            color: white;
        }
        
        .video-status.failed {
            background: var(--danger);
            color: white;
        }
        
        .video-info {
            padding: 1.5rem;
        }
        
        .video-title {
            font-weight: 700;
            color: var(--gray-900);
            margin-bottom: 0.5rem;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        
        .video-meta {
            display: flex;
            align-items: center;
            gap: 1rem;
            color: var(--gray-600);
            font-size: 0.875rem;
        }
        
        .video-actions {
            display: flex;
            gap: 0.5rem;
            padding: 0 1.5rem 1.5rem;
        }
        
        /* Responsive Design */
        @media (max-width: 1024px) {
            .sidebar {
                transform: translateX(-100%);
            }
            
            .sidebar.open {
                transform: translateX(0);
            }
            
            .main-content {
                margin-left: 0;
            }
            
            .menu-toggle {
                display: block;
            }
            
            .search-bar {
                width: 300px;
            }
        }
        
        @media (max-width: 768px) {
            .header {
                padding: 0 1rem;
            }
            
            .search-bar {
                display: none;
            }
            
            .user-info {
                display: none;
            }
            
            .page-content {
                padding: 1rem;
            }
            
            .feature-grid {
                grid-template-columns: 1fr;
            }
            
            .wizard-steps {
                gap: 1rem;
                font-size: 0.875rem;
            }
            
            .step-number {
                width: 2rem;
                height: 2rem;
                font-size: 0.875rem;
            }
            
            .format-selector {
                grid-template-columns: 1fr;
            }
        }
        
        /* Utility Classes */
        .text-center { text-align: center; }
        .hidden { display: none !important; }
        .mt-1 { margin-top: 0.5rem; }
        .mt-2 { margin-top: 1rem; }
        .mt-3 { margin-top: 1.5rem; }
        .mt-4 { margin-top: 2rem; }
        .mb-1 { margin-bottom: 0.5rem; }
        .mb-2 { margin-bottom: 1rem; }
        .mb-3 { margin-bottom: 1.5rem; }
        .mb-4 { margin-bottom: 2rem; }
        
        /* Form Elements */
        .form-label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 600;
            color: var(--gray-700);
            font-size: 0.875rem;
        }
        
        .form-input {
            width: 100%;
            padding: 0.75rem 1rem;
            border: 2px solid var(--gray-200);
            border-radius: 0.5rem;
            font-size: 1rem;
            transition: all var(--transition-fast);
            background: var(--white);
        }
        
        .form-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
    </style>
</head>
<body>
    <!-- App Container -->
    <div class="app-container">
        <!-- Sidebar -->
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div class="logo">
                    <span class="logo-icon">🎬</span>
                    <span>MyAvatar</span>
                </div>
            </div>
            
            <nav class="nav-menu">
                <div class="nav-section">
                    <div class="nav-section-title">Main</div>
                    <div class="nav-item">
                        <a href="#dashboard" class="nav-link active">
                            <i class="fas fa-home"></i>
                            <span>Dashboard</span>
                        </a>
                    </div>
                    <div class="nav-item">
                        <a href="#create" class="nav-link">
                            <i class="fas fa-plus-circle"></i>
                            <span>Create Video</span>
                            <span class="nav-badge">New</span>
                        </a>
                    </div>
                    <div class="nav-item">
                        <a href="#videos" class="nav-link">
                            <i class="fas fa-video"></i>
                            <span>My Videos</span>
                        </a>
                    </div>
                    <div class="nav-item">
                        <a href="#templates" class="nav-link">
                            <i class="fas fa-file-alt"></i>
                            <span>Templates</span>
                            <span class="premium-badge">Premium</span>
                        </a>
                    </div>
                </div>
                
                <div class="nav-section">
                    <div class="nav-section-title">Advanced</div>
                    <div class="nav-item">
                        <a href="#interactive" class="nav-link">
                            <i class="fas fa-users"></i>
                            <span>Interactive Avatars</span>
                            <span class="tag coming-soon">Soon</span>
                        </a>
                    </div>
                    <div class="nav-item">
                        <a href="#backgrounds" class="nav-link">
                            <i class="fas fa-image"></i>
                            <span>Backgrounds</span>
                        </a>
                    </div>
                    <div class="nav-item">
                        <a href="#distribution" class="nav-link">
                            <i class="fas fa-share-alt"></i>
                            <span>Distribution</span>
                        </a>
                    </div>
                    <div class="nav-item">
                        <a href="#analytics" class="nav-link">
                            <i class="fas fa-chart-line"></i>
                            <span>Analytics</span>
                        </a>
                    </div>
                </div>
                
                <div class="nav-section">
                    <div class="nav-section-title">Account</div>
                    <div class="nav-item">
                        <a href="#subscription" class="nav-link">
                            <i class="fas fa-crown"></i>
                            <span>Subscription</span>
                        </a>
                    </div>
                    <div class="nav-item">
                        <a href="/logout" class="nav-link">
                            <i class="fas fa-sign-out-alt"></i>
                            <span>Logout</span>
                        </a>
                    </div>
                    {% if is_admin %}
                    <div class="nav-item">
                        <a href="/admin" class="nav-link">
                            <i class="fas fa-cog"></i>
                            <span>Admin Panel</span>
                        </a>
                    </div>
                    {% endif %}
                </div>
            </nav>
        </aside>
        
        <!-- Main Content -->
        <main class="main-content">
            <!-- Header -->
            <header class="header">
                <div class="header-left">
                    <button class="menu-toggle" onclick="toggleSidebar()">
                        <i class="fas fa-bars"></i>
                    </button>
                    
                    <div class="search-bar">
                        <i class="fas fa-search search-icon"></i>
                        <input type="text" class="search-input" placeholder="Search videos, templates...">
                    </div>
                </div>
                
                <div class="header-right">
                    <button class="header-btn" onclick="toggleTheme()">
                        <i class="fas fa-moon"></i>
                    </button>
                    
                    <button class="header-btn">
                        <i class="fas fa-bell"></i>
                        <span class="notification-dot"></span>
                    </button>
                    
                    <div class="user-menu">
                        <div class="user-avatar" id="userAvatar">{{ user.username[0].upper() }}</div>
                        <div class="user-info">
                            <div class="user-name" id="userName">{{ user.username }}</div>
                            <div class="user-role">{% if user.is_admin %}Admin{% else %}Pro Member{% endif %}</div>
                        </div>
                        <i class="fas fa-chevron-down" style="margin-left: 0.5rem; color: var(--gray-500);"></i>
                    </div>
                </div>
            </header>
            
            <!-- Page Content -->
            <div class="page-content">
                <!-- Stats Overview -->
                <div class="stats-grid mb-4">
                    <div class="stat-card">
                        <div class="stat-icon">
                            <i class="fas fa-video"></i>
                        </div>
                        <div class="stat-value">{{ videos|length }}</div>
                        <div class="stat-label">Total Videos</div>
                        <span class="stat-change">+12%</span>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon" style="background: var(--gradient-premium);">
                            <i class="fas fa-clock"></i>
                        </div>
                        <div class="stat-value">{{ avatars|length }}</div>
                        <div class="stat-label">Active Avatars</div>
                        <span class="stat-change">+8%</span>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon" style="background: linear-gradient(135deg, #10b981, #34d399);">
                            <i class="fas fa-check-circle"></i>
                        </div>
                        <div class="stat-value">{{ videos|selectattr("status", "equalto", "completed")|list|length }}</div>
                        <div class="stat-label">Completed</div>
                        <span class="stat-change">+24%</span>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-icon" style="background: linear-gradient(135deg, #f59e0b, #fbbf24);">
                            <i class="fas fa-hourglass-half"></i>
                        </div>
                        <div class="stat-value">{{ videos|selectattr("status", "equalto", "processing")|list|length }}</div>
                        <div class="stat-label">Processing</div>
                        <span class="stat-change negative">-5%</span>
                    </div>
                </div>
                
                <!-- Feature Grid -->
                <h2 class="mb-3">Choose Your Creation Method</h2>
                <div class="feature-grid">
                    <div class="feature-card" onclick="startCreation('voice')">
                        <div class="feature-icon">
                            <i class="fas fa-microphone"></i>
                        </div>
                        <h3 class="feature-title">Voice Recording</h3>
                        <p class="feature-description">Record your voice and let our AI avatars speak for you. Perfect for personalized messages.</p>
                        <div class="feature-tags">
                            <span class="tag">Popular</span>
                            <span class="tag">Easy</span>
                        </div>
                    </div>
                    
                    <div class="feature-card" onclick="startCreation('text')">
                        <div class="feature-icon">
                            <i class="fas fa-keyboard"></i>
                        </div>
                        <h3 class="feature-title">Text to Speech</h3>
                        <p class="feature-description">Type your script and choose from multiple AI voices in different languages.</p>
                        <div class="feature-tags">
                            <span class="tag">Multiple Voices</span>
                            <span class="tag new">New</span>
                        </div>
                    </div>
                    
                    <div class="feature-card premium" onclick="showPremiumModal()">
                        <div class="feature-icon">
                            <i class="fas fa-magic"></i>
                        </div>
                        <h3 class="feature-title">
                            Templates
                            <span class="premium-badge">Premium</span>
                        </h3>
                        <p class="feature-description">Use pre-made templates for common scenarios like sales pitches, tutorials, and more.</p>
                        <div class="feature-tags">
                            <span class="tag coming-soon">Coming Soon</span>
                        </div>
                    </div>
                    
                    <div class="feature-card premium" onclick="showPremiumModal()">
                        <div class="feature-icon">
                            <i class="fas fa-comments"></i>
                        </div>
                        <h3 class="feature-title">
                            Interactive Avatars
                            <span class="premium-badge">Premium</span>
                        </h3>
                        <p class="feature-description">Create avatars that can interact with viewers in real-time conversations.</p>
                        <div class="feature-tags">
                            <span class="tag coming-soon">Coming Soon</span>
                        </div>
                    </div>
                </div>
                
                <!-- Recent Videos -->
                <div class="mt-4">
                    <div class="card-header">
                        <h2 class="card-title">
                            <i class="fas fa-history"></i>
                            Recent Videos
                        </h2>
                        <div class="card-actions">
                            <a href="#videos" class="btn btn-secondary">View All</a>
                        </div>
                    </div>
                    
                    <div class="videos-grid" id="recentVideos">
                        {% for video in videos[:3] %}
                        <div class="video-card">
                            <div class="video-thumbnail">
                                {% if video.status == 'completed' and video.video_path %}
                                <img src="{{ video.thumbnail_url or 'https://via.placeholder.com/300x170' }}" alt="{{ video.title }}">
                                {% else %}
                                <div class="skeleton" style="height: 100%;"></div>
                                {% endif %}
                                <span class="video-status {{ video.status }}">{{ video.status }}</span>
                                {% if video.duration %}
                                <span class="video-duration">{{ video.duration }}s</span>
                                {% endif %}
                            </div>
                            <div class="video-info">
                                <div class="video-title">{{ video.title or 'Untitled Video' }}</div>
                                <div class="video-meta">
                                    <span><i class="fas fa-calendar"></i> {{ video.created_at }}</span>
                                    <span><i class="fas fa-film"></i> {{ video.video_format or '16:9' }}</span>
                                </div>
                            </div>
                            {% if video.status == 'completed' and video.video_path %}
                            <div class="video-actions">
                                <a href="{{ video.video_path }}" target="_blank" class="btn btn-primary btn-sm">
                                    <i class="fas fa-play"></i> Play
                                </a>
                                <button class="btn btn-secondary btn-sm" onclick="downloadVideo({{ video.id }})">
                                    <i class="fas fa-download"></i>
                                </button>
                            </div>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </main>
    </div>
    
    <!-- Creation Wizard Modal -->
    <div class="modal" id="creationModal">
        <div class="modal-content" style="max-width: 900px;">
            <div class="wizard-container">
                <div class="wizard-header">
                    <h2 class="wizard-title">Create Your Avatar Video</h2>
                    <p class="wizard-subtitle">Follow the steps to create amazing AI-powered videos</p>
                </div>
                
                <div class="wizard-steps">
                    <div class="wizard-step active" id="step1">
                        <div class="step-number">1</div>
                        <span>Choose Avatar</span>
                    </div>
                    <div class="wizard-step" id="step2">
                        <div class="step-number">2</div>
                        <span>Add Content</span>
                    </div>
                    <div class="wizard-step" id="step3">
                        <div class="step-number">3</div>
                        <span>Customize</span>
                    </div>
                    <div class="wizard-step" id="step4">
                        <div class="step-number">4</div>
                        <span>Generate</span>
                    </div>
                </div>
                
                <div class="wizard-body">
                    <!-- Step 1: Avatar Selection -->
                    <div class="wizard-content" id="content1">
                        <h3 class="mb-3">Select Your Avatar</h3>
                        <div class="avatar-selection" id="avatarSelection">
                            {% for avatar in avatars %}
                            <div class="avatar-option" data-id="{{ avatar.id }}" onclick="selectAvatar({{ avatar.id }})">
                                <img src="{{ avatar.avatar_url or 'https://via.placeholder.com/100' }}" 
                                     alt="{{ avatar.name }}" 
                                     class="avatar-image">
                                <div class="avatar-label">{{ avatar.name }}</div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    
                    <!-- Step 2: Content Input -->
                    <div class="wizard-content hidden" id="content2">
                        <h3 class="mb-3">Add Your Content</h3>
                        
                        <!-- Voice Recording -->
                        <div class="content-method" id="voiceContent">
                            <div class="recording-interface" id="recordingInterface">
                                <button class="record-button" id="recordButton" onclick="toggleRecording()">
                                    <i class="fas fa-microphone"></i>
                                </button>
                                <div class="recording-timer hidden" id="recordingTimer">00:00</div>
                                <div class="waveform hidden" id="waveform">
                                    <div class="waveform-bar"></div>
                                    <div class="waveform-bar"></div>
                                    <div class="waveform-bar"></div>
                                    <div class="waveform-bar"></div>
                                    <div class="waveform-bar"></div>
                                    <div class="waveform-bar"></div>
                                    <div class="waveform-bar"></div>
                                    <div class="waveform-bar"></div>
                                    <div class="waveform-bar"></div>
                                </div>
                                <audio id="audioPreview" controls class="hidden mt-3" style="width: 100%; max-width: 400px;"></audio>
                            </div>
                        </div>
                        
                        <!-- Text Input -->
                        <div class="content-method hidden" id="textContent">
                            <div class="text-input-container">
                                <textarea class="text-area" id="textInput" placeholder="Type your script here..."></textarea>
                                <div class="char-counter">
                                    <span id="charCount">0</span> / 5000 characters
                                </div>
                                
                                <h4 class="mt-3 mb-2">Select Voice</h4>
                                <div class="voice-selector">
                                    <div class="voice-option selected" data-voice="en-US-JennyNeural">
                                        <div class="voice-icon">🇺🇸</div>
                                        <div class="voice-details">
                                            <div class="voice-name">Jenny</div>
                                            <div class="voice-lang">English (US) - Female</div>
                                        </div>
                                    </div>
                                    <div class="voice-option" data-voice="en-US-GuyNeural">
                                        <div class="voice-icon">🇺🇸</div>
                                        <div class="voice-details">
                                            <div class="voice-name">Guy</div>
                                            <div class="voice-lang">English (US) - Male</div>
                                        </div>
                                    </div>
                                    <div class="voice-option" data-voice="en-GB-SoniaNeural">
                                        <div class="voice-icon">🇬🇧</div>
                                        <div class="voice-details">
                                            <div class="voice-name">Sonia</div>
                                            <div class="voice-lang">English (UK) - Female</div>
                                        </div>
                                    </div>
                                    <div class="voice-option" data-voice="da-DK-ChristelNeural">
                                        <div class="voice-icon">🇩🇰</div>
                                        <div class="voice-details">
                                            <div class="voice-name">Christel</div>
                                            <div class="voice-lang">Danish - Female</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Step 3: Customization -->
                    <div class="wizard-content hidden" id="content3">
                        <h3 class="mb-3">Customize Your Video</h3>
                        
                        <!-- Video Title -->
                        <div class="mb-4">
                            <label class="form-label">Video Title</label>
                            <input type="text" class="form-input" id="videoTitle" placeholder="Enter a title for your video...">
                        </div>
                        
                        <!-- Format Selection -->
                        <h4 class="mb-2">Video Format</h4>
                        <div class="format-selector">
                            <div class="format-option selected" data-format="16:9">
                                <div class="format-preview"></div>
                                <div class="format-name">Landscape</div>
                                <div class="format-desc">YouTube, Business</div>
                            </div>
                            <div class="format-option" data-format="9:16">
                                <div class="format-preview"></div>
                                <div class="format-name">Portrait</div>
                                <div class="format-desc">TikTok, Stories</div>
                            </div>
                            <div class="format-option" data-format="1:1">
                                <div class="format-preview"></div>
                                <div class="format-name">Square</div>
                                <div class="format-desc">Instagram, Social</div>
                            </div>
                        </div>
                        
                        <!-- Background Selection (Future) -->
                        <h4 class="mt-4 mb-2">Background <span class="tag coming-soon">Coming Soon</span></h4>
                        <div class="background-selector">
                            <div class="background-option selected">
                                <div class="background-preview" style="background: #008000;"></div>
                                <div class="background-label">Green Screen</div>
                            </div>
                            <div class="background-option" style="opacity: 0.5; cursor: not-allowed;">
                                <div class="background-preview" style="background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);"></div>
                                <div class="background-label">Gradient</div>
                            </div>
                            <div class="background-option" style="opacity: 0.5; cursor: not-allowed;">
                                <div class="background-preview" style="background: url('https://via.placeholder.com/150x100') center/cover;"></div>
                                <div class="background-label">Office</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Step 4: Generate -->
                    <div class="wizard-content hidden" id="content4">
                        <div class="text-center">
                            <div class="mb-4">
                                <i class="fas fa-check-circle" style="font-size: 4rem; color: var(--success);"></i>
                            </div>
                            <h3 class="mb-2">Ready to Generate!</h3>
                            <p class="mb-4" style="color: var(--gray-600);">Review your settings and click generate to create your video.</p>
                            
                            <div class="summary-box" style="background: var(--gray-50); padding: 2rem; border-radius: 1rem; text-align: left; max-width: 500px; margin: 0 auto;">
                                <div class="summary-item mb-2">
                                    <strong>Avatar:</strong> <span id="summaryAvatar">Not selected</span>
                                </div>
                                <div class="summary-item mb-2">
                                    <strong>Content Type:</strong> <span id="summaryContent">Not selected</span>
                                </div>
                                <div class="summary-item mb-2">
                                    <strong>Format:</strong> <span id="summaryFormat">16:9 Landscape</span>
                                </div>
                                <div class="summary-item">
                                    <strong>Title:</strong> <span id="summaryTitle">Untitled</span>
                                </div>
                            </div>
                            
                            <div class="progress-bar mt-4 hidden" id="progressBar">
                                <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                            </div>
                            
                            <p class="mt-2 hidden" id="progressText" style="color: var(--gray-600);">Processing your video...</p>
                        </div>
                    </div>
                </div>
                
                <div class="wizard-footer" style="padding: 1.5rem 2rem; border-top: 1px solid var(--gray-200); display: flex; justify-content: space-between; align-items: center;">
                    <button class="btn btn-secondary" onclick="previousStep()" id="prevBtn" disabled>
                        <i class="fas fa-arrow-left"></i> Previous
                    </button>
                    <button class="btn btn-primary" onclick="nextStep()" id="nextBtn">
                        Next <i class="fas fa-arrow-right"></i>
                    </button>
                    <button class="btn btn-success hidden" onclick="generateVideo()" id="generateBtn">
                        <i class="fas fa-magic"></i> Generate Video
                    </button>
                </div>
            </div>
            
            <button class="modal-close" onclick="closeModal()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    </div>
    
    <!-- Notification Container -->
    <div class="notification-container" id="notificationContainer"></div>
    
    <!-- JavaScript -->
    <script>
        // State Management
        const state = {
            currentStep: 1,
            selectedMethod: null,
            selectedAvatar: null,
            selectedFormat: '16:9',
            selectedVoice: 'en-US-JennyNeural',
            audioBlob: null,
            isRecording: false,
            recordingTime: 0,
            mediaRecorder: null,
            recordingInterval: null,
            user: {{ user|tojson }},
            avatars: {{ avatars|tojson }},
            videos: {{ videos|tojson }}
        };
        
        // Initialize
        document.addEventListener('DOMContentLoaded', async () => {
            setupEventListeners();
            showNotification('Welcome to MyAvatar Studio!', 'success');
            startAutoRefresh();
        });
        
        // Avatar Selection
        function selectAvatar(avatarId) {
            state.selectedAvatar = state.avatars.find(a => a.id === avatarId);
            
            // Update UI
            document.querySelectorAll('.avatar-option').forEach(el => {
                el.classList.toggle('selected', parseInt(el.dataset.id) === avatarId);
            });
            
            updateSummary();
        }
        
        // Creation Flow
        function startCreation(method) {
            state.selectedMethod = method;
            state.currentStep = 1;
            resetWizard();
            openModal();
            
            // Show/hide content based on method
            if (method === 'voice') {
                document.getElementById('voiceContent').classList.remove('hidden');
                document.getElementById('textContent').classList.add('hidden');
            } else {
                document.getElementById('textContent').classList.remove('hidden');
                document.getElementById('voiceContent').classList.add('hidden');
            }
        }
        
        function resetWizard() {
            state.currentStep = 1;
            state.selectedAvatar = null;
            state.audioBlob = null;
            state.selectedFormat = '16:9';
            
            // Reset UI
            document.querySelectorAll('.wizard-step').forEach((el, index) => {
                el.classList.toggle('active', index === 0);
                el.classList.remove('completed');
            });
            
            document.querySelectorAll('.wizard-content').forEach((el, index) => {
                el.classList.toggle('hidden', index !== 0);
            });
            
            document.getElementById('prevBtn').disabled = true;
            document.getElementById('nextBtn').classList.remove('hidden');
            document.getElementById('generateBtn').classList.add('hidden');
        }
        
        function nextStep() {
            if (validateStep(state.currentStep)) {
                if (state.currentStep < 4) {
                    // Mark current step as completed
                    document.querySelector(`#step${state.currentStep}`).classList.add('completed');
                    
                    // Move to next step
                    state.currentStep++;
                    updateWizardUI();
                }
            }
        }
        
        function previousStep() {
            if (state.currentStep > 1) {
                state.currentStep--;
                updateWizardUI();
            }
        }
        
        function validateStep(step) {
            switch (step) {
                case 1:
                    if (!state.selectedAvatar) {
                        showNotification('Please select an avatar', 'warning');
                        return false;
                    }
                    break;
                case 2:
                    if (state.selectedMethod === 'voice' && !state.audioBlob) {
                        showNotification('Please record audio first', 'warning');
                        return false;
                    }
                    if (state.selectedMethod === 'text' && !document.getElementById('textInput').value.trim()) {
                        showNotification('Please enter text', 'warning');
                        return false;
                    }
                    break;
                case 3:
                    if (!document.getElementById('videoTitle').value.trim()) {
                        showNotification('Please enter a title', 'warning');
                        return false;
                    }
                    break;
            }
            return true;
        }
        
        function updateWizardUI() {
            // Update steps
            document.querySelectorAll('.wizard-step').forEach((el, index) => {
                el.classList.toggle('active', index + 1 === state.currentStep);
            });
            
            // Update content
            document.querySelectorAll('.wizard-content').forEach((el, index) => {
                el.classList.toggle('hidden', index + 1 !== state.currentStep);
            });
            
            // Update buttons
            document.getElementById('prevBtn').disabled = state.currentStep === 1;
            
            if (state.currentStep === 4) {
                document.getElementById('nextBtn').classList.add('hidden');
                document.getElementById('generateBtn').classList.remove('hidden');
                updateSummary();
            } else {
                document.getElementById('nextBtn').classList.remove('hidden');
                document.getElementById('generateBtn').classList.add('hidden');
            }
        }
        
        function updateSummary() {
            if (state.selectedAvatar) {
                document.getElementById('summaryAvatar').textContent = state.selectedAvatar.name;
            }
            document.getElementById('summaryContent').textContent = 
                state.selectedMethod === 'voice' ? 'Voice Recording' : 'Text to Speech';
            document.getElementById('summaryFormat').textContent = 
                state.selectedFormat === '16:9' ? '16:9 Landscape' :
                state.selectedFormat === '9:16' ? '9:16 Portrait' : '1:1 Square';
            document.getElementById('summaryTitle').textContent = 
                document.getElementById('videoTitle').value || 'Untitled';
        }
        
        // Recording Functions
        async function toggleRecording() {
            if (state.isRecording) {
                stopRecording();
            } else {
                await startRecording();
            }
        }
        
        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                state.mediaRecorder = new MediaRecorder(stream);
                const chunks = [];
                
                state.mediaRecorder.ondataavailable = (e) => {
                    if (e.data.size > 0) chunks.push(e.data);
                };
                
                state.mediaRecorder.onstop = () => {
                    state.audioBlob = new Blob(chunks, { type: 'audio/webm' });
                    const audioUrl = URL.createObjectURL(state.audioBlob);
                    const audioPreview = document.getElementById('audioPreview');
                    audioPreview.src = audioUrl;
                    audioPreview.classList.remove('hidden');
                    stream.getTracks().forEach(track => track.stop());
                };
                
                state.mediaRecorder.start();
                state.isRecording = true;
                state.recordingTime = 0;
                
                // Update UI
                const recordBtn = document.getElementById('recordButton');
                recordBtn.classList.add('recording');
                recordBtn.innerHTML = '<i class="fas fa-stop"></i>';
                document.getElementById('recordingInterface').classList.add('active');
                document.getElementById('recordingTimer').classList.remove('hidden');
                document.getElementById('waveform').classList.remove('hidden');
                
                // Start timer
                state.recordingInterval = setInterval(() => {
                    state.recordingTime++;
                    const minutes = Math.floor(state.recordingTime / 60);
                    const seconds = state.recordingTime % 60;
                    document.getElementById('recordingTimer').textContent = 
                        `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                }, 1000);
                
            } catch (error) {
                console.error('Recording error:', error);
                showNotification('Failed to access microphone', 'error');
            }
        }
        
        function stopRecording() {
            if (state.mediaRecorder && state.isRecording) {
                state.mediaRecorder.stop();
                state.isRecording = false;
                
                // Clear timer
                if (state.recordingInterval) {
                    clearInterval(state.recordingInterval);
                    state.recordingInterval = null;
                }
                
                // Update UI
                const recordBtn = document.getElementById('recordButton');
                recordBtn.classList.remove('recording');
                recordBtn.innerHTML = '<i class="fas fa-microphone"></i>';
                document.getElementById('recordingInterface').classList.remove('active');
                document.getElementById('waveform').classList.add('hidden');
            }
        }
        
        // Video Generation
        async function generateVideo() {
            if (!validateStep(3)) return;
            
            try {
                // Show progress
                document.getElementById('generateBtn').disabled = true;
                document.getElementById('progressBar').classList.remove('hidden');
                document.getElementById('progressText').classList.remove('hidden');
                
                // Simulate progress
                let progress = 0;
                const progressInterval = setInterval(() => {
                    progress += Math.random() * 15;
                    if (progress > 90) progress = 90;
                    document.getElementById('progressFill').style.width = progress + '%';
                }, 500);
                
                // Prepare form data
                const formData = new FormData();
                formData.append('title', document.getElementById('videoTitle').value);
                formData.append('avatar_id', state.selectedAvatar.id);
                formData.append('video_format', state.selectedFormat);
                
                if (state.selectedMethod === 'voice') {
                    formData.append('audio', state.audioBlob, 'recording.webm');
                } else {
                    formData.append('text_content', document.getElementById('textInput').value);
                    formData.append('voice_id', state.selectedVoice);
                }
                
                // Send request
                const response = await fetch('/api/heygen', {
                    method: 'POST',
                    body: formData,
                    credentials: 'include'
                });
                
                clearInterval(progressInterval);
                
                if (response.ok) {
                    const result = await response.json();
                    document.getElementById('progressFill').style.width = '100%';
                    
                    showNotification('Video generation started successfully!', 'success');
                    
                    setTimeout(() => {
                        closeModal();
                        location.reload();
                    }, 2000);
                } else {
                    throw new Error('Failed to generate video');
                }
                
            } catch (error) {
                console.error('Generation error:', error);
                showNotification('Failed to generate video', 'error');
                document.getElementById('generateBtn').disabled = false;
                document.getElementById('progressBar').classList.add('hidden');
                document.getElementById('progressText').classList.add('hidden');
            }
        }
        
        // UI Functions
        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const mainContent = document.querySelector('.main-content');
            sidebar.classList.toggle('open');
            mainContent.classList.toggle('full-width');
        }
        
        function toggleTheme() {
            const currentTheme = document.body.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            // Update theme icon
            const themeBtn = document.querySelector('.header-btn i');
            themeBtn.className = newTheme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
        
        function openModal() {
            document.getElementById('creationModal').classList.add('show');
            document.body.style.overflow = 'hidden';
        }
        
        function closeModal() {
            document.getElementById('creationModal').classList.remove('show');
            document.body.style.overflow = '';
            resetWizard();
        }
        
        function showPremiumModal() {
            showNotification('Premium feature coming soon!', 'info');
        }
        
        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            
            const icons = {
                success: 'fa-check-circle',
                error: 'fa-exclamation-circle',
                warning: 'fa-exclamation-triangle',
                info: 'fa-info-circle'
            };
            
            notification.innerHTML = `
                <i class="fas ${icons[type]} notification-icon"></i>
                <div class="notification-content">
                    <div class="notification-title">${type.charAt(0).toUpperCase() + type.slice(1)}</div>
                    <div class="notification-message">${message}</div>
                </div>
                <button onclick="this.parentElement.remove()" style="background: none; border: none; color: var(--gray-500); cursor: pointer; margin-left: 1rem;">
                    <i class="fas fa-times"></i>
                </button>
            `;
            
            document.getElementById('notificationContainer').appendChild(notification);
            
            setTimeout(() => {
                notification.classList.add('show');
            }, 10);
            
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, 5000);
        }
        
        function downloadVideo(videoId) {
            window.open(`/api/videos/${videoId}/download`, '_blank');
        }
        
        // Event Listeners
        function setupEventListeners() {
            // Format selection
            document.querySelectorAll('.format-option').forEach(el => {
                el.addEventListener('click', function() {
                    state.selectedFormat = this.dataset.format;
                    document.querySelectorAll('.format-option').forEach(opt => {
                        opt.classList.remove('selected');
                    });
                    this.classList.add('selected');
                });
            });
            
            // Voice selection
            document.querySelectorAll('.voice-option').forEach(el => {
                el.addEventListener('click', function() {
                    state.selectedVoice = this.dataset.voice;
                    document.querySelectorAll('.voice-option').forEach(opt => {
                        opt.classList.remove('selected');
                    });
                    this.classList.add('selected');
                });
            });
            
            // Text input character count
            const textInput = document.getElementById('textInput');
            if (textInput) {
                textInput.addEventListener('input', function() {
                    document.getElementById('charCount').textContent = this.value.length;
                });
            }
            
            // Close modal on outside click
            document.getElementById('creationModal').addEventListener('click', function(e) {
                if (e.target === this) {
                    closeModal();
                }
            });
            
            // Load saved theme
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme) {
                document.body.setAttribute('data-theme', savedTheme);
                if (savedTheme === 'dark') {
                    document.querySelector('.header-btn i').className = 'fas fa-sun';
                }
            }
        }
        
        // Auto-refresh videos
        function startAutoRefresh() {
            setInterval(async () => {
                const hasProcessingVideos = state.videos.some(v => 
                    v.status === 'processing' || v.status === 'pending'
                );
                if (hasProcessingVideos) {
                    location.reload();
                }
            }, 10000);
        }
    </script>
</body>
</html>"""