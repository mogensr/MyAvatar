#!/usr/bin/env python3
"""
Comprehensive Video Routes Diagnostic Script
===========================================
Diagnoses all issues with text-to-video and voice-to-video routes
"""

import sys
import os
import traceback
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test all required imports"""
    print("🔍 Testing imports...")
    
    try:
        from app.db.database import execute_query
        print("   ✅ execute_query imported")
    except Exception as e:
        print(f"   ❌ execute_query import failed: {e}")
        
    try:
        from app.logger.log_handler import log_info, log_error, log_warning
        print("   ✅ log functions imported")
    except Exception as e:
        print(f"   ❌ log functions import failed: {e}")
        
    try:
        from fastapi.templating import Jinja2Templates
        print("   ✅ Jinja2Templates imported")
    except Exception as e:
        print(f"   ❌ Jinja2Templates import failed: {e}")

def test_templates():
    """Test template availability"""
    print("\n🔍 Testing templates...")
    
    templates_dir = Path("templates")
    
    # Check voice-to-video template
    voice_template = templates_dir / "voice_recording.html"
    if voice_template.exists():
        print(f"   ✅ voice_recording.html exists ({voice_template.stat().st_size} bytes)")
    else:
        print(f"   ❌ voice_recording.html missing")
        
    # Check text-to-video template  
    text_template = templates_dir / "text_video_component.html"
    if text_template.exists():
        print(f"   ✅ text_video_component.html exists ({text_template.stat().st_size} bytes)")
    else:
        print(f"   ❌ text_video_component.html missing")

def test_route_registration():
    """Test if routes are properly registered"""
    print("\n🔍 Testing route registration...")
    
    try:
        # Import main app
        from main import app
        
        # Get all routes
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        # Check for our routes
        if "/text-to-video" in routes:
            print("   ✅ /text-to-video route registered")
        else:
            print("   ❌ /text-to-video route NOT registered")
            
        if "/voice-to-video" in routes:
            print("   ✅ /voice-to-video route registered")
        else:
            print("   ❌ /voice-to-video route NOT registered")
            
        print(f"   📊 Total routes: {len(routes)}")
        
    except Exception as e:
        print(f"   ❌ Route registration test failed: {e}")

def test_authentication_functions():
    """Test authentication functions"""
    print("\n🔍 Testing authentication functions...")
    
    try:
        # Test main.py auth function
        from main import get_current_user_from_request
        print("   ✅ get_current_user_from_request available in main.py")
    except Exception as e:
        print(f"   ❌ get_current_user_from_request in main.py failed: {e}")
        
    try:
        # Test video_routes.py auth function
        from app.routes.video_routes import get_current_user_fixed
        print("   ✅ get_current_user_fixed available in video_routes.py")
    except Exception as e:
        print(f"   ❌ get_current_user_fixed in video_routes.py failed: {e}")

def test_database_connection():
    """Test database connectivity"""
    print("\n🔍 Testing database connection...")
    
    try:
        from app.db.database import execute_query
        
        # Test simple query
        result = execute_query("SELECT 1 as test", fetch_one=True)
        if result:
            print("   ✅ Database connection working")
        else:
            print("   ❌ Database query returned no result")
            
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")

def test_avatar_query():
    """Test avatar query that both routes use"""
    print("\n🔍 Testing avatar query...")
    
    try:
        from app.db.database import execute_query
        
        # Test the exact query used in both routes
        avatars_query = """
        SELECT id, avatar_name, avatar_image_url, avatar_id, heygen_avatar_id, is_default, created_at 
        FROM user_avatars 
        WHERE user_id = %s 
        ORDER BY created_at DESC
        """
        
        # Test with user ID 1 (if exists)
        result = execute_query(avatars_query, (1,), fetch_all=True)
        print(f"   ✅ Avatar query executed successfully (found {len(result or [])} avatars for user 1)")
        
    except Exception as e:
        print(f"   ❌ Avatar query failed: {e}")

def test_specific_route_functions():
    """Test the specific route functions"""
    print("\n🔍 Testing specific route functions...")
    
    # Test text-to-video function from main.py
    try:
        import main
        if hasattr(main, 'text_to_video_page'):
            print("   ✅ text_to_video_page function exists in main.py")
        else:
            print("   ❌ text_to_video_page function missing in main.py")
    except Exception as e:
        print(f"   ❌ main.py function test failed: {e}")
        
    # Test voice-to-video function from video_routes.py
    try:
        from app.routes.video_routes import voice_recording_page
        print("   ✅ voice_recording_page function exists in video_routes.py")
    except Exception as e:
        print(f"   ❌ voice_recording_page function test failed: {e}")

def main():
    """Run comprehensive diagnostics"""
    print("🚀 MyAvatar Video Routes Comprehensive Diagnostic")
    print("=" * 50)
    
    test_imports()
    test_templates()
    test_route_registration()
    test_authentication_functions()
    test_database_connection()
    test_avatar_query()
    test_specific_route_functions()
    
    print("\n" + "=" * 50)
    print("🏁 Diagnostic complete!")
    print("\nNext steps:")
    print("1. Fix any ❌ issues shown above")
    print("2. Check production logs for specific error messages")
    print("3. Test routes individually with curl/browser dev tools")

if __name__ == "__main__":
    main()
