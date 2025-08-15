#!/usr/bin/env python3
"""
Test environment variable loading
"""
import os
from dotenv import load_dotenv

def test_env_loading():
    """Test if .env file is being loaded correctly"""
    print("=== ENVIRONMENT VARIABLE LOADING TEST ===")
    
    # Try to load .env file explicitly
    print("Loading .env file...")
    load_dotenv()
    
    # Check key environment variables
    env_vars = {
        'DATABASE_URL': os.getenv('DATABASE_URL'),
        'HEYGEN_API_KEY': os.getenv('HEYGEN_API_KEY'),
        'JWT_SECRET_KEY': os.getenv('JWT_SECRET_KEY')
    }
    
    print("\nEnvironment Variables Status:")
    for var_name, var_value in env_vars.items():
        if var_value:
            # Mask sensitive values for security
            if 'KEY' in var_name or 'PASSWORD' in var_name or 'DATABASE_URL' in var_name:
                if len(var_value) > 12:
                    masked = var_value[:8] + '...' + var_value[-4:]
                else:
                    masked = '***'
                print(f"✅ {var_name}: {masked}")
            else:
                print(f"✅ {var_name}: {var_value}")
        else:
            print(f"❌ {var_name}: Not found")
    
    # Test database connection
    if env_vars['DATABASE_URL']:
        print("\n=== DATABASE CONNECTION TEST ===")
        try:
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
            from app.db.database import execute_query
            
            # Simple test query
            result = execute_query("SELECT 1 as test", fetch_one=True)
            if result:
                print("✅ Database connection successful")
                
                # Test user table access
                users = execute_query("SELECT COUNT(*) as count FROM users", fetch_one=True)
                if users:
                    print(f"✅ Found {users['count']} users in database")
                else:
                    print("⚠️  Users table accessible but empty")
                    
            else:
                print("❌ Database connection failed")
                
        except Exception as e:
            print(f"❌ Database connection error: {e}")
    
    # Test HeyGen API
    if env_vars['HEYGEN_API_KEY']:
        print("\n=== HEYGEN API TEST ===")
        try:
            import requests
            
            headers = {
                'X-API-KEY': env_vars['HEYGEN_API_KEY'],
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                'https://api.heygen.com/v2/avatars',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ HeyGen API connection successful")
                data = response.json()
                avatars = data.get('data', {}).get('avatars', [])
                print(f"✅ Found {len(avatars)} avatars from HeyGen")
            else:
                print(f"❌ HeyGen API returned status {response.status_code}")
                
        except Exception as e:
            print(f"❌ HeyGen API error: {e}")

if __name__ == "__main__":
    test_env_loading()
