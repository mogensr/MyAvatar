#!/usr/bin/env python3
"""
Test script to check web_routes.py import issues
"""
import sys
import traceback

def test_web_routes_import():
    """Test importing web_routes and identify any issues"""
    print("🔍 Testing web_routes.py import...")
    
    try:
        # Test basic import
        from app.routes.web_routes import router
        print("✅ Router imported successfully")
        print(f"Router type: {type(router)}")
        
        # Check if router has routes
        if hasattr(router, 'routes'):
            print(f"Router routes count: {len(router.routes)}")
            
            # List some routes
            for i, route in enumerate(router.routes[:5]):  # Show first 5 routes
                if hasattr(route, 'path'):
                    print(f"  Route {i+1}: {route.path}")
        else:
            print("❌ Router has no routes attribute")
            
        return True
        
    except ImportError as e:
        print(f"❌ ImportError: {e}")
        print("\n📋 Full traceback:")
        traceback.print_exc()
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("\n📋 Full traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_web_routes_import()
    sys.exit(0 if success else 1)
