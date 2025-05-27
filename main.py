"""
MyAvatar - Complete Working Application
Railway-compatible with PostgreSQL + NO CLOUDINARY + Visual Record Feedback + CASCADE DELETE
Fixed all signature issues - Just works!
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
# HEYGEN API HANDLER - DIRECT HTTP IMPLEMENTATION
#####################################################################
def create_video_from_audio_file(api_key: str, avatar_id: str, audio_url: str, video_format: str = "16:9"):
    """
    Create HeyGen video using direct HTTP requests with format selection
    """
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    # Set dimensions based on format
    if video_format == "9:16":
        # Portrait (stående) - Social Media
        width, height = 720, 1280
        print(f"📱 Using Portrait format: {width}x{height}")
    else:
        # Landscape (siddende) - Business/default
        width, height = 1280, 720
        print(f"🖥️ Using Landscape format: {width}x{height}")
    
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
        print(f"🚀 Sending request to HeyGen API...")
        print(f"📄 Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers=headers,
            json=payload
        )
        
        print(f"📤 HeyGen Response Status: {response.status_code}")
        print(f"📤 HeyGen Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            video_id = result.get("data", {}).get("video_id")
            return {
                "success": True,
                "video_id": video_id,
                "message": f"Video generation started successfully ({video_format})",
                "format": video_format,
                "dimensions": f"{width}x{height}"
            }
        else:
            return {
                "success": False,
                "error": f"HeyGen API returned status {response.status_code}: {response.text}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"HeyGen API request failed: {str(e)}"
        }

def test_heygen_connection():
    """Quick test of HeyGen API connection"""
    heygen_key = os.getenv("HEYGEN_API_KEY", "")
    if not heygen_key:
        print("❌ HEYGEN_API_KEY not found")
        return
    
    print(f"🔑 Testing HeyGen API with key: {heygen_key[:10]}...")
    
    # Test med en dummy audio URL (dette vil fejle pga. invalid avatar, men vi tester connection)
    test_result = create_video_from_audio_file(
        api_key=heygen_key,
        avatar_id="test_avatar_id", # Dette vil fejle, men vi tester connection
        audio_url="https://www.soundjay.com/misc/bell-ringing-05.wav", # Dummy URL
        video_format="16:9"
    )
    
    print(f"🎯 HeyGen Connection Test Result: {test_result}")
    return test_result

HEYGEN_HANDLER_AVAILABLE = True
print("✅ HeyGen API handler loaded successfully (HTTP implementation)")

#####################################################################
# CONFIGURATION
#####################################################################
SECRET_KEY = "your_secret_key_here_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# HeyGen Configuration
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
HEYGEN_BASE_URL = "https://api.heygen.com"

# Base URL - Railway will set this correctly
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

# Create necessary directories
os.makedirs("static/uploads/audio", exist_ok=True)
os.makedirs("static/uploads/images", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

# Static files - Railway compatible
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    print("✅ Static files mounted: static")
except Exception as e:
    print(f"⚠️ Static files error: {e}")

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
# DATABASE FUNCTIONS - POSTGRESQL + SQLITE SUPPORT
#####################################################################
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_db_connection():
    """Get database connection - PostgreSQL on Railway, SQLite locally"""
    database_url = os.getenv("DATABASE_URL")
    
    if database_url and POSTGRESQL_AVAILABLE:
        # Railway PostgreSQL connection
        print("[INFO] Using PostgreSQL database (Railway)")
        try:
            conn = psycopg2.connect(database_url)
            return conn, True
        except Exception as e:
            print(f"[ERROR] PostgreSQL connection failed: {e}")
            raise
    else:
        # Local SQLite fallback
        print("[INFO] Using SQLite database (local)")
        conn = sqlite3.connect("myavatar.db")
        conn.row_factory = sqlite3.Row
        return conn, False

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
    """Execute database query with automatic PostgreSQL/SQLite compatibility"""
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

def init_database():
    """Initialize database - NO DEFAULT AVATARS"""
    print("🗃️ Initializing database...")
    
    database_url = os.getenv("DATABASE_URL")
    is_postgresql = bool(database_url and POSTGRESQL_AVAILABLE)
    
    conn, _ = get_db_connection()
    cursor = conn.cursor()
    
    if is_postgresql:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # PostgreSQL syntax
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
        # SQLite syntax
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
    
    # Check if we need to create default users
    cursor.execute("SELECT COUNT(*) as user_count FROM users")
    result = cursor.fetchone()
    
    # Handle different result formats between PostgreSQL and SQLite
    if is_postgresql:
        existing_users = result['user_count']
    else:
        existing_users = result[0]
    
    print(f"[DEBUG] Found {existing_users} existing users")
    
    if existing_users == 0:
        print("Creating default users...")
        
        # Create admin user
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
        
        print("✅ Default users created (admin/admin123, testuser/password123)")
        print("⚠️  NO default avatars - Admin must create avatars for each user")
    else:
        print("✅ Users already exist, skipping default creation")
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialization complete ({'PostgreSQL' if is_postgresql else 'SQLite'})")

# Initialize database on startup
init_database()

#####################################################################
# AUTHENTICATION FUNCTIONS
#####################################################################
def authenticate_user(username: str, password: str):
    user = execute_query("SELECT * FROM users WHERE username = ?", (username,), fetch_one=True)
    
    if not user or not verify_password(password, user["hashed_password"]):
        return False
    return user

def authenticate_user_by_email(email: str, password: str):
    """Authenticate user by email (for client login)"""
    user = execute_query("SELECT * FROM users WHERE email = ?", (email,), fetch_one=True)
    
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
    
    user = execute_query("SELECT * FROM users WHERE username = ?", (username,), fetch_one=True)
    return user

def is_admin(request: Request):
    user = get_current_user(request)
    return user and user.get("is_admin", 0) == 1

#####################################################################
# HTML TEMPLATES
#####################################################################

# Marketing Landing Page
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
    <div class="logo">
        <img src="/static/images/myavatar_logo.png" alt="MyAvatars.dk" onerror="this.style.display='none'">
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

# Dashboard with IMPROVED Record Button + Visual Feedback
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
        
        /* IMPROVED RECORD BUTTON WITH ANIMATIONS */
        .record-btn {
            background: #dc2626;
            color: white;
            border: none;
            border-radius: 50%;
            width: 80px;
            height: 80px;
            font-size: 16px;
            cursor: pointer;
            margin: 10px;
            transition: all 0.3s ease;
            position: relative;
            box-shadow: 0 4px 8px rgba(220, 38, 38, 0.3);
        }
        
        .record-btn:hover {
            background: #b91c1c;
            transform: scale(1.05);
        }
        
        .record-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        /* RECORDING STATE - Pulsing animation */
        .record-btn.recording {
            background: #ef4444;
            animation: pulse-record 1.5s infinite;
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.6);
        }
        
        @keyframes pulse-record {
            0% { transform: scale(1); box-shadow: 0 0 20px rgba(239, 68, 68, 0.6); }
            50% { transform: scale(1.1); box-shadow: 0 0 30px rgba(239, 68, 68, 0.8); }
            100% { transform: scale(1); box-shadow: 0 0 20px rgba(239, 68, 68, 0.6); }
        }
        
        /* RECORDING INDICATOR */
        .recording-indicator {
            display: none;
            color: #dc2626;
            font-weight: bold;
            margin: 10px 0;
            animation: blink 1s infinite;
        }
        
        .recording-indicator.active {
            display: block;
        }
        
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0.3; }
        }
        
        .audio-preview { width: 100%; margin: 20px 0; }
        .status-message { margin: 15px 0; padding: 10px; border-radius: 5px; }
        .status-message.success { background: #dcfce7; color: #16a34a; border: 1px solid #bbf7d0; }
        .status-message.error { background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; }
        .status-message.info { background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; }
        .format-info { background: #f8f9fa; padding: 10px; border-radius: 4px; font-size: 0.9em; color: #6b7280; margin-top: 5px; }
        
        /* RECORDING TIMER */
        .recording-timer {
            display: none;
            font-size: 1.5em;
            color: #dc2626;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .recording-timer.active {
            display: block;
        }
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
                        
                        // Reset visual state
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
            
            // Update UI
            const recordBtn = document.getElementById('record-btn');
            const indicator = document.getElementById('recording-indicator');
            const timer = document.getElementById('recording-timer');
            
            recordBtn.textContent = 'Stop';
            recordBtn.classList.add('recording');
            indicator.classList.add('active');
            timer.classList.add('active');
            
            // Start timer
            window.recordingTimer = setInterval(updateTimer, 100);
            
            showStatusMessage('🔴 Optagelse i gang... Klik Stop når du er færdig', 'info');
        }
        
        function stopRecording() {
            window.mediaRecorder.stop();
            window.isRecording = false;
            
            // Clear timer
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
            
            const timerDisplay = `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
            document.getElementById('recording-timer').textContent = timerDisplay;
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
                showStatusMessage('❌ Optag venligst lyd først', 'error');
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
                    showStatusMessage(`🚀 Sender til HeyGen (${videoFormat})... Dette kan tage et øjeblik`, 'info');
                    document.getElementById('heygen-submit-btn').disabled = true;
                    
                    fetch('/api/heygen', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showStatusMessage(`✅ Video generering startet! Format: ${data.format || videoFormat} (${data.dimensions || ''})`, 'success');
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
                <div class="format-info">
                    💡 Tip: Vælg 16:9 for business/præsentationer, 9:16 for social media
                </div>
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
            <ul>
            {% for video in videos %}
                <li style="margin-bottom: 10px;">
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
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔧 Admin Dashboard</h1>
            <div>
                <a href="/dashboard" class="btn">Dashboard</a>
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
            <h2>📊 System Status</h2>
            <p><strong>HeyGen API:</strong> ✅ Tilgængelig</p>
            <p><strong>Storage:</strong> ✅ Lokal (Railway)</p>
            <p><strong>Database:</strong> ✅ PostgreSQL</p>
            <p><strong>Cloudinary:</strong> ❌ Deaktiveret (bruger lokal storage)</p>
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
    
    users = execute_query("SELECT * FROM users ORDER BY id ASC", fetch_all=True)
    
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

@app.get("/admin/user/{user_id}/avatars", response_class=HTMLResponse)
async def admin_user_avatars(request: Request, user_id: int = Path(...)):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    user = execute_query("SELECT * FROM users WHERE id=?", (user_id,), fetch_one=True)
    if not user:
        return HTMLResponse("<h3>Bruger ikke fundet</h3><a href='/admin/users'>Tilbage</a>")
    
    avatars = execute_query("SELECT * FROM avatars WHERE user_id=? ORDER BY created_at DESC", (user_id,), fetch_all=True)
    
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
        # LOCAL FILE UPLOAD - NO CLOUDINARY
        img_bytes = await avatar_img.read()
        
        # Save image locally
        img_filename = f"avatar_{uuid.uuid4().hex}.{avatar_img.filename.split('.')[-1]}"
        img_path = f"static/uploads/images/{img_filename}"
        
        with open(img_path, "wb") as f:
            f.write(img_bytes)
        
        # Use Railway URL for serving
        img_url = f"{BASE_URL}/{img_path}"
        print(f"[DEBUG] Avatar image saved locally: {img_url}")
        
        # Save to database
        result = execute_query(
            "INSERT INTO avatars (user_id, name, image_path, heygen_avatar_id) VALUES (?, ?, ?, ?)",
            (user_id, avatar_name, img_url, heygen_avatar_id)
        )
        
        print(f"[DEBUG] Database insert: {result['rowcount']} rows affected")
        
        if result['rowcount'] > 0:
            return RedirectResponse(url=f"/admin/user/{user_id}/avatars?success=Avatar tilføjet succesfuldt", status_code=303)
        else:
            return RedirectResponse(url=f"/admin/user/{user_id}/avatars?error=Database fejl", status_code=303)
            
    except Exception as e:
        print(f"[ERROR] Avatar creation failed: {str(e)}")
        return RedirectResponse(url=f"/admin/user/{user_id}/avatars?error=Fejl: {str(e)}", status_code=303)

@app.post("/admin/user/{user_id}/avatars/delete/{avatar_id}", response_class=HTMLResponse)
async def admin_delete_avatar(request: Request, user_id: int = Path(...), avatar_id: int = Path(...)):
    # Admin authentication check
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    try:
        print(f"🗑️ Starting cascade delete for avatar {avatar_id} (user {user_id})")
        
        # Step 1: Delete all videos that reference this avatar
        videos_deleted = execute_query(
            "DELETE FROM videos WHERE avatar_id=?", 
            (avatar_id,),
            fetch_all=True
        )
        
        if videos_deleted:
            video_count = len(videos_deleted)
            print(f"✅ Deleted {video_count} video(s) referencing avatar {avatar_id}")
        else:
            print(f"ℹ️ No videos found for avatar {avatar_id}")
        
        # Step 2: Delete the avatar itself
        avatar_deleted = execute_query(
            "DELETE FROM avatars WHERE id=? AND user_id=?", 
            (avatar_id, user_id)
        )
        
        if avatar_deleted['rowcount'] > 0:
            print(f"✅ Avatar {avatar_id} deleted successfully")
            success_msg = f"Avatar slettet succesfuldt"
            if videos_deleted:
                success_msg += f" (inkl. {len(videos_deleted)} relaterede video(er))"
        else:
            print(f"⚠️ Avatar {avatar_id} not found or access denied")
            return RedirectResponse(
                url=f"/admin/user/{user_id}/avatars?error=Avatar ikke fundet", 
                status_code=303
            )
        
        return RedirectResponse(
            url=f"/admin/user/{user_id}/avatars?success={success_msg}", 
            status_code=303
        )
        
    except Exception as e:
        print(f"❌ Error during cascade delete: {e}")
        return RedirectResponse(
            url=f"/admin/user/{user_id}/avatars?error=Kunne ikke slette avatar", 
            status_code=303
        )

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
            <h2>➕ Opret Ny Bruger</h2>
            
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

@app.get("/admin/reset-password/{user_id}", response_class=HTMLResponse)
async def admin_reset_password_page(request: Request, user_id: int = Path(...)):
    admin = get_current_user(request)
    if not admin or admin.get("is_admin", 0) != 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    target_user = execute_query("SELECT * FROM users WHERE id = ?", (user_id,), fetch_one=True)
    
    if not target_user:
        return RedirectResponse(url="/admin/users?error=Bruger ikke fundet", status_code=status.HTTP_302_FOUND)
    
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
            <h2>🔐 Reset Password</h2>
            
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
    result = execute_query(
        "UPDATE users SET hashed_password = ? WHERE id = ?",
        (hashed_password, user_id)
    )
    
    if result['rowcount'] > 0:
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
# API ENDPOINTS - HEYGEN INTEGRATION - LOCAL FILE STORAGE
#####################################################################

@app.post("/api/heygen")
async def create_heygen_video(
    request: Request,
    title: str = Form(...),
    avatar_id: int = Form(...),
    video_format: str = Form(default="16:9"),
    audio: UploadFile = File(...)
):
    """HeyGen integration - LOCAL file storage (NO CLOUDINARY)"""
    try:
        user = get_current_user(request)
        if not user:
            return JSONResponse({"error": "Ikke autoriseret"}, status_code=401)

        if not HEYGEN_API_KEY:
            return JSONResponse({"error": "HeyGen API nøgle ikke fundet"}, status_code=500)

        # Get avatar details from database
        avatar = execute_query("SELECT * FROM avatars WHERE id = ? AND user_id = ?", (avatar_id, user["id"]), fetch_one=True)
        
        if not avatar:
            return JSONResponse({"error": "Avatar ikke fundet"}, status_code=404)
        
        heygen_avatar_id = avatar.get('heygen_avatar_id')

        print(f"[DEBUG] Video request by user: {user['id']} / {user.get('username')}")
        print(f"[DEBUG] Requested avatar_id: {avatar_id}")
        print(f"[DEBUG] Using heygen_avatar_id: {heygen_avatar_id}")
        print(f"[DEBUG] Video format: {video_format}")
        
        if not heygen_avatar_id:
            return JSONResponse({"error": "Manglende HeyGen avatar ID"}, status_code=500)
        
        # LOCAL FILE UPLOAD - Railway serves static files publicly
        audio_bytes = await audio.read()
        try:
            # Gem filen lokalt med unikt navn
            audio_filename = f"audio_{uuid.uuid4().hex}.wav"
            audio_path = f"static/uploads/audio/{audio_filename}"
            
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)
            
            # Railway URL som HeyGen kan tilgå
            audio_url = f"{BASE_URL}/static/uploads/audio/{audio_filename}"
            print(f"[DEBUG] Local file saved and accessible at: {audio_url}")
            
        except Exception as e:
            print(f"[ERROR] Local file save failed: {str(e)}")
            return JSONResponse({"error": f"Fil upload fejlede: {str(e)}"}, status_code=500)

        # Save to database
        result = execute_query(
            "INSERT INTO videos (user_id, avatar_id, title, audio_path, status) VALUES (?, ?, ?, ?, ?)",
            (user["id"], avatar_id, title, audio_url, "processing")
        )
        video_id = result['lastrowid']

        # Call HeyGen API with local audio URL and format
        print("🚀 Using HeyGen API (HTTP implementation)")
        heygen_result = create_video_from_audio_file(
            api_key=HEYGEN_API_KEY,
            avatar_id=heygen_avatar_id,
            audio_url=audio_url,
            video_format=video_format
        )
        
        if heygen_result["success"]:
            # Update database with HeyGen video ID
            execute_query(
                "UPDATE videos SET heygen_video_id = ?, status = ? WHERE id = ?",
                (heygen_result.get("video_id"), "processing", video_id)
            )
        
        return JSONResponse(heygen_result)

    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
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
        "handler_available": HEYGEN_HANDLER_AVAILABLE,
        "base_url": BASE_URL,
        "storage": "local_files"
    }

@app.get("/api/users")
async def get_users(request: Request):
    """Get all users (admin only)"""
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = execute_query("SELECT id, username, email, is_admin, created_at FROM users", fetch_all=True)
    
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
    print(f"✅ Storage: Local files (NO Cloudinary)")
    print("⚠️  NO default avatars - Admin must create avatars for users")
    
    # Test HeyGen connection
    if HEYGEN_API_KEY:
        test_heygen_connection()

#####################################################################
# MAIN ENTRY POINT
#####################################################################

if __name__ == "__main__":
    print("🌟 Starting MyAvatar server...")
    print("🔗 Local: http://localhost:8000")
    print("🔑 Admin: admin@myavatar.com / admin123")
    print("👤 User: test@example.com / password123")
    print("📋 Admin skal oprette avatars for hver bruger")
    print("🎯 NO Cloudinary - bruger lokal fil storage!")
    print("🎬 Forbedret record funktion med visuel feedback!")
    print("🗑️ CASCADE DELETE - sletter automatisk relaterede videoer!")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
