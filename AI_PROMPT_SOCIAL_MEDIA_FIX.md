# AI Prompt: Fix MyAvatar Social Media Button

## Problem Summary
The Social Media button in MyAvatar Dashboard is not working. When clicked, it should redirect to `/social-media` endpoint but currently does nothing.

## Technical Context

### Project Structure
- **FastAPI backend** with Jinja2 templates
- **Railway deployment** connected to GitHub repo `mogensr/MyAvatar`
- **PostgreSQL database** with user authentication via JWT cookies
- **Main files:**
  - `main.py` - FastAPI app with route loading
  - `templates/dashboard.html` - Dashboard with Social Media button
  - `app/routes/social_media_routes.py` - Social Media endpoint routes
  - `templates/social_media_gradio.html` - Social Media iframe template

### Current State
1. **Social Media routes exist** at `/social-media` endpoint
2. **Button exists** in dashboard but onclick handler may be incorrect
3. **Git/Railway deployment issues** - local uses `master`, GitHub uses `main`

## Required Fix

### Step 1: Fix Dashboard Button
In `templates/dashboard.html`, find the Social Media button and ensure it uses:
```html
<div class="feature-card premium" onclick="startDistribution('social')">
```

### Step 2: Add JavaScript Function
In `templates/dashboard.html`, add this function:
```javascript
function startDistribution(type) {
    if (type === 'social') {
        window.location.href = '/social-media';
    } else if (type === 'email') {
        showComingSoonModal();
    } else {
        window.location.href = '/distribution';
    }
}
```

### Step 3: Verify Routes
Ensure `app/routes/social_media_routes.py` contains:
```python
@router.get("/social-media", response_class=HTMLResponse)
async def social_media_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    context = {
        "request": request,
        "user": user,
        "username": user.get("username", "User"),
        "gradio_url": GRADIO_URL,
        "user_id": user.get("id"),
        "is_premium": user.get("subscription_type") == "Premium"
    }
    return templates.TemplateResponse("social_media_gradio.html", context)
```

### Step 4: Fix Git/Railway Deployment
```bash
git pull origin main
git push origin main
```

## Expected Outcome
Social Media button should redirect to `/social-media` endpoint showing LeadGenEngine Gradio UI iframe.

## Files to Check/Modify
1. `templates/dashboard.html` - Button onclick and JavaScript function
2. `app/routes/social_media_routes.py` - Route definition
3. `main.py` - Router loading (should include social_media_routes)
4. `templates/social_media_gradio.html` - Template exists

## Testing
After deployment, click Social Media button in dashboard - should open LeadGenEngine interface.
