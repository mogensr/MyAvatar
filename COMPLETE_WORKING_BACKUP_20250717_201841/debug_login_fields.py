#!/usr/bin/env python3
"""
Debug script to check what fields are returned for the admin user
"""
import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()

def main():
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found")
            return
        
        print("🔗 Connecting to database...")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Get admin user exactly as the login query does
        print("\n👤 ADMIN USER QUERY RESULT:")
        print("=" * 60)
        cursor.execute("SELECT * FROM users WHERE username = %s", ('admin',))
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        print(f"📋 Available columns: {column_names}")
        
        admin_row = cursor.fetchone()
        if admin_row:
            # Create dict like the app does
            admin_dict = dict(zip(column_names, admin_row))
            
            print(f"\n🔍 ADMIN USER DATA:")
            print(f"  👤 Username: {admin_dict.get('username')}")
            print(f"  📧 Email: {admin_dict.get('email')}")
            print(f"  🔑 Admin: {admin_dict.get('is_admin')}")
            
            # Check all possible password fields
            password_fields = ['password', 'hashed_password', 'password_hash']
            for field in password_fields:
                value = admin_dict.get(field)
                if value:
                    print(f"  🔐 {field}: {value[:30]}... (length: {len(value)})")
                else:
                    print(f"  ❌ {field}: NULL/Empty")
            
            # Test password verification
            print(f"\n🧪 PASSWORD VERIFICATION TEST:")
            test_password = "admin123"
            
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            for field in password_fields:
                stored_hash = admin_dict.get(field)
                if stored_hash:
                    try:
                        is_valid = pwd_context.verify(test_password, stored_hash)
                        print(f"  🔍 {field} vs '{test_password}': {'✅ VALID' if is_valid else '❌ INVALID'}")
                    except Exception as e:
                        print(f"  🔍 {field} vs '{test_password}': ❌ ERROR - {e}")
        else:
            print("  ❌ No admin user found")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
