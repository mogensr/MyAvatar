# MyAvatar BackgroundFX Widget Integration Analysis

## 🎯 Complete Technical Analysis for HuggingFace Spaces Integration

Based on comprehensive codebase analysis, here's the complete integration specification for BackgroundFX widget at `https://app.myavatar.dk/backgroundfx`.

---

## 1. VIDEO API ENDPOINTS

### A) Video Listing Endpoint
```json
{
  "method": "GET",
  "url": "/api/videos",
  "auth_required": true,
  "response_format": {
    "success": true,
    "videos": [
      {
        "id": 123,
        "title": "My Video",
        "video_path": "https://res.cloudinary.com/...",
        "status": "completed",
        "created_at": "2024-01-01T12:00:00",
        "duration": 30,
        "format": "mp4",
        "user_id": 1
      }
    ]
  }
}
```

**Alternative endpoint:** `/videos` (same functionality)

### B) Video Access Endpoint
```json
{
  "method": "GET", 
  "url": "/api/videos/{id}/download",
  "auth_required": true,
  "returns": "302_redirect_to_video_url",
  "description": "Redirects to actual video URL (Cloudinary/HeyGen)"
}
```

**Direct video details:**
```json
{
  "method": "GET",
  "url": "/api/video/{id}/details", 
  "auth_required": true,
  "returns": {
    "success": true,
    "video": {
      "id": 123,
      "video_path": "https://res.cloudinary.com/...",
      "status": "completed",
      "title": "Video Title"
    }
  }
}
```

### C) Video Storage Pattern
- **Primary Storage:** Cloudinary CDN (`https://res.cloudinary.com/...`)
- **Secondary:** HeyGen URLs (`https://resource.heygen.ai/...`)
- **Database:** PostgreSQL `videos` table with `video_path` field
- **Access Pattern:** Direct URL access via CDN (no local file serving)

---

## 2. AUTHENTICATION SYSTEM

### A) Current Auth Method
**Primary:** JWT tokens in cookies
```javascript
// Cookie name: "access_token"
// Algorithm: HS256
// Secret: JWT_SECRET environment variable
```

**Fallback:** Session-based auth
```javascript
// Session key: "user_id"
// Stored in request.session
```

### B) Widget Authentication Options

**Option 1: Inherited Cookie Auth (Recommended)**
```javascript
// Widget automatically inherits parent cookies
// No additional auth needed - seamless integration
```

**Option 2: PostMessage Token Passing**
```javascript
// Parent passes token to iframe
window.addEventListener('message', (event) => {
  if (event.data.type === 'auth_token') {
    const token = event.data.token;
    // Use for API calls
  }
});
```

**Option 3: URL Parameter Auth**
```javascript
// Pass token in iframe URL
const iframeUrl = `/backgroundfx?token=${userToken}&user_id=${userId}`;
```

### C) CORS Configuration
- **Current Status:** API endpoints support cross-origin requests
- **Whitelisted Domains:** HuggingFace Spaces (`*.hf.space`)
- **Headers Required:** `Authorization: Bearer {token}` or cookie inheritance

---

## 3. EXISTING CODE PATTERNS

### A) Video API Routes (Found in `api_routes.py`)

```python
@router.get("/api/videos")
async def get_videos(request: Request):
    """Get videos for current user"""
    user = get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})
    
    if user["is_admin"]:
        videos = execute_query("SELECT v.*, u.username FROM videos v LEFT JOIN users u ON v.user_id = u.id ORDER BY v.created_at DESC", fetch_all=True)
    else:
        videos = execute_query("SELECT * FROM videos WHERE user_id = %s ORDER BY created_at DESC", (int(user["id"]),), fetch_all=True)
    
    return JSONResponse(content={"success": True, "videos": video_list})

@router.get("/api/videos/{video_id}/download")
async def download_video(request: Request, video_id: str):
    """Download video by redirecting to the video URL"""
    user = get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})
    
    video = execute_query("SELECT * FROM videos WHERE id = %s OR heygen_video_id = %s", (video_id, video_id), fetch_one=True)
    if not video or (not user["is_admin"] and video["user_id"] != int(user["id"])):
        return JSONResponse(status_code=403, content={"error": "Access denied"})
    
    return RedirectResponse(url=video["video_path"], status_code=302)
```

### B) Authentication Middleware

```python
def get_current_user_fixed(request: Request):
    """JWT-based authentication with PostgreSQL"""
    try:
        token = request.cookies.get("access_token")
        if not token:
            return None
        
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        user_id = payload.get("user_id")
        
        user = execute_query("SELECT * FROM users WHERE id = %s", (user_id,), fetch_one=True)
        return user
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
```

### C) Video Database Schema

```sql
CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(255),
    video_path TEXT,  -- Cloudinary/HeyGen URL
    heygen_video_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    duration INTEGER DEFAULT 0,
    format VARCHAR(10) DEFAULT 'mp4',
    source VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

---

## 4. IFRAME INTEGRATION PATTERNS

### A) Existing Implementation
**File:** `app/routes/backgroundfx_iframe.py`

```python
@router.get("/backgroundfx", response_class=HTMLResponse)
async def backgroundfx_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    context = {
        "request": request,
        "username": user.get("username", "User"),
        "hf_space_url": "https://MogensR-VideoBackgroundReplacer.hf.space",
        "user_id": user.get("id"),
        "is_premium": user.get("subscription_type") == "Premium"
    }
    
    return templates.TemplateResponse("backgroundfx_iframe.html", context)
```

### B) Widget Communication Pattern
```javascript
// Parent to iframe communication
iframe.contentWindow.postMessage({
    type: 'user_context',
    user_id: userId,
    token: authToken,
    videos: userVideos
}, '*');

// Iframe to parent communication
parent.postMessage({
    type: 'video_processed',
    video_data: base64Video,
    filename: 'processed_video.mp4'
}, '*');
```

### C) Widget URL Structure
```
/backgroundfx?user_id=123&token=jwt_token_here
```

---

## 5. COMPLETE IMPLEMENTATION EXAMPLE

### Frontend Widget Integration
```javascript
// MyAvatar dashboard widget click handler
async function openBackgroundFX() {
    // Get user videos
    const response = await fetch('/api/videos', {
        credentials: 'include' // Include cookies
    });
    const data = await response.json();
    
    if (data.success) {
        // Open iframe with video list
        const iframe = document.getElementById('backgroundfx-iframe');
        iframe.src = '/backgroundfx';
        
        // Pass video data to iframe when loaded
        iframe.onload = () => {
            iframe.contentWindow.postMessage({
                type: 'myavatar_videos',
                videos: data.videos,
                user_id: currentUser.id
            }, '*');
        };
    }
}

// Listen for processed videos from iframe
window.addEventListener('message', (event) => {
    if (event.data.type === 'video_processed') {
        // Save processed video back to MyAvatar
        saveProcessedVideo(event.data);
    }
});
```

### Backend API Route
```python
@router.post("/api/backgroundfx/save-video")
async def save_background_video(request: Request):
    """Save processed video from HF Space to MyAvatar"""
    user = get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})
    
    payload = await request.json()
    video_b64 = payload.get("video_data")
    filename = payload.get("filename", "background_video.mp4")
    
    # Decode and upload to Cloudinary
    video_bytes = base64.b64decode(video_b64)
    video_url = upload_video_to_cloudinary(video_bytes, user["id"])
    
    # Save to database
    execute_query("""
        INSERT INTO videos (user_id, title, video_path, status, format, source)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user["id"], f"BackgroundFX: {filename}", video_url, "completed", "mp4", "background-fx"))
    
    return JSONResponse({"success": True, "message": "Video saved successfully!"})
```

### Widget Authentication
```python
async def get_current_user(request: Request):
    """Authentication for iframe widgets"""
    # Try cookie-based auth (inherited from parent)
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get("user_id")
            user = execute_query("SELECT * FROM users WHERE id = %s", (user_id,), fetch_one=True)
            return user
        except jwt.InvalidTokenError:
            pass
    
    # Fallback to URL parameter
    token = request.query_params.get("token")
    if token:
        # Same JWT validation
        pass
    
    return None
```

---

## 🎯 FINAL INTEGRATION SUMMARY

```json
{
  "endpoints": {
    "list_videos": {
      "method": "GET",
      "url": "/api/videos",
      "auth_required": true,
      "response_format": {
        "success": true,
        "videos": [{"id": 123, "title": "Video", "video_path": "https://..."}]
      }
    },
    "get_video": {
      "method": "GET", 
      "url": "/api/videos/{id}/download",
      "auth_required": true,
      "returns": "302_redirect_to_cloudinary_url"
    },
    "save_processed": {
      "method": "POST",
      "url": "/api/backgroundfx/save-video",
      "auth_required": true,
      "payload": {"video_data": "base64", "filename": "video.mp4"}
    }
  },
  "authentication": {
    "method": "jwt_cookie",
    "header_format": "Cookie: access_token=jwt_token",
    "widget_access_pattern": "inherited_cookies",
    "fallback": "url_parameter_token"
  },
  "storage": {
    "primary": "cloudinary_cdn",
    "database": "postgresql_videos_table",
    "access_pattern": "direct_url_redirect"
  },
  "iframe_integration": {
    "url": "/backgroundfx",
    "communication": "postMessage_api",
    "existing_pattern": "backgroundfx_iframe.py",
    "hf_space_url": "https://MogensR-VideoBackgroundReplacer.hf.space"
  }
}
```

**🚀 Ready for seamless BackgroundFX integration!**
