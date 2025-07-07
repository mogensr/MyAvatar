#!/usr/bin/env python3
"""
Export Railway PostgreSQL Data for Local Development
SAFE EXPORT - Only reads data, never modifies production
"""
import os
import json
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def export_railway_data():
    """Safely export all data from Railway PostgreSQL"""
    print("🚀 Starting Railway PostgreSQL Data Export")
    print("=" * 50)
    
    # Get Railway database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in .env file")
        print("   Make sure your .env file contains the Railway PostgreSQL connection string")
        return False
    
    print(f"🔗 Connecting to Railway PostgreSQL...")
    print(f"   Database: {database_url.split('@')[1] if '@' in database_url else 'Railway PostgreSQL'}")
    
    try:
        # Import PostgreSQL library
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Connect to Railway PostgreSQL
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        print("✅ Connected to Railway PostgreSQL successfully!")
        
        export_data = {
            'export_info': {
                'timestamp': datetime.now().isoformat(),
                'source': 'Railway PostgreSQL',
                'purpose': 'Local development setup'
            }
        }
        
        # Export users table
        print("\n📊 Exporting users...")
        try:
            cursor.execute("SELECT * FROM users ORDER BY id")
            users = [dict(row) for row in cursor.fetchall()]
            export_data['users'] = users
            print(f"   ✅ Exported {len(users)} users")
        except Exception as e:
            print(f"   ⚠️ Users table issue: {e}")
            export_data['users'] = []
        
        # Export user_avatars table
        print("\n🎭 Exporting user avatars...")
        try:
            cursor.execute("SELECT * FROM user_avatars ORDER BY id")
            avatars = [dict(row) for row in cursor.fetchall()]
            export_data['user_avatars'] = avatars
            print(f"   ✅ Exported {len(avatars)} user avatars")
            
            # Show sample avatar URLs for verification
            if avatars:
                print("   📋 Sample avatar URLs:")
                for i, avatar in enumerate(avatars[:3]):
                    url = avatar.get('avatar_image_url', 'No URL')
                    print(f"      {i+1}. {avatar.get('avatar_name', 'Unknown')}: {url}")
                    
        except Exception as e:
            print(f"   ⚠️ User avatars table issue: {e}")
            export_data['user_avatars'] = []
        
        # Export videos table
        print("\n🎬 Exporting videos...")
        try:
            cursor.execute("SELECT * FROM videos ORDER BY id")
            videos = [dict(row) for row in cursor.fetchall()]
            export_data['videos'] = videos
            print(f"   ✅ Exported {len(videos)} videos")
        except Exception as e:
            print(f"   ⚠️ Videos table issue: {e}")
            export_data['videos'] = []
        
        # Check for additional tables
        print("\n🔍 Checking for additional tables...")
        try:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                AND table_name NOT IN ('users', 'user_avatars', 'videos')
            """)
            additional_tables = [row['table_name'] for row in cursor.fetchall()]
            
            if additional_tables:
                print(f"   📋 Found additional tables: {', '.join(additional_tables)}")
                for table_name in additional_tables:
                    try:
                        cursor.execute(f"SELECT * FROM {table_name}")
                        table_data = [dict(row) for row in cursor.fetchall()]
                        export_data[table_name] = table_data
                        print(f"   ✅ Exported {len(table_data)} records from {table_name}")
                    except Exception as e:
                        print(f"   ⚠️ Could not export {table_name}: {e}")
            else:
                print("   ✅ No additional tables found")
                
        except Exception as e:
            print(f"   ⚠️ Could not check for additional tables: {e}")
        
        # Save export to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_filename = f"railway_export_{timestamp}.json"
        
        print(f"\n💾 Saving export to {export_filename}...")
        with open(export_filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str, ensure_ascii=False)
        
        # Create summary
        total_records = sum(len(data) for key, data in export_data.items() 
                          if isinstance(data, list))
        
        print("\n" + "=" * 50)
        print("🎉 EXPORT COMPLETED SUCCESSFULLY!")
        print(f"📁 File: {export_filename}")
        print(f"📊 Total records exported: {total_records}")
        print(f"📋 Tables exported: {len([k for k, v in export_data.items() if isinstance(v, list)])}")
        print("\n🔒 Your production data is completely safe and unchanged!")
        
        conn.close()
        return export_filename
        
    except ImportError:
        print("❌ ERROR: psycopg2 not installed")
        print("   Run: pip install psycopg2-binary")
        return False
        
    except Exception as e:
        print(f"❌ ERROR during export: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    export_file = export_railway_data()
    if export_file:
        print(f"\n🚀 Next step: Set up local PostgreSQL and import this data")
        print(f"📁 Keep this file safe: {export_file}")
    else:
        print("\n❌ Export failed - check the errors above")
        sys.exit(1)
