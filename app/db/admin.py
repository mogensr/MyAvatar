"""
Admin user creation functionality
"""
from ..auth.authentication import get_password_hash
from .database import execute_query
from ..logger.log_handler import log_info, log_warning

def create_admin_user():
    """
    Create admin user if it doesn't exist
    Username: admin
    Password: admin123
    """
    try:
        # Check if admin user exists
        admin = execute_query(
            "SELECT id FROM users WHERE username = ?", 
            ("admin",), 
            fetch_one=True
        )
        
        if not admin:
            # Create admin user
            admin_password = get_password_hash("admin123")
            execute_query(
                """
                INSERT INTO users (username, email, password, is_admin) 
                VALUES (?, ?, ?, ?)
                """, 
                ("admin", "admin@myavatar.com", admin_password, 1)
            )
            log_info("Admin user created successfully", "Database")
        else:
            log_warning("Admin user already exists", "Database")
    except Exception as e:
        log_warning(f"Error creating admin user: {str(e)}", "Database")