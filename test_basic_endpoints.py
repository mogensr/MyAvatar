#!/usr/bin/env python3
"""
Test basic endpoints to see what's actually working
"""
import requests

def test_endpoints():
    """Test various endpoints to see what's working"""
    
    base_url = "https://myavatar-production.up.railway.app"
    
    endpoints_to_test = [
        "/health",
        "/simple-health", 
        "/test",
        "/debug-routes",
        "/api/completed-videos",
        "/dashboard",
        "/"
    ]
    
    print(f"🔍 Testing endpoints on: {base_url}")
    print("=" * 60)
    
    for endpoint in endpoints_to_test:
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=10, allow_redirects=False)
            status = response.status_code
            
            if status == 200:
                print(f"✅ {endpoint:<20} - {status} OK")
            elif status == 401:
                print(f"🔐 {endpoint:<20} - {status} Auth Required")
            elif status == 302:
                print(f"↗️  {endpoint:<20} - {status} Redirect")
            elif status == 404:
                print(f"❌ {endpoint:<20} - {status} Not Found")
            else:
                print(f"❓ {endpoint:<20} - {status} {response.reason}")
                
        except Exception as e:
            print(f"💥 {endpoint:<20} - ERROR: {str(e)[:40]}...")
    
    print("=" * 60)

if __name__ == "__main__":
    test_endpoints()
