# LeadGenEngine Integration Plan
## Distribution Engine Widget → Separate Railway Deployment

### **Current Status**
- ✅ LeadGenEngine codebase complete in `C:\Brugere\mogen\CascadeProjects\LeadGenEngine`
- ✅ Dashboard widget changed from "Distribution Engine" to "3D Avatars" 
- ❌ Distribution Engine functionality not connected

### **Architecture Plan (Following BackgroundFX Pattern)**

```
MyAvatar Dashboard (Railway #1)
    ↓ (iframe integration)
LeadGenEngine Service (Railway #2)
    ↓ (API calls)
External APIs (LinkedIn, HubSpot, etc.)
```

### **Step 1: Deploy LeadGenEngine to Railway**

**Files Ready for Deployment:**
- `Backend/main.py` - FastAPI server (27KB)
- `Core/lead_engine.py` - Lead generation logic (21KB)  
- `Core/cold_email_engine.py` - Email automation (28KB)
- `Core/social_media_engine.py` - Social media integration (21KB)
- `requirements.txt` - All dependencies defined
- `Procfile` - Railway deployment config
- `Dockerfile` - Container setup

**Railway Setup:**
1. Create new Railway project: "LeadGenEngine"
2. Connect to new GitHub repo: `mogensr/LeadGenEngine`
3. Add PostgreSQL addon
4. Set environment variables from `.env.example`

### **Step 2: Create Iframe Integration Route**

**Pattern from BackgroundFX:**
```python
# app/routes/leadgen_iframe.py
@router.get("/distribution", response_class=HTMLResponse)
async def distribution_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse("distribution_iframe.html", {
        "request": request,
        "user": user,
        "leadgen_url": "https://leadgenengine-production.up.railway.app"
    })
```

### **Step 3: Update Dashboard Widget**

**Change widget from "3D Avatars" back to "Distribution Engine":**
```html
<div class="feature-card premium" onclick="window.location.href='/distribution'">
    <div class="feature-icon">
        <i class="fas fa-share-alt"></i>
    </div>
    <h3 class="feature-title">
        Distribution Engine
        <span class="premium-badge">Premium</span>
    </h3>
    <p class="feature-description">Advanced lead generation, cold email automation, and social media distribution.</p>
</div>
```

### **Step 4: Create Iframe Template**

**Template: `templates/distribution_iframe.html`**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Distribution Engine - MyAvatar</title>
    <style>
        iframe { width: 100%; height: 100vh; border: none; }
        body { margin: 0; padding: 0; }
    </style>
</head>
<body>
    <iframe src="{{ leadgen_url }}" 
            allow="camera; microphone; clipboard-write"
            sandbox="allow-same-origin allow-scripts allow-forms">
    </iframe>
</body>
</html>
```

### **Step 5: Authentication Bridge**

**Pass MyAvatar user context to LeadGenEngine:**
```python
# Add JWT token to iframe URL for seamless auth
leadgen_url_with_auth = f"{leadgen_url}?token={user_jwt_token}"
```

### **Deployment Timeline**
1. **Phase 1** (30 min): Deploy LeadGenEngine to Railway
2. **Phase 2** (20 min): Create iframe integration route  
3. **Phase 3** (10 min): Update dashboard widget
4. **Phase 4** (15 min): Test end-to-end functionality

### **Benefits of This Approach**
- ✅ **Separation of concerns** - LeadGenEngine runs independently
- ✅ **Scalability** - Can scale LeadGenEngine separately
- ✅ **Maintenance** - Easier to update/debug each service
- ✅ **User experience** - Seamless integration via iframe
- ✅ **Proven pattern** - Same approach as BackgroundFX

### **Next Steps When You Return**
1. Create GitHub repo for LeadGenEngine
2. Deploy to Railway with PostgreSQL
3. Implement iframe integration in MyAvatar
4. Test Distribution Engine widget functionality

**Ready to execute when you're back!** 🚀
