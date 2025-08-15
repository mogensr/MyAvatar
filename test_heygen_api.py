#!/usr/bin/env python3
"""
Test HeyGen API connection and video status directly
"""
import sys
import os
from pathlib import Path
import requests

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_heygen_api():
    """Test HeyGen API connection with your actual video ID"""
    try:
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            print("❌ No HEYGEN_API_KEY found in environment")
            return False
            
        print(f"🔑 API Key found: {api_key[:10]}...{api_key[-4:]}")
        
        # Test video ID from your logs
        test_video_id = "1b05592ce8cb4c4d9e8d1a27977acf53"
        
        print(f"🧪 Testing HeyGen API with video ID: {test_video_id}")
        
        # Test the exact same request as your polling service
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        
        url = f"https://api.heygen.com/v2/video/{test_video_id}"
        print(f"🌐 Making request to: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        print(f"📄 Response Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ API call successful!")
            data = response.json()
            print(f"📊 Video Status: {data.get('data', {}).get('status', 'unknown')}")
            return True
        elif response.status_code == 404:
            print("❌ 404 - Video not found")
            print("🔍 This could mean:")
            print("  - Video ID is incorrect")
            print("  - Video was deleted from HeyGen")
            print("  - API key doesn't have access to this video")
            return False
        elif response.status_code == 401:
            print("❌ 401 - Authentication failed")
            print("🔍 API key might be invalid or expired")
            return False
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing API: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_heygen_general_api():
    """Test general HeyGen API access"""
    try:
        api_key = os.getenv("HEYGEN_API_KEY")
        
        # Test with a general API endpoint
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        
        # Try to list available voices (should work if API key is valid)
        url = "https://api.heygen.com/v2/voices"
        print(f"\n🧪 Testing general API access: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"📊 General API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ API key is valid and working!")
            return True
        else:
            print(f"❌ General API test failed: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing general API: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 Testing HeyGen API Connection...")
    
    # Test general API first
    general_ok = test_heygen_general_api()
    
    # Test specific video
    video_ok = test_heygen_api()
    
    if general_ok and not video_ok:
        print("\n🎯 CONCLUSION: API key works, but specific video not found")
        print("💡 SOLUTION: Create a new video to test with")
    elif not general_ok:
        print("\n🎯 CONCLUSION: API key issue")
        print("💡 SOLUTION: Check your HEYGEN_API_KEY")
    elif video_ok:
        print("\n🎯 CONCLUSION: Everything works!")
        print("💡 SOLUTION: Check polling service configuration")
