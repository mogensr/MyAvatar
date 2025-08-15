#!/usr/bin/env python3
"""
Test the debug routes endpoint to see what's actually loaded
"""
import requests

def test_debug_routes():
    """Test the debug routes endpoint"""
    
    url = "https://myavatar-production.up.railway.app/debug-routes"
    
    print(f"🔍 Testing Debug Routes: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Total Routes: {data.get('total_routes', 0)}")
            print(f"✅ Routers Loaded: {data.get('routes_loaded_successfully', [])}")
            print(f"❌ Router Errors: {len(data.get('router_import_errors', []))}")
            
            # Look for our API endpoint
            api_routes = [r for r in data.get('all_routes', []) if '/api/' in r.get('path', '')]
            print(f"\n🔍 API Routes Found ({len(api_routes)}):")
            for route in api_routes:
                print(f"  - {route.get('path')} [{', '.join(route.get('methods', []))}]")
            
            # Check for errors
            errors = data.get('router_import_errors', [])
            if errors:
                print(f"\n❌ Router Import Errors:")
                for error in errors:
                    print(f"  - {error.get('module')}: {error.get('error')}")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_debug_routes()
