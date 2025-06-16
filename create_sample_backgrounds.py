import os
import numpy as np
import cv2
import sqlite3
import json

def create_gradient_image(width, height, color1, color2, direction="horizontal"):
    """Create a gradient background image"""
    img = np.zeros((height, width, 3), np.uint8)
    
    if direction == "horizontal":
        for x in range(width):
            alpha = x / width
            color = tuple([(1-alpha)*c1 + alpha*c2 for c1, c2 in zip(color1, color2)])
            cv2.line(img, (x, 0), (x, height), color, 1)
    else:  # vertical
        for y in range(height):
            alpha = y / height
            color = tuple([(1-alpha)*c1 + alpha*c2 for c1, c2 in zip(color1, color2)])
            cv2.line(img, (0, y), (width, y), color, 1)
            
    return img

def create_pattern_image(width, height, pattern_type="grid", color=(255, 255, 255), bg_color=(0, 0, 0)):
    """Create a patterned background"""
    img = np.zeros((height, width, 3), np.uint8)
    img[:] = bg_color
    
    if pattern_type == "grid":
        # Draw a grid pattern
        grid_size = 50
        for x in range(0, width, grid_size):
            cv2.line(img, (x, 0), (x, height), color, 1)
        for y in range(0, height, grid_size):
            cv2.line(img, (0, y), (width, y), color, 1)
    
    elif pattern_type == "dots":
        # Draw a dots pattern
        spacing = 30
        radius = 3
        for x in range(spacing, width, spacing):
            for y in range(spacing, height, spacing):
                cv2.circle(img, (x, y), radius, color, -1)
                
    return img

def create_sample_backgrounds():
    """Create and save sample background images"""
    # Create directory if it doesn't exist
    backgrounds_dir = os.path.join("static", "backgrounds")
    os.makedirs(backgrounds_dir, exist_ok=True)
    
    # Define image size
    width, height = 1280, 720
    
    # Create and save different backgrounds
    backgrounds = [
        {
            "name": "Blue Gradient",
            "description": "Smooth blue gradient background",
            "filename": "blue_gradient.jpg",
            "category": "Gradient",
            "is_default": True,
            "func": lambda: create_gradient_image(width, height, (255, 128, 0), (0, 128, 255), "horizontal")
        },
        {
            "name": "Green Gradient",
            "description": "Smooth green gradient background",
            "filename": "green_gradient.jpg",
            "category": "Gradient",
            "is_default": True,
            "func": lambda: create_gradient_image(width, height, (0, 150, 50), (150, 255, 150), "vertical")
        },
        {
            "name": "Red Sunset",
            "description": "Red to orange sunset-like gradient",
            "filename": "red_sunset.jpg",
            "category": "Gradient",
            "is_default": True,
            "func": lambda: create_gradient_image(width, height, (50, 50, 200), (200, 50, 50), "vertical")
        },
        {
            "name": "Dark Grid",
            "description": "Dark background with white grid lines",
            "filename": "dark_grid.jpg",
            "category": "Pattern",
            "is_default": True,
            "func": lambda: create_pattern_image(width, height, "grid", (100, 100, 100), (30, 30, 30))
        },
        {
            "name": "Light Dots",
            "description": "Light background with dot pattern",
            "filename": "light_dots.jpg",
            "category": "Pattern",
            "is_default": True,
            "func": lambda: create_pattern_image(width, height, "dots", (80, 80, 80), (220, 220, 220))
        },
        {
            "name": "Pure White",
            "description": "Clean white background",
            "filename": "white.jpg",
            "category": "Solid",
            "is_default": True,
            "func": lambda: np.ones((height, width, 3), np.uint8) * 255
        },
        {
            "name": "Pure Black",
            "description": "Clean black background",
            "filename": "black.jpg",
            "category": "Solid",
            "is_default": True, 
            "func": lambda: np.zeros((height, width, 3), np.uint8)
        }
    ]
    
    # Generate and save each background
    for bg in backgrounds:
        img = bg["func"]()
        filepath = os.path.join(backgrounds_dir, bg["filename"])
        
        # Also create a thumbnail
        thumbnail = cv2.resize(img, (320, 180))
        thumbnail_path = os.path.join(backgrounds_dir, f"thumb_{bg['filename']}")
        
        # Save both images
        cv2.imwrite(filepath, img)
        cv2.imwrite(thumbnail_path, thumbnail)
        print(f"Created {bg['name']} at {filepath}")
        
    # Return background data for database insertion
    return [
        {
            "name": bg["name"],
            "description": bg["description"],
            "category": bg["category"],
            "filepath": f"static/backgrounds/{bg['filename']}",
            "thumbnail_path": f"static/backgrounds/thumb_{bg['filename']}",
            "is_default": bg["is_default"]
        }
        for bg in backgrounds
    ]

def insert_backgrounds_into_db(backgrounds_data, db_path):
    """Insert background records into the database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the backgrounds table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backgrounds'")
        if cursor.fetchone() is None:
            print("Backgrounds table doesn't exist yet. Please run the app first to initialize the schema.")
            return
            
        # Insert each background
        for bg in backgrounds_data:
            cursor.execute(
                """
                INSERT INTO backgrounds 
                (name, description, category, filepath, thumbnail_path, is_default) 
                VALUES (?, ?, ?, ?, ?, ?)
                """, 
                (bg["name"], bg["description"], bg["category"], bg["filepath"], 
                 bg["thumbnail_path"], 1 if bg["is_default"] else 0)
            )
        
        conn.commit()
        print(f"Successfully inserted {len(backgrounds_data)} backgrounds into database")
    except Exception as e:
        print(f"Error inserting backgrounds into database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Creating sample background images...")
    backgrounds_data = create_sample_backgrounds()
    
    # Path to the database
    db_path = "database.db"
    
    # Insert the backgrounds into the database if it exists
    if os.path.exists(db_path):
        insert_backgrounds_into_db(backgrounds_data, db_path)
    else:
        print(f"Database file {db_path} not found. You can import these backgrounds later.")
        
    print("Done!")
