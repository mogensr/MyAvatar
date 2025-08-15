"""
Security utilities for MyAvatar
Handles input sanitization and validation
"""
import re
import html
from typing import Optional

def sanitize_input(input_str: str) -> str:
    """
    Sanitize user input to prevent XSS and other injection attacks
    
    Args:
        input_str: Raw user input string
        
    Returns:
        Sanitized string safe for display
    """
    if not input_str:
        return ""
    
    # Convert to string if not already
    input_str = str(input_str)
    
    # HTML escape to prevent XSS
    sanitized = html.escape(input_str)
    
    # Remove any remaining potentially dangerous characters
    # Allow letters, numbers, spaces, and common punctuation
    sanitized = re.sub(r'[<>"\']', '', sanitized)
    
    # Limit length to prevent abuse
    if len(sanitized) > 1000:
        sanitized = sanitized[:1000]
    
    return sanitized.strip()

def validate_email(email: str) -> bool:
    """
    Validate email address format
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email format is valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic email regex pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    return bool(re.match(email_pattern, email.strip()))

def validate_username(username: str) -> bool:
    """
    Validate username format
    
    Args:
        username: Username to validate
        
    Returns:
        True if username format is valid, False otherwise
    """
    if not username or not isinstance(username, str):
        return False
    
    # Username should be 3-50 characters, alphanumeric plus hyphens and underscores
    username_pattern = r'^[a-zA-Z0-9_-]{3,50}$'
    
    return bool(re.match(username_pattern, username.strip()))

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for file operations
    """
    if not filename:
        return "unnamed_file"
    
    # Remove directory separators and dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:250] + ('.' + ext if ext else '')
    
    return sanitized or "unnamed_file"

def is_safe_redirect_url(url: str, allowed_hosts: Optional[list] = None) -> bool:
    """
    Check if a redirect URL is safe (prevents open redirect attacks)
    
    Args:
        url: URL to check
        allowed_hosts: List of allowed host names (optional)
        
    Returns:
        True if URL is safe for redirect, False otherwise
    """
    if not url:
        return False
    
    # Allow relative URLs (starting with /)
    if url.startswith('/') and not url.startswith('//'):
        return True
    
    # If absolute URL, check against allowed hosts
    if allowed_hosts and url.startswith(('http://', 'https://')):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc in allowed_hosts
    
    # Reject all other absolute URLs
    return False
