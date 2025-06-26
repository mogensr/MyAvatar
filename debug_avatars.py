#!/usr/bin/env python3
"""
Debug script to check avatar data in the database
"""
import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor

def debug_avatars():
    """Debug avatar data for all users"""
    
    # Database connection
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    try:
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all avatars
        cursor.execute("SELECT * FROM avatars ORDER BY created_at DESC LIMIT 10")
        avatars = cursor.fetchall()
        
        print("🎭 AVATAR DEBUG - Recent Avatars:")
        print("=" * 60)
        
        if not avatars:
            print("❌ No avatars found in database")
            return
            
        for i, avatar in enumerate(avatars, 1):
            print(f"\n📋 Avatar #{i}:")
            print(f"   ID: {avatar.get('id')}")
            print(f"   Name: {avatar.get('name', 'N/A')}")
            print(f"   User ID: {avatar.get('user_id')}")
            print(f"   HeyGen Avatar ID: {avatar.get('heygen_avatar_id', 'N/A')}")
            print(f"   Image URL: {avatar.get('image_url', 'N/A')}")
            
            # Check if heygen_data exists and what it contains
            heygen_data = avatar.get('heygen_data')
            if heygen_data:
                if isinstance(heygen_data, str):
                    try:
                        heygen_data = json.loads(heygen_data)
                    except:
                        print(f"   HeyGen Data: {heygen_data[:100]}...")
                        continue
                        
                if isinstance(heygen_data, dict):
                    print(f"   HeyGen Data Keys: {list(heygen_data.keys())}")
                    if 'preview_image_url' in heygen_data:
                        print(f"   HeyGen Preview Image: {heygen_data['preview_image_url']}")
                    if 'image_url' in heygen_data:
                        print(f"   HeyGen Image URL: {heygen_data['image_url']}")
                else:
                    print(f"   HeyGen Data: {type(heygen_data)} - {heygen_data}")
            else:
                print(f"   HeyGen Data: None")
                
            print(f"   Created: {avatar.get('created_at', 'N/A')}")
            
        cursor.close()
        conn.close()
            
    except Exception as e:
        print(f"❌ Error debugging avatars: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_avatars()
