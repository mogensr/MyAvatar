#!/usr/bin/env python3
"""
Premium Database Setup Script
Run this to create premium tables in your database
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_premium_database():
    """Create premium system database tables"""
    
    print("🎯 Premium Database Setup Starting...")
    print("-" * 50)
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables")
        print("   Make sure you have a .env file with DATABASE_URL")
        return False
    
    print(f"📊 Database URL found: {database_url[:50]}...")
    
    try:
        # Connect to database
        print("🔗 Connecting to database...")
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("✅ Database connection successful!")
        print()
        
        # Create premium_subscriptions table
        print("📋 Creating premium_subscriptions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS premium_subscriptions (
                id SERIAL PRIMARY KEY,
                subscription_id VARCHAR(255) UNIQUE NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                plan_type VARCHAR(50) NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                features TEXT,
                payment_method VARCHAR(50),
                payment_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ premium_subscriptions table created/verified")
        
        # Create premium_features table
        print("📋 Creating premium_features table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS premium_features (
                id SERIAL PRIMARY KEY,
                feature_key VARCHAR(100) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                premium_required BOOLEAN DEFAULT true,
                enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ premium_features table created/verified")
        
        # Add premium_required column if it doesn't exist
        print("📋 Adding premium_required column if missing...")
        try:
            cur.execute("""
                ALTER TABLE premium_features 
                ADD COLUMN IF NOT EXISTS premium_required BOOLEAN DEFAULT true
            """)
            print("✅ premium_required column added/verified")
        except Exception as e:
            print(f"⚠️  Note: {e}")
        
        # Add trial_used column to users table
        print("📋 Adding trial_used column to users table...")
        try:
            cur.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS trial_used BOOLEAN DEFAULT false
            """)
            print("✅ trial_used column added to users table")
        except Exception as e:
            print(f"⚠️  Note: {e}")
        
        # Insert default premium features
        print("📋 Inserting default premium features...")
        
        features = [
            ('backgroundfx', 'BackgroundFX Studio', 'AI-powered background replacement with HeyGen WebM integration'),
            ('video_processing', 'Advanced Video Processing', 'Professional background replacement with multiple AI models'),
            ('unlimited_videos', 'Unlimited Video Generation', 'Generate unlimited videos without monthly limits'),
            ('priority_processing', 'Priority Processing', 'Faster video processing with priority queue'),
            ('advanced_avatars', 'Advanced Avatar Library', 'Access to premium avatar collection'),
            ('api_access', 'API Access', 'Full API access for integrations')
        ]
        
        for feature_key, name, description in features:
            cur.execute("""
                INSERT INTO premium_features (feature_key, name, description, premium_required)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (feature_key) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    premium_required = EXCLUDED.premium_required
            """, (feature_key, name, description, True))
            print(f"✅ Added feature: {name}")
        
        # Commit all changes
        conn.commit()
        print()
        print("💾 All changes committed to database")
        
        # Verify tables exist
        print("🔍 Verifying table creation...")
        
        # Check premium_subscriptions table
        cur.execute("SELECT COUNT(*) FROM premium_subscriptions")
        sub_count = cur.fetchone()[0]
        print(f"📊 premium_subscriptions table: {sub_count} records")
        
        # Check premium_features table
        cur.execute("SELECT COUNT(*) FROM premium_features")
        feature_count = cur.fetchone()[0]
        print(f"📊 premium_features table: {feature_count} records")
        
        # Check users table for trial_used column
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'trial_used'
        """)
        trial_column = cur.fetchone()
        if trial_column:
            print("📊 users table: trial_used column exists")
        else:
            print("⚠️  users table: trial_used column missing")
        
        # Show all premium features
        print()
        print("🎯 Premium Features Configured:")
        print("-" * 40)
        cur.execute("SELECT feature_key, name, premium_required FROM premium_features ORDER BY feature_key")
        features = cur.fetchall()
        
        for feature in features:
            status = "PREMIUM" if feature['premium_required'] else "FREE"
            print(f"  • {feature['feature_key']}: {feature['name']} ({status})")
        
        # Close connection
        cur.close()
        conn.close()
        
        print()
        print("🎉 Premium Database Setup Complete!")
        print("=" * 50)
        print("✅ All premium tables created successfully")
        print("✅ Default premium features configured")
        print("✅ Database is ready for premium system")
        print()
        print("📌 Next Steps:")
        print("1. Test your application locally")
        print("2. Go to /admin/premium to manage users")
        print("3. Set yourself as premium user")
        print("4. Test BackgroundFX functionality")
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def check_database_connection():
    """Test database connection"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return False
    
    try:
        conn = psycopg2.connect(database_url)
        conn.close()
        print("✅ Database connection test successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def show_current_users():
    """Show current users in the system"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found")
        return
    
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get users
        cur.execute("SELECT id, username, email, created_at FROM users ORDER BY id")
        users = cur.fetchall()
        
        print("👥 Current Users in System:")
        print("-" * 40)
        
        if users:
            for user in users:
                print(f"  ID: {user['id']} | Username: {user['username']} | Email: {user['email'] or 'N/A'}")
        else:
            print("  No users found in database")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error retrieving users: {e}")

if __name__ == "__main__":
    print("🎯 MyAvatar Premium Database Setup")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "test":
            print("🔍 Testing database connection...")
            check_database_connection()
        elif command == "users":
            print("👥 Showing current users...")
            show_current_users()
        elif command == "setup":
            setup_premium_database()
        else:
            print("❌ Unknown command. Use: setup, test, or users")
    else:
        # Default action - full setup
        print("🚀 Running full premium database setup...")
        print()
        
        # Test connection first
        if check_database_connection():
            print()
            setup_premium_database()
            print()
            show_current_users()
        else:
            print("❌ Cannot proceed - database connection failed")
            print("   Check your DATABASE_URL in .env file")
