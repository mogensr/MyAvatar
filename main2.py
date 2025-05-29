import os
import textwrap
import logging
from datetime import datetime
from fastapi import FastAPI, Request, Form, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional

# --- CONFIGURATION ---
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "dev-secret"))
app.mount("/static", StaticFiles(directory="static"), name="static")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("myavatar")

# --- IN-MEMORY MOCK DATABASES ---
USERS = [
    {"id": 1, "username": "admin", "is_admin": 1, "email": "admin@example.com", "password": "admin"},
    {"id": 2, "username": "user", "is_admin": 0, "email": "user@example.com", "password": "user"}
]
AVATARS = []  # [{id, user_id, name, url}]
VIDEOS = []   # [{id, user_id, avatar_id, url, status, created_at}]
UPLOADED_IMAGES = []  # [{user_id, filename, url}]
LOGS = []  # [{timestamp, module, level, message}]

# --- AUTH HELPERS ---
def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        user = next((u for u in USERS if u["id"] == user_id), None)
        if user:
            return user
    return None

def authenticate_user(email: str, password: str):
    return next((u for u in USERS if u["email"] == email and u["password"] == password), None)

def require_admin(user):
    return user and user.get("is_admin", 0) == 1

# --- LOGGING HELPERS ---
def log_info(msg, module="App"):
    logger.info(f"[{module}] {msg}")
    LOGS.append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "module": module, "level": "INFO", "message": msg})
def log_error(msg, module="App", e=None):
    logger.error(f"[{module}] {msg} {e if e else ''}")
    LOGS.append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "module": module, "level": "ERROR", "message": msg})
def log_warning(msg, module="App"):
    logger.warning(f"[{module}] {msg}")
    LOGS.append({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "module": module, "level": "WARNING", "message": msg})

# --- HTML TEMPLATES (Shortened for brevity, can expand as needed) ---
admin_dashboard_html = textwrap.dedent("""
<!DOCTYPE html><html><head><title>Admin Dashboard</title></head><body><h1>Admin Dashboard</h1>
<a href="/admin/users">User Management</a> | <a href="/admin/avatars">Avatar Management</a> | <a href="/admin/videos">Video Management</a> | <a href="/admin/logs">Logs</a> | <a href="/admin/quickclean">Quick Clean</a> | <a href="/logout">Logout</a></body></html>
""")
user_dashboard_html = textwrap.dedent("""
<!DOCTYPE html><html><head><title>User Dashboard</title></head><body><h1>User Dashboard</h1>
<a href="/dashboard/avatars">My Avatars</a> | <a href="/dashboard/videos">My Videos</a> | <a href="/dashboard/upload-image">Upload Background Image</a> | <a href="/logout">Logout</a><br>{uploaded_images}</body></html>
""")

# --- ROUTES ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = get_current_user(request)
    if user:
        if user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return HTMLResponse("<h2>Welcome! Please <a href='/login'>login</a>.</h2>")

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return HTMLResponse("""
        <h2>Login</h2>
        <form method='post' action='/login'>
            Email: <input type='email' name='email' required><br>
            Password: <input type='password' name='password' required><br>
            <button type='submit'>Login</button>
        </form>
    """)

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = authenticate_user(email, password)
    if user:
        request.session["user_id"] = user["id"]
        if user.get("is_admin", 0) == 1:
            return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return HTMLResponse("<h3>Invalid credentials. <a href='/login'>Try again</a></h3>")

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

# --- User Dashboard ---
@app.get("/dashboard", response_class=HTMLResponse)
def user_dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    uploaded_images_html = "".join([
        f'<img src="/static/uploads/{img["filename"]}" style="max-width:200px; margin:10px;" />' for img in UPLOADED_IMAGES if img['user_id'] == user['id']
    ])
    html = user_dashboard_html.format(uploaded_images=uploaded_images_html)
    return HTMLResponse(html)

@app.get("/dashboard/upload-image", response_class=HTMLResponse)
def upload_image_form(request: Request):
    return HTMLResponse("""
        <h2>Upload Background Image</h2>
        <form action="/dashboard/upload-image" method="post" enctype="multipart/form-data">
            <input type="file" name="image" accept="image/*" required />
            <button type="submit">Upload</button>
        </form>
    """)

@app.post("/dashboard/upload-image", response_class=HTMLResponse)
def upload_image(request: Request, image: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
    file_path = os.path.join("static", "uploads", filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(image.file.read())
    UPLOADED_IMAGES.append({"user_id": user["id"], "filename": filename, "url": f"/static/uploads/{filename}"})
    log_info(f"User {user['username']} uploaded image: {filename}", "User")
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)

# --- Admin Dashboard ---
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return HTMLResponse(admin_dashboard_html)

@app.get("/admin/logs", response_class=HTMLResponse)
def admin_logs(request: Request):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    log_entries = "".join([
        f'<div><span>{log["timestamp"]}</span> | <b>[{log["module"]}]</b> | <span>{log["level"]}</span> | {log["message"]}</div>' for log in LOGS[-200:]
    ])
    html = f"<h2>Logs (last 200)</h2><div>{log_entries}</div>"
    return HTMLResponse(html)

@app.get("/admin/quickclean", response_class=HTMLResponse)
def quick_clean(request: Request):
    user = get_current_user(request)
    if not require_admin(user):
        return HTMLResponse("Access denied")
    AVATARS.clear()
    VIDEOS.clear()
    UPLOADED_IMAGES.clear()
    LOGS.clear()
    log_warning("TOTAL RESET initiated by admin", "Admin")
    html = "<h2>RESET COMPLETE</h2><p>All avatars, videos, and images deleted.</p><a href='/admin'>Back to Admin Panel</a>"
    return HTMLResponse(html)

# --- User Management (CRUD) ---
@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    users_html = "<h2>Users</h2><table border='1'><tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th><th>Actions</th></tr>"
    for u in USERS:
        users_html += f"<tr><td>{u['id']}</td><td>{u['username']}</td><td>{u['email']}</td><td>{'Admin' if u['is_admin'] else 'User'}</td>"
        users_html += f"<td><a href='/admin/users/edit/{u['id']}'>Edit</a> | <a href='/admin/users/delete/{u['id']}'>Delete</a></td></tr>"
    users_html += "</table>"
    users_html += """
    <h3>Add User</h3>
    <form method='post' action='/admin/users/add'>
        Username: <input name='username' required> Email: <input name='email' required> 
        Password: <input name='password' required> 
        Admin: <input type='checkbox' name='is_admin'>
        <button type='submit'>Add</button>
    </form>
    <a href='/admin'>Back</a>"""
    return HTMLResponse(users_html)

@app.post("/admin/users/add")
def admin_add_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), is_admin: Optional[str] = Form(None)):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    new_id = max([u['id'] for u in USERS]+[0]) + 1
    USERS.append({"id": new_id, "username": username, "email": email, "password": password, "is_admin": 1 if is_admin else 0})
    log_info(f"Admin added user {username}", "Admin")
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_302_FOUND)

@app.get("/admin/users/edit/{user_id}", response_class=HTMLResponse)
def admin_edit_user_form(request: Request, user_id: int):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    u = next((u for u in USERS if u['id'] == user_id), None)
    if not u:
        return HTMLResponse("User not found")
    checked = "checked" if u['is_admin'] else ""
    return HTMLResponse(f"""
        <h2>Edit User {u['username']}</h2>
        <form method='post' action='/admin/users/edit/{u['id']}'>
            Username: <input name='username' value='{u['username']}' required> 
            Email: <input name='email' value='{u['email']}' required> 
            Password: <input name='password' value='{u['password']}' required> 
            Admin: <input type='checkbox' name='is_admin' {checked}>
            <button type='submit'>Save</button>
        </form>
        <a href='/admin/users'>Back</a>")

@app.post("/admin/users/edit/{user_id}")
def admin_edit_user(request: Request, user_id: int, username: str = Form(...), email: str = Form(...), password: str = Form(...), is_admin: Optional[str] = Form(None)):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    for u in USERS:
        if u['id'] == user_id:
            u['username'] = username
            u['email'] = email
            u['password'] = password
            u['is_admin'] = 1 if is_admin else 0
            log_info(f"Admin edited user {username}", "Admin")
            break
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_302_FOUND)

@app.get("/admin/users/delete/{user_id}")
def admin_delete_user(request: Request, user_id: int):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    global USERS
    USERS = [u for u in USERS if u['id'] != user_id]
    log_info(f"Admin deleted user id {user_id}", "Admin")
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_302_FOUND)

# --- Avatar Management (CRUD) ---
@app.get("/admin/avatars", response_class=HTMLResponse)
def admin_avatars(request: Request):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    avatars_html = "<h2>Avatars</h2><table border='1'><tr><th>ID</th><th>Name</th><th>URL</th><th>User</th><th>Actions</th></tr>"
    for a in AVATARS:
        owner = next((u['username'] for u in USERS if u['id'] == a['user_id']), 'N/A')
        avatars_html += f"<tr><td>{a['id']}</td><td>{a['name']}</td><td>{a['url']}</td><td>{owner}</td>"
        avatars_html += f"<td><a href='/admin/avatars/edit/{a['id']}'>Edit</a> | <a href='/admin/avatars/delete/{a['id']}'>Delete</a></td></tr>"
    avatars_html += "</table>"
    avatars_html += """
    <h3>Add Avatar</h3>
    <form method='post' action='/admin/avatars/add'>
        Name: <input name='name' required> URL: <input name='url' required> 
        User ID: <input name='user_id' required type='number'>
        <button type='submit'>Add</button>
    </form>
    <a href='/admin'>Back</a>"""
    return HTMLResponse(avatars_html)

@app.post("/admin/avatars/add")
def admin_add_avatar(request: Request, name: str = Form(...), url: str = Form(...), user_id: int = Form(...)):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    new_id = max([a['id'] for a in AVATARS]+[0]) + 1
    AVATARS.append({"id": new_id, "name": name, "url": url, "user_id": user_id})
    log_info(f"Admin added avatar {name}", "Admin")
    return RedirectResponse(url="/admin/avatars", status_code=status.HTTP_302_FOUND)

@app.get("/admin/avatars/edit/{avatar_id}", response_class=HTMLResponse)
def admin_edit_avatar_form(request: Request, avatar_id: int):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    a = next((a for a in AVATARS if a['id'] == avatar_id), None)
    if not a:
        return HTMLResponse("Avatar not found")
    return HTMLResponse(f"""
        <h2>Edit Avatar {a['name']}</h2>
        <form method='post' action='/admin/avatars/edit/{a['id']}'>
            Name: <input name='name' value='{a['name']}' required> 
            URL: <input name='url' value='{a['url']}' required> 
            User ID: <input name='user_id' value='{a['user_id']}' required type='number'>
            <button type='submit'>Save</button>
        </form>
        <a href='/admin/avatars'>Back</a>")

@app.post("/admin/avatars/edit/{avatar_id}")
def admin_edit_avatar(request: Request, avatar_id: int, name: str = Form(...), url: str = Form(...), user_id: int = Form(...)):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    for a in AVATARS:
        if a['id'] == avatar_id:
            a['name'] = name
            a['url'] = url
            a['user_id'] = user_id
            log_info(f"Admin edited avatar {name}", "Admin")
            break
    return RedirectResponse(url="/admin/avatars", status_code=status.HTTP_302_FOUND)

@app.get("/admin/avatars/delete/{avatar_id}")
def admin_delete_avatar(request: Request, avatar_id: int):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    global AVATARS
    AVATARS = [a for a in AVATARS if a['id'] != avatar_id]
    log_info(f"Admin deleted avatar id {avatar_id}", "Admin")
    return RedirectResponse(url="/admin/avatars", status_code=status.HTTP_302_FOUND)

# --- Video Management (CRUD) ---
@app.get("/admin/videos", response_class=HTMLResponse)
def admin_videos(request: Request):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    videos_html = "<h2>Videos</h2><table border='1'><tr><th>ID</th><th>URL</th><th>Status</th><th>User</th><th>Avatar</th><th>Created</th><th>Actions</th></tr>"
    for v in VIDEOS:
        owner = next((u['username'] for u in USERS if u['id'] == v['user_id']), 'N/A')
        avatar = next((a['name'] for a in AVATARS if a['id'] == v['avatar_id']), 'N/A')
        videos_html += f"<tr><td>{v['id']}</td><td>{v['url']}</td><td>{v['status']}</td><td>{owner}</td><td>{avatar}</td><td>{v['created_at']}</td>"
        videos_html += f"<td><a href='/admin/videos/edit/{v['id']}'>Edit</a> | <a href='/admin/videos/delete/{v['id']}'>Delete</a></td></tr>"
    videos_html += "</table>"
    videos_html += """
    <h3>Add Video</h3>
    <form method='post' action='/admin/videos/add'>
        URL: <input name='url' required> Status: <input name='status' required> 
        User ID: <input name='user_id' required type='number'>
        Avatar ID: <input name='avatar_id' required type='number'>
        <button type='submit'>Add</button>
    </form>
    <a href='/admin'>Back</a>"""
    return HTMLResponse(videos_html)

@app.post("/admin/videos/add")
def admin_add_video(request: Request, url: str = Form(...), status: str = Form(...), user_id: int = Form(...), avatar_id: int = Form(...)):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    new_id = max([v['id'] for v in VIDEOS]+[0]) + 1
    VIDEOS.append({"id": new_id, "url": url, "status": status, "user_id": user_id, "avatar_id": avatar_id, "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
    log_info(f"Admin added video {url}", "Admin")
    return RedirectResponse(url="/admin/videos", status_code=status.HTTP_302_FOUND)

@app.get("/admin/videos/edit/{video_id}", response_class=HTMLResponse)
def admin_edit_video_form(request: Request, video_id: int):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    v = next((v for v in VIDEOS if v['id'] == video_id), None)
    if not v:
        return HTMLResponse("Video not found")
    return HTMLResponse(f"""
        <h2>Edit Video {v['url']}</h2>
        <form method='post' action='/admin/videos/edit/{v['id']}'>
            URL: <input name='url' value='{v['url']}' required> 
            Status: <input name='status' value='{v['status']}' required> 
            User ID: <input name='user_id' value='{v['user_id']}' required type='number'>
            Avatar ID: <input name='avatar_id' value='{v['avatar_id']}' required type='number'>
            <button type='submit'>Save</button>
        </form>
        <a href='/admin/videos'>Back</a>")

@app.post("/admin/videos/edit/{video_id}")
def admin_edit_video(request: Request, video_id: int, url: str = Form(...), status: str = Form(...), user_id: int = Form(...), avatar_id: int = Form(...)):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    for v in VIDEOS:
        if v['id'] == video_id:
            v['url'] = url
            v['status'] = status
            v['user_id'] = user_id
            v['avatar_id'] = avatar_id
            log_info(f"Admin edited video {url}", "Admin")
            break
    return RedirectResponse(url="/admin/videos", status_code=status.HTTP_302_FOUND)

@app.get("/admin/videos/delete/{video_id}")
def admin_delete_video(request: Request, video_id: int):
    user = get_current_user(request)
    if not require_admin(user):
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    global VIDEOS
    VIDEOS = [v for v in VIDEOS if v['id'] != video_id]
    log_info(f"Admin deleted video id {video_id}", "Admin")
    return RedirectResponse(url="/admin/videos", status_code=status.HTTP_302_FOUND)

# --- Webhook Handler (HeyGen stub) ---
@app.post("/webhook/heygen")
def heygen_webhook(request: Request):
    # Simulate video completion
    data = {}  # Would parse JSON in real app
    log_info("HeyGen webhook received", "HeyGen")
    return JSONResponse({"status": "received"})

# --- Health Check ---
@app.get("/api/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# --- MAIN ENTRY ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main2:app", host="0.0.0.0", port=8000, reload=True)

.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "dev-secret"))
app.mount("/static", StaticFiles(directory="static"), name="static")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("myavatar")

# --- MOCK DB/UTILS ---
def get_current_user(request: Request):
    # Placeholder: always return admin
    return {"id": 1, "username": "admin", "is_admin": 1, "email": "admin@example.com"}

def get_password_hash(password):
    return "hashed-" + password

def log_info(msg, module="App"): logger.info(f"[{module}] {msg}")
def log_error(msg, module="App", e=None): logger.error(f"[{module}] {msg} {e if e else ''}")
def log_warning(msg, module="App"): logger.warning(f"[{module}] {msg}")

# --- HTML TEMPLATES ---
admin_dashboard_html = textwrap.dedent("""
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; }
        .container { max-width: 900px; margin: 40px auto; background: #fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 8px #0001; }
        .btn { background: #4f46e5; color: #fff; padding: 10px 18px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; margin: 5px; }
        .btn:hover { background: #3730a3; }
        .card { background: #f3f4f6; padding: 18px; margin-bottom: 15px; border-radius: 8px; }
        h1, h2 { color: #3730a3; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Admin Dashboard</h1>
        <a href="/admin/users" class="btn">User Management</a>
        <a href="/admin/logs" class="btn">View Logs</a>
        <a href="/admin/quickclean" class="btn">Quick Clean</a>
    </div>
</body>
</html>
""")

log_view_html = textwrap.dedent("""
<!DOCTYPE html>
<html>
<head>
    <title>System Logs</title>
    <style>
        body { font-family: 'Courier New', monospace; background: #1a1a1a; color: #fff; margin: 0; padding: 20px; }
        .header { background: #dc2626; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .card { background: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #444; }
        .btn { background: #4f46e5; color: white; padding: 10px 20px; border-radius: 5px; margin: 5px; }
        .btn:hover { background: #3730a3; }
        .log-entry { padding: 8px; margin: 2px 0; border-radius: 4px; font-size: 12px; }
        .log-info { background: #1e3a8a; color: #bfdbfe; }
        .log-warning { background: #92400e; color: #fcd34d; }
        .log-error { background: #7f1d1d; color: #fecaca; }
        .timestamp { color: #9ca3af; }
        .module { color: #34d399; font-weight: bold; }
    </style>
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
        <h3>Recent Activity</h3>
        <div style="max-height: 600px; overflow-y: scroll; background: #111; padding: 10px; border-radius: 4px;">
            {log_entries}
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
""")

# --- ROUTES ---
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return HTMLResponse(admin_dashboard_html)

@app.get("/admin/logs", response_class=HTMLResponse)
def admin_logs(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    # Mock log entries
    log_entries = "".join([
        f'<div class="log-entry log-info"><span class="timestamp">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span> | [App] | INFO | Log message {i}</div>'
        for i in range(10)
    ])
    html = log_view_html.format(log_entries=log_entries, recent_count=10, error_count=2)
    return HTMLResponse(html)

@app.get("/admin/quickclean", response_class=HTMLResponse)
def quick_clean(request: Request):
    user = get_current_user(request)
    if not user or user.get("is_admin", 0) != 1:
        return HTMLResponse("Access denied")
    # Mock DB clean
    log_warning("TOTAL RESET initiated by admin", "Admin")
    html = textwrap.dedent(f"""
        <h2>[RESET] TOTAL RESET COMPLETE!</h2>
        <p>Deleted all videos and avatars</p>
        <a href='/admin/users'>Start Fresh - Create Avatars</a><br>
        <a href='/admin'>Back to Admin Panel</a>
    """)
    return HTMLResponse(html.strip())

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# --- MAIN ENTRY ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main2:app", host="0.0.0.0", port=8000, reload=True)
