"""
Migration: Add Video Processing Tables
Creates complete database schema for advanced background replacement functionality

Migration ID: 20250711_001_add_video_processing_tables
Dependencies: Requires users table to exist
"""
import logging
from datetime import datetime
from typing import Dict, Any, List

# MyAvatar imports
try:
    from app.db.database import execute_query, get_db_connection
    from app.logger.log_handler import log_info, log_error, log_warning
except ImportError:
    # Fallback for migration environments
    def execute_query(*args, **kwargs): pass
    def get_db_connection(): return None
    def log_info(msg, context): logging.info(f"[{context}] {msg}")
    def log_error(msg, context, exc=None): logging.error(f"[{context}] {msg}")
    def log_warning(msg, context): logging.warning(f"[{context}] {msg}")

logger = logging.getLogger(__name__)

# Migration metadata
MIGRATION_ID = "20250711_001_add_video_processing_tables"
MIGRATION_NAME = "Add Video Processing Tables"
MIGRATION_DESCRIPTION = "Creates tables for advanced video background replacement functionality"

def check_prerequisites() -> bool:
    """Check if prerequisites for this migration exist"""
    try:
        # Check if users table exists
        result = execute_query(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            )""",
            fetch_one=True
        )
        
        if not result or not result.get('exists'):
            log_error("Users table does not exist - required for foreign keys", "Migration")
            return False
        
        # Check if migration tracking table exists
        migration_table_exists = execute_query(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'schema_migrations'
            )""",
            fetch_one=True
        )
        
        if not migration_table_exists or not migration_table_exists.get('exists'):
            log_warning("schema_migrations table does not exist - creating it", "Migration")
            create_migration_tracking_table()
        
        log_info("Prerequisites check passed", "Migration")
        return True
        
    except Exception as e:
        log_error(f"Error checking prerequisites: {e}", "Migration", e)
        return False

def create_migration_tracking_table():
    """Create migration tracking table if it doesn't exist"""
    sql = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id SERIAL PRIMARY KEY,
        migration_id VARCHAR(255) UNIQUE NOT NULL,
        migration_name VARCHAR(500) NOT NULL,
        description TEXT,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        rollback_script TEXT,
        checksum VARCHAR(64)
    );
    """
    execute_query(sql)
    log_info("Created schema_migrations tracking table", "Migration")

def check_migration_applied() -> bool:
    """Check if this migration has already been applied"""
    try:
        result = execute_query(
            "SELECT id FROM schema_migrations WHERE migration_id = %s",
            (MIGRATION_ID,),
            fetch_one=True
        )
        return result is not None
    except Exception:
        return False

def record_migration():
    """Record that this migration has been applied"""
    try:
        execute_query(
            """INSERT INTO schema_migrations 
               (migration_id, migration_name, description, rollback_script)
               VALUES (%s, %s, %s, %s)""",
            (MIGRATION_ID, MIGRATION_NAME, MIGRATION_DESCRIPTION, get_rollback_script())
        )
        log_info(f"Recorded migration {MIGRATION_ID}", "Migration")
    except Exception as e:
        log_error(f"Error recording migration: {e}", "Migration", e)

def get_rollback_script() -> str:
    """Get SQL script to rollback this migration"""
    return """
    -- Rollback script for video processing tables migration
    DROP TABLE IF EXISTS user_processing_preferences CASCADE;
    DROP TABLE IF EXISTS processing_templates CASCADE;
    DROP TABLE IF EXISTS background_images CASCADE;
    DROP TABLE IF EXISTS uploaded_videos CASCADE;
    DROP TABLE IF EXISTS video_processing_jobs CASCADE;
    
    -- Remove migration record
    DELETE FROM schema_migrations WHERE migration_id = '20250711_001_add_video_processing_tables';
    """

def apply_migration() -> bool:
    """Apply the video processing tables migration"""
    try:
        log_info(f"Starting migration: {MIGRATION_ID}", "Migration")
        
        # Check prerequisites
        if not check_prerequisites():
            log_error("Migration prerequisites not met", "Migration")
            return False
        
        # Check if already applied
        if check_migration_applied():
            log_info("Migration already applied, skipping", "Migration")
            return True
        
        # Apply migration steps
        steps = [
            ("Create video_processing_jobs table", create_video_processing_jobs_table),
            ("Create uploaded_videos table", create_uploaded_videos_table),
            ("Create background_images table", create_background_images_table),
            ("Create processing_templates table", create_processing_templates_table),
            ("Create user_processing_preferences table", create_user_processing_preferences_table),
            ("Create database indexes", create_database_indexes),
            ("Insert default data", insert_default_migration_data),
            ("Validate schema", validate_migration_schema)
        ]
        
        for step_name, step_function in steps:
            try:
                log_info(f"Executing: {step_name}", "Migration")
                step_function()
                log_info(f"Completed: {step_name}", "Migration")
            except Exception as e:
                log_error(f"Failed at step '{step_name}': {e}", "Migration", e)
                return False
        
        # Record successful migration
        record_migration()
        
        log_info(f"Migration {MIGRATION_ID} completed successfully", "Migration")
        return True
        
    except Exception as e:
        log_error(f"Migration failed: {e}", "Migration", e)
        return False

def create_video_processing_jobs_table():
    """Create video_processing_jobs table"""
    sql = """
    CREATE TABLE IF NOT EXISTS video_processing_jobs (
        id SERIAL PRIMARY KEY,
        job_id VARCHAR(255) UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        job_type VARCHAR(100) NOT NULL DEFAULT 'background_replacement',
        input_path TEXT NOT NULL,
        output_path TEXT,
        config JSONB,
        status VARCHAR(50) NOT NULL DEFAULT 'pending',
        progress DECIMAL(5,2) DEFAULT 0.0,
        message TEXT,
        error_message TEXT,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Processing metrics
        processing_time_seconds INTEGER,
        file_size_mb DECIMAL(10,2),
        video_duration_seconds DECIMAL(10,2),
        frames_processed INTEGER,
        segmentation_model VARCHAR(50),
        quality_setting VARCHAR(20),
        
        -- Constraints
        CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
        CONSTRAINT valid_progress CHECK (progress >= 0.0 AND progress <= 100.0),
        CONSTRAINT valid_job_type CHECK (job_type IN ('background_replacement', 'segmentation', 'enhancement', 'format_conversion'))
    );
    """
    execute_query(sql)

def create_uploaded_videos_table():
    """Create uploaded_videos table"""
    sql = """
    CREATE TABLE IF NOT EXISTS uploaded_videos (
        id SERIAL PRIMARY KEY,
        video_id VARCHAR(255) UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        filename VARCHAR(500) NOT NULL,
        original_filename VARCHAR(500) NOT NULL,
        file_path TEXT NOT NULL,
        file_size_bytes BIGINT NOT NULL,
        size_mb DECIMAL(10,2) NOT NULL,
        mime_type VARCHAR(100),
        
        -- Video properties
        duration_seconds DECIMAL(10,2),
        width INTEGER,
        height INTEGER,
        fps DECIMAL(6,2),
        codec VARCHAR(50),
        bitrate_kbps INTEGER,
        
        -- File management
        storage_location VARCHAR(100) DEFAULT 'local',
        is_processed BOOLEAN DEFAULT FALSE,
        is_archived BOOLEAN DEFAULT FALSE,
        
        -- Timestamps
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT valid_size CHECK (size_mb > 0 AND size_mb <= 2000),
        CONSTRAINT valid_dimensions CHECK (width > 0 AND height > 0),
        CONSTRAINT valid_duration CHECK (duration_seconds >= 0)
    );
    """
    execute_query(sql)

def create_background_images_table():
    """Create background_images table"""
    sql = """
    CREATE TABLE IF NOT EXISTS background_images (
        id SERIAL PRIMARY KEY,
        bg_id VARCHAR(255) UNIQUE NOT NULL,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        filename VARCHAR(500) NOT NULL,
        original_filename VARCHAR(500) NOT NULL,
        file_path TEXT NOT NULL,
        file_size_bytes BIGINT NOT NULL,
        size_mb DECIMAL(10,2) NOT NULL,
        mime_type VARCHAR(100),
        
        -- Image properties
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        aspect_ratio DECIMAL(8,4),
        color_profile VARCHAR(50),
        
        -- Categorization
        category VARCHAR(100) DEFAULT 'custom',
        tags TEXT[],
        is_public BOOLEAN DEFAULT FALSE,
        is_template BOOLEAN DEFAULT FALSE,
        
        -- Usage tracking
        usage_count INTEGER DEFAULT 0,
        last_used TIMESTAMP,
        
        -- File management
        storage_location VARCHAR(100) DEFAULT 'local',
        thumbnail_path TEXT,
        
        -- Timestamps
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT valid_bg_size CHECK (size_mb > 0 AND size_mb <= 100),
        CONSTRAINT valid_bg_dimensions CHECK (width > 0 AND height > 0),
        CONSTRAINT valid_category CHECK (category IN ('custom', 'office', 'nature', 'abstract', 'gradient', 'solid'))
    );
    """
    execute_query(sql)

def create_processing_templates_table():
    """Create processing_templates table"""
    sql = """
    CREATE TABLE IF NOT EXISTS processing_templates (
        id SERIAL PRIMARY KEY,
        template_id VARCHAR(255) UNIQUE NOT NULL,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        template_name VARCHAR(200) NOT NULL,
        description TEXT,
        
        -- Template configuration
        template_config JSONB NOT NULL,
        background_config JSONB,
        quality_settings JSONB,
        
        -- Template properties
        category VARCHAR(100) DEFAULT 'custom',
        is_public BOOLEAN DEFAULT FALSE,
        is_premium BOOLEAN DEFAULT FALSE,
        
        -- Usage tracking
        usage_count INTEGER DEFAULT 0,
        rating DECIMAL(3,2) DEFAULT 0.0,
        
        -- Preview
        preview_image_path TEXT,
        preview_video_path TEXT,
        
        -- Timestamps
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT valid_rating CHECK (rating >= 0.0 AND rating <= 5.0)
    );
    """
    execute_query(sql)

def create_user_processing_preferences_table():
    """Create user_processing_preferences table"""
    sql = """
    CREATE TABLE IF NOT EXISTS user_processing_preferences (
        id SERIAL PRIMARY KEY,
        user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        
        -- Default processing settings
        default_quality VARCHAR(20) DEFAULT 'medium',
        preferred_segmentation_model VARCHAR(50) DEFAULT 'auto',
        preserve_audio BOOLEAN DEFAULT TRUE,
        
        -- Quality preferences
        feather_radius INTEGER DEFAULT 3,
        sharpen_strength DECIMAL(3,2) DEFAULT 0.5,
        edge_enhancement BOOLEAN DEFAULT TRUE,
        temporal_smoothing BOOLEAN DEFAULT FALSE,
        
        -- File management preferences
        auto_delete_input BOOLEAN DEFAULT FALSE,
        auto_delete_days INTEGER DEFAULT 30,
        notification_email BOOLEAN DEFAULT TRUE,
        
        -- Usage limits and quotas
        monthly_processing_quota INTEGER DEFAULT 10,
        monthly_usage_count INTEGER DEFAULT 0,
        last_quota_reset DATE DEFAULT CURRENT_DATE,
        
        -- Timestamps
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT valid_quality_pref CHECK (default_quality IN ('low', 'medium', 'high')),
        CONSTRAINT valid_feather_radius CHECK (feather_radius >= 0 AND feather_radius <= 10),
        CONSTRAINT valid_sharpen_strength CHECK (sharpen_strength >= 0.0 AND sharpen_strength <= 2.0),
        CONSTRAINT valid_quota CHECK (monthly_processing_quota >= 0)
    );
    """
    execute_query(sql)

def create_database_indexes():
    """Create all performance indexes"""
    indexes = [
        # Jobs table indexes
        "CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON video_processing_jobs(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON video_processing_jobs(status);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON video_processing_jobs(created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON video_processing_jobs(user_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_job_type ON video_processing_jobs(job_type);",
        
        # Uploaded videos indexes
        "CREATE INDEX IF NOT EXISTS idx_videos_user_id ON uploaded_videos(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_videos_uploaded_at ON uploaded_videos(uploaded_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_videos_user_uploaded ON uploaded_videos(user_id, uploaded_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_videos_processed ON uploaded_videos(is_processed);",
        "CREATE INDEX IF NOT EXISTS idx_videos_expires ON uploaded_videos(expires_at) WHERE expires_at IS NOT NULL;",
        
        # Background images indexes
        "CREATE INDEX IF NOT EXISTS idx_backgrounds_user_id ON background_images(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_backgrounds_category ON background_images(category);",
        "CREATE INDEX IF NOT EXISTS idx_backgrounds_public ON background_images(is_public) WHERE is_public = TRUE;",
        "CREATE INDEX IF NOT EXISTS idx_backgrounds_template ON background_images(is_template) WHERE is_template = TRUE;",
        "CREATE INDEX IF NOT EXISTS idx_backgrounds_usage ON background_images(usage_count DESC);",
        "CREATE INDEX IF NOT EXISTS idx_backgrounds_tags ON background_images USING GIN(tags);",
        
        # Templates indexes
        "CREATE INDEX IF NOT EXISTS idx_templates_user_id ON processing_templates(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_templates_public ON processing_templates(is_public) WHERE is_public = TRUE;",
        "CREATE INDEX IF NOT EXISTS idx_templates_category ON processing_templates(category);",
        "CREATE INDEX IF NOT EXISTS idx_templates_rating ON processing_templates(rating DESC);",
        
        # Preferences indexes
        "CREATE INDEX IF NOT EXISTS idx_preferences_user_id ON user_processing_preferences(user_id);"
    ]
    
    for index_sql in indexes:
        try:
            execute_query(index_sql)
        except Exception as e:
            log_warning(f"Index creation warning: {e}", "Migration")

def insert_default_migration_data():
    """Insert default data as part of migration"""
    try:
        # Insert system default backgrounds
        default_backgrounds = [
            {
                'bg_id': 'system_office_professional',
                'filename': 'professional_office.jpg',
                'original_filename': 'Professional Office Background',
                'file_path': '/static/backgrounds/system/professional_office.jpg',
                'file_size_bytes': 1048576,
                'size_mb': 1.0,
                'width': 1920,
                'height': 1080,
                'category': 'office',
                'is_public': True,
                'is_template': True,
                'tags': ['office', 'professional', 'modern', 'business']
            },
            {
                'bg_id': 'system_gradient_blue',
                'filename': 'gradient_blue.jpg', 
                'original_filename': 'Blue Gradient Background',
                'file_path': '/static/backgrounds/system/gradient_blue.jpg',
                'file_size_bytes': 524288,
                'size_mb': 0.5,
                'width': 1920,
                'height': 1080,
                'category': 'gradient',
                'is_public': True,
                'is_template': True,
                'tags': ['gradient', 'blue', 'clean', 'minimal']
            },
            {
                'bg_id': 'system_solid_white',
                'filename': 'solid_white.jpg',
                'original_filename': 'Pure White Background',
                'file_path': '/static/backgrounds/system/solid_white.jpg',
                'file_size_bytes': 102400,
                'size_mb': 0.1,
                'width': 1920,
                'height': 1080,
                'category': 'solid',
                'is_public': True,
                'is_template': True,
                'tags': ['white', 'clean', 'minimal', 'professional']
            }
        ]
        
        for bg in default_backgrounds:
            # Check if already exists
            existing = execute_query(
                "SELECT id FROM background_images WHERE bg_id = %s",
                (bg['bg_id'],),
                fetch_one=True
            )
            
            if not existing:
                execute_query(
                    """INSERT INTO background_images 
                       (bg_id, user_id, filename, original_filename, file_path, file_size_bytes, 
                        size_mb, width, height, category, is_public, is_template, tags, aspect_ratio)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (bg['bg_id'], None, bg['filename'], bg['original_filename'],
                     bg['file_path'], bg['file_size_bytes'], bg['size_mb'], bg['width'],
                     bg['height'], bg['category'], bg['is_public'], bg['is_template'], 
                     bg['tags'], 1.777)  # 16:9 aspect ratio
                )
        
        # Insert default processing template
        default_template = {
            'template_id': 'system_professional_quality',
            'template_name': 'Professional Quality Processing',
            'description': 'High-quality background replacement optimized for professional videos',
            'template_config': {
                'quality': 'high',
                'segmentation_model': 'rvm',
                'feather_radius': 5,
                'sharpen_strength': 0.8,
                'edge_enhancement': True,
                'temporal_smoothing': True,
                'preserve_audio': True
            },
            'category': 'professional',
            'is_public': True
        }
        
        existing_template = execute_query(
            "SELECT id FROM processing_templates WHERE template_id = %s",
            (default_template['template_id'],),
            fetch_one=True
        )
        
        if not existing_template:
            execute_query(
                """INSERT INTO processing_templates 
                   (template_id, user_id, template_name, description, template_config, category, is_public)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (default_template['template_id'], None, default_template['template_name'],
                 default_template['description'], default_template['template_config'],
                 default_template['category'], default_template['is_public'])
            )
        
        log_info("Inserted default migration data", "Migration")
        
    except Exception as e:
        log_warning(f"Error inserting default data: {e}", "Migration")

def validate_migration_schema() -> bool:
    """Validate that migration was successful"""
    try:
        required_tables = [
            'video_processing_jobs',
            'uploaded_videos',
            'background_images',
            'processing_templates', 
            'user_processing_preferences'
        ]
        
        for table in required_tables:
            exists = execute_query(
                """SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )""",
                (table,),
                fetch_one=True
            )
            
            if not exists or not exists['exists']:
                log_error(f"Table {table} was not created", "Migration")
                return False
        
        log_info("Migration schema validation passed", "Migration")
        return True
        
    except Exception as e:
        log_error(f"Error validating migration schema: {e}", "Migration", e)
        return False

def rollback_migration() -> bool:
    """Rollback this migration"""
    try:
        log_warning(f"Rolling back migration: {MIGRATION_ID}", "Migration")
        
        # Execute rollback script
        rollback_script = get_rollback_script()
        
        # Split and execute each statement
        statements = [stmt.strip() for stmt in rollback_script.split(';') if stmt.strip()]
        
        for statement in statements:
            if statement and not statement.startswith('--'):
                execute_query(statement)
        
        log_warning(f"Migration {MIGRATION_ID} rolled back successfully", "Migration")
        return True
        
    except Exception as e:
        log_error(f"Error rolling back migration: {e}", "Migration", e)
        return False

def get_migration_status() -> Dict[str, Any]:
    """Get status of this migration"""
    try:
        # Check if applied
        is_applied = check_migration_applied()
        
        # Get table info if applied
        tables_info = {}
        if is_applied:
            tables = ['video_processing_jobs', 'uploaded_videos', 'background_images', 
                     'processing_templates', 'user_processing_preferences']
            
            for table in tables:
                try:
                    count = execute_query(f"SELECT COUNT(*) as count FROM {table}", fetch_one=True)
                    tables_info[table] = count['count'] if count else 0
                except Exception:
                    tables_info[table] = "error"
        
        return {
            "migration_id": MIGRATION_ID,
            "name": MIGRATION_NAME,
            "description": MIGRATION_DESCRIPTION,
            "is_applied": is_applied,
            "tables_info": tables_info,
            "can_rollback": is_applied
        }
        
    except Exception as e:
        return {
            "migration_id": MIGRATION_ID,
            "error": str(e)
        }

# CLI interface for manual migration management
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "apply":
            success = apply_migration()
            sys.exit(0 if success else 1)
        elif command == "rollback":
            success = rollback_migration()
            sys.exit(0 if success else 1)
        elif command == "status":
            status = get_migration_status()
            print(f"Migration Status: {status}")
            sys.exit(0)
        else:
            print("Usage: python add_video_processing_tables.py [apply|rollback|status]")
            sys.exit(1)
    else:
        # Default action: apply migration
        success = apply_migration()
        sys.exit(0 if success else 1)
