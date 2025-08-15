#!/usr/bin/env python3
import os
import json
from dotenv import load_dotenv
load_dotenv()

print("🔍 HeyGen API Debug Tool")
print("=" * 30)

try:
    from app.api.heygen import get_available_avatars, get_avatar_details
    print("✅ Successfully imported HeyGen API modules")
except ImportError as e:
    print(f"❌ Failed to import HeyGen API modules: {e}")
    exit(1)

api_key = os.getenv("HEYGEN_API_KEY")
print(f"🔑 API key found: {'Yes' if api_key else 'No'}")

if not api_key:
    print("❌ HEYGEN_API_KEY not found in environment variables")
    exit(1)

print("🌐 Calling HeyGen API...")
try:
    result = get_available_avatars(api_key)
    print(f"📊 API call completed. Success: {result.get('success')}")
except Exception as e:
    print(f"❌ API call failed: {e}")
    exit(1)

if result.get("success"):
    avatars = result.get("avatars", [])
    print(f"Found {len(avatars)} avatars")
    
    # Show first avatar structure
    if avatars:
        print("\nFirst avatar structure:")
        print(json.dumps(avatars[0], indent=2))
        
        # Get detailed info
        avatar_id = avatars[0].get("avatar_id")
        if avatar_id:
            details = get_avatar_details(api_key, avatar_id)
            if details.get("success"):
                print("\nDetailed info structure:")
                print(json.dumps(details.get("details"), indent=2))
