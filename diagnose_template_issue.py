#!/usr/bin/env python3
"""
Comprehensive diagnostic script to identify why templates aren't loading
"""
import sys
import os
import traceback
from pathlib import Path

def diagnose_template_issue():
    """Diagnose the template loading issue step by step"""
    print("🔍 COMPREHENSIVE TEMPLATE DIAGNOSTIC")
    print("=" * 50)
    
    # Step 1: Check if templates directory exists
    print("\n1. 📁 TEMPLATE DIRECTORY CHECK:")
    templates_dir = Path("templates")
    if templates_dir.exists():
        print(f"   ✅ Templates directory exists: {templates_dir.absolute()}")
        
        # List all template files
        template_files = list(templates_dir.glob("*.html"))
        print(f"   📄 Found {len(template_files)} HTML templates:")
        for template in template_files:
            print(f"      - {template.name}")
    else:
        print(f"   ❌ Templates directory NOT found: {templates_dir.absolute()}")
    
    # Step 2: Check specific template files
    print("\n2. 🎯 SPECIFIC TEMPLATE FILES:")
    target_templates = [
        "text_video_component.html",
        "voice_recording.html", 
        "dashboard.html",
        "index.html"
    ]
    
    for template in target_templates:
        template_path = templates_dir / template
        if template_path.exists():
            print(f"   ✅ {template} - EXISTS")
        else:
            print(f"   ❌ {template} - MISSING")
    
    # Step 3: Check if main app can import
    print("\n3. 🚀 MAIN APP IMPORT TEST:")
    try:
        from main import app, templates
        print("   ✅ Main app imported successfully")
        
        if templates:
            print("   ✅ Templates object initialized")
            print(f"   📂 Templates directory: {templates.directory}")
        else:
            print("   ❌ Templates object is None")
            
    except Exception as e:
        print(f"   ❌ Main app import failed: {e}")
        traceback.print_exc()
    
    # Step 4: Check route registration
    print("\n4. 🛣️ ROUTE REGISTRATION CHECK:")
    try:
        from main import app
        
        # Look for text-to-video and voice-to-video routes
        text_video_found = False
        voice_video_found = False
        
        print(f"   📊 Total registered routes: {len(app.routes)}")
        
        for route in app.routes:
            if hasattr(route, 'path'):
                if route.path == "/text-to-video":
                    text_video_found = True
                    print(f"   ✅ /text-to-video route FOUND")
                elif route.path == "/voice-to-video":
                    voice_video_found = True
                    print(f"   ✅ /voice-to-video route FOUND")
        
        if not text_video_found:
            print(f"   ❌ /text-to-video route NOT FOUND")
        if not voice_video_found:
            print(f"   ❌ /voice-to-video route NOT FOUND")
            
    except Exception as e:
        print(f"   ❌ Route check failed: {e}")
    
    # Step 5: Check router loading errors
    print("\n5. 🔧 ROUTER LOADING ERRORS:")
    try:
        from main import router_errors, loaded_routers
        
        print(f"   📊 Successfully loaded routers: {len(loaded_routers)}")
        for router in loaded_routers:
            print(f"      ✅ {router}")
            
        print(f"   ❌ Router errors: {len(router_errors)}")
        for error in router_errors:
            print(f"      ❌ {error}")
            
    except Exception as e:
        print(f"   ❌ Router status check failed: {e}")
    
    # Step 6: Test direct template rendering
    print("\n6. 🎨 DIRECT TEMPLATE RENDERING TEST:")
    try:
        from main import templates
        from fastapi import Request
        
        if templates:
            # Create a mock request
            class MockRequest:
                def __init__(self):
                    self.url = "http://localhost:8000/test"
            
            mock_request = MockRequest()
            
            # Try to render a simple template
            try:
                response = templates.TemplateResponse("dashboard.html", {
                    "request": mock_request,
                    "user": {"username": "test"},
                    "videos": []
                })
                print("   ✅ Template rendering test PASSED")
            except Exception as template_error:
                print(f"   ❌ Template rendering FAILED: {template_error}")
        else:
            print("   ❌ Templates object not available for testing")
            
    except Exception as e:
        print(f"   ❌ Template rendering test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 DIAGNOSTIC COMPLETE")
    
    return True

if __name__ == "__main__":
    diagnose_template_issue()
