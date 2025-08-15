"""
Script to generate a .env.example file for MyAvatar based on libraryFX configuration
"""
import os
import sys
from pathlib import Path

# Add libraryFX to path
LIBRARY_FX_PATH = os.path.join(Path.home(), "Projects", "Python", "libraryFX")
if os.path.exists(LIBRARY_FX_PATH):
    sys.path.insert(0, LIBRARY_FX_PATH)
    # Also add core module path
    core_path = os.path.join(LIBRARY_FX_PATH, "core")
    if os.path.exists(core_path):
        sys.path.insert(0, core_path)

try:
    # Try to import from libraryFX
    from libraryFX.core.config import generate_env_example
    from libraryFX.core.config.defaults import CONFIG_DESCRIPTIONS
    
    using_library_fx = True
    print("Using libraryFX configuration system")
except ImportError:
    using_library_fx = False
    print("LibraryFX core module not found, using simplified template")

# MyAvatar specific configuration variables
MYAVATAR_CONFIG = {
    # Basic app configuration
    "APP_NAME": "MyAvatar",
    "DEBUG": "false",
    "PORT": "8000",
    "HOST": "0.0.0.0",
    
    # Background replacement service
    "ENABLE_BACKGROUND_REPLACEMENT": "true",
    "BACKGROUNDFX_URL": "http://localhost:5000",
    
    # Video processing settings
    "VIDEO_PROCESSING_ENABLED": "true",
    "MAX_VIDEO_LENGTH_SEC": "180",
    
    # Storage paths
    "UPLOAD_FOLDER": "./uploads",
    "OUTPUT_FOLDER": "./output",
    
    # HeyGen API (used for avatar generation)
    "HEYGEN_API_KEY": "<your-heygen-api-key>",
    "HEYGEN_API_URL": "https://api.heygen.com/v1",
    
    # If using S3 for storage
    "S3_BUCKET": "",
    "S3_REGION": "",
    "AWS_ACCESS_KEY_ID": "",
    "AWS_SECRET_ACCESS_KEY": "",
}

def generate_myavatar_env_template():
    """Generate a .env.example file for MyAvatar"""
    if using_library_fx:
        # Use libraryFX's config system
        env_content = generate_env_example(
            additional_configs=MYAVATAR_CONFIG,
            include_categories=["core", "notifications", "media"]
        )
    else:
        # Simple fallback generation
        env_content = "# MyAvatar Environment Variables\n\n"
        for key, value in MYAVATAR_CONFIG.items():
            env_content += f"# {key}: MyAvatar specific setting\n"
            env_content += f"{key}={value}\n\n"
    
    # Write the file
    with open(".env.example", "w") as f:
        f.write(env_content)
    
    print(f"Created .env.example file with {len(MYAVATAR_CONFIG)} MyAvatar-specific variables")
    if using_library_fx:
        print("Plus additional variables from libraryFX configuration")
    
    print("\nTo use this template, copy it to .env and fill in your actual values:")
    print("cp .env.example .env")

if __name__ == "__main__":
    generate_myavatar_env_template()
