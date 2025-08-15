#!/usr/bin/env python3
"""
Debug what the /api/completed-videos endpoint is actually returning
"""

import requests
import json

def test_api_response():
    """Test the API and show exact response"""
    try:
        url = "https://app.myavatar.dk/api/completed-videos"
        
        print(f"🔍 Testing: {url}")
        
        # Test without authentication first
        response = requests.get(url, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📊 Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"📊 Response Type: {type(data)}")
                print(f"📊 Response Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                
                if isinstance(data, dict) and 'videos' in data:
                    videos = data['videos']
                    print(f"📊 Videos Count: {len(videos)}")
                    
                    if videos:
                        print(f"📊 First Video Keys: {list(videos[0].keys())}")
                        print(f"📊 First Video Sample:")
                        for key, value in videos[0].items():
                            if isinstance(value, str) and len(value) > 100:
                                print(f"   {key}: {value[:100]}...")
                            else:
                                print(f"   {key}: {value}")
                
                print(f"\n📊 Full Response (first 1000 chars):")
                response_text = json.dumps(data, indent=2)
                print(response_text[:1000])
                if len(response_text) > 1000:
                    print("... (truncated)")
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON Decode Error: {e}")
                print(f"📊 Raw Response: {response.text[:500]}")
        else:
            print(f"❌ Error Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Request Error: {e}")

if __name__ == "__main__":
    test_api_response()
