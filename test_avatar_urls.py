#!/usr/bin/env python3
"""
Test avatar image URLs in production to see if they're working
"""
import requests

def test_avatar_urls():
    # Test the specific URL from the PostgreSQL screenshot
    test_url = "https://files2.heygen.ai/avatar/v3/f1d5b3cfd8a64605ac960dd8862a9b"
    
    print("🧪 Testing Avatar Image URLs")
    print("=" * 35)
    
    print(f"Testing URL: {test_url}")
    
    try:
        response = requests.head(test_url, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ URL is working!")
            print("Headers:")
            for key, value in response.headers.items():
                if key.lower() in ['content-type', 'content-length', 'cache-control']:
                    print(f"  {key}: {value}")
        else:
            print(f"❌ URL returned status {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("❌ URL timed out")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test with full GET request
    print(f"\n🔄 Testing with full GET request...")
    try:
        response = requests.get(test_url, timeout=10)
        print(f"GET Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ GET request successful")
            print(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
            print(f"Content-Length: {response.headers.get('content-length', 'Unknown')}")
        else:
            print(f"❌ GET request failed with {response.status_code}")
    except Exception as e:
        print(f"❌ GET request error: {e}")

if __name__ == "__main__":
    test_avatar_urls()
