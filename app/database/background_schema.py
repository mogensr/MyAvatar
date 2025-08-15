"""
Database schema for background images in MyAvatar
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# SQL statements for creating the backgrounds table
CREATE_BACKGROUNDS_TABLE = """
CREATE TABLE IF NOT EXISTS backgrounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    file_path TEXT NOT NULL,
    thumbnail_path TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# SQL statement to add background relationship to videos table
ALTER_VIDEOS_TABLE = """
ALTER TABLE videos ADD COLUMN background_id INTEGER DEFAULT NULL;
"""

def initialize_backgrounds_schema():
    """
    Deprecated. All background schema management is now handled via PostgreSQL migrations. This function is no longer implemented.
    """
    raise NotImplementedError("Background schema is managed via PostgreSQL migrations only.")

# Deprecated: SQLite-only background schema logic removed (Postgres enforced)
def add_default_backgrounds(db_path, backgrounds_dir):
    raise NotImplementedError("This function is deprecated: background schema is now managed via PostgreSQL migrations.")
    """
    Add default background images to the backgrounds table
    
    Args:
        db_path: Path to the SQLite database
        backgrounds_dir: Directory containing default background images
    """
    if not os.path.exists(backgrounds_dir):
        os.makedirs(backgrounds_dir, exist_ok=True)
        logger.info(f"Created backgrounds directory: {backgrounds_dir}")
    
    # Default backgrounds to add
    default_backgrounds = [
        {
            "name": "Blue Gradient",
            "description": "Smooth blue gradient background",
            "category": "Gradient",
            "file_name": "blue_gradient.jpg",
            "is_default": 1
        },
        {
            "name": "Office",
            "description": "Professional office setting",
            "category": "Office",
            "file_name": "office.jpg",
            "is_default": 1
        },
        {
            "name": "Neutral",
            "description": "Neutral gray background",
            "category": "Solid",
            "file_name": "neutral.jpg",
            "is_default": 1
        },
        {
            "name": "Green Screen",
            "description": "Classic green screen for custom effects",
            "category": "Special",
            "file_name": "green_screen.jpg",
            "is_default": 1
        }
    ]
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for bg in default_backgrounds:
            # Check if background already exists
            cursor.execute(
                "SELECT id FROM backgrounds WHERE name = ? AND is_default = 1",
                (bg["name"],)
            )
            result = cursor.fetchone()
            
            if not result:
                file_path = os.path.join(backgrounds_dir, bg["file_name"])
                thumbnail_path = os.path.join(backgrounds_dir, f"thumb_{bg['file_name']}")
                
                # Insert background record
                cursor.execute(
                    """
                    INSERT INTO backgrounds (name, description, category, file_path, 
                                            thumbnail_path, is_default)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (bg["name"], bg["description"], bg["category"], 
                     file_path, thumbnail_path, bg["is_default"])
                )
                logger.info(f"Added default background: {bg['name']}")
        
        conn.commit()
        conn.close()
        logger.info("Default backgrounds added successfully")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Database error adding default backgrounds: {e}")
        return False
    except Exception as e:
        logger.error(f"Error adding default backgrounds: {e}")
        return False
