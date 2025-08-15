#!/usr/bin/env python3
"""
Test connection to Railway dev database
"""
import os
from dotenv import load_dotenv

def test_connection():
    """Test database connection and show data"""
    print("🔍 Testing Railway Dev Database Connection")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    print(f"🔗 Database URL: {database_url[:50]}...")
    
    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        print("✅ Connected successfully!")
        
        # Test users table
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"👥 Users: {user_count}")
        
        # Test user_avatars table
        cursor.execute("SELECT COUNT(*) FROM user_avatars")
        avatar_count = cursor.fetchone()[0]
        print(f"🎭 User Avatars: {avatar_count}")
        
        # Test videos table
        cursor.execute("SELECT COUNT(*) FROM videos")
        video_count = cursor.fetchone()[0]
        print(f"🎬 Videos: {video_count}")
        
        # Test avatar URLs
        cursor.execute("""
            SELECT avatar_name, avatar_image_url 
            FROM user_avatars 
            WHERE avatar_image_url IS NOT NULL 
            LIMIT 3
        """)
        avatars = cursor.fetchall()
        
        print(f"\n🖼️ Sample Avatar URLs:")
        for name, url in avatars:
            print(f"   {name}: {url[:60]}...")
        
        conn.close()
        
        print("\n" + "=" * 50)
        print("🎉 DATABASE CONNECTION TEST PASSED!")
        print("✅ Your app is ready to use Railway dev database")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
