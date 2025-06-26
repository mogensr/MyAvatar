#!/usr/bin/env python3
"""
Update avatar images with better HeyGen images
"""
import os
from dotenv import load_dotenv
from app.db.database import execute_query
from app.api.heygen import get_available_avatars
import json

def update_avatar_images():
    try:
        # Load environment variables from .env file
        load_dotenv()
        
        # Get API key
        api_key = os.getenv("HEYGEN_API_KEY")
        if not api_key:
            print("❌ HEYGEN_API_KEY not found in environment")
            return
            
        # Get current avatars for user 3
        current_avatars = execute_query(
            "SELECT id, user_id, avatar_id, avatar_name, avatar_image_url FROM user_avatars WHERE user_id = 3", 
            fetch_all=True
        )
        
        print("🔍 Current avatars:")
        for avatar in current_avatars:
            # Convert sqlite3.Row to dict-like access
            avatar_data = dict(avatar)
            print(f"  ID: {avatar_data['avatar_id']}")
            print(f"  Name: {avatar_data['avatar_name']}")
            print(f"  Current Image: {avatar_data['avatar_image_url']}")
            print()
        
        # Get fresh avatar data from HeyGen
        print("🔄 Fetching fresh avatar data from HeyGen...")
        heygen_response = get_available_avatars(api_key)
        
        if heygen_response and heygen_response.get('success'):
            avatars = heygen_response.get('avatars', [])
            print(f"✅ Found {len(avatars)} avatars from HeyGen")
            
            # Create a mapping of avatar_id to image_url
            heygen_image_map = {}
            for hg_avatar in avatars:
                avatar_id = hg_avatar.get('avatar_id')
                preview_image = hg_avatar.get('preview_image_url')
                if avatar_id and preview_image:
                    heygen_image_map[avatar_id] = preview_image
                    print(f"  HeyGen Avatar: {avatar_id} -> {preview_image}")
            
            # Update our database with better images
            print("\n🔄 Updating avatar images...")
            for avatar in current_avatars:
                avatar_data = dict(avatar)
                avatar_id = avatar_data['avatar_id']
                
                if avatar_id in heygen_image_map:
                    new_image_url = heygen_image_map[avatar_id]
                    print(f"  Updating {avatar_id} with new image: {new_image_url}")
                    
                    execute_query(
                        "UPDATE user_avatars SET avatar_image_url = ? WHERE user_id = 3 AND avatar_id = ?",
                        (new_image_url, avatar_id)
                    )
                else:
                    print(f"  ⚠️ No HeyGen image found for {avatar_id}")
            
            print("✅ Avatar images updated successfully!")
            
        else:
            error = heygen_response.get('error', 'Unknown error') if heygen_response else 'No response'
            print(f"❌ Could not fetch avatars from HeyGen: {error}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    update_avatar_images()
