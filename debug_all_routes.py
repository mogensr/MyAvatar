#!/usr/bin/env python3
"""
Debug script to check all registered routes in the FastAPI app
"""
import sys
import os
sys.path.append(os.getcwd())

def debug_all_routes():
    """Debug all routes registered in the FastAPI application"""
    print("🔍 Debugging all registered routes...")
    
    try:
        # Import the main FastAPI app
        from main import app
        
        print(f"✅ App imported successfully")
        print(f"Total routes in app: {len(app.routes)}")
        
        # List all routes
        print("\n📋 All registered routes:")
        text_to_video_found = False
        voice_to_video_found = False
        
        for i, route in enumerate(app.routes):
            try:
                if hasattr(route, 'path') and hasattr(route, 'methods'):
                    methods = list(route.methods) if hasattr(route, 'methods') else ['Unknown']
                    print(f"  {i+1:3d}. {route.path} - {methods}")
                    
                    # Check for our target routes
                    if route.path == "/text-to-video":
                        text_to_video_found = True
                        print(f"       ✅ FOUND /text-to-video!")
                    elif route.path == "/voice-to-video":
                        voice_to_video_found = True
                        print(f"       ✅ FOUND /voice-to-video!")
                        
                elif hasattr(route, 'path'):
                    print(f"  {i+1:3d}. {route.path} - [Static/Mount]")
                else:
                    print(f"  {i+1:3d}. [Unknown route type: {type(route)}]")
            except Exception as e:
                print(f"  {i+1:3d}. [Error reading route: {e}]")
        
        print(f"\n🎯 Target Route Status:")
        print(f"   /text-to-video found: {'✅ YES' if text_to_video_found else '❌ NO'}")
        print(f"   /voice-to-video found: {'✅ YES' if voice_to_video_found else '❌ NO'}")
        
        # Check router loading status
        try:
            from main import loaded_routers, router_errors
            print(f"\n📊 Router Loading Status:")
            print(f"   Successfully loaded: {len(loaded_routers)}")
            print(f"   Errors: {len(router_errors)}")
            
            if router_errors:
                print(f"\n❌ Router Errors:")
                for error in router_errors:
                    print(f"   - {error}")
                    
            if loaded_routers:
                print(f"\n✅ Successfully Loaded Routers:")
                for router in loaded_routers:
                    print(f"   - {router}")
                    
        except ImportError:
            print("⚠️ Could not import router status from main")
            
        return text_to_video_found and voice_to_video_found
        
    except Exception as e:
        print(f"❌ Error debugging routes: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_all_routes()
    sys.exit(0 if success else 1)
