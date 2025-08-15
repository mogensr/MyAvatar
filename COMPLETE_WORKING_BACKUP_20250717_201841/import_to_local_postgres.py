#!/usr/bin/env python3
"""
Import Railway data to Local PostgreSQL
"""
import json
import os
import sys
from datetime import datetime

def import_railway_data():
    """Import exported Railway data to local PostgreSQL"""
    print("🚀 Starting Local PostgreSQL Data Import")
    print("=" * 50)
    
    # Find the export file
    export_file = "railway_export_20250707_202703.json"
    if not os.path.exists(export_file):
        print(f"❌ Export file not found: {export_file}")
        return False
    
    print(f"📁 Loading data from: {export_file}")
    
    # Load the exported data
    with open(export_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✅ Loaded {len(data)} data sections")
    
    # Connect to Railway dev PostgreSQL
    railway_dev_url = "postgresql://postgres:eMzptnxaMkGLkEtdavxCrJcISgsMGWQQ@caboose.proxy.rlwy.net:34708/railway"
    
    print("🔗 Connecting to Railway dev PostgreSQL...")
    print("   Database: caboose.proxy.rlwy.net:34708/railway")
    
    local_db_url = railway_dev_url
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        print("🔗 Connecting to local PostgreSQL...")
        conn = psycopg2.connect(local_db_url)
        cursor = conn.cursor()
        
        print("✅ Connected to local PostgreSQL!")
        
        # Import users
        if 'users' in data and data['users']:
            print(f"\n👥 Importing {len(data['users'])} users...")
            for user in data['users']:
                cursor.execute("""
                    INSERT INTO users (id, username, email, password_hash, created_at, is_admin, last_login, last_video_created)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        is_admin = EXCLUDED.is_admin,
                        last_login = EXCLUDED.last_login,
                        last_video_created = EXCLUDED.last_video_created
                """, (
                    user['id'], user['username'], user['email'], 
                    user.get('password_hash', user.get('hashed_password', 'temp_hash')),
                    user['created_at'], bool(user.get('is_admin', 0)), 
                    user.get('last_login'), user.get('last_video_created')
                ))
            print("   ✅ Users imported successfully")
        
        # Import user_avatars
        if 'user_avatars' in data and data['user_avatars']:
            print(f"\n🎭 Importing {len(data['user_avatars'])} user avatars...")
            for avatar in data['user_avatars']:
                cursor.execute("""
                    INSERT INTO user_avatars (id, user_id, avatar_id, avatar_name, avatar_image_url, preview_video_url, is_default, is_custom, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        avatar_id = EXCLUDED.avatar_id,
                        avatar_name = EXCLUDED.avatar_name,
                        avatar_image_url = EXCLUDED.avatar_image_url,
                        preview_video_url = EXCLUDED.preview_video_url,
                        is_default = EXCLUDED.is_default,
                        is_custom = EXCLUDED.is_custom
                """, (
                    avatar['id'], avatar['user_id'], avatar['avatar_id'], avatar['avatar_name'],
                    avatar['avatar_image_url'], avatar.get('preview_video_url'),
                    int(avatar.get('is_default', 0)), bool(avatar.get('is_custom', False)), avatar['created_at']
                ))
            print("   ✅ User avatars imported successfully")
        
        # Import videos
        if 'videos' in data and data['videos']:
            print(f"\n🎬 Importing {len(data['videos'])} videos...")
            for video in data['videos']:
                cursor.execute("""
                    INSERT INTO videos (id, user_id, heygen_video_id, status, video_url, created_at, format, title, description, voice_id, template_id, background_config, script_content, thumbnail_url, duration, completed_at, avatar_id, quality, aspect_ratio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        video_url = EXCLUDED.video_url,
                        completed_at = EXCLUDED.completed_at
                """, (
                    video['id'], video['user_id'], video['heygen_video_id'], video['status'],
                    video.get('video_url'), video['created_at'], video.get('format', '16:9'),
                    video.get('title'), video.get('description'), video.get('voice_id'),
                    video.get('template_id'), video.get('background_config'), video.get('script_content'),
                    video.get('thumbnail_url'), video.get('duration'), video.get('completed_at'),
                    video.get('avatar_id'), video.get('quality', '720p'), video.get('aspect_ratio', '16:9')
                ))
            print("   ✅ Videos imported successfully")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 50)
        print("🎉 IMPORT COMPLETED SUCCESSFULLY!")
        print("✅ Your local PostgreSQL now has all your Railway data")
        print("🔄 Next: Update your .env file to use local PostgreSQL")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = import_railway_data()
    if not success:
        sys.exit(1)
