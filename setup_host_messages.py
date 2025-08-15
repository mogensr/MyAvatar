#!/usr/bin/env python3
"""
Simple Host Message System Database Migration
Run this script to set up the host messages tables

Usage: python simple_setup_host_messages.py
"""

import os
import psycopg2
from datetime import datetime

def main():
    print("🎭 MyAvatar Host Message System Setup")
    print("=" * 50)
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        database_url = input("Database URL: ").strip()
    
    if not database_url:
        print("❌ Database URL is required!")
        return
    
    try:
        print("📡 Connecting to database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        print("✅ Database connection successful")
        
        print("📋 Creating host_messages table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS host_messages (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                video_url TEXT,
                video_id VARCHAR(100),
                message_text TEXT,
                thumbnail_url TEXT,
                duration VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT true,
                priority INTEGER DEFAULT 1,
                expires_at TIMESTAMP
            );
        """)
        print("✅ host_messages table ready")
        
        print("📋 Creating user_host_message_reads table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_host_message_reads (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                host_message_id INTEGER REFERENCES host_messages(id) ON DELETE CASCADE,
                read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, host_message_id)
            );
        """)
        print("✅ user_host_message_reads table ready")
        
        print("📋 Adding indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_host_messages_active ON host_messages(is_active);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_host_messages_priority ON host_messages(priority DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_reads_user_id ON user_host_message_reads(user_id);")
        print("✅ Indexes added")
        
        print("📋 Checking for existing messages...")
        cursor.execute("SELECT COUNT(*) FROM host_messages;")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("📋 Adding sample host message...")
            cursor.execute("""
                INSERT INTO host_messages (
                    title, message_text, duration, is_active, priority, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s);
            """, (
                "Welcome to MyAvatar!",
                "Hey everyone! Welcome to MyAvatar - your AI video creation platform. I'm excited to have you here and can't wait to see what amazing videos you'll create. This is a sample message to test the host message system. You can delete this and create your own messages from the admin panel!",
                "1:30",
                True,
                1,
                datetime.now()
            ))
            print("✅ Sample message added")
        else:
            print(f"⏭️ Found {count} existing messages, skipping sample insert")
        
        # Commit all changes
        conn.commit()
        print("💾 All changes saved to database")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM host_messages;")
        message_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name IN ('host_messages', 'user_host_message_reads');
        """)
        table_count = cursor.fetchone()[0]
        
        print("\n🔍 Verification:")
        print(f"✅ Tables created: {table_count}/2")
        print(f"✅ Host messages: {message_count}")
        
        print("\n" + "=" * 50)
        print("🎉 HOST MESSAGE SYSTEM SETUP COMPLETE!")
        print("=" * 50)
        print("\n📋 NEXT STEPS:")
        print("1. ✅ Database tables created")
        print("2. 🎯 Add to main.py:")
        print("   from app.routes.host_routes import host_router")
        print("   app.include_router(host_router)")
        print("3. 🎭 Go to /admin/host-messages")
        print("4. 🎬 Create your first video message!")
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()
            print("🔌 Database connection closed")

if __name__ == "__main__":
    main()
