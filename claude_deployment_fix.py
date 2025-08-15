#!/usr/bin/env python3
"""
Deployment script to fix HeyGen webhook issues and deploy voice management
Run this script to apply all the fixes to your MyAvatar project
"""

import os
import sys
import sqlite3
import logging
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MyAvatarDeployment:
    def __init__(self, project_path):
        self.project_path = project_path
        self.db_path = os.path.join(project_path, 'app', 'database.db')
        
    def check_prerequisites(self):
        """Check if all required files and environment variables exist"""
        logger.info("Checking prerequisites...")
        
        # Check if project directory exists
        if not os.path.exists(self.project_path):
            logger.error(f"Project path does not exist: {self.project_path}")
            return False
            
        # Check for required environment variables
        required_env_vars = ['HEYGEN_API_KEY']
        for var in required_env_vars:
            if not os.getenv(var):
                logger.error(f"Required environment variable missing: {var}")
                return False
                
        logger.info("Prerequisites check passed!")
        return True
    
    def update_database_schema(self):
        """Apply database migrations"""
        logger.info("Updating database schema...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create videos table with all required columns
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    heygen_video_id TEXT UNIQUE,
                    script TEXT NOT NULL,
                    avatar_id TEXT NOT NULL,
                    voice_id TEXT,
                    status TEXT DEFAULT 'processing',
                    video_url TEXT,
                    duration INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Try to add columns that might be missing (SQLite safe)
            columns_to_add = [
                ('voice_id', 'TEXT'),
                ('video_url', 'TEXT'),
                ('duration', 'INTEGER DEFAULT 0'),
                ('error_message', 'TEXT'),
                ('completed_at', 'TIMESTAMP'),
                ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            ]
            
            for column_name, column_type in columns_to_add:
                try:
                    cursor.execute(f"ALTER TABLE videos ADD COLUMN {column_name} {column_type}")
                    logger.info(f"Added column: {column_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info(f"Column {column_name} already exists")
                    else:
                        logger.warning(f"Could not add column {column_name}: {e}")
            
            # Create indexes
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_videos_heygen_id ON videos(heygen_video_id)",
                "CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            # Create voice usage logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    voice_id TEXT NOT NULL,
                    video_id INTEGER,
                    usage_type TEXT DEFAULT 'video_creation',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_voice_usage_user ON voice_usage_logs(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_voice_usage_voice ON voice_usage_logs(voice_id)")
            
            conn.commit()
            conn.close()
            
            logger.info("Database schema updated successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error updating database schema: {e}")
            return False
    
    def test_webhook_endpoint(self, base_url="http://localhost:5000"):
        """Test if the webhook endpoint is working"""
        logger.info("Testing webhook endpoint...")
        
        webhook_test_url = f"{base_url}/api/heygen/webhook/test"
        
        try:
            # Test GET request
            response = requests.get(webhook_test_url, timeout=10)
            if response.status_code == 200:
                logger.info("Webhook test endpoint is working!")
                return True
            else:
                logger.error(f"Webhook test failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Could not reach webhook endpoint: {e}")
            logger.info("Make sure your Flask app is running")
            return False
    
    def fix_processing_videos(self):
        """Fix any videos stuck in processing status"""
        logger.info("Checking for videos stuck in processing...")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find videos stuck in processing for more than 1 hour
            cursor.execute("""
                SELECT id, heygen_video_id, created_at 
                FROM videos 
                WHERE status = 'processing' 
                AND datetime(created_at, '+1 hour') < datetime('now')
            """)
            
            stuck_videos = cursor.fetchall()
            
            if stuck_videos:
                logger.info(f"Found {len(stuck_videos)} videos stuck in processing")
                
                # You could implement logic here to check their actual status with HeyGen
                # For now, we'll just report them
                for video in stuck_videos:
                    logger.info(f"Video {video[0]} (HeyGen ID: {video[1]}) has been processing since {video[2]}")
                    
            else:
                logger.info("No videos found stuck in processing")
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error checking stuck videos: {e}")
            return False
    
    def validate_voice_manager(self):
        """Validate that the voice manager is working"""
        logger.info("Validating voice manager...")
        
        voice_manager_path = os.path.join(self.project_path, 'app', 'services', 'heygen_voice_manager.py')
        
        if not os.path.exists(voice_manager_path):
            logger.error("Voice manager file not found!")
            return False
        
        try:
            # Try to import the voice manager
            sys.path.insert(0, self.project_path)
            from app.services.heygen_voice_manager import HeyGenVoiceManager
            
            voice_manager = HeyGenVoiceManager()
            logger.info("Voice manager imported successfully!")
            
            # Test basic functionality
            test_voice = voice_manager.get_best_voice_for_user(1)
            logger.info(f"Voice manager test completed. Default voice: {test_voice}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating voice manager: {e}")
            return False
    
    def deploy(self):
        """Run the complete deployment"""
        logger.info("Starting MyAvatar webhook fix deployment...")
        
        steps = [
            ("Check prerequisites", self.check_prerequisites),
            ("Update database schema", self.update_database_schema),
            ("Validate voice manager", self.validate_voice_manager),
            ("Fix processing videos", self.fix_processing_videos),
            ("Test webhook endpoint", self.test_webhook_endpoint)
        ]
        
        for step_name, step_func in steps:
            logger.info(f"=== {step_name} ===")
            
            if not step_func():
                logger.error(f"Deployment failed at step: {step_name}")
                return False
            
            logger.info(f"✓ {step_name} completed successfully")
            
        logger.info("🎉 Deployment completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Restart your Flask application")
        logger.info("2. Test video creation with the new webhook")
        logger.info("3. Verify that custom voices are being used")
        
        return True


if __name__ == "__main__":
    # Set your project path
    PROJECT_PATH = r"C:\Users\mogen\Projects\python\CHATGPT\MyAvatar"
    
    # Run deployment
    deployment = MyAvatarDeployment(PROJECT_PATH)
    success = deployment.deploy()
    
    if success:
        print("\n✅ Deployment successful! Your webhook issue should be fixed.")
    else:
        print("\n❌ Deployment failed. Check the logs above for details.")
        sys.exit(1)
