#!/usr/bin/env python3
"""
Test what's actually running on the server
"""
import requests

def test_any_response():
    """Test what the server actually returns"""
    
    base_url = "https://myavatar-production.up.railway.app"
    
    print(f"🔍 Testing what's actually running on: {base_url}")
    print("=" * 60)
    
    # Test root
    try:
        response = requests.get(base_url, timeout=10)
        print(f"Root URL Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Content (first 200 chars): {response.text[:200]}")
        
        # Check if it's a default Railway page or actual app
        if "railway" in response.text.lower() or "404" in response.text:
            print("🚨 This looks like a Railway default page or error!")
        else:
            print("✅ This looks like your actual app")
            
    except Exception as e:
        print(f"💥 Root URL failed: {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    test_any_response()
