#!/usr/bin/env python3
"""
Create tables in Railway dev database
"""
import psycopg2

def setup_tables():
    """Create all necessary tables in Railway dev database"""
    print("🚀 Setting up Railway Dev Database Tables")
    print("=" * 50)
    
    # Connect to Railway dev PostgreSQL
    railway_dev_url = "postgresql://postgres:eMzptnxaMkGLkEtdavxCrJcISgsMGWQQ@caboose.proxy.rlwy.net:34708/railway"
    
    try:
        conn = psycopg2.connect(railway_dev_url)
        cursor = conn.cursor()
        
        print("✅ Connected to Railway dev PostgreSQL!")
        
        # Create users table
        print("\n👥 Creating users table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE,
                last_login TIMESTAMP,
                last_video_created TIMESTAMP
            )
        """)
        
        # Create user_avatars table
        print("🎭 Creating user_avatars table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_avatars (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                avatar_id VARCHAR(100) NOT NULL,
                avatar_name VARCHAR(100) NOT NULL,
                avatar_image_url TEXT,
                preview_video_url TEXT,
                is_default INTEGER DEFAULT 0,
                is_custom BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create videos table
        print("🎬 Creating videos table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                heygen_video_id VARCHAR(100),
                status VARCHAR(20) DEFAULT 'pending',
                video_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                format VARCHAR(10) DEFAULT '16:9',
                title VARCHAR(200),
                description TEXT,
                voice_id VARCHAR(100),
                template_id VARCHAR(100),
                background_config TEXT,
                script_content TEXT,
                thumbnail_url TEXT,
                duration INTEGER,
                completed_at TIMESTAMP,
                avatar_id VARCHAR(100),
                quality VARCHAR(10) DEFAULT '720p',
                aspect_ratio VARCHAR(10) DEFAULT '16:9'
            )
        """)
        
        # Create other tables
        print("📋 Creating additional tables...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS avatars (
                id SERIAL PRIMARY KEY,
                avatar_id VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                image_url TEXT,
                preview_video_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backgrounds (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                image_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                endpoint VARCHAR(200),
                method VARCHAR(10),
                status_code INTEGER,
                response_time INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                config TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        print("🔍 Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_avatars_user_id ON user_avatars(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_logs_user_id ON api_logs(user_id)")
        
        conn.commit()
        conn.close()
        
        print("\n" + "=" * 50)
        print("🎉 DATABASE SETUP COMPLETED!")
        print("✅ All tables created successfully")
        print("🚀 Ready to import data!")
        
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    setup_tables()
