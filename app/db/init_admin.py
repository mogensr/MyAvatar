"""
Initialize admin user for MyAvatar
"""
from ..auth.authentication import get_password_hash
from .database import execute_query
from ..logger.log_handler import log_info, log_error

def create_default_admin():
    """
    Create default admin user if it doesn't exist
    Username: admin
    Password: admin123
    """
    try:
        # Check if admin user already exists
        admin_user = execute_query(
            "SELECT * FROM users WHERE username = %s", 
            ("admin",), 
            fetch_one=True
        )
        
        if admin_user:
            log_info("Admin user already exists", "Database")
            return
        
        # Create admin user
        admin_password = get_password_hash("admin123")
        
        execute_query(
            """
            INSERT INTO users (username, email, hashed_password, is_admin)
            VALUES (%s, %s, %s, %s)
            """,
            ("admin", "admin@myavatar.com", admin_password, True)
        )
        
        log_info("Default admin user created", "Database")
    except Exception as e:
        log_error("Failed to create admin user", "Database", e)
