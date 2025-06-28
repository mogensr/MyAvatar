import os
import sys
sys.path.append('.')
from app.api.heygen import get_available_avatars

api_key = os.getenv('HEYGEN_API_KEY')
if not api_key:
    print("No HEYGEN_API_KEY found in environment")
    exit(1)

print("🔍 Fetching avatars from HeyGen API...")
result = get_available_avatars(api_key)

if result.get('success'):
    avatars = result.get('avatars', [])
    print(f"✅ Found {len(avatars)} avatars")
    
    # Show first few avatars with ALL fields
    for i, avatar in enumerate(avatars[:3]):
        print(f"\n--- Avatar {i+1} ---")
        for key, value in avatar.items():
            print(f"  {key}: {value}")
else:
    print(f"❌ Error: {result.get('error')}")
