"""
Enhanced logging system for MyAvatar
"""
from collections import deque
import logging
import traceback
from datetime import datetime

logger = logging.getLogger("MyAvatar")

class LogHandler:
    def __init__(self, max_logs=1000):
        self.logs = deque(maxlen=max_logs)
        self.max_logs = max_logs
    
    def add_log(self, level: str, message: str, module: str = "System"):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "module": module,
            "message": message
        }
        self.logs.append(log_entry)
        
        if level == "ERROR":
            logger.error(f"[{module}] {message}")
        elif level == "WARNING":
            logger.warning(f"[{module}] {message}")
        else:
            logger.info(f"[{module}] {message}")
    
    def get_recent_logs(self, limit: int = 100):
        return list(self.logs)[-limit:]
    
    def get_error_logs(self, limit: int = 50):
        error_logs = [log for log in self.logs if log["level"] == "ERROR"]
        return error_logs[-limit:]

# Create a global instance
log_handler = LogHandler()

def log_info(message: str, module: str = "System"):
    log_handler.add_log("INFO", message, module)

def log_error(message: str, module: str = "System", exception: Exception = None):
    if exception:
        error_details = f"{message}: {str(exception)}"
        log_handler.add_log("ERROR", error_details, module)
        log_handler.add_log("ERROR", f"Traceback: {traceback.format_exc()}", module)
    else:
        log_handler.add_log("ERROR", message, module)

def log_warning(message: str, module: str = "System"):
    log_handler.add_log("WARNING", message, module)
