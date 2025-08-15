#!/usr/bin/env python3
"""
Test the API endpoint directly to see what it returns
"""
import requests

def test_api_direct():
    """Test the API endpoint without authentication first"""
    
    url = "https://myavatar-production.up.railway.app/api/completed-videos"
    
    print(f"🔍 Testing API: {url}")
    
    try:
        # Test without auth first
        response = requests.get(url, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📊 Headers: {dict(response.headers)}")
        
        if response.status_code == 401:
            print("✅ API requires authentication (expected)")
        elif response.status_code == 200:
            print("✅ API responded successfully")
            try:
                data = response.json()
                print(f"📊 Response Data: {data}")
            except:
                print(f"📊 Response Text: {response.text[:200]}...")
        elif response.status_code == 500:
            print("❌ Server error")
            try:
                data = response.json()
                print(f"❌ Error: {data}")
            except:
                print(f"❌ Error text: {response.text[:200]}...")
        else:
            print(f"❓ Unexpected status: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_api_direct()
