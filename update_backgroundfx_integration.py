"""
Update script to integrate the BackgroundFX microservice with MyAvatar
This script will update the necessary files to use the new BackgroundFX client
"""
import os
import sys
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BackgroundFX-Integration")

def update_env_file():
    """Update or create the .env file with BackgroundFX service URL"""
    env_path = ".env"
    env_example_path = ".env.example"
    
    # Create .env file from example if it doesn't exist
    if not os.path.exists(env_path) and os.path.exists(env_example_path):
        shutil.copy(env_example_path, env_path)
        logger.info(f"Created {env_path} from {env_example_path}")
    
    # Check if BackgroundFX service URL is already in .env
    backgroundfx_url_found = False
    
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_contents = f.read()
            backgroundfx_url_found = "BACKGROUNDFX_SERVICE_URL" in env_contents
    
    # Add BackgroundFX service URL if not found
    if not backgroundfx_url_found:
        with open(env_path, "a") as f:
            f.write("\n# BackgroundFX Microservice\n")
            f.write("BACKGROUNDFX_SERVICE_URL=http://localhost:5000\n")
        logger.info("Added BackgroundFX service URL to .env file")
    else:
        logger.info("BackgroundFX service URL already in .env file")

def update_background_routes():
    """Update the background_routes.py file to use the new BackgroundFX client"""
    routes_path = os.path.join("app", "routes", "background_routes.py")
    
    if not os.path.exists(routes_path):
        logger.error(f"Background routes file not found: {routes_path}")
        return False
    
    # Read the current file
    with open(routes_path, "r") as f:
        content = f.read()
    
    # Check if already updated
    if "backgroundfx_client_v2" in content:
        logger.info("Background routes already using BackgroundFX client v2")
        return True
    
    # Make a backup
    backup_path = routes_path + ".bak"
    shutil.copy(routes_path, backup_path)
    logger.info(f"Created backup of background_routes.py at {backup_path}")
    
    # Update import statements
    content = content.replace(
        "from app.video_enhancer.background_replacer import BackgroundReplacer",
        "# Using BackgroundFX microservice instead of local background replacement\n"
        "from app.services.backgroundfx_client_v2 import BackgroundFXClient"
    )
    
    # Update background replacement initialization
    content = content.replace(
        "background_replacer = BackgroundReplacer()",
        "# Initialize BackgroundFX client\nbackground_replacer = BackgroundFXClient()"
    )
    
    # Write the updated content
    with open(routes_path, "w") as f:
        f.write(content)
        
    logger.info(f"Updated {routes_path} to use BackgroundFX client")
    return True

def main():
    """Main update function"""
    logger.info("Starting BackgroundFX integration update")
    
    # Verify BackgroundFX client exists
    client_path = os.path.join("app", "services", "backgroundfx_client_v2.py")
    if not os.path.exists(client_path):
        logger.error(f"BackgroundFX client not found: {client_path}")
        return 1
    
    # Update .env file
    update_env_file()
    
    # Update background routes
    update_background_routes()
    
    logger.info(
        "\n=== BackgroundFX Integration Complete ===\n"
        "MyAvatar is now configured to use the BackgroundFX microservice for background replacement.\n"
        "Make sure the BackgroundFX microservice is running before using background replacement features.\n"
        "Start the microservice with: python app.py in the BackgroundFX directory.\n"
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
