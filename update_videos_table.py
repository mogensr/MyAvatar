"""
Database Update Script for BackgroundFX Video Processing
Run this script to add required columns to the videos table for BackgroundFX functionality
"""

import os
import sys
from datetime import datetime

# Try to import database connection
try:
    # Add your project path to Python path
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from app.db.database import execute_query
    from app.logger.log_handler import log_info, log_error
    print("✅ Successfully imported database modules")
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print("Make sure you're running this from your MyAvatar project root directory")
    input("Press Enter to exit...")
    sys.exit(1)

def update_videos_table():
    """Add BackgroundFX columns to videos table"""
    print("\n🔧 UPDATING VIDEOS TABLE FOR BACKGROUNDFX")
    print("=" * 50)
    
    # List of columns to add
    columns_to_add = [
        {
            'name': 'background_image_path',
            'type': 'TEXT',
            'description': 'URL/path to background image used in processing'
        },
        {
            'name': 'original_video_path', 
            'type': 'TEXT',
            'description': 'URL/path to original input video before processing'
        },
        {
            'name': 'processing_type',
            'type': 'VARCHAR(50)',
            'description': 'Type of processing: background_replacement, enhancement, etc.'
        },
        {
            'name': 'background_type',
            'type': 'VARCHAR(50)', 
            'description': 'Background type: image, color, blur, processed'
        },
        {
            'name': 'description',
            'type': 'TEXT',
            'description': 'Video description'
        },
        {
            'name': 'format',
            'type': 'VARCHAR(20)',
            'description': 'Video format/aspect ratio'
        }
    ]
    
    print("Adding the following columns to videos table:")
    for i, col in enumerate(columns_to_add, 1):
        print(f"  {i}. {col['name']} ({col['type']}) - {col['description']}")
    
    print("\n" + "=" * 50)
    confirm = input("Do you want to proceed? (y/N): ").lower().strip()
    
    if confirm != 'y':
        print("❌ Operation cancelled")
        return False
    
    print("\n🚀 Starting database update...")
    
    # Add each column
    success_count = 0
    for col in columns_to_add:
        try:
            sql = f"ALTER TABLE videos ADD COLUMN IF NOT EXISTS {col['name']} {col['type']}"
            print(f"\n📝 Adding column: {col['name']}")
            execute_query(sql)
            print(f"✅ Successfully added: {col['name']}")
            success_count += 1
            
        except Exception as e:
            print(f"❌ Error adding {col['name']}: {e}")
            log_error(f"Failed to add column {col['name']}: {e}", "DatabaseUpdate")
    
    print(f"\n🎉 COMPLETED: {success_count}/{len(columns_to_add)} columns added successfully")
    
    if success_count == len(columns_to_add):
        print("✅ All columns added successfully! BackgroundFX is ready to use.")
        return True
    else:
        print("⚠️ Some columns failed to add. Check the errors above.")
        return False

def verify_table_structure():
    """Verify the updated table structure"""
    print("\n🔍 VERIFYING TABLE STRUCTURE")
    print("=" * 50)
    
    try:
        # Get a sample record to see all columns
        result = execute_query(
            "SELECT * FROM videos LIMIT 1",
            fetch_one=True
        )
        
        if result:
            print("Current videos table columns:")
            for i, column in enumerate(result.keys(), 1):
                print(f"  {i:2d}. {column}")
        else:
            print("No records found, but table structure should be updated")
            
        print("\n✅ Table verification completed")
        return True
        
    except Exception as e:
        print(f"❌ Error verifying table: {e}")
        return False

def main():
    """Main execution function"""
    print("🎬 MYAVATAR BACKGROUNDFX DATABASE UPDATE")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("This script will add required columns to support BackgroundFX video processing")
    
    try:
        # Step 1: Update table
        if update_videos_table():
            print("\n" + "=" * 50)
            
            # Step 2: Verify changes
            if verify_table_structure():
                print("\n🎉 DATABASE UPDATE SUCCESSFUL!")
                print("Your MyAvatar system is now ready for BackgroundFX video processing.")
                print("\nNext steps:")
                print("1. Deploy your updated video_processing_routes.py")
                print("2. Test BackgroundFX - processed videos should now appear in Recent Videos")
                
            else:
                print("\n⚠️ Update completed but verification failed")
        
        else:
            print("\n❌ DATABASE UPDATE FAILED")
            print("Please check the errors above and try again")
    
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        log_error(f"Database update script error: {e}", "DatabaseUpdate")
    
    finally:
        print("\n" + "=" * 50)
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
