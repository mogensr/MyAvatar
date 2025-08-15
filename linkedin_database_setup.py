"""
LinkedIn Database Setup - Schema for LinkedIn Integration
Creates tables for storing LinkedIn OAuth tokens and connection data
"""

import sqlite3
import logging
from typing import Dict, Optional, List
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def create_linkedin_tables():
    """Create LinkedIn-related database tables"""
    try:
        conn = sqlite3.connect('myavatar.db')
        cursor = conn.cursor()
        
        # LinkedIn Connections table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS linkedin_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                linkedin_user_id TEXT NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_expires_at DATETIME,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                profile_picture_url TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, linkedin_user_id)
            )
        ''')
        
        # LinkedIn Company Pages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS linkedin_company_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id INTEGER NOT NULL,
                company_id TEXT NOT NULL,
                company_name TEXT NOT NULL,
                company_logo_url TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (connection_id) REFERENCES linkedin_connections (id),
                UNIQUE(connection_id, company_id)
            )
        ''')
        
        # LinkedIn Posts table (for tracking posted content)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS linkedin_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                connection_id INTEGER NOT NULL,
                video_id INTEGER,
                linkedin_post_id TEXT,
                post_text TEXT NOT NULL,
                post_url TEXT,
                media_url TEXT,
                hashtags TEXT,
                emojis TEXT,
                post_type TEXT DEFAULT 'video_share',
                engagement_stats TEXT,
                posted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (connection_id) REFERENCES linkedin_connections (id),
                FOREIGN KEY (video_id) REFERENCES videos (id)
            )
        ''')
        
        # LinkedIn Content Templates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS linkedin_content_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                template_name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                content_template TEXT NOT NULL,
                hashtags_template TEXT,
                emojis_template TEXT,
                cta_template TEXT,
                is_active BOOLEAN DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # LinkedIn Analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS linkedin_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                likes_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                shares_count INTEGER DEFAULT 0,
                views_count INTEGER DEFAULT 0,
                clicks_count INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0.0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES linkedin_posts (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("✅ LinkedIn database tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create LinkedIn tables: {e}")
        return False

class LinkedInDatabaseManager:
    """Manage LinkedIn-related database operations"""
    
    def __init__(self, db_path: str = 'myavatar.db'):
        self.db_path = db_path
    
    def save_linkedin_connection(self, user_id: int, token_data: Dict, profile_data: Dict) -> Optional[int]:
        """Save LinkedIn OAuth connection to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Calculate token expiry
            expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 5184000))
            
            cursor.execute('''
                INSERT OR REPLACE INTO linkedin_connections 
                (user_id, linkedin_user_id, access_token, token_expires_at, 
                 first_name, last_name, email, profile_picture_url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                user_id,
                profile_data.get('id', ''),
                token_data['access_token'],
                expires_at,
                profile_data.get('first_name', ''),
                profile_data.get('last_name', ''),
                profile_data.get('email', ''),
                profile_data.get('profile_picture', '')
            ))
            
            connection_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Saved LinkedIn connection for user {user_id}")
            return connection_id
            
        except Exception as e:
            logger.error(f"❌ Failed to save LinkedIn connection: {e}")
            return None
    
    def get_linkedin_connection(self, user_id: int) -> Optional[Dict]:
        """Get active LinkedIn connection for user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, linkedin_user_id, access_token, token_expires_at,
                       first_name, last_name, email, profile_picture_url
                FROM linkedin_connections 
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'linkedin_user_id': row[1],
                    'access_token': row[2],
                    'token_expires_at': row[3],
                    'first_name': row[4],
                    'last_name': row[5],
                    'email': row[6],
                    'profile_picture_url': row[7]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get LinkedIn connection: {e}")
            return None
    
    def save_linkedin_post(self, user_id: int, connection_id: int, post_data: Dict) -> Optional[int]:
        """Save LinkedIn post record to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO linkedin_posts 
                (user_id, connection_id, video_id, linkedin_post_id, post_text, 
                 post_url, media_url, hashtags, emojis, post_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                connection_id,
                post_data.get('video_id'),
                post_data.get('linkedin_post_id'),
                post_data['post_text'],
                post_data.get('post_url'),
                post_data.get('media_url'),
                json.dumps(post_data.get('hashtags', [])),
                json.dumps(post_data.get('emojis', [])),
                post_data.get('post_type', 'video_share')
            ))
            
            post_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Saved LinkedIn post record: {post_id}")
            return post_id
            
        except Exception as e:
            logger.error(f"❌ Failed to save LinkedIn post: {e}")
            return None
    
    def save_content_template(self, user_id: int, template_data: Dict) -> Optional[int]:
        """Save LinkedIn content template"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO linkedin_content_templates 
                (user_id, template_name, template_type, content_template, 
                 hashtags_template, emojis_template, cta_template)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                template_data['name'],
                template_data['type'],
                template_data['content'],
                template_data.get('hashtags', ''),
                template_data.get('emojis', ''),
                template_data.get('cta', '')
            ))
            
            template_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Saved LinkedIn content template: {template_id}")
            return template_id
            
        except Exception as e:
            logger.error(f"❌ Failed to save content template: {e}")
            return None
    
    def get_user_templates(self, user_id: int, template_type: Optional[str] = None) -> List[Dict]:
        """Get user's LinkedIn content templates"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
                SELECT id, template_name, template_type, content_template,
                       hashtags_template, emojis_template, cta_template, usage_count
                FROM linkedin_content_templates 
                WHERE user_id = ? AND is_active = 1
            '''
            params = [user_id]
            
            if template_type:
                query += ' AND template_type = ?'
                params.append(template_type)
            
            query += ' ORDER BY usage_count DESC, created_at DESC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            templates = []
            for row in rows:
                templates.append({
                    'id': row[0],
                    'name': row[1],
                    'type': row[2],
                    'content': row[3],
                    'hashtags': row[4],
                    'emojis': row[5],
                    'cta': row[6],
                    'usage_count': row[7]
                })
            
            return templates
            
        except Exception as e:
            logger.error(f"❌ Failed to get user templates: {e}")
            return []
    
    def disconnect_linkedin(self, user_id: int) -> bool:
        """Disconnect LinkedIn account (deactivate connection)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE linkedin_connections 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Disconnected LinkedIn for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to disconnect LinkedIn: {e}")
            return False

# Initialize database tables
def init_linkedin_database():
    """Initialize LinkedIn database tables"""
    return create_linkedin_tables()

# Global database manager instance
linkedin_db = LinkedInDatabaseManager()
