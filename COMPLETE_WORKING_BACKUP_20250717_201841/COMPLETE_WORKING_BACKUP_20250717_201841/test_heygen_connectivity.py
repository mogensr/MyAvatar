#!/usr/bin/env python3
"""
Test if we can reach HeyGen URLs from current environment
"""
import requests
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def test_heygen_connectivity():
    """Test connectivity to HeyGen CDN"""
    print("🔍 TESTING HEYGEN CDN CONNECTIVITY")
    print("=" * 40)
    
    # Test URLs from your database
    test_urls = [
        "https://files2.heygen.ai/avatar/v3/25ef6c86b1e946969d9a684870c47c.jpg",
        "https://files2.heygen.ai/avatar/v3/25ef6c86b1e946969d9a684870c47c",  # without .jpg
    ]
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n[{i}] Testing: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            print(f"    Status: {response.status_code}")
            print(f"    Content-Type: {response.headers.get('content-type', 'Unknown')}")
            print(f"    Content-Length: {response.headers.get('content-length', 'Unknown')}")
            
            if response.status_code == 200:
                print("    ✅ SUCCESS - URL is accessible")
            else:
                print(f"    ❌ FAILED - HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("    ❌ TIMEOUT - Cannot reach HeyGen CDN")
        except requests.exceptions.ConnectionError:
            print("    ❌ CONNECTION ERROR - Network issue")
        except Exception as e:
            print(f"    ❌ ERROR: {e}")
    
    # Test HeyGen API connectivity
    print(f"\n🔍 TESTING HEYGEN API CONNECTIVITY")
    api_key = os.getenv('HEYGEN_API_KEY')
    if api_key:
        try:
            headers = {'X-Api-Key': api_key}
            response = requests.get('https://api.heygen.com/v1/avatar.list', 
                                  headers=headers, timeout=10)
            print(f"API Status: {response.status_code}")
            if response.status_code == 200:
                print("✅ HeyGen API is accessible")
            else:
                print("❌ HeyGen API connection issue")
        except Exception as e:
            print(f"❌ HeyGen API error: {e}")
    else:
        print("❌ No HEYGEN_API_KEY found")

if __name__ == "__main__":
    test_heygen_connectivity()
