import re
from typing import Tuple

# Try to import bleach for advanced sanitization
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False

def validate_email(email: str) -> bool:
    """Basic email validation"""
    if not email or not isinstance(email, str):
        return False
    
    # Basic regex for email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None

def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username format and requirements"""
    if not username or not isinstance(username, str):
        return False, "Username is required"
    
    username = username.strip()
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    
    if len(username) > 50:
        return False, "Username must be no more than 50 characters long"
    
    # Check for valid characters (letters, numbers, hyphens, underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, hyphens, and underscores"
    
    # Cannot start or end with special characters
    if username.startswith(('-', '_')) or username.endswith(('-', '_')):
        return False, "Username cannot start or end with hyphen or underscore"
    
    # Cannot be all numbers
    if username.isdigit():
        return False, "Username cannot be all numbers"
    
    return True, "Username is valid"

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS"""
    if not text:
        return ""
    
    # Convert to string and strip whitespace
    text = str(text).strip()
    
    if BLEACH_AVAILABLE:
        # Use bleach for advanced sanitization
        return bleach.clean(text, tags=[], attributes={}, strip=True)
    else:
        # Basic sanitization without bleach
        return (text.replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("&", "&amp;")
                   .replace('"', "&quot;")
                   .replace("'", "&#x27;"))

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Enhanced password validation"""
    if not password or not isinstance(password, str):
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 128:
        return False, "Password must be no more than 128 characters long"
    
    # Check for at least 2 digits
    digit_count = sum(1 for c in password if c.isdigit())
    if digit_count < 2:
        return False, "Password must contain at least 2 digits"
    
    # Check for uppercase letter
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for lowercase letter
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    # Optional: Check for special characters
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "Password should contain at least one special character"
    
    return True, "Password is strong"

def validate_file_upload(filename: str, max_size: int = 5242880, allowed_extensions: set = None) -> Tuple[bool, str]:
    """Validate file upload"""
    if not filename:
        return False, "Filename is required"
    
    if allowed_extensions is None:
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    
    # Check file extension
    if '.' not in filename:
        return False, "File must have an extension"
    
    extension = filename.rsplit('.', 1)[1].lower()
    if extension not in allowed_extensions:
        return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
    
    return True, "File is valid"

def validate_video_title(title: str) -> Tuple[bool, str]:
    """Validate video title"""
    if not title or not isinstance(title, str):
        return False, "Title is required"
    
    title = title.strip()
    
    if len(title) < 1:
        return False, "Title cannot be empty"
    
    if len(title) > 100:
        return False, "Title must be no more than 100 characters long"
    
    # Basic content validation (no HTML tags)
    if '<' in title or '>' in title:
        return False, "Title cannot contain HTML tags"
    
    return True, "Title is valid"

def validate_avatar_name(name: str) -> Tuple[bool, str]:
    """Validate avatar name"""
    if not name or not isinstance(name, str):
        return False, "Avatar name is required"
    
    name = name.strip()
    
    if len(name) < 1:
        return False, "Avatar name cannot be empty"
    
    if len(name) > 50:
        return False, "Avatar name must be no more than 50 characters long"
    
    # Only allow letters, numbers, spaces, and basic punctuation
    if not re.match(r'^[a-zA-Z0-9 ._-]+$', name):
        return False, "Avatar name can only contain letters, numbers, spaces, periods, hyphens, and underscores"
    
    return True, "Avatar name is valid"
