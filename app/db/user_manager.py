"""
User management database class for MyAvatar
Provides a Database class interface for user operations
"""
from .database import execute_query
from ..auth.authentication import get_password_hash, verify_password
from ..logger.log_handler import log_info, log_error, log_warning
from datetime import datetime

class Database:
    """Database class for user management operations"""
    
    def get_user_by_username(self, username):
        """Get user by username"""
        try:
            log_info(f"Looking up user: {username}", "UserManager")
            result = execute_query(
                "SELECT * FROM users WHERE username = ?", 
                (username,), 
                fetch_one=True
            )
            if result:
                log_info(f"User found: {username}", "UserManager")
                return dict(result) if hasattr(result, 'keys') else result
            else:
                log_warning(f"User not found: {username}", "UserManager")
                return None
        except Exception as e:
            log_error(f"Error getting user by username {username}: {str(e)}", "UserManager", e)
            return None
    
    def get_user_by_email(self, email):
        """Get user by email"""
        try:
            log_info(f"Looking up user by email: {email}", "UserManager")
            result = execute_query(
                "SELECT * FROM users WHERE email = ?", 
                (email,), 
                fetch_one=True
            )
            if result:
                log_info(f"User found by email: {email}", "UserManager")
                return dict(result) if hasattr(result, 'keys') else result
            else:
                log_warning(f"User not found by email: {email}", "UserManager")
                return None
        except Exception as e:
            log_error(f"Error getting user by email {email}: {str(e)}", "UserManager", e)
            return None
    
    def get_user_by_id(self, user_id):
        """Get user by ID"""
        try:
            log_info(f"Looking up user by ID: {user_id}", "UserManager")
            result = execute_query(
                "SELECT * FROM users WHERE id = ?", 
                (user_id,), 
                fetch_one=True
            )
            if result:
                log_info(f"User found by ID: {user_id}", "UserManager")
                return dict(result) if hasattr(result, 'keys') else result
            else:
                log_warning(f"User not found by ID: {user_id}", "UserManager")
                return None
        except Exception as e:
            log_error(f"Error getting user by ID {user_id}: {str(e)}", "UserManager", e)
            return None
    
    def create_user(self, user_data):
        """Create a new user"""
        try:
            log_info(f"Creating user: {user_data.get('username')}", "UserManager")
            
            # Hash the password
            password_hash = get_password_hash(user_data['password'])
            
            # Insert user
            result = execute_query(
                """
                INSERT INTO users (username, email, password, is_admin, created_at) 
                VALUES (?, ?, ?, ?, ?)
                """, 
                (
                    user_data['username'],
                    user_data['email'], 
                    password_hash,
                    user_data.get('is_admin', 0),
                    datetime.now()
                )
            )
            
            # Get the user ID
            user = self.get_user_by_username(user_data['username'])
            if user:
                user_id = user.get('id')
                log_info(f"User created successfully with ID: {user_id}", "UserManager")
                return user_id
            else:
                log_error("Failed to retrieve created user", "UserManager")
                return None
                
        except Exception as e:
            log_error(f"Error creating user {user_data.get('username')}: {str(e)}", "UserManager", e)
            return None
    
    def update_user_login(self, user_id):
        """Update user's last login time"""
        try:
            execute_query(
                "UPDATE users SET last_login = ? WHERE id = ?", 
                (datetime.now(), user_id)
            )
            log_info(f"Updated login time for user ID: {user_id}", "UserManager")
        except Exception as e:
            log_error(f"Error updating login time for user {user_id}: {str(e)}", "UserManager", e)
    
    def get_failed_login_attempts(self, ip, username):
        """Get failed login attempts count"""
        try:
            # For now, return 0 - this could be implemented with a separate table
            return 0
        except Exception as e:
            log_error(f"Error getting failed login attempts: {str(e)}", "UserManager", e)
            return 0
    
    def record_failed_login(self, ip, username):
        """Record a failed login attempt"""
        try:
            log_warning(f"Failed login attempt from {ip} for {username}", "UserManager")
            # Could implement with a separate failed_logins table
        except Exception as e:
            log_error(f"Error recording failed login: {str(e)}", "UserManager", e)
    
    def clear_failed_login_attempts(self, ip, username):
        """Clear failed login attempts"""
        try:
            log_info(f"Clearing failed login attempts for {username} from {ip}", "UserManager")
            # Could implement with a separate failed_logins table
        except Exception as e:
            log_error(f"Error clearing failed login attempts: {str(e)}", "UserManager", e)
    
    def get_user_videos(self, user_id):
        """Get videos for a user"""
        try:
            result = execute_query(
                "SELECT * FROM videos WHERE user_id = ? ORDER BY created_at DESC", 
                (user_id,), 
                fetch_all=True
            )
            return [dict(row) if hasattr(row, 'keys') else row for row in result] if result else []
        except Exception as e:
            log_error(f"Error getting videos for user {user_id}: {str(e)}", "UserManager", e)
            return []
    
    def get_user_avatars(self, user_id):
        """Get avatars for a user"""
        try:
            result = execute_query(
                "SELECT * FROM user_avatars WHERE user_id = ? ORDER BY created_at DESC", 
                (user_id,), 
                fetch_all=True
            )
            return [dict(row) if hasattr(row, 'keys') else row for row in result] if result else []
        except Exception as e:
            log_error(f"Error getting avatars for user {user_id}: {str(e)}", "UserManager", e)
            return []

    def create_user_settings_table(self):
        """Create user_settings table if it doesn't exist"""
        try:
            execute_query("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    setting_name VARCHAR(100) NOT NULL,
                    setting_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, setting_name)
                )
            """)
            log_info("user_settings table created/verified", "UserManager")
            return True
        except Exception as e:
            log_error(f"Error creating user_settings table: {str(e)}", "UserManager", e)
            return False

    def get_user_setting(self, user_id, setting_name, default_value=None):
        """Get a user setting value"""
        try:
            result = execute_query(
                "SELECT setting_value FROM user_settings WHERE user_id = ? AND setting_name = ?",
                (user_id, setting_name),
                fetch_one=True
            )
            if result:
                return result['setting_value'] if hasattr(result, 'keys') else result[0]
            return default_value
        except Exception as e:
            log_error(f"Error getting user setting {setting_name} for user {user_id}: {str(e)}", "UserManager", e)
            return default_value

    def set_user_setting(self, user_id, setting_name, setting_value):
        """Set a user setting value"""
        try:
            # Use UPSERT (INSERT ... ON CONFLICT) for PostgreSQL
            execute_query("""
                INSERT INTO user_settings (user_id, setting_name, setting_value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, setting_name)
                DO UPDATE SET 
                    setting_value = EXCLUDED.setting_value,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, setting_name, setting_value))
            log_info(f"Set user setting {setting_name} = {setting_value} for user {user_id}", "UserManager")
            return True
        except Exception as e:
            log_error(f"Error setting user setting {setting_name} for user {user_id}: {str(e)}", "UserManager", e)
            return False
