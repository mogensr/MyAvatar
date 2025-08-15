#!/usr/bin/env python3
"""
Export SQLite data for PostgreSQL migration
"""
import sqlite3
import json
import os
from datetime import datetime

def export_sqlite_data():
    """Export all data from SQLite database"""
    print("🔄 Starting SQLite data export...")
    
    # Connect to SQLite database
    db_path = "myavatar.db"
    if not os.path.exists(db_path):
        print(f"❌ SQLite database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    export_data = {}
    
    # Export users table
    try:
        cursor.execute("SELECT * FROM users")
        users = [dict(row) for row in cursor.fetchall()]
        export_data['users'] = users
        print(f"✅ Exported {len(users)} users")
    except Exception as e:
        print(f"⚠️ Users table: {e}")
        export_data['users'] = []
    
    # Export user_avatars table
    try:
        cursor.execute("SELECT * FROM user_avatars")
        avatars = [dict(row) for row in cursor.fetchall()]
        export_data['user_avatars'] = avatars
        print(f"✅ Exported {len(avatars)} user avatars")
    except Exception as e:
        print(f"⚠️ User avatars table: {e}")
        export_data['user_avatars'] = []
    
    # Export videos table
    try:
        cursor.execute("SELECT * FROM videos")
        videos = [dict(row) for row in cursor.fetchall()]
        export_data['videos'] = videos
        print(f"✅ Exported {len(videos)} videos")
    except Exception as e:
        print(f"⚠️ Videos table: {e}")
        export_data['videos'] = []
    
    # Save to JSON file
    export_file = f"sqlite_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(export_file, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    
    print(f"✅ Data exported to: {export_file}")
    
    conn.close()
    return export_file

if __name__ == "__main__":
    export_file = export_sqlite_data()
    if export_file:
        print(f"🎉 Export complete: {export_file}")
    else:
        print("❌ Export failed")
