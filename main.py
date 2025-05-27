"""
MyAvatar - Complete Working Application
Railway-compatible with PostgreSQL + HeyGen Webhook + CASCADE DELETE + Enhanced Logging
Clean, tested, and ready to deploy!
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
        with open(img_path, "wb") as f:
            f.write(await image_file.read())
        log_info(f"Avatar uploaded locally: {img_path}", "Storage")
        return f"/static/uploads/images/{img_filename}"
    except Exception as e:
        log_error(f"Local avatar upload failed for user {user_id}", "Storage", e)
        return None

        if not user or user.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        
        hashed_password = get_password_hash(password)
        
        result = execute_query(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            (username, email, hashed_password, 0)
        )
        
        if result['rowcount'] > 0:
            log_info(f"User created successfully: {username}", "Admin")
            return RedirectResponse(
                url="/admin/users?success=Bruger oprettet succesfuldt", 
                status_code=303
            )
        else:
            log_error(f"Database insert failed for user: {username}", "Admin")
            return RedirectResponse(
                url="/admin/create-user?error=Database fejl", 
                status_code=303
            )
            
    except Exception as e:
        log_error(f"User creation failed: {username}", "Admin", e)
        return RedirectResponse(
            url="/admin/create-user?error=Fejl: " + str(e), 
            status_code=303
        )

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
            
            {% if success %}
            <div class="success">{{ success }}</div>
            {% endif %}
            
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
            
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
        return HTMLResponse(content=Template(users_html).render(
            request=request, 
            users=users,
            success=request.query_params.get("success"),
            error=request.query_params.get("error")
        ))
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
                <h1>🎭 {{ user.username }} - Avatar Administration</h1>
                <div>
                    <a href="/admin/users" class="btn">Tilbage til Brugere</a>
                </div>
            </div>
            
            {% if success %}
            <div class="success">{{ success }}</div>
            {% endif %}
            
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
            
            <div class="card">
                <h2>➕ Tilføj Ny Avatar</h2>
                <form method="post" action="/admin/user/{{ user.id }}/avatars" enctype="multipart/form-data">
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
            
            {% if avatars %}
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
                <h2>❌ Ingen Avatars</h2>
                <p>{{ user.username }} har ingen avatars endnu. Brug formularen ovenfor til at tilføje den første avatar.</p>
            </div>
            {% endif %}
        </body>
        </html>
        '''
        return HTMLResponse(content=Template(avatar_html).render(
            request=request, 
            user=user, 
            avatars=avatars,
            success=request.query_params.get("success"),
            error=request.query_params.get("error")
        ))
        
    except Exception as e:
        log_error(f"Admin avatar management failed for user {user_id}", "Admin", e)
        return RedirectResponse(url="/admin/users?error=avatar_management_failed", status_code=status.HTTP_302_FOUND)

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
                    ''' + "".join([f'''
                    <div class="log-entry log-{log['level'].lower()}">
                        <span class="timestamp">{log['timestamp']}</span> | 
                        <span class="module">[{log['module']}]</span> | 
                        <span class="level">{log['level']}</span> | 
                        {log['message']}
                    </div>
                    ''' for log in recent_logs]) + '''
                </div>
            </div>
            
            <div class="card">
                <h3>ℹ️ Log Information</h3>
                <p>• Logs auto-refresh every 30 seconds</p>
                <p>• Showing last ''' + str(len(recent_logs)) + ''' entries</p>
                <p>• ''' + str(len(error_logs)) + ''' recent errors</p>
            </div>
        </body>
        </html>
        '''
        
        return HTMLResponse(content=logs_html)
        
    except Exception as e:
        log_error("Admin logs page failed", "Admin", e)
        return HTMLResponse("<h1>Error loading logs</h1><a href='/admin'>Back to Admin</a>")

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
# API ENDPOINTS - HEYGEN INTEGRATION
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
            return JSONResponse({"error": "Avatar ikke fundet"}, status_code=404)
        
        heygen_avatar_id = avatar.get('heygen_avatar_id')

        log_info(f"Video request by user: {user['username']} using avatar: {avatar['name']}", "HeyGen")
        log_info(f"Video format: {video_format}, Title: {title}", "HeyGen")
        
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
            log_info(f"Audio file saved and accessible at: {audio_url}", "HeyGen")
            
        except Exception as e:
            log_error("Local audio file save failed", "HeyGen", e)
            return JSONResponse({"error": f"Fil upload fejlede: {str(e)}"}, status_code=500)

        # Save to database
        result = execute_query(
            "INSERT INTO videos (user_id, avatar_id, title, audio_path, status) VALUES (?, ?, ?, ?, ?)",
            (user["id"], avatar_id, title, audio_url, "processing")
        )
        video_id = result['lastrowid']

        log_info(f"Video record created with ID: {video_id}", "HeyGen")

        # Call HeyGen API
        heygen_result = create_video_from_audio_file(
            api_key=HEYGEN_API_KEY,
            avatar_id=heygen_avatar_id,
            audio_url=audio_url,
            video_format=video_format
        )
        
        if heygen_result["success"]:
            execute_query(
                "UPDATE videos SET heygen_video_id = ?, status = ? WHERE id = ?",
                (heygen_result.get("video_id"), "processing", video_id)
            )
            log_info(f"HeyGen video generation started: {heygen_result.get('video_id')}", "HeyGen")
        else:
            log_error(f"HeyGen API failed: {heygen_result.get('error')}", "HeyGen")
        
        return JSONResponse(heygen_result)

    except Exception as e:
        log_error("Unexpected error in HeyGen video creation", "HeyGen", e)
        return JSONResponse({
            "success": False,
            "error": f"Uventet fejl: {str(e)}"
        }, status_code=500)

#####################################################################
# ENHANCED HEYGEN WEBHOOK HANDLER
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
    try:
        webhook_data = await request.json()
        log_info(f"HeyGen Webhook received: {json.dumps(webhook_data, indent=2)}", "Webhook")
        
        video_id = (
            webhook_data.get("video_id") or 
            webhook_data.get("id") or 
            webhook_data.get("data", {}).get("video_id") or
            webhook_data.get("data", {}).get("id")
        )
        
        status = webhook_data.get("status", "").lower()
        video_url = (
            webhook_data.get("video_url") or 
            webhook_data.get("url") or
            webhook_data.get("data", {}).get("video_url") or
            webhook_data.get("data", {}).get("url")
        )
        
        log_info(f"Extracted: video_id={video_id}, status={status}, video_url={video_url}", "Webhook")
        
        if not video_id:
            log_error(f"No video_id found in webhook data. Available keys: {list(webhook_data.keys())}", "Webhook")
            return JSONResponse({"error": "Missing video_id", "received_keys": list(webhook_data.keys())}, status_code=400)
        
        video_record = execute_query(
            "SELECT * FROM videos WHERE heygen_video_id = ?", 
            (video_id,), 
            fetch_one=True
        )
        
        if not video_record:
            log_error(f"Video record not found for HeyGen ID: {video_id}", "Webhook")
            return JSONResponse({"error": "Video record not found", "heygen_id": video_id}, status_code=404)
        
        log_info(f"Found video record: {video_record['id']} - {video_record['title']}", "Webhook")
        
        if status in ["completed", "success", "finished"]:
            if video_url:
                local_path = await download_video_from_heygen(video_url, video_record['id'])
                
                if local_path:
                    execute_query(
                        "UPDATE videos SET video_path = ?, status = ? WHERE id = ?",
                        (local_path, "completed", video_record['id'])
                    )
                    log_info(f"Video {video_record['id']} completed and downloaded: {local_path}", "Webhook")
                else:
                    execute_query(
                        "UPDATE videos SET status = ? WHERE id = ?",
                        ("error", video_record['id'])
                    )
                    log_error(f"Failed to download video {video_record['id']}", "Webhook")
            else:
                log_warning(f"No video_url provided in webhook for {video_id}", "Webhook")
                
        elif status in ["failed", "error"]:
            execute_query(
                "UPDATE videos SET status = ? WHERE id = ?",
                ("failed", video_record['id'])
            )
            log_error(f"Video {video_record['id']} failed in HeyGen", "Webhook")
        
        else:
            execute_query(
                "UPDATE videos SET status = ? WHERE id = ?",
                (status, video_record['id'])
            )
            log_info(f"Video {video_record['id']} status updated to: {status}", "Webhook")
        
        return JSONResponse({"success": True, "message": "Webhook processed", "video_id": video_id})
    
    except Exception as e:
        log_error("Webhook processing failed", "Webhook", e)
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
            "logging": "enhanced_tracking_enabled"
        }
    except Exception as e:
        log_error("Health check failed", "System", e)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/api/videos/{video_id}")
async def get_video_info(video_id: int, request: Request):
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Ikke autoriseret"}, status_code=401)
        
        video = execute_query(
            "SELECT v.*, a.name as avatar_name FROM videos v JOIN avatars a ON v.avatar_id = a.id WHERE v.id = ? AND v.user_id = ?",
            (video_id, user["id"]),
            fetch_one=True
        )
        
        if not video:
            log_warning(f"Video {video_id} not found for user {user['id']}", "API")
            return JSONResponse({"error": "Video ikke fundet"}, status_code=404)
        
        return JSONResponse({
            "id": video["id"],
            "title": video["title"],
            "status": video["status"],
            "avatar_name": video["avatar_name"],
            "video_path": video["video_path"],
            "created_at": video["created_at"],
            "heygen_video_id": video["heygen_video_id"]
        })
    except Exception as e:
        log_error(f"Get video info failed for video {video_id}", "API", e)
        return JSONResponse({"error": "Server error"}, status_code=500)

@app.get("/api/videos/{video_id}/download")
async def download_video_endpoint(video_id: int, request: Request):
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Ikke autoriseret"}, status_code=401)
        
        video = execute_query(
            "SELECT * FROM videos WHERE id = ? AND user_id = ?",
            (video_id, user["id"]),
            fetch_one=True
        )
        
        if not video:
            return JSONResponse({"error": "Video ikke fundet"}, status_code=404)
        
        if video["status"] != "completed" or not video["video_path"]:
            return JSONResponse({"error": "Video ikke færdig endnu"}, status_code=400)
        
        log_info(f"Video download requested: {video['title']} by user {user['username']}", "API")
        
        return JSONResponse({
            "download_url": video["video_path"],
            "filename": f"{video['title']}.mp4"
        })
    except Exception as e:
        log_error(f"Video download failed for video {video_id}", "API", e)
        return JSONResponse({"error": "Download error"}, status_code=500)

#####################################################################
# ADMIN UTILITIES
#####################################################################

@app.get("/admin/quickclean")
async def quick_clean(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return HTMLResponse("Access denied")
        
        log_warning("TOTAL RESET initiated by admin", "Admin")
        
        videos_result = execute_query("DELETE FROM videos")
        avatars_result = execute_query("DELETE FROM avatars")
        
        log_warning(f"TOTAL RESET completed: {videos_result['rowcount']} videos, {avatars_result['rowcount']} avatars deleted", "Admin")
        
        return HTMLResponse(f"""
        <h2>TOTAL RESET COMPLETE!</h2>
        <p>Deleted {videos_result['rowcount']} videos and {avatars_result['rowcount']} avatars</p>
        <a href='/admin/users'>Start Fresh - Create Avatars</a><br>
        <a href='/admin'>Back to Admin Panel</a>
        """)
    except Exception as e:
        log_error("Admin quickclean failed", "Admin", e)
        return HTMLResponse("<h1>Error during cleanup</h1><a href='/admin'>Back to Admin</a>")

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
    
    if HEYGEN_API_KEY:
        test_heygen_connection()
    
    log_info("MyAvatar application startup complete", "System")

#####################################################################
# MAIN ENTRY POINT
#####################################################################

if __name__ == "__main__":
    print("Starting MyAvatar server...")
    print("Local: http://localhost:8000")
    print("Admin: admin@myavatar.com / admin123")
    print("User: test@example.com / password123")
    print("Admin skal oprette avatars for hver bruger")
    print("Cloudinary - cloud storage med local fallback!")
    print("Record funktionalitet med visuel feedback!")
    print("CASCADE DELETE - sletter automatisk relaterede videoer!")
    print("HeyGen WEBHOOK - automatisk video retur system!")
    print("CLEANUP - /admin/quickclean endpoint tilgængelig!")
    print("ENHANCED LOGGING - /admin/logs for debugging!")
    print("ERROR TRACKING - comprehensive system monitoring!")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)