"""
Professional Migration Runner System
Tracks and executes database migrations safely
"""

import psycopg2
import os
import importlib.util
import sys
from datetime import datetime
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationRunner:
    def __init__(self, database_url=None, migrations_dir="migrations"):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.migrations_dir = Path(migrations_dir)
        
        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment variables")
    
    def ensure_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255) UNIQUE NOT NULL,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    checksum VARCHAR(64),
                    execution_time_ms INTEGER
                );
                
                -- Add missing columns if they don't exist
                ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER;
            """)
            
            conn.commit()
            logger.info("✅ Schema migrations table ready")
            
        except Exception as e:
            logger.error(f"❌ Failed to create migrations table: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_executed_migrations(self):
        """Get list of already executed migrations"""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            cursor.execute("SELECT migration_name FROM schema_migrations ORDER BY executed_at")
            executed = [row[0] for row in cursor.fetchall()]
            
            return executed
            
        except Exception as e:
            logger.error(f"❌ Failed to get executed migrations: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def discover_migrations(self):
        """Find all migration files in the migrations directory"""
        migration_files = []
        
        if not self.migrations_dir.exists():
            logger.warning(f"⚠️ Migrations directory {self.migrations_dir} does not exist")
            return migration_files
        
        for file_path in sorted(self.migrations_dir.glob("*.py")):
            if file_path.name.startswith("__"):
                continue
            if file_path.name == "migration_runner.py":
                continue  # Skip the runner itself
                
            migration_files.append(file_path)
        
        logger.info(f"📁 Found {len(migration_files)} migration files")
        return migration_files
    
    def load_migration_module(self, file_path):
        """Dynamically load a migration module"""
        try:
            spec = importlib.util.spec_from_file_location("migration", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            return module
        except Exception as e:
            logger.error(f"❌ Failed to load migration {file_path}: {e}")
            raise
    
    def execute_migration(self, file_path):
        """Execute a single migration file"""
        migration_name = file_path.stem
        start_time = datetime.now()
        
        logger.info(f"🚀 Executing migration: {migration_name}")
        
        try:
            # Load the migration module
            module = self.load_migration_module(file_path)
            
            if not hasattr(module, 'run_migration'):
                raise AttributeError(f"Migration {migration_name} must have a 'run_migration' function")
            
            # Execute the migration
            success = module.run_migration()
            
            if not success:
                raise Exception(f"Migration {migration_name} returned False")
            
            # Record successful execution
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.record_migration(migration_name, execution_time)
            
            logger.info(f"✅ Migration {migration_name} completed in {execution_time}ms")
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration {migration_name} failed: {e}")
            raise
    
    def record_migration(self, migration_name, execution_time_ms):
        """Record successful migration execution"""
        try:
            conn = psycopg2.connect(self.database_url)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO schema_migrations (migration_name, execution_time_ms)
                VALUES (%s, %s)
            """, (migration_name, execution_time_ms))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"❌ Failed to record migration: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def run_pending_migrations(self):
        """Run all pending migrations"""
        logger.info("🔍 Checking for pending migrations...")
        
        # Ensure migrations table exists
        self.ensure_migrations_table()
        
        # Get executed and available migrations
        executed_migrations = set(self.get_executed_migrations())
        migration_files = self.discover_migrations()
        
        pending_migrations = []
        for file_path in migration_files:
            migration_name = file_path.stem
            if migration_name not in executed_migrations:
                pending_migrations.append(file_path)
        
        if not pending_migrations:
            logger.info("✅ No pending migrations found")
            return True
        
        logger.info(f"📋 Found {len(pending_migrations)} pending migrations:")
        for file_path in pending_migrations:
            logger.info(f"  - {file_path.stem}")
        
        # Execute pending migrations
        total_start = datetime.now()
        executed_count = 0
        
        for file_path in pending_migrations:
            try:
                self.execute_migration(file_path)
                executed_count += 1
            except Exception as e:
                logger.error(f"💥 Migration batch failed at {file_path.stem}")
                return False
        
        total_time = (datetime.now() - total_start).total_seconds()
        logger.info(f"🎉 Successfully executed {executed_count} migrations in {total_time:.2f}s")
        
        return True
    
    def migration_status(self):
        """Show migration status"""
        executed_migrations = set(self.get_executed_migrations())
        migration_files = self.discover_migrations()
        
        print("\n📊 Migration Status:")
        print("=" * 60)
        
        for file_path in migration_files:
            migration_name = file_path.stem
            status = "✅ EXECUTED" if migration_name in executed_migrations else "⏳ PENDING"
            print(f"{status:12} {migration_name}")
        
        pending_count = len([f for f in migration_files if f.stem not in executed_migrations])
        print("=" * 60)
        print(f"Total: {len(migration_files)} migrations, {pending_count} pending")
        print()

def main():
    """Command line interface for migrations"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database Migration Runner")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--run", action="store_true", help="Run pending migrations")
    parser.add_argument("--migrations-dir", default="migrations", help="Migrations directory")
    
    args = parser.parse_args()
    
    try:
        runner = MigrationRunner(migrations_dir=args.migrations_dir)
        
        if args.status:
            runner.migration_status()
        elif args.run:
            runner.run_pending_migrations()
        else:
            print("Use --status to check migrations or --run to execute pending migrations")
            
    except Exception as e:
        logger.error(f"💥 Migration runner failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
