#!/usr/bin/env python3
import requests
import json

def test_api_endpoint():
    """Test the /api/completed-videos endpoint directly"""
    
    # You'll need to get a session cookie from your browser
    # For now, let's test without authentication to see the response
    
    api_url = "https://myavatar-production.up.railway.app/api/completed-videos"
    
    print(f"🔍 Testing API endpoint: {api_url}")
    
    try:
        response = requests.get(api_url, timeout=10)
        print(f"  Status Code: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        
        if response.status_code == 200:
            data = response.json()
            print("  ✅ API Response:")
            print(json.dumps(data, indent=2))
        else:
            print(f"  ❌ API returned status {response.status_code}")
            print(f"  Response: {response.text[:200]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error calling API: {e}")

if __name__ == "__main__":
    test_api_endpoint()
