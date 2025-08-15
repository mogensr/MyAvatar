#!/usr/bin/env python3
"""
Test avatar URL accessibility
"""
import requests
import sys

def test_avatar_url(url):
    """Test if avatar URL is accessible"""
    print(f"Testing URL: {url}")
    
    try:
        # Test with different headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        print(f"Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
        
        if response.status_code == 200:
            print("✅ URL is accessible")
            return True
        else:
            print(f"❌ URL returned status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def main():
    # Test the URL you showed
    test_url = "https://files2.heygen.ai/avatar/v3/8a6bac0a93d84c4c94b4d6275d41ff"
    
    print("=== Testing Avatar URL Accessibility ===")
    test_avatar_url(test_url)
    
    # Also test a complete URL format
    complete_url = test_url + "/" + test_url.split('/')[-1] + ".jpg"
    print(f"\n=== Testing Complete URL Format ===")
    test_avatar_url(complete_url)

if __name__ == "__main__":
    main()
