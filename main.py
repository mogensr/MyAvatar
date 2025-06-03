"""
MyAvatar - Modular AI Avatar Video Platform
===========================================
Production-ready FastAPI app with HeyGen integration
INCLUDES: Direct HeyGen avatar import functionality

CHAPTER STRUCTURE:
1. Imports & Configuration
2. Enhanced Logging System
3. Database & Authentication Helpers
4. HeyGen & Cloudinary Helpers (WITH AUDIO CONVERSION)
5. Admin Dashboard & Logs
6. Create User Page
7. Enhanced User CRUD & Management
8. Avatar CRUD & Management
9. Video CRUD & Management
10. System Maintenance, Health, & Startup
11. Authentication & Session Management
12. API Endpoints for Dashboard
13. HeyGen Webhook Endpoint
14. Static Files & Template Setup
15. Main Entry Point
"""
#####################################################################
# CHAPTER 1: IMPORTS & CONFIGURATION
#####################################################################
import os
import textwrap
import logging
import traceback
import subprocess
from datetime import datetime, timedelta
from collections import deque
from typing import List, Dict, Optional, Any
import random

from fastapi import FastAPI, Request, status, Form, Depends, HTTPException, File, UploadFile, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from dotenv import load_dotenv
import sqlite3
import uuid
from passlib.context import CryptContext
import requests
import json
import shutil

# Load environment variables
load_dotenv()
SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret")
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")
HEYGEN_API_KEY = os.environ.get("HEYGEN_API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# Debug prints for troubleshooting
print(f"🔑 HEYGEN_API_KEY loaded: {HEYGEN_API_KEY[:20]}..." if HEYGEN_API_KEY else "❌ HEYGEN_API_KEY is EMPTY!")
print(f"🌐 BASE_URL: {BASE_URL}")
print(f"🌥️ CLOUDINARY_URL set: {'Yes' if CLOUDINARY_URL else 'No'}")

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# Test Cloudinary connection
try:
    print(f"🌥️ Cloudinary configured: {cloudinary.config().cloud_name}")
    print(f"🌥️ Cloudinary API Key: {'Set' if cloudinary.config().api_key else 'Missing'}")
except Exception as e:
    print(f"❌ Cloudinary error: {e}")

# Initialiser FastAPI
app = FastAPI(title="MyAvatar", description="AI Avatar Video Platform")

# Middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Importér router og tilføj til app
from modules.video_routes import router as video_router
app.include_router(video_router)

#####################################################################
# CHAPTER 2: ENHANCED LOGGING SYSTEM
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
# CHAPTER 3: DATABASE & AUTHENTICATION HELPERS
#####################################################################
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_db_connection():
    conn = sqlite3.connect("myavatar.db")
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    result = None
    if fetch_one:
        result = cur.fetchone()
    elif fetch_all:
        result = cur.fetchall()
    conn.commit()
    conn.close()
    return result

def get_current_user(request: Request):
    return request.session.get("user", None)

def init_database():
    """Initialize database tables and create admin user if needed"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if users table exists and what columns it has
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    users_table_exists = cur.fetchone() is not None
    
    if users_table_exists:
        # Check column names
        cur.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cur.fetchall()]
        
        # Handle old schema with useravatar_name
        if 'useravatar_name' in columns and 'username' not in columns:
            log_info("Migrating users table from useravatar_name to username", "Database")
            # Create new table with correct schema
            cur.execute("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Copy data
            cur.execute("""
                INSERT INTO users_new (id, username, email, hashed_password, is_admin, created_at)
                SELECT id, useravatar_name, email, hashed_password, is_admin, created_at FROM users
            """)
            # Drop old table and rename new one
            cur.execute("DROP TABLE users")
            cur.execute("ALTER TABLE users_new RENAME TO users")
    else:
        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # Check if avatars table exists and fix column names if needed
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='avatars'")
    avatars_table_exists = cur.fetchone() is not None
    
    if avatars_table_exists:
        cur.execute("PRAGMA table_info(avatars)")
        columns = [column[1] for column in cur.fetchall()]
        
        if 'avatar_avatar_name' in columns and 'avatar_name' not in columns:
            log_info("Migrating avatars table from avatar_avatar_name to avatar_name", "Database")
            # Create new table
            cur.execute("""
                CREATE TABLE avatars_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    avatar_name TEXT NOT NULL,
                    avatar_url TEXT,
                    heygen_avatar_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            # Copy data
            cur.execute("""
                INSERT INTO avatars_new (id, user_id, avatar_name, avatar_url, heygen_avatar_id, created_at)
                SELECT id, user_id, avatar_avatar_name, avatar_url, heygen_avatar_id, created_at FROM avatars
            """)
            # Drop old table and rename
            cur.execute("DROP TABLE avatars")
            cur.execute("ALTER TABLE avatars_new RENAME TO avatars")
    else:
        # Create avatars table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS avatars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                avatar_name TEXT NOT NULL,
                avatar_url TEXT,
                heygen_avatar_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
    
    # Create videos table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            avatar_id INTEGER,
            title TEXT NOT NULL,
            script TEXT,
            video_url TEXT,
            heygen_job_id TEXT,
            status TEXT DEFAULT 'pending',
            video_format TEXT DEFAULT '16:9',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (avatar_id) REFERENCES avatars (id)
        )
    """)
    
    # Create admin user if not exists
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        hashed_password = get_password_hash("admin123")
        cur.execute("""
            INSERT INTO users (username, email, hashed_password, is_admin) 
            VALUES (?, ?, ?, ?)
        """, ("admin", "admin@myavatar.com", hashed_password, 1))
        log_info("Admin user created (username: admin, password: admin123)", "Database")
    
    conn.commit()
    conn.close()
    log_info("Database tables initialized", "Database")

def update_database_schema():
    """Update database schema to match current requirements"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check videos table columns
        cur.execute("PRAGMA table_info(videos)")
        video_columns = [column[1] for column in cur.fetchall()]
        
        # Add missing columns to videos table
        if 'heygen_job_id' not in video_columns:
            log_info("Adding heygen_job_id column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN heygen_job_id TEXT")
            
        if 'status' not in video_columns:
            log_info("Adding status column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN status TEXT DEFAULT 'pending'")
            
        if 'video_format' not in video_columns:
            log_info("Adding video_format column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN video_format TEXT DEFAULT '16:9'")
            
        if 'video_url' not in video_columns:
            log_info("Adding video_url column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN video_url TEXT")
            
        if 'script' not in video_columns:
            log_info("Adding script column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN script TEXT")
        
        conn.commit()
        log_info("Database schema updated successfully", "Database")
        
    except Exception as e:
        log_error(f"Failed to update database schema: {str(e)}", "Database", e)
        conn.rollback()
    finally:
        conn.close()

#####################################################################
# CHAPTER 4: HEYGEN & CLOUDINARY HELPERS (WITH AUDIO CONVERSION)
#####################################################################

def convert_webm_to_m4a(webm_path: str, m4a_path: str) -> bool:
    """Convert WebM audio to M4A/AAC using ffmpeg"""
    try:
        # Convert WebM to M4A (AAC codec)
        cmd = [
            'ffmpeg',
            '-i', webm_path,      # Input file
            '-vn',                # No video
            '-ar', '44100',       # Audio sample rate
            '-ac', '2',           # Audio channels (stereo)
            '-c:a', 'aac',        # AAC codec
            '-b:a', '128k',       # Audio bitrate
            m4a_path,             # Output file
            '-y'                  # Overwrite output file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            log_error(f"FFmpeg conversion failed: {result.stderr}", "Audio")
            return False
            
        log_info(f"Successfully converted WebM to M4A", "Audio")
        return True
        
    except Exception as e:
        log_error(f"Audio conversion error: {str(e)}", "Audio", e)
        return False

def upload_audio_to_cloudinary(audio_path: str) -> str:
    """Upload audio to Cloudinary and return public URL"""
    try:
        # Check file extension to determine resource type
        file_ext = os.path.splitext(audio_path)[1].lower()
        
        if file_ext in ['.mp3', '.wav', '.m4a']:
            # Standard audio formats can use 'auto' or 'raw'
            result = cloudinary.uploader.upload(
                audio_path,
                resource_type="auto",
                folder="audio"
            )
        else:
            # WebM and other video containers need 'video' type
            result = cloudinary.uploader.upload(
                audio_path,
                resource_type="video",
                folder="audio"
            )
        
        secure_url = result.get("secure_url")
        log_info(f"Audio uploaded to Cloudinary: {secure_url}", "Cloudinary")
        return secure_url
        
    except Exception as e:
        log_error(f"Failed to upload audio to Cloudinary: {str(e)}", "Cloudinary", e)
        raise

def create_heygen_video(heygen_avatar_id: str, audio_url: str) -> dict:
    """Create video using HeyGen API v2"""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": heygen_avatar_id,
                "avatar_style": "normal"
            },
            "voice": {
                "type": "audio",
                "audio_url": audio_url
            }
        }],
        "test": False,
        "caption": False
    }
    
    try:
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error(f"HeyGen API error: {str(e)}", "HeyGen")
        raise

def check_heygen_status(video_id: str) -> dict:
    """Check video generation status"""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY
    }
    
    try:
        response = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error(f"HeyGen status check error: {str(e)}", "HeyGen")
        raise

def get_heygen_avatar_info(avatar_id: str) -> dict:
    """Get avatar information from HeyGen API"""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY
    }
    
    try:
        # First try V2 API
        response = requests.get(
            f"https://api.heygen.com/v2/avatars/{avatar_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            # V2 API response format
            if "data" in data:
                return data["data"]
            return data
        
        # If V2 fails, try V1 API
        response = requests.get(
            f"https://api.heygen.com/v1/avatar.list",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])
            # Find the avatar in the list
            for avatar in avatars:
                if avatar.get("avatar_id") == avatar_id:
                    return avatar
            
        raise Exception(f"Avatar with ID '{avatar_id}' not found in HeyGen. Please ensure the avatar exists and you have access to it.")
            
    except Exception as e:
        log_error(f"Failed to get HeyGen avatar: {str(e)}", "HeyGen")
        raise

def list_heygen_avatars() -> list:
    """List all available avatars from HeyGen"""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY
    }
    
    try:
        response = requests.get(
            "https://api.heygen.com/v1/avatar.list",
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("error"):
            log_error(f"HeyGen list avatars error: {data.get('error')}", "HeyGen")
            return []
            
        return data.get("data", {}).get("avatars", [])
    except Exception as e:
        log_error(f"Failed to list HeyGen avatars: {str(e)}", "HeyGen")
        return []

def upload_avatar_to_cloudinary(image_file: UploadFile, user_id: int):
    # Save to temp file
    temp_path = f"temp_{user_id}_{image_file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image_file.file, buffer)
    result = cloudinary.uploader.upload(temp_path, folder="avatars")
    os.remove(temp_path)
    return result.get("secure_url")

def upload_avatar_locally(image_file: UploadFile, user_id: int):
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{user_id}_{image_file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image_file.file, buffer)
    return f"/uploads/{user_id}_{image_file.filename}"

#####################################################################
# CHAPTER 5: ADMIN DASHBOARD & LOGS
#####################################################################
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    try:
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        admin_html = textwrap.dedent("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .header { background: #dc2626; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .btn { background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; border: none; cursor: pointer; }
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
                    <a href="/dashboard" class="btn">User Dashboard</a>
                    <a href="/admin/logs" class="btn btn-success">System Logs</a>
                    <a href="/auth/logout" class="btn">Log Out</a>
                </div>
            </div>
            <div class="card">
                <h2>👥 User & Avatar Management</h2>
                <p>Manage users, their avatars, and system access.</p>
                <a href="/admin/users" class="btn">Manage Users</a>
                <a href="/admin/create-user" class="btn">Create New User</a>
                <a href="/admin/avatars" class="btn">View All Avatars</a>
            </div>
            <div class="card">
                <h2>🎬 Video Management</h2>
                <p>View and manage all generated videos.</p>
                <a href="/admin/videos" class="btn">View All Videos</a>
            </div>
            <div class="card">
                <h2>📊 System Status</h2>
                <p><strong>HeyGen API:</strong> ✅ Available</p>
                <p><strong>Storage:</strong> ✅ Cloudinary CDN</p>
                <p><strong>Database:</strong> ✅ SQLite</p>
                <p><strong>Webhook:</strong> ✅ /api/heygen/webhook</p>
                <p><strong>Logging:</strong> ✅ Enhanced Error Tracking</p>
                <p><strong>Audio Processing:</strong> ✅ FFmpeg WebM to M4A</p>
            </div>
            <div class="card">
                <h2>🧹 System Maintenance</h2>
                <p>Tools for system maintenance and troubleshooting.</p>
                <a href="/admin/quickclean" class="btn btn-danger">Total Reset (Delete All)</a>
                <a href="/admin/logs" class="btn btn-success">View System Logs</a>
            </div>
        </body>
        </html>
        """)
        return HTMLResponse(content=admin_html)
    except Exception as e:
        log_error("Admin dashboard failed", "Admin", e)
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@app.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs(request: Request):
    try:
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

        recent_logs = log_handler.get_recent_logs(200)
        error_logs = log_handler.get_error_logs(50)

        logs_html = """
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
            <a href="/admin" class="btn">Back to Admin</a>
            <button onclick="location.reload()" class="btn">Refresh</button>
        </div>
    </div>
    <div class="card">
        <h3>Recent Activity (Last 200 entries)</h3>
        <div style='max-height: 600px; overflow-y: scroll; background: #111; padding: 10px; border-radius: 4px;'>
"""
        for log in recent_logs:
            level_class = f"log-{log['level'].lower()}"
            logs_html += (
                f"<div class='log-entry {level_class}'>"
                f"<span class='timestamp'>[{log['timestamp']}]</span> "
                f"<span class='module'>{log['module']}</span>: "
                f"{log['message']}</div>"
            )
        logs_html += """
        </div>
    </div>
    <div class="card">
        <h3>ℹ️ Log Information</h3>
        <p>• Logs auto-refresh every 30 seconds</p>
        <p>• Showing last {recent_count} entries</p>
        <p>• {error_count} recent errors</p>
    </div>
</body>
</html>
"""
        logs_html = logs_html.replace("{recent_count}", str(len(recent_logs))).replace("{error_count}", str(len(error_logs)))
        return HTMLResponse(content=logs_html)
    except Exception as e:
        log_error("Admin logs page failed", "Admin", e)
        return HTMLResponse("<h1>Error loading logs</h1><a href='/admin'>Back to Admin</a>")

#####################################################################
# CHAPTER 6: CREATE USER PAGE
#####################################################################
@app.get("/admin/create-user", response_class=HTMLResponse)
async def create_user_page(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Create New User</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h2 { color: #333; }
                input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }
                button { background: #4f46e5; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }
                button:hover { background: #3730a3; }
                .error { color: red; margin: 10px 0; }
                a { color: #4f46e5; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Create New User</h2>
                <form method="post" action="/admin/create-user">
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="email" name="email" placeholder="Email" required>
                    <input type="password" name="password" placeholder="Password" required>
                    <label>
                        <input type="checkbox" name="is_admin"> Admin User
                    </label>
                    <br><br>
                    <button type="submit">Create User</button>
                </form>
                <br>
                <a href="/admin">← Back to Admin</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    except Exception as e:
        log_error("Create user page failed", "Admin", e)
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/create-user")
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: Optional[str] = Form(None)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        hashed_password = get_password_hash(password)
        is_admin_val = 1 if is_admin else 0
        
        execute_query(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            (username, email, hashed_password, is_admin_val)
        )
        
        log_info(f"New user created: {username} (admin: {bool(is_admin_val)})", "Admin")
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_302_FOUND)
        
    except Exception as e:
        log_error("Create user failed", "Admin", e)
        return HTMLResponse("<h1>Error creating user</h1><p>Username or email may already exist.</p><a href='/admin/create-user'>Try again</a>")

#####################################################################
# CHAPTER 7: ENHANCED USER CRUD & MANAGEMENT
#####################################################################
@app.get("/admin/users", response_class=HTMLResponse)
async def list_users(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        users = execute_query("SELECT id, username, email, is_admin, created_at FROM users", fetch_all=True)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>User Management</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 1000px; margin: 0 auto; }
                h2 { color: #333; }
                table { width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                th { background: #4f46e5; color: white; padding: 12px; text-align: left; }
                td { padding: 12px; border-bottom: 1px solid #e0e0e0; }
                tr:hover { background: #f5f5f5; }
                .btn { padding: 6px 12px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 2px; }
                .btn-primary { background: #4f46e5; color: white; }
                .btn-primary:hover { background: #3730a3; }
                .btn-danger { background: #dc2626; color: white; }
                .btn-danger:hover { background: #b91c1c; }
                .btn-success { background: #16a34a; color: white; }
                .btn-success:hover { background: #15803d; }
                .admin-badge { background: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
                .user-badge { background: #6b7280; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
                .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>User Management</h2>
                    <div>
                        <a href="/admin/create-user" class="btn btn-success">+ Create New User</a>
                        <a href="/admin" class="btn btn-primary">← Back to Admin</a>
                    </div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Type</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for user in users:
            created_date = user['created_at'][:10] if user['created_at'] else 'Unknown'
            user_type = '<span class="admin-badge">Admin</span>' if user['is_admin'] else '<span class="user-badge">User</span>'
            
            html += f"""
                <tr>
                    <td>{user['id']}</td>
                    <td><strong>{user['username']}</strong></td>
                    <td>{user['email']}</td>
                    <td>{user_type}</td>
                    <td>{created_date}</td>
                    <td>
                        <a href='/admin/user/{user['id']}' class="btn btn-primary">Manage</a>
                        <a href='/admin/user/{user['id']}/delete' class="btn btn-danger" 
                           onclick="return confirm('Are you sure you want to delete this user?')">Delete</a>
                    </td>
                </tr>
            """
        
        html += """
                    </tbody>
                </table>
                
                <div style="margin-top: 20px; padding: 20px; background: white; border-radius: 8px;">
                    <h3>Quick Stats</h3>
                    <p>Total Users: <strong>{}</strong></p>
                    <p>Administrators: <strong>{}</strong></p>
                    <p>Regular Users: <strong>{}</strong></p>
                </div>
            </div>
        </body>
        </html>
        """.format(
            len(users),
            sum(1 for u in users if u['is_admin']),
            sum(1 for u in users if not u['is_admin'])
        )
        
        return HTMLResponse(html)
    except Exception as e:
        log_error("List users failed", "Admin", e)
        return HTMLResponse("<h1>Error loading users</h1><a href='/admin'>Back to Admin</a>")

@app.get("/admin/user/{user_id}", response_class=HTMLResponse)
async def edit_user(request: Request, user_id: int):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Get user details
        user = execute_query("SELECT id, username, email, is_admin FROM users WHERE id = ?", (user_id,), fetch_one=True)
        if not user:
            return HTMLResponse("<h2>User not found</h2><a href='/admin/users'>Back</a>")
        
        # Get user's avatars
        avatars = execute_query(
            "SELECT id, avatar_name, avatar_url, heygen_avatar_id, created_at FROM avatars WHERE user_id = ?",
            (user_id,),
            fetch_all=True
        )
        
        # Get user's videos count
        video_count = execute_query(
            "SELECT COUNT(*) as count FROM videos WHERE user_id = ?",
            (user_id,),
            fetch_one=True
        )
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Edit User: {user['username']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                h2 {{ color: #333; }}
                .btn {{ padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; border: none; cursor: pointer; }}
                .btn-primary {{ background: #4f46e5; color: white; }}
                .btn-primary:hover {{ background: #3730a3; }}
                .btn-danger {{ background: #dc2626; color: white; }}
                .btn-danger:hover {{ background: #b91c1c; }}
                .btn-success {{ background: #16a34a; color: white; }}
                .btn-success:hover {{ background: #15803d; }}
                input, select {{ width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }}
                .avatar-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; margin-top: 15px; }}
                .avatar-card {{ text-align: center; padding: 10px; border: 1px solid #e0e0e0; border-radius: 8px; }}
                .avatar-card img {{ width: 100px; height: 100px; border-radius: 50%; object-fit: cover; }}
                .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                .heygen-id {{ font-size: 10px; color: #666; word-break: break-all; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>User Management: {user['username']}</h1>
                
                <div class="card">
                    <h3>User Information</h3>
                    <div class="info-grid">
                        <div>
                            <p><strong>User ID:</strong> {user['id']}</p>
                            <p><strong>Username:</strong> {user['username']}</p>
                            <p><strong>Email:</strong> {user['email']}</p>
                        </div>
                        <div>
                            <p><strong>Account Type:</strong> {'Administrator' if user['is_admin'] else 'Regular User'}</p>
                            <p><strong>Total Videos:</strong> {video_count['count'] if video_count else 0}</p>
                            <p><strong>Total Avatars:</strong> {len(avatars) if avatars else 0}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Edit User Details</h3>
                    <form method='post' action='/admin/user/{user['id']}'>
                        <label>Email:</label>
                        <input type='email' name='email' value='{user['email']}' required>
                        
                        <label style="display: block; margin-top: 10px;">
                            <input type='checkbox' name='is_admin' {'checked' if user['is_admin'] else ''}> 
                            Administrator Access
                        </label>
                        
                        <button type='submit' class="btn btn-primary">Save Changes</button>
                    </form>
                </div>
                
                <div class="card">
                    <h3>Change Password</h3>
                    <form method='post' action='/admin/user/{user['id']}/reset-password'>
                        <label>New Password:</label>
                        <div style="position: relative;">
                            <input type='password' id='password-field' name='new_password' required minlength="6" style="padding-right: 40px;">
                            <span onclick="togglePassword()" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); cursor: pointer; user-select: none;">
                                👁️
                            </span>
                        </div>
                        <small style="color: #666;">Minimum 6 characters</small>
                        <br><br>
                        <button type='submit' class="btn btn-success">Save New Password</button>
                    </form>
                    
                    <script>
                        function togglePassword() {{
                            const passwordField = document.getElementById('password-field');
                            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
                            passwordField.setAttribute('type', type);
                        }}
                    </script>
                </div>
                
                <div class="card">
                    <h3>User's Avatars</h3>
        """
        
        if avatars:
            html += '<div class="avatar-grid">'
            for avatar in avatars:
                html += f"""
                    <div class="avatar-card">
                        <img src="{avatar['avatar_url']}" alt="{avatar['avatar_name']}">
                        <p><strong>{avatar['avatar_name']}</strong></p>
                        <p class="heygen-id">HeyGen: {avatar['heygen_avatar_id'] or 'Not set'}</p>
                        <small>Created: {avatar['created_at'][:10]}</small>
                        <br>
                        <a href="/admin/avatar/{avatar['id']}" class="btn btn-sm btn-primary">Edit</a>
                    </div>
                """
            html += '</div>'
        else:
            html += '<p>No avatars yet</p>'
        
        html += f"""
                    <hr style="margin: 20px 0;">
                    
                    <!-- Import from HeyGen Option -->
                    <div style="background: #f0f9ff; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <h4>🚀 Quick Import from HeyGen</h4>
                        <form method='post' action='/admin/user/{user['id']}/import-avatar-heygen' style="display: flex; gap: 10px; align-items: flex-end;">
                            <div style="flex: 1;">
                                <label>HeyGen Avatar ID:</label>
                                <input type='text' name='heygen_avatar_id' required placeholder='e.g., b5038ba7bd9b4d94ac6b5c9ea70f8d28' style="width: 100%;">
                                <small style="color: #666;">Enter the avatar ID from your HeyGen dashboard</small>
                            </div>
                            <button type='submit' class="btn btn-success" style="white-space: nowrap;">
                                Import from HeyGen
                            </button>
                        </form>
                    </div>
                    
                    <!-- Traditional Upload Option -->
                    <div style="background: #f8f8f8; padding: 20px; border-radius: 8px;">
                        <h4>📤 Manual Upload</h4>
                        <form method='post' action='/admin/user/{user['id']}/upload-avatar' enctype='multipart/form-data'>
                            <label>Avatar Name:</label>
                            <input type='text' name='avatar_name' required placeholder='e.g., Professional Avatar'>
                            
                            <label>HeyGen Avatar ID:</label>
                            <input type='text' name='heygen_avatar_id' required placeholder='e.g., b5038ba7bd9b4d94ac6b5c9ea70f8d28'>
                            <small style="color: #666;">Get this ID from your HeyGen dashboard</small>
                            
                            <label style="margin-top: 10px;">Avatar Image:</label>
                            <input type='file' name='avatar_image' accept='image/*' required>
                            <small style="color: #666;">Upload a preview image for this avatar</small>
                            
                            <button type='submit' class="btn btn-success" style="margin-top: 15px;">Upload Avatar</button>
                        </form>
                    </div>
                </div>
                
                <div style="margin-top: 20px;">
                    <a href='/admin/users' class="btn btn-primary">← Back to Users</a>
                    <a href='/admin' class="btn btn-primary">← Back to Admin</a>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("Edit user failed", "Admin", e)
        return HTMLResponse("<h1>Error loading user</h1><a href='/admin/users'>Back</a>")

@app.post("/admin/user/{user_id}", response_class=HTMLResponse)
async def update_user(request: Request, user_id: int, email: str = Form(...), is_admin: Optional[str] = Form(None)):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        is_admin_val = 1 if is_admin else 0
        execute_query("UPDATE users SET email = ?, is_admin = ? WHERE id = ?", (email, is_admin_val, user_id))
        return RedirectResponse(url=f"/admin/user/{user_id}", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Update user failed", "Admin", e)
        return HTMLResponse("<h1>Error updating user</h1><a href='/admin/users'>Back</a>")

@app.post("/admin/user/{user_id}/reset-password")
async def reset_user_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        hashed_password = get_password_hash(new_password)
        execute_query(
            "UPDATE users SET hashed_password = ? WHERE id = ?",
            (hashed_password, user_id)
        )
        
        user = execute_query("SELECT username FROM users WHERE id = ?", (user_id,), fetch_one=True)
        log_info(f"Password reset for user {user['username']} by admin {admin['username']}", "Admin")
        
        return RedirectResponse(url=f"/admin/user/{user_id}", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Password reset failed", "Admin", e)
        return HTMLResponse("<h1>Error resetting password</h1><a href='/admin/users'>Back</a>")

@app.post("/admin/user/{user_id}/upload-avatar")
async def upload_avatar_for_user(
    request: Request,
    user_id: int,
    avatar_name: str = Form(...),
    heygen_avatar_id: str = Form(...),
    avatar_image: UploadFile = File(...)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Upload avatar image
        if CLOUDINARY_URL:
            avatar_url = upload_avatar_to_cloudinary(avatar_image, user_id)
        else:
            avatar_url = upload_avatar_locally(avatar_image, user_id)
        
        # Save to database with HeyGen ID
        execute_query(
            "INSERT INTO avatars (user_id, avatar_name, avatar_url, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (user_id, avatar_name, avatar_url, heygen_avatar_id)
        )
        
        user = execute_query("SELECT username FROM users WHERE id = ?", (user_id,), fetch_one=True)
        log_info(f"Avatar '{avatar_name}' created for user {user['username']} with HeyGen ID {heygen_avatar_id}", "Admin")
        
        return RedirectResponse(url=f"/admin/user/{user_id}", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Avatar upload failed", "Admin", e)
        return HTMLResponse(f"<h1>Error uploading avatar</h1><p>{str(e)}</p><a href='/admin/users'>Back</a>")

@app.post("/admin/user/{user_id}/import-avatar-heygen")
async def import_avatar_from_heygen(
    request: Request,
    user_id: int,
    heygen_avatar_id: str = Form(...)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Since we can't fetch avatar details from HeyGen API (403 Forbidden),
        # we'll just save the ID and use a default name/thumbnail
        log_info(f"Importing avatar {heygen_avatar_id} for user {user_id}", "Admin")
        
        # Use a default name based on the ID
        avatar_name = f"HeyGen Avatar ({heygen_avatar_id[:8]}...)"
        
        # Use a placeholder thumbnail since we can't fetch from HeyGen
        # You can replace this with a better default image
        thumbnail_url = "https://via.placeholder.com/200x200?text=HeyGen+Avatar"
        
        # Check if avatar already exists for this user
        existing = execute_query(
            "SELECT id FROM avatars WHERE user_id = ? AND heygen_avatar_id = ?",
            (user_id, heygen_avatar_id),
            fetch_one=True
        )
        
        if existing:
            return HTMLResponse(
                f"<h1>Avatar already exists</h1><p>This HeyGen avatar is already imported for this user.</p><a href='/admin/user/{user_id}'>Back</a>"
            )
        
        # Save to database
        execute_query(
            "INSERT INTO avatars (user_id, avatar_name, avatar_url, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (user_id, avatar_name, thumbnail_url, heygen_avatar_id)
        )
        
        user = execute_query("SELECT username FROM users WHERE id = ?", (user_id,), fetch_one=True)
        log_info(f"Avatar '{avatar_name}' imported from HeyGen for user {user['username']}", "Admin")
        
        return RedirectResponse(url=f"/admin/user/{user_id}", status_code=status.HTTP_302_FOUND)
        
    except Exception as e:
        log_error("HeyGen avatar import failed", "Admin", e)
        return HTMLResponse(f"<h1>Error importing avatar from HeyGen</h1><p>{str(e)}</p><a href='/admin/user/{user_id}'>Back</a>")

@app.get("/admin/user/{user_id}/delete")
async def delete_user(request: Request, user_id: int):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Don't allow deleting yourself
        if user_id == admin["id"]:
            return HTMLResponse("<h1>Cannot delete your own account</h1><a href='/admin/users'>Back</a>")
        
        # Delete user's videos, avatars, and then the user
        execute_query("DELETE FROM videos WHERE user_id = ?", (user_id,))
        execute_query("DELETE FROM avatars WHERE user_id = ?", (user_id,))
        execute_query("DELETE FROM users WHERE id = ?", (user_id,))
        
        log_info(f"User ID {user_id} deleted by admin {admin['username']}", "Admin")
        
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Delete user failed", "Admin", e)
        return HTMLResponse("<h1>Error deleting user</h1><a href='/admin/users'>Back</a>")

#####################################################################
# CHAPTER 8: AVATAR CRUD & MANAGEMENT
#####################################################################
@app.get("/admin/avatars", response_class=HTMLResponse)
async def list_avatars(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Get all avatars with user information
        avatars = execute_query("""
            SELECT a.id, a.avatar_name, a.avatar_url, a.created_at, 
                   u.username, u.id as user_id
            FROM avatars a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
        """, fetch_all=True)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>All Avatars</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
                .avatar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
                .avatar-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
                .avatar-card img { width: 120px; height: 120px; border-radius: 50%; object-fit: cover; margin-bottom: 10px; }
                .btn { padding: 6px 12px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 2px; }
                .btn-primary { background: #4f46e5; color: white; }
                .btn-primary:hover { background: #3730a3; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>All Avatars</h2>
                    <a href="/admin" class="btn btn-primary">← Back to Admin</a>
                </div>
                
                <div class="avatar-grid">
        """
        
        if avatars:
            for avatar in avatars:
                html += f"""
                    <div class="avatar-card">
                        <img src="{avatar['avatar_url']}" alt="{avatar['avatar_name']}">
                        <h4>{avatar['avatar_name']}</h4>
                        <p>User: <strong>{avatar['username']}</strong></p>
                        <small>Created: {avatar['created_at'][:10]}</small>
                        <br><br>
                        <a href="/admin/avatar/{avatar['id']}" class="btn btn-primary">Edit</a>
                    </div>
                """
        else:
            html += '<p>No avatars created yet</p>'
        
        html += """
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("List avatars failed", "Admin", e)
        return HTMLResponse("<h1>Error loading avatars</h1><a href='/admin'>Back to Admin</a>")

@app.get("/admin/avatar/{avatar_id}", response_class=HTMLResponse)
async def edit_avatar(request: Request, avatar_id: int):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        avatar = execute_query("SELECT id, user_id, avatar_name, avatar_url FROM avatars WHERE id = ?", (avatar_id,), fetch_one=True)
        if not avatar:
            return HTMLResponse("<h2>Avatar not found</h2><a href='/admin/avatars'>Back</a>")
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Edit Avatar</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
                input {{ width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }}
                button {{ background: #4f46e5; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
                button:hover {{ background: #3730a3; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Edit Avatar: {avatar['avatar_name']}</h2>
                <img src="{avatar['avatar_url']}" width="200" style="border-radius: 50%;"><br><br>
                
                <form method='post' action='/admin/avatar/{avatar['id']}' enctype='multipart/form-data'>
                    <label>Avatar Name:</label>
                    <input type='text' name='avatar_name' value='{avatar['avatar_name']}' required><br><br>
                    
                    <label>Replace Image:</label>
                    <input type='file' name='avatar_image' accept='image/*'><br><br>
                    
                    <button type='submit'>Update Avatar</button>
                </form>
                <br>
                <a href='/admin/avatars'>← Back to Avatars</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("Edit avatar failed", "Admin", e)
        return HTMLResponse("<h1>Error loading avatar</h1><a href='/admin/avatars'>Back</a>")


#####################################################################
# CHAPTER 9: VIDEO CRUD & MANAGEMENT
#####################################################################
@app.get("/admin/videos", response_class=HTMLResponse)
async def list_videos(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        videos = execute_query("""
            SELECT v.id, v.title, v.video_url, v.status, v.created_at,
                   u.username, a.avatar_name
            FROM videos v
            JOIN users u ON v.user_id = u.id
            LEFT JOIN avatars a ON v.avatar_id = a.id
            ORDER BY v.created_at DESC
        """, fetch_all=True)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>All Videos</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; }
                table { width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                th { background: #4f46e5; color: white; padding: 12px; text-align: left; }
                td { padding: 12px; border-bottom: 1px solid #e0e0e0; }
                .btn { padding: 6px 12px; text-decoration: none; border-radius: 4px; display: inline-block; }
                .btn-primary { background: #4f46e5; color: white; }
                .status-completed { background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
                .status-processing { background: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
                .status-pending { background: #6b7280; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>All Videos</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Title</th>
                            <th>User</th>
                            <th>Avatar</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        if videos:
            for video in videos:
                status_class = f"status-{video['status']}"
                html += f"""
                    <tr>
                        <td>{video['id']}</td>
                        <td>{video['title']}</td>
                        <td>{video['username']}</td>
                        <td>{video['avatar_name'] or 'N/A'}</td>
                        <td><span class="{status_class}">{video['status']}</span></td>
                        <td>{video['created_at'][:16]}</td>
                        <td>
                            <a href='/admin/video/{video['id']}' class="btn btn-primary">View</a>
                        </td>
                    </tr>
                """
        else:
            html += '<tr><td colspan="7">No videos yet</td></tr>'
        
        html += """
                    </tbody>
                </table>
                <br>
                <a href='/admin' class="btn btn-primary">← Back to Admin</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("List videos failed", "Admin", e)
        return HTMLResponse("<h1>Error loading videos</h1><a href='/admin'>Back to Admin</a>")

@app.get("/admin/video/{video_id}", response_class=HTMLResponse)
async def view_video(request: Request, video_id: int):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        video = execute_query("SELECT * FROM videos WHERE id = ?", (video_id,), fetch_one=True)
        if not video:
            return HTMLResponse("<h2>Video not found</h2><a href='/admin/videos'>Back</a>")
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Video Details</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Video: {video['title']}</h2>
                <p><strong>Status:</strong> {video['status']}</p>
                <p><strong>Created:</strong> {video['created_at']}</p>
                {f'<video src="{video["video_url"]}" controls width="600"></video>' if video['video_url'] else '<p>Video not yet generated</p>'}
                <br><br>
                <a href='/admin/videos'>← Back to Videos</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("View video failed", "Admin", e)
        return HTMLResponse("<h1>Error loading video</h1><a href='/admin/videos'>Back</a>")

#####################################################################
# CHAPTER 10: SYSTEM MAINTENANCE, HEALTH, & STARTUP
#####################################################################
@app.get("/admin/quickclean")
async def quick_clean(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return HTMLResponse("Access denied")
        execute_query("DELETE FROM videos")
        execute_query("DELETE FROM avatars")
        execute_query("DELETE FROM users WHERE is_admin = 0")
        log_warning("TOTAL RESET initiated by admin", "Admin")
        html = textwrap.dedent(f"""
            <h2>[RESET] TOTAL RESET COMPLETE!</h2>
            <a href='/admin/users'>Start Fresh - Create Users</a><br>
            <a href='/admin'>Back to Admin Panel</a>
        """)
        return HTMLResponse(html.strip())
    except Exception as e:
        log_error("Admin quickclean failed", "Admin", e)
        return HTMLResponse("<h1>Error during cleanup</h1><a href='/admin'>Back to Admin</a>")

@app.get("/health", response_class=HTMLResponse)
async def health_check():
    return HTMLResponse("OK")

@app.on_event("startup")
async def startup_event():
    init_database()  # Initialize database tables
    update_database_schema()  # Update schema for existing databases
    log_info("MyAvatar application startup initiated", "System")
    log_info("Database initialized", "System")
    log_info(f"HeyGen API Key: {'✓ Set' if HEYGEN_API_KEY else '✗ Missing'}", "System")
    log_info(f"Base URL: {BASE_URL}", "System")
    log_info("Avatar Management: ✓ Available", "System")
    log_info("Storage: Cloudinary CDN with local fallback", "System")
    log_info(f"Webhook Endpoint: {BASE_URL}/api/heygen/webhook", "System")
    log_info("Enhanced logging system enabled", "System")
    log_info("Audio Processing: FFmpeg WebM to M4A conversion", "System")
    log_info("🚀 MyAvatar application startup complete", "System")

#####################################################################
# CHAPTER 11: AUTHENTICATION & SESSION MANAGEMENT
#####################################################################
@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("portal/login.html", {"request": request})

@app.post("/auth/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(None), useravatar_name: str = Form(None), password: str = Form(...)):
    try:
        # Support both field names for backwards compatibility
        login_username = username or useravatar_name
        if not login_username:
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "error": "Username is required"
            })
            
        user = execute_query("SELECT id, username, hashed_password, is_admin FROM users WHERE username = ?", (login_username,), fetch_one=True)
        if user and verify_password(password, user["hashed_password"]):    
            request.session["user"] = {"id": user["id"], "username": user["username"], "is_admin": user["is_admin"]}
            
            # Redirect based on user type
            if user["is_admin"]:
                return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
            else:
                return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        else:
            return templates.TemplateResponse("portal/login.html", {
                "request": request,
                "error": "Invalid username or password"
            })
    except Exception as e:
        log_error("Login failed", "Auth", e)
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "error": "An error occurred during login. Please try again."
        })
    
@app.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    # Serve the modern dashboard with necessary JavaScript files
    return RedirectResponse(url="/static/dashboard.html", status_code=status.HTTP_302_FOUND)

#####################################################################
# CHAPTER 12: API ENDPOINTS FOR DASHBOARD
#####################################################################

# NEW: API Service JavaScript - this provides the missing APIService object
@app.get("/static/js/api-service.js", response_class=PlainTextResponse)
async def get_api_service():
    """Provide the APIService module that the dashboard expects"""
    api_service_js = """
// API Service for MyAvatar Dashboard
window.APIService = {
    async getAvatars() {
        const response = await fetch('/api/avatars', {
            credentials: 'include'
        });
        if (!response.ok) throw new Error('Failed to fetch avatars');
        return await response.json();
    },
    
    async getVideos() {
        const response = await fetch('/api/videos', {
            credentials: 'include'
        });
        if (!response.ok) throw new Error('Failed to fetch videos');
        return await response.json();
    },
    
    async generateVideo(audioBlob, avatarId) {
        const formData = new FormData();
        const audioFile = new File([audioBlob], 'recording.webm', {
            type: audioBlob.type || 'audio/webm'
        });
        formData.append('audio', audioFile);
        formData.append('avatar_id', avatarId.toString());
        
        const response = await fetch('/api/video/generate', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate video');
        }
        
        return await response.json();
    },
    
    async pollVideoStatus(videoId, onProgress) {
        let attempts = 0;
        const maxAttempts = 60; // 5 minutes max
        
        while (attempts < maxAttempts) {
            const response = await fetch(`/api/video/status/${videoId}`, {
                credentials: 'include'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to check status');
            }
            
            const data = await response.json();
            
            if (data.status === 'completed') {
                if (onProgress) onProgress(100);
                return data;
            } else if (data.status === 'failed') {
                throw new Error('Video generation failed');
            } else {
                if (onProgress) onProgress(data.progress || 50);
                await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds
                attempts++;
            }
        }
        
        throw new Error('Video generation timed out');
    }
};

// App Configuration
window.AppConfig = {
    ui: {
        maxRecordingTime: 300,
        text: {
            selectAvatarFirst: 'Vælg venligst en avatar først',
            noVideosMessage: 'Ingen videoer endnu',
            recordTitle: 'Optag Video',
            generationFailed: 'Video generering fejlede'
        },
        logo: '/static/logo.png'
    },
    api: {
        baseUrl: ''
    }
};

// Audio Recorder Class
window.AudioRecorder = class AudioRecorder {
    constructor(options = {}) {
        this.options = options;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.stream = null;
        this.startTime = null;
        this.timerInterval = null;
    }
    
    async start() {
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.mediaRecorder = new MediaRecorder(this.stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        this.audioChunks = [];
        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                this.audioChunks.push(event.data);
            }
        };
        
        this.mediaRecorder.start();
        this.startTime = Date.now();
        
        // Start timer
        if (this.options.onTick) {
            this.timerInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
                const remaining = this.options.maxSeconds - elapsed;
                this.options.onTick(remaining);
                
                if (remaining <= 0) {
                    this.stop();
                }
            }, 1000);
        }
    }
    
    async stop() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        
        return new Promise((resolve) => {
            this.mediaRecorder.onstop = () => {
                this.stream.getTracks().forEach(track => track.stop());
                resolve();
            };
            this.mediaRecorder.stop();
        });
    }
    
    async getBlob() {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm;codecs=opus' });
        return audioBlob;
    }
};

console.log("API Service loaded successfully!");
"""
    return api_service_js

@app.get("/api/user")
async def get_user_api(request: Request):
    """Get current user info for dashboard"""
    user = get_current_user(request)
    return {"user": user}

@app.get("/api/avatars")
async def get_user_avatars(request: Request):
    """Get all avatars for current user"""
    user = get_current_user(request)
    if not user:
        return {"avatars": []}
    
    try:
        avatars = execute_query(
            "SELECT id, avatar_name as name, avatar_url as thumbnail_url, heygen_avatar_id, created_at FROM avatars WHERE user_id = ?",
            (user["id"],),
            fetch_all=True
        )
        
        avatar_list = []
        if avatars:
            for avatar in avatars:
                avatar_dict = dict(avatar)
                avatar_list.append(avatar_dict)
        
        return {"avatars": avatar_list}
    except Exception as e:
        log_error(f"Error fetching avatars: {str(e)}", "API", e)
        return {"avatars": []}

@app.get("/api/videos")
async def get_user_videos(request: Request):
    """Get all videos for current user"""
    user = get_current_user(request)
    if not user:
        return []
    
    try:
        videos = execute_query(
            "SELECT heygen_job_id as video_id, title, video_url, status, created_at FROM videos WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
            fetch_all=True
        )
        
        video_list = []
        if videos:
            for video in videos:
                video_dict = dict(video)
                video_list.append(video_dict)
        
        return video_list
    except Exception as e:
        log_error(f"Error fetching videos: {str(e)}", "API", e)
        return []

@app.get("/api/logs")
async def get_logs_api(request: Request):
    """Get recent logs for admin users"""
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return {"logs": []}
    
    recent_logs = log_handler.get_recent_logs(50)
    return {"logs": recent_logs}

@app.post("/api/avatar")
async def create_avatar_api(
    request: Request,
    avatar_name: str = Form(...),
    avatar_image: UploadFile = File(...)
):
    """Create a new avatar"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Upload avatar
        if CLOUDINARY_URL:
            avatar_url = upload_avatar_to_cloudinary(avatar_image, user["id"])
        else:
            avatar_url = upload_avatar_locally(avatar_image, user["id"])
        
        # Save to database
        execute_query(
            "INSERT INTO avatars (user_id, avatar_name, avatar_url) VALUES (?, ?, ?)",
            (user["id"], avatar_name, avatar_url)
        )
        
        log_info(f"New avatar created for user {user['username']}: {avatar_name}", "Avatar")
        
        return {"success": True, "message": "Avatar created successfully"}
    except Exception as e:
        log_error(f"Failed to create avatar for user {user['username']}", "Avatar", e)
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/video/generate")
async def generate_video_api(
    request: Request,
    audio: UploadFile = File(...),
    avatar_id: int = Form(...),
    title: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Log incoming data
    log_info(f"Received video generation request from {user['username']}", "Video")
    log_info(f"Audio file: {audio.filename}, size: {audio.size}, type: {audio.content_type}", "Video")
    log_info(f"Avatar ID: {avatar_id}", "Video")
    
    try:
        # Verify avatar belongs to user and get HeyGen ID
        avatar = execute_query(
            "SELECT * FROM avatars WHERE id = ? AND user_id = ?",
            (avatar_id, user["id"]),
            fetch_one=True
        )
        
        if not avatar:
            raise HTTPException(status_code=404, detail="Avatar not found")
        
        if not avatar["heygen_avatar_id"]:
            raise HTTPException(status_code=400, detail="Avatar missing HeyGen ID. Please set HeyGen Avatar ID in admin panel.")
        
        # Save audio file temporarily
        audio_filename = f"audio_{user['id']}_{uuid.uuid4()}"
        webm_path = os.path.join("uploads", f"{audio_filename}.webm")
        m4a_path = os.path.join("uploads", f"{audio_filename}.m4a")
        os.makedirs("uploads", exist_ok=True)
        
        # Read and save audio content
        log_info(f"Saving audio to: {webm_path}", "Video")
        content = await audio.read()
        log_info(f"Audio content size: {len(content)} bytes", "Video")
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        with open(webm_path, "wb") as f:
            f.write(content)
        
        # Convert WebM to M4A
        log_info("Converting WebM to M4A...", "Video")
        if not convert_webm_to_m4a(webm_path, m4a_path):
            raise HTTPException(status_code=500, detail="Failed to convert audio format")
        
        # Upload M4A to Cloudinary
        log_info(f"Uploading M4A to Cloudinary", "Video")
        audio_url = upload_audio_to_cloudinary(m4a_path)
        log_info(f"Audio uploaded: {audio_url}", "Video")
        
        # Call HeyGen API
        log_info(f"Calling HeyGen API with avatar {avatar['heygen_avatar_id']}", "Video")
        heygen_response = create_heygen_video(avatar["heygen_avatar_id"], audio_url)
        
        if heygen_response.get("error"):
            error_msg = heygen_response.get("error", {}).get("message", "HeyGen error")
            log_error(f"HeyGen API error: {error_msg}", "Video")
            raise HTTPException(status_code=400, detail=error_msg)
        
        video_id = heygen_response.get("data", {}).get("video_id")
        if not video_id:
            log_error(f"No video ID in HeyGen response: {heygen_response}", "Video")
            raise HTTPException(status_code=500, detail="No video ID returned from HeyGen")
        
        # Create video record in database
        execute_query(
            "INSERT INTO videos (user_id, avatar_id, title, status, heygen_job_id) VALUES (?, ?, ?, ?, ?)",
         (user["id"], avatar_id, title, "processing", video_id)
        )
        
        log_info(f"Video generation started for user {user['username']}, video_id: {video_id}", "Video")
        
        # Clean up temp files
        try:
            os.remove(webm_path)
            os.remove(m4a_path)
        except Exception as e:
            log_warning(f"Failed to delete temp files: {str(e)}", "Video")
        
        return {
            "video_id": video_id,
            "status": "processing",
            "message": "Video generation started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Failed to generate video for user {user['username']}", "Video", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/video/status/{video_id}")
async def get_video_status(request: Request, video_id: str):
    """Get video generation status"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        video = execute_query(
            "SELECT * FROM videos WHERE heygen_job_id = ? AND user_id = ?",
            (video_id, user["id"]),
            fetch_one=True
        )
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Check real HeyGen status
        heygen_status = check_heygen_status(video_id)
        
        status = heygen_status.get("data", {}).get("status", "unknown")
        video_url = heygen_status.get("data", {}).get("video_url")
        
        # Map HeyGen status to our status
        if status == "completed" and video_url:
            # Update database with video URL
            execute_query(
                "UPDATE videos SET status = 'completed', video_url = ? WHERE heygen_job_id = ?",
                (video_url, video_id)
            )
            
            return {
                "video_id": video_id,
                "status": "completed",
                "progress": 100,
                "video_url": video_url,
                "created_at": video["created_at"]
            }
        elif status == "processing" or status == "pending":
            # Calculate approximate progress
            progress = 50 if status == "processing" else 10
            
            return {
                "video_id": video_id,
                "status": "processing",
                "progress": progress
            }
        elif status == "failed":
            execute_query(
                "UPDATE videos SET status = 'failed' WHERE heygen_job_id = ?",
                (video_id,)
            )
            
            error_msg = heygen_status.get("data", {}).get("error", {}).get("message", "Unknown error")
            raise HTTPException(status_code=500, detail=f"Video generation failed: {error_msg}")
        
        return {
            "video_id": video_id,
            "status": status,
            "progress": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Failed to get video status", "Video", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug")
async def debug_api(request: Request):
    """Debug endpoint to check session and user data"""
    session_data = dict(request.session)
    user = get_current_user(request)
    
    return {
        "session": session_data,
        "user": user,
        "cookies": dict(request.cookies),
        "headers": {k: v for k, v in request.headers.items() if k.lower() != 'cookie'}
    }

#####################################################################
# CHAPTER 13: HEYGEN WEBHOOK ENDPOINT - FIXED VERSION
#####################################################################
@app.post("/api/heygen/webhook")
async def heygen_webhook(request: Request):
    """FIXED HeyGen webhook handler - searches for heygen_job_id correctly"""
    try:
        webhook_data = await request.json()
        log_info(f"[Webhook] Full payload received: {json.dumps(webhook_data, indent=2)}", "Webhook")
        
        # Extract video_id from webhook
        video_id = (
            webhook_data.get("video_id") or
            webhook_data.get("id") or
            webhook_data.get("data", {}).get("video_id") or
            webhook_data.get("data", {}).get("id")
        )
        
        if not video_id:
            log_error(f"[Webhook] No video_id found in webhook data", "Webhook")
            return JSONResponse({"error": "Missing video_id"}, status_code=400)

        log_info(f"[Webhook] Looking for video with HeyGen ID: {video_id}", "Webhook")
        
        # FIXED: Use heygen_job_id (not heygen_video_id)
        video_record = execute_query(
            "SELECT * FROM videos WHERE heygen_job_id = ?",
            (video_id,),
            fetch_one=True
        )
        
        if not video_record:
            log_error(f"[Webhook] Video record not found for HeyGen ID: {video_id}", "Webhook")
            # DEBUG: Show existing IDs
            existing_videos = execute_query(
                "SELECT heygen_job_id FROM videos WHERE heygen_job_id IS NOT NULL ORDER BY created_at DESC LIMIT 10",
                fetch_all=True
            )
            existing_ids = [v["heygen_job_id"] for v in existing_videos]
            log_error(f"[Webhook] Existing HeyGen IDs in database: {existing_ids}", "Webhook")
            return JSONResponse({"error": "Video record not found"}, status_code=404)

        # Extract status and video_url
        status = webhook_data.get("status", "completed")
        video_url = (
            webhook_data.get("video_url") or
            webhook_data.get("data", {}).get("video_url")
        )

        if status == "completed" and video_url:
            execute_query(
                "UPDATE videos SET status = ?, video_url = ? WHERE id = ?",
                ("completed", video_url, video_record['id'])
            )
            log_info(f"[Webhook] Video {video_record['id']} completed with URL: {video_url}", "Webhook")
        else:
            execute_query(
                "UPDATE videos SET status = ? WHERE id = ?",
                (status, video_record['id'])
            )
            log_info(f"[Webhook] Video {video_record['id']} status updated to: {status}", "Webhook")

        return JSONResponse({
            "success": True,
            "message": "Webhook processed successfully",
            "video_id": video_id,
            "status": status
        })
        
    except Exception as e:
        log_error("[Webhook] Webhook processing failed", "Webhook", e)
        return JSONResponse({"error": f"Webhook processing failed: {str(e)}"}, status_code=500)

#####################################################################
# CHAPTER 14: STATIC FILES & TEMPLATE SETUP
#####################################################################
@app.get("/admin/test-heygen/{avatar_id}")
async def test_heygen_avatar(request: Request, avatar_id: str):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return {"error": "Admin only"}
    
    import requests
    headers = {"X-Api-Key": HEYGEN_API_KEY}
    
    # Test different endpoints
    results = {}
    
    # Test 1: avatar/{id}
    try:
        r1 = requests.get(f"https://api.heygen.com/v1/avatar/{avatar_id}", headers=headers)
        results["v1_avatar_id"] = {
            "status": r1.status_code,
            "response": r1.json() if r1.status_code == 200 else r1.text
        }
    except Exception as e:
        results["v1_avatar_id"] = {"error": str(e)}
    
    # Test 2: avatar.get?avatar_id=
    try:
        r2 = requests.get(f"https://api.heygen.com/v1/avatar.get?avatar_id={avatar_id}", headers=headers)
        results["v1_avatar_get"] = {
            "status": r2.status_code,
            "response": r2.json() if r2.status_code == 200 else r2.text
        }
    except Exception as e:
        results["v1_avatar_get"] = {"error": str(e)}
    
    # Test 3: List all avatars
    try:
        r3 = requests.get("https://api.heygen.com/v1/avatar.list", headers=headers)
        if r3.status_code == 200:
            avatars = r3.json().get("data", {}).get("avatars", [])
            found = next((a for a in avatars if a.get("avatar_id") == avatar_id), None)
            results["avatar_list"] = {
                "total_avatars": len(avatars),
                "requested_avatar_found": found is not None,
                "avatar_details": found
            }
        else:
            results["avatar_list"] = {
                "status": r3.status_code,
                "error": r3.text
            }
    except Exception as e:
        results["avatar_list"] = {"error": str(e)}
    
    # Test 4: Check API key validity
    try:
        r4 = requests.get("https://api.heygen.com/v1/user.info", headers=headers)
        results["api_key_test"] = {
            "status": r4.status_code,
            "valid": r4.status_code == 200,
            "response": r4.json() if r4.status_code == 200 else r4.text
        }
    except Exception as e:
        results["api_key_test"] = {"error": str(e)}
    
    return results

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("templates/portal", exist_ok=True)

# Mount static directories
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Root redirect
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/auth/login")

#####################################################################
# CHAPTER 1: IMPORTS & CONFIGURATION
#####################################################################
import os
import textwrap
import logging
import traceback
import subprocess
from datetime import datetime, timedelta
from collections import deque
from typing import List, Dict, Optional, Any
import random

from fastapi import FastAPI, Request, status, Form, Depends, HTTPException, File, UploadFile, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
from dotenv import load_dotenv
import sqlite3
import uuid
from passlib.context import CryptContext
import requests
import json
import shutil

# Load environment variables
load_dotenv()
SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret")
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")
HEYGEN_API_KEY = os.environ.get("HEYGEN_API_KEY", "")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# Debug prints for troubleshooting
print(f"🔑 HEYGEN_API_KEY loaded: {HEYGEN_API_KEY[:20]}..." if HEYGEN_API_KEY else "❌ HEYGEN_API_KEY is EMPTY!")
print(f"🌐 BASE_URL: {BASE_URL}")
print(f"🌥️ CLOUDINARY_URL set: {'Yes' if CLOUDINARY_URL else 'No'}")

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# Test Cloudinary connection
try:
    print(f"🌥️ Cloudinary configured: {cloudinary.config().cloud_name}")
    print(f"🌥️ Cloudinary API Key: {'Set' if cloudinary.config().api_key else 'Missing'}")
except Exception as e:
    print(f"❌ Cloudinary error: {e}")

# Initialiser FastAPI
app = FastAPI(title="MyAvatar", description="AI Avatar Video Platform")

# Middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Importér router og tilføj til app
from modules.video_routes import router as video_router
app.include_router(video_router)

#####################################################################
# CHAPTER 2: ENHANCED LOGGING SYSTEM
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
# CHAPTER 3: DATABASE & AUTHENTICATION HELPERS
#####################################################################
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_db_connection():
    conn = sqlite3.connect("myavatar.db")
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    result = None
    if fetch_one:
        result = cur.fetchone()
    elif fetch_all:
        result = cur.fetchall()
    conn.commit()
    conn.close()
    return result

def get_current_user(request: Request):
    return request.session.get("user", None)

def init_database():
    """Initialize database tables and create admin user if needed"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if users table exists and what columns it has
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    users_table_exists = cur.fetchone() is not None
    
    if users_table_exists:
        # Check column names
        cur.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cur.fetchall()]
        
        # Handle old schema with useravatar_name
        if 'useravatar_name' in columns and 'username' not in columns:
            log_info("Migrating users table from useravatar_name to username", "Database")
            # Create new table with correct schema
            cur.execute("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Copy data
            cur.execute("""
                INSERT INTO users_new (id, username, email, hashed_password, is_admin, created_at)
                SELECT id, useravatar_name, email, hashed_password, is_admin, created_at FROM users
            """)
            # Drop old table and rename new one
            cur.execute("DROP TABLE users")
            cur.execute("ALTER TABLE users_new RENAME TO users")
    else:
        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # Check if avatars table exists and fix column names if needed
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='avatars'")
    avatars_table_exists = cur.fetchone() is not None
    
    if avatars_table_exists:
        cur.execute("PRAGMA table_info(avatars)")
        columns = [column[1] for column in cur.fetchall()]
        
        if 'avatar_avatar_name' in columns and 'avatar_name' not in columns:
            log_info("Migrating avatars table from avatar_avatar_name to avatar_name", "Database")
            # Create new table
            cur.execute("""
                CREATE TABLE avatars_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    avatar_name TEXT NOT NULL,
                    avatar_url TEXT,
                    heygen_avatar_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            # Copy data
            cur.execute("""
                INSERT INTO avatars_new (id, user_id, avatar_name, avatar_url, heygen_avatar_id, created_at)
                SELECT id, user_id, avatar_avatar_name, avatar_url, heygen_avatar_id, created_at FROM avatars
            """)
            # Drop old table and rename
            cur.execute("DROP TABLE avatars")
            cur.execute("ALTER TABLE avatars_new RENAME TO avatars")
    else:
        # Create avatars table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS avatars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                avatar_name TEXT NOT NULL,
                avatar_url TEXT,
                heygen_avatar_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
    
    # Create videos table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            avatar_id INTEGER,
            title TEXT NOT NULL,
            script TEXT,
            video_url TEXT,
            heygen_job_id TEXT,
            status TEXT DEFAULT 'pending',
            video_format TEXT DEFAULT '16:9',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (avatar_id) REFERENCES avatars (id)
        )
    """)
    
    # Create admin user if not exists
    cur.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    if not cur.fetchone():
        hashed_password = get_password_hash("admin123")
        cur.execute("""
            INSERT INTO users (username, email, hashed_password, is_admin) 
            VALUES (?, ?, ?, ?)
        """, ("admin", "admin@myavatar.com", hashed_password, 1))
        log_info("Admin user created (username: admin, password: admin123)", "Database")
    
    conn.commit()
    conn.close()
    log_info("Database tables initialized", "Database")

def update_database_schema():
    """Update database schema to match current requirements"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check videos table columns
        cur.execute("PRAGMA table_info(videos)")
        video_columns = [column[1] for column in cur.fetchall()]
        
        # Add missing columns to videos table
        if 'heygen_job_id' not in video_columns:
            log_info("Adding heygen_job_id column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN heygen_job_id TEXT")
            
        if 'status' not in video_columns:
            log_info("Adding status column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN status TEXT DEFAULT 'pending'")
            
        if 'video_format' not in video_columns:
            log_info("Adding video_format column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN video_format TEXT DEFAULT '16:9'")
            
        if 'video_url' not in video_columns:
            log_info("Adding video_url column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN video_url TEXT")
            
        if 'script' not in video_columns:
            log_info("Adding script column to videos table", "Database")
            cur.execute("ALTER TABLE videos ADD COLUMN script TEXT")
        
        conn.commit()
        log_info("Database schema updated successfully", "Database")
        
    except Exception as e:
        log_error(f"Failed to update database schema: {str(e)}", "Database", e)
        conn.rollback()
    finally:
        conn.close()

#####################################################################
# CHAPTER 4: HEYGEN & CLOUDINARY HELPERS (WITH AUDIO CONVERSION)
#####################################################################

def convert_webm_to_m4a(webm_path: str, m4a_path: str) -> bool:
    """Convert WebM audio to M4A/AAC using ffmpeg"""
    try:
        # Convert WebM to M4A (AAC codec)
        cmd = [
            'ffmpeg',
            '-i', webm_path,      # Input file
            '-vn',                # No video
            '-ar', '44100',       # Audio sample rate
            '-ac', '2',           # Audio channels (stereo)
            '-c:a', 'aac',        # AAC codec
            '-b:a', '128k',       # Audio bitrate
            m4a_path,             # Output file
            '-y'                  # Overwrite output file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            log_error(f"FFmpeg conversion failed: {result.stderr}", "Audio")
            return False
            
        log_info(f"Successfully converted WebM to M4A", "Audio")
        return True
        
    except Exception as e:
        log_error(f"Audio conversion error: {str(e)}", "Audio", e)
        return False

def upload_audio_to_cloudinary(audio_path: str) -> str:
    """Upload audio to Cloudinary and return public URL"""
    try:
        # Check file extension to determine resource type
        file_ext = os.path.splitext(audio_path)[1].lower()
        
        if file_ext in ['.mp3', '.wav', '.m4a']:
            # Standard audio formats can use 'auto' or 'raw'
            result = cloudinary.uploader.upload(
                audio_path,
                resource_type="auto",
                folder="audio"
            )
        else:
            # WebM and other video containers need 'video' type
            result = cloudinary.uploader.upload(
                audio_path,
                resource_type="video",
                folder="audio"
            )
        
        secure_url = result.get("secure_url")
        log_info(f"Audio uploaded to Cloudinary: {secure_url}", "Cloudinary")
        return secure_url
        
    except Exception as e:
        log_error(f"Failed to upload audio to Cloudinary: {str(e)}", "Cloudinary", e)
        raise

def create_heygen_video(heygen_avatar_id: str, audio_url: str) -> dict:
    """Create video using HeyGen API v2"""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": heygen_avatar_id,
                "avatar_style": "normal"
            },
            "voice": {
                "type": "audio",
                "audio_url": audio_url
            }
        }],
        "test": False,
        "caption": False
    }
    
    try:
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error(f"HeyGen API error: {str(e)}", "HeyGen")
        raise

def check_heygen_status(video_id: str) -> dict:
    """Check video generation status"""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY
    }
    
    try:
        response = requests.get(
            f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error(f"HeyGen status check error: {str(e)}", "HeyGen")
        raise

def get_heygen_avatar_info(avatar_id: str) -> dict:
    """Get avatar information from HeyGen API"""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY
    }
    
    try:
        # First try V2 API
        response = requests.get(
            f"https://api.heygen.com/v2/avatars/{avatar_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            # V2 API response format
            if "data" in data:
                return data["data"]
            return data
        
        # If V2 fails, try V1 API
        response = requests.get(
            f"https://api.heygen.com/v1/avatar.list",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            avatars = data.get("data", {}).get("avatars", [])
            # Find the avatar in the list
            for avatar in avatars:
                if avatar.get("avatar_id") == avatar_id:
                    return avatar
            
        raise Exception(f"Avatar with ID '{avatar_id}' not found in HeyGen. Please ensure the avatar exists and you have access to it.")
            
    except Exception as e:
        log_error(f"Failed to get HeyGen avatar: {str(e)}", "HeyGen")
        raise

def list_heygen_avatars() -> list:
    """List all available avatars from HeyGen"""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY
    }
    
    try:
        response = requests.get(
            "https://api.heygen.com/v1/avatar.list",
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("error"):
            log_error(f"HeyGen list avatars error: {data.get('error')}", "HeyGen")
            return []
            
        return data.get("data", {}).get("avatars", [])
    except Exception as e:
        log_error(f"Failed to list HeyGen avatars: {str(e)}", "HeyGen")
        return []

def upload_avatar_to_cloudinary(image_file: UploadFile, user_id: int):
    # Save to temp file
    temp_path = f"temp_{user_id}_{image_file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image_file.file, buffer)
    result = cloudinary.uploader.upload(temp_path, folder="avatars")
    os.remove(temp_path)
    return result.get("secure_url")

def upload_avatar_locally(image_file: UploadFile, user_id: int):
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{user_id}_{image_file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image_file.file, buffer)
    return f"/uploads/{user_id}_{image_file.filename}"

#####################################################################
# CHAPTER 5: ADMIN DASHBOARD & LOGS
#####################################################################
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    try:
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        admin_html = textwrap.dedent("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Admin Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .header { background: #dc2626; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
                .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
                .btn { background: #4f46e5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; border: none; cursor: pointer; }
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
                    <a href="/dashboard" class="btn">User Dashboard</a>
                    <a href="/admin/logs" class="btn btn-success">System Logs</a>
                    <a href="/auth/logout" class="btn">Log Out</a>
                </div>
            </div>
            <div class="card">
                <h2>👥 User & Avatar Management</h2>
                <p>Manage users, their avatars, and system access.</p>
                <a href="/admin/users" class="btn">Manage Users</a>
                <a href="/admin/create-user" class="btn">Create New User</a>
                <a href="/admin/avatars" class="btn">View All Avatars</a>
            </div>
            <div class="card">
                <h2>🎬 Video Management</h2>
                <p>View and manage all generated videos.</p>
                <a href="/admin/videos" class="btn">View All Videos</a>
            </div>
            <div class="card">
                <h2>📊 System Status</h2>
                <p><strong>HeyGen API:</strong> ✅ Available</p>
                <p><strong>Storage:</strong> ✅ Cloudinary CDN</p>
                <p><strong>Database:</strong> ✅ SQLite</p>
                <p><strong>Webhook:</strong> ✅ /api/heygen/webhook</p>
                <p><strong>Logging:</strong> ✅ Enhanced Error Tracking</p>
                <p><strong>Audio Processing:</strong> ✅ FFmpeg WebM to M4A</p>
            </div>
            <div class="card">
                <h2>🧹 System Maintenance</h2>
                <p>Tools for system maintenance and troubleshooting.</p>
                <a href="/admin/quickclean" class="btn btn-danger">Total Reset (Delete All)</a>
                <a href="/admin/logs" class="btn btn-success">View System Logs</a>
            </div>
        </body>
        </html>
        """)
        return HTMLResponse(content=admin_html)
    except Exception as e:
        log_error("Admin dashboard failed", "Admin", e)
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@app.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs(request: Request):
    try:
        user = get_current_user(request)
        if not user or user.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

        recent_logs = log_handler.get_recent_logs(200)
        error_logs = log_handler.get_error_logs(50)

        logs_html = """
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
            <a href="/admin" class="btn">Back to Admin</a>
            <button onclick="location.reload()" class="btn">Refresh</button>
        </div>
    </div>
    <div class="card">
        <h3>Recent Activity (Last 200 entries)</h3>
        <div style='max-height: 600px; overflow-y: scroll; background: #111; padding: 10px; border-radius: 4px;'>
"""
        for log in recent_logs:
            level_class = f"log-{log['level'].lower()}"
            logs_html += (
                f"<div class='log-entry {level_class}'>"
                f"<span class='timestamp'>[{log['timestamp']}]</span> "
                f"<span class='module'>{log['module']}</span>: "
                f"{log['message']}</div>"
            )
        logs_html += """
        </div>
    </div>
    <div class="card">
        <h3>ℹ️ Log Information</h3>
        <p>• Logs auto-refresh every 30 seconds</p>
        <p>• Showing last {recent_count} entries</p>
        <p>• {error_count} recent errors</p>
    </div>
</body>
</html>
"""
        logs_html = logs_html.replace("{recent_count}", str(len(recent_logs))).replace("{error_count}", str(len(error_logs)))
        return HTMLResponse(content=logs_html)
    except Exception as e:
        log_error("Admin logs page failed", "Admin", e)
        return HTMLResponse("<h1>Error loading logs</h1><a href='/admin'>Back to Admin</a>")

#####################################################################
# CHAPTER 6: CREATE USER PAGE
#####################################################################
@app.get("/admin/create-user", response_class=HTMLResponse)
async def create_user_page(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Create New User</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h2 { color: #333; }
                input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }
                button { background: #4f46e5; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }
                button:hover { background: #3730a3; }
                .error { color: red; margin: 10px 0; }
                a { color: #4f46e5; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Create New User</h2>
                <form method="post" action="/admin/create-user">
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="email" name="email" placeholder="Email" required>
                    <input type="password" name="password" placeholder="Password" required>
                    <label>
                        <input type="checkbox" name="is_admin"> Admin User
                    </label>
                    <br><br>
                    <button type="submit">Create User</button>
                </form>
                <br>
                <a href="/admin">← Back to Admin</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    except Exception as e:
        log_error("Create user page failed", "Admin", e)
        return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

@app.post("/admin/create-user")
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: Optional[str] = Form(None)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        hashed_password = get_password_hash(password)
        is_admin_val = 1 if is_admin else 0
        
        execute_query(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            (username, email, hashed_password, is_admin_val)
        )
        
        log_info(f"New user created: {username} (admin: {bool(is_admin_val)})", "Admin")
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_302_FOUND)
        
    except Exception as e:
        log_error("Create user failed", "Admin", e)
        return HTMLResponse("<h1>Error creating user</h1><p>Username or email may already exist.</p><a href='/admin/create-user'>Try again</a>")

#####################################################################
# CHAPTER 7: ENHANCED USER CRUD & MANAGEMENT
#####################################################################
@app.get("/admin/users", response_class=HTMLResponse)
async def list_users(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        users = execute_query("SELECT id, username, email, is_admin, created_at FROM users", fetch_all=True)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>User Management</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 1000px; margin: 0 auto; }
                h2 { color: #333; }
                table { width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                th { background: #4f46e5; color: white; padding: 12px; text-align: left; }
                td { padding: 12px; border-bottom: 1px solid #e0e0e0; }
                tr:hover { background: #f5f5f5; }
                .btn { padding: 6px 12px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 2px; }
                .btn-primary { background: #4f46e5; color: white; }
                .btn-primary:hover { background: #3730a3; }
                .btn-danger { background: #dc2626; color: white; }
                .btn-danger:hover { background: #b91c1c; }
                .btn-success { background: #16a34a; color: white; }
                .btn-success:hover { background: #15803d; }
                .admin-badge { background: #dc2626; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
                .user-badge { background: #6b7280; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
                .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>User Management</h2>
                    <div>
                        <a href="/admin/create-user" class="btn btn-success">+ Create New User</a>
                        <a href="/admin" class="btn btn-primary">← Back to Admin</a>
                    </div>
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Type</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for user in users:
            created_date = user['created_at'][:10] if user['created_at'] else 'Unknown'
            user_type = '<span class="admin-badge">Admin</span>' if user['is_admin'] else '<span class="user-badge">User</span>'
            
            html += f"""
                <tr>
                    <td>{user['id']}</td>
                    <td><strong>{user['username']}</strong></td>
                    <td>{user['email']}</td>
                    <td>{user_type}</td>
                    <td>{created_date}</td>
                    <td>
                        <a href='/admin/user/{user['id']}' class="btn btn-primary">Manage</a>
                        <a href='/admin/user/{user['id']}/delete' class="btn btn-danger" 
                           onclick="return confirm('Are you sure you want to delete this user?')">Delete</a>
                    </td>
                </tr>
            """
        
        html += """
                    </tbody>
                </table>
                
                <div style="margin-top: 20px; padding: 20px; background: white; border-radius: 8px;">
                    <h3>Quick Stats</h3>
                    <p>Total Users: <strong>{}</strong></p>
                    <p>Administrators: <strong>{}</strong></p>
                    <p>Regular Users: <strong>{}</strong></p>
                </div>
            </div>
        </body>
        </html>
        """.format(
            len(users),
            sum(1 for u in users if u['is_admin']),
            sum(1 for u in users if not u['is_admin'])
        )
        
        return HTMLResponse(html)
    except Exception as e:
        log_error("List users failed", "Admin", e)
        return HTMLResponse("<h1>Error loading users</h1><a href='/admin'>Back to Admin</a>")

@app.get("/admin/user/{user_id}", response_class=HTMLResponse)
async def edit_user(request: Request, user_id: int):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Get user details
        user = execute_query("SELECT id, username, email, is_admin FROM users WHERE id = ?", (user_id,), fetch_one=True)
        if not user:
            return HTMLResponse("<h2>User not found</h2><a href='/admin/users'>Back</a>")
        
        # Get user's avatars
        avatars = execute_query(
            "SELECT id, avatar_name, avatar_url, heygen_avatar_id, created_at FROM avatars WHERE user_id = ?",
            (user_id,),
            fetch_all=True
        )
        
        # Get user's videos count
        video_count = execute_query(
            "SELECT COUNT(*) as count FROM videos WHERE user_id = ?",
            (user_id,),
            fetch_one=True
        )
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Edit User: {user['username']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                h2 {{ color: #333; }}
                .btn {{ padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px; border: none; cursor: pointer; }}
                .btn-primary {{ background: #4f46e5; color: white; }}
                .btn-primary:hover {{ background: #3730a3; }}
                .btn-danger {{ background: #dc2626; color: white; }}
                .btn-danger:hover {{ background: #b91c1c; }}
                .btn-success {{ background: #16a34a; color: white; }}
                .btn-success:hover {{ background: #15803d; }}
                input, select {{ width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }}
                .avatar-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; margin-top: 15px; }}
                .avatar-card {{ text-align: center; padding: 10px; border: 1px solid #e0e0e0; border-radius: 8px; }}
                .avatar-card img {{ width: 100px; height: 100px; border-radius: 50%; object-fit: cover; }}
                .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                .heygen-id {{ font-size: 10px; color: #666; word-break: break-all; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>User Management: {user['username']}</h1>
                
                <div class="card">
                    <h3>User Information</h3>
                    <div class="info-grid">
                        <div>
                            <p><strong>User ID:</strong> {user['id']}</p>
                            <p><strong>Username:</strong> {user['username']}</p>
                            <p><strong>Email:</strong> {user['email']}</p>
                        </div>
                        <div>
                            <p><strong>Account Type:</strong> {'Administrator' if user['is_admin'] else 'Regular User'}</p>
                            <p><strong>Total Videos:</strong> {video_count['count'] if video_count else 0}</p>
                            <p><strong>Total Avatars:</strong> {len(avatars) if avatars else 0}</p>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Edit User Details</h3>
                    <form method='post' action='/admin/user/{user['id']}'>
                        <label>Email:</label>
                        <input type='email' name='email' value='{user['email']}' required>
                        
                        <label style="display: block; margin-top: 10px;">
                            <input type='checkbox' name='is_admin' {'checked' if user['is_admin'] else ''}> 
                            Administrator Access
                        </label>
                        
                        <button type='submit' class="btn btn-primary">Save Changes</button>
                    </form>
                </div>
                
                <div class="card">
                    <h3>Change Password</h3>
                    <form method='post' action='/admin/user/{user['id']}/reset-password'>
                        <label>New Password:</label>
                        <div style="position: relative;">
                            <input type='password' id='password-field' name='new_password' required minlength="6" style="padding-right: 40px;">
                            <span onclick="togglePassword()" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%); cursor: pointer; user-select: none;">
                                👁️
                            </span>
                        </div>
                        <small style="color: #666;">Minimum 6 characters</small>
                        <br><br>
                        <button type='submit' class="btn btn-success">Save New Password</button>
                    </form>
                    
                    <script>
                        function togglePassword() {{
                            const passwordField = document.getElementById('password-field');
                            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
                            passwordField.setAttribute('type', type);
                        }}
                    </script>
                </div>
                
                <div class="card">
                    <h3>User's Avatars</h3>
        """
        
        if avatars:
            html += '<div class="avatar-grid">'
            for avatar in avatars:
                html += f"""
                    <div class="avatar-card">
                        <img src="{avatar['avatar_url']}" alt="{avatar['avatar_name']}">
                        <p><strong>{avatar['avatar_name']}</strong></p>
                        <p class="heygen-id">HeyGen: {avatar['heygen_avatar_id'] or 'Not set'}</p>
                        <small>Created: {avatar['created_at'][:10]}</small>
                        <br>
                        <a href="/admin/avatar/{avatar['id']}" class="btn btn-sm btn-primary">Edit</a>
                    </div>
                """
            html += '</div>'
        else:
            html += '<p>No avatars yet</p>'
        
        html += f"""
                    <hr style="margin: 20px 0;">
                    
                    <!-- Import from HeyGen Option -->
                    <div style="background: #f0f9ff; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                        <h4>🚀 Quick Import from HeyGen</h4>
                        <form method='post' action='/admin/user/{user['id']}/import-avatar-heygen' style="display: flex; gap: 10px; align-items: flex-end;">
                            <div style="flex: 1;">
                                <label>HeyGen Avatar ID:</label>
                                <input type='text' name='heygen_avatar_id' required placeholder='e.g., b5038ba7bd9b4d94ac6b5c9ea70f8d28' style="width: 100%;">
                                <small style="color: #666;">Enter the avatar ID from your HeyGen dashboard</small>
                            </div>
                            <button type='submit' class="btn btn-success" style="white-space: nowrap;">
                                Import from HeyGen
                            </button>
                        </form>
                    </div>
                    
                    <!-- Traditional Upload Option -->
                    <div style="background: #f8f8f8; padding: 20px; border-radius: 8px;">
                        <h4>📤 Manual Upload</h4>
                        <form method='post' action='/admin/user/{user['id']}/upload-avatar' enctype='multipart/form-data'>
                            <label>Avatar Name:</label>
                            <input type='text' name='avatar_name' required placeholder='e.g., Professional Avatar'>
                            
                            <label>HeyGen Avatar ID:</label>
                            <input type='text' name='heygen_avatar_id' required placeholder='e.g., b5038ba7bd9b4d94ac6b5c9ea70f8d28'>
                            <small style="color: #666;">Get this ID from your HeyGen dashboard</small>
                            
                            <label style="margin-top: 10px;">Avatar Image:</label>
                            <input type='file' name='avatar_image' accept='image/*' required>
                            <small style="color: #666;">Upload a preview image for this avatar</small>
                            
                            <button type='submit' class="btn btn-success" style="margin-top: 15px;">Upload Avatar</button>
                        </form>
                    </div>
                </div>
                
                <div style="margin-top: 20px;">
                    <a href='/admin/users' class="btn btn-primary">← Back to Users</a>
                    <a href='/admin' class="btn btn-primary">← Back to Admin</a>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("Edit user failed", "Admin", e)
        return HTMLResponse("<h1>Error loading user</h1><a href='/admin/users'>Back</a>")

@app.post("/admin/user/{user_id}", response_class=HTMLResponse)
async def update_user(request: Request, user_id: int, email: str = Form(...), is_admin: Optional[str] = Form(None)):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        is_admin_val = 1 if is_admin else 0
        execute_query("UPDATE users SET email = ?, is_admin = ? WHERE id = ?", (email, is_admin_val, user_id))
        return RedirectResponse(url=f"/admin/user/{user_id}", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Update user failed", "Admin", e)
        return HTMLResponse("<h1>Error updating user</h1><a href='/admin/users'>Back</a>")

@app.post("/admin/user/{user_id}/reset-password")
async def reset_user_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        hashed_password = get_password_hash(new_password)
        execute_query(
            "UPDATE users SET hashed_password = ? WHERE id = ?",
            (hashed_password, user_id)
        )
        
        user = execute_query("SELECT username FROM users WHERE id = ?", (user_id,), fetch_one=True)
        log_info(f"Password reset for user {user['username']} by admin {admin['username']}", "Admin")
        
        return RedirectResponse(url=f"/admin/user/{user_id}", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Password reset failed", "Admin", e)
        return HTMLResponse("<h1>Error resetting password</h1><a href='/admin/users'>Back</a>")

@app.post("/admin/user/{user_id}/upload-avatar")
async def upload_avatar_for_user(
    request: Request,
    user_id: int,
    avatar_name: str = Form(...),
    heygen_avatar_id: str = Form(...),
    avatar_image: UploadFile = File(...)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Upload avatar image
        if CLOUDINARY_URL:
            avatar_url = upload_avatar_to_cloudinary(avatar_image, user_id)
        else:
            avatar_url = upload_avatar_locally(avatar_image, user_id)
        
        # Save to database with HeyGen ID
        execute_query(
            "INSERT INTO avatars (user_id, avatar_name, avatar_url, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (user_id, avatar_name, avatar_url, heygen_avatar_id)
        )
        
        user = execute_query("SELECT username FROM users WHERE id = ?", (user_id,), fetch_one=True)
        log_info(f"Avatar '{avatar_name}' created for user {user['username']} with HeyGen ID {heygen_avatar_id}", "Admin")
        
        return RedirectResponse(url=f"/admin/user/{user_id}", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Avatar upload failed", "Admin", e)
        return HTMLResponse(f"<h1>Error uploading avatar</h1><p>{str(e)}</p><a href='/admin/users'>Back</a>")

@app.post("/admin/user/{user_id}/import-avatar-heygen")
async def import_avatar_from_heygen(
    request: Request,
    user_id: int,
    heygen_avatar_id: str = Form(...)
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Since we can't fetch avatar details from HeyGen API (403 Forbidden),
        # we'll just save the ID and use a default name/thumbnail
        log_info(f"Importing avatar {heygen_avatar_id} for user {user_id}", "Admin")
        
        # Use a default name based on the ID
        avatar_name = f"HeyGen Avatar ({heygen_avatar_id[:8]}...)"
        
        # Use a placeholder thumbnail since we can't fetch from HeyGen
        # You can replace this with a better default image
        thumbnail_url = "https://via.placeholder.com/200x200?text=HeyGen+Avatar"
        
        # Check if avatar already exists for this user
        existing = execute_query(
            "SELECT id FROM avatars WHERE user_id = ? AND heygen_avatar_id = ?",
            (user_id, heygen_avatar_id),
            fetch_one=True
        )
        
        if existing:
            return HTMLResponse(
                f"<h1>Avatar already exists</h1><p>This HeyGen avatar is already imported for this user.</p><a href='/admin/user/{user_id}'>Back</a>"
            )
        
        # Save to database
        execute_query(
            "INSERT INTO avatars (user_id, avatar_name, avatar_url, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (user_id, avatar_name, thumbnail_url, heygen_avatar_id)
        )
        
        user = execute_query("SELECT username FROM users WHERE id = ?", (user_id,), fetch_one=True)
        log_info(f"Avatar '{avatar_name}' imported from HeyGen for user {user['username']}", "Admin")
        
        return RedirectResponse(url=f"/admin/user/{user_id}", status_code=status.HTTP_302_FOUND)
        
    except Exception as e:
        log_error("HeyGen avatar import failed", "Admin", e)
        return HTMLResponse(f"<h1>Error importing avatar from HeyGen</h1><p>{str(e)}</p><a href='/admin/user/{user_id}'>Back</a>")

@app.get("/admin/user/{user_id}/delete")
async def delete_user(request: Request, user_id: int):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Don't allow deleting yourself
        if user_id == admin["id"]:
            return HTMLResponse("<h1>Cannot delete your own account</h1><a href='/admin/users'>Back</a>")
        
        # Delete user's videos, avatars, and then the user
        execute_query("DELETE FROM videos WHERE user_id = ?", (user_id,))
        execute_query("DELETE FROM avatars WHERE user_id = ?", (user_id,))
        execute_query("DELETE FROM users WHERE id = ?", (user_id,))
        
        log_info(f"User ID {user_id} deleted by admin {admin['username']}", "Admin")
        
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Delete user failed", "Admin", e)
        return HTMLResponse("<h1>Error deleting user</h1><a href='/admin/users'>Back</a>")

#####################################################################
# CHAPTER 8: AVATAR CRUD & MANAGEMENT
#####################################################################
@app.get("/admin/avatars", response_class=HTMLResponse)
async def list_avatars(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Get all avatars with user information
        avatars = execute_query("""
            SELECT a.id, a.avatar_name, a.avatar_url, a.created_at, 
                   u.username, u.id as user_id
            FROM avatars a
            JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
        """, fetch_all=True)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>All Avatars</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
                .avatar-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
                .avatar-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
                .avatar-card img { width: 120px; height: 120px; border-radius: 50%; object-fit: cover; margin-bottom: 10px; }
                .btn { padding: 6px 12px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 2px; }
                .btn-primary { background: #4f46e5; color: white; }
                .btn-primary:hover { background: #3730a3; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>All Avatars</h2>
                    <a href="/admin" class="btn btn-primary">← Back to Admin</a>
                </div>
                
                <div class="avatar-grid">
        """
        
        if avatars:
            for avatar in avatars:
                html += f"""
                    <div class="avatar-card">
                        <img src="{avatar['avatar_url']}" alt="{avatar['avatar_name']}">
                        <h4>{avatar['avatar_name']}</h4>
                        <p>User: <strong>{avatar['username']}</strong></p>
                        <small>Created: {avatar['created_at'][:10]}</small>
                        <br><br>
                        <a href="/admin/avatar/{avatar['id']}" class="btn btn-primary">Edit</a>
                    </div>
                """
        else:
            html += '<p>No avatars created yet</p>'
        
        html += """
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("List avatars failed", "Admin", e)
        return HTMLResponse("<h1>Error loading avatars</h1><a href='/admin'>Back to Admin</a>")

@app.get("/admin/avatar/{avatar_id}", response_class=HTMLResponse)
async def edit_avatar(request: Request, avatar_id: int):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        avatar = execute_query("SELECT id, user_id, avatar_name, avatar_url FROM avatars WHERE id = ?", (avatar_id,), fetch_one=True)
        if not avatar:
            return HTMLResponse("<h2>Avatar not found</h2><a href='/admin/avatars'>Back</a>")
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Edit Avatar</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
                input {{ width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; }}
                button {{ background: #4f46e5; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }}
                button:hover {{ background: #3730a3; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Edit Avatar: {avatar['avatar_name']}</h2>
                <img src="{avatar['avatar_url']}" width="200" style="border-radius: 50%;"><br><br>
                
                <form method='post' action='/admin/avatar/{avatar['id']}' enctype='multipart/form-data'>
                    <label>Avatar Name:</label>
                    <input type='text' name='avatar_name' value='{avatar['avatar_name']}' required><br><br>
                    
                    <label>Replace Image:</label>
                    <input type='file' name='avatar_image' accept='image/*'><br><br>
                    
                    <button type='submit'>Update Avatar</button>
                </form>
                <br>
                <a href='/admin/avatars'>← Back to Avatars</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("Edit avatar failed", "Admin", e)
        return HTMLResponse("<h1>Error loading avatar</h1><a href='/admin/avatars'>Back</a>")

@app.post("/admin/avatar/{avatar_id}", response_class=HTMLResponse)
async def update_avatar(
    request: Request, 
    avatar_id: int, 
    avatar_name: str = Form(...),
    avatar_image: UploadFile = File(...),
):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        # Update avatar name
        execute_query("UPDATE avatars SET avatar_name = ? WHERE id = ?", (avatar_name, avatar_id))
        
        # Update avatar image if provided
        if avatar_image:
            # Save image to disk
            image_path = f"avatars/{avatar_id}.jpg"
            with open(image_path, "wb") as f:
                f.write(avatar_image.file.read())
            
            # Update avatar URL in database
            execute_query("UPDATE avatars SET avatar_url = ? WHERE id = ?", (image_path, avatar_id))
        
        log_info(f"Avatar {avatar_id} updated by admin {admin['username']}", "Admin")
        
        return RedirectResponse(url=f"/admin/avatar/{avatar_id}", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Update avatar failed", "Admin", e)
        return HTMLResponse("<h1>Error updating avatar</h1><a href='/admin/avatars'>Back</a>")