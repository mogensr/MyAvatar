#!/usr/bin/env python3
"""
Find endpoints that actually work
"""
import requests

def test_working_endpoints():
    """Test endpoints that should work"""
    
    base_url = "https://myavatar-production.up.railway.app"
    
    # Test basic health endpoints (these are in main.py directly)
    endpoints_to_test = [
        "/health",
        "/simple-health",
        "/debug-env",
        "/debug-avatars"
    ]
    
    print(f"🔍 Testing main.py endpoints on: {base_url}")
    print("=" * 60)
    
    for endpoint in endpoints_to_test:
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=10)
            status = response.status_code
            
            if status == 200:
                print(f"✅ {endpoint:<20} - {status} OK")
                if endpoint == "/health":
                    try:
                        data = response.json()
                        print(f"   Health data: {data}")
                    except:
                        pass
            else:
                print(f"❌ {endpoint:<20} - {status}")
                
        except Exception as e:
            print(f"💥 {endpoint:<20} - ERROR: {str(e)[:40]}...")
    
    print("=" * 60)

if __name__ == "__main__":
    test_working_endpoints()
