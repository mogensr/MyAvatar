#!/usr/bin/env python3
"""
🔍 MyAvatar Admin Status Checker
===============================
Check the current admin status in both local and production databases
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import execute_query, USE_POSTGRES
from dotenv import load_dotenv

load_dotenv()

def check_local_admin():
    """Check local database admin status"""
    print("🏠 LOCAL DATABASE STATUS")
    print("-" * 30)
    
    try:
        # Check database type
        db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
        print(f"Database type: {db_type}")
        
        # List all users
        users = execute_query("SELECT id, username, email, is_admin, created_at FROM users ORDER BY id", fetch_all=True)
        
        if not users:
            print("❌ No users found in local database")
            return False
        
        print(f"Total users: {len(users)}")
        print("\nUser details:")
        
        admin_count = 0
        for user in users:
            admin_status = "👑 ADMIN" if user[3] else "👤 USER"
            if user[3]:
                admin_count += 1
            created = user[4] if len(user) > 4 and user[4] else "Unknown"
            print(f"  ID {user[0]}: {user[1]} ({user[2]}) - {admin_status}")
            print(f"    Created: {created}")
        
        print(f"\nAdmin users: {admin_count}")
        
        if admin_count == 0:
            print("⚠️  WARNING: No admin users found!")
            return False
        else:
            print("✅ Admin users found")
            return True
            
    except Exception as e:
        print(f"❌ Error checking local database: {e}")
        return False

def check_production_admin():
    """Check production database admin status"""
    print("\n🚂 PRODUCTION DATABASE STATUS")
    print("-" * 35)
    
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found - cannot check production")
        return False
    
    try:
        import psycopg2
        
        # Convert postgres:// to postgresql:// if needed
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        print("✅ Connected to production database")
        
        # List all users
        cursor.execute("SELECT id, username, email, is_admin, created_at FROM users ORDER BY id")
        users = cursor.fetchall()
        
        if not users:
            print("❌ No users found in production database")
            conn.close()
            return False
        
        print(f"Total users: {len(users)}")
        print("\nUser details:")
        
        admin_count = 0
        for user in users:
            admin_status = "👑 ADMIN" if user[3] else "👤 USER"
            if user[3]:
                admin_count += 1
            created = user[4] if user[4] else "Unknown"
            print(f"  ID {user[0]}: {user[1]} ({user[2]}) - {admin_status}")
            print(f"    Created: {created}")
        
        print(f"\nAdmin users: {admin_count}")
        
        conn.close()
        
        if admin_count == 0:
            print("⚠️  WARNING: No admin users found in production!")
            return False
        else:
            print("✅ Admin users found in production")
            return True
            
    except ImportError:
        print("❌ psycopg2 not available - cannot check production database")
        return False
    except Exception as e:
        print(f"❌ Error checking production database: {e}")
        return False

def main():
    print("🔍 MyAvatar Admin Status Check")
    print("=" * 40)
    
    local_ok = check_local_admin()
    prod_ok = check_production_admin()
    
    print("\n" + "=" * 40)
    print("📊 SUMMARY")
    print("=" * 40)
    
    if local_ok:
        print("✅ Local database: Admin access OK")
    else:
        print("❌ Local database: No admin access")
        print("   💡 Run: python quick_admin_fix.py")
    
    if prod_ok:
        print("✅ Production database: Admin access OK")
    elif os.getenv("DATABASE_URL"):
        print("❌ Production database: No admin access")
        print("   💡 Run: python railway_admin_reset.py")
    else:
        print("⚠️  Production database: Cannot check (no DATABASE_URL)")
    
    print("\n🔑 Default admin credentials after reset:")
    print("   Username: admin")
    print("   Email: admin@myavatar.dk or admin@myavatar.com")
    print("   Password: Admin2025!")

if __name__ == "__main__":
    main()
