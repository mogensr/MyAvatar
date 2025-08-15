#!/usr/bin/env python3
"""
Database Migration Script for HeyGen Voice Management System
Creates necessary tables and indexes for the voice management system
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import execute_query
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoiceMigration")

def create_voice_assignment_log_table():
    """Create voice_assignment_log table for debugging and analytics"""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS voice_assignment_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        avatar_id TEXT NOT NULL,
        assigned_voice_id TEXT NOT NULL,
        voice_type TEXT NOT NULL,
        source TEXT NOT NULL,
        confidence TEXT NOT NULL,
        is_fallback BOOLEAN DEFAULT FALSE,
        avatar_type TEXT,
        warning TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Indexes for performance
        INDEX idx_voice_log_user_id (user_id),
        INDEX idx_voice_log_avatar_id (avatar_id),
        INDEX idx_voice_log_created_at (created_at DESC)
    )
    """
    
    try:
        execute_query(create_table_sql)
        logger.info("✅ voice_assignment_log table created/verified")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating voice_assignment_log table: {e}")
        return False

def create_public_avatar_voices_table():
    """Create public_avatar_voices table for default voice mappings"""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS public_avatar_voices (
        avatar_id TEXT PRIMARY KEY,
        default_voice_id TEXT NOT NULL,
        voice_name TEXT,
        supported_languages TEXT DEFAULT 'en',
        gender TEXT,
        accent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    try:
        execute_query(create_table_sql)
        logger.info("✅ public_avatar_voices table created/verified")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating public_avatar_voices table: {e}")
        return False

def populate_default_public_avatars():
    """Populate some default public avatar voice mappings"""
    
    default_avatars = [
        {
            'avatar_id': 'Josh_public_ele',
            'default_voice_id': 'en-US-GuyNeural',
            'voice_name': 'Guy',
            'supported_languages': 'en,es,fr',
            'gender': 'male'
        },
        {
            'avatar_id': 'Anna_public_ele',
            'default_voice_id': 'en-US-JennyNeural',
            'voice_name': 'Jenny',
            'supported_languages': 'en,es,fr',
            'gender': 'female'
        },
        {
            'avatar_id': 'default_male',
            'default_voice_id': 'en-US-GuyNeural',
            'voice_name': 'Guy',
            'supported_languages': 'en',
            'gender': 'male'
        },
        {
            'avatar_id': 'default_female',
            'default_voice_id': 'en-US-JennyNeural',
            'voice_name': 'Jenny',
            'supported_languages': 'en',
            'gender': 'female'
        }
    ]
    
    try:
        for avatar in default_avatars:
            # Check if avatar already exists
            existing = execute_query(
                "SELECT avatar_id FROM public_avatar_voices WHERE avatar_id = ?",
                (avatar['avatar_id'],)
            )
            
            if not existing:
                execute_query("""
                    INSERT INTO public_avatar_voices 
                    (avatar_id, default_voice_id, voice_name, supported_languages, gender)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    avatar['avatar_id'],
                    avatar['default_voice_id'],
                    avatar['voice_name'],
                    avatar['supported_languages'],
                    avatar['gender']
                ))
                logger.info(f"✅ Added default avatar: {avatar['avatar_id']}")
            else:
                logger.info(f"⏭️ Avatar {avatar['avatar_id']} already exists")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error populating default avatars: {e}")
        return False

def verify_existing_tables():
    """Verify that required existing tables have the necessary columns"""
    
    # Check users.heygen_voice_id column
    try:
        result = execute_query("SELECT heygen_voice_id FROM users LIMIT 1")
        logger.info("✅ users.heygen_voice_id column exists")
    except Exception as e:
        logger.warning(f"⚠️ users.heygen_voice_id column may be missing: {e}")
        logger.info("💡 You may need to run: ALTER TABLE users ADD COLUMN heygen_voice_id TEXT")
    
    # Check user_avatars.is_custom column
    try:
        result = execute_query("SELECT is_custom FROM user_avatars LIMIT 1")
        logger.info("✅ user_avatars.is_custom column exists")
    except Exception as e:
        logger.warning(f"⚠️ user_avatars.is_custom column may be missing: {e}")
        logger.info("💡 You may need to run: ALTER TABLE user_avatars ADD COLUMN is_custom BOOLEAN DEFAULT FALSE")
    
    return True

def main():
    """Main migration function"""
    print("🔧 HeyGen Voice Management Database Migration")
    print("=" * 50)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    success_count = 0
    total_steps = 4
    
    # Step 1: Verify existing tables
    print("\n📋 Step 1: Verifying existing table structure...")
    if verify_existing_tables():
        success_count += 1
    
    # Step 2: Create voice_assignment_log table
    print("\n📊 Step 2: Creating voice_assignment_log table...")
    if create_voice_assignment_log_table():
        success_count += 1
    
    # Step 3: Create public_avatar_voices table
    print("\n🎭 Step 3: Creating public_avatar_voices table...")
    if create_public_avatar_voices_table():
        success_count += 1
    
    # Step 4: Populate default public avatars
    print("\n🎯 Step 4: Populating default public avatars...")
    if populate_default_public_avatars():
        success_count += 1
    
    # Summary
    print(f"\n🎉 Migration Complete!")
    print(f"✅ {success_count}/{total_steps} steps completed successfully")
    
    if success_count == total_steps:
        print("🚀 Your HeyGen Voice Management System is ready to use!")
        print("\nNext steps:")
        print("1. Run: python diagnose_voice_assignment.py")
        print("2. Test voice assignment with your avatars")
        print("3. Check the voice_assignment_log table for debugging info")
    else:
        print("⚠️ Some steps failed. Please check the logs and fix any issues.")
    
    return success_count == total_steps

if __name__ == "__main__":
    main()
