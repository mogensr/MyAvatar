#!/usr/bin/env python3
"""
Test the specific avatar URL from production database
"""
import requests
from datetime import datetime

def test_specific_url():
    # The URL from production database
    test_url = "https://files2.heygen.ai/talking_photo/d4bd85b709cd44e1b5d386d75eaeedaf/43fe5ae3125549a887a733de7bda360a.WEBP?Expires=1751809636&Signature=IhlXbaZYdi79mMxsbnVVRP53Ni9sPWQCR9oarWZb~wk8QvNn2UCZEnBYD01~sraVRynLLcjlUkuS0nuKgQ5HWKyy1jVGewwQEdc-mNgZgeIvJuV0v66HQmpUb~fnZUK-b2UUBg2zR~4YmOrY8gar3-Jr9sZ0L8vGJo0aw-aHuBiTYulAA5shXxLGt-rDX4rtylSoJmOMqjB1zZ7MXmKNF9nRvq2UkIvN-uX9IO4L4MofWq9T18WdOSvPHbkIM9AtzbOIB2GYxGjscQ5PMVJWCgiyzNBCekIu4FjU-pJ-PGFMUWm69y1owy4g5xGDjADlznpd-xB2ehPV8qstiJHBgg__&Key-Pair-Id=K38HBHX5LX3X2H"
    
    print("🧪 Testing Specific Avatar URL from Production")
    print("=" * 50)
    
    # Parse expiration timestamp
    expires_timestamp = 1751809636
    expires_date = datetime.fromtimestamp(expires_timestamp)
    current_date = datetime.now()
    
    print(f"📅 URL Expiration: {expires_date}")
    print(f"📅 Current Time: {current_date}")
    print(f"⏰ Time until expiry: {expires_date - current_date}")
    
    if current_date > expires_date:
        print("❌ URL has EXPIRED!")
    else:
        print("✅ URL should still be valid")
    
    print(f"\n🔗 Testing URL...")
    print(f"URL: {test_url[:80]}...")
    
    try:
        # Test with HEAD request first
        response = requests.head(test_url, timeout=10)
        print(f"📡 HEAD Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ HEAD request successful!")
            print(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
            print(f"Content-Length: {response.headers.get('content-length', 'Unknown')}")
            
            # Try GET request to confirm
            print(f"\n🔄 Testing GET request...")
            get_response = requests.get(test_url, timeout=10)
            print(f"📡 GET Status Code: {get_response.status_code}")
            
            if get_response.status_code == 200:
                print("✅ GET request successful - Image is accessible!")
            else:
                print(f"❌ GET request failed: {get_response.status_code}")
                
        elif response.status_code == 403:
            print("❌ 403 Forbidden - URL likely expired or signature invalid")
        elif response.status_code == 404:
            print("❌ 404 Not Found - Image doesn't exist")
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_specific_url()
