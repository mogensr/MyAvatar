#!/usr/bin/env python3
"""
Test the avatar image update API endpoint
"""
import requests
import json

def test_avatar_update():
    try:
        # Test the API endpoint
        url = "https://myavatar-production.up.railway.app/api/avatars/update-images"
        
        # You'll need to be logged in - this is just a test to see if the endpoint exists
        response = requests.post(url)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 401:
            print("✅ Endpoint exists (authentication required)")
        elif response.status_code == 200:
            print("✅ Endpoint worked!")
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_avatar_update()
