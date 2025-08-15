#!/usr/bin/env python3
"""
Auto-run migrations on startup for Railway deployment
"""
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def run_migrations():
    """Run all pending migrations"""
    try:
        print("🔄 Running database migrations...")
        
        # Import and run video processing migration
        from migrations.add_video_processing_tables import apply_migration, get_migration_status
        
        # Check status first
        status = get_migration_status()
        print(f"Migration status: {status}")
        
        if not status.get('is_applied', False):
            print("📊 Applying video processing tables migration...")
            success = apply_migration()
            if success:
                print("✅ Video processing migration completed successfully")
            else:
                print("❌ Video processing migration failed")
                return False
        else:
            print("✅ Video processing migration already applied")
        
        print("🎉 All migrations completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
