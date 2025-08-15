import logging
import sys
from datetime import datetime

def setup_logger(name="MyAvatar", level="INFO"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, level.upper()))
    return logger

logger = setup_logger()

# Export the required log functions that other modules expect
def log_info(message, module="MyAvatar"):
    """Log info message"""
    logger.info(f"[{module}] {message}")

def log_error(message, module="MyAvatar", exception=None):
    """Log error message"""
    if exception:
        logger.error(f"[{module}] {message}", exc_info=exception)
    else:
        logger.error(f"[{module}] {message}")

def log_warning(message, module="MyAvatar"):
    """Log warning message"""
    logger.warning(f"[{module}] {message}")
