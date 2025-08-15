#!/usr/bin/env python3
"""
Debug JWT Token Issues
"""
import os
import jwt
from datetime import datetime
import sys

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from config import JWT_SECRET

def debug_jwt_token():
    print("🔍 JWT Token Debug")
    print("=" * 50)
    
    # Check JWT secret
    print(f"📋 JWT_SECRET configured: {'Yes' if JWT_SECRET else 'No'}")
    if JWT_SECRET:
        print(f"📋 JWT_SECRET length: {len(JWT_SECRET)} characters")
        print(f"📋 JWT_SECRET preview: {JWT_SECRET[:10]}...")
    
    print("\n🔧 To debug your current token:")
    print("1. Open browser developer tools (F12)")
    print("2. Go to Application/Storage > Cookies")
    print("3. Find 'access_token' cookie")
    print("4. Copy the token value and paste it below when prompted")
    
    token = input("\n📝 Paste your JWT token here (or press Enter to skip): ").strip()
    
    if token:
        try:
            # Decode without verification first to see contents
            print("\n🔍 Token contents (unverified):")
            unverified = jwt.decode(token, options={"verify_signature": False})
            print(f"   User ID: {unverified.get('user_id')}")
            print(f"   Username: {unverified.get('username')}")
            print(f"   Issued at: {datetime.fromtimestamp(unverified.get('iat', 0))}")
            print(f"   Expires at: {datetime.fromtimestamp(unverified.get('exp', 0))}")
            
            # Check if expired
            exp = unverified.get('exp', 0)
            now = datetime.now().timestamp()
            if exp < now:
                print(f"❌ Token is EXPIRED! (expired {int(now - exp)} seconds ago)")
            else:
                print(f"✅ Token is still valid (expires in {int(exp - now)} seconds)")
            
            # Try to verify signature
            print("\n🔐 Verifying signature...")
            verified = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            print("✅ Token signature is VALID!")
            
        except jwt.ExpiredSignatureError:
            print("❌ Token is EXPIRED")
        except jwt.InvalidSignatureError:
            print("❌ Token signature is INVALID - wrong secret or corrupted token")
        except jwt.InvalidTokenError as e:
            print(f"❌ Token is invalid: {e}")
        except Exception as e:
            print(f"❌ Error decoding token: {e}")
    
    print("\n💡 Solutions:")
    print("1. If token is expired: Log out and log back in")
    print("2. If signature invalid: Clear cookies and log in again")
    print("3. If still failing: Check JWT_SECRET environment variable")

if __name__ == "__main__":
    debug_jwt_token()
