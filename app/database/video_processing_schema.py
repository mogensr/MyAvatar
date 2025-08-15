"""
Database Schema for Video Processing System
Creates tables for background replacement functionality
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# MyAvatar imports
from app.db.database import execute_query, get_db_connection
from app.logger.log_handler import log_info, log_error, log_warning

logger = logging.getLogger(__name__)

def create_video_processing_tables():
    """
    Create all tables required for video processing functionality
    """
    try:
        log_info("Creating video processing database tables", "VideoProcessingSchema")
        
        # Table 1: Video Processing Jobs
        create_jobs_table()
        
        # Table 2: Uploaded Videos
        create_uploaded_videos_table()
        
        # Table 3: Background Images
        create_background_images_table()
        
        # Table 4: Processing Templates (for future use)
        create_processing_templates_table()
        
        # Table 5: User Processing Preferences
        create_user_preferences_table()
        
        # Create indexes for performance
        create_indexes()
        
        # Insert default data
        insert_default_data()
        
        log_info("Video processing database schema created successfully", "VideoProcessingSchema")
        return True
        
    except Exception as e:
        log_error(f"Error creating video processing schema: {e}", "VideoProcessingSchema", e)
        return False

def create_jobs_table():
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
    log_info("Created video_processing_jobs table", "VideoProcessingSchema")

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
    log_info("Created uploaded_videos table", "VideoProcessingSchema")

def create_background_images_table():
    """Create background_images table"""
    sql = """
    CREATE TABLE IF NOT EXISTS background_images (
        id SERIAL PRIMARY KEY,
        bg_id VARCHAR(255) UNIQUE NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
    log_info("Created background_images table", "VideoProcessingSchema")

def create_processing_templates_table():
    """Create processing_templates table for future use"""
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
    log_info("Created processing_templates table", "VideoProcessingSchema")

def create_user_preferences_table():
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
    log_info("Created user_processing_preferences table", "VideoProcessingSchema")

def create_indexes():
    """Create indexes for optimal performance"""
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
        "CREATE INDEX IF NOT EXISTS idx_preferences_user_id ON user_processing_preferences(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_preferences_quota_reset ON user_processing_preferences(last_quota_reset);"
    ]
    
    for index_sql in indexes:
        try:
            execute_query(index_sql)
        except Exception as e:
            log_warning(f"Failed to create index: {e}", "VideoProcessingSchema")
    
    log_info("Created database indexes", "VideoProcessingSchema")

def insert_default_data():
    """Insert default data and templates"""
    try:
        # Insert default background categories
        default_backgrounds = [
            {
                'bg_id': 'default_office_1',
                'user_id': None,  # System template
                'filename': 'modern_office.jpg',
                'original_filename': 'Modern Office Background',
                'file_path': '/static/backgrounds/office/modern_office.jpg',
                'file_size_bytes': 1048576,
                'size_mb': 1.0,
                'width': 1920,
                'height': 1080,
                'category': 'office',
                'is_public': True,
                'is_template': True,
                'tags': ['office', 'professional', 'modern']
            },
            {
                'bg_id': 'default_gradient_1',
                'user_id': None,
                'filename': 'blue_gradient.jpg',
                'original_filename': 'Blue Gradient Background',
                'file_path': '/static/backgrounds/gradient/blue_gradient.jpg',
                'file_size_bytes': 524288,
                'size_mb': 0.5,
                'width': 1920,
                'height': 1080,
                'category': 'gradient',
                'is_public': True,
                'is_template': True,
                'tags': ['gradient', 'blue', 'clean']
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
                        size_mb, width, height, category, is_public, is_template, tags)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (bg['bg_id'], bg['user_id'], bg['filename'], bg['original_filename'],
                     bg['file_path'], bg['file_size_bytes'], bg['size_mb'], bg['width'],
                     bg['height'], bg['category'], bg['is_public'], bg['is_template'], bg['tags'])
                )
        
        # Insert default processing template
        default_template = {
            'template_id': 'default_professional',
            'template_name': 'Professional Background Replacement',
            'description': 'High-quality background replacement with edge enhancement',
            'template_config': {
                'quality': 'high',
                'segmentation_model': 'rvm',
                'feather_radius': 5,
                'sharpen_strength': 0.8,
                'edge_enhancement': True,
                'temporal_smoothing': True
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
                   (template_id, template_name, description, template_config, category, is_public)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (default_template['template_id'], default_template['template_name'],
                 default_template['description'], default_template['template_config'],
                 default_template['category'], default_template['is_public'])
            )
        
        log_info("Inserted default data", "VideoProcessingSchema")
        
    except Exception as e:
        log_warning(f"Error inserting default data: {e}", "VideoProcessingSchema")

def drop_video_processing_tables():
    """Drop all video processing tables (for development/testing)"""
    try:
        log_warning("Dropping video processing database tables", "VideoProcessingSchema")
        
        tables = [
            'user_processing_preferences',
            'processing_templates',
            'background_images',
            'uploaded_videos',
            'video_processing_jobs'
        ]
        
        for table in tables:
            execute_query(f"DROP TABLE IF EXISTS {table} CASCADE;")
        
        log_warning("Video processing tables dropped", "VideoProcessingSchema")
        return True
        
    except Exception as e:
        log_error(f"Error dropping tables: {e}", "VideoProcessingSchema", e)
        return False

def get_table_info():
    """Get information about video processing tables"""
    try:
        tables_info = {}
        
        tables = [
            'video_processing_jobs',
            'uploaded_videos', 
            'background_images',
            'processing_templates',
            'user_processing_preferences'
        ]
        
        for table in tables:
            # Get table size and row count
            size_info = execute_query(
                f"""SELECT 
                    COUNT(*) as row_count,
                    pg_size_pretty(pg_total_relation_size('{table}')) as table_size
                FROM {table}""",
                fetch_one=True
            )
            
            if size_info:
                tables_info[table] = {
                    'row_count': size_info['row_count'],
                    'table_size': size_info['table_size']
                }
        
        return tables_info
        
    except Exception as e:
        log_error(f"Error getting table info: {e}", "VideoProcessingSchema", e)
        return {}

def validate_schema():
    """Validate that all required tables and indexes exist"""
    try:
        required_tables = [
            'video_processing_jobs',
            'uploaded_videos',
            'background_images', 
            'processing_templates',
            'user_processing_preferences'
        ]
        
        missing_tables = []
        
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
                missing_tables.append(table)
        
        if missing_tables:
            log_error(f"Missing tables: {missing_tables}", "VideoProcessingSchema")
            return False
        
        log_info("Video processing schema validation passed", "VideoProcessingSchema")
        return True
        
    except Exception as e:
        log_error(f"Error validating schema: {e}", "VideoProcessingSchema", e)
        return False

# Convenience function for initialization
def initialize_video_processing_schema():
    """Initialize the complete video processing database schema"""
    try:
        log_info("Initializing video processing database schema", "VideoProcessingSchema")
        
        # Create tables
        success = create_video_processing_tables()
        
        if success:
            # Validate schema
            if validate_schema():
                log_info("Video processing schema initialized successfully", "VideoProcessingSchema")
                return True
            else:
                log_error("Schema validation failed after creation", "VideoProcessingSchema")
                return False
        else:
            log_error("Failed to create video processing tables", "VideoProcessingSchema")
            return False
            
    except Exception as e:
        log_error(f"Error initializing video processing schema: {e}", "VideoProcessingSchema", e)
        return False

# Run initialization if called directly
if __name__ == "__main__":
    initialize_video_processing_schema()
