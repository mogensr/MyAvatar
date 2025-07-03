#!/usr/bin/env python3
"""
Add JWT_SECRET_KEY to .env file if missing
"""
import os
import secrets

def add_jwt_secret():
    """Add JWT_SECRET_KEY to .env file if it's missing"""
    env_file = '.env'
    
    if not os.path.exists(env_file):
        print("❌ .env file not found")
        return False
    
    # Read current .env content
    with open(env_file, 'r') as f:
        content = f.read()
    
    # Check if JWT_SECRET_KEY already exists
    if 'JWT_SECRET_KEY=' in content:
        print("✅ JWT_SECRET_KEY already exists in .env")
        return True
    
    # Generate a secure random key
    jwt_secret = secrets.token_urlsafe(32)
    
    # Add JWT_SECRET_KEY to .env file
    with open(env_file, 'a') as f:
        f.write(f'\n# JWT Secret Key (auto-generated)\nJWT_SECRET_KEY={jwt_secret}\n')
    
    print("✅ JWT_SECRET_KEY added to .env file")
    print(f"Generated key: {jwt_secret[:8]}...{jwt_secret[-8:]}")
    return True

if __name__ == "__main__":
    add_jwt_secret()
