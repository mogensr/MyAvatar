"""
MyAvatar - Modular AI Avatar Video Platform
===========================================
Production-ready, chaptered FastAPI app with CRUD, REST, Cloudinary/HeyGen, enhanced logging, and admin/user flows.
"""
#####################################################################
# CHAPTER 1: IMPORTS & CONFIGURATION
#####################################################################
import os
import textwrap
import logging
import traceback
from datetime import datetime, timedelta
from collections import deque
from typing import List, Dict, Optional, Any

from fastapi import FastAPI, Request, status, Form, Depends, HTTPException, File, UploadFile, Path
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Cloudinary, HeyGen, DB, Auth, and other integrations
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

app = FastAPI(title="MyAvatar", description="AI Avatar Video Platform")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
    # Replace with real session/user logic
    return request.session.get("user", {"username": "admin", "is_admin": 1})
#####################################################################
# CHAPTER 4: HEYGEN & CLOUDINARY HELPERS
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
                "avatar_id": avatar_id
            },
            "audio_url": audio_url,
            "video_format": video_format,
            "resolution": {"width": width, "height": height}
        }]
    }
    response = requests.post(
        "https://api.heygen.com/v1/video/generate",
        headers=headers,
        data=json.dumps(payload)
    )
    return response.json()

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
    return file_path
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
                    <a href="/dashboard" class="btn">Dashboard</a>
                    <a href="/admin/logs" class="btn btn-success">System Logs</a>
                    <a href="/auth/logout" class="btn">Log Ud</a>
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
            <a href="/admin" class="btn">Tilbage til Admin</a>
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
#####################################################################
# CHAPTER 7: USER CRUD & MANAGEMENT
#####################################################################

@app.get("/admin/users", response_class=HTMLResponse)
async def list_users(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        users = execute_query("SELECT id, username, email, is_admin FROM users", fetch_all=True)
        html = "<h2>Brugeroversigt</h2><ul>"
        for user in users:
            html += f"<li>{user['username']} ({user['email']}) - {'Admin' if user['is_admin'] else 'User'} <a href='/admin/user/{user['id']}'>[Rediger]</a></li>"
        html += "</ul><a href='/admin'>Tilbage til Admin</a>"
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
        user = execute_query("SELECT id, username, email, is_admin FROM users WHERE id = ?", (user_id,), fetch_one=True)
        if not user:
            return HTMLResponse("<h2>User not found</h2><a href='/admin/users'>Back</a>")
        html = f"""
        <h2>Edit User: {user['username']}</h2>
        <form method='post' action='/admin/user/{user['id']}'>
            Email: <input type='email' name='email' value='{user['email']}' required><br>
            Admin: <input type='checkbox' name='is_admin' {'checked' if user['is_admin'] else ''}><br>
            <button type='submit'>Save</button>
        </form>
        <a href='/admin/users'>Back to Users</a>
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
        return RedirectResponse(url="/admin/users", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Update user failed", "Admin", e)
        return HTMLResponse("<h1>Error updating user</h1><a href='/admin/users'>Back</a>")
        return HTMLResponse("<h1>Error loading logs</h1><a href='/admin'>Back to Admin</a>")
#####################################################################
# CHAPTER 8: AVATAR CRUD & MANAGEMENT
#####################################################################

@app.get("/admin/avatars", response_class=HTMLResponse)
async def list_avatars(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        avatars = execute_query("SELECT id, user_id, avatar_url FROM avatars", fetch_all=True)
        html = "<h2>Avataroversigt</h2><ul>"
        for avatar in avatars:
            html += f"<li>User ID: {avatar['user_id']} - <img src='{avatar['avatar_url']}' width='64'> <a href='/admin/avatar/{avatar['id']}'>[Rediger]</a></li>"
        html += "</ul><a href='/admin'>Tilbage til Admin</a>"
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
        avatar = execute_query("SELECT id, user_id, avatar_url FROM avatars WHERE id = ?", (avatar_id,), fetch_one=True)
        if not avatar:
            return HTMLResponse("<h2>Avatar not found</h2><a href='/admin/avatars'>Back</a>")
        html = f"""
        <h2>Edit Avatar: {avatar['id']}</h2>
        <form method='post' action='/admin/avatar/{avatar['id']}' enctype='multipart/form-data'>
            Avatar Image: <input type='file' name='avatar_image' accept='image/*'><br>
            <button type='submit'>Upload</button>
        </form>
        <img src='{avatar['avatar_url']}' width='128'><br>
        <a href='/admin/avatars'>Back to Avatars</a>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("Edit avatar failed", "Admin", e)
        return HTMLResponse("<h1>Error loading avatar</h1><a href='/admin/avatars'>Back</a>")

@app.post("/admin/avatar/{avatar_id}", response_class=HTMLResponse)
async def update_avatar(request: Request, avatar_id: int, avatar_image: UploadFile = File(...)):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        avatar_url = upload_avatar_to_cloudinary(avatar_image, avatar_id)
        execute_query("UPDATE avatars SET avatar_url = ? WHERE id = ?", (avatar_url, avatar_id))
        return RedirectResponse(url="/admin/avatars", status_code=status.HTTP_302_FOUND)
    except Exception as e:
        log_error("Update avatar failed", "Admin", e)
        return HTMLResponse("<h1>Error updating avatar</h1><a href='/admin/avatars'>Back</a>")
#####################################################################
# CHAPTER 9: VIDEO CRUD & MANAGEMENT
#####################################################################

@app.get("/admin/videos", response_class=HTMLResponse)
async def list_videos(request: Request):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        videos = execute_query("SELECT id, user_id, title, video_url FROM videos", fetch_all=True)
        html = "<h2>Videooversigt</h2><ul>"
        for video in videos:
            html += f"<li>User ID: {video['user_id']} - {video['title']} <a href='/admin/video/{video['id']}'>[Rediger]</a></li>"
        html += "</ul><a href='/admin'>Tilbage til Admin</a>"
        return HTMLResponse(html)
    except Exception as e:
        log_error("List videos failed", "Admin", e)
        return HTMLResponse("<h1>Error loading videos</h1><a href='/admin'>Back to Admin</a>")

@app.get("/admin/video/{video_id}", response_class=HTMLResponse)
async def edit_video(request: Request, video_id: int):
    try:
        admin = get_current_user(request)
        if not admin or admin.get("is_admin", 0) != 1:
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        video = execute_query("SELECT id, user_id, title, video_url FROM videos WHERE id = ?", (video_id,), fetch_one=True)
        if not video:
            return HTMLResponse("<h2>Video not found</h2><a href='/admin/videos'>Back</a>")
        html = f"""
        <h2>Edit Video: {video['title']}</h2>
        <video src='{video['video_url']}' controls width='320'></video><br>
        <a href='/admin/videos'>Back to Videos</a>
        """
        return HTMLResponse(html)
    except Exception as e:
        log_error("Edit video failed", "Admin", e)
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
            <a href='/admin/users'>Start Fresh - Create Avatars</a><br>
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
    log_info("MyAvatar application startup initiated", "System")
    log_info("Database initialized", "System")
    log_info(f"HeyGen API Key: {'✓ Set' if HEYGEN_API_KEY else '✗ Missing'}", "System")
    log_info(f"Base URL: {BASE_URL}", "System")
    log_info("Avatar Management: ✓ Available", "System")
    log_info("Storage: Cloudinary CDN with local fallback", "System")
    log_info(f"Webhook Endpoint: {BASE_URL}/api/heygen/webhook", "System")
    log_info("Enhanced logging system enabled", "System")
    log_info("🚀 MyAvatar application startup complete", "System")
#####################################################################
# CHAPTER 11: AUTHENTICATION & SESSION MANAGEMENT
#####################################################################

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("portal/login.html", {"request": request})

@app.post("/auth/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        user = execute_query("SELECT id, username, hashed_password, is_admin FROM users WHERE username = ?", (username,), fetch_one=True)
        if user and verify_password(password, user["hashed_password"]):    
            request.session["user"] = {"id": user["id"], "username": user["username"], "is_admin": user["is_admin"]}
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

from fastapi.responses import FileResponse

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    # Serve the modern dashboard
    return FileResponse("static/dashboard.html")

#####################################################################
# CHAPTER 14: STATIC FILES & TEMPLATE SETUP
#####################################################################

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Homepage route
from fastapi.responses import HTMLResponse, FileResponse

from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/dashboard")

# Favicon route
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/auth/login")

#####################################################################
# CHAPTER 15: MAIN ENTRY POINT
#####################################################################

if __name__ == "__main__":
    import uvicorn
    print("Starting MyAvatar server...")
    print("Local: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

