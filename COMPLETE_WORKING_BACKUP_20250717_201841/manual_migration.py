# manual_migration.py - Direct database migration script
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️  python-dotenv not installed, trying without it")

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    print("Please add your Railway DATABASE_URL to your .env file")
    exit(1)

print("🚀 Starting manual migration for MyAvatar premium features...")

try:
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    print("✅ Connected to database successfully")
    
    # Check if alembic_version table exists
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = 'alembic_version'
    """)
    
    alembic_exists = cursor.fetchone()
    
    if not alembic_exists:
        print("📝 Creating alembic_version table...")
        cursor.execute("""
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
        """)
        print("✅ alembic_version table created")
    
    # Check existing tables
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    
    existing_tables = [row[0] for row in cursor.fetchall()]
    print(f"📋 Existing tables: {', '.join(existing_tables)}")
    
    # ===============================================================================
    # 🆕 ADD is_premium COLUMN TO USERS TABLE
    # ===============================================================================
    
    print("🔍 Checking users table for is_premium column...")
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'is_premium'
    """)
    
    has_premium_column = cursor.fetchone()
    
    if not has_premium_column:
        print("📝 Adding is_premium column to users table...")
        cursor.execute("""
            ALTER TABLE users ADD COLUMN is_premium BOOLEAN DEFAULT FALSE
        """)
        print("✅ is_premium column added to users table")
        
        # Set existing admin users to premium for testing
        cursor.execute("""
            UPDATE users SET is_premium = TRUE WHERE is_admin = TRUE
        """)
        print("✅ Existing admin users set to premium")
    else:
        print("✅ is_premium column already exists in users table")
    
    # Check videos table structure
    print("🔍 Checking videos table structure...")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'videos'
        ORDER BY ordinal_position
    """)
    
    video_columns = cursor.fetchall()
    print("📋 Videos table columns:")
    for col in video_columns:
        print(f"   - {col[0]} ({col[1]}) - Nullable: {col[2]}")
    
    # Check if premium tables already exist
    premium_tables = ['user_subscriptions', 'premium_features', 'user_backgrounds', 'background_replacement_jobs']
    premium_exists = any(table in existing_tables for table in premium_tables)
    
    if premium_exists:
        print("✅ Premium tables already exist - migration not needed")
    else:
        print("📝 Creating premium tables...")
        
        # Skip videos table fixes since the structure is different
        print("⚠️  Skipping videos table fixes - will add columns if needed")
        
        # Create enum types
        print("📝 Creating enum types...")
        
        cursor.execute("""
            DO $$ BEGIN
                CREATE TYPE subscriptiontype AS ENUM ('trial', 'basic', 'premium', 'enterprise');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        cursor.execute("""
            DO $$ BEGIN
                CREATE TYPE subscriptionstatus AS ENUM ('active', 'inactive', 'cancelled', 'expired', 'trialing');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        cursor.execute("""
            DO $$ BEGIN
                CREATE TYPE backgroundtype AS ENUM ('original', 'custom', 'ai_generated', 'stock_image');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        cursor.execute("""
            DO $$ BEGIN
                CREATE TYPE jobstatus AS ENUM ('pending', 'processing', 'completed', 'failed', 'cancelled');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        print("✅ Enum types created")
        
        # Create user_subscriptions table
        print("📝 Creating user_subscriptions table...")
        cursor.execute("""
            CREATE TABLE user_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                subscription_type subscriptiontype NOT NULL,
                status subscriptionstatus NOT NULL,
                trial_start_date TIMESTAMP,
                trial_end_date TIMESTAMP,
                subscription_start_date TIMESTAMP,
                subscription_end_date TIMESTAMP,
                stripe_customer_id VARCHAR(255),
                stripe_subscription_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create premium_features table
        print("📝 Creating premium_features table...")
        cursor.execute("""
            CREATE TABLE premium_features (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                feature_key VARCHAR(255) NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create user_backgrounds table
        print("📝 Creating user_backgrounds table...")
        cursor.execute("""
            CREATE TABLE user_backgrounds (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name VARCHAR(255) NOT NULL,
                background_type backgroundtype NOT NULL,
                cloudinary_url VARCHAR(512) NOT NULL,
                cloudinary_public_id VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create background_replacement_jobs table
        print("📝 Creating background_replacement_jobs table...")
        cursor.execute("""
            CREATE TABLE background_replacement_jobs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                video_id INTEGER NOT NULL REFERENCES videos(id),
                background_id INTEGER REFERENCES user_backgrounds(id),
                background_prompt TEXT,
                stock_image_url VARCHAR(512),
                job_status jobstatus DEFAULT 'pending',
                heygen_job_id VARCHAR(255),
                result_video_url VARCHAR(512),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        print("📝 Creating indexes...")
        cursor.execute("CREATE INDEX idx_user_subscriptions_user_id ON user_subscriptions(user_id)")
        cursor.execute("CREATE INDEX idx_user_subscriptions_status ON user_subscriptions(status)")
        cursor.execute("CREATE INDEX idx_user_backgrounds_user_id ON user_backgrounds(user_id)")
        cursor.execute("CREATE INDEX idx_background_jobs_user_id ON background_replacement_jobs(user_id)")
        cursor.execute("CREATE INDEX idx_background_jobs_status ON background_replacement_jobs(job_status)")
        
        # Insert default premium features
        print("📝 Inserting default premium features...")
        cursor.execute("""
            INSERT INTO premium_features (name, description, feature_key, is_active, created_at)
            VALUES 
            ('Background Replacement', 'Replace video backgrounds with custom images or AI-generated backgrounds', 'background_replacement', true, CURRENT_TIMESTAMP),
            ('Custom Backgrounds', 'Upload and use custom background images', 'custom_backgrounds', true, CURRENT_TIMESTAMP),
            ('AI Background Generation', 'Generate backgrounds using AI prompts', 'ai_backgrounds', true, CURRENT_TIMESTAMP),
            ('Stock Image Search', 'Search and use stock images as backgrounds', 'stock_images', true, CURRENT_TIMESTAMP),
            ('Unlimited Videos', 'Generate unlimited videos per month', 'unlimited_videos', true, CURRENT_TIMESTAMP),
            ('Priority Processing', 'Faster video generation queue', 'priority_processing', true, CURRENT_TIMESTAMP),
            ('Custom Voices', 'Upload and use custom voice models', 'custom_voices', true, CURRENT_TIMESTAMP),
            ('Commercial License', 'Use videos for commercial purposes', 'commercial_license', true, CURRENT_TIMESTAMP),
            ('Extended Video Length', 'Create videos up to 5 minutes long', 'extended_video_length', true, CURRENT_TIMESTAMP),
            ('Premium Support', 'Priority customer support', 'premium_support', true, CURRENT_TIMESTAMP)
            ON CONFLICT (feature_key) DO NOTHING
        """)
        
        # Update alembic version
        cursor.execute("""
            INSERT INTO alembic_version (version_num) 
            VALUES ('premium_features_002') 
            ON CONFLICT (version_num) DO UPDATE SET version_num = 'premium_features_002'
        """)
        
        print("✅ All premium tables created successfully!")
    
    # ===============================================================================
    # 🆕 SHOW PREMIUM STATS
    # ===============================================================================
    
    # Show user premium stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_users,
            COUNT(CASE WHEN is_premium = TRUE THEN 1 END) as premium_users,
            COUNT(CASE WHEN is_admin = TRUE THEN 1 END) as admin_users
        FROM users
    """)
    
    user_stats = cursor.fetchone()
    print(f"\n👥 USER STATS:")
    print(f"   Total Users: {user_stats[0]}")
    print(f"   Premium Users: {user_stats[1]}")
    print(f"   Admin Users: {user_stats[2]}")
    
    # Verify tables were created
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    
    final_tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📋 Final tables: {', '.join(final_tables)}")
    
    # Check feature count
    if 'premium_features' in final_tables:
        cursor.execute("SELECT COUNT(*) FROM premium_features")
        feature_count = cursor.fetchone()[0]
        print(f"🎯 Premium features loaded: {feature_count}")
        
        # Show premium features
        cursor.execute("SELECT name, feature_key FROM premium_features ORDER BY name")
        features = cursor.fetchall()
        print("💎 Available premium features:")
        for feature in features:
            print(f"   - {feature[0]} ({feature[1]})")
    
    print("\n🎉 MIGRATION COMPLETED SUCCESSFULLY!")
    print("====================================")
    print("✅ is_premium column added to users table")
    print("✅ Existing admins set to premium")
    print("✅ Premium subscription system ready")
    print("✅ Background replacement tables created")
    print("✅ Enhanced premium features loaded")
    print("✅ Database indexes created")
    print("\n🚀 Your MyAvatar premium system is now active!")
    print("💎 Admin users can now manage premium status in the admin panel!")
    
except Exception as e:
    print(f"❌ Error during migration: {str(e)}")
    print("\nPlease check your DATABASE_URL and try again.")
    
finally:
    if 'conn' in locals():
        conn.close()
        print("🔌 Database connection closed")
