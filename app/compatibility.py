"""
Compatibility module to enable safe mode running without heavy dependencies
"""
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get environment settings
ENABLE_SAFE_MODE = os.environ.get("ENABLE_SAFE_MODE", "false").lower() in ("true", "1", "yes")

# Feature flags
ENABLE_BACKGROUND_REPLACEMENT = not ENABLE_SAFE_MODE

def log_compatibility_status():
    """Log the current compatibility mode status"""
    if ENABLE_SAFE_MODE:
        logger.warning("⚠️ Running in SAFE MODE - Some features are disabled")
        logger.warning("Background replacement is disabled in safe mode")
    else:
        logger.info("Running with all features enabled")
        
    return {
        "safe_mode": ENABLE_SAFE_MODE,
        "background_replacement_enabled": ENABLE_BACKGROUND_REPLACEMENT
    }
